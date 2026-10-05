"""
Synthetic-image traces (experimental): the periodic-peak measurement must
stay low on clean photos (PNG and JPEG) and rise on an injected periodic
upsampling-like pattern; wording must never be a verdict.
"""
import io
import shutil
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from skimage import data

from analysis import deepfake_detector as dd

SAMPLE = Path(__file__).resolve().parent.parent / "assets" / "sample images" / "sampleImg.jpeg"


def _gray(a):
    a = np.asarray(a)
    return (a[..., :3].mean(2) if a.ndim == 3 else a).astype(float)


def _enc(a, q):
    a = np.clip(a, 0, 255).round().astype(np.uint8)
    if q is None:
        return a.astype(float)
    b = io.BytesIO()
    Image.fromarray(a).save(b, "JPEG", quality=q)
    return np.asarray(Image.open(b), float)


def _checker(shape, amp=1.5):
    yy, xx = np.mgrid[:shape[0], :shape[1]]
    return amp * (-1.0) ** (yy + xx) + amp / 1.5 * (-1.0) ** yy


def _period3(shape, amp=1.5):
    yy, xx = np.mgrid[:shape[0], :shape[1]]
    return amp * np.cos(2 * np.pi * xx / 3) * np.cos(2 * np.pi * yy / 3)


# Sources never JPEG-compressed as far as the grid test can tell (their k/8
# bins stay in the search, so a 2×2 checkerboard is visible).
CLEAN = {"camera": data.camera(), "astronaut": data.astronaut(), "brick": data.brick(),
         "grass": data.grass(), "gravel": data.gravel(), "coffee": data.coffee(),
         "chelsea": data.chelsea()}


class TestBenchmark(unittest.TestCase):
    def test_clean_photos_low(self):
        """Negatives: PNG and JPEG q50/q75/q95. Calibrated FPR 0/107."""
        srcs = dict(CLEAN, sample=np.asarray(Image.open(SAMPLE)))
        peaks = [dd.measure(_enc(_gray(a), q), q is not None)["peak_db"]
                 for a in srcs.values() for q in (None, 50, 75, 95)]
        self.assertLessEqual(np.mean(np.array(peaks) > dd.PEAK_NOTICE_DB), 0.05, peaks)

    def test_demosaiced_camera_png_low(self):
        """Bayer RGGB + noise + bilinear demosaic puts energy on the Nyquist
        lines; those are excluded from the peak search."""
        r = np.random.default_rng(3)
        for a in (data.astronaut(), data.coffee(), data.chelsea()):
            sc = np.asarray(a, float)[:, :, :3]
            raw = np.zeros(sc.shape[:2])
            raw[0::2, 0::2] = sc[0::2, 0::2, 0]
            raw[0::2, 1::2] = sc[0::2, 1::2, 1]
            raw[1::2, 0::2] = sc[1::2, 0::2, 1]
            raw[1::2, 1::2] = sc[1::2, 1::2, 2]
            raw = np.clip(raw + r.normal(0, 1, raw.shape) * np.sqrt(0.3 * raw + 4), 0, 255)
            rgb = cv2.cvtColor(raw.astype(np.uint8), cv2.COLOR_BayerRG2RGB)
            m = dd.measure(_gray(rgb), False)
            self.assertLessEqual(m["peak_db"], dd.PEAK_NOTICE_DB, m["freq"])

    def test_injected_periodic_patterns_high(self):
        chk = [dd.measure(_enc(_gray(a) + _checker(_gray(a).shape), None), False)
               for a in CLEAN.values()]
        # a period-2 checkerboard sits on the Nyquist lines: reported there,
        # never as the off-grid peak
        self.assertTrue(all(m["nyquist_db"] > dd.PEAK_NOTICE_DB for m in chk))
        self.assertTrue(all(abs(m["freq"][0]) < 0.49 and abs(m["freq"][1]) < 0.49 for m in chk))
        p3 = [dd.measure(_enc(_gray(a) + _period3(_gray(a).shape), None), False)["peak_db"]
              for a in CLEAN.values()]
        self.assertGreaterEqual(np.mean(np.array(p3) > dd.PEAK_NOTICE_DB), 0.9, p3)

    def test_jpeg_grid_excluded(self):
        m = dd.measure(_enc(_gray(data.camera()), 75), True)
        self.assertTrue(m["exclude_grid"])
        fy, fx = m["freq"]
        self.assertFalse(abs(fy * 8 - round(fy * 8)) < 0.01 and abs(fx * 8 - round(fx * 8)) < 0.01)


class TestEntryPoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = Path(tempfile.mkdtemp())

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.d, ignore_errors=True)

    def _save(self, name, arr, **kw):
        p = self.d / name
        Image.fromarray(np.clip(arr, 0, 255).round().astype(np.uint8)).save(p, **kw)
        return str(p)

    def test_notice_on_period3_info_on_clean(self):
        cam = data.camera().astype(float)
        pos = dd.analyze_synthetic_traces(self._save("p3.png", cam + _period3(cam.shape)))
        neg = dd.analyze_synthetic_traces(self._save("cam.jpg", cam, quality=90))
        self.assertEqual(pos["status"], "ok")
        self.assertEqual(pos["findings"][0]["level"], "notice")
        self.assertEqual(neg["findings"][0]["level"], "info")
        self.assertTrue(any("8-px-grid" in f["text"] for f in neg["findings"]))
        for r in (pos, neg):
            self.assertLessEqual(len(r["images"]), 4)
            self.assertTrue(all(f["level"] != "warning" for f in r["findings"]))
            text = " ".join([r["summary"]] + [f["text"] for f in r["findings"]]).lower()
            for banned in ("authentic", "genuine", "no gan", "ai-generated image detected", "real photo"):
                self.assertNotIn(banned, text)
            self.assertTrue(any("cannot reliably identify" in x.lower() for x in r["limitations"]))

    def test_degenerate(self):
        self.assertEqual(dd.analyze_synthetic_traces(
            self._save("flat.png", np.full((300, 300), 90.0)))["status"], "insufficient_data")
        self.assertEqual(dd.analyze_synthetic_traces(
            self._save("small.png", data.camera()[:200, :200].astype(float)))["status"],
            "insufficient_data")


if __name__ == "__main__":
    unittest.main()
