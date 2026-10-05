"""
Frequency-domain measurements.

analyze_spectrum: radially averaged power spectrum of the mean-subtracted,
Hann-windowed luminance. Natural images fall off roughly as 1/f^2
(D. J. Field, "Relations between the statistics of natural images and the
response properties of cortical cells", JOSA A 4(12), 1987; A. Torralba and
A. Oliva, "Statistics of natural image categories", Network 14, 2003). The
log-log slope and the share of power above half-Nyquist are reported as
measurements; values outside the range measured on unedited photos are a
notice only, because scene content moves both numbers as much as editing.

analyze_blocking: block artifact grid (BAG) extraction after W. Li, Y. Yuan,
N. Yu, "Passive detection of doctored JPEG image via block artifact grid
extraction", Signal Processing 89(9), 2009 (implementation in
analysis.util.bag_maps). Reports the global 8x8 grid origin (a non-zero
origin means the image was cropped after JPEG compression, or is itself a
pasted JPEG region), and local windows whose grid phase disagrees with the
global grid. A periodic pattern whose period is not 8 (e.g. nearest-neighbour
upscaling) is reported as such, not as a JPEG grid.
"""
import numpy as np
from PIL import Image
from scipy import ndimage

from analysis import util
from analysis.util import error_result, fig_to_array, load_array, make_result

# ── Spectrum ──────────────────────────────────────────────────────
MAX_SIDE = 2048   # centre square crop; cropping (unlike resizing) keeps the spectrum
# Interpretation ranges for the log-binned slope (scratchpad fix3/cal_spec.py).
# Calibration set: sample + 8 skimage photos + 8 camera-pipeline scenes (Bayer
# RGGB, shot/read noise, cv2 demosaic, half sharpened), each PNG and JPEG
# q70/85/95: slope -3.01 .. -1.08 (grass), HF 0.19 .. 28.6 %.
# Hold-out (6 other skimage images + 8 other seeds, 60 negatives):
#   outside the range 8/60 (13 %): every version of 'cat' (slope -4.3, smooth
#   fur) and 'colorwheel' (HF 0.02 %, flat graphic) - scene content, as the
#   limitations say; Gaussian blur s=1.5 13/15, 2x bicubic upscale 3/15,
#   Gaussian noise s=8 0/15.
SLOPE_LO, SLOPE_HI = -3.5, -1.0
HF_LO, HF_HI = 0.0005, 0.30

SPECTRUM_LIMITATIONS = [
    "The slope and HF share depend mostly on scene content (sky vs foliage, "
    "focus, depth of field); an out-of-range value is not evidence of editing.",
    "Upscaling, sharpening and added noise stay inside the range measured on "
    "unedited photos in most cases; only strong blur is usually visible.",
    "A whole-image spectrum cannot localise an edit.",
    f"Images larger than {MAX_SIDE} px are measured on a centre crop.",
]


def _square_crop(g, n):
    y0, x0 = (g.shape[0] - n) // 2, (g.shape[1] - n) // 2
    return g[y0:y0 + n, x0:x0 + n]


def power_spectrum_stats(gray):
    """(slope, hf_share, radial_profile, log_power) for a square 2-D array."""
    n = gray.shape[0]
    x = gray - gray.mean()
    x = x * np.outer(np.hanning(n), np.hanning(n))
    p = np.abs(np.fft.fftshift(np.fft.fft2(x))) ** 2
    c = n // 2
    yy, xx = np.ogrid[:n, :n]
    r = np.hypot(yy - c, xx - c).astype(int)
    prof = (np.bincount(r.ravel(), p.ravel())[:c]
            / np.maximum(np.bincount(r.ravel())[:c], 1))
    slope = float(_loglog_fit(prof)[0])
    hf = float(p[r > c / 2].sum() / max(p.sum(), 1e-12))
    return slope, hf, prof, np.log1p(p)


def _loglog_fit(prof, nbins=24):
    """Line fit of log power vs log frequency on log-spaced bins. A plain
    fit over all radii k=1..c is dominated by the high-frequency end (most
    radii live there), so noise / JPEG floor sets the slope; equal-width
    bins in log k weight each octave equally."""
    k = np.arange(1, prof.size)
    edges = np.unique(np.geomspace(1, prof.size, nbins + 1).astype(int))
    idx = np.digitize(k, edges) - 1
    lk = np.bincount(idx, np.log(k)) / np.maximum(np.bincount(idx), 1)
    lp = np.bincount(idx, np.log(prof[1:] + 1e-12)) / np.maximum(np.bincount(idx), 1)
    used = np.bincount(idx) > 0
    return np.polyfit(lk[used], lp[used], 1)


