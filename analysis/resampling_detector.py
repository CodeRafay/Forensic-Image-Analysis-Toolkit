"""
Resampling detection (rescaling / rotation) with localisation.

Method: M. Kirchner, "Fast and reliable resampling detection by spectral
analysis of fixed linear predictor residue", ACM MM&Sec 2008, with the
JPEG-aware peak masking of M. Kirchner & T. Gloe, "On resampling detection in
re-compressed images", IEEE WIFS 2009.

1. Grayscale at full resolution (no resize: resizing is what we look for).
2. Residual of Kirchner's fixed 3x3 linear predictor
   e = x - (0.5*(N+S+E+W) - 0.25*(NE+NW+SE+SW)).
3. p-map p = lambda*exp(-|e|^tau / sigma) (lambda=1, tau=2 as in the paper;
   sigma calibrated, see SIGMA). Interpolated pixels are well predicted by
   their neighbours in a pattern that repeats with the resampling period,
   so p is periodic after resampling and aperiodic in a camera image.
4. |DFT| of the (Hann-windowed, mean-removed) p-map. Contrast step: each bin
   is divided by the geometric mean of its 9x9 neighbourhood, so a periodic
   component shows as an isolated peak whatever the image spectrum's shape.
5. Statistic = the largest normalised peak outside the low-frequency disc
   (image content), after a narrow notch at lattice points (Kirchner & Gloe
   2009): always (0.5, 0), (0, 0.5), (0.5, 0.5) (CFA demosaicing), and the
   whole 8x8 lattice (k/8, l/8) for JPEG files or images with a measurable
   grid (frequency_analysis.GRID_MIN).
5b. Derivative-projection detector (Gallagher 2005; axis-aligned Mahdian &
   Saic 2008): column/row means of |2nd derivative|, 1-D spectrum, same
   lattice notch (2.5 bins). Survives JPEG much better than the p-map; sees
   axis-aligned scaling only. The image is flagged if either detector
   exceeds its own threshold.
6. Separate nearest-neighbour test: exact duplication of whole pixel rows or
   columns. Needed because a centre-aligned 2x enlargement (Pillow, OpenCV)
   is symmetric in both phases and leaves no p-map periodicity at all.
7. Localisation: the same statistic in 128x128 windows (stride 64).

Scale factor from the peak frequency f (cycles/pixel): an up-scaling by s
peaks at 1 - 1/s (1.25x -> 0.2, 1.5x -> 0.333, verified exact), but f is
aliased, so 1/f and the down-scaling reading 1/(1+f) fit the same peak and
all are reported. An off-axis peak at radius r fits a rotation by
2*asin(r/2).
"""
import cv2
import numpy as np
from scipy import fft as sfft, ndimage

from analysis.frequency_analysis import GRID_MIN
from analysis.util import (error_result, fig_to_array, image_format,
                           jpeg_grid_offset, load_array, make_result,
                           overlay_mask, to_uint8)

PREDICTOR = np.array([[-0.25, 0.5, -0.25],
                      [0.5, 0.0, 0.5],
                      [-0.25, 0.5, -0.25]])
