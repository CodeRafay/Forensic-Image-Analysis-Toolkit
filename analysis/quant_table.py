"""
JPEG quantization-table analysis.

Reads the DQT tables of the last JPEG encoder, estimates the IJG quality
they correspond to, and says whether they are a scaled copy of the IJG
(libjpeg) reference tables of ITU-T T.81 Annex K. That tells you which
*encoder family* saved the file last; it says nothing about whether the pixels
were edited. (Background: Farid, "Digital Image Ballistics from JPEG
Quantization", Dartmouth TR2006-583; Kornblum, "Using JPEG quantization tables
to identify imagery processed by software", DFRWS 2008.)

estimate_jpeg_quality / is_standard_table are reused by double_jpeg and
jpeg_ghost.
"""
import numpy as np
from PIL import Image

from analysis.util import error_result, make_result

LIMITATIONS = [
    "Tables describe only the last JPEG save. Earlier compressions, edits made "
    "before that save, and lossless edits are invisible here (see Double JPEG "
    "and JPEG Ghost).",
    "IJG tables are used by a huge range of software and by some cameras; "
    "custom tables are used by most camera vendors and by Photoshop. The "
    "encoder hint narrows the family, it does not identify a device.",
    "Quality is the IJG quality that produces these tables (exact for libjpeg "
    "tables; when several qualities give the same table the highest is "
    "reported). For non-IJG "
    "tables it is only a rough equivalent.",
    "No database of camera tables is consulted, so a camera claim in EXIF "
    "cannot be confirmed or refuted from the tables alone.",
]

TABLE_NAMES = {0: "luminance", 1: "chrominance"}


def analyze_quantization_table(image_path):
    """
    Returns the shared result contract (analysis.util.make_result):
        metrics: "Table N estimated quality (IJG)", "Table N IJG-standard"
        tables:  "Table N (<channel>)": 8 rows of {"0".."7": value}
        details: {"quantization_tables": {id: [64 ints]}, "qualities": {id: q},
                  "standard": {id: bool}, "exif": {...}, "encoder_family": str}
    """
    try:
        with Image.open(image_path) as img:
            fmt = img.format
            exif = img.getexif() if fmt == "JPEG" else {}
            exif = {k: str(exif.get(tag)).strip("\x00 ").strip()
                    for k, tag in (("Make", 271), ("Model", 272), ("Software", 305))
                    if exif.get(tag)}
        if fmt != "JPEG":
            return make_result(
                "not_applicable",
                f"{fmt or 'This'} file has no JPEG quantization tables.",
                [("info", "Quantization tables exist only in JPEG files.")],
                limitations=LIMITATIONS)

        qtables = extract_jpeg_quantization_tables(image_path)
        if not qtables:
            return make_result(
                "insufficient_data", "No readable quantization tables found.",
                [("notice", "The JPEG decoder exposed no 64-entry tables "
                            "(unusual; the file may be damaged or non-baseline).")],
                limitations=LIMITATIONS)

        findings, metrics, tables = [], {}, {}
        qualities, standard = {}, {}
        for tid, qt in sorted(qtables.items()):
            arr = np.array(qt)
            q = estimate_jpeg_quality(arr, tid)
            std = is_standard_table(arr, tid)
            qualities[tid], standard[tid] = q, std
            name = TABLE_NAMES.get(tid, "chrominance")
            metrics[f"Table {tid} estimated quality (IJG)"] = q
            metrics[f"Table {tid} IJG-standard"] = "yes" if std else "no"
            tables[f"Table {tid} ({name})"] = [
                {str(c): int(v) for c, v in enumerate(row)}
                for row in arr.reshape(8, 8)]

        all_ones = all(max(t) <= 1 for t in qtables.values())
        if all_ones:
            family = "unclassifiable"
            findings.append((
                "info", "All table entries are 1 (quality ≈ 100): every encoder "
                        "family produces this, so the encoder cannot be classified."))
        elif all(standard.values()):
            family = "IJG"
            findings.append((
                "info", "Tables are scaled IJG/libjpeg reference tables — typical "
                        "of software saves (PIL, OpenCV, GIMP, many web/AI "
                        "pipelines); many cameras use vendor tables instead."))
        else:
            family = "custom"
            odd = [t for t, s in standard.items() if not s]
            findings.append((
                "info", f"Table(s) {odd} are not scaled IJG tables (custom "
                        "tables) — typical of a camera vendor encoder or an "
                        "editor such as Photoshop."))

        lum_q = qualities.get(0, min(qualities.values()))
        findings.append(("info", f"Luminance table corresponds to IJG quality "
                                 f"≈ {lum_q} (exact for libjpeg tables)."))
        if lum_q < 50 and not all_ones:
            findings.append(("info", "Strong compression (quality < 50): fine "
                                     "detail and other pixel-level traces are "
                                     "degraded."))

        if exif:
            desc = ", ".join(f"{k}: {v}" for k, v in exif.items())
            text = f"EXIF {desc}."
            if family == "IJG" and "Make" in exif:
                text += (" A camera Make with IJG tables fits a later software "
                         "re-save, or a camera whose firmware uses IJG tables.")
            elif family == "custom" and "Software" in exif:
                text += (" Custom tables with a Software tag fit that program's "
                         "own encoder or an untouched camera file.")
            findings.append(("info", text + " (EXIF is editable; context only.)"))
        else:
            findings.append(("info", "No EXIF Make/Model/Software to compare "
                                     "the tables with."))

        return make_result(
            "ok",
            f"Read {len(qtables)} quantization table(s); estimated luminance "
            f"quality {lum_q}, encoder family: {family}.",
            findings, metrics, tables=tables, limitations=LIMITATIONS,
            details={
                "quantization_tables": {str(t): [int(v) for v in qt]
                                        for t, qt in qtables.items()},
                "qualities": {str(t): int(q) for t, q in qualities.items()},
                "standard": {str(t): bool(s) for t, s in standard.items()},
                "exif": exif,
                "encoder_family": family,
            })
    except Exception as e:  # noqa: BLE001 — contract: never raise
        return error_result(e, LIMITATIONS)


