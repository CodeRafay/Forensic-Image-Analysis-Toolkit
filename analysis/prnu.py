"""
PRNU — Photo-Response Non-Uniformity sensor fingerprint.

Every photosite has a slightly different gain, so a sensor imprints a fixed
multiplicative pattern K on every photo:  I = I0 + I0*K + noise.
The pipeline follows the Camera-Fingerprint reference implementation:

- Lukáš, Fridrich, Goljan, "Digital camera identification from sensor pattern
  noise", IEEE TIFS 2006 (wavelet noise residual).
- Chen, Fridrich, Goljan, Lukáš, "Determining image origin and integrity using
  sensor noise", IEEE TIFS 2008 (ML fingerprint estimate, block correlation
  predictor).
- Goljan, Fridrich, Filler, "Large scale test of sensor fingerprint camera
  identification", SPIE 2009 (ZeroMeanTotal, WienerInDFT, PCE > 60).
- Chierchia, Poggi, Sansone, Verdoliva, "A Bayesian-MRF approach for
  PRNU-based image forgery detection", IEEE TIFS 2014 (local decision as a
  binary MRF: per-block likelihood ratio of "fingerprint present"
  N(ρ̂, σ̂²) vs "absent" N(0, σ0²) plus an Ising smoothness prior). Here
  the MRF energy is minimised exactly by an s–t minimum cut (scipy
  maximum_flow) on the 128-px block grid, not per pixel as in the paper.

Steps: NoiseExtract (db4, 4 levels, local Wiener on detail coefficients,
σ0 = 3) → ZeroMeanTotal → WienerInDFT → K = Σ W·I / Σ I² → test W against
I_test·K by NCC and PCE → (match) local MRF test on 128 px blocks.

Everything is float32 and references are streamed one at a time (running
sums ΣW·I, ΣI²). Images larger than max_px per side are CENTRE-CROPPED
(never resized — resampling destroys the pixel-aligned pattern).
"""
from concurrent.futures import ThreadPoolExecutor
from itertools import islice

import cv2
import numpy as np
import pywt
import scipy.fft as sfft
from PIL import Image
from scipy.ndimage import label

from .util import error_result, load_array, make_result, overlay_mask, to_uint8

F32 = np.float32
SIGMA0 = 3.0          # NoiseExtract noise std (Goljan's default)
LEVELS = 4            # wavelet decomposition levels
PCE_THRESHOLD = 60.0  # Goljan et al. 2009: FAR ≈ 2.4e-5 on 1M+ images.
# Camera matching is unchanged by design (published threshold); measured
# hold-out numbers are in Descriptions/PRNU.md (realistic Bayer+demosaic+JPEG
# simulator, K std 0.003–0.01).
BLOCK = 128           # Chen 2008 / Chierchia 2014 block size
STRIDE = 32
# MRF parameters, calibrated on simulator set A (Bayer+demosaic+JPEG q85,
# 4 MP, 8 refs, K 0.006/0.01): clean false regions 0/24. Hold-out set B
# (other scenes/seeds, q75/85/95): clean false regions 3/39; K 0.01 q85
# splice found 192 px 2/12, 256 px 8/12, 384 px 12/12, 512 px 10/12;
# K 0.006: 0/8 at every size (see Descriptions/PRNU.md).
MIN_SEP = 1.0         # block testable when predicted ρ̂ ≥ MIN_SEP·σ0
GAMMA = 2.0           # prior cost of labelling a block "fingerprint absent"
BETA_MRF = 0.5        # Ising cost per disagreeing 8-neighbour pair
MIN_CLUSTER = 16      # labelled-absent testable blocks per region before reporting
MIN_TESTABLE = 0.10   # below this testable fraction the local test is skipped
DARK, BRIGHT = 40.0, 250.0  # block-mean limits (pixel saturation: BRIGHT); dark
#   blocks (< 40) gave hold-out false alarms: read noise + JPEG bury the PRNU
MAX_PX = 4096         # default per-side cap (4000×3000 = 12 MP runs uncropped)

