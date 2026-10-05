"""
PRNU: behavioural checks of the Goljan pipeline pieces, the MRF min-cut,
the entry point's status handling, and a small seeded benchmark on a
camera-like simulator (Bayer RGGB raw with PRNU, shot + read noise, OpenCV
bilinear demosaic, JPEG). Full hold-out numbers: Descriptions/PRNU.md.
"""
import itertools
import shutil
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from skimage import data

from analysis import prnu

N = 1024
SOURCES = [data.astronaut, data.coffee, data.chelsea, data.rocket, data.immunohistochemistry,
           data.retina, data.horse, data.brick, data.grass]


def scene(rng, n=N):
    a = np.asarray(SOURCES[rng.integers(len(SOURCES))](), np.float32)
    a = np.stack([a] * 3, -1) if a.ndim == 2 else a[..., :3]
    a = a * 255 if a.max() <= 1 else a
    s = n / min(a.shape[:2]) * rng.uniform(1.05, 1.4)
    a = cv2.resize(a, (int(a.shape[1] * s) + 1, int(a.shape[0] * s) + 1),
                   interpolation=cv2.INTER_CUBIC)
    y, x = rng.integers(0, a.shape[0] - n), rng.integers(0, a.shape[1] - n)
    return np.clip(a[y:y + n, x:x + n] * rng.uniform(0.6, 1.1), 0, 255)


def shoot(sc, k, rng, q=92):
    """Bayer RGGB raw · (1+K) + shot/read noise → bilinear demosaic → JPEG q
    (None = no compression) → grey, as load_array(…, "L") would see it."""
    raw = np.empty(k.shape, np.float32)
    raw[0::2, 0::2] = sc[0::2, 0::2, 0]
    raw[0::2, 1::2] = sc[0::2, 1::2, 1]
    raw[1::2, 0::2] = sc[1::2, 0::2, 1]
    raw[1::2, 1::2] = sc[1::2, 1::2, 2]
    raw *= 1 + k
    raw += rng.standard_normal(raw.shape, np.float32) * np.sqrt(0.3 * np.maximum(raw, 0) + 4)
    rgb = cv2.cvtColor(np.clip(raw, 0, 255).astype(np.uint8), cv2.COLOR_BayerRG2RGB)
    if q is not None:
        rgb = cv2.imdecode(cv2.imencode(".jpg", rgb, [cv2.IMWRITE_JPEG_QUALITY, q])[1], 1)
    return np.asarray(Image.fromarray(rgb).convert("L"), np.float32)


def _w(im):
    w = prnu.residual(im)
    return prnu.wiener_dft(w, float(w.std()))


