"""
Behavioural tests and a small seeded benchmark for the LSB steganalysis
module (WS / SPA / RS payload estimators, PoV sequential test).
"""
import io
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
import skimage.data as skd
from PIL import Image

from analysis import steganography_detection as S

SAMPLE = Path(__file__).resolve().parent.parent / "assets" / "sample images" / "sampleImg.jpeg"


def lsb_replace(a, p, rng, sequential=False):
    x = a.astype(np.int64).ravel().copy()
    if sequential:
        m = np.zeros(x.size, bool)
        m[: int(round(p * x.size))] = True
    else:
        m = rng.random(x.size) < p
    x[m] = (x[m] & ~1) | rng.integers(0, 2, m.sum())
    return x.reshape(a.shape).astype(np.uint8)


def lsb_match(a, p, rng):
    x = a.astype(np.int64).ravel().copy()
    bits = rng.integers(0, 2, x.size)
    need = (rng.random(x.size) < p) & ((x & 1) != bits)
    step = rng.choice([-1, 1], x.size)
    step[x == 0], step[x == 255] = 1, -1
    x[need] += step[need]
    return x.reshape(a.shape).astype(np.uint8)


def decode_jpeg(a, q):
    b = io.BytesIO()
    Image.fromarray(a).save(b, "JPEG", quality=q)
    return np.asarray(Image.open(io.BytesIO(b.getvalue())))


def score(a):
    a = np.asarray(a, np.int64)
    cs = [a] if a.ndim == 2 else [a[..., i] for i in range(3)]
    return max(S.channel_score(c) for c in cs)


class TestEstimators(unittest.TestCase):
    def test_estimators_track_true_payload(self):
        rng = np.random.default_rng(0)
        for name in ("astronaut", "camera", "coffee"):
            a = getattr(skd, name)()
            c = a[..., 1] if a.ndim == 3 else a
            for p in (0.0, 0.25, 0.5, 1.0):
                s = lsb_replace(c, p, rng).astype(np.int64)
                with self.subTest(name=name, p=p):
                    self.assertAlmostEqual(S.weighted_stego(s), p, delta=0.06)
                    self.assertAlmostEqual(S.spa(s), p, delta=0.06)
                    if p < 1.0:  # RS quadratic degenerates at p = 1
                        self.assertAlmostEqual(S.rs_analysis(s), p, delta=0.06)

    def test_saturated_cover_falls_back_to_spa(self):
        """Line art / binary covers: WS has no weights (or blows up), so the
        decision must be SPA, not min(WS, SPA) hiding the payload."""
        rng = np.random.default_rng(3)
        horse = skd.horse().astype(np.uint8) * 255
        checker = skd.checkerboard()
        for c in (horse, checker):
            for p in (0.1, 0.25):
                s = lsb_replace(c, p, rng)
                t = S.WSTerms(s)
                sc, rule = S.decision_score(t.estimate(), S.spa(s), t.valid)
                self.assertEqual(rule, "SPA (WS unreliable)")
                self.assertAlmostEqual(sc, p, delta=0.05)

    def test_ws_terms_row_ranges_match_direct(self):
        """Prefix WS from per-row sums equals WS on the full image."""
        c = np.asarray(Image.open(SAMPLE).convert("L"))
        t = S.WSTerms(c)
        self.assertAlmostEqual(t.estimate(), t.estimate(0, None), places=9)
        self.assertEqual(t.blocks.shape, ((c.shape[0] - 2) // 64, (c.shape[1] - 2) // 64))

    def test_pov_direction(self):
        """High p-value = pairs equalised = embedding. Clean → p ≈ 0."""
        c = np.asarray(Image.open(SAMPLE).convert("L"))
        s = lsb_replace(c, 1.0, np.random.default_rng(1))
        self.assertLess(S.pov_chi_square_test(c)[1], 0.01)
        self.assertGreater(S.pov_chi_square_test(s)[1], 0.5)

    def test_old_tuple_api_removed(self):
        self.assertFalse(hasattr(S, "detect_lsb_steganography"))


class TestAnalyzeLsb(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.base = np.asarray(Image.open(SAMPLE).convert("RGB"))
        cls.rng = np.random.default_rng(42)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def run_on(self, arr, name, **kw):
        p = self.tmp / name
        Image.fromarray(arr).save(p, **kw)
        return S.analyze_lsb(str(p))

    def levels(self, r):
        return [f["level"] for f in r["findings"]]

    def test_clean_png_no_warning(self):
        r = self.run_on(self.base, "clean.png")
        self.assertEqual(r["status"], "ok")
        self.assertNotIn("warning", self.levels(r))
        self.assertLess(r["details"]["score"], S.THRESHOLD)
        self.assertEqual(len(r["images"]), 2)
        self.assertTrue(r["limitations"])

    def test_random_10pct_detected_with_estimate(self):
        r = self.run_on(lsb_replace(self.base, 0.10, self.rng), "r10.png")
        self.assertIn("warning", self.levels(r))
        self.assertAlmostEqual(r["details"]["score"], 0.10, delta=0.03)
        self.assertFalse(r["details"]["sequential_detected"])

    def test_random_50pct_not_called_sequential(self):
        """Regression: the old randomness gate zeroed a 50 % embed."""
        r = self.run_on(lsb_replace(self.base, 0.50, self.rng), "r50.png")
        self.assertIn("warning", self.levels(r))
        self.assertAlmostEqual(r["details"]["score"], 0.5, delta=0.05)
        self.assertFalse(r["details"]["sequential_detected"])

    def test_sequential_detected_and_localised(self):
        r = self.run_on(lsb_replace(self.base, 0.25, self.rng, True), "s25.png")
        self.assertTrue(r["details"]["sequential_detected"])
        self.assertAlmostEqual(r["details"]["sequential_fraction"], 0.25, delta=0.03)

    def test_lsb_matching_is_not_detected(self):
        """Documents a blind spot: ±1 embedding leaves no pair structure."""
        r = self.run_on(lsb_match(self.base, 0.5, self.rng), "m50.png")
        self.assertNotIn("warning", self.levels(r))
        text = " ".join(f["text"] for f in r["findings"])
        self.assertIn("LSB matching", text)

    def test_resized_clean_not_flagged(self):
        """Ported from test_integration: interpolation smooths histograms."""
        im = Image.fromarray(self.base)
        for filt in (Image.Resampling.BICUBIC, Image.Resampling.LANCZOS,
                     Image.Resampling.BILINEAR):
            with self.subTest(filt=filt.name):
                r = self.run_on(np.asarray(im.resize((600, 400), filt)),
                                f"rs_{filt.name}.png")
                self.assertNotIn("warning", self.levels(r))

    def test_jpeg_gets_dct_caveat(self):
        r = S.analyze_lsb(str(SAMPLE))
        self.assertEqual(r["status"], "ok")
        self.assertIn("DCT", r["findings"][0]["text"])
        self.assertNotIn("warning", self.levels(r))

    def test_grayscale_single_channel(self):
        r = self.run_on(np.asarray(Image.fromarray(self.base).convert("L")), "g.png")
        self.assertEqual(list(r["details"]["estimates"]), ["gray"])

    def test_degenerate_inputs(self):
        self.assertEqual(self.run_on(self.base[:1, :1], "t1.png")["status"],
                         "insufficient_data")
        self.assertEqual(self.run_on(self.base[:16, :16], "t16.png")["status"],
                         "insufficient_data")
        flat = np.full((128, 128, 3), 128, np.uint8)
        self.assertEqual(self.run_on(flat, "flat.png")["status"], "insufficient_data")
        self.assertEqual(S.analyze_lsb(str(self.tmp / "missing.png"))["status"], "error")

    def test_no_overclaiming_words(self):
        r = self.run_on(self.base, "clean2.png")
        text = (r["summary"] + " ".join(f["text"] for f in r["findings"])).lower()
        for w in ("authentic", "admissible", "no manipulation", "proves", "genuine"):
            self.assertNotIn(w, text)


class TestBenchmark(unittest.TestCase):
    """Seeded mini-benchmark on bundled photos (full numbers in
    Descriptions/Steganography.md): FPR on clean PNG and decoded-JPEG covers,
    TPR for 10 % random LSB replacement, ~0 TPR for LSB matching."""

    def test_fpr_tpr(self):
        rng = np.random.default_rng(7)
        covers = [np.asarray(Image.open(SAMPLE).convert("RGB"))]
        covers += [getattr(skd, n)() for n in
                   ("astronaut", "coffee", "chelsea", "camera", "rocket",
                    "coins", "moon", "gravel")]
        clean = [score(c) for c in covers]
        clean += [score(decode_jpeg(c, q)) for c, q in zip(covers, (75, 85, 95, 100) * 3)]
        r10 = [score(lsb_replace(c, 0.10, rng)) for c in covers]
        m25 = [score(lsb_match(c, 0.25, rng)) for c in covers]
        fpr = np.mean(np.array(clean) > S.THRESHOLD)
        tpr = np.mean(np.array(r10) > S.THRESHOLD)
        mae = np.mean(np.abs(np.array(r10) - 0.10))
        self.assertLessEqual(fpr, 0.06, clean)
        self.assertGreaterEqual(tpr, 0.9, r10)
        self.assertLess(mae, 0.03)
        self.assertLessEqual(np.mean(np.array(m25) > S.THRESHOLD), 0.12)


if __name__ == "__main__":
    unittest.main()
