"""
Shared helpers: the result contract every analysis returns, decoding images
to arrays without re-encoding them, and JPEG grid alignment.
"""
import io

import numpy as np
from PIL import Image, ImageOps

# ── Result contract ───────────────────────────────────────────────
# Every public analysis function returns make_result(...). The app renders
# any result the same way, so a module can't return keys the UI never reads.
STATUSES = ("ok", "insufficient_data", "not_applicable", "error")
LEVELS = ("info", "notice", "warning")  # neutral / weak indicator / inconsistency


def make_result(status, summary, findings=(), metrics=None, images=None,
                tables=None, limitations=(), details=None):
    """
    Args:
        status: one of STATUSES
        summary: one neutral sentence describing what was measured
        findings: iterable of (level, text) or {"level", "text"}
        metrics: {label: number|str} shown as headline numbers
        images: {caption: uint8 ndarray (H,W) or (H,W,3)}
        tables: {title: list[dict] | dict}
        limitations: what this technique cannot see, always shown
        details: raw values for power users / tests (JSON-serialisable)
    """
    if status not in STATUSES:
        raise ValueError(f"bad status {status!r}")
    norm = []
    for f in findings:
        level, text = (f["level"], f["text"]) if isinstance(f, dict) else f
        if level not in LEVELS:
            raise ValueError(f"bad finding level {level!r}")
        norm.append({"level": level, "text": str(text)})
    return {
        "status": status,
        "summary": str(summary),
        "findings": norm,
        "metrics": dict(metrics or {}),
        "images": dict(images or {}),
        "tables": dict(tables or {}),
        "limitations": [str(x) for x in limitations],
        "details": dict(details or {}),
    }


def error_result(exc, limitations=()):
    return make_result("error", f"Analysis failed: {exc}", limitations=limitations)


# ── Decoding ──────────────────────────────────────────────────────
def load_array(image_path, mode="RGB", max_px=None):
    """
    Decode an image to a float64 array in [0, 255] without re-encoding it.

    EXIF orientation is NOT applied: forensic traces (JPEG grid, PRNU, CFA)
    live in the stored pixel order.

    Args:
        mode: "RGB" or "L". Alpha is dropped; 16-bit and palette images are
            converted by Pillow.
        max_px: if set and the longer side exceeds it, downscale in memory
            (area interpolation). Only for analyses that do not depend on
            compression traces. The returned scale says what happened.

    Returns:
        (array, scale) where scale <= 1.0 is the applied resize factor.
    """
    with Image.open(image_path) as img:
        if img.mode in ("I;16", "I;16B", "I;16L", "I"):
            arr = np.asarray(img, dtype=np.float64)
            arr = arr * (255.0 / max(arr.max(), 1.0))
            img = Image.fromarray(arr.astype(np.uint8))
        img = img.convert(mode)
        scale = 1.0
        if max_px and max(img.size) > max_px:
            scale = max_px / max(img.size)
            size = (max(1, round(img.width * scale)),
                    max(1, round(img.height * scale)))
            img = img.resize(size, Image.Resampling.BOX)
        return np.asarray(img, dtype=np.float64), scale


def image_format(image_path):
    with Image.open(image_path) as img:
        return img.format


def to_uint8(arr, stretch=True):
    """Map any array to uint8 for display. stretch=True uses the 0.5-99.5 %
    percentiles so one outlier can't flatten the picture."""
    a = np.asarray(arr, dtype=np.float64)
    a = np.nan_to_num(a)
    if stretch:
        lo, hi = np.percentile(a, [0.5, 99.5])
        a = (a - lo) / (hi - lo) if hi > lo else np.zeros_like(a)
        a = a * 255.0
    return np.clip(a, 0, 255).astype(np.uint8)


def fig_to_array(fig):
    """Rasterise a matplotlib figure to an RGB uint8 array and close it."""
    import matplotlib.pyplot as plt
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=100)
    plt.close(fig)
    buf.seek(0)
    with Image.open(buf) as im:
        return np.asarray(im.convert("RGB"))


