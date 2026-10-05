"""
Double-JPEG tampering localization.

Method: T. Bianchi and A. Piva, "Image Forgery Localization via Block-Grained
Analysis of JPEG Artifacts", IEEE Trans. Information Forensics and Security
7(3), 2012.

When a JPEG (primary quantization Q1) is edited and saved again (Q2), the
untouched areas are quantized twice while a region pasted from elsewhere is,
on the file's grid, quantized only once. For each low DCT frequency:

Aligned case (A-DJPG, primary grid = file grid). The file's DCT coefficients
are recovered from the decoded luminance (no YCbCr->RGB round trip) by an
8x8 DCT; x = round(c / Q2) with the stored luminance table Q2. The
unquantized coefficient density is estimated from the image itself on a
grid shifted by (4, 4) px (calibration). Following the paper's full model,
a doubly-quantized coefficient is Q1 k + e, with e the rounding/truncation
error of the first decompression (Gaussian, variance s2), quantized with Q2:
    p(x | H0) = sum_k P(Q1 cell k) * P(Q2 (x-1/2) <= Q1 k + e < Q2 (x+1/2)),
while a singly-quantized (tampered) block follows p(x | H1) = the
calibrated density in Q2 bins. Q1 is not fitted per frequency: one IJG
primary quality (1-100, its whole luminance table) and s2 are chosen by
maximum likelihood jointly over all analysed frequencies, the mixture
weight per frequency by EM. A frequency counts as double-compressed when
the model gain per coefficient exceeds GAIN_MIN. Only non-zero coefficients
enter the fit and the per-block score log L = sum_f log p1(x_f)/p0(x_f),
and only blocks with >= MIN_NZ non-zero AC coefficients vote (flat blocks
carry no lattice evidence; the hard n(x) model scored any odd coefficient
of a smooth block as tampered when Q1 = 2 Q2).

Non-aligned case (NA-DJPG: image cropped/shifted between the two saves). The
primary grid shift is searched over the 49 offsets with dy, dx both non-zero
(see find_nonaligned_shift for why axis-aligned shifts are skipped) with an
integer-periodicity measure (Bianchi & Piva, "Detection of Nonaligned Double
JPEG Compression Based on Integer Periodicity Maps", TIFS 2012): on the right
shift the DCT coefficients cluster on multiples of Q1. There, H0 is modelled
as Q1-lattice + Gaussian noise of the second compression and H1 as the
calibrated unquantized density, as in the 2012 localization paper.

Blind spots: primary quality >= final quality (Q1 <= Q2). Q1 = Q2 and Q1
dividing Q2 leave no trace by construction; other Q1 < Q2 leave only a weak
trace that this model does not pick up (95->75, 90->70: no trace found).
Primary tables that are not IJG-scaled are matched to the nearest IJG table.
"""
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter1d, label, median_filter
from scipy.special import ndtr

from analysis.quant_table import estimate_jpeg_quality, ijg_table
from analysis.util import error_result, make_result, overlay_mask

# JPEG zig-zag order as (row, col); frequencies analysed = first AC terms.
ZIGZAG = sorted(((i, j) for i in range(8) for j in range(8)),
                key=lambda p: (p[0] + p[1], -p[0] if (p[0] + p[1]) % 2 == 0 else p[0]))
FREQS = ZIGZAG[1:10]

