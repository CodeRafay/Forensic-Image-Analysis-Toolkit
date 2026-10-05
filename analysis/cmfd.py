"""
Copy-move forgery detection (CMFD): finds regions of an image that were
copied and pasted elsewhere in the same image, possibly rotated or scaled.

Hybrid of the two standard non-learned pipelines:

1. Keypoint branch - I. Amerini, L. Ballan, R. Caldelli, A. Del Bimbo,
   G. Serra, "A SIFT-based forensic method for copy-move attack detection and
   transformation recovery", IEEE TIFS 6(3), 2011. SIFT keypoints (RootSIFT
   descriptors, Arandjelovic & Zisserman 2012) are matched against the image
   itself with the generalised 2NN test (ratio 0.5), matched locations are
   grouped by Ward hierarchical clustering and every cluster pair with >= 4
   matches gets a RANSAC affine fit (any offset, rotation, scale).
   Mirror-invariant matching (MIFT idea: M. Jaberi, G. Bebis, M. Hussain, G. Muhammad,
   "Accurate and robust localization of duplicated region in copy-move image
   forgery", Machine Vision and Applications 25, 2014): descriptors from the
   left-right flipped image are matched too, so mirrored clones are found and
   fitted with a reflecting affine. SIFT runs at <= 1536 px (memory).
2. Dense branch - D. Cozzolino, G. Poggi, L. Verdoliva, "Efficient dense-field
   copy-move forgery detection", IEEE TIFS 10(11), 2015. Rotation-invariant
   Zernike-moment magnitudes per pixel (at <= 1024 px / 0.6 MP), the paper's
   PatchMatch with first-order offset prediction 2*d(n') - d(n'') and
   radius-halving random search (8 iterations), a minimum-offset constraint,
   median filtering and dense linear fitting (DLF) of the offset field. Catches low-texture
   clones with too few keypoints. Flat pixels are excluded (they match
   everything).
3. Verification - I. Amerini, L. Ballan, R. Caldelli, A. Del Bimbo, L. Del
   Tongo, G. Serra, "Copy-move forgery detection and localization by means of
   robust clustering with J-Linkage", Signal Processing: Image Communication
   28(6), 2013 (after Pan & Lyu, IEEE TIFS 2010): every affine hypothesis is
   checked by warping the image with it and computing a local zero-mean
   normalised cross-correlation (ZNCC) map; only regions that correlate over a
   minimum connected area are reported. A single stray match never produces a
   finding. Then a region-level test (this module's addition, calibrated on
   seeded data): the median |difference| between the region and its copy
   must be explained by the resampling the paste implies plus the JPEG
   quality of the file; natural look-alikes (grass, gravel, text) differ more.
"""
import math

import cv2
import numpy as np
from scipy import ndimage
from scipy.cluster.hierarchy import fcluster, linkage

from PIL import Image

from analysis import util
from analysis.quant_table import estimate_jpeg_quality

# ── Parameters (calibrated in tests/test_cmfd.py and Descriptions/CMFD.md) ──
MIN_SIDE = 64          # px; smaller images have no room for a clone + offset
G2NN_RATIO = 0.5       # Amerini 2011
MIN_SHIFT = 30         # px; matches closer than this are the same structure
WARD_CUT = 2.2         # Amerini 2011 inconsistency cut-off for Ward clustering
MIN_INLIERS = 4        # RANSAC inliers (paper minimum); verification below does the rejecting
RANSAC_PX = 3.0        # reprojection tolerance
DENSE_PX = 1024        # long side of the dense-branch image
DENSE_AREA = 6e5      # px; and at most this many pixels (time budget)
SIFT_PX = 1536         # long side SIFT runs at (memory: SIFT upsamples 2x)
ZM_RADIUS = 6          # Zernike disc radius at dense scale (13 px patch)
FLAT_STD = 2.5         # grey levels; flatter patches are not matched densely
DLF_ERR = 1.0          # px^2; max dense-linear-fit error of the offset field
ZNCC_TH = 0.7          # min local 7x7 ZNCC between region and its copy
DIFF_TH = 12.0         # grey levels; max local mean |I - I(M x)| per pixel
# Region test (median over the region): |diff| <= DIFF_BASE
#   + RESAMPLE_K * (residual of re-sampling the region with M and back)
#   + JPEG_K * (100 - JPEG quality of the file; 0 for PNG/TIFF).
DIFF_BASE = 2.0
RESAMPLE_K = 1.5
JPEG_K = 0.06
DENSE_ZNCC = 0.85      # dense-only hypotheses (no keypoint support) need this
DETAIL_MIN = 0.4       # and this median |I - Gauss_1.5(I)| (noise/texture); a
                       # clean synthetic colour wheel has 0.14, camera images > 0.5
