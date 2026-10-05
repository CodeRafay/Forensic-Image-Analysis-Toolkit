"""
Histogram analysis: contrast-enhancement fingerprint.

M. C. Stamm and K. J. R. Liu, "Forensic detection of image manipulation using
statistical intrinsic fingerprints", IEEE Trans. Information Forensics and
Security 5(3), 2010. A pixel-value mapping (gamma, linear stretch, histogram
equalisation) applied to an 8-bit image leaves impulsive peaks and gaps in the
histogram, which add high-frequency energy to the histogram's DFT. Unaltered
camera images have smooth histograms. The detector:

    g(x) = h(x) p(x)          p = pinch-off window (N = 8) that suppresses
                              saturation spikes at 0 and 255
    G(k) = DFT(g) / sum(g)
    F    = mean_{c <= k <= 128} |G(k)|

and F > ETA flags a channel. Run on the stored pixels at full resolution.
"""
import numpy as np
from PIL import Image

from analysis.util import error_result, fig_to_array, load_array, make_result

PINCH_N = 8       # pinch-off width (paper value)
CUTOFF = 112      # first high-frequency DFT bin c (paper value; c=32/64
                  # let smooth narrow histograms of dark photos through)
# ETA calibrated on 16 photos (sample + skimage), max F over channels:
#   negatives (96): PNG, JPEG q70-100, 0.5x area-downscaled, dark (x0.3 +
#     sensor-like noise) and bright variants -> max 8e-3 except skimage
#     'retina' (mostly black background, spike near 10: 33-39e-3, 5/96
#     flagged -> FPR 5.2 %, 0/90 on the other 15 photos).
#   positives saved lossless: gamma 0.7 15/16, gamma 1.4 13/16, 2-98 %
#     linear stretch 14/16, histogram equalisation 16/16 (TPR 91 %).
#   same positives saved as JPEG q90: 1-3/16 each (fingerprint smoothed).
ETA = 0.020
TAIL_PCT = 0.1    # gaps are counted inside the 0.1-99.9 percentile range

LIMITATIONS = [
    "Detects global pixel-value mappings (gamma, levels/curves, stretch, "
    "equalisation); local edits, splicing and geometric changes leave the "
    "histogram smooth.",
    "JPEG compression after the enhancement smooths the histogram and "
    "weakens the fingerprint, especially at quality < 90.",
    "Linear gains whose gap pattern repeats every 3-5 values (e.g. x1.25, "
    "x1.5, x3) put their energy below the DFT cutoff and are missed "
    "(measured F 2.7-8.9e-3 vs threshold 20e-3); gains 1.2, 1.7, 2 are "
    "detected.",
    "Contrast reduction (mapping many values onto fewer) and mappings "
    "followed by resizing or noise addition are harder to see.",
    "Synthetic graphics, screenshots, images with very few distinct "
    "values or a large uniform background (one dominant value) have spiky "
    "histograms without any enhancement.",
]


def pinch_window(n=PINCH_N):
    x = np.arange(256, dtype=np.float64)
    p = np.ones(256)
    lo, hi = x <= n, x >= 255 - n
    p[lo] = 0.5 - 0.5 * np.cos(np.pi * x[lo] / n)
    p[hi] = 0.5 + 0.5 * np.cos(np.pi * (x[hi] - 255 + n) / n)
    return p


_P = pinch_window()


def hf_energy(hist):
    """Stamm & Liu high-frequency histogram energy F (0 for a flat input)."""
    g = np.asarray(hist, np.float64) * _P
    s = g.sum()
    if s <= 0:
        return 0.0
    G = np.abs(np.fft.fft(g / s))
    return float(G[CUTOFF:129].mean())


def interior_gaps(hist):
    """Empty bins strictly inside the channel's occupied (0.1-99.9 %) range."""
    c = np.cumsum(hist) / max(hist.sum(), 1)
    lo = int(np.searchsorted(c, TAIL_PCT / 100))
    hi = int(np.searchsorted(c, 1 - TAIL_PCT / 100))
    return int((hist[lo:hi + 1] == 0).sum()), lo, hi


