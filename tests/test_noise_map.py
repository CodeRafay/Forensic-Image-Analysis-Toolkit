"""Splicebuster (Cozzolino, Poggi & Verdoliva 2015) residual consistency."""
import shutil
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np
import skimage.data as sd
from PIL import Image
from scipy.ndimage import gaussian_filter

from analysis import noise_map as nm


def _scene(name, long=1024):
    a = getattr(sd, name)()
    a = np.stack([a] * 3, -1) if a.ndim == 2 else a[..., :3]
    im = Image.fromarray(a)
    s = long / max(im.size)
    im = im.resize((round(im.width * s) // 2 * 2, round(im.height * s) // 2 * 2), Image.BICUBIC)
    return np.asarray(im, np.float32)


DEM = [cv2.COLOR_BayerRG2RGB, cv2.COLOR_BayerRG2RGB_EA, cv2.COLOR_BayerRG2RGB_VNG]


def _camera(sc, rng, gain=None, dem=0):
    """RGGB mosaic -> shot + read noise -> OpenCV demosaic -> gamma ->
    optional unsharp mask (same pipeline as the documented benchmark)."""
    gain = rng.uniform(0.3, 2.0) if gain is None else gain
    read = rng.uniform(0.5, 3.0)
    sharpen = rng.choice([0.0, 0.5, 1.0])
    lin = (sc / 255.0) ** 2.2 * 235
    bay = np.empty(lin.shape[:2], np.float32)
    bay[0::2, 0::2] = lin[0::2, 0::2, 0]
    bay[0::2, 1::2] = lin[0::2, 1::2, 1]
    bay[1::2, 0::2] = lin[1::2, 0::2, 1]
    bay[1::2, 1::2] = lin[1::2, 1::2, 2]
    bay = bay + rng.normal(0, 1, bay.shape) * np.sqrt(gain * bay + read ** 2)
    bay = np.clip(np.rint(bay), 0, 255).astype(np.uint8)
    rgb = cv2.cvtColor(bay, DEM[dem]).astype(np.float32)
    rgb = 255 * (rgb / 255) ** (1 / 2.2)
    if sharpen:
        rgb = rgb + sharpen * (rgb - gaussian_filter(rgb, (1, 1, 0)))
    return np.clip(np.rint(rgb), 0, 255).astype(np.uint8)


class TestNoiseMap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _save(self, name, a, q=None):
        p = self.tmp / name
        Image.fromarray(a).save(p, **({"quality": q} if q else {}))
        return str(p)

    def test_small_and_flat_insufficient(self):
        g = _scene("coffee").astype(np.uint8)
        for a in (g[:200, :300], np.full((400, 400, 3), 128, np.uint8)):
            self.assertEqual(nm.analyze_noise(self._save("s.png", a))["status"],
                             "insufficient_data")

    def test_codes(self):
        """3rd-order residual -1,3,-3,1; quantised by Q, truncated to T."""
        x = np.zeros((1, 12), np.float32)
        x[0, 5], x[0, 8] = 1.0, 9.0
        r = (x[:, 3:] - x[:, :-3]) + 3 * (x[:, 1:-2] - x[:, 2:-1])
        q = np.clip(np.rint(r / nm.Q), -nm.T, nm.T) + nm.T
        n = 2 * nm.T + 1
        expect = q[:, :-3] + n * q[:, 1:-2] + n * n * q[:, 2:-1] + n ** 3 * q[:, 3:]
        np.testing.assert_array_equal(nm._codes(x), expect)
        self.assertLess(int(nm._codes(x).max()), n ** 4)

    def test_benchmark(self):
        """Camera-like negatives vs splices from another photo + camera
        chain (1/9 area), JPEG q92. Hold-out numbers in
        Descriptions/Noise_Ghost.md: FPR 7/132, TPR 38/56."""
        rng = np.random.default_rng(0)
        fp = tp = loc = 0
        names = ("chelsea", "astronaut", "rocket", "coffee", "camera", "cat")
        for i, n in enumerate(names):
            host = _camera(_scene(n), rng)
            donor = _camera(_scene(names[(i + 1) % 6]), rng,
                            gain=rng.uniform(0.3, 2) * rng.choice([0.3, 3.0]),
                            dem=int(rng.integers(0, 3)))
            h, w = host.shape[:2]
            c = host.copy()
            c[h // 3:h // 3 + h // 3, w // 3:w // 3 + w // 3] = donor[:h // 3, :w // 3]
            fp += nm.analyze_noise(self._save(f"n{i}.jpg", host, 92))["details"]["flagged"]
            r = nm.analyze_noise(self._save(f"p{i}.jpg", c, 92))
            if r["details"]["flagged"]:
                tp += 1
                ov = next(v for k, v in r["images"].items() if "red" in k).astype(int)
                gt = np.zeros(ov.shape[:2], bool)
                gt[h // 3:2 * h // 3, w // 3:2 * w // 3] = True
                red = ov[..., 0] - ov[..., 1] > 40
                loc += (red & gt).sum() > 0.5 * red.sum()
        print(f"Splicebuster test benchmark TP {tp}/6 FP {fp}/6 localised {loc}")
        self.assertEqual(fp, 0)
        self.assertGreaterEqual(tp, 3)
        self.assertEqual(loc, tp)

    def test_contract_fields_and_wording(self):
        rng = np.random.default_rng(1)
        r = nm.analyze_noise(self._save("c.png", _camera(_scene("chelsea"), rng)))
        self.assertEqual(r["status"], "ok")
        text = " ".join(f["text"] for f in r["findings"]).lower()
        for bad in ("authentic", "genuine", "no manipulation", "proves"):
            self.assertNotIn(bad, text)
        self.assertLessEqual(len(r["images"]), 4)
        for im in r["images"].values():
            self.assertEqual(im.dtype, np.uint8)
        for v in r["metrics"].values():
            self.assertTrue(np.isfinite(v))


if __name__ == "__main__":
    unittest.main()