MIN_AREA = 900         # px at analysis size (~30x30), or 0.1 % of large images
# Calibration set (seeded; scratch cal.py): camera-pipeline renders (Bayer
# RGGB, shot+read noise, bilinear demosaic, optional sharpening) of
# astronaut/camera/retina/cat; 96 clones 40-128 px, rotation -45..180 deg,
# scale 0.8-1.2, 25 % mirrored, PNG or JPEG q60-95; 40 clean renders
# (PNG, q60-92) + brick/moon/coins/hubble/page (PNG, q70). The region test
# constants were picked from a grid as the most sensitive setting with 0
# false alarms on that set (TPR 0.71). Hold-out numbers: Descriptions/CMFD.md.

LIMITATIONS = [
    "Only detects duplication within this image; content pasted from another "
    "image (splicing) is invisible to this method.",
    "Clones of flat, featureless regions (clear sky, plain walls) cannot be "
    "told apart from genuine flat areas, especially after JPEG compression.",
    "Naturally repetitive content (tiles, windows, fences, text, symmetric "
    "scenes) can produce matches that look like cloning; check every "
    "hypothesis visually.",
    "Clones smaller than ~64 px, or rotated/scaled clones after JPEG below "
    "~q75, are often missed (see the measured hit rates).",
    "Heavy JPEG compression (quality below ~70), strong blur, noise or large "
    "scaling after pasting weakens the matches; rotation/scale are only "
    "recovered as a single affine transform per region.",
    "Regions smaller than about 30x30 px at the analysed size are ignored; "
    "large photos are analysed at 2048 px, so a 60 px clone in a 4000 px "
    "photo is below that limit.",
]


def detect_copy_move(image_path, max_px=2048):
    """
    Args:
        image_path: image file.
        max_px: long side the image is downscaled to (in memory) before
            analysis; the analysed size is reported.

    Returns:
        util.make_result(...) with a source/target overlay, per-clone affine
        parameters and the dense-field consistency map.
    """
    try:
        rgb, scale = util.load_array(image_path, "RGB", max_px)
        h, w = rgb.shape[:2]
        gray = rgb @ np.array([0.299, 0.587, 0.114])
        if min(h, w) < MIN_SIDE or gray.std() < 1.0:
            return util.make_result(
                "insufficient_data",
                f"Image too small or too flat ({w}x{h} px) for copy-move "
                "detection.", limitations=LIMITATIONS,
                metrics={"Analysed size (px)": f"{w}x{h}"})
        with Image.open(image_path) as im:
            qt = getattr(im, "quantization", None)
        quality = estimate_jpeg_quality(qt[0]) if qt and 0 in qt else None
        return _analyse(rgb, gray, scale, quality)[0]
    except Exception as e:  # noqa: BLE001 - contract: never raise
        return util.error_result(e, LIMITATIONS)