def extract_jpeg_quantization_tables(image_path):
    """
    Extracts quantization tables from a JPEG.

    Uses Pillow's JPEG decoder, which walks the marker structure properly.
    A naive byte-scan for the DQT marker (0xFFDB) cannot be used here: that
    byte pair also occurs inside entropy-coded scan data and inside APP
    segments such as XMP, which yields dozens of tables built from unrelated
    bytes. Pillow returns each table de-zigzagged into raster order, which is
    the order `estimate_jpeg_quality` and `is_standard_table` expect.

    Returns:
        dict: {table_id: [64 values]} (empty if none / not a JPEG)
    """
    try:
        with Image.open(image_path) as img:
            tables = getattr(img, 'quantization', None) or {}
            return {
                int(table_id): list(values)
                for table_id, values in tables.items()
                if len(values) == 64
            }
    except Exception:  # noqa: BLE001
        return {}


# Standard IJG quantization tables for quality 50, in raster order.
# Pillow returns tables de-zigzagged, so these line up element for element.
STANDARD_LUMINANCE = np.array([
    16, 11, 10, 16, 24, 40, 51, 61,
    12, 12, 14, 19, 26, 58, 60, 55,
    14, 13, 16, 24, 40, 57, 69, 56,
    14, 17, 22, 29, 51, 87, 80, 62,
    18, 22, 37, 56, 68, 109, 103, 77,
    24, 35, 55, 64, 81, 104, 113, 92,
    49, 64, 78, 87, 103, 121, 120, 101,
    72, 92, 95, 98, 112, 100, 103, 99
])

STANDARD_CHROMINANCE = np.array([
    17, 18, 24, 47, 99, 99, 99, 99,
    18, 21, 26, 66, 99, 99, 99, 99,
    24, 26, 56, 99, 99, 99, 99, 99,
    47, 66, 99, 99, 99, 99, 99, 99,
    99, 99, 99, 99, 99, 99, 99, 99,
    99, 99, 99, 99, 99, 99, 99, 99,
    99, 99, 99, 99, 99, 99, 99, 99,
    99, 99, 99, 99, 99, 99, 99, 99
])