def _profile_plot(prof, slope):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    k = np.arange(1, prof.size)
    fit = _loglog_fit(prof)
    fig, ax = plt.subplots(figsize=(6, 3.6))
    ax.loglog(k, prof[1:], lw=1, label="radial average")
    ax.loglog(k, np.exp(np.polyval(fit, np.log(k))), "--",
              label=f"fit, slope {slope:.2f}")
    ax.axvline(prof.size / 2, color="grey", lw=0.8, ls=":")
    ax.set_xlabel("spatial frequency (cycles per crop)")
    ax.set_ylabel("power")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3, which="both")
    return fig_to_array(fig)


def analyze_spectrum(image_path):
    """
    Power-spectrum slope and high-frequency share.

    Images: log power spectrum, radial profile with fit. Metrics: slope,
    HF share (%), analysed size.
    """
    try:
        g, _ = load_array(image_path, "L")
        n = min(min(g.shape), MAX_SIDE)
        if n < 16 or g.std() < 1.0:
            return make_result(
                "insufficient_data",
                f"Image is {g.shape[1]}x{g.shape[0]} px or uniform; a "
                "spectral slope needs at least 16x16 px of varying content.",
                limitations=SPECTRUM_LIMITATIONS)
        sq = _square_crop(g, n)
        slope, hf, prof, logp = power_spectrum_stats(sq)
        findings = []
        if not SLOPE_LO <= slope <= SLOPE_HI:
            kind = ("steeper (less fine detail: blur, denoising, upscaling, "
                    "or a smooth scene)" if slope < SLOPE_LO else
                    "flatter (more fine detail: noise, sharpening, or a "
                    "highly textured scene)")
            findings.append(("notice", f"Spectral slope {slope:.2f} is outside "
                             f"the range measured on unedited photos "
                             f"({SLOPE_LO} to {SLOPE_HI}): {kind}."))
        if not HF_LO <= hf <= HF_HI:
            findings.append(("notice", f"{hf * 100:.3f} % of power lies above "
                             "half-Nyquist, outside the range measured on "
                             f"unedited photos ({HF_LO * 100:g}-{HF_HI * 100:g} %)."))
        if not findings:
            findings.append(("info", f"Slope {slope:.2f} and HF share "
                             f"{hf * 100:.2f} % are within the ranges measured "
                             "on unedited photos: no inconsistency found at "
                             "this sensitivity."))
        if n < min(g.shape):
            findings.append(("info", f"Measured on the centre {n}x{n} px."))
        return make_result(
            "ok",
            f"Measured the radially averaged power spectrum of a {n}x{n} px "
            f"luminance crop (slope {slope:.2f}).",
            findings,
            {"Spectral slope (log power / log freq)": round(slope, 3),
             "Power above half-Nyquist (%)": round(hf * 100, 4),
             "Analysed size (px)": f"{n}x{n}"},
            {"Log power spectrum (centre = DC)": util.to_uint8(logp),
             "Radial power profile": _profile_plot(prof, slope)},
            limitations=SPECTRUM_LIMITATIONS,
            details={"slope": slope, "hf_share": hf, "size": int(n),
                     "slope_range": [SLOPE_LO, SLOPE_HI],
                     "hf_range": [HF_LO, HF_HI]})
    except Exception as e:  # noqa: BLE001
        return error_result(e, SPECTRUM_LIMITATIONS)


# ── Blocking / BAG ────────────────────────────────────────────────
# Calibrated (scratchpad p7/cal_grid.py, cal_local.py, sweep_local4.py) on
# 16 photos (sample + skimage):
# GRID_MIN: grid reported when jpeg_grid_offset strength >= 1.4. Never-
#   compressed (0.5x area-downscaled) photos, their NN-2x and bicubic-1.5x
#   upscales: 0/48 false grids. Cropped JPEGs (random 0-7 px crop) with the
#   crop offset recovered: q50 15/16, q60 15/16, q70 14/16, q80 12/16,
#   q90 9/16, q95 5/16 (73 %).
# Local: 64x64 windows on a 32-px step; a window is misaligned when its
#   strongest phase pair differs from the global one and beats the global
#   phase by LOCAL_UNIQ on some axis; MIN_CLUSTER touching windows with the
#   SAME phase pair are reported (texture gives random phases, a pasted JPEG
#   one consistent phase). Positives: 25-40 % patch from a q50-80 JPEG
#   pasted at a non-aligned position into a q70-95 JPEG: saved at q95 6/16,
#   q100 7/16, PNG 8/16 localised (44 %; 39/48 had a measurable global
#   grid). Negatives: cropped clean JPEGs q50-95 2/48 flagged (both the
#   bundled sample, itself a q95 JPEG, so the crop created a real 2nd grid).
GRID_MIN = 1.4
AC_MIN = 0.5      # |diff| profile autocorrelation; clean photos max 0.34 (0/16),
                  # NN 2x 16/16, NN 3x 16/16, bilinear 2x 10/16 (chk_period.py)
