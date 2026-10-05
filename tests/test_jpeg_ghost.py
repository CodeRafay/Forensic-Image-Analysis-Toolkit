"""JPEG ghosts (Farid 2009): behaviour + seeded splice benchmark."""
import io
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
import skimage.data as sd
from PIL import Image

from analysis.jpeg_ghost import analyze_jpeg_ghost


def _clean(a):
    im = Image.fromarray(a[..., :3] if a.ndim == 3 else np.stack([a] * 3, -1))
    return np.asarray(im.resize((round(im.width * .8), round(im.height * .8)),
                                Image.Resampling.LANCZOS))


def _jpeg(a, q):
    b = io.BytesIO()
    Image.fromarray(a).save(b, "JPEG", quality=q)
    return np.asarray(Image.open(io.BytesIO(b.getvalue())).convert("RGB")), b.getvalue()


def _warned(r):
    return any(f["level"] == "warning" for f in r["findings"])


class TestJpegGhost(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.imgs = [_clean(sd.chelsea()), _clean(sd.rocket()), _clean(sd.coffee()),
                    _clean(sd.astronaut())]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _save(self, name, data):
        p = self.tmp / name
        if isinstance(data, bytes):
            p.write_bytes(data)
        else:
            Image.fromarray(data).save(p)
        return str(p)

    def test_primary_quality_from_table(self):
        _, b = _jpeg(self.imgs[0], 83)
        r = analyze_jpeg_ghost(self._save("q83.jpg", b))
        self.assertEqual(r["details"]["primary_q"], 83)  # not the argmin (95)

    def test_whole_image_quality(self):
        """q90 -> q95: the earlier quality is found exactly (it used to be
        capped at final - 10); a single q85 save shows no whole-image ghost."""
        a1, _ = _jpeg(self.imgs[0], 90)
        r = analyze_jpeg_ghost(self._save("w.jpg", _jpeg(a1, 95)[1]))
        self.assertEqual(r["details"]["whole_image_ghost_q"], 90)
        r = analyze_jpeg_ghost(self._save("s.jpg", _jpeg(self.imgs[1], 85)[1]))
        self.assertIsNone(r["details"]["whole_image_ghost_q"])

    def test_tiny_insufficient(self):
        r = analyze_jpeg_ghost(self._save("tiny.png", self.imgs[0][:32, :32]))
        self.assertEqual(r["status"], "insufficient_data")

    def test_benchmark(self):
        """Positives: patch from a q1 JPEG (1/9 of the area), on the file
        grid or 8x8-offset from it (Farid's grid-shift case), pasted into a
        clean image saved at q2. Negatives: single JPEG,
        PNG, whole-image double JPEG."""
        rng = np.random.default_rng(5)
        tp, fp, n_neg = 0, 0, 0
        for i, host in enumerate(self.imgs):
            donor = self.imgs[(i + 1) % len(self.imgs)]
            q1, q2 = [(60, 90), (70, 95), (60, 85), (50, 90)][i]
            off = [(0, 0), (3, 3), (4, 4), (2, 5)][i]  # donor's grid offset
            d1 = np.roll(_jpeg(np.ascontiguousarray(np.roll(donor, off, (0, 1))), q1)[0],
                         (-off[0], -off[1]), (0, 1))
            h, w = host.shape[:2]
            ph = min(h, d1.shape[0]) // 3 // 8 * 8
            pw = min(w, d1.shape[1]) // 3 // 8 * 8
            y0 = int(rng.integers(0, (h - ph) // 8)) * 8
            x0 = int(rng.integers(0, (w - pw) // 8)) * 8
            sp = host.copy()
            sp[y0:y0 + ph, x0:x0 + pw] = d1[:ph, :pw]
            _, b = _jpeg(sp, q2)
            r = analyze_jpeg_ghost(self._save(f"p{i}.jpg", b))
            tp += _warned(r) and abs(r["details"]["ghost_q"] - q1) <= 10

            for tag, data in (("s85.jpg", _jpeg(host, 85)[1]), ("n.png", host)):
                fp += _warned(analyze_jpeg_ghost(self._save(f"{i}{tag}", data)))
                n_neg += 1
        a1, _ = _jpeg(self.imgs[0], 60)
        r = analyze_jpeg_ghost(self._save("dj.jpg", _jpeg(a1, 90)[1]))
        self.assertIsNotNone(r["details"]["whole_image_ghost_q"])
        fp += _warned(r)
        self.assertGreaterEqual(tp, 3)
        self.assertEqual(fp, 0, f"{fp}/{n_neg + 1} false alarms")


if __name__ == "__main__":
    unittest.main()