HIST_R = 60             # coefficient indices |x| <= HIST_R enter the EM
NZB = np.arange(2 * HIST_R + 1) != HIST_R   # all bins but x = 0
# Variance (coefficient units) of the rounding/truncation error between the
# two quantizations, fitted per image over this grid. Measured on decoded
# luma: ~0.08 (q98) .. 0.14 (q90) .. 0.33 (q70) .. 0.5 (q50) per decode.
S2_GRID = (0.1, 0.2, 0.35, 0.6, 1.0)
LLR_CLIP = 7.0          # per-coefficient |log LR| cap
MIN_NZ = 4              # non-zero quantized AC coefs a block needs to vote
# Minimum log-likelihood gain per coefficient for a frequency to count as
# double-compressed. Calibration set: weak q80->85 frequencies 0.05-0.2;
# single-compressed files reach 0.16 on a few frequencies, which the
# MIN_FREQS_FOR_MAP gate below keeps out of the findings.
GAIN_MIN = 0.05
NA_GAIN_MIN = 0.02      # NA path only runs after the shift test below passed
# Robust z of the best grid shift. Negatives (single + aligned double, 50
# files): max 6.3; non-aligned positives: 7/10 above 8 (misses q1=80->85).
NA_Z_MIN = 8.0
MEDIAN_SIZE = 5         # blocks; median filter on the log-likelihood map
MIN_BLOCKS = 16 * 16    # below this the histograms are too thin
# Warn when the largest connected p>0.5 region covers this share of blocks.
# Calibration set (8 hosts incl. camera-pipeline, seed 11): unspliced
# aligned double JPEG (70->90, 85->95, 90->95, 80->85, 60->75, 75->92) max
# 0.039, non-aligned unspliced max 0.015; spliced 1/9-area regions 0.014-0.16
# (median 0.12). Hold-out: Descriptions/Quantization.md.
WARN_REGION = 0.045
# ...and only when most frequencies show the trace: with weak evidence
# (e.g. q1=80 -> q2=85, 3-5 of 9 frequencies) the map is noise; one such
# unspliced file produced a 30 % false region.
MIN_FREQS_FOR_MAP = 6

LIMITATIONS = [
    "Blind when the earlier save had equal or higher quality than the last "
    "one (Q1 ≤ Q2): Q1 = Q2 or Q1 dividing Q2 leaves no trace, other Q1 < Q2 "
    "only a weak one this model does not use. Close qualities (e.g. 80→85) "
    "give a weak, partial map.",
    "The primary table is assumed to be an IJG-scaled table (most software); "
    "camera vendor tables are matched to the nearest IJG quality, which can "
    "lose frequencies.",
    "A pasted region is found only if it carries a different compression "
    "history on the file's grid; content pasted from another JPEG with the "
    "same grid and quality looks untouched.",
    "Flat or saturated areas have all-zero coefficients and carry no "
    "evidence; they are reported as consistent with the rest.",
    "Resizing, rotation or strong filtering after the first save erases the "
    "primary quantization trace.",
    "Resolution is one 8×8 block; regions smaller than ~5×5 blocks are "
    "suppressed by the median filter.",
]

_C = np.array([[np.sqrt((1 if k == 0 else 2) / 8) * np.cos((2 * n + 1) * k * np.pi / 16)
                for n in range(8)] for k in range(8)])
_C32 = _C.astype(np.float32)


def _luma_and_q2(path):
    """Decoded luminance exactly as stored (no RGB round trip) + luma table."""
    with Image.open(path) as im:
        if im.format != "JPEG":
            return None, None, im.format
        qt = getattr(im, "quantization", None) or {}
        if 0 not in qt:
            return None, None, "JPEG"
        if im.mode != "L":
            im.draft("YCbCr", im.size)
        a = np.asarray(im)
        y = a if a.ndim == 2 else (a[..., 0] if im.mode == "YCbCr"
                                   else np.asarray(im.convert("L")))
        return y.astype(np.float32), np.array(qt[0], float).reshape(8, 8), "JPEG"


def block_dct(y, dy=0, dx=0):
    """8x8 orthonormal DCT (the JPEG FDCT) of y[dy:, dx:], level-shifted.
    Returns (H/8, W/8, 8, 8)."""
    y = y[dy:, dx:]
    h, w = y.shape[0] // 8, y.shape[1] // 8
    b = (y[:h * 8, :w * 8] - 128.0).reshape(h, 8, w, 8).transpose(0, 2, 1, 3)
    return _C32 @ b @ _C32.T


def _em_alpha(counts, h0, p1, iters=60):
    """EM for the mixture weight a of alpha*h0 + (1-alpha)*p1 on binned data.
    Returns (alpha, log-likelihood gain over the pure p1 model)."""
    a = 0.5
    tot = counts.sum()
    for _ in range(iters):
        mix = a * h0 + (1 - a) * p1
        a = float((counts * a * h0 / mix).sum() / tot)
        a = min(max(a, 1e-4), 1 - 1e-4)
    ll = (counts * np.log(a * h0 + (1 - a) * p1)).sum()
    return a, float(ll - (counts * np.log(p1)).sum())


