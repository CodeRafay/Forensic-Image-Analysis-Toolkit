"""
Double-JPEG localization (Bianchi & Piva 2012): behaviour + seeded benchmark.
Full calibration numbers are in analysis/double_jpeg.py and
Descriptions/Quantization.md.
"""
import io
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
import skimage.data as sd
from PIL import Image

from analysis import double_jpeg as dj

SAMPLE = Path(__file__).resolve().parent.parent / "assets" / "sample images" / "sampleImg.jpeg"


def _clean(a):
    """Resize to erase any JPEG history of the source photo."""
    im = Image.fromarray(a[..., :3] if a.ndim == 3 else np.stack([a] * 3, -1))
    return np.asarray(im.resize((round(im.width * .8), round(im.height * .8)),
                                Image.Resampling.LANCZOS))


def _jpeg(a, q):
    b = io.BytesIO()
    Image.fromarray(a).save(b, "JPEG", quality=q)
    return np.asarray(Image.open(io.BytesIO(b.getvalue())).convert("RGB")), b.getvalue()


def _blocks_iou(prob_map, mask):
    p = np.array(prob_map) > 0.5
    hb, wb = p.shape
    g = mask[:hb * 8, :wb * 8].reshape(hb, 8, wb, 8).mean(axis=(1, 3)) > 0.5
    return (p & g).sum() / max((p | g).sum(), 1)


def _warned(r):
    return any(f["level"] == "warning" for f in r["findings"])


class TestDoubleJpeg(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.imgs = [_clean(sd.chelsea()), _clean(sd.rocket()), _clean(sd.astronaut()),
                    _clean(sd.immunohistochemistry())]
        cls.donor = _clean(sd.coffee())

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _save(self, name, data):
        p = self.tmp / name
        p.write_bytes(data)
        return str(p)

    def test_lattice_hist(self):
        """Q1 = 2, Q2 = 1: odd bins get only the rounding-error mass."""
        c = np.random.default_rng(0).laplace(0, 6, 50000)
        edges = np.arange(-20, 22) - 0.5
        p = dj.lattice_hist(c, 2, edges, 0.1)
        x = np.arange(-20, 21)
        self.assertAlmostEqual(float(p.sum()), 1.0, places=6)
        # P(|e| > 1/2) = 0.11 at sigma^2 = 0.1 moves to the odd bins
        self.assertAlmostEqual(float(p[x % 2 == 1].sum()), 0.11, delta=0.03)
        p = dj.lattice_hist(c, 2, edges, 0.01)
        self.assertLess(float(p[x % 2 == 1].sum()), 0.01)

    def test_not_applicable_and_tiny(self):
        p = self.tmp / "a.png"
        Image.fromarray(self.imgs[0]).save(p)
        self.assertEqual(dj.analyze_double_jpeg(str(p))["status"], "not_applicable")
        _, b = _jpeg(self.imgs[0][:40, :40], 80)
        self.assertEqual(dj.analyze_double_jpeg(self._save("t.jpg", b))["status"],
                         "insufficient_data")

    def test_benchmark_aligned(self):
        """Positives: q1 JPEG, region pasted from an uncompressed source,
        resaved at q2 > q1. Negatives: single JPEG, and double JPEG without
        a splice (must not produce a localized warning)."""
        rng = np.random.default_rng(7)
        tp, ious, fp, n_neg = 0, [], 0, 0
        for i, host in enumerate(self.imgs):
            q1, q2 = [(60, 90), (75, 95), (70, 90), (80, 95)][i]
            a1, _ = _jpeg(host, q1)
            h, w = host.shape[:2]
            ph, pw = h // 2, w // 2
            y0, x0 = int(rng.integers(0, h - ph)), int(rng.integers(0, w - pw))
            sp = a1.copy()
            sp[y0:y0 + ph, x0:x0 + pw] = self.donor[:ph, :pw]
            m = np.zeros((h, w), bool)
            m[y0:y0 + ph, x0:x0 + pw] = True
            _, b = _jpeg(sp, q2)
            r = dj.analyze_double_jpeg(self._save(f"p{i}.jpg", b))
            tp += _warned(r)
            ious.append(_blocks_iou(r["details"]["prob_map"], m) if r["details"]["prob_map"] else 0)

            for q in (70, 95):
                _, b = _jpeg(host, q)
                r = dj.analyze_double_jpeg(self._save(f"s{i}{q}.jpg", b))
                fp += _warned(r)
                n_neg += 1
                self.assertLess(r["metrics"]["Frequencies with double-JPEG evidence"],
                                dj.MIN_FREQS_FOR_MAP)
            _, b = _jpeg(a1, q2)
            r = dj.analyze_double_jpeg(self._save(f"d{i}.jpg", b))
            self.assertEqual(r["details"]["model"], "aligned")  # DQ trace found
            # neighbouring qualities can share the 9 analysed table entries
            self.assertLessEqual(abs(r["metrics"]["Estimated primary quality (IJG)"] - q1), 1)
            fp += _warned(r)
            n_neg += 1
            # close qualities, no splice: the review's false-alarm case
            _, b = _jpeg(_jpeg(host, 90)[0], 95)
            fp += _warned(dj.analyze_double_jpeg(self._save(f"c{i}.jpg", b)))
            n_neg += 1
        self.assertGreaterEqual(tp, 4)
        self.assertGreaterEqual(float(np.median(ious)), 0.6, ious)
        self.assertEqual(fp, 0, f"{fp}/{n_neg} false alarms")

    def test_nonaligned_shift_found(self):
        """Crop by (r, c) between the saves: the primary grid sits at
        ((8-r)%8, (8-c)%8)."""
        hits = 0
        for i, (r_, c_) in enumerate([(3, 5), (6, 2), (1, 7)]):
            a1, _ = _jpeg(self.imgs[i], 60)
            _, b = _jpeg(np.ascontiguousarray(a1[r_:, c_:]), 90)
            r = dj.analyze_double_jpeg(self._save(f"na{i}.jpg", b))
            hits += (r["details"]["model"] == "non-aligned"
                     and r["details"]["na_shift"] == [(8 - r_) % 8, (8 - c_) % 8])
        self.assertGreaterEqual(hits, 2)


if __name__ == "__main__":
    unittest.main()
