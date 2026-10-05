"""ELA: behaviour of analyze_ela and a small seeded splice benchmark."""
import io
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
import skimage.data as skd
from PIL import Image

from analysis.ela import analyze_ela

SAMPLE = Path(__file__).resolve().parent.parent / "assets" / "sample images" / "sampleImg.jpeg"


def _jpeg(arr, q):
    b = io.BytesIO()
    Image.fromarray(arr).save(b, "JPEG", quality=q)
    return np.asarray(Image.open(io.BytesIO(b.getvalue())).convert("RGB"))


def _photos():
    out = [np.asarray(Image.open(SAMPLE).convert("RGB"))]
    out += [getattr(skd, n)() for n in ("astronaut", "coffee", "chelsea", "rocket")]
    out += [np.stack([getattr(skd, n)()] * 3, -1)
            for n in ("camera", "moon", "brick", "coins", "clock")]
    return out


class TestELA(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.photos = _photos()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _save(self, name, arr, **kw):
        p = self.tmp / name
        Image.fromarray(arr).save(p, **kw)
        return str(p)

    def test_quality_is_reflected_in_labels_and_error(self):
        r90 = analyze_ela(str(SAMPLE), quality=90)
        r70 = analyze_ela(str(SAMPLE), quality=70)
        self.assertEqual(r90["status"], "ok")
        self.assertTrue(any("q90" in k for k in r90["metrics"]))
        self.assertTrue(any("q70" in k for k in r70["metrics"]))
        self.assertFalse(any("q90" in k for k in r70["metrics"]))
        self.assertGreater(r70["details"]["mean_error"], r90["details"]["mean_error"])

    def test_percentage_matches_the_overlay(self):
        """The reported % and the red overlay come from the same mask."""
        r = analyze_ela(str(SAMPLE))
        pct = next(v for k, v in r["metrics"].items() if k.startswith("Area above"))
        overlay = next(v for k, v in r["images"].items() if "red" in k)
        rgb = np.asarray(Image.open(SAMPLE).convert("RGB")).astype(int)
        changed = (np.abs(overlay.astype(int) - rgb).sum(axis=2) > 3).mean() * 100
        self.assertAlmostEqual(pct, changed, delta=0.5)
        self.assertAlmostEqual(pct, r["details"]["area_above_k_pct"], delta=0.01)

    def test_images_are_arrays_not_ssim(self):
        r = analyze_ela(str(SAMPLE))
        self.assertLessEqual(len(r["images"]), 4)
        for cap, im in r["images"].items():
            self.assertNotIn("SSIM", cap)
            self.assertEqual(im.dtype, np.uint8)
            self.assertLessEqual(max(im.shape[:2]), 1200)

    def test_degenerate_inputs(self):
        flat = self._save("flat.png", np.full((200, 200, 3), 90, np.uint8))
        tiny = self._save("tiny.png", np.zeros((10, 10, 3), np.uint8))
        self.assertEqual(analyze_ela(flat)["status"], "insufficient_data")
        self.assertEqual(analyze_ela(tiny)["status"], "insufficient_data")
        self.assertEqual(analyze_ela(str(self.tmp / "missing.jpg"))["status"], "error")

    def test_png_gets_an_info_note(self):
        p = self._save("p.png", self.photos[1])
        r = analyze_ela(p)
        self.assertTrue(any("not JPEG" in f["text"] for f in r["findings"]))

    def test_bundled_sample_ufo_is_marked(self):
        """The bundled sample has a pasted disc ("UFO") above the city."""
        r = analyze_ela(str(SAMPLE))
        self.assertGreater(r["details"]["n_regions"], 0)
        mask = next(v for k, v in r["images"].items() if "red" in k)
        rgb = np.asarray(Image.open(SAMPLE).convert("RGB")).astype(int)
        red = (np.abs(mask.astype(int) - rgb).sum(axis=2) > 3)
        self.assertGreater(red[240:300, 480:840].mean(), 0.5)  # the disc

    def test_smooth_photo_with_texture_is_not_flagged(self):
        """Reviewer's false-alarm case: large smooth area next to texture
        (old 4x-median rule fired on such photos)."""
        rng = np.random.default_rng(3)
        fp = 0
        for i, img in enumerate(self.photos[1:6]):
            a = np.clip(img.astype(float) + rng.normal(0, 1.5, img.shape), 0, 255).astype(np.uint8)
            for q in (75, 92):
                fp += bool(analyze_ela(self._save(f"sm{i}_{q}.jpg", a, quality=q))["details"]["n_regions"])
        self.assertEqual(fp, 0)

    def test_splice_benchmark(self):
        """Raw patch pasted into a q70-90 JPEG, saved losslessly, vs clean
        JPEGs. Hold-out (Descriptions/ELA.md): PNG 14/21, FPR 0/84."""
        rng = np.random.default_rng(7)
        tp = fp = 0
        photos = self.photos[1:]  # the sample itself contains a paste
        n = len(photos)
        for i, img in enumerate(photos):
            q = int(rng.choice([70, 80, 90, 95]))
            neg = self._save(f"neg{i}.jpg", img, quality=q)
            fp += bool(analyze_ela(neg)["details"]["n_regions"])
            donor = photos[(i + 3) % n]
            h, w = img.shape[:2]
            s = int(min(h, w) * 0.3)
            y, x = rng.integers(0, h - s), rng.integers(0, w - s)
            bg = _jpeg(img, int(rng.choice([70, 80, 90]))).copy()
            bg[y:y + s, x:x + s] = donor[:s, :s]
            r = analyze_ela(self._save(f"pos{i}.png", bg))
            tp += bool(r["details"]["n_regions"])
        print(f"ELA benchmark TPR {tp}/{n} FPR {fp}/{n}")
        self.assertEqual(fp, 0, f"false alarms {fp}/{n}")
        self.assertGreaterEqual(tp, n // 2, f"detections {tp}/{n}")


if __name__ == "__main__":
    unittest.main()