SIGMA = 8.0        # p-map width (grey levels^2); 8 beat 4 and 16 on JPEG-after-resize
LOW_FREQ = 0.06    # radius (cycles/px) of the content disc excluded around DC
NOTCH_BINS = 2.5   # half-width (DFT bins) of the notch at each lattice point
# Texture modulates the JPEG lattice peaks by a few 1/1000 cycles/px (rocket
# q50: peak at (0.124, 0.0078), 5 bins off the lattice), so the 2-D notch is
# at least NOTCH_MIN wide; the 1-D projection keeps the pure 2.5-bin notch.
NOTCH_MIN = 0.01
PROJ_LOW = 0.03    # projection detector: content cut-off (cycles/px)
UNIFORM_TOL = 0.01 # |fy| ~ |fx| within this (cycles/px) = uniform scaling
BG_SIZE = 9        # neighbourhood for spectrum normalisation (bins)
GLOBAL_MAX = 2048  # central crop for the global DFT (crop, never resize)
# FIX-ROUND CALIBRATION (scratchpad fix3/cal_rs.py), thresholds chosen on
# set A only: 8 photos (sample, coffee, chelsea, rocket, brick, page, grass,
# gravel) + 10 camera-pipeline scenes (Bayer, noise, cv2 demosaic, half
# sharpened); negatives PNG, JPEG q75/85/92/95, crop of q80 re-saved q90
# (108): Kirchner max 11.49 (brick q85) -> THRESHOLD 12; projection max 7.68
# (page) -> PROJ_THRESHOLD 7.8; fused FP 0/108.
# Hold-out B (7 other skimage images + 10 other seeds, 102 negatives): FP
# 1/102 (hubble_deep_field PNG, Kirchner 26.8 - the source is itself
# resampled, likely). Reviewer's independent set (16 hosts): 0/64.
# Hold-out B TPR (10 camera hosts) PNG / q95 / q90 / q80:
#   up 1.1x bicubic 10/10/10/9, 1.25x 10/10/10/10, 1.3x bilinear
#   10/10/10/9, 1.7x 10/10/10/10; down 0.8x 10/0/0/0; rotation 7 deg
#   bilinear 10/8/0/0, bicubic 9/8/1/0.
# Reviewer set (harder, 16 hosts) PNG / q95 / q90 / q80: 1.1x 14/9/6/0,
#   1.3x 16/12/8/1, 1.7x 16/14/11/9; down 0.8x 14/0/0/0; rot7 13/0/0/0.
THRESHOLD = 12.0       # fix-round calibration, see the block below
WIN, STRIDE = 128, 64
# 6144 negative windows: 0.05 % >= 10, 3/146 images have any such window.
# 200x200 pasted bicubic object in 4 bases x 4 sources: 1.5x 14/16, 1.25x
# 11/16 hit, 0 windows off the object; after JPEG q90: 0/16.
WIN_THRESHOLD = 10.0
# Nearest-neighbour s-x enlargement duplicates a share 1 - 1/s of columns
# (1.1x -> 0.09, 2x -> 0.5): 13/13 PNG found at each of 1.1-2x; 0.0 on all
# 143 negatives incl. JPEG q20 decodes; a later JPEG q90 erases the copies.
NN_RATE = 0.05
MIN_SIDE = 64
PROJ_THRESHOLD = 7.8
MAX_WINDOWS = 1500     # window grid cap: stride grows on very large images

LIMITATIONS = [
    "Down-scaling is detectable only in lossless files; after any JPEG "
    "(even q95) it was missed in all test cases.",
    "Rotation is seen only by the 2-D p-map test: found in most lossless "
    "files and about 8/10 at JPEG q95, almost never at q90 or below.",
    "JPEG after enlargement: the projection test finds most 1.1-1.7x "
    "enlargements at q90-95, but at q80 small factors (1.1-1.3x) are "
    "often missed (0-1 of 16 in the hardest test set).",
    "Scale factors whose peak falls within 0.01 cycles/px of a multiple of "
    "1/8 (about 1.14x, 1.33x, 1.6x, 2x and aliases) are masked in the 2-D "
    "test of JPEG images; the 1-D projection test keeps a narrower mask.",
    "Centre-aligned 2x smooth interpolation (bilinear/bicubic/Lanczos) leaves "
    "no periodicity; only nearest-neighbour enlargement up to 2x is caught "
    "(duplication test), and only in lossless files.",
    "The scale factor is ambiguous: aliasing makes several factors fit one "
    "peak; all candidates are listed.",
    "Periodic textures (brick, fabric, screens, halftone) can produce peaks "
    "unrelated to resampling; brick JPEGs came closest to the threshold.",
    "Resizing is routine (web publishing, thumbnails); a detection says the "
    "pixels were interpolated, not that content was altered.",
]


def p_map(gray, sigma=SIGMA):
    """Kirchner p-map of the fixed-predictor residual (float32)."""
    g = np.asarray(gray, np.float32)
    # PREDICTOR is symmetric, so correlation (cv2) = convolution
    e = g - cv2.filter2D(g, cv2.CV_32F, PREDICTOR.astype(np.float32),
                         borderType=cv2.BORDER_REFLECT)
    return np.exp(-e * e / np.float32(sigma))


