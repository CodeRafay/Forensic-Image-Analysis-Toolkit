import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, PngImagePlugin
from skimage import data

from analysis import hash_verification as hv

SAMPLE = Path(__file__).resolve().parent.parent / "assets" / "sample images" / "sampleImg.jpeg"
BANNED = ("admissible", "legal", "authentic", "chain of custody")
ALLOWED = "This is not a legal chain of custody"


def _text(obj):
    return json.dumps(obj, default=str).replace(ALLOWED, "").lower()


class HashLedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp())
        cls.base = Image.open(SAMPLE).convert("RGB")
        cls.orig = str(SAMPLE)
        cls.png = cls._save(Image.fromarray(data.astronaut()), "a.png")
        info = PngImagePlugin.PngInfo()
        info.add_text("Comment", "metadata only")
        cls.png_meta = str(cls.dir / "a_meta.png")
        Image.open(cls.png).save(cls.png_meta, pnginfo=info)
        cls.other = cls._save(Image.fromarray(data.coffee()), "coffee.png")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    @classmethod
    def _save(cls, img, name, **kw):
        p = cls.dir / name
        img.save(p, **kw)
        return str(p)

    def _ledger(self, *paths):
        led = hv.new_ledger()
        for p in paths:
            led, _ = hv.add_record(led, p, label=Path(p).name)
        return led

    # ── hashes ────────────────────────────────────────────────────
    def test_compute_hashes(self):
        h = hv.compute_hashes(self.orig)
        self.assertEqual(len(h["sha256"]), 64)
        self.assertEqual(len(h["sha512"]), 128)
        self.assertEqual(len(h["md5"]), 32)
        self.assertEqual(h["dimensions"], [1024, 576])
        self.assertEqual(h["format"], "JPEG")
        self.assertEqual(h["size"], SAMPLE.stat().st_size)

    def test_pixel_hash_survives_metadata_only_change(self):
        a, b = hv.compute_hashes(self.png), hv.compute_hashes(self.png_meta)
        self.assertNotEqual(a["sha256"], b["sha256"])
        self.assertEqual(a["pixel_sha256"], b["pixel_sha256"])

    def test_label_never_stores_paths_and_input_not_mutated(self):
        led = hv.new_ledger()
        led2, rec = hv.add_record(led, self.png, label=r"C:\srv\tmp\uuid\photo.png")
        self.assertEqual(rec["label"], "photo.png")
        self.assertEqual(led, [])
        self.assertEqual(len(led2), 1)
        self.assertNotIn(str(self.dir), json.dumps(led2))

    # ── chain (ported from the old integration tests) ─────────────
    def test_untouched_chain_verifies(self):
        led = self._ledger(self.orig, self.png, self.other)
        self.assertEqual(hv.verify_chain(led), {"valid": True, "broken_at": None, "n": 3})

    def test_edited_record_is_detected(self):
        led = self._ledger(self.orig, self.png, self.other)
        led[1]["hashes"]["sha256"] = "0" * 64
        self.assertEqual(hv.verify_chain(led)["broken_at"], 1)

    def test_rehashed_record_still_breaks_next_link(self):
        led = self._ledger(self.orig, self.png, self.other)
        led[1] = hv._link({**led[1], "label": "forged"}, led[1]["prev_hash"])
        self.assertEqual(hv.verify_chain(led)["broken_at"], 2)

    def test_full_recompute_is_not_detectable_in_session(self):
        # documented limitation: rebuild every hash -> consistent chain again
        led = self._ledger(self.orig, self.png)
        forged, prev = [], hv.GENESIS_HASH
        for r in led:
            forged.append(hv._link({**r, "label": "forged"}, prev))
            prev = forged[-1]["record_hash"]
        self.assertTrue(hv.verify_chain(forged)["valid"])

    def test_broken_chain_gives_warning(self):
        led = self._ledger(self.orig)
        led[0]["label"] = "edited"
        res = hv.verify_image(led, self.orig)
        self.assertIn("warning", [f["level"] for f in res["findings"]])

    # ── verify_image ──────────────────────────────────────────────
    def test_exact_match(self):
        res = hv.verify_image(self._ledger(self.png, self.orig), self.orig)
        self.assertEqual(res["status"], "ok")
        f0 = [f for f in res["findings"] if "Byte-identical" in f["text"]]
        self.assertEqual(f0[0]["level"], "info")
        self.assertIn("record #2", f0[0]["text"])
        self.assertEqual(res["metrics"]["Byte-identical matches"], 1)

    def test_pixel_only_match(self):
        res = hv.verify_image(self._ledger(self.png), self.png_meta)
        self.assertEqual(res["metrics"]["Pixel-identical matches"], 1)
        self.assertTrue(any(f["level"] == "notice" and "metadata/container" in f["text"]
                            for f in res["findings"]))

    def test_not_in_ledger(self):
        res = hv.verify_image(self._ledger(self.orig), self.other)
        self.assertTrue(any("Not in this session's ledger" in f["text"]
                            for f in res["findings"]))

    def test_empty_ledger_and_bad_path(self):
        self.assertEqual(hv.verify_image([], self.orig)["status"], "insufficient_data")
        self.assertEqual(hv.verify_image([], "missing.jpg")["status"], "error")

    def test_splice_never_reads_as_integrity(self):
        a = np.asarray(self.base).copy()
        a[300:400, 500:600] = a[50:150, 100:200]  # 100x100 copy-paste
        buf = io.BytesIO()
        Image.fromarray(a).save(buf, "JPEG", quality=90)
        p = self.dir / "splice.jpg"
        p.write_bytes(buf.getvalue())
        res = hv.verify_image(self._ledger(self.orig), str(p))
        texts = [f["text"] for f in res["findings"]]
        self.assertFalse(any("Byte-identical" in t or "Pixels identical" in t for t in texts))
        for f in res["findings"]:
            if "Visually similar" in f["text"]:
                self.assertEqual(f["level"], "notice")
                self.assertIn("NOT evidence of integrity", f["text"])
        self.assertEqual(res["metrics"]["Byte-identical matches"], 0)
        # the documented weakness: this splice still reads as visually similar
        self.assertEqual(res["metrics"]["Visually similar matches"], 1)

    def test_no_overclaiming_words(self):
        led = self._ledger(self.orig, self.png)
        for q in (self.orig, self.png_meta, self.other):
            self.assertFalse([w for w in BANNED if w in _text(hv.verify_image(led, q))])
        self.assertIn(ALLOWED, " ".join(hv.LIMITATIONS))

    def test_threshold_benchmark(self):
        # benign re-encodes must match; unrelated images must not
        led = self._ledger(self.orig)
        benign = 0
        cases = [("q", q) for q in (30, 70, 95)] + [("s", s) for s in (0.5, 2.0)]
        for kind, v in cases:
            im = self.base if kind == "q" else self.base.resize(
                (int(1024 * v), int(576 * v)), Image.Resampling.LANCZOS)
            p = self._save(im, f"b_{kind}{v}.jpg", quality=v if kind == "q" else 90)
            benign += hv.verify_image(led, p)["metrics"]["Visually similar matches"]
        self.assertEqual(benign, len(cases))
        false = 0
        for name in ("astronaut", "coffee", "chelsea", "camera", "rocket"):
            p = self._save(Image.fromarray(getattr(data, name)()), f"u_{name}.png")
            false += hv.verify_image(led, p)["metrics"]["Visually similar matches"]
        self.assertEqual(false, 0)

    # ── export / import ───────────────────────────────────────────
    def test_unkeyed_roundtrip(self):
        led = self._ledger(self.orig, self.png)
        blob = hv.export_ledger(led)
        doc = json.loads(blob)
        self.assertEqual(doc["format"], "veritas-ledger/1")
        self.assertEqual(doc["signature"]["alg"], "SHA-256")
        self.assertIn("integrity-only", doc["signature"]["note"])
        got, rep = hv.import_ledger(blob)
        self.assertIsNone(rep["signature_valid"])
        self.assertTrue(rep["digest_ok"] and rep["accepted"] and rep["chain_valid"])
        self.assertEqual(got, led)

    def test_hmac_roundtrip_and_wrong_key(self):
        led = self._ledger(self.orig)
        blob = hv.export_ledger(led, key=b"server-secret")
        self.assertEqual(json.loads(blob)["signature"]["alg"], "HMAC-SHA256")
        self.assertTrue(hv.import_ledger(blob, key=b"server-secret")[1]["signature_valid"])
        rep = hv.import_ledger(blob, key=b"other")[1]
        self.assertFalse(rep["signature_valid"])
        self.assertFalse(rep["accepted"])

    def test_accidental_edit_rejected(self):
        blob = hv.export_ledger(self._ledger(self.orig))
        led, rep = hv.import_ledger(blob.replace(b"sampleImg", b"sampleImX"))
        self.assertFalse(rep["digest_ok"])
        self.assertFalse(rep["accepted"])
        self.assertEqual(led, [])

    def _resigned(self, key):
        """Attacker edits a record, rebuilds the chain, re-signs with `key`."""
        doc = json.loads(hv.export_ledger(self._ledger(self.orig, self.png), key=b"server"))
        forged, prev = [], hv.GENESIS_HASH
        for r in doc["records"]:
            forged.append(hv._link({**r, "label": "forged"}, prev))
            prev = forged[-1]["record_hash"]
        body = {"format": doc["format"], "exported_utc": doc["exported_utc"],
                "records": forged}
        return json.dumps({**body, "signature": hv._sign(body, key)}).encode()

    def test_resign_attack_detected_with_hmac(self):
        for attacker_key in (None, b"guess"):
            led, rep = hv.import_ledger(self._resigned(attacker_key), key=b"server")
            self.assertFalse(rep["signature_valid"])
            self.assertFalse(rep["accepted"])
            self.assertEqual(led, [])

    def test_resign_attack_undetectable_without_key_and_says_so(self):
        led, rep = hv.import_ledger(self._resigned(None))
        self.assertTrue(rep["accepted"])  # nothing to check against
        self.assertIsNone(rep["signature_valid"])
        self.assertIn("anyone can edit", rep["message"])
        self.assertEqual(led[0]["label"], "forged")

    def test_merge_relinks_and_dedupes(self):
        a = self._ledger(self.orig, self.png)
        b = self._ledger(self.png, self.other)
        merged, rep = hv.import_ledger(hv.export_ledger(b), into=a)
        self.assertTrue(hv.verify_chain(merged)["valid"])
        self.assertEqual((rep["merged"], rep["duplicates_skipped"]), (1, 1))
        self.assertEqual(len(merged), 3)
        new = merged[-1]
        self.assertEqual(new["prev_hash"], a[-1]["record_hash"])
        self.assertEqual(new["original_record_hash"], b[1]["record_hash"])
        self.assertEqual(new["id"], 3)
        self.assertEqual(len(a), 2)  # input untouched

    def test_malformed_import(self):
        for bad in (b"{}", b'{"format":"veritas-ledger/1","records":[{"id":1}]}'):
            with self.assertRaises(ValueError):
                hv.import_ledger(bad)

    def test_stats(self):
        s = hv.ledger_stats(self._ledger(self.orig, self.png))
        self.assertEqual(s["records"], 2)
        self.assertTrue(s["chain_valid"])
        self.assertEqual(hv.ledger_stats([])["records"], 0)


if __name__ == "__main__":
    unittest.main()