def _standard_table(table_id):
    """Table 0 is luminance; any other id is chrominance."""
    return STANDARD_LUMINANCE if table_id == 0 else STANDARD_CHROMINANCE


def ijg_table(quality, table_id=0):
    """The table libjpeg builds for `quality` (1-100, baseline: clipped to
    1..255), raster order, int array of 64."""
    q = min(100, max(1, int(quality)))
    scale = 5000 // q if q < 50 else 200 - 2 * q
    return np.clip((_standard_table(table_id) * scale + 50) // 100, 1, 255)


_IJG = {t: [ijg_table(q, t) for q in range(1, 101)] for t in (0, 1)}


def estimate_jpeg_quality(qtable, table_id=0):
    """
    Estimates JPEG quality from a quantization table.

    An exact match with a libjpeg table for q = 1..100 returns that q (the
    highest q when several produce the same table). Otherwise it inverts
    the IJG scaling that libjpeg applies when building a table:

        scale = 5000/quality        if quality < 50
        scale = 200 - 2*quality     otherwise
        Q[i]  = clip((T50[i]*scale + 50) / 100, 1, 255)

    so scale is recovered per entry as (100*Q[i] - 50) / T50[i] and inverted
    back to a quality. Entries clipped at 1 or 255 carry no scale information
    and are excluded.

    Args:
        qtable: 64-element quantization table (raster order)
        table_id (int): 0 for luminance, otherwise chrominance

    Returns:
        int: Estimated quality (1-100)
    """
    q = np.asarray(qtable, dtype=np.float64).ravel()
    if q.size != 64:
        return 50  # default
    exact = [i + 1 for i, t in enumerate(_IJG[0 if table_id == 0 else 1])
             if np.array_equal(t, q)]
    if exact:
        return exact[-1]

    standard = _standard_table(table_id).astype(np.float64)

    # Saturated entries pin to the clip bounds and would bias the estimate
    usable = (q > 1) & (q < 255)
    if not usable.any():
        # Everything saturated: all 1s means maximum quality, all 255s minimum
        return 100 if q.max() <= 1 else 1

    scales = (100.0 * q[usable] - 50.0) / standard[usable]
    scale = float(np.median(scales))  # median resists a few odd entries

    if scale <= 0:
        return 100
    quality = 5000.0 / scale if scale > 100 else (200.0 - scale) / 2.0

    return int(round(min(100.0, max(1.0, quality))))


def is_standard_table(qtable, table_id=0, tolerance=0.02):
    """
    Checks whether a table is a scaled version of the standard IJG table.

    An IJG-family encoder (libjpeg, PIL, OpenCV, GIMP) produces T50 scaled by
    a single factor, so every entry divided by its standard counterpart gives
    the same ratio. Encoders with custom tables (many camera vendors,
    Photoshop) break that proportionality. A match says which encoder saved
    the file last, not that the pixels are unedited.

    Args:
        qtable: 64-element quantization table (raster order)
        table_id (int): 0 for luminance, otherwise chrominance
        tolerance (float): Allowed relative spread in the per-entry ratios,
            absorbing the integer rounding libjpeg applies

    Returns:
        bool: True if the table matches the standard family
    """
    q = np.asarray(qtable, dtype=np.float64).ravel()
    if q.size != 64:
        return False

    standard = _standard_table(table_id).astype(np.float64)

    # Clipped entries lost their ratio; judge on the rest
    usable = (q > 1) & (q < 255)
    if usable.sum() < 8:
        return True  # too little information to call it non-standard

    ratios = q[usable] / standard[usable]
    median = np.median(ratios)
    if median <= 0:
        return False

    # Rounding to integers perturbs small quantizer values most, so allow the
    # spread to scale with the rounding step (0.5/standard) as well.
    allowed = tolerance + (0.5 / standard[usable]) / median
    return bool(np.mean(np.abs(ratios - median) / median <= allowed) >= 0.9)
