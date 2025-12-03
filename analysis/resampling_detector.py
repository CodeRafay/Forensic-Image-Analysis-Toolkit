import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter


def detect_resampling(image_path):
    """
    Detects resampling artifacts (upsampling/downsampling) which indicate image resizing.
    Resampling leaves periodic patterns and interpolation artifacts.

    Args:
        image_path (str): Path to image file

    Returns:
        dict: Resampling detection results
    """
    try:
        img = Image.open(image_path).convert('L')
        img_array = np.array(img, dtype=np.float32)

        # Apply high-pass filter to detect resampling artifacts
        blurred = gaussian_filter(img_array, sigma=1.0)
        high_pass = img_array - blurred

        # Analyze periodicity in residuals (resampling creates periodic patterns)
        from scipy.fft import fft2, fftshift
        fft_result = fft2(high_pass)
        magnitude = np.abs(fftshift(fft_result))

        # Look for peak concentration (indicates periodic patterns from resampling)
        h, w = magnitude.shape
        center_h, center_w = h // 2, w // 2

        # Sample rings at different radii
        peak_count = 0
        magnitude_threshold = np.percentile(magnitude, 95)

        for r in range(5, min(center_h, center_w), 15):
            y, x = np.ogrid[:h, :w]
            distance = np.sqrt((y - center_h)**2 + (x - center_w)**2)
            mask = (distance >= r) & (distance < r + 5)

            if np.any(magnitude[mask] > magnitude_threshold):
                peak_count += 1

        # Calculate resampling likelihood
        resampling_score = peak_count / \
            max(1, (min(center_h, center_w) - 5) // 15)

        result = {
            "status": "analysis_complete",
            "method": "Resampling Detection via Periodicity Analysis",
            "image_size": img_array.shape,
            "resampling_score": float(resampling_score),
            "interpretation": "Score > 0.5 suggests likely resampling; < 0.3 suggests natural resolution",
            "artifacts_detected": peak_count
        }

        return result

    except Exception as e:
        return {"error": str(e), "status": "analysis_failed"}


def detect_interpolation_method(image_path):
    """
    Attempts to detect which interpolation method was used (nearest neighbor, bilinear, etc).
    Different interpolation methods leave characteristic fingerprints.

    Args:
        image_path (str): Path to image file

    Returns:
        dict: Interpolation method analysis
    """
    try:
        img = Image.open(image_path).convert('L')
        img_array = np.array(img, dtype=np.float32)

        # Analyze local pixel relationships
        # Nearest neighbor: sharp pixel blocks
        # Bilinear: smoother gradients
        # Bicubic: smoother still with possible ringing

        # Calculate gradient statistics
        from scipy.ndimage import sobel
        gradient_x = sobel(img_array, axis=1)
        gradient_y = sobel(img_array, axis=0)
        gradient_magnitude = np.sqrt(gradient_x**2 + gradient_y**2)

        # Analyze directional consistency
        gradient_std = np.std(gradient_magnitude)
        gradient_mean = np.mean(gradient_magnitude)

        # Look for ringing artifacts (characteristic of bicubic)
        laplacian = sobel(gradient_magnitude)
        ringing_score = np.std(laplacian)

        # Classify based on characteristics
        if gradient_std < 5:
            likely_method = "Nearest Neighbor (blocky)"
        elif ringing_score < 10:
            likely_method = "Bilinear (smooth)"
        else:
            likely_method = "Bicubic or higher-order (possible ringing)"

        result = {
            "status": "analysis_complete",
            "method": "Interpolation Method Classification",
            "gradient_std": float(gradient_std),
            "ringing_score": float(ringing_score),
            "likely_interpolation": likely_method,
            "confidence": "Low - this is a heuristic classifier"
        }

        return result

    except Exception as e:
        return {"error": str(e), "status": "analysis_failed"}
