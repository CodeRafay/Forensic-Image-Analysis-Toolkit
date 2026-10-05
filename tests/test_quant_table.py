import io
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from analysis.quant_table import (analyze_quantization_table, estimate_jpeg_quality,
                                  extract_jpeg_quantization_tables, is_standard_table)

SAMPLE = Path(__file__).resolve().parent.parent / "assets" / "sample images" / "sampleImg.jpeg"


def _jpeg(tmp, name, arr, **kw):
    p = tmp / name
    Image.fromarray(arr).save(p, "JPEG", **kw)
    return str(p)


class TestQuantTable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import tempfile
        cls.tmp = Path(tempfile.mkdtemp())
        cls.rgb = np.asarray(Image.open(SAMPLE).convert("RGB"))[:256, :256]

    def test_quality_exact_for_libjpeg(self):
        small = self.rgb[:16, :16]
        for q in range(1, 101):
            p = _jpeg(self.tmp, f"q{q}.jpg", small, quality=q)
            t = extract_jpeg_quantization_tables(p)
            self.assertEqual(estimate_jpeg_quality(t[0], 0), q, q)
            # chroma q1-3 are the same all-255 table: the highest q is reported
            self.assertEqual(estimate_jpeg_quality(t[1], 1), max(q, 3), q)
            self.assertTrue(is_standard_table(t[0], 0), q)
            self.assertTrue(is_standard_table(t[1], 1), q)

    def test_non_ijg_table_falls_back_to_inversion(self):
        t = np.array(extract_jpeg_quantization_tables(
            _jpeg(self.tmp, "q75.jpg", self.rgb[:16, :16], quality=75))[0])
        t[5] += 1  # no longer an exact libjpeg table
        self.assertLessEqual(abs(estimate_jpeg_quality(t, 0) - 75), 1)

    def test_contract_and_family(self):
        r = analyze_quantization_table(_jpeg(self.tmp, "a.jpg", self.rgb, quality=80))
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["details"]["encoder_family"], "IJG")
        self.assertEqual(r["metrics"]["Table 0 estimated quality (IJG)"], 80)
        rows = r["tables"]["Table 0 (luminance)"]
        self.assertEqual((len(rows), len(rows[0])), (8, 8))
        self.assertTrue(any("IJG" in f["text"] for f in r["findings"]))

    def test_custom_table_detected(self):
        rng = np.random.default_rng(0)
        custom = [int(v) for v in rng.integers(2, 60, 64)]
        p = _jpeg(self.tmp, "c.jpg", self.rgb, qtables=[custom, custom])
        r = analyze_quantization_table(p)
        self.assertEqual(r["details"]["encoder_family"], "custom")
        self.assertTrue(any("custom" in f["text"] for f in r["findings"]))

    def test_all_ones_cannot_classify(self):
        p = _jpeg(self.tmp, "ones.jpg", self.rgb, qtables=[[1] * 64, [1] * 64])
        r = analyze_quantization_table(p)
        self.assertEqual(r["details"]["encoder_family"], "unclassifiable")

    def test_exif_reported_as_context(self):
        r = analyze_quantization_table(str(SAMPLE))
        self.assertEqual(r["details"]["exif"].get("Make"), "SONY")
        self.assertTrue(any("EXIF" in f["text"] and f["level"] == "info" for f in r["findings"]))

    def test_png_not_applicable(self):
        p = self.tmp / "x.png"
        Image.fromarray(self.rgb).save(p)
        self.assertEqual(analyze_quantization_table(str(p))["status"], "not_applicable")

    def test_never_raises(self):
        self.assertEqual(analyze_quantization_table("does/not/exist.jpg")["status"], "error")


if __name__ == "__main__":
    unittest.main()
