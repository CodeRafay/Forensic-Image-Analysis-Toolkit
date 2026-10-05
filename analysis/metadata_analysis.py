"""
Metadata consistency checks and C2PA Content Credentials.

What is read (never re-encoded, all files closed):
  * true EXIF — IFD0, Exif IFD (0x8769), GPS IFD (0x8825), Interop and IFD1
    via Pillow ``getexif()`` / ``get_ifd()`` (CIPA DC-008 "Exif 2.32").
    Pillow's ``info`` fields (jfif, dpi, ...) are NOT EXIF and are not
    counted as such.
  * XMP packet — xmp:CreatorTool, xmpMM:History (stEvt:*),
    xmpMM:DerivedFrom, photoshop:DocumentAncestors, Iptc4xmpExt:
    DigitalSourceType (Adobe XMP Specification Part 1-2, IPTC Photo Metadata
    2023.1).
  * PNG tEXt/iTXt/zTXt/eXIf chunks.
  * C2PA manifest store via c2pa-python (C2PA Technical Specification 2.x),
    offline: remote manifests and OCSP are not fetched.

Checks follow the metadata-forensics practice summarised in Kee, Johnson &
Farid, "Digital image authentication from JPEG headers", IEEE TIFS 2011 and
Gloe, "Forensic analysis of ordered data structures on the example of JPEG
files", WIFS 2012: metadata can reveal the software that last wrote a file
and internal contradictions, but it is trivially edited or stripped, so it
can raise questions and never settles them. No score or verdict is produced.
"""
import io
import json
import re
import warnings
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import numpy as np
import piexif
from PIL import ExifTags, Image
from scipy.ndimage import gaussian_filter

from analysis.util import error_result, make_result

LIMITATIONS = [
    "Metadata is easy to edit, copy from another file or strip; a consistent "
    "record says nothing about the pixels, and an inconsistent one can have "
    "an innocent cause (wrong camera clock, batch tools, messaging apps).",
    "Absence of EXIF, XMP or a thumbnail is common and is not evidence "
    "either way.",
    "The thumbnail check only sees changes large enough to survive "
    "downscaling to the thumbnail size (roughly ≥ 2 % of the frame), and "
    "only when the editor left the old thumbnail in place.",
    "C2PA validation is offline: no trust list is configured, so a signer "
    "is reported as untrusted unless the manifest itself fails; remote "
    "manifests and certificate revocation (OCSP) are not checked.",
]

# Substrings (lower-case) of Software / CreatorTool values. Raw developers
# are checked first because "Adobe Photoshop Lightroom" / "Photoshop Camera
# Raw" contain "photoshop".
RAW_DEVELOPERS = ["lightroom", "camera raw", "darktable", "rawtherapee",
                  "capture one", "dxo", "on1 photo raw", "silkypix"]
EDITORS = ["photoshop", "gimp", "affinity", "pixelmator", "snapseed",
           "picsart", "paint.net", "pixlr", "canva", "luminar", "facetune",
           "photopea", "fotor", "vsco", "acdsee", "corel", "paintshop",
           "krita", "inkscape", "photoscape", "meitu", "airbrush", "lensa"]
# Makers whose cameras/phones write a MakerNote in normal operation.
MAKERNOTE_MAKES = ["canon", "nikon", "sony", "fujifilm", "olympus",
                   "om digital", "panasonic", "pentax", "ricoh", "leica",
                   "apple"]
# PNG text keys written by image-generation front ends.
AI_TEXT_KEYS = ["parameters", "prompt", "workflow", "dream",
                "sd-metadata", "invokeai_metadata", "negative_prompt"]

# Thumbnail vs main image. After a gain/offset fit, the worst 8x8
# thumbnail block's mean abs residual divided by the median block residual.
# Calibrated on 8 photos (sampleImg + 7 skimage) x 40 seeded trials:
# 320 genuine 160-px thumbnails (nearest/bilinear/bicubic/lanczos/box,
# thumb q50-95, main re-saved q20-100): max ratio 6.2, min corr 0.987
# → FPR 0/320 at these thresholds. Stale thumbnail after pasting a patch of
# 2/5/10/20 % of the frame (main q50-100): TPR 98.1/99.4/98.8/99.1 %.
# Correlation alone (the previous check) caught only 7-78 % of those, and
# missed the real stale thumbnail in assets/sample images (corr 0.953,
# ratio 11.4). tests/test_metadata.py re-measures a subset.
THUMB_SIGMA = 1.0          # px blur on both before comparing (kills aliasing)
THUMB_MAX_BLOCK_RATIO = 9.0
THUMB_MIN_CORR = 0.90
TAG_TEXT_MAX = 200