class TestPipelinePieces(unittest.TestCase):
    def test_wiener_dft_removes_periodic_peaks(self):
        r = np.random.default_rng(1)
        white = r.normal(0, 1, (256, 256))
        yy, xx = np.mgrid[:256, :256]
        x = white + 0.5 * np.cos(2 * np.pi * xx / 8) + 0.5 * (-1.0) ** (yy + xx)
        f = np.abs(np.fft.fft2(prnu.wiener_dft(x, x.std())))
        f0 = np.abs(np.fft.fft2(x))
        for pos in [(0, 32), (128, 128)]:
            self.assertGreater(f0[pos] / np.median(f0), 50)
            self.assertLess(f[pos] / np.median(f), 3)
        self.assertGreater(prnu.ncc(prnu.wiener_dft(x, x.std()), white), 0.99)

    def test_zero_mean_total(self):
        z = prnu.zero_mean_total(np.random.default_rng(0).normal(5, 1, (64, 64)))
        for i in (0, 1):
            for j in (0, 1):
                s = z[i::2, j::2]
                self.assertLess(np.abs(s.mean(0)).max(), 1e-5)
                self.assertLess(np.abs(s.mean(1)).max(), 1e-5)

    def test_pce_same_vs_independent(self):
        r = np.random.default_rng(2)
        a, b = r.normal(size=(256, 256)), r.normal(size=(256, 256))
        self.assertGreater(prnu.pce(a, a + 3 * b), 1000)
        self.assertLess(abs(prnu.pce(a, b)), 30)

    def test_win_mean_matches_direct(self):
        x = np.random.default_rng(3).normal(size=(300, 260)).astype(np.float32)
        m = prnu._win_mean(x)
        self.assertEqual(m.shape, ((300 - 128) // 32 + 1, (260 - 128) // 32 + 1))
        self.assertAlmostEqual(m[2, 3], x[64:192, 96:224].mean(), places=5)

    def test_min_cut_is_exact(self):
        r = np.random.default_rng(4)

        def energy(u, lam, g, b):
            pairs = ((u[:, :-1], u[:, 1:]), (u[:-1], u[1:]),
                     (u[:-1, :-1], u[1:, 1:]), (u[:-1, 1:], u[1:, :-1]))
            return (u * (g - lam)).sum() + b * sum((p != q).sum() for p, q in pairs)

        for _ in range(20):
            h, w = r.integers(2, 4, 2)
            lam, t = r.normal(0, 3, (h, w)), r.random((h, w)) > 0.2
            g, b = r.uniform(0, 3), r.uniform(0, 2)
            lt = np.where(t, lam, 0)
            best = min(energy(np.array(c).reshape(h, w), lt, g, b)
                       for c in itertools.product([0, 1], repeat=h * w))
            u = prnu._min_cut(lam, t, g, b)
            self.assertLess(energy(u, lt, g, b) - best, 0.02 * h * w)


class TestEntryPoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = Path(tempfile.mkdtemp())
        rng = np.random.default_rng(7)
        k = rng.normal(0, 0.01, (N, N)).astype(np.float32)
        cls.refs = []
        for i in range(4):
            p = cls.d / f"ref{i}.png"
            Image.fromarray(shoot(scene(rng), k, rng, None).astype(np.uint8)).save(p)
            cls.refs.append(str(p))
        cls.test = str(cls.d / "test.png")
        Image.fromarray(shoot(scene(rng), k, rng, None).astype(np.uint8)).save(cls.test)
        # mostly saturated frame with a 64 px textured strip: the fingerprint
        # matches, but < 10 % of blocks are testable → the local test must
        # report "insufficient data", not "nothing found"
        cls.sat = []
        for i in range(5):
            sc = np.full((N, N, 3), 255.0)
            sc[-64:] = scene(rng)[-64:]
            p = cls.d / f"sat{i}.png"
            Image.fromarray(shoot(sc, k, rng, None).astype(np.uint8)).save(p)
            cls.sat.append(str(p))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.d, ignore_errors=True)

    def test_no_reference(self):
        r = prnu.analyze_prnu(self.test)
        self.assertEqual(r["status"], "ok")
        self.assertIn("no reference fingerprint", r["findings"][0]["text"].lower())
        self.assertNotIn("PCE", r["metrics"])

    def test_size_mismatch_not_applicable(self):
        p = self.d / "small.png"
        Image.open(self.refs[0]).crop((0, 0, 400, 400)).save(p)
        self.assertEqual(prnu.analyze_prnu(self.test, [str(p)])["status"], "not_applicable")

    def test_match_full_resolution_and_crop(self):
        r = prnu.analyze_prnu(self.test, self.refs)
        self.assertTrue(r["metrics"]["Analysed region (px)"].startswith(f"{N}×{N}"))
        self.assertGreater(r["metrics"]["PCE"], prnu.PCE_THRESHOLD)
        self.assertIn("Testable fraction (%)", r["metrics"])
        c = prnu.analyze_prnu(self.test, self.refs, max_px=512)
        self.assertTrue(c["metrics"]["Analysed region (px)"].startswith("512×512"))

    def test_mostly_saturated_local_test_insufficient(self):
        r = prnu.analyze_prnu(self.sat[0], self.sat[1:])
        self.assertGreater(r["metrics"]["PCE"], prnu.PCE_THRESHOLD)
        self.assertEqual(r["details"]["local_test"], "insufficient_data")
        self.assertTrue(any("insufficient data" in f["text"] for f in r["findings"]))
        self.assertFalse(any("no region lacking" in f["text"] for f in r["findings"]))

    def test_degenerate(self):
        p = self.d / "flat.png"
        Image.fromarray(np.full((256, 256), 128, np.uint8)).save(p)
        self.assertEqual(prnu.analyze_prnu(str(p))["status"], "insufficient_data")
        p = self.d / "tiny.png"
        Image.fromarray(np.zeros((16, 16), np.uint8)).save(p)
        self.assertEqual(prnu.analyze_prnu(str(p))["status"], "insufficient_data")


class TestCameraSimulatorBenchmark(unittest.TestCase):
    """2 simulated cameras (K std 0.01, JPEG q92, 1 MP) × 8 references × 3
    test shots. Matching: same camera PCE > 60, different camera never.
    Local test: no region on clean shots; a 384 px patch from the other
    camera (same scene) found in most matched shots."""

    @classmethod
    def setUpClass(cls):
        rng = np.random.default_rng(11)
        cls.ks = [rng.normal(0, 0.01, (N, N)).astype(np.float32) for _ in range(2)]
        cls.cams = []
        for k in cls.ks:
            refs = [shoot(scene(rng), k, rng) for _ in range(8)]
            num, den = prnu.accumulate(refs)
            train = prnu.train_predictor(refs, num, den)
            scenes = [scene(rng) for _ in range(3)]
            cls.cams.append(dict(k=prnu.finalize(num, den), train=train, scenes=scenes,
                                 tests=[shoot(s, k, rng) for s in scenes]))
        cls.rng = rng

    def test_same_vs_different_camera_pce(self):
        same, diff = [], []
        for c, cam in enumerate(self.cams):
            for im in cam["tests"]:
                w = _w(im)
                for d, other in enumerate(self.cams):
                    (same if c == d else diff).append(prnu.pce(w, im * other["k"]))
        self.assertGreaterEqual(np.mean(np.array(same) > prnu.PCE_THRESHOLD), 0.8, same)
        self.assertEqual(sum(p > prnu.PCE_THRESHOLD for p in diff), 0, diff)

    def test_local_splice_test(self):
        clean_fa, hits, n, P = 0, 0, 0, 384
        for c, cam in enumerate(self.cams):
            for j, im in enumerate(cam["tests"]):
                w = _w(im)
                if prnu.pce(w, im * cam["k"]) <= prnu.PCE_THRESHOLD:
                    continue
                n += 1
                clean_fa += prnu.local_test(im, w, cam["k"], cam["train"])["flagged"].any()
                y, x = 128 + 128 * j, 320
                foreign = shoot(cam["scenes"][j], self.ks[1 - c], self.rng)
                sp = im.copy()
                sp[y:y + P, x:x + P] = foreign[y:y + P, x:x + P]
                fl = prnu.local_test(sp, _w(sp), cam["k"], cam["train"])["flagged"]
                ys, xs = np.nonzero(fl)
                cy, cx = ys * 32 + 64, xs * 32 + 64
                hits += bool(((cy >= y) & (cy < y + P) & (cx >= x) & (cx < x + P)).any())
        self.assertGreaterEqual(n, 4)
        self.assertEqual(clean_fa, 0)
        self.assertGreaterEqual(hits / n, 0.5, f"{hits}/{n}")


if __name__ == "__main__":
    unittest.main()