TILE = 32
LOCAL_UNIQ = 2.0
MIN_CLUSTER = 5
GLOBAL_SECOND = 50.0  # % of image: a second grid this widespread is global

BLOCKING_LIMITATIONS = [
    "JPEG quality >= 90 leaves a weak grid that is often not measurable, "
    "especially in small or smooth images.",
    "Resizing, rotation, strong filtering or noise after compression erase "
    "the grid; a grid-free image may still have been a JPEG.",
    "A pasted region is only visible if it carries its own grid at a "
    "different phase and was not recompressed at a lower quality afterwards.",
    "Flat regions (sky, walls) have no measurable local grid.",
]


DISPLAY_MAX = 1200


def _display(a):
    """Downscale a uint8 image so its longer side is <= DISPLAY_MAX."""
    h, w = a.shape[:2]
    s = max(h, w) / DISPLAY_MAX
    if s <= 1:
        return a
    return np.asarray(Image.fromarray(a).resize(
        (max(1, round(w / s)), max(1, round(h / s))), Image.Resampling.BOX))


def _period(g, axis):
    """Dominant period (px) of the mean |first difference| profile along
    `axis` (1 = x) and its normalised autocorrelation, lags 2..32."""
    prof = np.abs(np.diff(g, axis=axis)).mean(axis=1 - axis)
    if prof.size < 72:
        return 0, 0.0
    hp = prof - ndimage.uniform_filter1d(prof, 9)
    hp = hp - hp.mean()
    ac = np.correlate(hp, hp, "full")[hp.size - 1:]
    ac = ac / max(ac[0], 1e-12)
    lags = ac[2:33]
    best = float(lags.max())
    period = int(np.flatnonzero(lags >= 0.8 * best)[0] + 2)
    return period, best


