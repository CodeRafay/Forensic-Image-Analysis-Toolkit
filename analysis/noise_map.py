"""
Local noise-residual consistency: Splicebuster.

D. Cozzolino, G. Poggi, L. Verdoliva, "Splicebuster: a new blind image
splicing detector", IEEE WIFS 2015.

Every camera/processing chain (sensor noise, demosaicing, sharpening, JPEG
history) leaves a characteristic texture in the high-pass residual. The
method, on luma at full resolution:

1. Third-order residuals r = -x[i] + 3x[i+1] - 3x[i+2] + x[i+3], horizontal
   and vertical.
2. Quantise with step Q and truncate to [-T, T].
3. Co-occurrence of 4 adjacent residual samples along the residual's own
   direction: one of (2T+1)^4 codes per pixel. Horizontal and vertical
   counts are pooled.
4. Local features: code histogram over WIN x WIN windows (paper: 128 px)
   at a stride of 8 px, or 16/32 px when that would exceed 50k windows
   (12 MP: 16 px). Window histograms are summed from per-cell histograms
   (integral-histogram trick), normalised and square-rooted.
5. PCA to D = 25 dimensions.
6. EM for a two-class Gaussian-Gaussian mixture (the paper's variant for
   larger forgeries; its Gaussian-uniform variant separated the
   calibration splices worse: mean window AUC 0.69 vs 0.94). Heat map =
   log-likelihood ratio minority/majority class; candidate region = windows
   whose minority posterior is > 0.5.

Deviations from the paper: T = 1 instead of 2 (see Q, T) and the
image-level decision below (the paper only outputs the heat map).
"""
import numpy as np
from scipy import ndimage

from analysis.util import error_result, fig_to_array, load_array, make_result, overlay_mask

# Paper: T = 2 (625 bins). On the calibration splices T = 1 (81 bins) with
# Q = 2 separated far better (mean window AUC 0.94 vs 0.72 for Q=1, T=2).
Q, T = 2.0, 1
WIN = 128               # feature window (px), paper value
D = 25                  # PCA dimensions, paper value
EM_ITERS = 30
MIN_SIDE = 256          # need a few windows per side
MIN_WINDOWS = 64
DARK, BRIGHT = 8, 247   # windows whose mean luma is outside are skipped
# Decision (our addition): the largest connected minority region is reported
# when it covers REGION_MIN..REGION_MAX of the usable windows, holds >=
# COMPACT_MIN of all minority windows (a splice is one blob; content-driven
# clusters are scattered) and its median log-likelihood ratio is >= LLR_MIN.
# Chosen on the calibration set for <= 4 % false alarms; hold-out numbers in
# Descriptions/Noise_Ghost.md.
# Hold-out (7 photos not used for calibration, other seeds; camera-like
# pipeline + plain photos + reviewer's 48 files): false alarms 7/132 (5.3 %;
# 4 of them the same flat-background photo, skimage 'clock'); splices of
# another photo/camera chain/JPEG history, 1/16-1/4 area, saved PNG / q75 /
# q85 / q92: 38/56 (68 %), mean pixel F1 0.50. The old Lyu kurtosis method
# on the same set: 0/132, 2/56, F1 0.01 (it abstained on 28/42 camera JPEGs).
REGION_MIN, REGION_MAX = 0.05, 0.3
COMPACT_MIN = 0.95
LLR_MIN = 5.0

LIMITATIONS = [
    "Sees regions whose noise residual texture (camera noise, demosaicing, "
    "sharpening, compression) differs from the rest; a region from the same "
    "camera and settings, or re-processed to match, is invisible.",
    "Resizing, denoising or strong JPEG compression of the whole image "
    "after the edit flattens the residual and weakens the contrast.",
    "Content changes the residual too: large saturated, very dark, flat or "
    "heavily textured areas (sky, shadows, foliage) can form a separate "
    "cluster on an untouched image.",
    "Resolution is one 128-px window; regions much smaller than that are "
    "not resolved, and region borders are blurred by about half a window.",
    "The model assumes one dominant 'pristine' class; a splice covering "
    "half the image or more cannot be told apart from the host.",
]


def _codes(x):
    """(2T+1)^4-level co-occurrence codes of the quantised 3rd-order
    residual along axis 1 of x (float32). Returns uint16, shape (H, W - 6)."""
    r = (x[:, 3:] - x[:, :-3]) + 3 * (x[:, 1:-2] - x[:, 2:-1])
    r = np.clip(np.rint(r / Q), -T, T).astype(np.int16) + T
    n = 2 * T + 1
    return (r[:, :-3] + n * r[:, 1:-2] + n * n * r[:, 2:-1] + n ** 3 * r[:, 3:]).astype(np.uint16)


