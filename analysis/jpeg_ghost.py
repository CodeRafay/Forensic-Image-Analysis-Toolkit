from PIL import Image, ImageChops, ImageEnhance
from pathlib import Path
from io import BytesIO
import numpy as np


def detect_jpeg_ghost(image_path, quality_steps=(95, 85, 75, 65, 55)):
    """
    Detects JPEG ghost (compression artifacts) by comparing multiple compression levels.
    Helps identify at which quality level the image was previously saved.

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
        difference_scores = {}

        # Test each quality level
        for q in quality_steps:
            # Use in-memory compression
            buffer = BytesIO()
            original.save(buffer, 'JPEG', quality=q)
            buffer.seek(0)
            resaved = Image.open(buffer)

            # Calculate difference
            diff = ImageChops.difference(original, resaved)
            diff_array = np.array(diff)

            # Store difference score (lower = likely previous quality)
            score = float(np.mean(diff_array))
            difference_scores[q] = score

            # Save difference map
            diff_path = temp_dir / f'temp_ghost_q{q}.png'

            # Enhance for visibility
            enhanced = ImageEnhance.Contrast(diff).enhance(3.0)
            enhanced.save(str(diff_path))
            differences[q] = str(diff_path)

        # Find quality with minimum difference (likely original quality)
        min_quality = min(difference_scores, key=difference_scores.get)

        # Create combined ghost visualization
        accum = None
        for q in quality_steps:
            buffer = BytesIO()
            original.save(buffer, 'JPEG', quality=q)
            buffer.seek(0)
            resaved = Image.open(buffer)
            diff = ImageChops.difference(original, resaved)

            if accum is None:
                accum = diff
            else:
                accum = ImageChops.add(accum, diff)

        # Enhance contrast for visibility
        if accum:
            extrema = accum.getextrema()
            max_diff = max([ex[1] for ex in extrema]) if extrema else 1
            if max_diff > 0:
                scale = 255.0 / max_diff
                accum = ImageEnhance.Brightness(accum).enhance(scale)

            combined_path = temp_dir / 'temp_ghost_combined.png'
            accum.save(str(combined_path))
        else:
            combined_path = None

        # Analyze compression history
        warnings = []
        score_range = max(difference_scores.values()) - \
            min(difference_scores.values())

        if score_range < 5:
            warnings.append(
                "Very similar scores across all qualities - image may have been resaved many times")

        if difference_scores[min_quality] > 20:
            warnings.append(
                "High difference even at estimated quality - possible multiple edits")

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