LIMITATIONS = [
    "Needs reference images from the candidate camera with the same pixel "
    "dimensions and orientation; rotated, resized, digitally zoomed or "
    "re-cropped images cannot be matched without geometric search (not done).",
    "Strong JPEG compression, denoising, HDR/multi-frame processing and "
    "resizing weaken or remove the fingerprint; no match does not exclude "
    "the camera. Small images (≲ 1 MP) rarely match even when genuine.",
    "Cameras of the same model sharing firmware artifacts can correlate "
    "weakly; ZeroMeanTotal and WienerInDFT reduce but do not remove this.",
    "The local test cannot evaluate dark, saturated, flat or weak-fingerprint "
    "blocks; those are shown as untestable. With a realistic (weak) sensor "
    "fingerprint most blocks are untestable and spliced regions are usually "
    "missed: absence of a flagged region is weak evidence.",
    "Local test resolution is about 128 px: smaller pasted objects are missed.",
]


# ── Residual extraction (Goljan's Camera-Fingerprint toolbox) ─────
def _box(x, w, wrap_rows=False):
    """w×w moving average, mirror boundary (scipy 'reflect'); with wrap_rows
    the rows wrap around (periodic spectrum axis)."""
    x = np.asarray(x, F32)
    if not wrap_rows:
        return cv2.blur(x, (w, w), borderType=cv2.BORDER_REFLECT)
    p = w // 2
    xp = np.concatenate([x[-p:], x, x[:p]])
    return cv2.blur(xp, (w, w), borderType=cv2.BORDER_REFLECT)[p:-p]


def _wiener(c, var0, wrap_rows=False):
    """Goljan's WaveNoise: local variance = min over 3,5,7,9 windows of
    max(E[c²] - σ0², 0); returns the NOISE part c·σ0² / (var + σ0²)."""
    c2 = c * c
    var = None
    for w in (3, 5, 7, 9):
        v = _box(c2, w, wrap_rows)
        v -= var0
        np.maximum(v, 0, out=v)
        var = v if var is None else np.minimum(var, v, out=var)
    var += var0
    return c * (F32(var0) / var)


def noise_extract(img, sigma0=SIGMA0, levels=LEVELS):
    """Wavelet noise residual of a 2-D array (approximation band zeroed)."""
    img = np.asarray(img, F32)
    h, w = img.shape
    m = 2 ** levels
    x = np.pad(img, ((0, (-h) % m), (0, (-w) % m)), mode="symmetric")
    coeffs = pywt.wavedec2(x, "db4", mode="periodization", level=levels)
    del x
    var0 = sigma0 ** 2
    coeffs[0] = np.zeros_like(coeffs[0])
    for i in range(1, len(coeffs)):
        coeffs[i] = tuple(_wiener(d, var0) for d in coeffs[i])
    return pywt.waverec2(coeffs, "db4", mode="periodization")[:h, :w].astype(F32, copy=False)


def zero_mean_total(x):
    """Remove row and column means on each of the four 2×2 sub-lattices
    (CFA/JPEG artifacts shared by all cameras of a model)."""
    z = np.array(x, dtype=F32)
    for i in (0, 1):
        for j in (0, 1):
            s = z[i::2, j::2]  # view: edits land in z
            s -= s.mean(axis=0, keepdims=True, dtype=np.float64).astype(F32)
            s -= s.mean(axis=1, keepdims=True, dtype=np.float64).astype(F32)
    return z


def wiener_dft(x, sigma):
    """Goljan's WienerInDFT: Wiener-filter |Re F| (normalised so white noise
    of std σ has E|F|² = σ²), keeping phase. Flat (noise-like) parts of the
    spectrum pass, isolated peaks are flattened. Uses the real FFT (half
    spectrum; wrap along rows, reflect along the cut column axis)."""
    h, w = x.shape
    f = sfft.rfft2(np.asarray(x, F32), workers=-1)
    mag = np.abs(f.real) / F32(np.sqrt(h * w))
    mag1 = _wiener(mag, sigma ** 2, wrap_rows=True)
    np.divide(mag1, mag, out=mag1, where=mag > 0)
    mag1[mag == 0] = 0
    del mag
    f *= mag1
    del mag1
    return sfft.irfft2(f, s=(h, w), workers=-1).astype(F32, copy=False)


