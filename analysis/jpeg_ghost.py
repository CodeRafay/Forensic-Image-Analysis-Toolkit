"""
JPEG ghosts.

Method: H. Farid, "Exposing Digital Forgeries from JPEG Ghosts", IEEE Trans.
Information Forensics and Security 4(1), 2009.

The image f is recompressed at each quality q; the difference
    d(x, y, q) = mean_{b x b window} [f - f_q]^2
(b = 16) is normalised per pixel across q to [0, 1]. A region that was
compressed at a lower quality q1 before the whole image was saved at its
final quality q2 shows a second minimum ("ghost") at q ≈ q1, while the rest
of the image does not. Deviation from the paper: the difference is taken on
the luminance channel only (decoded Y, recompressed as a greyscale JPEG with
the same IJG luminance table), which is where the quantization traces live
and is a third of the cost.

Grid shift (Farid §3): a ghost only appears when the recompression grid
lines up with the region's earlier JPEG grid. Besides the file's own grid
(0, 0) the image is recompressed at the one other grid offset where the
most blocks sit on a requantization lattice (_offgrid_shift, a DCT-domain
ghost test over all 63 offsets), so a region pasted off the file grid can
still show its ghost.

Farid inspects the normalised maps visually; to decide automatically we
compare d with the same measurement on a grid shifted by (4, 4) px from the
tested one, where an earlier quantization no longer lines up (content
normalisation — without it, smooth content alone produced "ghosts"). A
window is a ghost at q when log(d/d_ref) is far below the image's median at
q; when the median itself is low, the whole image carries the ghost (entire
image double-compressed). A singly-compressed file already sits closer to
its recompression just below its own quality, so the whole-image test
subtracts the median measured on a simulated single compression
(_single_baseline).

The final quality is taken from the stored quantization table
(quant_table.estimate_jpeg_quality), not from the argmin of d, which is
biased to the highest tested quality. Only qualities below it are searched.

Windows are evaluated on an 8-pixel stride (16x16 window = 2x2 blocks), so
maps have one value per 8x8 block.
"""
import io

import numpy as np
from PIL import Image
from scipy.ndimage import binary_opening, label, uniform_filter

from analysis.quant_table import estimate_jpeg_quality, ijg_table
from analysis.util import error_result, make_result, overlay_mask, to_uint8

MIN_RANGE = 1.0     # windows whose d varies less than this over q are flat
# A window is a ghost at q when log(d / d_ref), smoothed over 3x3 windows,
# lies DELTA below the image median at q. Calibrated with MIN_REGION below.
DELTA = 0.7
# Whole-image ghost: median log ratio this far below the simulated single
# compression. Calibration (8 hosts): single q75-95 >= -0.66, whole-image
# double 60->90 and 90->95 <= -2.17.
GLOBAL_LR = 1.0
# Largest ghost component, share of textured windows (hold-out numbers in
# Descriptions/Noise_Ghost.md).
MIN_REGION = 0.03
# Off-grid offset search (_offgrid_shift): a sampled block is on an earlier
# lattice when >= SHIFT_MIN_COEFS of its coefficients lie off the zero cell
# with mean normalised requantization error < SHIFT_ERR.
SHIFT_BLOCKS = 6000
SHIFT_ERR = 0.03      # mean normalised error; 1/12 for unquantized content
SHIFT_MIN_COEFS = 4

LIMITATIONS = [
    "Only finds regions whose earlier compression was at a lower quality "
    "than the final save; q1 ≥ q2 leaves no ghost, and q1 within ~5 of q2 "
    "a weak one.",
    "Besides the file grid only the one strongest other grid offset is "
    "tested; several pasted regions on different off-grid offsets are not "
    "all covered, and an off-grid region whose blocking is weaker than the "
    "file's own (final quality much lower than the region's) is not found.",
    "Flat or saturated regions have no measurable difference at any quality "
    "and are excluded.",
    "Resizing or filtering after the earlier save erases the ghost.",
]


def _luma(path):
    """Stored luminance (no RGB round trip for JPEG), table, format."""
    with Image.open(path) as im:
        fmt = im.format
        qt = getattr(im, "quantization", None) or {}
        if fmt == "JPEG" and im.mode != "L":
            im.draft("YCbCr", im.size)
        if im.mode == "YCbCr":
            y = np.asarray(im)[..., 0]
        else:
            y = np.asarray(im.convert("L"))
    return y, qt, fmt


