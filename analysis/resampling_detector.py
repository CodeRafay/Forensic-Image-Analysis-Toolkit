"""
Resampling Detection
====================
Detects whether an image has been rescaled, and recovers the scale factor.

Method (Gallagher 2005; Popescu & Farid 2005): interpolation makes every
output pixel a fixed linear combination of its neighbours, and which
combination is used cycles with a period set by the scale factor. That leaves
the *variance of the second derivative* periodic along the resampled axis. A
never-resampled image has no such periodicity.

Measured on the bundled sample image, the dominant peak lands at exactly
`1 - 1/s` for a scale factor `s` (1.25 -> 0.200, 1.5 -> 0.333, 1.9 -> 0.474),
which is what makes the scale factor recoverable rather than just detectable.
"""

import numpy as np
from PIL import Image

# Search band for the periodicity peak, in cycles/pixel.
#
# Chosen from measurement, not guessed. Genuine resampling peaks at 1 - 1/s,
# which spans 0.048 (s=1.05) to 0.474 (s=1.9) before aliasing folds larger
# factors back into the same range. Natural image structure peaks near 0.019,
# below the band. Restricting to this range discards no real detection and
# removes the natural low-frequency floor: on the sample image it drops a clean
# photo from 35.7 to 17.5 while every true detection stays above 100.
FREQ_LO, FREQ_HI = 0.04, 0.49

# Peak prominence (in MAD units above the in-band median) treated as evidence
# of resampling. Measured: clean 17.5, downscaled 9.3, integer 2x 21.0, versus
# 103-361 for detected fractional rescaling.
DETECTION_THRESHOLD = 50.0

# Prominence mapped onto the 0-1 score
_SCORE_FLOOR, _SCORE_CEIL = 20.0, 150.0


def _second_derivative_profiles(gray):
    """
    Collapse the image to one 1-D profile per axis.

    Returns:
        dict: {'horizontal': profile, 'vertical': profile}
    """
    g = np.asarray(gray, dtype=np.float64)
    return {
        # Second difference across columns, averaged down the rows
        "horizontal": np.abs(g[:, :-2] - 2 * g[:, 1:-1] + g[:, 2:]).mean(axis=0),
        "vertical": np.abs(g[:-2, :] - 2 * g[1:-1, :] + g[2:, :]).mean(axis=1),
    }


def _spectral_peak(profile, lo=FREQ_LO, hi=FREQ_HI):
    """
    Strongest periodic component of a profile within the search band.

    Prominence is measured against the band's median using the median absolute
    deviation, so it is robust to the handful of large bins a real peak creates
    (a mean/std normalisation would be inflated by the very peak it measures).

    Returns:
        tuple: (prominence, frequency in cycles/pixel)
    """
    signal = np.asarray(profile, dtype=np.float64)
    n = signal.size
    if n < 32:
        return 0.0, 0.0

    centred = signal - signal.mean()
    spectrum = np.abs(np.fft.rfft(centred * np.hanning(n)))
    freqs = np.arange(spectrum.size) / (2 * (spectrum.size - 1))

    band = (freqs >= lo) & (freqs <= hi)
    if band.sum() < 8:
        return 0.0, 0.0

    values, band_freqs = spectrum[band], freqs[band]
    median = np.median(values)
    mad = np.median(np.abs(values - median)) + 1e-9

    peak = int(np.argmax(values))
    return float((values[peak] - median) / mad), float(band_freqs[peak])


def _scale_candidates(frequency):
    """
    Scale factors consistent with an observed peak frequency.

    The signature sits at `1 - 1/s`. Once that exceeds 0.5 it aliases back
    below Nyquist, so an observed frequency f admits two readings: the direct
    one, 1/(1-f), and the aliased one, 1/f. Both are returned because the
    ambiguity is real — a 1.5x and a 3.0x enlargement both peak at 0.333.
    """
    if not 0 < frequency < 1:
        return []

    candidates = []
    for value in (1.0 / (1.0 - frequency), 1.0 / frequency):
        if 1.01 <= value <= 16.0:
            candidates.append(round(value, 3))

    # Deduplicate while preserving order
    return sorted(set(candidates))


