"""
Behaviour and a small seeded benchmark for analysis.resampling_detector
(Kirchner 2008 p-map spectrum, JPEG-aware, plus nearest-neighbour test).
"""
import io
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image
from skimage import data

from analysis import resampling_detector as R

SAMPLE = Path(__file__).resolve().parent.parent / "assets" / "sample images" / "sampleImg.jpeg"
BIC = Image.Resampling.BICUBIC


def _jpeg(a, q):
    buf = io.BytesIO()
    Image.fromarray(a).save(buf, "JPEG", quality=q)
    with Image.open(io.BytesIO(buf.getvalue())) as im:
        return np.asarray(im)


def _resize(a, s, m=BIC):
    im = Image.fromarray(a)
    return np.asarray(im.resize((round(im.width * s), round(im.height * s)), m))


def _gray(a):
    return np.asarray(Image.fromarray(a).convert("L"), np.float64)


def _detected(a, jpeg):
    st = R.statistics(_gray(a), jpeg)
    return st["ratio"] >= R.THRESHOLD or st["proj"][0] >= R.PROJ_THRESHOLD


def _camera(seed, h=480, w=640):
    """Camera-like host: textured scene -> RGGB mosaic -> noise -> OpenCV
    bilinear demosaic. Its period-2 CFA trace must not read as resampling."""
    import cv2
    from scipy import ndimage
    r = np.random.default_rng(seed)
    f = np.hypot(*np.meshgrid(np.fft.fftfreq(w), np.fft.fftfreq(h)))
    f[0, 0] = 1
    tex = np.real(np.fft.ifft2(np.fft.fft2(r.normal(size=(h, w))) / f ** 0.9))
    x = 128 + 40 * tex / tex.std()
    x = ndimage.gaussian_filter(x, 0.7)[..., None] * r.uniform(0.7, 1.2, 3)
    mos = np.empty((h, w))
    mos[0::2, 0::2] = x[0::2, 0::2, 0]; mos[0::2, 1::2] = x[0::2, 1::2, 1]
    mos[1::2, 0::2] = x[1::2, 0::2, 1]; mos[1::2, 1::2] = x[1::2, 1::2, 2]
    mos += r.normal(0, 1, mos.shape) * np.sqrt(np.clip(mos, 1, 255) * 0.5)
    return cv2.cvtColor(np.clip(mos, 0, 255).astype(np.uint8), cv2.COLOR_BayerRG2RGB)