_NS = {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "xmp": "http://ns.adobe.com/xap/1.0/",
    "xmpMM": "http://ns.adobe.com/xap/1.0/mm/",
    "stEvt": "http://ns.adobe.com/xap/1.0/sType/ResourceEvent#",
    "stRef": "http://ns.adobe.com/xap/1.0/sType/ResourceRef#",
    "photoshop": "http://ns.adobe.com/photoshop/1.0/",
    "Iptc4xmpExt": "http://iptc.org/std/Iptc4xmpExt/2008-02-29/",
}


# ── Value helpers ─────────────────────────────────────────────────
def _text(v):
    """Stringify an EXIF value for display; bytes and long text truncated."""
    if isinstance(v, bytes):
        s = v.rstrip(b"\x00")
        if len(s) <= 64 and all(32 <= c < 127 for c in s):
            return s.decode("ascii")
        return f"<{len(v)} bytes>"
    if isinstance(v, tuple):
        return ", ".join(_text(x) for x in v)
    if isinstance(v, float) or type(v).__name__ == "IFDRational":
        f = float(v)
        return f"{f:g}" if np.isfinite(f) else "undefined"
    s = str(v).strip("\x00 ")
    return s if len(s) <= TAG_TEXT_MAX else s[:TAG_TEXT_MAX] + "…"


def _clean(v):
    """EXIF string value or None when blank."""
    if isinstance(v, bytes):
        v = v.decode("latin-1", "ignore")
    if not isinstance(v, str):
        return None
    v = v.strip("\x00 ")
    return v or None


# ── EXIF ──────────────────────────────────────────────────────────
_IFDS = [("Exif", ExifTags.IFD.Exif), ("GPS", ExifTags.IFD.GPSInfo),
         ("Interop", ExifTags.IFD.Interop), ("IFD1", ExifTags.IFD.IFD1)]


def read_exif(img):
    """
    True EXIF of an open Pillow image as {ifd_name: {tag_name: raw_value}}.
    Empty IFDs are omitted. Pillow ``info`` keys are not included.
    """
    exif = img.getexif()
    out = {}
    ifd0 = {ExifTags.TAGS.get(k, hex(k)): v for k, v in exif.items()
            if k not in (ExifTags.IFD.Exif, ExifTags.IFD.GPSInfo)}
    if ifd0:
        out["IFD0"] = ifd0
    for name, ifd in _IFDS:
        try:
            # Pillow warns on a missing next-IFD pointer (piexif and some
            # cameras write none) but still returns the tags.
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                tags = exif.get_ifd(ifd)
        except Exception:  # noqa: BLE001 — corrupt pointer: skip that IFD
            continue
        names = ExifTags.GPSTAGS if name == "GPS" else ExifTags.TAGS
        tags = {names.get(k, hex(k)): v for k, v in tags.items()
                if k != ExifTags.IFD.Interop}
        if tags:
            out[name] = tags
    return out


def gps_coordinates(gps):
    """(lat, lon) in decimal degrees, or None unless BOTH are present."""
    try:
        lat, lon = gps["GPSLatitude"], gps["GPSLongitude"]
        to_deg = lambda v: float(v[0]) + float(v[1]) / 60 + float(v[2]) / 3600
        lat, lon = to_deg(lat), to_deg(lon)
    except (KeyError, TypeError, ValueError, IndexError, ZeroDivisionError):
        return None
    if not (np.isfinite(lat) and np.isfinite(lon)):
        return None
    if _clean(gps.get("GPSLatitudeRef")) == "S":
        lat = -lat
    if _clean(gps.get("GPSLongitudeRef")) == "W":
        lon = -lon
    return round(lat, 6), round(lon, 6)


