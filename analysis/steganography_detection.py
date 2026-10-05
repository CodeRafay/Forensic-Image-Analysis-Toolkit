"""
Quantitative LSB-replacement steganalysis in the pixel domain.

Estimators (each returns p̂ = payload in bits per pixel of one channel,
i.e. the fraction of samples that carry a message bit):

- Weighted Stego (WS): J. Fridrich & M. Goljan, "On estimation of secret
  message length in LSB steganography in spatial domain", SPIE 2004, in the
  improved form of A. Ker & R. Böhme, "Revisiting weighted stego-image
  steganalysis", SPIE 2008 — KB predictor, moderated weights 1/(5+σ²),
  bias correction. Most accurate on ordinary covers; unreliable when most
  pixels are saturated (line art, clipped skies).
- Sample Pairs Analysis (SPA): S. Dumitrescu, X. Wu & Z. Wang, "Detection of
  LSB steganography via sample pair analysis", IEEE TSP 51(7), 2003.
- RS analysis: J. Fridrich, M. Goljan & R. Du, "Reliable detection of LSB
  steganography in color and grayscale images", ACM MM&Sec 2001
  (1x4 groups, mask [0,1,1,0], flips F1/F-1, quadratic in z).
- Pair-of-Values chi-square: A. Westfeld & A. Pfitzmann, "Attacks on
  steganographic systems", IH 1999 — sensitive to *sequential* embedding;
  reported as a cumulative p-value curve over the raster scan.

Decision statistic per channel: min(WS, SPA), or SPA alone when WS is
unreliable (see decision_score); the image score is the highest channel.

All four model LSB *replacement*. LSB matching (±1), and anything hidden in
JPEG DCT coefficients (JSteg, F5, OutGuess, J-UNIWARD), leaves none of the
structure they measure.
"""
import cv2
import numpy as np
from scipy import stats

from analysis import util

# ── Calibrated decision threshold (bpp, on max-channel min(WS, SPA)) ──
# Seeded benchmark (scratchpad calib.py; covers = sampleImg + 14 skimage
# photos): clean lossless covers (PNG, grayscale, bicubic 0.6x, crops; n=53)
# FPR 1.9 % (95th pct 0.041, max 0.116 = resized 'grass'); clean decoded
# JPEG q75/85/95/100 (n=60) FPR 3.3 % (max 0.067). TPR on 23 lossless covers,
# random LSB replacement: 5 % → 70 %, 10 %+ → 100 %; sequential (score or
# PoV finding): 5 % → 87 %, 10 %+ → 100 %; LSB matching 5-100 % → 0-4 %.
THRESHOLD = 0.05
JPEG_FPR = "3.3 % at this threshold, vs 1.9 % for lossless covers"
SEQ_P_THRESHOLD = 0.5        # PoV prefix p-value that counts as "equalised"
SEQ_CONFIRM = 0.5            # prefix rows must read ≥ this (bpp) to confirm
MIN_SIDE = 32
BLOCK = 64

LIMITATIONS = [
    "Models LSB replacement only. LSB matching (±1 embedding) leaves no pair "
    "structure and is not detected by any of these tests.",
    "JPEG steganography (JSteg, F5, OutGuess, J-UNIWARD, ...) hides data in "
    "DCT coefficients; pixel-LSB tests cannot see it.",
    "Payloads below the detection threshold are indistinguishable from the "
    "estimator's own error on clean covers.",
    "Palette images are analysed after conversion to RGB; palette-index "
    "embedding (EzStego) is not modelled.",
    "Only pixel values are examined: metadata, appended bytes and file "
    "structure cannot influence (or be checked by) these tests.",
]


# ── Estimators ────────────────────────────────────────────────────
def _small_root(a, b, c):
    """Root of a x² + b x + c = 0 with the smaller magnitude (real part if
    the discriminant is negative, which happens only from noise near p=0)."""
    if abs(a) < 1e-12:
        return -c / b if abs(b) > 1e-12 else 0.0
    disc = max(b * b - 4 * a * c, 0.0)
    r = [(-b + s * np.sqrt(disc)) / (2 * a) for s in (1, -1)]
    return float(min(r, key=abs))