def overlay_mask(rgb, mask, color=(255, 0, 0), alpha=0.45):
    """Blend a boolean/float mask onto an RGB image for display."""
    base = np.asarray(rgb, dtype=np.float64)
    if base.ndim == 2:
        base = np.stack([base] * 3, axis=-1)
    m = np.clip(np.asarray(mask, dtype=np.float64), 0, 1)[..., None] * alpha
    out = base * (1 - m) + np.array(color, dtype=np.float64) * m
    return np.clip(out, 0, 255).astype(np.uint8)


# ── JPEG grid ─────────────────────────────────────────────────────
# Block artifact grid (BAG) after W. Li, Y. Yuan, N. Yu, "Passive detection
# of doctored JPEG image via block artifact grid extraction", Signal
# Processing 89(9), 2009. Second-order differences are taken across every
# column/row gap (see _gap_diff); values above T are zeroed so object edges
# do not swamp the weak block-boundary steps; the rest is accumulated along
# the boundary over 33 px, a 33-px running median across it is subtracted,
# and the energy is summed per grid phase. Deviation from the paper: T adapts
# to the image, T = max(BAG_EDGE_MIN, BAG_EDGE_K * median difference). A
# fixed T missed the grid either in textured (grass, gravel) or in smooth
# images. Global crop-offset recovery with the adaptive T: 73 % of 96 cropped
# JPEGs q50-95 (q50-70 94 %, q80 75 %, q90 56 %, q95 31 %), 0/48 false grids
# on never-compressed, NN-2x and bicubic-1.5x images (frequency_analysis).
BAG_EDGE_K = 8.0
BAG_EDGE_MIN = 4.0


def _gap_diff(g, axis):
    """Second-order difference e[x] = |2g[x] - g[x-1] - g[x+1]| (Li et al.),
    summed over the two pixels either side of each gap: out[x] = e[x-1] +
    e[x] is the response to a step between pixels x-1 and x. A lone second
    difference peaks equally on both sides of a block boundary, so the sum
    is what makes the grid phase unambiguous."""
    a = g if axis == 1 else g.T
    e = np.zeros_like(a)
    e[:, 1:-1] = np.abs(2 * a[:, 1:-1] - a[:, :-2] - a[:, 2:])
    out = np.zeros_like(a)
    out[:, 1:] = e[:, 1:] + e[:, :-1]
    return out if axis == 1 else out.T


def bag_diffs(gray, edge_t=None):
    """
    Edge-suppressed boundary differences (edge_t=None: adaptive T above).

    Returns:
        (dh, dv) both shaped like gray. dh[y, x] is the boundary response
        at the gap where a block would start at column x (column 0 is 0);
        dv likewise for rows. Values above edge_t are set to 0.
    """
    g = np.asarray(gray, dtype=np.float64)
    if g.ndim == 3:
        g = g.mean(axis=2)
    dh = _gap_diff(g, 1)
    dv = _gap_diff(g, 0)
    if edge_t is None:
        edge_t = max(BAG_EDGE_MIN, BAG_EDGE_K * float(np.median(dh)))
    dh[dh > edge_t] = 0
    dv[dv > edge_t] = 0
    return dh, dv


