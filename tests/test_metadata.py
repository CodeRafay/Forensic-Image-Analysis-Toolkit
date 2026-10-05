"""Behavioural tests for analysis.metadata_analysis (fixtures built with piexif)."""
import io
import shutil
import tempfile
import unittest
import warnings
from pathlib import Path

import numpy as np
import piexif
from PIL import Image, PngImagePlugin

from analysis import metadata_analysis as md

SAMPLE = Path(__file__).resolve().parent.parent / "assets" / "sample images" / "sampleImg.jpeg"


def _photo(w=480, h=320, seed=0):
    """Smooth random 'photo' (textured enough for the thumbnail check)."""
    rng = np.random.default_rng(seed)
    small = rng.integers(0, 256, (h // 16, w // 16, 3), dtype=np.uint8)
    img = Image.fromarray(small).resize((w, h), Image.BICUBIC)
    noise = rng.normal(0, 6, (h, w, 3))
    return np.clip(np.asarray(img, float) + noise, 0, 255).astype(np.uint8)


def _jpeg_bytes(arr, q=90):
    b = io.BytesIO()
    Image.fromarray(arr).save(b, "JPEG", quality=q)
    return b.getvalue()


def _thumb(arr, width=160):
    h, w = arr.shape[:2]
    return _jpeg_bytes(np.asarray(Image.fromarray(arr).resize(
        (width, round(h * width / w)), Image.BILINEAR)), 85)


def _save(path, arr, zeroth=None, exif_ifd=None, gps=None, thumb=None, q=90):
    d = {"0th": zeroth or {}, "Exif": exif_ifd or {}, "GPS": gps or {},
         "1st": {}, "thumbnail": None}
    if thumb:
        d["1st"] = {piexif.ImageIFD.JPEGInterchangeFormat: 0,
                    piexif.ImageIFD.JPEGInterchangeFormatLength: 0}
        d["thumbnail"] = thumb
    Image.fromarray(arr).save(path, "JPEG", quality=q, exif=piexif.dump(d))
    return str(path)


CAMERA = {piexif.ImageIFD.Make: b"Canon", piexif.ImageIFD.Model: b"Canon EOS 80D",
          piexif.ImageIFD.DateTime: b"2023:05:01 10:00:00"}
CAMERA_EXIF = {piexif.ExifIFD.DateTimeOriginal: b"2023:05:01 10:00:00",
               piexif.ExifIFD.DateTimeDigitized: b"2023:05:01 10:00:00",
               piexif.ExifIFD.MakerNote: b"\x00" * 64,
               piexif.ExifIFD.PixelXDimension: 480,
               piexif.ExifIFD.PixelYDimension: 320}


def levels(r, word):
    """Levels of findings whose text contains word (case-insensitive)."""
    return [f["level"] for f in r["findings"] if word.lower() in f["text"].lower()]


class TestMetadata(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = Path(tempfile.mkdtemp())
        cls.arr = _photo()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.d, ignore_errors=True)

    def run_on(self, path):
        with warnings.catch_warnings():
            warnings.simplefilter("error", ResourceWarning)
            r = md.analyze_metadata(path)
        self.assertEqual(r["status"], "ok", r["summary"])
        self.assertTrue(r["limitations"])
        text = " ".join(f["text"] for f in r["findings"]).lower()
        for banned in ("authentic", "verdict", "score", "double compression"):
            self.assertNotIn(banned, text)
        return r

    def test_camera_file_clean(self):
        p = _save(self.d / "cam.jpg", self.arr, CAMERA, CAMERA_EXIF,
                  thumb=_thumb(self.arr))
        r = self.run_on(p)
        self.assertEqual([f for f in r["findings"] if f["level"] != "info"], [],
                         r["findings"])
        self.assertIn("no inconsistency found",
                      " ".join(f["text"] for f in r["findings"]))
        self.assertEqual(r["tables"]["Camera"]["Make"], "Canon")
        self.assertIn("Thumbnail correlation", r["metrics"])
        self.assertEqual(len(r["images"]), 1)

    def test_no_exif_jpeg_is_notice_not_clean(self):
        p = self.d / "plain.jpg"
        Image.fromarray(self.arr).save(p, "JPEG", quality=90)  # jfif/dpi only
        r = self.run_on(str(p))
        self.assertEqual(r["metrics"]["EXIF tags (count)"], 0)
        self.assertEqual(levels(r, "no camera metadata"), ["notice"])

    def test_photoshop_software_is_editor_notice(self):
        z = {**CAMERA, piexif.ImageIFD.Software: b"Adobe Photoshop 25.0 (Windows)"}
        r = self.run_on(_save(self.d / "ps.jpg", self.arr, z, CAMERA_EXIF))
        self.assertIn("notice", levels(r, "image editor"))

    def test_raw_developer_and_firmware(self):
        z = {**CAMERA, piexif.ImageIFD.Software: b"Adobe Photoshop Lightroom Classic 13.0"}
        r = self.run_on(_save(self.d / "lr.jpg", self.arr, z, CAMERA_EXIF))
        self.assertEqual(levels(r, "raw developer"), ["notice"])
        self.assertEqual(levels(r, "image editor"), [])
        z = {**CAMERA, piexif.ImageIFD.Software: b"G998BXXU5CVDB"}
        r = self.run_on(_save(self.d / "fw.jpg", self.arr, z, CAMERA_EXIF))
        self.assertEqual(levels(r, "G998BXXU5CVDB"), ["info"])

    def test_stale_thumbnail_warns(self):
        edited = self.arr.copy()
        edited[80:200, 150:330] = _photo(192, 128, seed=7)[:120, :180]
        p = _save(self.d / "stale.jpg", edited, CAMERA, CAMERA_EXIF,
                  thumb=_thumb(self.arr))
        r = self.run_on(p)
        self.assertEqual(levels(r, "thumbnail differs from main image"), ["warning"])

    def test_sample_image_real_stale_thumbnail(self):
        r = self.run_on(str(SAMPLE))
        self.assertEqual(levels(r, "thumbnail differs"), ["warning"])
        self.assertEqual(levels(r, "raw developer"), ["notice"])  # darktable

    def test_gps_version_only_has_no_coordinates(self):
        gps = {piexif.GPSIFD.GPSVersionID: (2, 2, 0, 0)}
        r = self.run_on(_save(self.d / "gps0.jpg", self.arr, CAMERA, CAMERA_EXIF, gps))
        self.assertNotIn("coordinates", r["tables"]["GPS"])
        self.assertEqual(levels(r, "0.0, 0.0"), [])
        self.assertEqual(levels(r, "without a latitude"), ["info"])

    def test_gps_coordinates(self):
        gps = {piexif.GPSIFD.GPSLatitudeRef: b"S",
               piexif.GPSIFD.GPSLatitude: ((33, 1), (52, 1), (0, 1)),
               piexif.GPSIFD.GPSLongitudeRef: b"E",
               piexif.GPSIFD.GPSLongitude: ((151, 1), (12, 1), (36, 1))}
        r = self.run_on(_save(self.d / "gps.jpg", self.arr, CAMERA, CAMERA_EXIF, gps))
        self.assertEqual(r["tables"]["GPS"]["coordinates"], "-33.866667, 151.21")

    def test_date_inconsistencies(self):
        z = {**CAMERA, piexif.ImageIFD.DateTime: b"2023:06:01 09:00:00"}
        r = self.run_on(_save(self.d / "later.jpg", self.arr, z, CAMERA_EXIF))
        self.assertEqual(levels(r, "later than DateTimeOriginal"), ["notice"])

        z = {**CAMERA, piexif.ImageIFD.DateTime: b"2022:01:01 00:00:00"}
        r = self.run_on(_save(self.d / "before.jpg", self.arr, z, CAMERA_EXIF))
        self.assertEqual(levels(r, "earlier than DateTimeOriginal"), ["warning"])

        e = {**CAMERA_EXIF, piexif.ExifIFD.DateTimeOriginal: b"2023:02:30 10:00:00"}
        r = self.run_on(_save(self.d / "bad.jpg", self.arr, CAMERA, e))
        self.assertEqual(levels(r, "Impossible DateTimeOriginal"), ["warning"])

        e = {**CAMERA_EXIF, piexif.ExifIFD.DateTimeDigitized: b"2023:04:01 10:00:00"}
        r = self.run_on(_save(self.d / "digi.jpg", self.arr, CAMERA, e))
        self.assertEqual(levels(r, "digitised before"), ["warning"])

    def test_offsets_used_in_comparison(self):
        # Same instant in two zones: 12:00+02:00 == 10:00+00:00.
        z = {**CAMERA, piexif.ImageIFD.DateTime: b"2023:05:01 12:00:00"}
        e = {**CAMERA_EXIF, piexif.ExifIFD.OffsetTime: b"+02:00",
                                 piexif.ExifIFD.OffsetTimeOriginal: b"+00:00"}
        r = self.run_on(_save(self.d / "tz.jpg", self.arr, z, e))
        self.assertEqual(levels(r, "DateTimeOriginal"), [])

    def test_makernote_and_dimensions(self):
        e = {k: v for k, v in CAMERA_EXIF.items() if k != piexif.ExifIFD.MakerNote}
        e[piexif.ExifIFD.PixelXDimension] = 6000
        e[piexif.ExifIFD.PixelYDimension] = 4000
        r = self.run_on(_save(self.d / "mn.jpg", self.arr, CAMERA, e))
        self.assertEqual(levels(r, "No MakerNote"), ["notice"])
        self.assertEqual(levels(r, "resized or cropped"), ["notice"])

    def test_missing_file_is_error(self):
        self.assertEqual(md.analyze_metadata(str(self.d / "nope.jpg"))["status"], "error")

    def test_png_text_chunks(self):
        info = PngImagePlugin.PngInfo()
        info.add_text("Software", "GIMP 2.10.36")
        info.add_itxt("Description", "holiday")
        p = self.d / "t.png"
        Image.fromarray(self.arr).save(p, pnginfo=info)
        r = self.run_on(str(p))
        self.assertEqual(levels(r, "normal for PNG"), ["info"])
        self.assertEqual(r["tables"]["PNG text chunks"]["Description"], "holiday")
        self.assertIn("notice", levels(r, "GIMP"))

        info = PngImagePlugin.PngInfo()
        info.add_text("parameters", "a cat, Steps: 20, Sampler: Euler a")
        p = self.d / "sd.png"
        Image.fromarray(self.arr).save(p, pnginfo=info)
        self.assertEqual(levels(self.run_on(str(p)), "image-generation"), ["warning"])

    def test_xmp_history(self):
        xmp = ('<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF '
               'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
               '<rdf:Description xmlns:xmp="http://ns.adobe.com/xap/1.0/" '
               'xmlns:xmpMM="http://ns.adobe.com/xap/1.0/mm/" '
               'xmlns:stEvt="http://ns.adobe.com/xap/1.0/sType/ResourceEvent#" '
               'xmlns:photoshop="http://ns.adobe.com/photoshop/1.0/" '
               'xmp:CreatorTool="Adobe Photoshop 24.1">'
               '<xmpMM:History><rdf:Seq>'
               '<rdf:li stEvt:action="created" stEvt:softwareAgent="Adobe Photoshop 24.1"/>'
               '<rdf:li><stEvt:action>saved</stEvt:action><stEvt:changed>/</stEvt:changed></rdf:li>'
               '</rdf:Seq></xmpMM:History>'
               '<photoshop:DocumentAncestors><rdf:Bag><rdf:li>xmp.did:1</rdf:li>'
               '<rdf:li>xmp.did:2</rdf:li></rdf:Bag></photoshop:DocumentAncestors>'
               '</rdf:Description></rdf:RDF></x:xmpmeta>')
        p = self.d / "xmp.jpg"
        Image.fromarray(self.arr).save(p, "JPEG", xmp=xmp.encode())
        r = self.run_on(str(p))
        self.assertEqual(len(r["tables"]["XMP history"]), 2)
        self.assertEqual(levels(r, "DocumentAncestors lists 2"), ["notice"])
        self.assertIn("notice", levels(r, "Photoshop"))
        self.assertIn("XMP CreatorTool", [s["source"] for s in r["tables"]["Software"]])

    def test_xmp_entity_bomb_refused(self):
        out = md.parse_xmp('<!DOCTYPE x [<!ENTITY a "aaaa">]><x:xmpmeta/>')
        self.assertIn("DTD", out["error"])


class TestC2PA(unittest.TestCase):
    def test_absent(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.jpg"
            Image.fromarray(_photo()).save(p, quality=90)
            c = md.read_c2pa(str(p))
        self.assertFalse(c["present"])
        self.assertEqual(c["errors"], [])

    def test_sample_manifest(self):
        c = md.read_c2pa(str(SAMPLE))
        self.assertTrue(c["present"])
        self.assertEqual(c["claim_generator"], "29a.ch/photo-forensics/")
        self.assertEqual(c["signer"], "C2PA Signer")
        self.assertTrue(c["ai_generated"])
        self.assertIn("c2pa.edited", [a["action"] for a in c["actions"]])
        self.assertFalse(c["valid"])
        r = md.analyze_metadata(str(SAMPLE))
        self.assertIn("C2PA", r["tables"])
        self.assertEqual(levels(r, "AI-generated content"), ["warning"])

    def test_tampered_manifest_hash_mismatch(self):
        b = bytearray(SAMPLE.read_bytes())
        b[-5000] ^= 0xFF  # inside the entropy-coded image data
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "t.jpg"
            p.write_bytes(bytes(b))
            r = md.analyze_metadata(str(p))
        self.assertEqual(levels(r, "C2PA hash mismatch"), ["warning"])


class TestThumbnailBenchmark(unittest.TestCase):
    """Seeded subset of the calibration documented at THUMB_* in the module."""

    def test_tpr_fpr(self):
        from skimage import data
        rng = np.random.default_rng(1)
        srcs = [data.astronaut(), data.coffee(), data.chelsea(), data.rocket()]
        filters = [Image.NEAREST, Image.BILINEAR, Image.BICUBIC, Image.LANCZOS, Image.BOX]
        fp = tp = n = 0
        for f in filters:
            for i, a in enumerate(srcs):
                H, W = a.shape[:2]
                tb = _jpeg_bytes(np.asarray(Image.fromarray(a).resize(
                    (160, round(H * 160 / W)), f)), int(rng.integers(50, 96)))
                with Image.open(io.BytesIO(_jpeg_bytes(a, int(rng.integers(20, 101))))) as m:
                    fp += md.compare_thumbnail(m, tb)["content_mismatch"]
                e = a.copy()
                s = int(np.sqrt(0.05 * H * W))
                y, x = rng.integers(0, H - s), rng.integers(0, W - s)
                o = srcs[(i + 1) % len(srcs)]  # splice from another photo
                oy, ox = rng.integers(0, o.shape[0] - s), rng.integers(0, o.shape[1] - s)
                e[y:y + s, x:x + s] = o[oy:oy + s, ox:ox + s]
                with Image.open(io.BytesIO(_jpeg_bytes(e, int(rng.integers(50, 101))))) as m:
                    tp += md.compare_thumbnail(m, tb)["content_mismatch"]
                n += 1
        self.assertLessEqual(fp / n, 0.05)
        self.assertGreaterEqual(tp / n, 0.90)


if __name__ == "__main__":
    unittest.main()