def lattice_hist(c, q1, edges, s2):
    """H0 histogram over `edges` of coefficients first quantized with step
    q1, then perturbed by Gaussian rounding/truncation error of variance s2
    (Bianchi & Piva 2012, eq. for p(x|H0) with the error term). c: samples of
    the unquantized coefficient (from the calibrated grid)."""
    k = np.round(c / q1).astype(np.int64)
    w = np.bincount(k - k.min()).astype(float)
    lat = (np.arange(w.size) + k.min()) * q1
    keep = (w > 0) & (lat > edges[0] - 6) & (lat < edges[-1] + 6)
    if not keep.any():
        return np.full(edges.size - 1, 1.0 / (edges.size - 1))
    z = (edges[None, :] - lat[keep, None]) / np.sqrt(s2)
    p = w[keep] @ np.diff(ndtr(z), axis=1)
    return np.maximum(p / max(p.sum(), 1e-12), 1e-9)


def _aligned(d, dcal, q2, vote):
    """A-DJPG. One IJG primary quality q1 (hence one Q1 table) and one
    error variance are fitted jointly over all FREQS by maximum likelihood,
    so a single frequency cannot pick an incidental lattice. Fit and
    per-block score use non-zero coefficients only (the zero bin is
    dominated by flat blocks); blocks with fewer than MIN_NZ non-zero AC
    coefficients do not vote."""
    R = HIST_R
    rows, used = [], []
    data = []
    for u, v in FREQS:
        qq = float(q2[u, v])
        x = np.clip(np.round(d[..., u, v].ravel() / qq), -R, R).astype(np.int64)
        c = dcal[..., u, v].ravel().astype(np.float64)
        edges = qq * (np.arange(-R, R + 2) - 0.5)
        edges[0], edges[-1] = -np.inf, np.inf
        cnt = np.bincount(x[vote.ravel()] + R, minlength=2 * R + 1)[NZB].astype(float)
        p1 = (np.histogram(c, edges)[0] + 0.5)[NZB]
        # p0 needs only the density shape: a fixed subsample bounds the cost
        data.append((x, c[::max(1, c.size // 40000)], edges, cnt, p1 / p1.sum()))

    def fit(q1, s2):
        t1 = ijg_table(q1, 0).reshape(8, 8)
        tot, res = 0.0, []
        for f, (u, v) in enumerate(FREQS):
            a1, qq = int(t1[u, v]), int(q2[u, v])
            if qq % a1 == 0:
                res.append(None)  # Q1 = Q2 or Q1 | Q2: no trace
                continue
            x, c, edges, cnt, p1 = data[f]
            p0 = lattice_hist(c, a1, edges, s2)[NZB]
            p0 = np.maximum(p0 / p0.sum(), 1e-9)
            a, g = _em_alpha(cnt, p0, p1)
            tot += g
            res.append((g / max(cnt.sum(), 1), a, p0))
        return tot, res

    # q1 by ML at a typical error variance, then the variance for that q1
    cands, seen = [], set()
    for q1 in range(1, 101):
        t1 = ijg_table(q1, 0).reshape(8, 8)
        key = tuple(int(t1[u, v]) for u, v in FREQS)
        if key not in seen:
            seen.add(key)
            cands.append(q1)
    q1 = max(cands, key=lambda q: fit(q, S2_GRID[1])[0])
    s2 = max(S2_GRID, key=lambda v: fit(q1, v)[0])
    tot, res = fit(q1, s2)
    if tot <= 0:
        res = []
    llr = np.zeros(data[0][0].shape)
    for f, (u, v) in enumerate(FREQS):
        r = res[f] if res else None
        ok = r is not None and r[0] >= GAIN_MIN
        rows.append({"frequency (u,v)": f"({u},{v})", "Q2": int(q2[u, v]),
                     "estimated Q1": int(ijg_table(q1, 0)[u * 8 + v]) if ok else "-",
                     "untampered weight": round(r[1], 3) if ok else "-",
                     "gain per coef": round(r[0], 4) if r else 0.0})
        if ok:
            used.append(f)
            x, p1 = data[f][0], data[f][4]
            l = np.zeros(2 * R + 1)
            l[NZB] = np.clip(np.log(p1 / r[2]), -LLR_CLIP, LLR_CLIP)
            llr += l[x + R]
    llr[~vote.ravel()] = 0.0
    return (llr if used else None), rows, len(used), q1, s2


def find_nonaligned_shift(y, qmax=24, max_blocks=3000):
    """Integer-periodicity search over the 49 grid shifts with dy, dx != 0:
    |E exp(2*pi*i*y/Q)| per frequency and Q on a fixed block subsample.
    Returns (dy, dx, robust_z, per-frequency Q1 estimates)."""
    hb, wb = (y.shape[0] - 8) // 8, (y.shape[1] - 8) // 8
    idx = np.arange(hb * wb)[::max(1, hb * wb // max_blocks)]
    by, bx = 8 * (idx // wb), 8 * (idx % wb)
    off = np.arange(8)
    cu = _C[[u for u, _ in FREQS]]
    cv = _C[[v for _, v in FREQS]]
    qs = np.arange(2, qmax + 1)
    # Shifts keeping one axis aligned (dy=0 or dx=0) are skipped: there the
    # final compression's sparse blocks alone make the coefficients a scaled
    # Q2 lattice, which fired on 40 % of single-compressed q70-80 files.
    shifts = [(dy, dx) for dy in range(1, 8) for dx in range(1, 8)]
    P = []
    for dy, dx in shifts:
        b = y[(by + dy)[:, None, None] + off[None, :, None],
              (bx + dx)[:, None, None] + off[None, None, :]] - 128.0
        c = np.einsum("nij,fi,fj->nf", b, cu, cv)       # (N, F)
        ang = (2 * np.pi * c[:, :, None] / qs).astype(np.float32)
        # only coefficients off the zero cell: partially aligned shifts turn
        # flat JPEG blocks into exact zeros, which look "periodic" at every Q
        m = np.abs(c[:, :, None]) >= qs / 2
        n = np.maximum(m.sum(0), 1)
        P.append(np.hypot((np.cos(ang) * m).sum(0) / n, (np.sin(ang) * m).sum(0) / n))
    P = np.array(P)                      # (49, F, Q)
    exc = P - np.median(P, axis=0)       # excess over the unquantized baseline
    E = exc.max(axis=2).sum(axis=1)
    i = int(np.argmax(E))
    others = np.delete(E, i)
    mad = 1.4826 * np.median(np.abs(others - np.median(others)))
    z = float((E[i] - np.median(others)) / max(mad, 1e-9))
    # divisors of Q1 are also lattice-periodic; take the largest near-max Q
    q1s = [int(qs[np.nonzero(e >= 0.8 * e.max())[0].max() if e.max() > 0
                  else np.argmax(e)]) for e in exc[i]]
    return shifts[i][0], shifts[i][1], z, q1s


def _nonaligned(y, dy, dx, q1s, q2):
    """NA-DJPG likelihood at the primary grid shift (dy, dx)."""
    d = block_dct(y, dy, dx)
    cal = block_dct(y, (dy + 4) % 8, (dx + 4) % 8)
    # Variance of the second-compression error as seen on a misaligned grid:
    # the mean over frequencies of the Q2 rounding error, measured on the
    # calibration coefficients, plus pixel rounding (1/12).
    c = cal.reshape(-1, 64)
    s2 = float(np.mean((c - q2.ravel() * np.round(c / q2.ravel())) ** 2) + 1 / 12.0)
    edges = np.arange(-HIST_R * 8 - 0.5, HIST_R * 8 + 1.5)  # unit bins
    centers = (edges[:-1] + edges[1:]) / 2
    H, W = min(d.shape[0], cal.shape[0]), min(d.shape[1], cal.shape[1])
    llr = np.zeros((H * W, len(FREQS)))
    rows, used = [], []
    for f, (u, v) in enumerate(FREQS):
        yf = d[:H, :W, u, v].ravel()
        p1 = gaussian_filter1d(np.histogram(cal[..., u, v].ravel(), edges)[0]
                               .astype(float), 1.0) + 1e-3
        p1 = p1 / p1.sum()
        q1 = q1s[f]
        k = np.round(centers / q1)
        w = np.bincount((k - k.min()).astype(int), weights=p1)  # mass per cell
        ks = np.arange(w.size) + k.min()
        g = np.exp(-(centers[:, None] - ks[None, :] * q1) ** 2 / (2 * s2))
        p0 = (g * w).sum(axis=1)
        p0 = np.maximum(p0 / p0.sum(), 1e-9)
        idx = np.clip(np.searchsorted(edges, yf) - 1, 0, centers.size - 1)
        counts = np.bincount(idx, minlength=centers.size).astype(float)
        a, gain = _em_alpha(counts, p0, p1)
        gain /= max(yf.size, 1)
        ok = gain >= NA_GAIN_MIN
        rows.append({"frequency (u,v)": f"({u},{v})", "Q2": int(q2[u, v]),
                     "estimated Q1": q1 if ok else "-",
                     "untampered weight": round(a, 3) if ok else "-",
                     "gain per coef": round(gain, 4)})
        if ok:
            used.append(f)
            llr[:, f] = np.clip(np.log(p1[idx] / p0[idx]), -LLR_CLIP, LLR_CLIP)
    s = llr[:, used].sum(axis=1).reshape(H, W) if used else None
    return s, rows, len(used)


def analyze_double_jpeg(image_path):
    """
    Returns the shared result contract. Metrics:
        "Blocks with p(tampered)>0.5 (%)", "Frequencies with double-JPEG
        evidence", "Model" (aligned / non-aligned / none),
        "Primary grid shift (dy,dx)", "Non-aligned search z".
    Images: probability overlay, thresholded mask overlay (when evidence).
    Tables: per-frequency Q2, estimated Q1, mixture weight, likelihood gain.
    details: "prob_map" (list of lists, per 8x8 block), "fraction", "model".
    """
    try:
        y, q2, fmt = _luma_and_q2(image_path)
        if fmt != "JPEG":
            return make_result(
                "not_applicable", f"{fmt or 'This'} file is not a JPEG.",
                [("info", "Double-JPEG analysis needs the file's own JPEG "
                          "coefficients and quantization table.")],
                limitations=LIMITATIONS)
        if y is None:
            return make_result("insufficient_data", "No luminance table found.",
                               limitations=LIMITATIONS)
        nb = (y.shape[0] // 8) * (y.shape[1] // 8)
        if nb < MIN_BLOCKS or y.std() < 1.0:
            return make_result(
                "insufficient_data",
                f"Only {nb} 8×8 blocks (need {MIN_BLOCKS}) or no texture.",
                [("info", "Too little data for coefficient histograms.")],
                metrics={"8×8 blocks": nb}, limitations=LIMITATIONS)

        d = block_dct(y)
        hb, wb = d.shape[:2]
        nz = (np.abs(d / q2.astype(np.float32)) >= 0.5).reshape(hb, wb, 64)[..., 1:].sum(-1)
        informative = nz >= MIN_NZ
        q1_est, s2_est = None, None

        dy, dx, z, q1s = find_nonaligned_shift(y)
        if z >= NA_Z_MIN:
            model = "non-aligned"
            del d
            s, rows, nf = _nonaligned(y, dy, dx, q1s, q2)
            if s is not None:
                # the shifted grid lost the first dy/dx rows/cols; pad back
                full = np.zeros((hb, wb))
                full[:s.shape[0], :s.shape[1]] = s
                s = full
        else:
            model = "aligned"
            s, rows, nf, q1_est, s2_est = _aligned(d, block_dct(y, 4, 4), q2, informative)
            del d
            if s is not None:
                s = s.reshape(hb, wb)

        q2_q = estimate_jpeg_quality(q2.ravel(), 0)
        metrics = {"Final quality (IJG est.)": q2_q,
                   "Estimated primary quality (IJG)": q1_est if q1_est and s is not None else "-",
                   "Non-aligned search z": round(float(np.clip(z, -1e6, 1e6)), 2),
                   "Primary grid shift (dy,dx)": f"({dy},{dx})" if model == "non-aligned" else "(0,0)"}
        tables = {"Per-frequency estimates": rows}
        limitations = LIMITATIONS
        if s is None:
            metrics.update({"Model": "none", "Frequencies with double-JPEG evidence": 0,
                            "Blocks with p(tampered)>0.5 (%)": 0.0})
            return make_result(
                "ok",
                f"Tested {len(FREQS)} DCT frequencies for an earlier "
                f"({model}) JPEG compression; none showed its trace.",
                [("info", "No double-compression trace in the tested "
                          "frequencies at this sensitivity: the file looks "
                          "singly compressed, or the earlier save used equal "
                          "or finer quantization (method blind there). No "
                          "localization is possible.")],
                metrics, tables=tables, limitations=limitations,
                details={"model": "none", "fraction": 0.0, "region": 0.0, "prob_map": None,
                         "na_z": float(z), "na_shift": [dy, dx]})

        s = median_filter(s, size=MEDIAN_SIZE, mode="nearest")
        p = 1.0 / (1.0 + np.exp(-np.clip(s, -50, 50)))
        tampered = (p > 0.5) & informative
        frac = float(tampered.sum() / max(informative.sum(), 1))
        lab, ncomp = label(tampered, structure=np.ones((3, 3)))
        sizes = np.bincount(lab.ravel())[1:] if ncomp else np.zeros(1, int)
        region = float(sizes.max() / tampered.size)
        metrics.update({"Model": model, "Frequencies with double-JPEG evidence": nf,
                        "Blocks with p(tampered)>0.5 (%)": round(100 * frac, 2),
                        "Largest inconsistent region (% of blocks)": round(100 * region, 2)})
        where = (f"{model} grid" + (f", primary grid shifted by ({dy},{dx}) px — "
                                    "the image was cropped or shifted between saves"
                                    if model == "non-aligned" else
                                    f", earlier quality ≈ {q1_est}"))
        if nf < MIN_FREQS_FOR_MAP:
            findings = [(
                "notice",
                f"Weak double-compression evidence in only {nf}/{len(FREQS)} "
                f"frequencies ({where}): either a weak double compression "
                "(close first and last qualities) or a chance fit on a singly "
                "compressed file. The block map is unreliable and is not used "
                "for a finding.")]
        else:
            findings = [("info", f"Trace of an earlier JPEG compression found in "
                                 f"{nf}/{len(FREQS)} frequencies ({where}).")]
        if nf < MIN_FREQS_FOR_MAP:
            pass  # notice above; no map-based finding
        elif region >= WARN_REGION:
            ys, xs = np.nonzero(lab == int(np.argmax(sizes)) + 1)
            findings.append((
                "warning",
                f"A connected region of {100 * region:.1f}% of the blocks "
                "(rows {0}–{1}, columns {2}–{3} px) does not follow the "
                "double-compression pattern of the rest (probability > 0.5): "
                "it was compressed only once on this grid (e.g. pasted in, "
                "or re-rendered).".format(8 * ys.min(), 8 * ys.max() + 7,
                                          8 * xs.min(), 8 * xs.max() + 7)))
        else:
            findings.append(("info", "Double-compression pattern is consistent "
                                     "across the informative blocks; no "
                                     "inconsistent region at this sensitivity."))

        # display at block resolution x k, at most ~1200 px
        k = max(1, min(8, 1200 // max(hb, wb)))
        base = np.asarray(Image.fromarray(np.clip(y[:hb * 8, :wb * 8], 0, 255)
                                          .astype(np.uint8)).resize((wb * k, hb * k)))
        up = lambda a: np.kron(a, np.ones((k, k)))  # noqa: E731
        images = {"Probability of single compression (red = high)": overlay_mask(base, up(p), alpha=0.6),
                  "Blocks with p > 0.5 after median filter": overlay_mask(base, up(tampered))}
        return make_result(
            "ok",
            f"Per-block double-JPEG likelihood map ({model} model) over "
            f"{nf} DCT frequencies.",
            findings, metrics, images, tables, limitations,
            details={"model": model, "fraction": frac, "region": region,
                     "prob_map": np.round(p, 4).tolist(),
                     "na_z": float(z), "na_shift": [dy, dx]})
    except Exception as e:  # noqa: BLE001
        return error_result(e, LIMITATIONS)