class TestResampling(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.rgb = np.asarray(Image.open(SAMPLE).convert("RGB"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def save(self, name, arr, **kw):
        p = self.tmp / name
        Image.fromarray(arr).save(p, **kw)
        return str(p)

    def test_small_and_flat_are_insufficient(self):
        for name, arr in (("tiny.png", self.rgb[:40, :40]),
                          ("flat.png", np.full((200, 200, 3), 90, np.uint8))):
            r = R.detect_resampling(self.save(name, arr))
            self.assertEqual(r["status"], "insufficient_data", name)
            self.assertTrue(r["limitations"])

    def test_missing_file_is_error(self):
        self.assertEqual(R.detect_resampling(str(self.tmp / "nope.jpg"))["status"], "error")

    def test_clean_and_low_quality_jpeg_not_flagged(self):
        # Old bug: the 8x8 grid peak at 0.125 made every q<=50 JPEG and every
        # crop read as "resampled 1.143x / 7.98x".
        crop = _jpeg(self.rgb, 30)[3:, 5:]
        for name, arr, kw in (("clean.jpg", self.rgb, {"quality": 95}),
                              ("q30.jpg", self.rgb, {"quality": 30}),
                              ("crop_q30.png", crop, {})):
            r = R.detect_resampling(self.save(name, arr, **kw))
            self.assertEqual(r["status"], "ok", name)
            self.assertFalse(r["details"]["resampling_detected"], name)
            self.assertFalse(r["details"]["nearest_neighbour"], name)

    def test_upscale_detected_and_factor_recovered(self):
        for s in (1.25, 1.5):
            r = R.detect_resampling(self.save(f"up{s}.png", _resize(self.rgb, s)))
            self.assertTrue(r["details"]["resampling_detected"], s)
            self.assertTrue(any(abs(c - s) < 0.02 for c in r["details"]["scale_candidates"]),
                            r["details"]["scale_candidates"])
            self.assertEqual(r["findings"][0]["level"], "warning")

    def test_demosaiced_png_not_flagged(self):
        """Review: 7/16 clean demosaiced PNGs were read as resized (Nyquist)."""
        for seed in range(3):
            r = R.detect_resampling(self.save(f"cam{seed}.png", _camera(seed)))
            self.assertFalse(r["details"]["resampling_detected"], seed)

    def test_uniform_upscale_not_read_as_rotation(self):
        """Review: 1.3x gave a diagonal peak read as a ~19 deg rotation."""
        self.assertIsNone(R.scale_candidates(0.231, -0.231)[1])
        self.assertIn(1.3, R.scale_candidates(0.231, -0.231)[0])
        self.assertIsNotNone(R.scale_candidates(0.12, 0.0075)[1])  # 7 deg

    def test_upscale_then_jpeg_found_by_projection(self):
        for s in (1.1, 1.3):
            up = _jpeg(_resize(_camera(7), s), 85)
            r = R.detect_resampling(self.save(f"upj{s}.png", up))
            self.assertTrue(r["details"]["projection_detected"], s)

    def test_nearest_neighbour_2x(self):
        up = _resize(self.rgb[:300, :400], 2.0, Image.Resampling.NEAREST)
        r = R.detect_resampling(self.save("nn2.png", up))
        self.assertTrue(r["details"]["nearest_neighbour"])
        self.assertTrue(any("2.0" in f["text"] and "nearest" in f["text"] for f in r["findings"]))

    def test_localises_pasted_rescaled_object(self):
        base =np.asarray(Image.fromarray(np.asarray(data.coffee())).convert("L"))
        obj = np.asarray(Image.fromarray(np.asarray(data.camera())[100:234, 150:284])
                         .resize((200, 200), BIC))  # 134 -> 200 px = 1.5x
        img = base.copy()
        y0, x0 = 120, 300
        img[y0:y0 + 200, x0:x0 + 200] = obj
        r = R.detect_resampling(self.save("paste.png", img))
        grid = np.array(r["details"]["window_grid"]) >= R.WIN_THRESHOLD
        self.assertTrue(grid.any(), "pasted object not flagged")
        ys, xs = np.nonzero(grid)
        for i, j in zip(ys, xs):  # every flagged window touches the object
            self.assertTrue(i * R.STRIDE < y0 + 200 and i * R.STRIDE + R.WIN > y0 and
                            j * R.STRIDE < x0 + 200 and j * R.STRIDE + R.WIN > x0, (i, j))


class TestBenchmark(unittest.TestCase):
    """Seeded mini-benchmark (the full calibration is in Descriptions/Resampling.md)."""

    def test_tpr_fpr(self):
        rng = np.random.default_rng(0)
        imgs = [np.asarray(Image.open(SAMPLE).convert("RGB")), data.coffee(),
                data.camera(), data.rocket(), data.chelsea()]
        neg, pos = [], []
        for a in imgs:
            for q in (20, 50, 75, 95):
                neg.append(_detected(_jpeg(a, q), True))
        for seed in range(4):
            c = _camera(10 + seed)
            neg += [_detected(c, False), _detected(_jpeg(c, 85), True)]
            pos += [_detected(_jpeg(_resize(c, s), 90), True) for s in (1.1, 1.3, 1.7)]
        for a in imgs:
            y, x = rng.integers(1, 30, 2)
            neg.append(_detected(_jpeg(a, 60)[y:, x:], True))
            neg.append(_detected(a, False))
            for s in (1.1, 1.25, 1.5):
                pos.append(_detected(_resize(a, s), False))
        self.assertLessEqual(np.mean(neg), 0.05, f"FPR {np.mean(neg):.2f}")
        self.assertGreaterEqual(np.mean(pos), 0.9, f"TPR {np.mean(pos):.2f}")


if __name__ == "__main__":
    unittest.main()