# ── Keypoint branch ───────────────────────────────────────────────
def _sift(g8):
    """RootSIFT keypoints (x, y) and descriptors of an 8-bit image."""
    kps, des = cv2.SIFT_create(nfeatures=20000, contrastThreshold=0.01).detectAndCompute(g8, None)
    if des is None:
        return np.zeros((0, 2), np.float32), np.zeros((0, 128), np.float32)
    des = np.sqrt(des / (des.sum(1, keepdims=True) + 1e-7)).astype(np.float32)
    return np.array([k.pt for k in kps], np.float32), des


def _keypoint_hypotheses(gray8):
    """Returns (hypotheses, n_keypoints, n_matches); a hypothesis is
    (M 2x3 src->dst, src_pts, dst_pts) with the RANSAC inliers.

    Mirror-invariant (MIFT idea, Jaberi et al., MVA 2014): SIFT is also run
    on the horizontally flipped image, its keypoints are mapped back, and the
    original descriptors are matched against both sets. A match to a flipped
    descriptor is a mirrored copy; the affine RANSAC then fits a reflection."""
    h, w = gray8.shape
    f = min(1.0, SIFT_PX / max(h, w))  # SIFT doubles the base image: cap memory
    g = gray8 if f == 1 else cv2.resize(gray8, (round(w * f), round(h * f)),
                                        interpolation=cv2.INTER_AREA)
    pts, des = _sift(g)
    pf, df = _sift(np.ascontiguousarray(g[:, ::-1]))
    pf[:, 0] = g.shape[1] - 1 - pf[:, 0]
    n = len(pts)
    if n < 10:
        return [], n, 0
    pts = np.vstack([pts, pf]) / f
    alld = np.vstack([des, df])
    k = min(10, len(alld) - 1)
    knn = cv2.FlannBasedMatcher({"algorithm": 1, "trees": 4},
                                {"checks": 64}).knnMatch(des, alld, k=k + 1)
    pairs = set()
    for i, ms in enumerate(knn):
        ms = [m for m in ms if m.trainIdx != i]
        # g2NN: keep neighbours while d_j / d_{j+1} < ratio
        for a, b in zip(ms, ms[1:]):
            if a.distance > G2NN_RATIO * b.distance + 1e-6:
                break
            j = a.trainIdx
            if np.hypot(*(pts[i] - pts[j])) > MIN_SHIFT:
                pairs.add((min(i, j), max(i, j)) if j < n else (i, j))
    if len(pairs) < 4:
        return [], n, len(pairs)
    pairs = np.array(sorted(pairs))
    used = np.unique(pairs)
    if len(used) > 2:
        lab = fcluster(linkage(pts[used], "ward"), WARD_CUT, "inconsistent")
    else:
        lab = np.ones(len(used), int)
    cl = dict(zip(used.tolist(), lab.tolist()))
    groups = {}
    for i, j in pairs:
        # direct and mirrored matches never share a RANSAC model
        key = tuple(sorted((cl[i], cl[j]))) + (j >= n,)
        groups.setdefault(key, []).append((i, j))
    hyps = []
    for key, g in groups.items():
        g = np.array(g)
        p, q = pts[g[:, 0]], pts[g[:, 1]]
        if key[0] != key[1]:  # orient source -> cluster key[0]
            flip = np.array([cl[i] != key[0] for i in g[:, 0]])
        else:  # same cluster: orient along the dominant displacement
            v = q - p
            u = np.linalg.svd(v, full_matrices=False)[2][0]
            flip = v @ u < 0
        p[flip], q[flip] = q[flip].copy(), p[flip].copy()
        # sequential RANSAC: one affine per clone, several clones per pair
        while len(p) >= 4:
            M, inl = cv2.estimateAffine2D(p, q, method=cv2.RANSAC,
                                          ransacReprojThreshold=RANSAC_PX,
                                          maxIters=2000, confidence=0.995)
            if M is None:
                break
            inl = inl.ravel().astype(bool)
            if inl.sum() < MIN_INLIERS:
                break
            if _plausible(M):
                hyps.append((M, p[inl], q[inl]))
            p, q = p[~inl], q[~inl]
    return hyps, n, len(pairs)