def _recompress(y8, q):
    buf = io.BytesIO()
    Image.fromarray(y8).save(buf, "JPEG", quality=int(q))
    buf.seek(0)
    with Image.open(buf) as r:
        return np.asarray(r, dtype=np.float32)


def _diff_map(y8, q, dy, dx):
    """Farid's d for the grid starting at (dy, dx): 16x16-window mean of the
    squared recompression error, one value per 8x8 block of that grid."""
    a = y8[dy:, dx:]
    hb, wb = a.shape[0] // 8, a.shape[1] // 8
    a = np.ascontiguousarray(a[:hb * 8, :wb * 8])
    e = (a.astype(np.float32) - _recompress(a, q)) ** 2
    blk = e.reshape(hb, 8, wb, 8).mean(axis=(1, 3))
    return uniform_filter(blk, size=2, mode="nearest")


_C = np.array([[np.sqrt((1 if k == 0 else 2) / 8) * np.cos((2 * n + 1) * k * np.pi / 16)
                for n in range(8)] for k in range(8)], dtype=np.float32)


LOWF = [(u, v) for u in range(8) for v in range(8) if 0 < u + v <= 4]


def _offgrid_shift(y8, qualities):
    """Pick the one off-file-grid offset to test. For each of the 63 grid
    offsets, a fixed subsample of blocks is DCT-transformed and its
    low-frequency AC coefficients outside the zero cell are requantized
    with the IJG luminance table of each tested quality. On an earlier JPEG
    lattice the normalised error ((c - Q round(c/Q)) / Q)^2 is near 0
    instead of 1/12 — the DCT-domain form of Farid's ghost. Returns
    ((dy, dx), excess share of blocks on a lattice over the median
    offset) for the best offset."""
    hb, wb = (y8.shape[0] - 8) // 8, (y8.shape[1] - 8) // 8
    idx = np.arange(hb * wb)[::max(1, hb * wb // SHIFT_BLOCKS)]
    by, bx = 8 * (idx // wb), 8 * (idx % wb)
    o = np.arange(8)
    cu = _C[[u for u, _ in LOWF]]
    cv = _C[[v for _, v in LOWF]]
    tabs = [np.array([ijg_table(q, 0)[u * 8 + v] for u, v in LOWF], np.float32)
            for q in qualities]
    shares = {}
    for dy in range(8):
        for dx in range(8):
            if (dy, dx) == (0, 0):
                continue
            b = y8[(by + dy)[:, None, None] + o[None, :, None],
                   (bx + dx)[:, None, None] + o[None, None, :]].astype(np.float32) - 128
            c = np.einsum("nij,fi,fj->nf", b, cu, cv)
            hit = np.zeros(len(idx), bool)
            for Q in tabs:
                r = c / Q
                m = np.abs(r) >= 0.5
                n = m.sum(1)
                e = (((r - np.round(r)) ** 2) * m).sum(1)
                hit |= (n >= SHIFT_MIN_COEFS) & (e < SHIFT_ERR * n)
            shares[(dy, dx)] = float(hit.mean())
    off = max(shares, key=shares.get)
    # chance hits (few coefficients, small error at some q) set a baseline
    return off, shares[off] - float(np.median(list(shares.values())))


def _ghost_search(y8, qualities, dy, dx, base=None):
    """Recompress on grid (dy, dx) and on its (4, 4)-shifted reference (the
    reference never coincides with the file grid when dy, dx != 0: it then
    uses a 2-px offset). base: {q: median log ratio of a simulated single
    compression}, subtracted before the whole-image test. Returns D, valid,
    best (region, q, mask), whole [(excess, q)], meds {q: median}."""
    ry, rx = (dy + 4) % 8, (dx + 4) % 8
    if (dy, dx) != (0, 0) and (ry, rx) == (0, 0):
        ry, rx = (dy + 2) % 8, (dx + 2) % 8
    D, R = [], []
    for q in qualities:
        D.append(_diff_map(y8, q, dy, dx))
        r = _diff_map(y8, q, ry, rx)
        h, w = min(r.shape[0], D[-1].shape[0]), min(r.shape[1], D[-1].shape[1])
        rr = np.empty_like(D[-1])
        rr[:] = np.median(r)
        rr[:h, :w] = r[:h, :w]
        R.append(rr)
    D, R = np.array(D), np.array(R)                  # (Q, hb, wb)
    lo, hi = D.min(axis=0), D.max(axis=0)
    valid = (hi - lo) >= MIN_RANGE
    best, whole, meds = (0.0, None, None), [], {}
    if valid.mean() < 0.1:
        return D, valid, best, whole, meds
    for i, q in enumerate(qualities):
        lr = uniform_filter(np.log((D[i] + 0.5) / (R[i] + 0.5)), size=3, mode="nearest")
        med = meds[q] = float(np.median(lr[valid]))
        if med - (base or {}).get(q, 0.0) < -GLOBAL_LR:
            whole.append((med - (base or {}).get(q, 0.0), q))  # whole image ghost
            continue
        ghost = binary_opening(valid & (med - lr > DELTA), np.ones((2, 2)))
        lab, n = label(ghost)
        if n:
            sizes = np.bincount(lab.ravel())[1:]
            reg = float(sizes.max() / valid.sum())
            if reg > best[0]:
                best = (reg, q, lab == int(np.argmax(sizes)) + 1)
    return D, valid, best, whole, meds


def _single_baseline(y8, qualities, primary):
    """Median log ratios of a simulated singly-compressed image: a central
    crop (<= 1024 px) taken 4 px off the file grid (old lattices no longer
    line up) and saved once at the final quality. A singly-compressed file
    is closer to its recompression just below its own quality than its
    shifted copy is; this is the level a real earlier save must beat."""
    h, w = y8.shape
    S = min(1024, (h - 8) // 8 * 8, (w - 8) // 8 * 8)
    r0, c0 = (h - S) // 16 * 8 + 4, (w - S) // 16 * 8 + 4
    crop = np.ascontiguousarray(y8[r0:r0 + S, c0:c0 + S])
    sim = _recompress(crop, primary).astype(np.uint8)
    return _ghost_search(sim, qualities, 0, 0)[4]


def analyze_jpeg_ghost(image_path, qualities=range(50, 100, 5)):
    """
    Returns the shared result contract. Metrics: "Primary quality (from
    table)", "Ghost quality", "Ghost region (% of windows)", "Ghost grid
    offset (dy,dx)", "Tested qualities".
    Images: normalised difference at the ghost quality (dark = ghost),
    argmin-quality map, ghost overlay (when found).
    details: {"curve": {q: mean d}, "ghost_q", "region", "primary_q",
    "whole_image_ghost_q", "grid_offset", "tested_offsets"}.
    UI may expose `qualities` (tested range).
    """
    try:
        y8, qt, fmt = _luma(image_path)
        h, w = y8.shape
        if min(h, w) < 64 or y8.std() < 1.0:
            return make_result(
                "insufficient_data",
                f"{w}×{h} image is too small or flat for ghost analysis.",
                [("info", "Needs at least 64×64 px of textured content.")],
                limitations=LIMITATIONS)
        primary = estimate_jpeg_quality(qt[0], 0) if fmt == "JPEG" and 0 in qt else None
        ceiling = (primary if primary is not None else 101) - 1
        qualities = sorted(int(q) for q in qualities if int(q) <= ceiling)
        if not qualities:
            return make_result(
                "insufficient_data",
                f"No tested quality lies below the final quality {primary}.",
                [("info", "Ghosts can only appear below the final quality.")],
                limitations=LIMITATIONS, details={"primary_q": primary})

        # ponytail: the second pass always runs (2x cost); the shift score
        # did not separate negatives from positives well enough to gate it
        # (best-offset excess 0.007-0.042 on clean/double files, 0.013-0.093
        # on off-grid patches) but picked the right offset in ~90 % of them.
        off, share = _offgrid_shift(y8, qualities)
        offsets = [(0, 0), off]
        base = _single_baseline(y8, qualities, primary) if primary is not None else None
        runs = [(o,) + _ghost_search(y8, qualities, *o, base=base) for o in offsets]
        D0, valid0 = runs[0][1], runs[0][2]
        curve = {str(q): round(float(D0[i][valid0].mean()), 3) if valid0.any() else 0.0
                 for i, q in enumerate(qualities)}
        if valid0.mean() < 0.1:
            return make_result(
                "insufficient_data", "Almost no textured windows to compare.",
                [("info", "Recompression changes too few pixels for ghosts.")],
                limitations=LIMITATIONS, details={"curve": curve, "primary_q": primary})

        (gy, gx), D, valid, (region, gq, gmask), _, _ = max(runs, key=lambda r: r[3][0])
        whole = runs[0][4]
        found = region >= MIN_REGION
        metrics = {"Primary quality (from table)": primary if primary is not None else "n/a (no table)",
                   "Tested qualities": f"{qualities[0]}–{qualities[-1]}",
                   "Tested grid offsets": ", ".join(f"({a},{b})" for a, b in offsets),
                   "Ghost region (% of windows)": round(100 * region, 2),
                   "Ghost quality": gq if found else "none",
                   "Ghost grid offset (dy,dx)": f"({gy},{gx})" if found else "-"}
        findings = []
        if primary is None:
            findings.append(("info", f"{fmt} file has no stored quantization "
                                     "table; the test looks for traces of any "
                                     "earlier JPEG compression."))
        else:
            findings.append(("info", f"Final save quality {primary} (from "
                                     "the quantization table); qualities "
                                     f"{qualities[0]}–{qualities[-1]} searched."))
        whole = min(whole)[1] if whole else None
        if whole is not None:
            metrics["Whole-image ghost quality"] = whole
            findings.append((
                "info", f"The whole image is closer to its quality-{whole} "
                        "recompression than its grid-shifted copy is: it was "
                        f"probably saved at about q{whole} (nearest tested "
                        "quality) before the final save (double compression "
                        "of the entire image). Local ghosts at that quality "
                        "are not evaluated."))
        if found:
            ys, xs = np.nonzero(gmask)
            where = "" if (gy, gx) == (0, 0) else (
                f" on an 8×8 grid offset by ({gy},{gx}) px from the file's grid")
            findings.append((
                "warning",
                f"JPEG ghost at quality {gq}{where}: a connected region "
                f"({100 * region:.1f}% of textured windows, rows "
                f"{gy + 8 * ys.min()}–{gy + 8 * ys.max() + 15}, columns "
                f"{gx + 8 * xs.min()}–{gx + 8 * xs.max() + 15} px) is much closer to "
                f"its quality-{gq} recompression than the rest — it was "
                "probably compressed at that lower quality before the final "
                "save (e.g. pasted from another JPEG)."))
        else:
            findings.append((
                "info", f"Tested qualities up to {qualities[-1]} on grid offset(s) "
                        f"{metrics['Tested grid offsets']} for local regions with "
                        "an earlier lower-quality compression; no ghost region at "
                        "this sensitivity."))

        # display at block resolution, scaled to <= ~1200 px
        k = qualities.index(gq) if found else len(qualities) - 1
        hb, wb = D.shape[1:]
        s = max(1, min(8, 1200 // max(hb, wb)))
        up = lambda a: np.kron(a, np.ones((s, s)))  # noqa: E731
        lo, hi = D.min(axis=0), D.max(axis=0)
        N = (D[k] - lo) / np.maximum(hi - lo, 1e-9)
        argq = np.array(qualities)[np.argmin(D, axis=0)]
        images = {
            f"Normalised difference at q={qualities[k]} (dark = ghost)":
                to_uint8(up(np.where(valid, N, 1.0)) * 255, stretch=False),
            "Quality of minimum difference (bright = high q)":
                to_uint8(up(np.where(valid, argq, qualities[-1])).astype(float)),
        }
        if found:
            base = np.asarray(Image.fromarray(np.ascontiguousarray(
                y8[gy:gy + hb * 8, gx:gx + wb * 8])).resize((wb * s, hb * s)))
            images["Ghost region"] = overlay_mask(base, up(gmask))
        return make_result(
            "ok",
            f"Recompressed the luminance at {len(qualities)} qualities on "
            f"{len(offsets)} grid offset(s) and compared 16×16-window "
            "differences (Farid JPEG ghosts).",
            findings, metrics, images, limitations=LIMITATIONS,
            details={"curve": curve, "ghost_q": gq if found else None,
                     "whole_image_ghost_q": whole, "region": region,
                     "primary_q": primary, "grid_offset": [gy, gx] if found else None,
                     "tested_offsets": [list(o) for o in offsets],
                     "offgrid_excess_share": share})
    except Exception as e:  # noqa: BLE001
        return error_result(e, LIMITATIONS)