def bag_maps(gray, edge_t=None, step=8, win=33):
    """
    Block artifact grid maps (Li et al. 2009, eqs. for accumulation and
    median-based periodic extraction).

    The edge-suppressed differences are summed along the boundary direction
    over `win` px, and the median over `win` px across it is subtracted, so
    only the periodic boundary peaks remain (clipped at 0). To keep this
    O(pixels) the accumulated maps are sampled every `step` px along the
    boundary direction (the 33-px window makes neighbours redundant).

    Returns:
        (gh, gv): gh[i, x] = vertical-boundary BAG at row i*step, column x;
        gv[y, j] = horizontal-boundary BAG at row y, column j*step.
    """
    from scipy import ndimage
    dh, dv = bag_diffs(gray, edge_t)
    ah = ndimage.uniform_filter1d(dh, win, axis=0)[step // 2::step]
    av = ndimage.uniform_filter1d(dv, win, axis=1)[:, step // 2::step]
    gh = np.maximum(ah - ndimage.median_filter(ah, size=(1, win)), 0)
    gv = np.maximum(av - ndimage.median_filter(av, size=(win, 1)), 0)
    return gh, gv


def phase_energy(d, axis):
    """Mean of d over all columns (axis=1) or rows (axis=0) of each phase
    p = index mod 8, normalised to mean 1. Index 0 (no gap) is skipped."""
    prof = np.asarray(d, dtype=np.float64).mean(axis=1 - axis)[1:]
    phase = np.arange(1, prof.size + 1) % 8
    e = np.array([prof[phase == p].mean() if (phase == p).any() else 0.0
                  for p in range(8)])
    return e / max(e.mean(), 1e-12)


def blockiness_by_offset(gray):
    """
    Blocking-artifact strength for all 64 possible 8x8 grid offsets.

    A JPEG that was never cropped peaks at (0, 0); a JPEG cropped by (r, c)
    pixels peaks at ((8 - r) % 8, (8 - c) % 8); an image that was never
    JPEG-compressed has no clear peak.

    Returns:
        (8, 8) array R where R[dy, dx] = row_ratio[dy] * col_ratio[dx]
        (BAG energy at that phase relative to the mean of all phases).
    """
    g = np.asarray(gray, dtype=np.float64)
    if min(g.shape[:2]) < 32:
        return np.ones((8, 8))
    gh, gv = bag_maps(g)
    return np.outer(phase_energy(gv, 0), phase_energy(gh, 1))


def grid_uniqueness(e):
    """Strongest phase energy over the second strongest (1.0 = no unique
    8-periodic peak; an upscale's period-2/4 pattern also gives 1.0)."""
    s = np.sort(np.asarray(e, dtype=np.float64))
    return float(s[-1] / max(s[-2], 1e-12))


def jpeg_grid_offset(gray):
    """
    Estimate where the 8x8 JPEG grid starts.

    Returns:
        (dy, dx, strength) — row/column where blocks start (mod 8) and the
        product over both axes of grid_uniqueness. strength ≈ 1.0 means no
        unique 8x8 grid is visible (never compressed, resampled, upscaled,
        or very high quality); calibrated grid threshold is
        frequency_analysis.GRID_MIN.
    """
    g = np.asarray(gray, dtype=np.float64)
    if min(g.shape[:2]) < 32:
        return 0, 0, 1.0
    gh, gv = bag_maps(g)
    ey, ex = phase_energy(gv, 0), phase_energy(gh, 1)
    return (int(np.argmax(ey)), int(np.argmax(ex)),
            grid_uniqueness(ey) * grid_uniqueness(ex))


if __name__ == "__main__":
    # ponytail: self-check for the grid finder, the one non-trivial helper here
    rng = np.random.default_rng(0)
    # smoothed noise: photo-like texture (pure white noise hides the grid)
    from scipy.ndimage import gaussian_filter
    base = (128 + 12 * gaussian_filter(rng.normal(0, 4, (256, 256)), 1.5)
            ).clip(0, 255).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(base).save(buf, "JPEG", quality=40)
    dec = np.asarray(Image.open(io.BytesIO(buf.getvalue())).convert("L"), float)
    assert jpeg_grid_offset(dec)[:2] == (0, 0), jpeg_grid_offset(dec)
    cropped = dec[3:, 5:]
    assert jpeg_grid_offset(cropped)[:2] == (5, 3), jpeg_grid_offset(cropped)
    assert jpeg_grid_offset(base.astype(float))[2] < 1.2
    up = np.repeat(np.repeat(base, 2, 0), 2, 1).astype(float)  # NN 2x: period 2
    assert jpeg_grid_offset(up)[2] < 1.2, jpeg_grid_offset(up)
    print("util self-check ok")