def _plot(hists, names, colors):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9, 3.6))
    for h, n, c in zip(hists, names, colors):
        ax.plot(np.arange(256), h / h.sum() * 100, color=c, lw=0.9, label=n)
    ax.set_xlim(0, 255)
    ax.set_xlabel("pixel value")
    ax.set_ylabel("% of pixels")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(alpha=0.3)
    return fig_to_array(fig)


def analyze_histogram(image_path):
    """
    Per-channel histogram statistics and the Stamm & Liu contrast-enhancement
    detector. Images: histogram plot. Metrics: F per channel, interior gaps
    per channel, clipped % at 0/255.
    """
    try:
        # uint8 straight from the decoder (a float RGB copy was 864 MB at
        # 12 MP); 16-bit files go through load_array's rescale.
        with Image.open(image_path) as im:
            if im.mode in ("I;16", "I;16B", "I;16L", "I"):
                u8 = load_array(image_path, "RGB")[0].astype(np.uint8)
            else:
                u8 = np.asarray(im.convert("RGB"))
        h, w = u8.shape[:2]
        gray = bool((u8[..., 0] == u8[..., 1]).all()
                    and (u8[..., 1] == u8[..., 2]).all())
        chans = [("Luma", u8[..., 0], "k")] if gray else [
            ("Red", u8[..., 0], "r"), ("Green", u8[..., 1], "g"),
            ("Blue", u8[..., 2], "b")]
        if h * w < 64 * 64 or u8[::4, ::4].std() < 1.0:
            return make_result(
                "insufficient_data",
                f"Image is {w}x{h} px or nearly uniform; the histogram test "
                "needs at least 64x64 px of varying content.",
                limitations=LIMITATIONS)

        findings, metrics, rows, hists, flagged = [], {}, [], [], []
        for name, ch, _ in chans:
            hist = np.bincount(ch.ravel(), minlength=256).astype(np.float64)
            hists.append(hist)
            F = hf_energy(hist)
            gaps, lo, hi = interior_gaps(hist)
            v = np.arange(256)
            mu = float((hist * v).sum() / hist.sum())  # stats from the histogram:
            sd = float(np.sqrt((hist * (v - mu) ** 2).sum() / hist.sum()))  # no pixel copies
            c0, c255 = hist[0] / hist.sum() * 100, hist[255] / hist.sum() * 100
            metrics[f"{name} HF energy F (x1000)"] = round(F * 1000, 2)
            metrics[f"{name} empty bins inside occupied range"] = gaps
            rows.append({"channel": name, "F (x1000)": round(F * 1000, 2),
                         "occupied range": f"{lo}-{hi}", "interior gaps": gaps,
                         "at 0 (%)": round(c0, 2), "at 255 (%)": round(c255, 2),
                         "mean": round(mu, 1), "std": round(sd, 1)})
            if F > ETA:
                flagged.append(f"{name} (F={F * 1000:.1f}e-3)")
            for v, pct in ((0, c0), (255, c255)):
                if pct > 1.0:
                    findings.append(("info", f"{name}: {pct:.1f}% of pixels "
                                     f"are clipped at {v} (exposure or "
                                     "processing; not by itself an edit)."))

        eta_txt = f"{ETA * 1000:g}e-3"
        if flagged:
            findings.insert(0, (
                "warning",
                "Histogram shows the peak/gap fingerprint of a pixel-value "
                f"mapping (Stamm & Liu F above {eta_txt}) in: "
                f"{', '.join(flagged)}. Consistent with gamma/levels/curves or "
                "equalisation applied after capture."))
        else:
            findings.insert(0, (
                "info",
                "Tested for the contrast-enhancement fingerprint (Stamm & Liu "
                f"HF energy F > {eta_txt}): no inconsistency found at this "
                "sensitivity."))
        return make_result(
            "ok",
            f"Measured the {len(chans)}-channel histogram of all {w}x{h} "
            "pixels and its high-frequency energy.",
            findings, metrics,
            {"Histogram (% of pixels per value)":
                _plot(hists, [c[0] for c in chans], [c[2] for c in chans])},
            {"Per-channel statistics": rows}, LIMITATIONS,
            details={"F": {r["channel"]: r["F (x1000)"] / 1000 for r in rows},
                     "eta": ETA, "flagged": bool(flagged), "channels": rows})
    except Exception as e:  # noqa: BLE001
        return error_result(e, LIMITATIONS)
