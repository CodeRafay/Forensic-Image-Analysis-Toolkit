"""
Copy-move detection: behaviour on the cases that broke the old block matcher
(non-multiple-of-8 offsets, smooth gradients, a stray match on a clean JPEG,
tiny images) plus a small seeded benchmark.
"""
import io
import shutil
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np
import skimage.data as sd
from PIL import Image

from analysis import cmfd

SAMPLE = Path(__file__).resolve().parent.parent / "assets" / "sample images" / "sampleImg.jpeg"


def _clone(img, src_xy, dst_xy, size, angle=0.0, scale=1.0, mirror=False):
    """Paste img[src square] at dst, (mirrored left-right, then) rotated
    counter-clockwise by `angle` and scaled about its centre.
    Returns (forged, ground-truth mask of both copies)."""
    h, w = img.shape[:2]
    (x0, y0), (x1, y1) = src_xy, dst_xy
    M = cv2.getRotationMatrix2D((x0 + size / 2, y0 + size / 2), angle, scale)
    if mirror:
        M = M @ np.array([[-1, 0, 2 * x0 + size], [0, 1, 0], [0, 0, 1.0]])
    M[:, 2] += (x1 - x0, y1 - y0)
    src = np.zeros((h, w), np.uint8)
    src[y0:y0 + size, x0:x0 + size] = 1
    dst = cv2.warpAffine(src, M, (w, h), flags=cv2.INTER_NEAREST) > 0
    out = np.where(dst[..., None], cv2.warpAffine(img, M, (w, h)), img)
    return out, (src > 0) | dst