def _stride(h, w):
    """Smallest stride (cell size) in 8/16/32 px with at most 50k windows."""
    for s in (8, 16, 32):
        if ((h - WIN) // s + 1) * ((w - WIN) // s + 1) <= 50000:
            return s
    return 64


def cell_histograms(gray, s):
    """Pooled H+V co-occurrence histograms per s x s cell, uint16
    (rows, cols, (2T+1)^4). Cell grid starts at pixel (3, 3)."""
    ch = _codes(gray)[3:-3]            # horizontal: rows 3..H-4 -> align
    cv = _codes(gray.T).T[:, 3:-3]     # vertical
    h, w = ch.shape
    nr, nc = h // s, w // s
    nb = (2 * T + 1) ** 4
    out = np.zeros((nr, nc, nb), np.uint16)
    col = (np.arange(nc * s) // s * nb)[None, :]
    for i in range(nr):
        for c in (ch, cv):
            band = c[i * s:(i + 1) * s, :nc * s].astype(np.int32) + col
            out[i] += np.bincount(band.ravel(), minlength=nc * nb).reshape(nc, nb).astype(np.uint16)
    return out


def _box(c, k, dtype):
    """Sum over k x k neighbourhoods of the leading two axes ('valid')."""
    c = np.cumsum(np.cumsum(c, 0, dtype=dtype), 1, dtype=dtype)
    c = np.pad(c, ((1, 0), (1, 0)) + ((0, 0),) * (c.ndim - 2))
    return c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]


def window_features(cells, k):
    """Window histograms from k x k cells, normalised, square-rooted."""
    f = _box(cells, k, np.int32).astype(np.float32)
    f /= np.maximum(f.sum(axis=2, keepdims=True), 1)
    return np.sqrt(f, out=f)


def _gauss_ll(z, w):
    """Weighted Gaussian fit; returns (log-likelihood per sample, m2)."""
    mu = (w[:, None] * z).sum(0) / max(w.sum(), 1e-9)
    xc = z - mu
    S = (w[:, None] * xc).T @ xc / max(w.sum(), 1e-9) + 1e-4 * np.eye(z.shape[1])
    L = np.linalg.cholesky(S)
    m2 = np.sum(np.linalg.solve(L, xc.T) ** 2, axis=0)
    return -0.5 * m2 - np.sum(np.log(np.diag(L))), m2


def gaussian_gaussian_em(z, iters=EM_ITERS):
    """EM for a two-Gaussian mixture. Initialised with the 10 % of windows
    farthest (Mahalanobis) from a single Gaussian fit. Returns (posterior of
    the minority class, log-likelihood ratio minority/majority)."""
    _, m2 = _gauss_ll(z, np.ones(len(z)))
    w1 = (m2 > np.quantile(m2, 0.9)).astype(np.float64)
    for _ in range(iters):
        l0, _ = _gauss_ll(z, 1 - w1)
        l1, _ = _gauss_ll(z, w1)
        pi = np.clip(w1.mean(), 1e-3, 1 - 1e-3)
        llr = l1 - l0
        w1 = 1.0 / (1.0 + np.exp(np.clip(-(llr + np.log(pi / (1 - pi))), -50, 50)))
    if w1.mean() > 0.5:
        w1, llr = 1 - w1, -llr
    return w1, llr


def splicebuster(gray):
    """Returns dict with window maps 'heat' (log-likelihood ratio), 'post'
    (minority posterior), 'valid', the stride s and window size k in cells."""
    gray = np.asarray(gray, np.float32)
    h, w = gray.shape
    s = _stride(h, w)
    k = WIN // s
    feats = window_features(cell_histograms(gray, s), k)
    nr, nc = feats.shape[:2]
    # mean luma per window, from cell means on the same grid
    R, C = nr + k - 1, nc + k - 1
    m = gray[3:3 + R * s, 3:3 + C * s].reshape(R, s, C, s).mean(axis=(1, 3))
    m = _box(m, k, np.float64) / (k * k)
    valid = (m >= DARK) & (m <= BRIGHT)
    x = feats[valid]
    del feats
    heat = np.zeros((nr, nc))
    post = np.zeros((nr, nc))
    if x.shape[0] >= MIN_WINDOWS:
        x -= x.mean(0)
        _, vec = np.linalg.eigh(x.T @ x)
        z = (x @ vec[:, ::-1][:, :D]).astype(np.float64)
        pu, llr = gaussian_gaussian_em(z)
        heat[valid], post[valid] = llr, pu
    return {"heat": heat, "post": post, "valid": valid, "s": s, "k": k}


def decide(sb):
    """Largest connected minority region and the image-level decision."""
    valid, post, llr = sb["valid"], sb["post"], sb["heat"]
    nv = max(int(valid.sum()), 1)
    out = valid & (post > 0.5)
    lab, n = ndimage.label(out, structure=np.ones((3, 3)))
    if not n:
        return dict(sel=out, out=out, region=0.0, compact=0.0, llr=0.0, flagged=False)
    sizes = np.bincount(lab.ravel())[1:]
    sel = lab == int(np.argmax(sizes)) + 1
    region, compact = sizes.max() / nv, sizes.max() / out.sum()
    m = float(np.median(llr[sel]))
    return dict(sel=sel, out=out, region=float(region), compact=float(compact), llr=m,
                flagged=bool(REGION_MIN <= region <= REGION_MAX and compact >= COMPACT_MIN
                             and m >= LLR_MIN))


def to_pixels(a, s, k, shape):
    """Window map -> pixel map: each window value covers the s x s cell at
    the window centre (pixel origin 3 + (k/2) s)."""
    h, w = shape
    o = 3 + (k // 2) * s - s // 2
    up = np.repeat(np.repeat(a, s, 0), s, 1)
    up = np.pad(up, ((o, max(0, h - o - up.shape[0])), (o, max(0, w - o - up.shape[1]))), mode="edge")
    return up[:h, :w]


def _heat_image(heat, valid):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    hb, wb = heat.shape
    fig, ax = plt.subplots(figsize=(6, 6 * hb / max(wb, 1) + 0.5))
    im = ax.imshow(np.where(valid, heat, np.nan), cmap="inferno")
    ax.set_title("log-likelihood ratio, minority vs majority residual model")
    ax.axis("off")
    fig.colorbar(im, ax=ax, fraction=0.046, label="log-likelihood ratio")
    return fig_to_array(fig)


def analyze_noise(image_path):
    """
    Splicebuster on luma at full resolution. Metrics: usable windows,
    stride, outlier windows, largest candidate region (% of usable windows),
    its mean distance vs the median distance. Images: heat map, candidate
    region overlay. details: "flagged", "region" (share), "stride",
    "heat"/"post" (window maps, lists).
    """
    try:
        gray = load_array(image_path, "L")[0].astype(np.float32)
        h, w = gray.shape
        if min(h, w) < MIN_SIDE or gray[::4, ::4].std() < 1.0:
            return make_result(
                "insufficient_data",
                f"{w}×{h} px is below the {MIN_SIDE} px minimum or has no "
                "texture; Splicebuster needs several 128-px windows.",
                limitations=LIMITATIONS)
        sb = splicebuster(gray)
        heat, post, valid, s, k = sb["heat"], sb["post"], sb["valid"], sb["s"], sb["k"]
        nv = int(valid.sum())
        if nv < MIN_WINDOWS:
            return make_result(
                "insufficient_data",
                f"Only {nv} usable {WIN}-px windows (need {MIN_WINDOWS}); the "
                "rest are too dark or too bright.",
                metrics={"Usable windows": nv}, limitations=LIMITATIONS)
        d = decide(sb)
        sel, region, out = d["sel"], d["region"], d["out"]
        big, flagged = int(sel.sum()), d["flagged"]

        metrics = {
            "Usable windows": nv,
            "Window stride (px)": s,
            "Outlier windows (%)": round(100 * float(out.sum()) / nv, 2),
            "Largest candidate region (% of usable windows)": round(100 * region, 2),
            "Region compactness (share of outlier windows)": round(d["compact"], 3),
            "Region median log-likelihood ratio": round(d["llr"], 2),
        }
        findings = [("info", f"Residual co-occurrence features of {nv} "
                             f"{WIN}×{WIN} windows (stride {s} px) were "
                             "modelled as one dominant source plus outliers.")]
        if flagged:
            ys, xs = np.nonzero(sel)
            o = 3 + (k // 2) * s - s // 2
            findings.append((
                "notice",
                f"A connected region of {big} windows ({100 * region:.1f}% of "
                f"the usable area, rows ≈{o + s * ys.min()}–{o + s * ys.max() + s}, "
                f"columns ≈{o + s * xs.min()}–{o + s * xs.max() + s} px) has a "
                "noise residual that does not fit the rest of the image: "
                "consistent with content from another camera or processing "
                "chain, or with a large area of very different content (sky, "
                "shadow, foliage); check the region visually."))
        else:
            findings.append(("info", "Tested for a region whose noise residual "
                                     "differs from the rest: no inconsistency "
                                     "found at this sensitivity."))
        mask = to_pixels(sel.astype(np.uint8), s, k, (h, w))
        step = max(1, int(np.ceil(max(h, w) / 1200)))
        images = {
            "Splicebuster heat map (minority vs majority residual model)": _heat_image(heat, valid),
            "Candidate region (red)": overlay_mask(gray[::step, ::step], mask[::step, ::step]),
        }
        r4 = lambda a: [[round(float(v), 4) for v in row] for row in a]  # noqa: E731
        return make_result(
            "ok",
            f"Splicebuster residual-consistency analysis of {nv} windows of "
            f"{WIN}×{WIN} px at full resolution.",
            findings, metrics, images, limitations=LIMITATIONS,
            details={"flagged": bool(flagged), "region": float(region),
                     "compact": d["compact"], "llr": d["llr"], "stride": int(s),
                     "heat": r4(heat), "post": r4(post)})
    except Exception as e:  # noqa: BLE001
        return error_result(e, LIMITATIONS)
