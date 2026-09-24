from PIL import Image, ImageChops, ImageEnhance
from pathlib import Path
from io import BytesIO
import numpy as np


def _compute_ghosts(original, quality_steps, on_diff=None):
    """
    Recompress `original` at each quality and diff against it.

    Shared by detect_ghost (in-memory) and detect_jpeg_ghost (writes maps to
    disk) so the compress/diff logic exists once.

    Args:
        original (PIL.Image): RGB source image
        quality_steps (iterable): JPEG qualities to test
        on_diff (callable): Optional hook(quality, diff_image) run per step,
            before the diff is closed

    Returns:
        tuple: (accumulated_ghost PIL.Image or None, {quality: mean_difference})
    """
    difference_scores = {}
    accum = None

    for q in quality_steps:
        buffer = BytesIO()
        original.save(buffer, 'JPEG', quality=q)
        buffer.seek(0)
        resaved = Image.open(buffer)

        diff = ImageChops.difference(original, resaved)
        resaved.close()

        # Score (lower = closer to the quality it was last saved at)
        diff_np = np.asarray(diff, dtype=np.float32)
        difference_scores[q] = float(diff_np.mean())
        del diff_np

        if on_diff is not None:
            on_diff(q, diff)

        # Accumulate for combined visualization
        accum = diff.copy() if accum is None else ImageChops.add(accum, diff)
        diff.close()

    return accum, difference_scores


def _normalize(img):
    """Stretch an image to full range so faint ghosts become visible."""
    extrema = img.getextrema()
    max_diff = max([ex[1] for ex in extrema]) if extrema else 0
    if max_diff > 0:
        return ImageEnhance.Brightness(img).enhance(255.0 / max_diff)
    return img


def _ghost_warnings(difference_scores):
    """Interpret the per-quality scores into forensic warnings."""
    warnings = []
    score_range = max(difference_scores.values()) - \
        min(difference_scores.values())
    min_quality = min(difference_scores, key=difference_scores.get)

    if score_range < 5:
        warnings.append(
            "Very similar scores across all qualities - image may have been resaved many times")

    if difference_scores[min_quality] > 20:
        warnings.append(
            "High difference even at estimated quality - possible multiple edits")

    return warnings, min_quality, score_range


def detect_ghost(image_path, quality_steps=(90, 70, 50)):
    """
    Detects JPEG compression ghosts, returning the visualization in memory.

    Same analysis as detect_jpeg_ghost but writes nothing to disk — use this
    when you want the image object rather than a set of temp file paths.

    Args:
        image_path (str): Path to the image
        quality_steps (tuple): Quality levels to test

    Returns:
        tuple: (ghost_img, analysis)
            - ghost_img (PIL.Image): Combined ghost visualization (None on error)
            - analysis (dict): Detected compression levels and warnings
    """
    try:
        with Image.open(image_path) as img:
            original = img.convert('RGB')

        accum, difference_scores = _compute_ghosts(original, quality_steps)
        original.close()

        warnings, min_quality, score_range = _ghost_warnings(difference_scores)
        ghost_img = _normalize(accum) if accum is not None else None

        return ghost_img, {
            'status': 'success',
            'difference_scores': difference_scores,
            'estimated_last_save_quality': min_quality,
            'quality_confidence': 'high' if score_range > 10 else 'low',
            'warnings': warnings,
            'interpretation': f"Image likely last saved at quality ~{min_quality}. "
                              "Lower difference = closer to original quality.",
        }

    except Exception as e:
        return None, {'status': 'error', 'error': str(e)}


def detect_jpeg_ghost(image_path, quality_steps=(95, 85, 75, 65, 55)):
    """
    Detects JPEG ghost (compression artifacts) by comparing multiple compression levels.
    Helps identify at which quality level the image was previously saved.

    Memory-optimised: single loop instead of double (was compressing 2× per quality).

    Args:
        image_path (str): Path to the image file
        quality_steps (tuple): Quality levels to test (default 95, 85, 75, 65, 55)

    Returns:
        dict: Ghost analysis results with difference maps and quality estimation
    """
    try:
        original = Image.open(image_path).convert('RGB')

        # Create temp directory
        temp_dir = Path(__file__).parent.parent / "temp"
        temp_dir.mkdir(exist_ok=True)

        differences = {}

        def save_map(q, diff):
            """Write the per-quality difference map as we go."""
            diff_path = temp_dir / f'temp_ghost_q{q}.png'
            enhanced = ImageEnhance.Contrast(diff).enhance(3.0)
            enhanced.save(str(diff_path))
            enhanced.close()
            differences[q] = str(diff_path)

        accum, difference_scores = _compute_ghosts(
            original, quality_steps, on_diff=save_map)
        original.close()

        # Enhance and persist the combined visualization
        combined_path = None
        if accum is not None:
            accum = _normalize(accum)
            combined_path = temp_dir / 'temp_ghost_combined.png'
            accum.save(str(combined_path))
            accum.close()

        warnings, min_quality, score_range = _ghost_warnings(difference_scores)

        return {
            'status': 'success',
            'combined_ghost_path': str(combined_path) if combined_path else None,
            'difference_maps': differences,
            'difference_scores': difference_scores,
            'estimated_last_save_quality': min_quality,
            'quality_confidence': 'high' if score_range > 10 else 'low',
            'warnings': warnings,
            'interpretation': f"Image likely last saved at quality ~{min_quality}. Lower difference = closer to original quality."
        }

    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }
