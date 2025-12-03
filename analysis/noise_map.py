from PIL import Image, ImageFilter, ImageChops


def generate_noise_map(image_path):
    """
    Generates a noise map by detecting high-frequency components.

    Args:
        image_path (str): Path to the image file

    Returns:
        PIL Image object representing noise map, or None on error
    """
    try:
        img = Image.open(image_path).convert('L')

        # Apply Gaussian blur to smooth the image
        blurred = img.filter(ImageFilter.GaussianBlur(radius=2))

        # Calculate difference (high-pass filter effect)
        diff = ImageChops.difference(img, blurred)

        # Enhance contrast to highlight noise
        diff = ImageChops.add(diff, diff)

        return diff

    except Exception as e:
        print(f"Error in noise map generation: {e}")
        return None
