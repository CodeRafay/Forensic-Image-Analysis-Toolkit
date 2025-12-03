from PIL import Image
import cv2
import numpy as np


def resize_image(image_path, max_width=1000, max_height=1000):
    """
    Resizes an image to fit within max dimensions while maintaining aspect ratio.

    Args:
        image_path (str): Path to the image
        max_width (int): Maximum width in pixels
        max_height (int): Maximum height in pixels

    Returns:
        PIL Image object
    """
    try:
        img = Image.open(image_path)
        img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
        return img
    except Exception as e:
        print(f"Error resizing image: {e}")
        return None


def convert_to_grayscale(image_path):
    """
    Converts an image to grayscale.

    Args:
        image_path (str): Path to the image

    Returns:
        PIL Image object in grayscale
    """
    try:
        img = Image.open(image_path)
        return img.convert('L')
    except Exception as e:
        print(f"Error converting to grayscale: {e}")
        return None


def load_image_cv(image_path):
    """
    Loads image using OpenCV (BGR format).

    Args:
        image_path (str): Path to the image

    Returns:
        numpy array or None
    """
    try:
        img = cv2.imread(image_path)
        return img
    except Exception as e:
        print(f"Error loading image with OpenCV: {e}")
        return None


def get_image_info(image_path):
    """
    Retrieves basic information about an image.

    Args:
        image_path (str): Path to the image

    Returns:
        dict: Dictionary with image properties
    """
    try:
        img = Image.open(image_path)
        return {
            "format": img.format,
            "size": img.size,
            "mode": img.mode,
            "width": img.width,
            "height": img.height,
        }
    except Exception as e:
        print(f"Error getting image info: {e}")
        return None
