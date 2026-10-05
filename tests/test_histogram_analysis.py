"""Histogram: Stamm & Liu contrast-enhancement detector."""
import shutil
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np
import skimage.data as skd
from PIL import Image

from analysis.histogram_analysis import (analyze_histogram, hf_energy,
                                         interior_gaps, pinch_window)

SAMPLE = Path(__file__).resolve().parent.parent / "assets" / "sample images" / "sampleImg.jpeg"


def _photos():
    out = [np.asarray(Image.open(SAMPLE).convert("RGB"))]
    out += [getattr(skd, n)() for n in ("astronaut", "coffee", "chelsea", "rocket")]
    out += [np.stack([getattr(skd, n)()] * 3, -1)
            for n in ("camera", "moon", "gravel", "coins", "clock")]
    return out


class TestHistogram(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.photos = _photos()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _run(self, name, arr, **kw):
        p = self.tmp / name
        Image.fromarray(arr).save(p, **kw)
        return analyze_histogram(str(p))

    def test_pinch_window(self):
        p = pinch_window()
        self.assertEqual(p[0], 0.0)
        self.assertAlmostEqual(p[255], 0.0)
        self.assertTrue((p[9:247] == 1).all())

    def test_gaps_only_inside_occupied_range(self):
        """A dark image occupying 0-60 must not count 195 empty bins."""
        h = np.zeros(256)
        h[:61] = 1000
        self.assertEqual(interior_gaps(h)[0], 0)
        h[::2] = 0
        h[0] = 1000
        self.assertGreater(interior_gaps(h)[0], 20)

    def test_smooth_vs_comb_energy(self):
        x = np.arange(256)
        smooth = np.exp(-((x - 120) / 40.0) ** 2) * 1e4
        comb = smooth.copy()
        comb[::2] = 0  # period-2 comb (gain 2): energy at k=128
        self.assertLess(hf_energy(smooth), 0.002)
        self.assertGreater(hf_energy(comb), 0.05)

    def test_dark_photo_is_not_flagged(self):
        rng = np.random.default_rng(0)
        f = self.photos[1].astype(float) * 0.3 + rng.normal(0, 1.5, self.photos[1].shape)
        r = self._run("dark.jpg", np.clip(np.rint(f), 0, 255).astype(np.uint8), quality=90)
        self.assertEqual(r["status"], "ok")
        self.assertFalse(r["details"]["flagged"])

    def test_clipping_is_info_only(self):
        a = self.photos[1].astype(float) * 1.0
        a[:100] = 255  # 20 % saturated, histogram otherwise untouched
        r = self._run("clip.png", a.astype(np.uint8))
        clip = [f for f in r["findings"] if "clipped" in f["text"]]
        self.assertTrue(clip)
        self.assertTrue(all(f["level"] == "info" for f in clip))

    def test_outputs(self):
        r = analyze_histogram(str(SAMPLE))
        self.assertEqual(r["status"], "ok")
        self.assertEqual(len(r["images"]), 1)
        self.assertIn("Per-channel statistics", r["tables"])
        g = self._run("g.png", self.photos[5][..., 0])
        self.assertEqual(len(g["tables"]["Per-channel statistics"]), 1)
        self.assertEqual(self._run("flat.png", np.full((100, 100, 3), 7, np.uint8))["status"],
                         "insufficient_data")

    def test_benchmark(self):
        """Calibration: TPR 91 % on lossless enhancements, FPR 0/90 excluding
        a mostly-black medical image (see histogram_analysis.py)."""
        rng = np.random.default_rng(3)
        fp = tp = npos = 0
        for i, img in enumerate(self.photos):
            q = int(rng.choice([70, 80, 90, 95, 100]))
            fp += self._run(f"n{i}.jpg", img, quality=q)["details"]["flagged"]
            fp += self._run(f"n{i}.png", img)["details"]["flagged"]
            f = img / 255.0
            lo, hi = np.percentile(img, [2, 98])
            for name, m in [
                ("g07", 255 * f ** 0.7), ("g14", 255 * f ** 1.4),
                ("st", (img - lo) * 255 / max(hi - lo, 1)),
                ("he", np.stack([cv2.equalizeHist(np.ascontiguousarray(img[..., c]))
                                 for c in range(3)], -1))]:
                m = np.clip(np.rint(m), 0, 255).astype(np.uint8)
                tp += self._run(f"p{i}{name}.png", m)["details"]["flagged"]
                npos += 1
        self.assertLessEqual(fp, 1, f"false alarms {fp}/20")
        self.assertGreaterEqual(tp / npos, 0.8, f"detections {tp}/{npos}")


if __name__ == "__main__":
    unittest.main()
