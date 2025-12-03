from PIL import Image, ImageChops, ImageEnhance
from pathlib import Path


def detect_ghost(image_path, quality_steps=(90, 70, 50)):
    """
    Detects JPEG ghost (compression artifacts) by comparing multiple compression levels.

    Args:
        image_path (str): Path to the image file
        quality_steps (tuple): Quality levels to test (default 90, 70, 50)

    Returns:
        PIL Image object showing compression artifacts, or None on error
    """
    try:
        original = Image.open(image_path).convert('RGB')

        # Create temp directory
        temp_dir = Path(__file__).parent.parent / "temp"
        temp_dir.mkdir(exist_ok=True)

        accum = None

        # Accumulate differences across quality levels
        for q in quality_steps:
            out = temp_dir / f'temp_ghost_q{q}.jpg'
            original.save(str(out), 'JPEG', quality=q)
            resaved = Image.open(str(out))
            diff = ImageChops.difference(original, resaved)

            if accum is None:
                accum = diff
            else:
                accum = ImageChops.add(accum, diff)

        if accum is None:
            return original

        # Enhance contrast
        extrema = accum.getextrema()
        max_diff = max([ex[1] for ex in extrema]) if extrema else 0
        scale = 255.0 / max_diff if max_diff != 0 else 1
        accum = ImageEnhance.Brightness(accum).enhance(scale)

        return accum

    except Exception as e:
        print(f"Error in JPEG ghost detection: {e}")
        return None