class TestCMFD(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def save(self, arr, name, q=None):
        p = self.tmp / name
        if q:
            Image.fromarray(arr).save(p, "JPEG", quality=q)
        else:
            Image.fromarray(arr).save(p)
        return str(p)

    def run_arr(self, arr, q=None):
        """Analyse an in-memory image (after optional JPEG) and return
        (result, predicted mask)."""
        if q:
            b = io.BytesIO()
            Image.fromarray(arr).save(b, "JPEG", quality=q)
            arr = np.asarray(Image.open(io.BytesIO(b.getvalue())).convert("RGB"))
        rgb = arr.astype(np.float64)
        return cmfd._analyse(rgb, rgb @ np.array([0.299, 0.587, 0.114]), 1.0, q)

    @staticmethod
    def f1(pred, gt):
        tp = (pred & gt).sum()
        return 2 * tp / max(2 * tp + (pred & ~gt).sum() + (~pred & gt).sum(), 1)

    def test_tiny_and_flat_are_insufficient(self):
        for arr in (sd.astronaut()[:16, :16], np.full((128, 128, 3), 90, np.uint8)):
            r = cmfd.detect_copy_move(self.save(arr, "t.png"))
            self.assertEqual(r["status"], "insufficient_data")
            self.assertTrue(r["limitations"])

    def test_offset_not_multiple_of_8(self):
        """Old matcher: offset (200, 505)-style shifts gave 0 matches."""
        img = sd.astronaut()
        forged, gt = _clone(img, (20, 300), (221, 101), 90)
        r = cmfd.detect_copy_move(self.save(forged, "off.png"))
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["findings"][0]["level"], "warning")
        c = r["details"]["clones"][0]
        self.assertAlmostEqual(abs(c["shift dx (px)"]), 201, delta=3)
        self.assertAlmostEqual(abs(c["shift dy (px)"]), 199, delta=3)

    def test_rotation_scale_recovered_after_jpeg(self):
        img = sd.chelsea()
        forged, gt = _clone(img, (40, 40), (280, 150), 100, angle=20, scale=1.05)
        r, m = self.run_arr(forged, q=85)
        self.assertEqual(r["metrics"]["Verified clones"], 1)
        c = r["details"]["clones"][0]
        self.assertAlmostEqual(abs(c["rotation (deg)"]), 20, delta=2)
        self.assertFalse(c["mirrored"])
        # A->B direction is arbitrary, so the scale may come out inverted
        self.assertLess(min(abs(c["scale"] - 1.05), abs(c["scale"] - 1 / 1.05)), 0.03)
        self.assertGreater(self.f1(m, gt), 0.7)

    def test_mirrored_clone_and_rotation_convention(self):
        """Mirrored clones are matched (SIFT on the flipped image); rotation
        is counter-clockwise-positive (OpenCV convention)."""
        img = sd.astronaut()
        forged, gt = _clone(img, (300, 60), (60, 330), 110, angle=30, mirror=True)
        r, m = self.run_arr(forged, q=90)
        c = r["details"]["clones"][0]
        self.assertTrue(c["mirrored"])
        # B = R(30) mirror(A) and A = R(30) mirror(B): same angle either way
        self.assertAlmostEqual(c["rotation (deg)"], 30, delta=3)
        self.assertGreater(self.f1(m, gt), 0.6)

    def test_textures_are_not_clones(self):
        """Grass/gravel: affine-consistent SIFT matches (ZNCC > 0.9) but the
        copies differ by 5-10 grey levels in a PNG; a pasted copy would
        differ only by resampling. Old code reported 18.6 % / 2.9 %
        (gravel is in the hold-out set, kept out of the test for time)."""
        for name in ("grass",):
            r, _ = self.run_arr(np.stack([getattr(sd, name)()] * 3, -1))
            self.assertEqual(r["metrics"]["Verified clones"], 0, name)

    def test_smooth_gradient_is_not_cloning(self):
        """Old matcher: sky-like gradients hit the match cap as 'exact cloning'."""
        y, x = np.mgrid[0:400, 0:600]
        rng = np.random.default_rng(0)
        sky = 90 + 0.2 * y + 0.05 * x + rng.normal(0, 1.5, y.shape)
        arr = np.stack([sky * 0.6, sky * 0.8, sky], -1).clip(0, 255).astype(np.uint8)
        r = cmfd.detect_copy_move(self.save(arr, "sky.jpg", q=90))
        self.assertEqual(r["metrics"]["Verified clones"], 0)
        self.assertFalse([f for f in r["findings"] if f["level"] == "warning"])

    def test_real_clone_in_bundled_sample(self):
        """The bundled sample contains clouds cloned 317 px horizontally
        (ZNCC 0.98, mean |diff| ~1 grey level); it must be found."""
        r = cmfd.detect_copy_move(str(SAMPLE))
        shifts = [(abs(c["shift dx (px)"]), abs(c["shift dy (px)"]))
                  for c in r["details"]["clones"]]
        self.assertTrue(any(abs(dx - 317) < 3 and dy < 3 for dx, dy in shifts), shifts)

    def test_benchmark(self):
        """Seeded mini-benchmark (the full one is in Descriptions/CMFD.md)."""
        pos = [(sd.coffee(), (30, 250), (397, 81), 110, 12, 1.0, 95),
               (np.stack([sd.camera()] * 3, -1), (300, 330), (57, 205), 100, 27, 1.0, 75),
               (sd.immunohistochemistry(), (10, 10), (333, 301), 130, 5, 1.08, None)]
        hits, f1s = 0, []
        for img, s, d, size, ang, sc, q in pos:
            forged, gt = _clone(img, s, d, size, ang, sc)
            r, m = self.run_arr(forged, q)
            hits += r["metrics"]["Verified clones"] > 0
            f1s.append(self.f1(m, gt))
        # coffee PNG and the colour wheel were dense-branch false alarms
        neg = [(sd.coffee(), None), (sd.colorwheel()[..., :3], None)]
        fps = sum(self.run_arr(img, q)[0]["metrics"]["Verified clones"] > 0 for img, q in neg)
        self.assertGreaterEqual(hits, 3, f1s)
        self.assertGreater(np.mean(f1s), 0.6, f1s)
        self.assertEqual(fps, 0)


if __name__ == "__main__":
    unittest.main()