def _plausible(M):
    s = np.linalg.svd(M[:, :2], compute_uv=False)
    return 0.5 < s.min() and s.max() < 2.0


# ── Dense branch ──────────────────────────────────────────────────
def _zernike_features(g, radius):
    """|Z_nm| for n <= 5 (12 rotation-invariant features) at every pixel."""
    r = np.arange(-radius, radius + 1, dtype=np.float64)
    x, y = np.meshgrid(r, r)
    rho, th = np.hypot(x, y) / radius, np.arctan2(y, x)
    disc = rho <= 1
    feats = []
    for n in range(6):
        for m in range(n % 2, n + 1, 2):
            rad = np.zeros_like(rho)
            for s in range((n - m) // 2 + 1):
                c = ((-1) ** s * math.factorial(n - s) /
                     (math.factorial(s) * math.factorial((n + m) // 2 - s)
                      * math.factorial((n - m) // 2 - s)))
                rad += c * rho ** (n - 2 * s)
            rad *= disc * (n + 1) / np.pi / disc.sum()
            re = cv2.filter2D(g, cv2.CV_32F, (rad * np.cos(m * th)).astype(np.float32))
            im = cv2.filter2D(g, cv2.CV_32F, (rad * np.sin(m * th)).astype(np.float32))
            feats.append(np.hypot(re, im))
    return np.stack(feats, -1)


def _patchmatch(F, min_shift, rng, iters=8):
    """Nearest-neighbour offset field (dy, dx) with |offset| >= min_shift.

    Cozzolino 2015 PatchMatch, vectorised (all pixels update at once):
    zero-order propagation of a neighbour's offset delta(n'), the paper's
    first-order prediction 2*delta(n') - delta(n'') (n'' = neighbour of the
    neighbour, so rotated/scaled clones with linearly varying offsets
    propagate), and random search around the current offset with the radius
    halving from the image size to 1. 8 iterations as in the paper; the first
    also propagates at jump-flooding distances 2^k to make up for the
    parallel (not raster-order) update."""
    h, w, c = F.shape
    Ff = F.reshape(-1, c)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.int32)

    own = np.arange(h * w, dtype=np.int32).reshape(h, w)
    buf = np.empty_like(Ff)

    def cost(dy, dx):
        ty, tx = ys + dy, xs + dx
        ok = ((ty >= 0) & (ty < h) & (tx >= 0) & (tx < w)
              & (dy * dy + dx * dx >= min_shift ** 2))
        idx = np.where(ok, ty * w + tx, own)
        np.take(Ff, idx.ravel(), axis=0, out=buf)
        np.subtract(buf, Ff, out=buf)
        d = np.einsum("ij,ij->i", buf, buf).reshape(h, w)
        d[~ok] = np.inf
        return d

    dy = rng.integers(0, h, (h, w), dtype=np.int32) - ys
    dx = rng.integers(0, w, (h, w), dtype=np.int32) - xs
    best = cost(dy, dx)

    def attempt(cy, cx):
        nonlocal dy, dx, best
        c_ = cost(cy, cx)
        b = c_ < best
        dy[b], dx[b], best[b] = cy[b], cx[b], c_[b]

    def roll(a, ay, ax):
        return np.roll(a, (ay, ax), (0, 1))

    steps = [2 ** k for k in range(int(np.log2(max(h, w))), -1, -1)]
    for it in range(iters):
        for s in (steps if it == 0 else steps[-2:]):
            for ay, ax in ((0, s), (0, -s), (s, 0), (-s, 0)):
                attempt(roll(dy, ay, ax), roll(dx, ay, ax))
        for ay, ax in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            attempt(2 * roll(dy, ay, ax) - roll(dy, 2 * ay, 2 * ax),
                    2 * roll(dx, ay, ax) - roll(dx, 2 * ay, 2 * ax))
        rad = max(h, w) // 2
        while rad >= 1:
            attempt(dy + rng.integers(-rad, rad + 1, (h, w), dtype=np.int32),
                    dx + rng.integers(-rad, rad + 1, (h, w), dtype=np.int32))
            rad //= 2
    return dy, dx


def _dlf_error(dy, dx, r=3):
    """Mean squared residual of a local linear fit of the offset field in a
    (2r+1)^2 window (Cozzolino 2015, dense linear fitting)."""
    u = np.arange(-r, r + 1, dtype=np.float64)
    U = np.tile(u, (2 * r + 1, 1))
    n, su2 = U.size, (U ** 2).sum()
    err = 0.0
    for d in (dy.astype(np.float64), dx.astype(np.float64)):
        s1 = cv2.boxFilter(d, -1, (2 * r + 1,) * 2, normalize=False)
        s2 = cv2.boxFilter(d * d, -1, (2 * r + 1,) * 2, normalize=False)
        su = cv2.filter2D(d, -1, U)
        sv = cv2.filter2D(d, -1, U.T)
        err = err + s2 - s1 ** 2 / n - (su ** 2 + sv ** 2) / su2
    return np.maximum(err, 0) / n


def _dense_hypotheses(gray):
    """Returns (hypotheses, dlf_error_map). Each hypothesis is
    (M 2x3 src->dst at analysis size, seed mask at dense size)."""
    h, w = gray.shape
    f = min(1.0, DENSE_PX / max(h, w), math.sqrt(DENSE_AREA / (h * w)))
    g = cv2.resize(gray.astype(np.float32), (max(1, round(w * f)), max(1, round(h * f))),
                   interpolation=cv2.INTER_AREA)
    min_shift = max(MIN_SHIFT * f, 2 * ZM_RADIUS + 1)
    F = _zernike_features(g, ZM_RADIUS).reshape(-1, 12)
    # ponytail: project the 12 Zernike magnitudes on their top 8 principal
    # axes (L2 distances nearly preserved) - halves PatchMatch time at 12 MP.
    sub = F[::max(1, len(F) // 20000)]
    V = np.linalg.svd(sub - sub.mean(0), full_matrices=False)[2][:8]
    F = np.ascontiguousarray((F @ V.T).reshape(g.shape + (8,)), np.float32)
    dy, dx = _patchmatch(F, min_shift, np.random.default_rng(0))
    dy = cv2.medianBlur(dy.astype(np.float32), 5)
    dx = cv2.medianBlur(dx.astype(np.float32), 5)
    err = _dlf_error(dy, dx)
    mu = cv2.blur(g, (2 * ZM_RADIUS + 1,) * 2)
    std = np.sqrt(np.maximum(cv2.blur(g * g, (2 * ZM_RADIUS + 1,) * 2) - mu * mu, 0))
    edge = np.zeros_like(g, bool)
    edge[ZM_RADIUS:-ZM_RADIUS, ZM_RADIUS:-ZM_RADIUS] = True
    cand = (err < DLF_ERR) & (std > FLAT_STD) & edge & (np.hypot(dy, dx) >= min_shift)
    cand = ndimage.binary_opening(cand, iterations=2)
    lab, n = ndimage.label(cand)
    hyps = []
    min_area = max(MIN_AREA / 3 * f * f, 100)  # seed only; _verify enforces MIN_AREA
    for i in range(1, n + 1):
        m = lab == i
        if m.sum() < min_area:
            continue
        yy, xx = np.nonzero(m)
        src = np.stack([xx, yy], 1).astype(np.float32)
        dst = src + np.stack([dx[m], dy[m]], 1).astype(np.float32)
        M, _ = cv2.estimateAffine2D(src, dst, method=cv2.LMEDS)
        if M is None or not _plausible(M):
            continue
        M = M.copy()
        M[:, 2] /= f  # translation back to analysis pixels
        hyps.append((M, m))
    return hyps, err


# ── Verification / localisation ───────────────────────────────────
def _verify(gray, M, seed):
    """Warp by M, keep connected regions whose local ZNCC with their copy is
    high and that touch the seed. Returns (src_mask, dst_mask) or None."""
    h, w = gray.shape
    g = gray.astype(np.float32)
    Wg = cv2.warpAffine(g, M, (w, h), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
                        borderValue=-1)
    valid = cv2.warpAffine(np.ones_like(g), M, (w, h),
                           flags=cv2.INTER_NEAREST | cv2.WARP_INVERSE_MAP) > 0
    k = (7, 7)
    ma, mb = cv2.blur(g, k), cv2.blur(Wg, k)
    va = cv2.blur(g * g, k) - ma * ma
    vb = cv2.blur(Wg * Wg, k) - mb * mb
    cov = cv2.blur(g * Wg, k) - ma * mb
    zncc = cov / np.sqrt(np.maximum(va * vb, 1e-6))
    diff = cv2.blur(np.abs(g - Wg), k)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    shift = np.hypot(M[0, 0] * xs + M[0, 1] * ys + M[0, 2] - xs,
                     M[1, 0] * xs + M[1, 1] * ys + M[1, 2] - ys)
    cand = ((zncc > ZNCC_TH) & (diff < DIFF_TH) & valid
            & (np.minimum(va, vb) > FLAT_STD ** 2 / 4) & (shift > MIN_SHIFT))
    cand = cv2.GaussianBlur(cand.astype(np.float32), (0, 0), 2) > 0.5
    cand = cv2.morphologyEx(cand.astype(np.uint8), cv2.MORPH_CLOSE,
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    _, lab = cv2.connectedComponents(cand)
    cand = cand > 0
    keep = np.unique(lab[seed & cand])
    src = ndimage.binary_fill_holes(np.isin(lab, keep[keep > 0]))
    if src.sum() < max(MIN_AREA, 0.001 * h * w):
        return None
    dst = cv2.warpAffine(src.astype(np.uint8), M, (w, h), flags=cv2.INTER_NEAREST) > 0
    core = src & valid
    stats = {"ZNCC": float(np.median(zncc[core])) if core.any() else 0.0,
             "mean |diff| (grey levels)": float(np.median(diff[core])) if core.any() else 99.0}
    # residual a true clone would show from the two bilinear resamplings
    # alone (paste with M, compare via M^-1): ~0 for integer shifts
    fwd = cv2.warpAffine(g, M, (w, h), flags=cv2.INTER_LINEAR)
    back = cv2.warpAffine(fwd, M, (w, h), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP)
    ei = cv2.blur(np.abs(g - back), k)
    stats["resampling |diff| (grey levels)"] = float(np.median(ei[core])) if core.any() else 0.0
    hp = cv2.blur(np.abs(g - cv2.GaussianBlur(g, (0, 0), 1.5)), k)
    stats["fine detail (grey levels)"] = float(np.median(hp[core])) if core.any() else 0.0
    return src, dst, stats


def _support(M, kp_hyps):
    """Number of RANSAC-inlier keypoint matches (any hypothesis) that M
    maps onto each other within 4 px, in either direction."""
    n = 0
    for _, p, q in kp_hyps:
        for a, b in ((p, q), (q, p)):
            n += int((np.hypot(*(cv2.transform(a[None], M)[0] - b).T) < 4).sum())
    return n


def _accept(branch, st, quality):
    """Region-level test: a real clone differs from its copy only by the
    resampling of the paste and by JPEG applied after it. Natural look-alikes
    (texture, repeated structure) differ more."""
    jpeg = JPEG_K * (100 - quality) if quality else 0.0
    limit = DIFF_BASE + RESAMPLE_K * st["resampling |diff| (grey levels)"] + jpeg
    if st["mean |diff| (grey levels)"] > limit:
        return False
    if branch == "keypoint" or st["keypoint support"] >= MIN_INLIERS:
        return True
    # dense-only: smooth synthetic gradients (no noise, no texture) match
    # themselves under many rotations/scales, so demand detail and ZNCC
    return st["ZNCC"] >= DENSE_ZNCC and st["fine detail (grey levels)"] >= DETAIL_MIN


def _snap(M):
    """Editors paste translations at whole pixels: round a near-pure
    translation so the resampling term above is not inflated by a
    fractional RANSAC estimate."""
    if np.abs(M[:, :2] - np.eye(2)).max() < 0.02:
        M = np.hstack([np.eye(2), np.round(M[:, 2:])])
    return M


def _twin(Ms, M, lin_tol=0.02, t_tol=3.0):
    """Index of an accepted transform equal to M or to its inverse (the same
    clone found in two pieces, possibly in opposite directions), and whether
    it is the inverse; None if there is none."""
    Minv = cv2.invertAffineTransform(M)
    for i, M0 in enumerate(Ms):
        for cand, inverse in ((M, False), (Minv, True)):
            if (np.abs(cand[:, :2] - M0[:, :2]).max() < lin_tol
                    and np.abs(cand[:, 2] - M0[:, 2]).max() < t_tol):
                return i, inverse
    return None


def _params(M, src, dst, scale):
    A = M[:, :2]
    det = float(np.linalg.det(A))
    if det < 0:  # B = R(rot) * scale * mirror_x(A)
        A = A @ np.diag([-1.0, 1.0])
    # counter-clockwise on screen is positive (OpenCV getRotationMatrix2D)
    rot = np.degrees(np.arctan2(A[0, 1] - A[1, 0], A[0, 0] + A[1, 1]))
    cs = np.array(ndimage.center_of_mass(src))[::-1] / scale
    cd = np.array(ndimage.center_of_mass(dst))[::-1] / scale
    return {
        "copy A centre (x, y)": f"({cs[0]:.0f}, {cs[1]:.0f})",
        "copy B centre (x, y)": f"({cd[0]:.0f}, {cd[1]:.0f})",
        "shift dx (px)": round(float(cd[0] - cs[0]), 1),
        "shift dy (px)": round(float(cd[1] - cs[1]), 1),
        "rotation (deg)": round(float(rot), 1),
        "scale": round(float(np.sqrt(abs(det))), 3),
        "mirrored": det < 0,
        "area of one copy (% of image)": round(100.0 * float(src.sum()) / src.size, 2),
    }


_TABLE_KEYS = {"rotation (deg)": "rotation A->B (deg, CCW +)",
               "scale": "scale A->B", "mirrored": "mirrored A->B"}


def _analyse(rgb, gray, scale, quality=None):
    h, w = gray.shape
    gray8 = np.clip(gray, 0, 255).astype(np.uint8)
    kp_hyps, n_kp, n_match = _keypoint_hypotheses(gray8)
    dense_hyps, dlf = _dense_hypotheses(gray)

    cands = []
    for M, p, q in kp_hyps:
        seed = np.zeros((h, w), bool)
        for x, y in p:
            seed[int(round(y)) - 3:int(round(y)) + 4, int(round(x)) - 3:int(round(x)) + 4] = True
        cands.append(("keypoint", M, seed, len(p), (p, q)))
    for M, m in dense_hyps:
        seed = cv2.resize(m.astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST) > 0
        cands.append(("dense", M, seed, 0, None))

    clones, Ms, union = [], [], np.zeros((h, w), bool)
    for branch, M, seed, n_in, lines in cands:
        M = _snap(M) if scale == 1 else M
        v = _verify(gray, M, seed)
        if v is None:
            continue
        src, dst, st = v
        st["keypoint support"] = _support(M, kp_hyps)
        if not _accept(branch, st, quality):
            continue
        both = src | dst
        if (both & union).sum() > 0.5 * both.sum():
            continue  # same clone already found (other branch / other direction)
        union |= both
        twin = _twin(Ms, M)
        if twin is not None:  # another piece of an accepted clone: merge
            i, inverse = twin
            row0, s0, d0, l0 = clones[i]
            s0, d0 = (s0 | dst, d0 | src) if inverse else (s0 | src, d0 | dst)
            row0.update(_params(Ms[i], s0, d0, scale))
            clones[i] = (row0, s0, d0, l0)
            continue
        Ms.append(M)
        row = {"branch": branch, "RANSAC inliers": n_in}
        row.update(_params(M, src, dst, scale))
        row.update({k: round(v, 3) for k, v in st.items()})
        clones.append((row, src, dst, lines))

    src_all = np.zeros((h, w), bool)
    dst_all = np.zeros((h, w), bool)
    for _, s, d, _ in clones:
        src_all |= s
        dst_all |= d
    ov = util.overlay_mask(rgb, src_all & ~dst_all, (0, 200, 0))
    ov = util.overlay_mask(ov, dst_all, (230, 0, 0))
    for _, _, _, lines in clones:
        if lines is not None:
            for a, b in zip(*lines):
                cv2.line(ov, tuple(int(v) for v in a), tuple(int(v) for v in b),
                         (255, 220, 0), 1, cv2.LINE_AA)
    f = min(1.0, 1200 / max(h, w))
    if f < 1:
        ov = cv2.resize(ov, (round(w * f), round(h * f)), interpolation=cv2.INTER_AREA)
    dlf_img = util.to_uint8(-np.log10(dlf + 1e-2))

    area = 100.0 * float(union.sum()) / union.size
    rows = [c[0] for c in clones]
    findings = []
    if clones:
        big = max(rows, key=lambda r: r["area of one copy (% of image)"])
        findings.append((
            "warning",
            f"{len(clones)} duplicated region(s) found: affine-consistent "
            f"matches confirmed by local correlation over {area:.1f} % of the "
            f"image. Largest: {big['copy A centre (x, y)']} matches "
            f"{big['copy B centre (x, y)']} (A to B: rotation "
            f"{big['rotation (deg)']} deg counter-clockwise, scale {big['scale']}"
            f"{', mirrored' if big['mirrored'] else ''}). Which copy is the original cannot be "
            "determined; check the region is not naturally repeated content."))
    else:
        if n_match:
            findings.append((
                "info",
                f"{n_match} SIFT self-matches found, none formed a verified "
                "affine-consistent duplicated region."))
        findings.append((
            "info",
            "Tested SIFT keypoint matching and dense Zernike-moment matching; "
            "no duplicated region found at this sensitivity."))

    return util.make_result(
        "ok",
        "Searched the image for regions duplicated within itself "
        "(copy-move), allowing any shift, rotation and scale.",
        findings=findings,
        metrics={
            "Analysed size (px)": f"{w}x{h}",
            "SIFT keypoints": n_kp,
            "g2NN matches": n_match,
            "Verified clones": len(clones),
            "Duplicated area (% of image)": round(area, 2),
        },
        images={
            "Duplicated regions (green: copy A, red: copy B, yellow: "
            "keypoint matches)": ov,
            "Dense offset-field consistency (bright = locally consistent "
            "offsets, dense-branch scale)": dlf_img,
        },
        tables={"Clone hypotheses (B = scale * R(rotation) * [mirror] * A; "
                "rotation counter-clockwise positive)":
                [{_TABLE_KEYS.get(k, k): v for k, v in r.items()} for r in rows]}
        if rows else {},
        limitations=LIMITATIONS,
        details={
            "scale": float(scale),
            "clones": [{k: (bool(v) if isinstance(v, (bool, np.bool_)) else v)
                        for k, v in r.items()} for r in rows],
            "n_keypoints": int(n_kp),
            "jpeg_quality": quality,
            "n_matches": int(n_match),
            "keypoint_hypotheses": len(kp_hyps),
            "dense_hypotheses": len(dense_hyps),
        },
    ), union