def residual(img):
    return zero_mean_total(noise_extract(img))


def _crop(img, max_px):
    """Centre crop to ≤ max_px per side; returns an independent copy."""
    h, w = img.shape[:2]
    ch, cw = (min(h, max_px), min(w, max_px)) if max_px else (h, w)
    y0, x0 = (h - ch) // 2, (w - cw) // 2
    return np.array(img[y0:y0 + ch, x0:x0 + cw], dtype=F32), (y0, x0)


def accumulate(images, workers=2):
    """Running sums Σ W·I and Σ I² of the ML estimator over an iterable of
    images (saturated pixels excluded). `workers` residuals are computed in
    parallel threads (pywt/OpenCV release the GIL), so at most that many
    images are in memory at a time."""
    num = den = None
    it = iter(images)
    with ThreadPoolExecutor(workers) as ex:
        while True:
            batch = [np.asarray(im, F32) for im in islice(it, workers)]
            if not batch:
                break
            for im, w in zip(batch, ex.map(residual, batch)):
                ok = im < BRIGHT
                w *= im
                w *= ok
                i2 = im * im
                i2 *= ok
                if num is None:
                    num, den = w, i2
                else:
                    num += w
                    den += i2
                del w, i2, ok
            del batch
    return num, den


def finalize(num, den):
    """K = num / den, then ZeroMeanTotal + WienerInDFT(σ = std K)."""
    k = zero_mean_total(num / (den + 1.0))
    return wiener_dft(k, float(k.std(dtype=np.float64)))


# ── Matching ──────────────────────────────────────────────────────
def ncc(a, b):
    a = a - F32(a.mean(dtype=np.float64))
    b = b - F32(b.mean(dtype=np.float64))
    num = np.sum(a * b, dtype=np.float64)
    return float(num / (np.sqrt(np.sum(a * a, dtype=np.float64) *
                                 np.sum(b * b, dtype=np.float64)) + 1e-12))