# ── Dates ─────────────────────────────────────────────────────────
_DATE_TAGS = [  # (label, datetime tag, offset tag, subsec tag, IFD)
    ("DateTime (modified)", "DateTime", "OffsetTime", "SubsecTime", "IFD0"),
    ("DateTimeOriginal (capture)", "DateTimeOriginal", "OffsetTimeOriginal",
     "SubsecTimeOriginal", "Exif"),
    ("DateTimeDigitized", "DateTimeDigitized", "OffsetTimeDigitized",
     "SubsecTimeDigitized", "Exif"),
]
_OFFSET_RE = re.compile(r"^([+-])(\d\d):(\d\d)$")
EARLIEST_PLAUSIBLE = datetime(1839, 1, 1)  # first practical photographs


def parse_exif_date(value, offset=None, subsec=None):
    """
    Returns (datetime | None, problem | None). A blank or all-zero value is
    'not set' (None, None); anything else that does not parse, or lies
    before 1839 or after tomorrow, is reported as a problem.
    """
    s = _clean(value)
    if not s or set(s) <= set("0: -"):
        return None, None
    try:
        dt = datetime.strptime(s[:19], "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None, f"'{s}' is not a valid date/time"
    sub = _clean(subsec)
    if sub and sub.isdigit():
        dt += timedelta(seconds=float("0." + sub))
    m = _OFFSET_RE.match(_clean(offset) or "")
    if m:
        sign = 1 if m.group(1) == "+" else -1
        dt = dt.replace(tzinfo=timezone(sign * timedelta(
            hours=int(m.group(2)), minutes=int(m.group(3)))))
    naive = dt.replace(tzinfo=None)
    if naive < EARLIEST_PLAUSIBLE:
        return dt, f"{s} is before photography existed"
    if naive > datetime.now() + timedelta(days=1):
        return dt, f"{s} is in the future"
    return dt, None


def _diff_seconds(a, b):
    """a - b in seconds; offsets used only when both carry one."""
    if (a.tzinfo is None) != (b.tzinfo is None):
        a, b = a.replace(tzinfo=None), b.replace(tzinfo=None)
    return (a - b).total_seconds()


def check_dates(exif):
    """Returns (findings, table rows)."""
    findings, rows, parsed = [], [], {}
    for label, tag, off_tag, sub_tag, ifd in _DATE_TAGS:
        src = exif.get(ifd, {})
        if tag == "DateTime":  # offsets / subsec for DateTime live in Exif IFD
            extra = exif.get("Exif", {})
        else:
            extra = src
        raw = src.get(tag)
        if raw is None:
            continue
        dt, problem = parse_exif_date(raw, extra.get(off_tag), extra.get(sub_tag))
        rows.append({"tag": label, "value": _text(raw),
                     "offset": _text(extra.get(off_tag, "")),
                     "subsec": _text(extra.get(sub_tag, ""))})
        if problem:
            findings.append(("warning", f"Impossible {tag}: {problem}."))
        elif dt is not None:
            parsed[tag] = dt

    orig, digi, mod = (parsed.get(k) for k in
                       ("DateTimeOriginal", "DateTimeDigitized", "DateTime"))
    if orig and digi and _diff_seconds(digi, orig) < -1:
        findings.append(("warning", "DateTimeDigitized is earlier than "
                         "DateTimeOriginal — an image cannot be digitised "
                         "before it was captured."))
    if orig and mod:
        d = _diff_seconds(mod, orig)
        if d < -1:
            findings.append(("warning", f"DateTime (last modified) is "
                             f"{_human(-d)} earlier than DateTimeOriginal — "
                             "the file claims to have been saved before it "
                             "was captured."))
        elif d > 2:
            findings.append(("notice", f"DateTime (last modified) is "
                             f"{_human(d)} later than DateTimeOriginal — the "
                             "file was written again after capture (editing, "
                             "raw development or re-export)."))
    return findings, rows


def _human(sec):
    for unit, n in (("days", 86400), ("hours", 3600), ("minutes", 60)):
        if sec >= n:
            return f"{sec / n:.1f} {unit}"
    return f"{sec:.0f} s"


# ── XMP ───────────────────────────────────────────────────────────
def xmp_packet(img):
    """The raw XMP packet as str, or None."""
    for key in ("xmp", "XML:com.adobe.xmp"):
        v = img.info.get(key)
        if v:
            return v.decode("utf-8", "ignore") if isinstance(v, bytes) else v
    tiff_xmp = getattr(img, "tag_v2", {}).get(700) if img.format == "TIFF" else None
    if tiff_xmp:
        return tiff_xmp.decode("utf-8", "ignore") \
            if isinstance(tiff_xmp, bytes) else str(tiff_xmp)
    return None


def parse_xmp(packet):
    """
    Pull the provenance fields out of an XMP packet.
    Returns dict: creator_tool, history [ {action, softwareAgent, when,
    changed} ], derived_from, ancestors (count), digital_source_type,
    error.
    """
    out = {"creator_tool": None, "history": [], "derived_from": None,
           "ancestors": 0, "digital_source_type": None, "error": None}
    # Entities are never needed in XMP; refusing them blocks entity bombs.
    if "<!DOCTYPE" in packet or "<!ENTITY" in packet:
        out["error"] = "XMP packet contains a DTD; not parsed"
        return out
    start, end = packet.find("<x:xmpmeta"), packet.rfind("</x:xmpmeta>")
    body = packet[start:end + 12] if start >= 0 and end > start else packet
    if start < 0:
        start = body.find("<rdf:RDF")
        body = body[start:body.rfind("</rdf:RDF>") + 10] if start >= 0 else body
    try:
        root = ET.fromstring(body)
    except ET.ParseError as e:
        out["error"] = f"XMP packet is not well-formed XML: {e}"
        return out

    q = lambda p, n: f"{{{_NS[p]}}}{n}"

    def value(desc, prefix, name):
        """Simple property as attribute or child element text."""
        if q(prefix, name) in desc.attrib:
            return desc.attrib[q(prefix, name)]
        el = desc.find(f"{prefix}:{name}", _NS)
        if el is None:
            return None
        if el.text and el.text.strip():
            return el.text.strip()
        li = el.find(".//rdf:li", _NS)
        return li.text.strip() if li is not None and li.text else None

    for desc in root.iter(q("rdf", "Description")):
        out["creator_tool"] = out["creator_tool"] or value(desc, "xmp", "CreatorTool")
        out["digital_source_type"] = (out["digital_source_type"]
                                      or value(desc, "Iptc4xmpExt", "DigitalSourceType"))
        df = desc.find("xmpMM:DerivedFrom", _NS)
        if q("xmpMM", "DerivedFrom") in desc.attrib:
            out["derived_from"] = desc.attrib[q("xmpMM", "DerivedFrom")]
        elif df is not None:
            out["derived_from"] = (df.get(q("stRef", "documentID"))
                                   or df.get(q("stRef", "filePath"))
                                   or df.findtext(".//stRef:documentID", None, _NS)
                                   or "present")
        anc = desc.find("photoshop:DocumentAncestors", _NS)
        if anc is not None:
            out["ancestors"] += len(anc.findall(".//rdf:li", _NS))
        hist = desc.find("xmpMM:History", _NS)
        if hist is not None:
            for li in hist.findall(".//rdf:li", _NS):
                ev = {}
                for f in ("action", "softwareAgent", "when", "changed"):
                    v = li.get(q("stEvt", f)) or li.findtext(f"stEvt:{f}", None, _NS)
                    if v:
                        ev[f] = v.strip()
                if ev:
                    out["history"].append(ev)
    return out


# ── Software ──────────────────────────────────────────────────────
def classify_software(value):
    """'raw developer' | 'editor' | None for a Software / CreatorTool value."""
    v = str(value).lower()
    if any(k in v for k in RAW_DEVELOPERS):
        return "raw developer"
    if any(k in v for k in EDITORS):
        return "editor"
    return None


# ── Thumbnail ─────────────────────────────────────────────────────
def compare_thumbnail(img, thumb_bytes):
    """
    Compare the embedded EXIF thumbnail with the main image downscaled to
    the same size. Both are blurred (THUMB_SIGMA) to suppress resampling
    aliasing and fitted with one gain/offset (tone differences between the
    camera's thumbnail and main pipelines are global). An edit made after
    the thumbnail was written leaves a local residual.

    Returns dict with thumbnail_size, aspect_mismatch, correlation,
    block_ratio (worst 8x8 block residual / median block residual),
    content_mismatch, residual (float HxW for display), thumb / main_small
    (uint8 arrays for display). None if the thumbnail cannot be decoded.
    """
    try:
        with Image.open(io.BytesIO(thumb_bytes)) as t:
            thumb = t.convert("RGB")
    except Exception:  # noqa: BLE001
        return None
    tw, th = thumb.size
    w, h = img.size
    out = {"thumbnail_size": [tw, th],
           "aspect_mismatch": abs(w / h - tw / th) > 0.05 * (w / h)}
    main_small = img.convert("RGB").resize(thumb.size, Image.LANCZOS)
    a = gaussian_filter(np.asarray(thumb, float), (THUMB_SIGMA, THUMB_SIGMA, 0))
    b = gaussian_filter(np.asarray(main_small, float), (THUMB_SIGMA, THUMB_SIGMA, 0))
    if a.std() < 1e-6 or b.std() < 1e-6:
        corr = 1.0 if abs(a.mean() - b.mean()) < 2 else 0.0
        resid = np.abs(a - b).mean(2)
    else:
        corr = float(np.corrcoef(a.ravel(), b.ravel())[0, 1])
        g, o = np.polyfit(b.ravel(), a.ravel(), 1)
        resid = np.abs(a - (g * b + o)).mean(2)
    bs = 8
    if min(th, tw) >= 2 * bs:
        blocks = resid[:th // bs * bs, :tw // bs * bs] \
            .reshape(th // bs, bs, tw // bs, bs).mean((1, 3))
        ratio = float(blocks.max() / max(np.median(blocks), 1.0))
    else:
        ratio = 1.0
    out.update(correlation=round(corr, 4), block_ratio=round(ratio, 2),
               content_mismatch=bool(not out["aspect_mismatch"] and (
                   corr < THUMB_MIN_CORR or ratio > THUMB_MAX_BLOCK_RATIO)),
               residual=resid, thumb=np.asarray(thumb),
               main_small=np.asarray(main_small))
    return out


def _thumbnail_bytes(img):
    raw = img.info.get("exif")
    if not raw:
        return None
    try:
        return piexif.load(raw).get("thumbnail") or None
    except Exception:  # noqa: BLE001 — malformed EXIF: no thumbnail
        return None


def _thumbnail_figure(cmp):
    """thumbnail | main downscaled | residual, upscaled for visibility."""
    t, m = cmp["thumb"], cmp["main_small"]
    r = cmp["residual"]
    r = np.clip(r * (255.0 / max(np.percentile(r, 99.5), 1.0)), 0, 255).astype(np.uint8)
    strip = np.hstack([t, m, np.stack([r] * 3, -1)])
    k = max(1, min(4, 1200 // strip.shape[1]))
    return np.repeat(np.repeat(strip, k, 0), k, 1)


# ── C2PA ──────────────────────────────────────────────────────────
def read_c2pa(path):
    """
    Read C2PA Content Credentials offline.

    Returns a plain dict:
      present (bool), validation_state ("Valid" | "Invalid" | "Trusted" |
      None), valid (bool: state is Valid or Trusted), claim_generator,
      title, signer, issuer, signing_time, actions [ {action, softwareAgent,
      digitalSourceType, when} ], ai_generated (bool), ai_indicators [str],
      ingredients (int), manifests (int), failures [ {code, explanation} ],
      errors [str].
    """
    out = {"present": False, "validation_state": None, "valid": False,
           "claim_generator": None, "title": None, "signer": None,
           "issuer": None, "signing_time": None, "actions": [],
           "ai_generated": False, "ai_indicators": [], "ingredients": 0,
           "manifests": 0, "failures": [], "errors": []}
    try:
        import c2pa
        settings = c2pa.Settings.from_dict(
            {"verify": {"remote_manifest_fetch": False, "ocsp_fetch": False}})
        reader = c2pa.Reader.try_create(str(path), context=c2pa.Context(settings))
        if reader is None:
            return out
        try:
            store = json.loads(reader.json())
        finally:
            reader.close()
    except Exception as e:  # noqa: BLE001 — unsupported format, corrupt JUMBF
        msg = str(e)
        if "ManifestNotFound" not in msg and "JumbfNotFound" not in msg:
            out["errors"].append(msg[:300])
        return out

    manifests = store.get("manifests") or {}
    active = manifests.get(store.get("active_manifest")) or {}
    out.update(present=True, manifests=len(manifests))
    state = store.get("validation_state")
    out["validation_state"] = state
    out["valid"] = state in ("Valid", "Trusted")
    gen = active.get("claim_generator")
    if not gen and active.get("claim_generator_info"):
        gen = ", ".join(str(g.get("name", "")) for g in active["claim_generator_info"])
    out["claim_generator"] = gen
    out["title"] = active.get("title")
    sig = active.get("signature_info") or {}
    out["signer"] = sig.get("common_name") or sig.get("issuer")
    out["issuer"] = sig.get("issuer")
    out["signing_time"] = sig.get("time")
    out["ingredients"] = len(active.get("ingredients") or [])

    for a in active.get("assertions") or []:
        if not str(a.get("label", "")).startswith("c2pa.actions"):
            continue
        for act in (a.get("data") or {}).get("actions") or []:
            agent = act.get("softwareAgent")
            if isinstance(agent, dict):
                agent = agent.get("name")
            out["actions"].append({
                "action": act.get("action"), "softwareAgent": agent,
                "digitalSourceType": act.get("digitalSourceType"),
                "when": act.get("when")})
    for act in out["actions"]:
        dst = str(act.get("digitalSourceType") or "")
        if "trainedalgorithmicmedia" in dst.lower():
            out["ai_indicators"].append(
                f"{act['action']}: digitalSourceType {dst.rsplit('/', 1)[-1]}")
    out["ai_generated"] = bool(out["ai_indicators"])

    res = (store.get("validation_results") or {}).get("activeManifest") or {}
    fails = res.get("failure")
    if fails is None:  # older stores only carry validation_status
        fails = store.get("validation_status") or []
    out["failures"] = [{"code": f.get("code"), "explanation": f.get("explanation")}
                       for f in fails]
    return out


def _c2pa_findings(c):
    if c["errors"]:
        return [("info", "C2PA manifest could not be read: " + c["errors"][0])]
    if not c["present"]:
        return [("info", "No C2PA Content Credentials embedded (most images "
                 "have none; absence is not evidence either way).")]
    f = []
    who = f"signed by '{c['signer']}'" if c["signer"] else "signer unknown"
    f.append(("info", f"C2PA Content Credentials present: claim generator "
              f"'{c['claim_generator']}', {who}"
              + (f" at {c['signing_time']}" if c["signing_time"] else "") + "."))
    codes = [x["code"] for x in c["failures"] if x.get("code")]
    # No trust list is configured, so "untrusted" is expected, not a defect.
    real = [k for k in codes if k != "signingCredential.untrusted"]
    integrity = [k for k in real if "mismatch" in k.lower()]
    if integrity:
        f.append(("warning", "C2PA hash mismatch (" + ", ".join(integrity)
                  + "): the file was changed after the Content Credential "
                  "was signed."))
    if c["validation_state"] == "Trusted":
        f.append(("info", "C2PA signature and hashes validated against the "
                  "trust list."))
    elif real or c["validation_state"] not in ("Valid", "Invalid"):
        f.append(("warning", f"C2PA manifest failed validation "
                  f"(state {c['validation_state']}): "
                  + ", ".join(real or ["no failure code given"]) + "."))
    else:
        f.append(("info", "C2PA signature and hashes are intact; the signer "
                  "is not on a configured trust list, so its identity is "
                  "unconfirmed."))
    for ind in c["ai_indicators"]:
        f.append(("warning", "C2PA declares AI-generated content — " + ind + "."))
    return f


# ── Entry point ───────────────────────────────────────────────────
def analyze_metadata(image_path):
    """
    Read EXIF / XMP / PNG text / C2PA and report internal inconsistencies.

    Returns the util.make_result contract. Tables: Camera, Software,
    Timestamps, GPS, XMP history, PNG text chunks, Full EXIF, C2PA,
    C2PA actions (only those with content). Image: thumbnail vs main image
    (when an EXIF thumbnail exists).
    """
    try:
        with Image.open(image_path) as img:
            fmt = img.format or "unknown"
            w, h = img.size
            exif = read_exif(img)
            xmp_raw = xmp_packet(img)
            text_chunks = dict(getattr(img, "text", {}) or {}) if fmt == "PNG" else {}
            thumb = None
            tb = _thumbnail_bytes(img)
            if tb:
                thumb = compare_thumbnail(img, tb)
        c2 = read_c2pa(image_path)
    except Exception as e:  # noqa: BLE001
        return error_result(e, LIMITATIONS)

    findings, tables, images = [], {}, {}
    ifd0, exif_ifd, gps = (exif.get(k, {}) for k in ("IFD0", "Exif", "GPS"))
    make, model = _clean(ifd0.get("Make")), _clean(ifd0.get("Model"))
    n_tags = sum(len(v) for v in exif.values())
    xmp = parse_xmp(xmp_raw) if xmp_raw else None

    # Presence
    if not n_tags:
        if fmt in ("JPEG", "MPO", "TIFF"):
            findings.append(("notice", "No camera metadata (EXIF) — stripped "
                             "by software or messaging apps, or never "
                             "written; absence is not evidence either way."))
        else:
            findings.append(("info", f"No EXIF — normal for {fmt} files."))
    else:
        findings.append(("info", f"EXIF present: {n_tags} tags."))

    # Camera
    camera = {k: _text(src[k]) for src, keys in (
        (ifd0, ("Make", "Model")),
        (exif_ifd, ("LensMake", "LensModel", "BodySerialNumber",
                    "ExposureTime", "FNumber", "ISOSpeedRatings",
                    "FocalLength"))) for k in keys if k in src}
    if camera:
        tables["Camera"] = camera
    if make or model:
        findings.append(("info", f"Camera: {make or '?'} {model or ''}".strip() + "."))

    # MakerNote
    has_mn = "MakerNote" in exif_ifd
    if make and not has_mn and any(m in make.lower() for m in MAKERNOTE_MAKES):
        findings.append(("notice", f"No MakerNote, although {make} cameras "
                         "normally write one — software that rewrites EXIF "
                         "often drops it."))
    elif has_mn:
        findings.append(("info", "MakerNote present "
                         f"({len(exif_ifd['MakerNote']) if isinstance(exif_ifd['MakerNote'], bytes) else '?'} bytes)."))

    # Software
    sw_rows = []
    for src, val in (("EXIF Software", ifd0.get("Software")),
                     ("EXIF ProcessingSoftware", ifd0.get("ProcessingSoftware")),
                     ("XMP CreatorTool", xmp and xmp["creator_tool"]),
                     ("PNG Software", text_chunks.get("Software"))):
        if _clean(val):
            sw_rows.append({"source": src, "value": _text(val)})
    for ev in (xmp["history"] if xmp else []):
        if ev.get("softwareAgent"):
            sw_rows.append({"source": "XMP History", "value": ev["softwareAgent"]})
    seen = set()
    for row in sw_rows:
        row["class"] = classify_software(row["value"]) or "unrecognised"
        key = (row["class"], row["value"].lower())
        if key in seen:
            continue
        seen.add(key)
        if row["class"] == "editor":
            findings.append(("notice", f"Written by image editor '{row['value']}' "
                             f"({row['source']}): the file was opened and saved "
                             "in an editor; this does not tell what, if "
                             "anything, was changed."))
        elif row["class"] == "raw developer":
            findings.append(("notice", f"Processed with raw developer/editor "
                             f"'{row['value']}' ({row['source']}): normal for "
                             "photographers, not proof of manipulation."))
        else:
            findings.append(("info", f"{row['source']}: '{row['value']}' (not a "
                             "known editor — typically camera or phone firmware)."))
    if sw_rows:
        tables["Software"] = sw_rows

    # Dates
    f_dates, rows = check_dates(exif)
    findings += f_dates
    if rows:
        tables["Timestamps"] = rows

    # Dimensions
    px, py = exif_ifd.get("ExifImageWidth"), exif_ifd.get("ExifImageHeight")
    if isinstance(px, int) and isinstance(py, int) and px and py \
            and (px, py) not in ((w, h), (h, w)):
        findings.append(("notice", f"Image is {w}×{h} px but EXIF "
                         f"PixelX/YDimension says {px}×{py} — resized or "
                         "cropped after the EXIF was written."))

    # Thumbnail
    if thumb:
        images["Embedded thumbnail | main image downscaled | residual"] = \
            _thumbnail_figure(thumb)
        tw, th = thumb["thumbnail_size"]
        if thumb["aspect_mismatch"]:
            findings.append(("notice", f"EXIF thumbnail ({tw}×{th}) has a "
                             f"different aspect ratio from the image ({w}×{h}) "
                             "— cropped after the thumbnail was written, or a "
                             "camera that letterboxes thumbnails."))
        elif thumb["content_mismatch"]:
            findings.append(("warning", "Thumbnail differs from main image — "
                             "image content changed after the thumbnail was "
                             f"written (correlation {thumb['correlation']:.3f}, "
                             f"worst-block residual ×{thumb['block_ratio']:.1f} "
                             "the median). Compare the two in the figure."))
        else:
            findings.append(("info", "EXIF thumbnail matches the main image "
                             f"(correlation {thumb['correlation']:.3f}); no "
                             "inconsistency found at this sensitivity."))

    # GPS
    if gps:
        coords = gps_coordinates(gps)
        g = {k: _text(v) for k, v in gps.items()}
        if coords:
            g["coordinates"] = f"{coords[0]}, {coords[1]}"
            findings.append(("info", f"GPS position recorded: {coords[0]}, "
                             f"{coords[1]}."))
        else:
            findings.append(("info", "GPS block present without a latitude/"
                             "longitude pair (no fix recorded)."))
        tables["GPS"] = g

    # XMP
    if xmp:
        if xmp["error"]:
            findings.append(("info", xmp["error"] + "."))
        if xmp["history"]:
            tables["XMP history"] = xmp["history"]
            acts = sorted({e.get("action", "?") for e in xmp["history"]})
            findings.append(("notice", f"XMP edit history: {len(xmp['history'])} "
                             f"event(s) ({', '.join(acts)})."))
        if xmp["ancestors"]:
            findings.append(("notice", f"photoshop:DocumentAncestors lists "
                             f"{xmp['ancestors']} other document(s) — content "
                             "from other files was placed into this one."))
        if xmp["derived_from"]:
            findings.append(("info", f"xmpMM:DerivedFrom: {xmp['derived_from']}."))
        dst = xmp["digital_source_type"] or ""
        if "trainedalgorithmicmedia" in dst.lower():
            findings.append(("warning", "XMP declares AI-generated content "
                             f"(Iptc4xmpExt:DigitalSourceType "
                             f"{dst.rsplit('/', 1)[-1]})."))

    # PNG text
    if text_chunks:
        tables["PNG text chunks"] = {k: _text(v) for k, v in text_chunks.items()}
        ai = [k for k in text_chunks if k.lower() in AI_TEXT_KEYS]
        if ai:
            findings.append(("warning", "PNG text chunks of the kind written "
                             f"by image-generation tools ({', '.join(ai)}) — "
                             "likely AI-generated output; read the chunk "
                             "text to confirm."))

    # Full EXIF
    if exif:
        tables["Full EXIF"] = [{"ifd": ifd, "tag": k, "value": _text(v)}
                               for ifd, tags in exif.items() for k, v in tags.items()]

    # C2PA
    findings += _c2pa_findings(c2)
    if c2["present"]:
        c2t = dict(c2, failures=[f"{x['code']}: {x['explanation']}" for x in c2["failures"]])
        tables["C2PA"] = {k: ("; ".join(map(str, v)) if isinstance(v, list) else v)
                          for k, v in c2t.items() if k != "actions"}
        if c2["actions"]:
            tables["C2PA actions"] = c2["actions"]

    if not any(lvl != "info" for lvl, _ in findings):
        findings.append(("info", "Checked editor tags, dates, thumbnail, "
                         "maker note, pixel dimensions, XMP history and C2PA: "
                         "no inconsistency found at this sensitivity."))

    metrics = {"Format": fmt, "Width (px)": w, "Height (px)": h,
               "EXIF tags (count)": n_tags,
               "XMP history events (count)": len(xmp["history"]) if xmp else 0,
               "Software entries (count)": len(sw_rows),
               "C2PA manifests (count)": c2["manifests"]}
    if thumb and not thumb["aspect_mismatch"]:
        metrics["Thumbnail correlation"] = float(thumb["correlation"])
        metrics["Thumbnail worst-block residual (× median)"] = float(thumb["block_ratio"])

    details = {
        "format": fmt, "size": [w, h],
        "exif": {ifd: {k: _text(v) for k, v in tags.items()} for ifd, tags in exif.items()},
        "xmp": xmp, "c2pa": c2,
        "thumbnail": None if not thumb else {
            k: thumb[k] for k in ("thumbnail_size", "aspect_mismatch",
                                  "correlation", "block_ratio", "content_mismatch")},
        "png_text": {k: _text(v) for k, v in text_chunks.items()},
    }
    summary = (f"Read EXIF ({n_tags} tags), XMP ({'present' if xmp else 'absent'})"
               + (", PNG text chunks" if fmt == "PNG" else "")
               + f" and C2PA from a {fmt} file and checked them for internal "
               "inconsistencies.")
    return make_result("ok", summary, findings, metrics, images, tables,
                       LIMITATIONS, details)