def _freqs(h, w):
    return np.meshgrid(np.fft.fftshift(np.fft.fftfreq(h)),
                       np.fft.fftshift(np.fft.fftfreq(w)), indexing="ij")


def _lattice_dist(f, jpeg):
    """Distance (cycles/px) to the nearest notched frequency on one axis:
    the JPEG lattice k/8 (incl. 0 and Nyquist) or, without a JPEG grid, only
    0 and Nyquist (the CFA / demosaicing period 2)."""
    step = 8 if jpeg else 2
    return np.abs(f * step - np.round(f * step)) / step


def _search_mask(fy, fx, jpeg):
    """Exclude the content disc and a narrow square of +-NOTCH_BINS bins
    around each lattice point (Kirchner & Gloe 2009). The point set always
    contains (0.5, 0), (0, 0.5), (0.5, 0.5): bilinear demosaicing alone puts
    peaks there (review: 7/16 clean demosaiced PNGs flagged without it)."""
    ny, nx = fy.shape[-2], fx.shape[-1]
    ok = np.hypot(fx, fy) > LOW_FREQ
    ok &= ~((_lattice_dist(fy, jpeg) <= max(NOTCH_BINS / ny, NOTCH_MIN)) &
            (_lattice_dist(fx, jpeg) <= max(NOTCH_BINS / nx, NOTCH_MIN)))
    return ok


def peak_ratio(spec, bg_axes, jpeg):
    """Normalised spectrum and its search mask (works on a stack too)."""
    size = [BG_SIZE if a in bg_axes else 1 for a in range(spec.ndim)]
    # ponytail: geometric mean of the neighbourhood (mean of log) instead of
    # the median: same robustness to one peak, ~50x faster on 2048^2.
    log = np.log(spec + 1e-12)
    ratio = np.exp(log - ndimage.uniform_filter(log, size=size, mode="wrap"))
    fy, fx = _freqs(*spec.shape[-2:])
    return ratio, _search_mask(fy, fx, jpeg)


def projection_statistic(gray, jpeg):
    """
    Axis-aligned derivative-projection detector (A. C. Gallagher, "Detection
    of linear and cubic interpolation in JPEG compressed images", CRV 2005;
    the axis-aligned case of B. Mahdian & S. Saic, "Blind authentication
    using periodic properties of interpolation", IEEE TIFS 3(3), 2008):
    mean |2nd derivative| per column (and per row), 1-D DFT, contrast
    against the local log-spectrum mean. Averaging over a whole column
    keeps the interpolation period after JPEG, where the 2-D p-map loses it.
    Returns (ratio, f cycles/px, axis 'horizontal'/'vertical').
    """
    g = np.asarray(gray, np.float32)
    best = (0.0, 0.0, "horizontal")
    for a, name in ((g, "horizontal"), (g.T, "vertical")):
        prof = np.abs(a[:, 2:] - 2 * a[:, 1:-1] + a[:, :-2]).mean(axis=0, dtype=np.float64)
        prof = prof - ndimage.uniform_filter1d(prof, 15)
        n = prof.size
        s = np.abs(np.fft.rfft(prof * np.hanning(n)))
        f = np.fft.rfftfreq(n)
        lg = np.log(s + 1e-12)
        ratio = np.exp(lg - ndimage.uniform_filter1d(lg, 15))
        ok = (f > PROJ_LOW) & (_lattice_dist(f, jpeg) > NOTCH_BINS / n)
        if ok.any():
            i = np.flatnonzero(ok)[np.argmax(ratio[ok])]
            if ratio[i] > best[0]:
                best = (float(ratio[i]), float(f[i]), name)
    return best


def global_spectrum(p):
    h, w = p.shape
    # ponytail: central crop keeps the DFT bounded for huge photos; a global
    # resampling is present in every part, so no evidence is lost.
    ch, cw = min(h, GLOBAL_MAX), min(w, GLOBAL_MAX)
    y0, x0 = (h - ch) // 2, (w - cw) // 2
    t = p[y0:y0 + ch, x0:x0 + cw]
    win = np.outer(np.hanning(ch), np.hanning(cw)).astype(np.float32)
    return np.abs(np.fft.fftshift(sfft.fft2((t - t.mean()) * win)))