def _local_phase(gh, gv, h, w):
    """Per-window 8-phase BAG energies (nwy, nwx, 8) for x and y, on
    2x2-tile (64 px) windows with a TILE-px step."""
    step = 8  # bag_maps sampling step
    rows_per_tile = TILE // step
    nty, ntx = h // TILE, w // TILE
    # x phases: gh[i, x], x = column; phase = x % 8
    a = gh[:nty * rows_per_tile, :ntx * TILE]
    a = a.reshape(nty, rows_per_tile, ntx, TILE // 8, 8).sum(axis=(1, 3))
    # y phases: gv[y, j]
    b = gv[:nty * TILE, :ntx * rows_per_tile]
    b = b.reshape(nty, TILE // 8, 8, ntx, rows_per_tile).sum(axis=(1, 4))
    b = b.transpose(0, 2, 1)
    win = lambda t: t[:-1, :-1] + t[1:, :-1] + t[:-1, 1:] + t[1:, 1:]
    return win(a), win(b)


def local_misalignment(gh, gv, h, w, gy, gx):
    """
    Returns (score, keep): score[i, j] in [-1, 1] = log2 of global-phase
    energy over the strongest other phase (min over axes; >0 aligned, <0
    another phase dominates); keep = windows in clusters of >= MIN_CLUSTER
    touching misaligned windows sharing one phase pair.
    """
    ex, ey = _local_phase(gh, gv, h, w)

    def axis_score(e, g):
        other = np.delete(e, g, axis=2).max(axis=2)
        return np.log2((e[..., g] + 1e-9) / (other + 1e-9))

    score = np.minimum(axis_score(ex, gx), axis_score(ey, gy))
    pair = ey.argmax(axis=2) * 8 + ex.argmax(axis=2)
    mis = (score < -np.log2(LOCAL_UNIQ)) & (pair != gy * 8 + gx)
    keep = np.zeros_like(mis)
    for v in np.unique(pair[mis]):
        lab, n = ndimage.label(mis & (pair == v))
        sizes = np.bincount(lab.ravel())[1:]
        keep |= np.isin(lab, np.flatnonzero(sizes >= MIN_CLUSTER) + 1)
    return np.clip(score, -1, 1), keep


def analyze_blocking(image_path):
    """
    JPEG block-artifact-grid analysis.

    Images: BAG map, local alignment heatmap (when a grid is present).
    Metrics: grid origin, grid strength, dominant period per axis,
    misaligned area %.
    """
    try:
        g, _ = load_array(image_path, "L")
        h, w = g.shape
        if min(h, w) < 64 or g.std() < 1.0:
            return make_result(
                "insufficient_data",
                f"Image is {w}x{h} px or uniform; grid analysis needs at "
                "least 64x64 px of varying content.",
                limitations=BLOCKING_LIMITATIONS)
        gh, gv = util.bag_maps(g)
        ey, ex = util.phase_energy(gv, 0), util.phase_energy(gh, 1)
        gy, gx = int(np.argmax(ey)), int(np.argmax(ex))
        strength = util.grid_uniqueness(ey) * util.grid_uniqueness(ex)
        px, acx = _period(g, 1)
        py, acy = _period(g, 0)
        grid = strength >= GRID_MIN
        fmt = util.image_format(image_path)

        findings, images = [], {}
        metrics = {"Grid strength (1 = none)": round(strength, 3),
                   "Grid origin (x, y) px": f"{gx}, {gy}" if grid else "none",
                   "Periodicity x / y (px)": " / ".join(
                       str(p) if ac >= AC_MIN else "none"
                       for p, ac in ((px, acx), (py, acy)))}
        details = {"grid": bool(grid), "strength": float(strength),
                   "origin": [gy, gx], "period": [py, px],
                   "autocorr": [float(acy), float(acx)], "format": fmt}
        bag = np.zeros((h, w))
        bag[4::8, :] = gh
        bag[:, 4::8] += gv
        k = max(3, int(np.ceil(max(h, w) / DISPLAY_MAX)) + 1)
        images["BAG map (block-boundary energy)"] = _display(
            util.to_uint8(ndimage.maximum_filter(bag, k)))

        if grid:
            findings.append(("info", f"8x8 JPEG block grid found (strength "
                             f"{strength:.2f}), blocks start at x={gx}, y={gy}."))
            if fmt != "JPEG":
                findings.append(("info", f"File is {fmt} but carries a JPEG "
                                 "grid: it was JPEG-compressed before being "
                                 "saved in this format."))
            if (gx, gy) != (0, 0):
                findings.append((
                    "info",
                    f"Grid origin is not (0, 0): consistent with {(8 - gx) % 8} "
                    f"column(s) and {(8 - gy) % 8} row(s) removed from the "
                    "left/top after JPEG compression (a crop), or with the "
                    "image being a pasted JPEG region."))
            score, keep = local_misalignment(gh, gv, h, w, gy, gx)
            n_reg = int(ndimage.label(keep)[1])
            mis_pct = float(keep.mean() * 100) if keep.size else 0.0
            metrics["Misaligned-grid area (%)"] = round(mis_pct, 2)
            details["misaligned_pct"] = mis_pct
            details["n_misaligned_regions"] = n_reg
            rgb = np.zeros(score.shape + (3,))
            rgb[..., 0] = np.clip(-score, 0, 1) * 255   # red: other phase
            rgb[..., 1] = np.clip(score, 0, 1) * 255    # green: aligned
            sc = min(TILE, DISPLAY_MAX / max(score.shape) / 1.0)
            images["Local grid alignment (green aligned, red misaligned, "
                   "dark = no measurable grid)"] = np.asarray(
                Image.fromarray(rgb.astype(np.uint8)).resize(
                    (max(1, round(score.shape[1] * sc)),
                     max(1, round(score.shape[0] * sc))),
                    Image.Resampling.NEAREST))
            if mis_pct >= GLOBAL_SECOND:
                findings.append((
                    "notice",
                    f"A second JPEG grid at another phase covers {mis_pct:.0f}% "
                    "of the image: consistent with the whole image having "
                    "been cropped and recompressed (double JPEG), not with a "
                    "local paste."))
            elif n_reg:
                findings.append((
                    "warning",
                    f"{n_reg} region(s) ({mis_pct:.1f}% of the image) show "
                    "a JPEG grid at a different phase from the rest of the "
                    "image: consistent with content pasted from another JPEG."))
            else:
                findings.append(("info", "Tested local windows for a grid "
                                 "misaligned with the global grid: no "
                                 "inconsistency found at this sensitivity."))
        else:
            per = [(a, p, ac) for a, p, ac in (("x", px, acx), ("y", py, acy))
                   if ac >= AC_MIN and p % 8]
            if per:
                findings.append(("info", "Periodic pattern with period " +
                                 ", ".join(f"{p} px along {a}" for a, p, _ in per) +
                                 ": typical of upscaling/resampling, not of an "
                                 "8x8 JPEG grid."))
            findings.append(("info", "No 8x8 JPEG grid measurable (strength "
                             f"{strength:.2f} < {GRID_MIN}): never compressed, "
                             "high quality, or resized after compression. "
                             "Local grid analysis needs a global grid."))
        return make_result(
            "ok",
            f"Extracted the JPEG block artifact grid from {w}x{h} px "
            f"({'grid found' if grid else 'no grid'}).",
            findings, metrics, images, limitations=BLOCKING_LIMITATIONS,
            details=details)
    except Exception as e:  # noqa: BLE001
        return error_result(e, BLOCKING_LIMITATIONS)
