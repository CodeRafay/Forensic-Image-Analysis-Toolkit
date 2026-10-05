"""
Error Level Analysis (ELA).

N. Krawetz, "A Picture's Worth: Digital Image Analysis and Forensics",
Black Hat 2007. The image is re-saved once as JPEG at a chosen quality and
the per-pixel absolute difference to the stored pixels is measured. Regions
whose last compression history differs from the rest (e.g. a patch pasted
from a less compressed source) change more on resave than regions that have
already converged at that quality.

One definition is used everywhere: error = max over RGB channels of
|original - recompressed|, averaged over a WIN x WIN window. Raw error grows
with local detail (edges and texture always change more on resave), so it is
content-normalised: windows are binned by their local high-pass energy (mean
|Laplacian| of luma over the same window) and each window's error is divided
by the median error of its texture bin. A ratio of 1 means "as much error as
other parts of this image with the same amount of detail". Every metric, the
mask and the overlay come from that ratio (never from a display copy).
"""
import io

import numpy as np
from PIL import Image
from scipy import ndimage

from analysis.util import (error_result, image_format, load_array,
                           make_result, overlay_mask, to_uint8)

WIN = 16          # smoothing window (px): ~2x2 JPEG blocks
ERR_FLOOR = 1.0   # grey levels; bin medians below this are treated as 1.0
N_BINS = 16       # texture-energy quantile bins
# A connected region whose content-normalised error exceeds K_RATIO and covers
# >= MIN_REGION_PCT of the image is reported (notice). Calibrated at q=90 on
# 8 photos through a camera-like pipeline (RGGB mosaic, shot+read noise,
# demosaic, sharpening; PNG/JPEG q70-95) plus the reviewer's 48 skimage files
# (old 4x-median rule: 9/48 false alarms; now 0/48). Hold-out (7 other photos,
# other seeds), 84 negatives: 0 flagged (0 %); same-quality resave (q88/q90,
# 60 files) 1/60. Positives: raw camera patch
# (1/16-1/4 area, other photo) pasted into a q70-90 JPEG, saved PNG/q92/q95:
# 32/63 (51 %; PNG 14/21, q95 13/21, q92 5/21). Mixed-history splices (host
# and donor JPEG history random, final PNG/q75/85/92): 6/56 (11 %); ELA is
# blind when the host was never JPEG-compressed or the final save is q<=85.
K_RATIO = 2.0
MIN_REGION_PCT = 1.0

LIMITATIONS = [
    "Error is compared only between windows with similar local detail; a "
    "region whose detail differs in kind (text, sharp graphics, a sky "
    "gradient next to foliage) can still stand out on an untouched image.",
    "Resaving the whole image (or saving the splice at a low quality) "
    "equalises error levels and hides pasted regions.",
    "A pasted region that shares the background's compression history "
    "(same source quality, grid-aligned) produces no ELA contrast.",
    "Smooth or dark regions have near-zero error regardless of history, so "
    "absence of high-error regions is not evidence of an unedited image.",
    "On PNG or other lossless files ELA shows how the image reacts to its "
    "first JPEG compression, not a compression history.",
]


def ela_error(rgb, quality):
    """Raw per-pixel ELA error: max_c |rgb - JPEG_q(rgb)|, uint8 array HxW."""
    u8 = np.asarray(rgb, np.uint8)
    buf = io.BytesIO()
    Image.fromarray(u8).save(buf, "JPEG", quality=int(quality))
    with Image.open(io.BytesIO(buf.getvalue())) as im:
        rec = np.asarray(im.convert("RGB"))
    # int16 difference, uint8 channel max: ~10x less memory than float64
    return np.abs(u8.astype(np.int16) - rec).max(axis=2).astype(np.uint8)


def ela_ratio(err, gray):
    """Content-normalised error: WIN-smoothed error divided by the median
    smoothed error of windows with the same local high-pass energy (one of
    N_BINS quantile bins of WIN-smoothed |Laplacian| of luma).
    Returns (smoothed error, ratio, median smoothed error)."""
    sm = ndimage.uniform_filter(err.astype(np.float32), WIN, mode="reflect")
    tex = ndimage.uniform_filter(np.abs(ndimage.laplace(gray)), WIN, mode="reflect")
    # ponytail: bin edges/medians from a 4-px subsample, plenty for 16 bins
    ts, ss = tex[::4, ::4].ravel(), sm[::4, ::4].ravel()
    edges = np.unique(np.quantile(ts, np.linspace(0, 1, N_BINS + 1)[1:-1]))
    idx = np.searchsorted(edges, ts)
    med = np.array([np.median(ss[idx == i]) if (idx == i).any() else 0.0
                    for i in range(edges.size + 1)], np.float32)
    expect = np.maximum(med, ERR_FLOOR)[np.searchsorted(edges, tex)]
    return sm, sm / expect, float(np.median(ss))