def global_statistic(gray, jpeg):
    """(ratio, fy, fx, spectrum) of the strongest in-band peak."""
    spec = global_spectrum(p_map(gray))
    ratio, ok = peak_ratio(spec, (0, 1), jpeg)
    fy, fx = _freqs(*spec.shape)
    r = np.where(ok, ratio, 0.0)
    i = int(np.argmax(r))
    return float(r.flat[i]), float(fy.flat[i]), float(fx.flat[i]), spec


def statistics(gray, jpeg_file):
    """Both global detectors on a grayscale array. The JPEG notch applies
    to JPEG files and to images carrying a measurable 8x8 grid
    (frequency_analysis.GRID_MIN, calibrated on never-compressed images)."""
    grid_strength = float(jpeg_grid_offset(gray)[2])
    jpeg = bool(jpeg_file or grid_strength >= GRID_MIN)
    ratio, fy, fx, spec = global_statistic(gray, jpeg)
    return {"jpeg": jpeg, "grid_strength": grid_strength, "ratio": ratio,
            "fy": fy, "fx": fx, "spec": spec,
            "proj": projection_statistic(gray, jpeg)}


def window_stride(h, w):
    """STRIDE, doubled until the grid has at most MAX_WINDOWS windows."""
    st = STRIDE
    while ((h - WIN) // st + 1) * ((w - WIN) // st + 1) > MAX_WINDOWS:
        st *= 2
    return st


def window_statistics(gray, jpeg, stride=STRIDE):
    """Peak ratio per WIN x WIN window; returns 2-D grid."""
    p = p_map(gray)
    h, w = p.shape
    ys = range(0, h - WIN + 1, stride)
    xs = range(0, w - WIN + 1, stride)
    win = np.outer(np.hanning(WIN), np.hanning(WIN)).astype(np.float32)
    out = np.zeros((len(ys), len(xs)))
    for i, y in enumerate(ys):  # one row of windows at a time bounds memory
        tiles = np.stack([p[y:y + WIN, x:x + WIN] for x in xs])
        tiles = (tiles - tiles.mean(axis=(1, 2), keepdims=True)) * win
        spec = np.abs(np.fft.fftshift(sfft.fft2(tiles), axes=(1, 2)))
        ratio, ok = peak_ratio(spec, (1, 2), jpeg)
        out[i] = np.where(ok, ratio, 0.0).max(axis=(1, 2))
    return out


def duplication_rate(gray):
    """
    Share of adjacent (non-flat) columns / rows that are exact copies, counted
    only when the copies sit on a regular lattice (gaps of g or g+1 px, as
    nearest-neighbour scaling produces). Smooth or posterised content also
    repeats columns, but at irregular positions; it scores 0.
    """
    def rate(a):
        same = (a[:, 1:] == a[:, :-1]).mean(axis=0) >= 0.99
        textured = a.std(axis=0)[1:] > 1.0
        pos = np.flatnonzero(same & textured)
        if pos.size < 3:
            return 0.0
        gaps = np.diff(pos)
        # ponytail: lattice gaps >= 2 only, i.e. enlargements up to 2x; gap 1
        # would also match flat JPEG blocks. Wider NN factors: add runs.
        regular = max((np.isin(gaps, (g, g + 1)).mean() for g in np.unique(gaps) if g >= 2),
                      default=0.0)
        return float(pos.size / max(textured.sum(), 1)) if regular >= 0.9 else 0.0
    return rate(gray), rate(gray.T)


def scale_candidates(fy, fx):
    """Readings consistent with a peak at (fy, fx) cycles/pixel."""
    """
    Returns (scale candidates, rotation reading in degrees or None).

    On-axis peak at f: up-scaling 1/(1-f), aliased up-scaling 1/f,
    down-scaling 1/(1+f). A rotation by t peaks at (sin t, 1-cos t), i.e.
    radius r = 2 sin(t/2) and only ~t/2 off-axis, so a peak up to 8 deg
    off-axis also gets a rotation reading; clearly off-axis peaks
    (> 8 deg, beyond the 15-deg rotations tested) get no scale reading.
    """
    f = max(abs(fy), abs(fx))
    r = min(np.hypot(fy, fx), 1.0)
    if abs(abs(fy) - abs(fx)) <= UNIFORM_TOL:
        # A uniform scale by s peaks on both axes at once: the strongest bin
        # is the diagonal (f, f), not a rotation (review: 1.3x read as 19 deg).
        return sorted({round(v, 3) for v in (1 / (1 - f), 1 / f, 1 / (1 + f))
                       if 0.5 <= v <= 16}), None
    angle = np.degrees(np.arctan2(min(abs(fy), abs(fx)), f))
    rot = float(np.degrees(2 * np.arcsin(r / 2))) if 0.3 < angle <= 8 else None
    if angle > 8:
        return [], float(np.degrees(2 * np.arcsin(r / 2)))
    cands = sorted({round(v, 3) for v in (1 / (1 - f), 1 / f, 1 / (1 + f))
                    if 0.5 <= v <= 16})
    return cands, rot


def _heatmap(grid, shape, stride=STRIDE):
    """Per-pixel max of the window statistics covering it."""
    h, w = shape
    m = np.zeros(shape, np.float32)
    for i in range(grid.shape[0]):
        for j in range(grid.shape[1]):
            sl = (slice(i * stride, i * stride + WIN), slice(j * stride, j * stride + WIN))
            m[sl] = np.maximum(m[sl], grid[i, j])
    return m


def _spectrum_image(spec):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    k = max(1, max(spec.shape) // 512)   # block max keeps isolated peaks visible
    h, w = (spec.shape[0] // k) * k, (spec.shape[1] // k) * k
    spec = spec[:h, :w].reshape(h // k, k, w // k, k).max(axis=(1, 3))
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.imshow(np.log1p(spec), cmap="gray", extent=(-0.5, 0.5, 0.5, -0.5))
    ax.set_xlabel("horizontal frequency (cycles/px)")
    ax.set_ylabel("vertical frequency (cycles/px)")
    ax.set_title("p-map spectrum")
    return fig_to_array(fig)


def detect_resampling(image_path):
    """
    Test an image for resampling (rescaling / rotation) traces.

    Returns the util.make_result contract. images: p-map spectrum, window
    heatmap, heatmap overlay. metrics: peak ratio vs threshold, peak
    frequency, duplication rates, flagged-window share.
    """
    try:
        gray, _ = load_array(image_path, "L")
        h, w = gray.shape
        if min(h, w) < MIN_SIDE or gray.std() < 1.0:
            return make_result(
                "insufficient_data",
                f"Image is {w}x{h} px or flat; resampling periodicity needs "
                f"at least {MIN_SIDE} px of textured content per side.",
                limitations=LIMITATIONS,
                details={"width": w, "height": h})

        jpeg_file = image_format(image_path) == "JPEG"
        st = statistics(gray, jpeg_file)
        jpeg, grid_strength = st["jpeg"], st["grid_strength"]
        ratio, fy, fx, spec = st["ratio"], st["fy"], st["fx"], st["spec"]
        pr, pf, paxis = st["proj"]
        kir_hit, proj_hit = ratio >= THRESHOLD, pr >= PROJ_THRESHOLD
        detected = kir_hit or proj_hit
        cands, rot = scale_candidates(fy, fx)
        pcands = scale_candidates(0.0, pf)[0] if pf > 0 else []
        dup_cols, dup_rows = duplication_rate(gray)
        # Exact copies cannot survive a later JPEG (q90 already erases them),
        # while coarse JPEG quantisation of smooth content creates some.
        nn = not jpeg_file and max(dup_cols, dup_rows) >= NN_RATE

        findings, details = [], {}
        if kir_hit:
            readings = []
            if cands:
                readings.append("scale factor " + " or ".join(f"{c:g}x" for c in cands))
            if rot is not None:
                readings.append(f"a rotation of about {rot:.1f} deg")
            reading = "consistent with " + " or ".join(readings) + \
                      " (aliasing makes these readings indistinguishable)"
            findings.append(("warning",
                             f"Periodic interpolation correlations found (peak ratio "
                             f"{ratio:.1f} >= {THRESHOLD:g} at {fy:+.3f}, {fx:+.3f} "
                             f"cycles/px): {reading}."))
        if proj_hit:
            findings.append(("warning",
                             f"Periodic interpolation trace in the {paxis} derivative "
                             f"projection (peak ratio {pr:.1f} >= {PROJ_THRESHOLD:g} at "
                             f"{pf:.3f} cycles/px): consistent with {paxis} scaling by "
                             + " or ".join(f"{c:g}x" for c in pcands) +
                             " (aliased readings)."))
        if nn:
            s = [round(1 / (1 - r), 3) for r in (dup_cols, dup_rows) if r >= NN_RATE]
            findings.append(("warning",
                             f"{100 * max(dup_cols, dup_rows):.1f} % of adjacent pixel "
                             f"columns/rows are exact duplicates: nearest-neighbour "
                             f"enlargement by about {' / '.join(f'{v:g}x' for v in s)}."))

        images = {"p-map spectrum (peaks = periodic interpolation)": _spectrum_image(spec)}
        flagged_pct = 0.0
        if min(h, w) >= WIN:
            stride = window_stride(h, w)
            grid = window_statistics(gray, jpeg, stride)
            flagged = grid >= WIN_THRESHOLD
            flagged_pct = float(100 * flagged.mean())
            heat = _heatmap(grid, (h, w), stride)
            mask = _heatmap(flagged.astype(np.float32), (h, w), stride)
            details["window_stride"] = stride
            step = max(1, int(np.ceil(max(h, w) / 1200)))
            images["Window peak ratio (brighter = stronger periodicity)"] = \
                to_uint8(heat[::step, ::step])
            images["Windows above threshold (red)"] = overlay_mask(
                gray[::step, ::step], mask[::step, ::step])
            details["window_grid"] = grid.round(2).tolist()
            if flagged.any() and not detected:
                findings.append(("notice",
                                 f"{flagged.sum()} of {flagged.size} {WIN}x{WIN} windows "
                                 f"show resampling periodicity (red): a locally rescaled "
                                 f"or rotated region is possible there."))
        if not findings:
            findings.append(("info",
                             "Tested for periodic interpolation correlations (global and "
                             f"per {WIN}x{WIN} window) and pixel duplication: no "
                             "inconsistency found at this sensitivity."))
        if jpeg:
            findings.append(("info", "JPEG grid present: 8x8 lattice frequencies were "
                                     "masked before the peak search."))

        metrics = {
            "Peak ratio (x local background)": round(ratio, 2),
            "Detection threshold (ratio)": THRESHOLD,
            "Peak frequency (vertical, horizontal) cycles/px": f"{fy:+.3f}, {fx:+.3f}",
            "Projection peak ratio (x local background)": round(pr, 2),
            "Projection threshold (ratio)": PROJ_THRESHOLD,
            "Projection peak frequency (cycles/px)": f"{pf:.3f} ({paxis})",
            "Duplicated columns (%)": round(100 * dup_cols, 2),
            "Duplicated rows (%)": round(100 * dup_rows, 2),
            "Windows above threshold (%)": round(flagged_pct, 1),
        }
        details.update({
            "resampling_detected": bool(detected), "nearest_neighbour": bool(nn),
            "peak_ratio": ratio, "peak_frequency": [fy, fx],
            "kirchner_detected": bool(kir_hit), "projection_detected": bool(proj_hit),
            "projection_ratio": pr, "projection_frequency": pf,
            "projection_axis": paxis, "projection_scale_candidates": pcands,
            "scale_candidates": cands, "rotation_deg": rot,
            "duplication_rate": [dup_cols, dup_rows], "jpeg_notch": bool(jpeg),
            "grid_strength": float(grid_strength), "flagged_windows_pct": flagged_pct,
        })
        return make_result(
            "ok",
            f"Measured interpolation periodicity in the {w}x{h} px image "
            f"(Kirchner p-map spectrum, derivative projections) and exact "
            f"row/column duplication.",
            findings, metrics, images, limitations=LIMITATIONS, details=details)
    except Exception as e:  # noqa: BLE001
        return error_result(e, LIMITATIONS)