def detect_resampling(image_path):
    """
    Detects whether an image has been rescaled and estimates by how much.

    Args:
        image_path (str): Path to image file

    Returns:
        dict: Detection result including `resampling_detected`,
            `resampling_score` (0-1), the recovered scale-factor candidates and
            the axis the evidence came from.
    """
    try:
        with Image.open(image_path) as img:
            gray = np.asarray(img.convert("L"), dtype=np.float64)

        if gray.shape[0] < 32 or gray.shape[1] < 32:
            return {
                "status": "analysis_complete",
                "method": "Second-derivative periodicity (Gallagher)",
                "image_size": gray.shape,
                "resampling_detected": False,
                "resampling_score": 0.0,
                "interpretation": "Image is too small to test for resampling periodicity.",
            }

        profiles = _second_derivative_profiles(gray)

        per_axis = {}
        for axis, profile in profiles.items():
            prominence, frequency = _spectral_peak(profile)
            per_axis[axis] = {
                "peak_prominence": round(prominence, 2),
                "peak_frequency": round(frequency, 4),
                "scale_candidates": _scale_candidates(frequency),
            }

        strongest = max(per_axis, key=lambda a: per_axis[a]["peak_prominence"])
        best = per_axis[strongest]
        prominence = best["peak_prominence"]

        detected = prominence >= DETECTION_THRESHOLD
        score = (prominence - _SCORE_FLOOR) / (_SCORE_CEIL - _SCORE_FLOOR)
        score = float(min(1.0, max(0.0, score)))

        if detected:
            candidates = best["scale_candidates"]
            if candidates:
                shown = " or ".join(f"{c:g}x" for c in candidates)
                verdict = (f"Resampling detected along the {strongest} axis. "
                           f"Scale factor is consistent with {shown} "
                           f"(the two readings are indistinguishable from the "
                           f"periodicity alone).")
            else:
                verdict = (f"Resampling detected along the {strongest} axis, "
                           f"but the scale factor could not be resolved.")
        else:
            verdict = ("No resampling periodicity found. Note the blind spots "
                       "below before reading this as 'not resized'.")

        return {
            "status": "analysis_complete",
            "method": "Second-derivative periodicity (Gallagher)",
            "image_size": gray.shape,
            "resampling_detected": bool(detected),
            "resampling_score": round(score, 3),
            "peak_prominence": prominence,
            "detected_axis": strongest if detected else None,
            "estimated_scale_factors": best["scale_candidates"] if detected else [],
            "per_axis": per_axis,
            "detection_threshold": DETECTION_THRESHOLD,
            "interpretation": verdict,
            "limitations": [
                "Integer scale factors (exactly 2x, 3x...) are a blind spot: the "
                "signature lands on the Nyquist limit and cannot be separated.",
                "Downscaling is largely undetectable - it discards samples rather "
                "than manufacturing correlated ones.",
                "Heavy JPEG compression after resizing can erase the periodicity.",
                "A negative result is weak evidence; a positive result is strong.",
            ],
        }

    except Exception as e:
        return {"error": str(e), "status": "analysis_failed"}


def detect_interpolation_method(image_path):
    """
    Identifies the interpolation kernel, where the evidence supports it.

    Nearest-neighbour is separable: it copies pixels rather than blending them,
    so duplicated columns and rows land on a regular lattice. The smooth kernels
    are not reliably separable from one another. Measured on the sample image,
    overshoot orders them correctly every time (bilinear 0.079 < bicubic 0.104 <
    lanczos 0.115) but the margins are ~0.02 and shift with image content, so
    this reports the family and an ordering hint rather than asserting one name.

    Args:
        image_path (str): Path to image file

    Returns:
        dict: Classification with an explicit confidence level
    """
    try:
        with Image.open(image_path) as img:
            gray = np.asarray(img.convert("L"), dtype=np.float64)

        if gray.shape[0] < 32 or gray.shape[1] < 32:
            return {
                "status": "analysis_complete",
                "method": "Interpolation kernel classification",
                "likely_interpolation": "Undetermined (image too small)",
                "confidence": "None",
            }

        # Duplication rate: share of neighbouring pairs that are exactly equal
        dup_rate = float(np.mean([
            (np.diff(gray, axis=1) == 0).mean(),
            (np.diff(gray, axis=0) == 0).mean(),
        ]))

        # Duplication periodicity: nearest-neighbour repeats whole columns on a
        # fixed lattice, so the per-column duplication rate is itself periodic.
        # The raw rate alone is content-dependent (a blurred photo duplicates
        # heavily on its own); the periodicity is what identifies the lattice.
        column_dup = (np.diff(gray, axis=1) == 0).mean(axis=0)
        dup_periodicity, _ = _spectral_peak(column_dup, lo=0.02, hi=0.49)

        # Overshoot: cubic and windowed-sinc kernels have negative lobes, so
        # they ring past the values they interpolate between.
        centre, left, right = gray[:, 1:-1], gray[:, :-2], gray[:, 2:]
        overshoot = float((((centre - left) * (centre - right) > 0)
                           & (np.abs(2 * centre - left - right) > 8)).mean())

        resampling = detect_resampling(image_path)
        is_resampled = resampling.get("resampling_detected", False)

        if not is_resampled and dup_periodicity < 200:
            likely, confidence = "No resampling detected - kernel not applicable", "N/A"
        elif dup_rate > 0.40 and dup_periodicity > 200:
            likely, confidence = "Nearest Neighbour (pixels duplicated on a lattice)", "High"
        elif overshoot > 0.10:
            likely, confidence = (
                "Smooth kernel with ringing - bicubic or Lanczos more likely than bilinear",
                "Low")
        else:
            likely, confidence = (
                "Smooth kernel without strong ringing - bilinear more likely than bicubic",
                "Low")

        return {
            "status": "analysis_complete",
            "method": "Interpolation kernel classification",
            "likely_interpolation": likely,
            "confidence": confidence,
            "duplication_rate": round(dup_rate, 4),
            "duplication_periodicity": round(dup_periodicity, 1),
            "overshoot_ratio": round(overshoot, 4),
            "note": ("Nearest-neighbour is identified reliably. Bilinear, bicubic "
                     "and Lanczos are not reliably separable from one another on a "
                     "single image - treat any choice between them as a hint."),
        }

    except Exception as e:
        return {"error": str(e), "status": "analysis_failed"}
