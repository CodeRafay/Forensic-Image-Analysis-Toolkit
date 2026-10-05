"""Frequency: power-spectrum measurements and JPEG block-artifact grid."""
import io
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
import skimage.data as skd
from PIL import Image, ImageFilter

from analysis.frequency_analysis import analyze_blocking, analyze_spectrum
from analysis.util import jpeg_grid_offset

SAMPLE = Path(__file__).resolve().parent.parent / "assets" / "sample images" / "sampleImg.jpeg"


def _jpeg(arr, q):
    b = io.BytesIO()
    Image.fromarray(arr).save(b, "JPEG", quality=q)
    return np.asarray(Image.open(io.BytesIO(b.getvalue())).convert("RGB"))


def _half(arr):
    """Area-downscale 2x: removes any earlier JPEG grid from the source."""
    im = Image.fromarray(arr)
    return np.asarray(im.resize((im.width // 2, im.height // 2), Image.BOX))


def _photos():
    out = [np.asarray(Image.open(SAMPLE).convert("RGB"))]
    out += [getattr(skd, n)() for n in ("astronaut", "coffee", "chelsea",
                                        "hubble_deep_field", "retina")]
    out += [np.stack([getattr(skd, n)()] * 3, -1) for n in ("camera", "moon", "brick")]
    return out


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.photos = _photos()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def save(self, name, arr, **kw):
        p = self.tmp / name
        Image.fromarray(np.asarray(arr, np.uint8)).save(p, **kw)
        return str(p)


class TestSpectrum(Base):
    def test_brightness_shift_does_not_move_measurements(self):
        g = np.asarray(Image.open(SAMPLE).convert("L"), float) * 0.5
        a = analyze_spectrum(self.save("a.png", np.rint(g)))["details"]
        b = analyze_spectrum(self.save("b.png", np.rint(g) + 100))["details"]
        self.assertAlmostEqual(a["slope"], b["slope"], places=6)
        self.assertAlmostEqual(a["hf_share"], b["hf_share"], places=6)

    def test_blur_steepens_and_noise_flattens(self):
        im = Image.open(SAMPLE).convert("RGB")
        base = analyze_spectrum(str(SAMPLE))["details"]["slope"]
        blur = analyze_spectrum(self.save(
            "blur.png", np.asarray(im.filter(ImageFilter.GaussianBlur(1.5)))))
        rng = np.random.default_rng(0)
        noise = analyze_spectrum(self.save("noise.png", rng.integers(0, 256, (256, 256))))
        self.assertLess(blur["details"]["slope"], base - 1.0)
        self.assertTrue(any(f["level"] == "notice" for f in blur["findings"]))
        self.assertGreater(noise["details"]["slope"], -0.5)

    def test_small_and_flat_are_insufficient(self):
        self.assertEqual(analyze_spectrum(self.save("t.png", np.zeros((15, 40))))["status"],
                         "insufficient_data")
        self.assertEqual(analyze_spectrum(self.save("f.png", np.full((64, 64), 9)))["status"],
                         "insufficient_data")

    def test_no_scores_or_verdicts(self):
        r = analyze_spectrum(str(SAMPLE))
        keys = " ".join(r["metrics"]).lower() + " ".join(r["details"]).lower()
        for banned in ("authentic", "score", "risk", "quality"):
            self.assertNotIn(banned, keys)

    def test_slope_recovers_power_law(self):
        """Log-spaced bins: a 1/f^(2a) power image reads about -2a."""
        from analysis.frequency_analysis import power_spectrum_stats
        r = np.random.default_rng(0)
        n = 512
        f = np.hypot(*np.meshgrid(np.fft.fftfreq(n), np.fft.fftfreq(n)))
        f[0, 0] = 1
        for a in (1.0, 1.5):
            x = np.real(np.fft.ifft2(np.fft.fft2(r.normal(size=(n, n))) / f ** a))
            self.assertAlmostEqual(power_spectrum_stats(x)[0], -2 * a, delta=0.3)

    def test_benchmark_clean_photos_in_range(self):
        """Clean photos at q90: at most 1 outside the ranges."""
        out = 0
        for i, img in enumerate(self.photos):
            r = analyze_spectrum(self.save(f"c{i}.jpg", img, quality=90))
            out += any(f["level"] == "notice" for f in r["findings"])
        self.assertLessEqual(out, 1)


class TestBlocking(Base):
    def test_crop_offset_is_recovered(self):
        img = _half(self.photos[0])
        for r, c in [(0, 0), (3, 5), (7, 1)]:
            dec = _jpeg(img, 70)[r:, c:]
            res = analyze_blocking(self.save(f"crop{r}{c}.png", dec))
            self.assertTrue(res["details"]["grid"])
            self.assertEqual(res["details"]["origin"], [(8 - r) % 8, (8 - c) % 8])
            if (r, c) != (0, 0):
                self.assertTrue(any("cropped" in f["text"] or "crop" in f["text"]
                                    for f in res["findings"]))

    def test_nn_upscale_is_not_a_jpeg_grid(self):
        img = _half(self.photos[1])
        up = np.repeat(np.repeat(img, 2, 0), 2, 1)
        r = analyze_blocking(self.save("nn2.png", up))
        self.assertFalse(r["details"]["grid"])
        self.assertEqual(r["details"]["period"], [2, 2])
        self.assertTrue(any("upscaling" in f["text"] for f in r["findings"]))
        self.assertFalse(any(f["level"] == "warning" for f in r["findings"]))

    def test_misaligned_splice_is_localised(self):
        bg = _jpeg(self.photos[0], 80).copy()
        patch = _jpeg(self.photos[1], 60)[96:352, 96:352]
        bg[131:387, 453:709] = patch          # grid phase (3, 5) vs (0, 0)
        r = analyze_blocking(self.save("splice.jpg", bg, quality=95))
        self.assertTrue(any(f["level"] == "warning" for f in r["findings"]))
        self.assertGreater(r["details"]["misaligned_pct"], 1.0)

    def test_small_and_flat_are_insufficient(self):
        self.assertEqual(analyze_blocking(self.save("t.png", np.zeros((40, 40))))["status"],
                         "insufficient_data")
        self.assertEqual(analyze_blocking(self.save("f.png", np.full((128, 128), 9)))["status"],
                         "insufficient_data")

    def test_benchmark(self):
        """Grid present and offset right on cropped JPEGs q50-80; no grid on
        never-compressed images; no local warning on clean cropped JPEGs.
        Calibration: offset TPR 94 % at q50-70, 75 % at q80; 0/48 false grids;
        local FPR 2/48 (see frequency_analysis.py)."""
        rng = np.random.default_rng(11)
        ok = n = false_grid = warn = 0
        for i, img in enumerate(self.photos):
            h = _half(img)
            false_grid += jpeg_grid_offset(np.asarray(Image.fromarray(h).convert("L"), float))[2] >= 1.4
            q = int(rng.choice([50, 60, 70, 80]))
            r, c = (int(v) for v in rng.integers(0, 8, 2))
            res = analyze_blocking(self.save(f"b{i}.png", _jpeg(h, q)[r:, c:]))
            n += 1
            ok += res["details"]["grid"] and res["details"]["origin"] == [(8 - r) % 8, (8 - c) % 8]
            warn += any(f["level"] == "warning" for f in res["findings"])
        self.assertEqual(false_grid, 0)
        self.assertGreaterEqual(ok, 7, f"offsets {ok}/{n}")
        self.assertLessEqual(warn, 1, f"local false alarms {warn}/{n}")


if __name__ == "__main__":
    unittest.main()
