import numpy as np
from PIL import Image


def analyze_prnu(image_path, reference_image_path=None):
    """
    Analyzes Photo Response Non-Uniformity (PRNU) - sensor fingerprint.
    PRNU is a unique pattern produced by a camera's sensor.

    Args:
        image_path (str): Path to the test image
        reference_image_path (str): Optional reference image from same camera

    Returns:
        dict: PRNU analysis results
    """
    try:
        img = Image.open(image_path).convert('RGB')
        img_array = np.array(img, dtype=np.float32)

        # Extract noise residual (simplified Wiener filter approach)
        from scipy.ndimage import gaussian_filter
        blurred = gaussian_filter(img_array, sigma=2)
        noise_residual = img_array - blurred

        # Calculate PRNU statistics
        prnu_variance = np.var(noise_residual)
        prnu_mean = np.mean(noise_residual)

        result = {
            "status": "analysis_complete",
            "method": "Simplified PRNU Extraction",
            "image_shape": img_array.shape,
            "noise_residual_variance": float(prnu_variance),
            "noise_residual_mean": float(prnu_mean),
            "interpretation": "PRNU analysis complete - variance indicates sensor fingerprint strength"
        }

        if reference_image_path:
            result["reference_image"] = "Reference image processing pending"

        return result

    except Exception as e:
        return {"error": str(e), "status": "analysis_failed"}