def spa(x):
    """Sample Pairs Analysis (Dumitrescu et al. 2003), horizontal + vertical
    pairs. With trace sets C_m (|⌊u/2⌋-⌊v/2⌋| = m), D_0 (u = v) and, over
    odd differences 2m+1, X (trace difference m+1) / Y (trace difference m),
    the assumption |X| = |Y| on covers gives
        |C_0| p² - 2(|D_0| + |Y| - |X|) p + 2(|Y| - |X|) = 0.
    """
    x = np.asarray(x, dtype=np.int16)
    u = np.concatenate([x[:, :-1].ravel(), x[:-1, :].ravel()])
    v = np.concatenate([x[:, 1:].ravel(), x[1:, :].ravel()])
    d = np.abs(u - v)
    td = np.abs((u >> 1) - (v >> 1))
    odd = (d & 1) == 1
    c0 = np.count_nonzero(td == 0)
    d0 = np.count_nonzero(d == 0)
    X = np.count_nonzero(odd & (td == (d + 1) // 2))
    Y = np.count_nonzero(odd & (td == (d - 1) // 2))
    return _small_root(c0, -2.0 * (d0 + Y - X), 2.0 * (Y - X))


def _rs_counts(x):
    """(R-S) for mask M=[0,1,1,0] with F1 and F-1 on 1x4 groups."""
    g = x[:, : x.shape[1] // 4 * 4]
    a, b, c, d = (g[:, i::4] for i in range(4))   # int16 views, no reshape copy
    f = np.abs(b - a) + np.abs(c - b) + np.abs(d - c)
    n = f.size

    def rs(flip):
        fb, fc = flip(b), flip(c)
        fh = np.abs(fb - a) + np.abs(fc - fb) + np.abs(d - fc)
        return (np.count_nonzero(fh > f) - np.count_nonzero(fh < f)) / n

    return rs(lambda v: v ^ 1), rs(lambda v: ((v + 1) ^ 1) - 1)


def rs_analysis(x):
    """RS analysis (Fridrich, Goljan & Du 2001). Returns p̂ in bpp."""
    x = np.asarray(x, dtype=np.int16)
    d0, dm0 = _rs_counts(x)          # R_M - S_M, R_-M - S_-M on the image
    d1, dm1 = _rs_counts(x ^ 1)      # same with every LSB flipped
    z = _small_root(2 * (d1 + d0), dm0 - dm1 - d1 - 3 * d0, d0 - dm0)
    return float(z / (z - 0.5)) if abs(z - 0.5) > 1e-9 else 1.0


# Ker & Böhme 2008 predictor: fits the cover from the 8 neighbours.
_KB = np.array([[-1, 2, -1], [2, 0, 2], [-1, 2, -1]], np.float32) / 4.0
_NB = np.array([[1, 1, 1], [1, 0, 1], [1, 1, 1]], np.float32) / 8.0


def _corr(a, k):
    """3x3 correlation, edge-replicated (ndimage mode='nearest'); cv2 is
    ~5x faster than ndimage.correlate on 12 MP float32."""
    return cv2.filter2D(a, cv2.CV_32F, k, borderType=cv2.BORDER_REPLICATE)


def ws_terms(x):
    """Per-pixel WS weights w and residual term r (interior pixels) such that
    p̂ = Σ w r / Σ w, plus the bias-correction term b (same weighting):
    corrected p̂ = p̂_raw / (1 - Σ w b / Σ w)."""
    s = np.asarray(x, dtype=np.float32)
    # s - sbar is +1 for odd, -1 for even samples (sbar = s with LSB flipped)
    sign = (np.asarray(x, dtype=np.int16) & 1).astype(np.float32) * 2 - 1
    pred = _corr(s, _KB)
    mean = _corr(s, _NB)
    var = _corr(s * s, _NB) - mean ** 2
    del mean
    w = 1.0 / (5.0 + np.maximum(var, 0.0))            # moderated weights
    del var
    # Saturated pixels (and their neighbours) break the predictor: a 0 can
    # only move up. Excluding them cut the clean-cover 95th percentile from
    # 0.096 to 0.053 bpp (hubble_deep_field's black sky was the worst case).
    sat = cv2.dilate(((s <= 0) | (s >= 255)).astype(np.uint8), np.ones((3, 3), np.uint8))
    w[sat > 0] = 0.0
    r = 2.0 * sign * (s - pred)
    # Bias from predicting with stego neighbours, which enter the predictor
    # as ±1 LSB flips; the correction is proportional to p̂ (Ker & Böhme
    # 2008 §4). Its sign was checked empirically: on 'moon' at p=0.5 it moves
    # p̂ from 0.70 (uncorrected) to 0.59; the opposite sign gives 0.86.
    b = sign * _corr(-sign, _KB)
    sl = (slice(1, -1), slice(1, -1))
    return w[sl], r[sl], b[sl]


def _ws(sw, swr, swb):
    """WS estimate from the summed terms Σw, Σwr, Σwb."""
    if sw <= 0:
        return 0.0
    k = 1.0 - swb / sw
    return float(swr / sw / k) if abs(k) > 1e-6 else float(swr / sw)


class WSTerms:
    """ws_terms computed once per channel; global, per-row-range and per-block
    estimates are all read from these sums (12 MP: one pass, not three)."""

    def __init__(self, x):
        w, r, b = ws_terms(x)
        self.n = w.size
        self.valid = float(np.count_nonzero(w) / max(w.size, 1))
        wr, wb = w * r, w * b
        # per-row sums (float64) for prefix estimates; block sums for the map
        self.rows = np.stack([w.sum(1, dtype=np.float64), wr.sum(1, dtype=np.float64),
                              wb.sum(1, dtype=np.float64)])
        H, W = (w.shape[0] // BLOCK) * BLOCK, (w.shape[1] // BLOCK) * BLOCK
        if H == 0 or W == 0:
            self.blocks = np.zeros((1, 1))
        else:
            t = lambda a: a[:H, :W].reshape(H // BLOCK, BLOCK, W // BLOCK, BLOCK).sum((1, 3), dtype=np.float64)
            tw = np.maximum(t(w), 1e-12)   # all-saturated tile -> 0
            raw, k = t(wr) / tw, 1.0 - t(wb) / tw
            self.blocks = raw / np.where(np.abs(k) > 1e-6, k, 1.0)

    def estimate(self, r0=0, r1=None):
        """WS on interior rows r0:r1 (row index of the interior array)."""
        return _ws(*self.rows[:, r0:r1].sum(1))


def weighted_stego(x):
    return WSTerms(x).estimate()


def ws_block_map(x):
    """Local WS estimate per BLOCK x BLOCK tile (partial tiles cut)."""
    return WSTerms(x).blocks


# WS is unusable when most pixels are saturated (or their neighbours), as in
# line art and clipped skies: few weights left and the predictor is wrong
# (review: WS -55 at p=0 and -2.5 at p=0.25 on such a cover while SPA read
# 0.28). Then SPA alone decides.
WS_MIN_VALID = 0.5            # share of interior pixels with non-zero weight
WS_RANGE = (-0.5, 1.5)        # WS outside this is a broken fit, not a payload


def decision_score(ws, sp, valid):
    """min(WS, SPA) where WS is trustworthy (a clean texture rarely fools
    both: grass crop WS 0.215, SPA 0.048), else SPA alone. Returns
    (score, rule)."""
    if valid < WS_MIN_VALID or not WS_RANGE[0] <= ws <= WS_RANGE[1]:
        return sp, "SPA (WS unreliable)"
    return min(ws, sp), "min(WS, SPA)"


def channel_score(x):
    t = WSTerms(x)
    return decision_score(t.estimate(), spa(x), t.valid)[0]


def pov_chi_square_test(channel, min_expected=5):
    """
    Westfeld-Pfitzmann Pair-of-Values chi-square test. Pairs (2i, 2i+1) are
    compared with an even split; a HIGH p-value means the pairs are already
    equalised — the signature of LSB replacement at (near) full capacity in
    the tested samples. Natural images give p ≈ 0.

    Returns (chi2, p_value, valid_pairs).
    """
    hist = np.bincount(np.asarray(channel).astype(np.uint8, copy=False).ravel(),
                       minlength=256)[:256].astype(np.float64)
    return _pov_from_hist(hist, min_expected)


def _pov_from_hist(hist, min_expected=5):
    even, odd = hist[0::2], hist[1::2]
    expected = (even + odd) / 2.0
    valid = expected >= min_expected
    n = int(valid.sum())
    if n < 2:
        return 0.0, 0.0, n
    chi2 = float(np.sum((even[valid] - expected[valid]) ** 2 / expected[valid]))
    return chi2, float(stats.chi2.sf(chi2, n - 1)), n


def pov_curve(arr, steps=100):
    """PoV p-value on the first k% of samples in raster order (channels
    interleaved, as sequential embedders write them), k = 1..steps."""
    flat = np.asarray(arr).astype(np.uint8, copy=False).ravel()  # uint8: no 8x int64 copy at 12 MP
    chunks = np.array_split(flat, steps)
    hists = np.cumsum([np.bincount(c, minlength=256)[:256] for c in chunks], 0)
    return np.array([_pov_from_hist(h.astype(float))[1] for h in hists])


# ── Entry point ───────────────────────────────────────────────────
def _plot_curve(curve):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7, 3))
    ax.plot(np.arange(1, len(curve) + 1), curve, lw=1.5)
    ax.axhline(SEQ_P_THRESHOLD, color="grey", ls="--", lw=0.8)
    ax.set_xlabel("first k % of pixels (raster order)")
    ax.set_ylabel("PoV p-value")
    ax.set_ylim(-0.02, 1.02)
    ax.set_title("Pair-of-Values cumulative test (high = pairs equalised)")
    return util.fig_to_array(fig)


def _plot_heatmap(m):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6, 6 * m.shape[0] / max(m.shape[1], 1) + 0.6))
    im = ax.imshow(np.clip(m, 0, 1), cmap="magma", vmin=0, vmax=1,
                   interpolation="nearest")
    ax.set_title(f"Local WS payload, {BLOCK}x{BLOCK} blocks\n"
                 "localisation aid; single blocks are noisy", fontsize=10)
    ax.axis("off")
    fig.colorbar(im, ax=ax, fraction=0.046, label="bpp")
    return util.fig_to_array(fig)


def _sequential_extent(stack, chans, terms, curve):
    """Fraction k of the raster scan over which PoV pairs stay equalised,
    and whether WS/SPA on the rows in that prefix confirm it. Smooth
    histograms (textures, resized images) also keep PoV p high, so the curve
    alone false-alarmed on 24 of 53 clean lossless covers; requiring the
    prefix rows to read as heavily embedded removes that. The prefix must
    also read clearly above the remaining rows, otherwise uniform random
    embedding at ≥50 % would be misdescribed as sequential."""
    above = np.nonzero(curve >= SEQ_P_THRESHOLD)[0]
    k = float((above[-1] + 1) / len(curve)) if above.size else 0.0
    rows = int(k * stack.shape[0])
    if rows < 8:
        return k, 0.0, 0.0, False
    # WS on a row range comes from the precomputed per-row sums (interior
    # row i = image row i+1), SPA is recomputed on the uint8 rows.
    def score(name, sl, r0, r1):
        t = terms[name]
        return decision_score(t.estimate(r0, r1), spa(chans[name][sl]), t.valid)[0]
    local = max(score(n, slice(None, rows), 0, rows - 1) for n in chans)
    rest = (max(score(n, slice(rows, None), rows - 1, None) for n in chans)
            if stack.shape[0] - rows >= 8 else 0.0)
    return k, float(local), float(rest), bool(local > SEQ_CONFIRM and local - rest > 0.25)


def analyze_lsb(image_path):
    """
    Estimate the LSB-replacement payload of an image.

    Returns util.make_result with metrics (decision score and per-channel
    WS / SPA / RS estimates in bpp, threshold, PoV sequential extent), images
    (local WS payload heatmap, PoV cumulative p-value curve), a per-channel
    table, and details (all raw estimates, the PoV curve, the block map).
    """
    try:
        fmt = (util.image_format(image_path) or "").upper()
        arr, _ = util.load_array(image_path, "RGB")   # full resolution
        arr = np.asarray(arr, dtype=np.uint8)
        H, W = arr.shape[:2]
        is_jpeg = fmt in ("JPEG", "MPO")
        gray = bool((arr[..., 0] == arr[..., 1]).all()
                    and (arr[..., 1] == arr[..., 2]).all())
        stack = arr[..., 0] if gray else arr
        chans = ({"gray": arr[..., 0]} if gray else
                 {"red": arr[..., 0], "green": arr[..., 1], "blue": arr[..., 2]})
        if min(H, W) < MIN_SIDE or max(c.std() for c in chans.values()) < 2.0:
            return util.make_result(
                "insufficient_data",
                f"Image is {W}x{H} or nearly uniform; the LSB estimators need "
                f"at least {MIN_SIDE}x{MIN_SIDE} px of non-uniform content.",
                [("info", "Not enough data to estimate an LSB payload.")],
                limitations=LIMITATIONS)

        est, rows, terms = {}, [], {}
        for name, c in chans.items():
            terms[name] = t = WSTerms(c)
            e = {"ws": t.estimate(), "spa": spa(c), "rs": rs_analysis(c),
                 "pov_p": pov_chi_square_test(c)[1], "ws_valid_share": t.valid}
            e["score"], e["rule"] = decision_score(e["ws"], e["spa"], t.valid)
            est[name] = e
            rows.append({"channel": name,
                         "decision score (bpp)": round(e["score"], 4),
                         "rule": e["rule"],
                         "WS (bpp)": round(e["ws"], 4),
                         "SPA (bpp)": round(e["spa"], 4),
                         "RS (bpp)": round(e["rs"], 4),
                         "PoV p-value": round(e["pov_p"], 4)})
        top_name = max(est, key=lambda k: est[k]["score"])
        top = est[top_name]["score"]
        combined = float(np.mean([e["ws"] for e in est.values()]))

        curve = pov_curve(stack)
        seq_k, seq_local, seq_rest, seq_ok = _sequential_extent(stack, chans, terms, curve)
        heat = np.mean([t.blocks for t in terms.values()], axis=0)
        del terms

        findings = []
        if is_jpeg:
            findings.append((
                "info",
                "This is a JPEG. JPEG steganography (JSteg, F5, OutGuess, "
                "J-UNIWARD, ...) hides data in DCT coefficients, which these "
                "pixel-LSB tests cannot see. LSB replacement in pixels does not "
                "survive JPEG saving, so a payload found here would mean the "
                "decoded pixels were edited and the file re-saved losslessly, "
                "which is unusual. JPEG decoding noise also widens the "
                f"estimators' error (clean decoded-JPEG FPR {JPEG_FPR})."))
        if top > THRESHOLD:
            findings.append((
                "warning",
                f"Estimated LSB-replacement payload {top:.3f} bpp in the "
                f"{top_name} channel exceeds the detection threshold "
                f"{THRESHOLD:.3f} bpp calibrated on clean covers; rule "
                f"{est[top_name]['rule']} "
                f"(WS {est[top_name]['ws']:.3f}, SPA {est[top_name]['spa']:.3f}, "
                f"RS {est[top_name]['rs']:.3f} bpp; mean WS over channels "
                f"{combined:.3f} bpp)."))
        else:
            findings.append((
                "info",
                f"Estimated payload {max(top, 0.0):.3f} bpp (highest channel: "
                f"{top_name}), below the detection threshold {THRESHOLD:.3f} "
                "bpp; no inconsistency found at this sensitivity. LSB "
                f"replacement below ~{THRESHOLD:.2f} bpp and LSB matching (±1) "
                "are not detectable with these tests."))
        if seq_ok and seq_k >= 0.98:
            findings.append((
                "warning",
                "Pair-of-Values pairs are equalised across the whole scan "
                f"(p = {curve[-1]:.2f}): consistent with LSB replacement "
                "spread over the whole image (see the payload estimate; at "
                "100 % sequential and random embedding look the same)."))
        elif seq_ok:
            findings.append((
                "warning",
                f"Pair-of-Values p-value stays ≥ {SEQ_P_THRESHOLD} over the "
                f"first {seq_k:.0%} of the raster scan and those rows read as "
                f"{seq_local:.2f} bpp against {seq_rest:.2f} bpp below: the "
                "signature of sequential LSB embedding from the top of the "
                "image."))
        elif seq_k >= 0.02 and seq_local <= SEQ_CONFIRM:
            findings.append((
                "info",
                f"PoV pairs look equalised over the first {seq_k:.0%} of the "
                f"scan, but WS/SPA read only {seq_local:.3f} bpp there — "
                "consistent with a smooth histogram rather than sequential "
                "embedding."))

        metrics = {
            "Payload estimate, highest channel (bpp)": round(top, 4),
            "Mean WS payload over channels (bpp)": round(combined, 4),
            "Detection threshold (bpp)": THRESHOLD,
            "PoV equalised prefix (% of scan)": round(100 * seq_k, 1),
            "PoV p-value, whole image": round(float(curve[-1]), 4),
        }
        return util.make_result(
            "ok",
            f"Estimated the LSB-replacement payload per channel with Weighted "
            f"Stego, Sample Pairs and RS analysis, and ran the Pair-of-Values "
            f"test for sequential embedding ({W}x{H}, {len(chans)} channel(s)).",
            findings, metrics,
            images={"Local WS payload per 64x64 block": _plot_heatmap(heat),
                    "PoV cumulative p-value": _plot_curve(curve)},
            tables={"Per-channel payload estimates": rows},
            limitations=LIMITATIONS,
            details={"format": fmt, "threshold_bpp": THRESHOLD,
                     "estimates": est, "score": top, "max_channel": top_name,
                     "combined_ws": combined,
                     "pov_curve": [float(v) for v in curve],
                     "sequential_fraction": seq_k,
                     "sequential_local_bpp": seq_local,
                     "sequential_rest_bpp": seq_rest,
                     "sequential_detected": bool(seq_ok),
                     "block_map": heat.round(4).tolist()})
    except Exception as e:  # noqa: BLE001
        return util.error_result(e, LIMITATIONS)