def _display(arr, max_side=1200):
    a = np.asarray(arr, np.uint8)
    h, w = a.shape[:2]
    s = max(h, w) / max_side
    if s <= 1:
        return a
    return np.asarray(Image.fromarray(a).resize(
        (max(1, round(w / s)), max(1, round(h / s))), Image.Resampling.BOX))


def _load_u8(image_path):
    """uint8 RGB straight from the decoder (16-bit via load_array)."""
    with Image.open(image_path) as im:
        if im.mode in ("I;16", "I;16B", "I;16L", "I"):
            return load_array(image_path, "RGB")[0].astype(np.uint8)
        return np.asarray(im.convert("RGB"))


def analyze_ela(image_path, quality=90):
    """
    ELA at one resave quality, content-normalised.

    Returns the util result contract with images
    {ELA error, high-ratio overlay}, metrics (mean / 95th-percentile error,
    median error, % area above K x expected error, max ratio) and
    details (raw values for tests).
    """
    try:
        rgb = _load_u8(image_path)
        h, w = rgb.shape[:2]
        if min(h, w) < 2 * WIN or rgb[::4, ::4].std() < 1.0:
            return make_result(
                "insufficient_data",
                f"Image is {w}x{h} px or has no texture; ELA needs at least "
                f"{2 * WIN}x{2 * WIN} px of varying content.",
                limitations=LIMITATIONS)

        err = ela_error(rgb, quality)
        gray = np.asarray(Image.fromarray(rgb).convert("L"), np.float32)
        sm, ratio, med = ela_ratio(err, gray)
        del gray, sm
        mask = ratio > K_RATIO
        lab, n = ndimage.label(mask)
        sizes = np.bincount(lab.ravel())[1:] if n else np.zeros(0)
        big = np.flatnonzero(sizes >= MIN_REGION_PCT / 100 * h * w)
        area_pct = float(mask.mean() * 100)
        region_pct = float(sizes[big].sum() / (h * w) * 100) if big.size else 0.0
        del lab
        max_ratio = float(ratio.max())
        p95 = float(np.percentile(err[::2, ::2], 95))

        q, k = int(quality), K_RATIO
        metrics = {
            f"Mean error at q{q} (grey levels)": round(float(err.mean()), 2),
            f"95th pct error at q{q} (grey levels)": round(p95, 2),
            "Median smoothed error (grey levels)": round(med, 2),
            f"Area above {k:g}x expected error (%)": round(area_pct, 2),
            "Max error / expected for its texture": round(max_ratio, 2),
        }
        findings = []
        fmt = image_format(image_path)
        if fmt != "JPEG":
            findings.append(("info", f"File is {fmt}, not JPEG: the error map "
                             "shows the first JPEG compression, not a history."))
        if big.size:
            findings.append((
                "notice",
                f"{big.size} region(s) covering {region_pct:.1f}% of the image "
                f"change more than {k:g}x as much on resave as other parts of "
                f"the image with the same amount of detail (max {max_ratio:.1f}x). "
                "Consistent with a different compression history; check the "
                "region visually before concluding."))
        else:
            findings.append((
                "info",
                f"Tested for regions with error above {k:g}x the error expected "
                f"for their texture covering >= {MIN_REGION_PCT:g}% of the "
                f"image at q{q}: no inconsistency found at this sensitivity."))

        images = {
            f"ELA error at q{q} (contrast-stretched for display)":
                to_uint8(_display(err)),
            f"Regions above {k:g}x expected error (red)":
                overlay_mask(_display(rgb), _display(mask.astype(np.uint8) * 255) / 255.0),
        }
        return make_result(
            "ok",
            f"Re-saved at JPEG q{q} and measured the per-pixel change "
            f"(median {med:.2f}, 95th pct {p95:.1f} grey levels), normalised "
            "by local detail.",
            findings, metrics, images, limitations=LIMITATIONS,
            details={"quality": q, "median_error": med,
                     "mean_error": float(err.mean()),
                     "area_above_k_pct": area_pct,
                     "region_pct": region_pct, "n_regions": int(big.size),
                     "max_ratio": max_ratio, "k": K_RATIO})
    except Exception as e:  # noqa: BLE001
        return error_result(e, LIMITATIONS)
