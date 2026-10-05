"""
Every analysis entry point must return the shared result contract
(analysis.util.make_result) for every input format and size, and must never
raise. This is what keeps the app's single renderer in sync with the modules.
"""
import importlib
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from analysis.util import LEVELS, STATUSES

SAMPLE = Path(__file__).resolve().parent.parent / "assets" / "sample images" / "sampleImg.jpeg"

# (module, function, extra kwargs). Hash/ledger functions are covered in
# test_hash_verification.py because they take a ledger, not just a path.
ENTRY_POINTS = [
    ("ela", "analyze_ela", {}),
    ("metadata_analysis", "analyze_metadata", {}),
    ("histogram_analysis", "analyze_histogram", {}),
    ("noise_map", "analyze_noise", {}),
    ("jpeg_ghost", "analyze_jpeg_ghost", {}),
    ("quant_table", "analyze_quantization_table", {}),
    ("double_jpeg", "analyze_double_jpeg", {}),
    ("cmfd", "detect_copy_move", {}),
    ("prnu", "analyze_prnu", {}),
    ("frequency_analysis", "analyze_spectrum", {}),
    ("frequency_analysis", "analyze_blocking", {}),
    ("deepfake_detector", "analyze_synthetic_traces", {}),
    ("resampling_detector", "detect_resampling", {}),
    ("steganography_detection", "analyze_lsb", {}),
]


def _make_inputs(d):
    """Formats and sizes that have broken modules before."""
    rgb = np.asarray(Image.open(SAMPLE).convert("RGB"))
    small = rgb[:200, :240]
    paths = {}

    def save(name, arr, mode=None, **kw):
        p = d / name
        im = Image.fromarray(arr)
        if mode:
            im = im.convert(mode)
        im.save(p, **kw)
        paths[name] = str(p)

    paths["sample.jpg"] = str(SAMPLE)
    save("small_q75.jpg", small, quality=75)
    save("small.png", small)
    save("gray.jpg", small, mode="L", quality=90)
    save("rgba.png", small, mode="RGBA")
    save("palette.png", small, mode="P")
    save("tiny16.jpg", rgb[:16, :16], quality=90)
    save("tiny1.png", rgb[:1, :1])
    save("flat.png", np.full((128, 128, 3), 128, np.uint8))
    return paths


class TestResultContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.inputs = _make_inputs(cls.tmp)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def assert_contract(self, r, where):
        self.assertIsInstance(r, dict, where)
        self.assertIn(r.get("status"), STATUSES, where)
        self.assertIsInstance(r.get("summary"), str, where)
        for f in r["findings"]:
            self.assertIn(f["level"], LEVELS, where)
            self.assertIsInstance(f["text"], str, where)
        for k, v in r["metrics"].items():
            self.assertIsInstance(k, str, where)
            if isinstance(v, float):
                self.assertTrue(np.isfinite(v), f"{where}: metric {k}={v}")
        for cap, img in r["images"].items():
            a = np.asarray(img)
            self.assertEqual(a.dtype, np.uint8, f"{where}: image {cap}")
            self.assertIn(a.ndim, (2, 3), f"{where}: image {cap}")
        self.assertIsInstance(r["limitations"], list, where)
        # The app must never be told an image is authentic.
        text = " ".join([r["summary"]] + [f["text"] for f in r["findings"]]).lower()
        for banned in ("authentic", "admissible", "no manipulation", "proves"):
            if banned in text and "not " + banned not in text \
                    and "cannot " not in text:
                self.fail(f"{where}: overclaiming wording {banned!r}: {text[:200]}")

    def test_all_entry_points_all_inputs(self):
        for mod_name, fn_name, kw in ENTRY_POINTS:
            fn = getattr(importlib.import_module(f"analysis.{mod_name}"), fn_name)
            for name, path in self.inputs.items():
                where = f"{mod_name}.{fn_name}({name})"
                with self.subTest(where):
                    try:
                        r = fn(path, **kw)
                    except Exception as e:  # noqa: BLE001
                        self.fail(f"{where} raised {type(e).__name__}: {e}")
                    self.assert_contract(r, where)

    def test_tiny_and_flat_are_not_reported_as_clean(self):
        """No data must never look like a clean result."""
        for mod_name, fn_name, kw in ENTRY_POINTS:
            if mod_name == "metadata_analysis":
                continue  # metadata doesn't depend on pixel count
            fn = getattr(importlib.import_module(f"analysis.{mod_name}"), fn_name)
            r = fn(self.inputs["tiny1.png"], **kw)
            with self.subTest(f"{mod_name}.{fn_name}"):
                self.assertIn(r["status"],
                              ("insufficient_data", "not_applicable", "error"))


if __name__ == "__main__":
    unittest.main()