def pce(a, b, nbhd=11):
    """Peak-to-correlation energy at zero shift (Goljan 2009): signed
    C(0)² / mean C² outside an nbhd×nbhd neighbourhood of the peak."""
    a = np.asarray(a, F32)
    b = np.asarray(b, F32)
    fa = sfft.rfft2(a - F32(a.mean(dtype=np.float64)), workers=-1)
    fa *= np.conj(sfft.rfft2(b - F32(b.mean(dtype=np.float64)), workers=-1))
    c = sfft.irfft2(fa, s=a.shape, workers=-1)
    del fa
    h, w = c.shape
    r = np.arange(-(nbhd // 2), nbhd // 2 + 1)
    nb = c[np.ix_(r % h, r % w)].astype(np.float64)
    e = (np.sum(c * c, dtype=np.float64) - (nb ** 2).sum()) / (c.size - nb.size)
    peak = float(c[0, 0])
    return float(np.sign(peak) * peak ** 2 / (e + 1e-30))


# ── Local integrity test ──────────────────────────────────────────
def _win_mean(x, b=BLOCK, s=STRIDE):
    """Mean of x in every b×b window at stride s (b a multiple of s), via
    exact float64 sums of s×s cells."""
    H, W = x.shape[0] // s, x.shape[1] // s
    cells = x[:H * s, :W * s].reshape(H, s, W, s).sum((1, 3), dtype=np.float64)
    c = np.pad(cells.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    n = b // s
    return (c[n:, n:] - c[:-n, n:] - c[n:, :-n] + c[:-n, :-n]) / b ** 2


def _win_corr(a, b):
    ma, mb = _win_mean(a), _win_mean(b)
    cov = _win_mean(a * b) - ma * mb
    va = np.maximum(_win_mean(a * a) - ma ** 2, 1e-12)
    vb = np.maximum(_win_mean(b * b) - mb ** 2, 1e-12)
    return cov / np.sqrt(va * vb)


def _features(img):
    """Chen 2008 block features: intensity attenuation, texture, flatness."""
    att = np.where(img > 252, np.exp(-(img - 252) ** 2 / 6.0), img / 252.0).astype(F32)
    f_i = _win_mean(att)
    del att
    m3 = _box(img, 3)
    hp = img - m3
    f_t = _win_mean(1.0 / (1.0 + _box(hp * hp, 5)))
    del hp
    local_var = _box(img * img, 3) - m3 * m3
    f_f = _win_mean((local_var < (0.03 * img) ** 2).astype(F32))
    return f_i, f_t, f_f


def block_data(img, w, k):
    """Per-block observed correlation ρ, predictor design matrix and the
    mask of blocks that are neither dark, saturated nor flat."""
    rho = _win_corr(w, img * k)
    f_i, f_t, f_f = _features(img)
    mean_i = _win_mean(img)
    usable = (mean_i > DARK) & (mean_i < BRIGHT) & (f_f < 0.95)
    x = np.stack([np.ones_like(f_i), f_i, f_t, f_f, f_i ** 2, f_t ** 2,
                  f_f ** 2, f_i * f_t, f_i * f_f, f_t * f_f], -1)
    return rho, x, usable


def _min_cut(llr, testable, gamma=GAMMA, beta=BETA_MRF):
    """Exact minimiser of E(u) = Σ u_i (γ − λ_i) + β Σ_{i~j} [u_i ≠ u_j]
    (8-neighbour Ising prior; u = 1: fingerprint absent) by s–t min-cut
    (scipy maximum_flow, capacities quantised to 1/100). Untestable blocks
    have λ = 0, so they only follow their neighbours."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import breadth_first_order, maximum_flow
    h, w = llr.shape
    n = h * w
    s, t = n, n + 1
    a = np.round(100 * (gamma - np.where(testable, llr, 0.0))).astype(np.int64).ravel()
    idx = np.arange(n).reshape(h, w)
    rows, cols, caps = [], [], []
    pos = a > 0  # u=1 costs a → edge s→i cut when i is on the sink (u=1) side
    rows += [np.full(pos.sum(), s), idx.ravel()[~pos]]
    cols += [idx.ravel()[pos], np.full((~pos).sum(), t)]
    caps += [a[pos], -a[~pos]]
    bq = max(1, int(round(100 * beta)))
    for p, q in ((idx[:, :-1], idx[:, 1:]), (idx[:-1], idx[1:]),
                 (idx[:-1, :-1], idx[1:, 1:]), (idx[:-1, 1:], idx[1:, :-1])):
        p, q = p.ravel(), q.ravel()
        rows += [p, q]
        cols += [q, p]
        caps += [np.full(p.size, bq), np.full(p.size, bq)]
    cap = coo_matrix((np.concatenate(caps).astype(np.int32),
                      (np.concatenate(rows), np.concatenate(cols))), shape=(n + 2, n + 2)).tocsr()
    cap.sum_duplicates()
    flow = maximum_flow(cap, s, t).flow
    resid = (cap - flow).tocsr()
    resid.data = (resid.data > 0).astype(np.int8)
    resid.eliminate_zeros()
    src_side = breadth_first_order(resid, s, directed=True, return_predecessors=False)
    u = np.ones(n + 2, bool)
    u[src_side] = False
    return u[:n].reshape(h, w)


def local_test(img, w, k, train):
    """Block-wise fingerprint-presence test (Chen 2008 predictor,
    Chierchia 2014 MRF decision).

    ρ̂ = x·θ is fitted on the references (`train`: block_data tuples, each
    against a leave-one-out fingerprint). σ0 (no fingerprint) comes from
    correlating with circularly shifted fingerprints, σ̂ is the predictor's
    residual std. Per-block LLR λ = log N(ρ;0,σ0) − log N(min(ρ,ρ̂);ρ̂,σ̂)
    (one-sided: ρ above prediction never favours "absent"). Testable: usable
    and ρ̂ ≥ MIN_SEP·σ0. Labels by min-cut on the MRF; flagged = labelled-absent
    testable blocks in regions of ≥ MIN_CLUSTER. Returns testable_fraction;
    when it is < MIN_TESTABLE the predictor is still reported but nothing is
    flagged (insufficient data).
    """
    rho, x, usable = block_data(img, w, k)
    ik = img * k
    h, wd = img.shape
    null = []
    for i in (1, 2):
        null.append(_win_corr(w, np.roll(ik, (h // 3 + 7 * i, wd // 3 + 11 * i), (0, 1))))
    del ik
    sigma0 = float(np.std(null))
    xt = np.concatenate([d[1][d[2]] for d in train])
    yt = np.concatenate([d[0][d[2]] for d in train])
    base = dict(rho=rho, usable=usable, sigma0=sigma0, testable=np.zeros(rho.shape, bool),
                flagged=np.zeros(rho.shape, bool), rho_hat=np.zeros(rho.shape),
                sigma_hat=0.0, testable_fraction=0.0, llr=np.zeros(rho.shape))
    if len(yt) < 3 * x.shape[-1]:
        return base
    theta = np.linalg.lstsq(xt, yt, rcond=None)[0]
    sigma_hat = float((yt - xt @ theta).std()) + 1e-9
    rho_hat = x @ theta
    testable = usable & (rho_hat >= MIN_SEP * sigma0)
    frac = float(testable.mean())
    base.update(rho_hat=rho_hat, sigma_hat=sigma_hat, testable=testable,
                testable_fraction=frac)
    if frac < MIN_TESTABLE:
        return base
    r1 = np.minimum(rho, rho_hat)
    llr = (0.5 * ((r1 - rho_hat) / sigma_hat) ** 2 + np.log(sigma_hat)
           - 0.5 * (rho / sigma0) ** 2 - np.log(sigma0))
    flagged = _min_cut(llr, testable) & testable
    lab, _ = label(flagged, structure=np.ones((3, 3)))
    for i, size in enumerate(np.bincount(lab.ravel())[1:], 1):
        if size < MIN_CLUSTER:
            flagged[lab == i] = False
    base.update(flagged=flagged, llr=llr)
    return base


TRAIN_SIDE = 1024      # predictor training window per reference


def train_predictor(refs, num, den):
    """block_data of every reference (iterable) against its leave-one-out
    fingerprint, each on one TRAIN_SIDE² window (windows cycle over the
    frame so different references cover different areas).
    ponytail: the window residual differs from the full-frame one within a
    few px of the window edge, so LOO is slightly imperfect at edge blocks;
    the window keeps training at 8 references cheap at 12 MP."""
    out = []
    for i, im in enumerate(refs):
        h, w = im.shape
        th, tw = min(TRAIN_SIDE, h), min(TRAIN_SIDE, w)
        ny, nx = max(1, h // th), max(1, w // tw)
        y = (i % ny) * (h - th) // max(1, ny - 1)
        x = ((i // ny) % nx) * (w - tw) // max(1, nx - 1)
        win = (slice(y, y + th), slice(x, x + tw))
        im = np.asarray(im[win], F32)
        ok = im < BRIGHT
        wi = residual(im)
        k_loo = finalize(num[win] - wi * im * ok, den[win] - im * im * ok)
        out.append(block_data(im, wiener_dft(wi, float(wi.std(dtype=np.float64))), k_loo))
        del wi, k_loo, ok
    return out


# ── Display helpers (downscale first, so no full-res RGB copies) ──
def _disp_size(shape, side=1200):
    s = min(1.0, side / max(shape[:2]))
    return max(1, round(shape[1] * s)), max(1, round(shape[0] * s))


def _small(a, size, resample=Image.Resampling.BOX):
    a = np.asarray(a, F32)
    if (a.shape[1], a.shape[0]) == size:
        return a
    return np.asarray(Image.fromarray(a, "F").resize(size, resample), F32)


def _block_mask(grid, shape):
    """Mark the central half of each set block (full-res bool mask)."""
    m = np.zeros(shape, bool)
    q = BLOCK // 4
    for i, j in zip(*np.nonzero(grid)):
        y, x = i * STRIDE, j * STRIDE
        m[y + q:y + BLOCK - q, x + q:x + BLOCK - q] = True
    return m


def _iter_refs(paths, full_shape, max_px, used, skipped):
    """Yield cropped references one at a time, recording used/skipped."""
    for p in paths:
        try:
            r, _ = load_array(p, "L")
        except Exception as e:  # noqa: BLE001
            skipped.append({"reference": str(p), "reason": f"unreadable: {e}"})
            continue
        if r.shape != full_shape:
            skipped.append({"reference": str(p),
                            "reason": f"size {r.shape[1]}×{r.shape[0]} ≠ test "
                                      f"{full_shape[1]}×{full_shape[0]}"})
            continue
        rc = _crop(r, max_px)[0]
        del r
        used.append(p)
        yield rc


# ── Entry point ───────────────────────────────────────────────────
def analyze_prnu(image_path, reference_paths=None, max_px=MAX_PX):
    """
    Noise-residual statistics; with references, camera matching (NCC, PCE)
    and a local fingerprint-presence test.

    Args:
        reference_paths: path or list of paths of images known to come from
            the candidate camera (same pixel size as the test image; flat,
            bright, uncompressed-ish shots work best; ≥ 8 recommended).
        max_px: images larger than this per side are centre-cropped to at
            most max_px × max_px (never resized); references are cropped the
            same. Default 4096 (a 4000×3000 image is analysed in full).
    """
    try:
        full, _ = load_array(image_path, "L")
        full_shape = full.shape
        img, (y0, x0) = _crop(full, max_px)
        del full
        h, w = img.shape
        if min(h, w) < BLOCK:
            return make_result("insufficient_data",
                               f"Image {w}×{h} px is too small for sensor-noise analysis "
                               f"(needs ≥ {BLOCK} px per side).", limitations=LIMITATIONS)
        res = residual(img)
        res_std = float(res.std(dtype=np.float64))
        metrics = {"Analysed region (px)": f"{w}×{h} at x={x0}, y={y0}",
                   "Residual std (grey levels)": round(res_std, 4)}
        if res_std < 0.05:
            return make_result("insufficient_data",
                               "The image has essentially no noise residual (flat or "
                               "synthetic content); no sensor pattern to analyse.",
                               metrics=metrics, limitations=LIMITATIONS)
        dsize = _disp_size(img.shape)
        images = {"Noise residual (zero-meaned)": to_uint8(_small(res, dsize))}
        details = {"crop_offset": [int(y0), int(x0)], "shape": [h, w],
                   "residual_std": res_std}

        if not reference_paths:
            return make_result(
                "ok", "Sensor-noise residual extracted; no reference fingerprint given.",
                [("info", "No reference fingerprint — camera identification not "
                          "possible. Add reference images from the candidate camera.")],
                metrics, images, limitations=LIMITATIONS, details=details)

        if isinstance(reference_paths, (str, bytes)) or hasattr(reference_paths, "__fspath__"):
            reference_paths = [reference_paths]
        used, skipped = [], []
        num, den = accumulate(_iter_refs(reference_paths, full_shape, max_px, used, skipped))
        tables = {"Skipped references": skipped} if skipped else {}
        metrics["References used"] = len(used)
        if not used:
            return make_result(
                "not_applicable",
                "No reference image has the same pixel dimensions as the test image.",
                [("info", "The fingerprint is pixel-aligned, so references must have "
                          "the same size and orientation as the test image. Rotated, "
                          "resized or cropped references cannot be used.")],
                metrics, images, tables, LIMITATIONS, details)

        k = finalize(num, den)
        wt = wiener_dft(res, res_std)
        del res
        expected = img * k
        c_ncc, c_pce = ncc(wt, expected), pce(wt, expected)
        del expected
        metrics.update({"NCC": round(c_ncc, 5), "PCE": round(c_pce, 1),
                        "PCE threshold": PCE_THRESHOLD})
        details.update(ncc=c_ncc, pce=c_pce, references_used=len(used))
        findings = []
        if c_pce <= PCE_THRESHOLD:
            findings.append(("notice",
                             f"PCE {c_pce:.1f} ≤ {PCE_THRESHOLD:.0f}: the noise residual does "
                             "not match the reference fingerprint. This does not exclude "
                             "the camera — compression, resizing, denoising, a small image "
                             "or few references also prevent a match."))
            return make_result("ok", f"Sensor fingerprint from {len(used)} reference(s) "
                               "compared with the test image by NCC and PCE.",
                               findings, metrics, images, tables, LIMITATIONS, details)

        findings.append(("info", f"PCE {c_pce:.1f} > {PCE_THRESHOLD:.0f} (NCC {c_ncc:.4f}): "
                                 "the image carries the reference camera's sensor fingerprint."))
        if len(used) < 2:
            findings.append(("info", "Local splice test not run: it needs at least 2 "
                                     "reference images to fit the correlation predictor."))
            return make_result("ok", "Sensor fingerprint from 1 reference compared with "
                               "the test image by NCC and PCE.",
                               findings, metrics, images, tables, LIMITATIONS, details)
        train = train_predictor(_iter_refs(used, full_shape, max_px, [], []), num, den)
        del num, den
        lt = local_test(img, wt, k, train)
        del train, wt, k
        n_test, n_flag = int(lt["testable"].sum()), int(lt["flagged"].sum())
        n_blocks = lt["rho"].size
        frac = lt["testable_fraction"]
        metrics.update({"Blocks tested (128 px, stride 32)": n_test,
                        "Blocks untestable": n_blocks - n_test,
                        "Testable fraction (%)": round(100 * frac, 1),
                        "Blocks lacking fingerprint": n_flag})
        details.update(sigma0=lt["sigma0"], sigma_hat=lt["sigma_hat"],
                       blocks_tested=n_test, blocks_flagged=n_flag,
                       testable_fraction=frac)
        if frac < MIN_TESTABLE:
            findings.append(("info",
                             f"Local splice test: insufficient data — only {100 * frac:.1f} % "
                             f"of blocks are testable (needs ≥ {100 * MIN_TESTABLE:.0f} %). "
                             "The fingerprint is too weak, or the scene too dark/flat/"
                             "saturated, to say anything about individual regions."))
            details.update(local_test="insufficient_data", regions=[])
            return make_result("ok", f"Sensor fingerprint from {len(used)} reference(s) "
                               "compared with the test image by NCC and PCE; local test "
                               "had insufficient data.",
                               findings, metrics, images, tables, LIMITATIONS, details)
        lab, n_reg = label(lt["flagged"], structure=np.ones((3, 3)))
        regions = []
        for i in range(1, n_reg + 1):
            ys, xs = np.nonzero(lab == i)
            regions.append({"x": int(xs.min() * STRIDE + x0), "y": int(ys.min() * STRIDE + y0),
                            "width": int((xs.max() - xs.min()) * STRIDE + BLOCK),
                            "height": int((ys.max() - ys.min()) * STRIDE + BLOCK),
                            "blocks": int(len(ys)),
                            "mean observed corr.": round(float(lt["rho"][lab == i].mean()), 4),
                            "mean predicted corr.": round(float(lt["rho_hat"][lab == i].mean()), 4)})
        if regions:
            tables["Regions lacking the fingerprint"] = regions
            findings.append(("warning",
                             f"{n_reg} region(s) ({n_flag} blocks) show no fingerprint where "
                             "the predictor expects it — consistent with content from another "
                             "source (splice) or strong local processing."))
        else:
            findings.append(("info", f"{n_test} blocks tested ({100 * frac:.0f} % of the "
                                     "image); no region lacking the fingerprint found at this "
                                     "sensitivity. Small or weakly-fingerprinted splices are "
                                     "often missed."))
        tm = _block_mask(lt["testable"], img.shape)
        untest = _small(_block_mask(~lt["testable"], img.shape) & ~tm, dsize) > 0.5
        del tm
        flag = _small(_block_mask(lt["flagged"], img.shape), dsize) > 0.5
        vis = overlay_mask(to_uint8(_small(img, dsize), stretch=False), untest, (128, 128, 128), 0.5)
        images["Local test (red: fingerprint missing, grey: untestable)"] = overlay_mask(vis, flag)
        details.update(local_test="ok", regions=regions)
        return make_result("ok", f"Sensor fingerprint from {len(used)} reference(s) "
                           "compared with the test image by NCC, PCE and a local MRF block test.",
                           findings, metrics, images, tables, LIMITATIONS, details)
    except Exception as e:  # noqa: BLE001
        return error_result(e, LIMITATIONS)
