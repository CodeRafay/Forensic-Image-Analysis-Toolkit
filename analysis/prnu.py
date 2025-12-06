import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter
from pathlib import Path


def analyze_prnu(image_path, reference_image_path=None):
    """
    Analyzes Photo Response Non-Uniformity (PRNU) - sensor fingerprint.
    PRNU is a unique pattern produced by a camera's sensor due to manufacturing imperfections.
    Can be used for camera identification and forgery detection.

    Args:
        image_path (str): Path to the test image
        reference_image_path (str): Optional reference image from same camera

    Returns:
        dict: PRNU analysis results with fingerprint metrics
    """
    try:
        img = Image.open(image_path).convert('RGB')
        img_array = np.array(img, dtype=np.float32)

        # Extract noise residual using Wiener-like filter approach
        # This extracts high-frequency pattern unique to sensor
        prnu_pattern = extract_prnu_pattern(img_array)

        # Calculate PRNU statistics
        prnu_variance = float(np.var(prnu_pattern))
        prnu_mean = float(np.mean(prnu_pattern))
        prnu_std = float(np.std(prnu_pattern))

        # Analyze pattern characteristics
        # Strong PRNU indicates natural camera image
        # Weak or inconsistent PRNU suggests manipulation
        pattern_strength = prnu_variance / \
            (np.mean(np.abs(prnu_pattern)) + 1e-10)

        # Check for local inconsistencies (sign of splicing)
        block_size = 64
        h, w = prnu_pattern.shape[:2]
        block_variances = []

        for i in range(0, h - block_size, block_size):
            for j in range(0, w - block_size, block_size):
                block = prnu_pattern[i:i+block_size, j:j+block_size]
                block_variances.append(np.var(block))

        variance_consistency = float(
            np.std(block_variances) / (np.mean(block_variances) + 1e-10))

        # Generate warnings
        warnings = []

        if prnu_variance < 1.0:
            warnings.append(
                "Very weak PRNU pattern - possible synthetic image or heavy processing")

        if variance_consistency > 1.5:
            warnings.append(
                "Inconsistent PRNU across image - possible splicing or manipulation")

        if pattern_strength < 0.1:
            warnings.append(
                "Low pattern strength - image may have been heavily compressed or filtered")

        result = {
            "status": "success",
            "method": "PRNU Sensor Fingerprint Extraction",
            "image_shape": img_array.shape,
            "metrics": {
                "prnu_variance": prnu_variance,
                "prnu_mean": prnu_mean,
                "prnu_std": prnu_std,
                "pattern_strength": float(pattern_strength),
                "variance_consistency": variance_consistency,
                "blocks_analyzed": len(block_variances)
            },
            "warnings": warnings,
            "interpretation": "Strong, consistent PRNU = authentic camera image; weak/inconsistent = possible manipulation"
        }

        # If reference image provided, compute correlation
        if reference_image_path:
            try:
                ref_img = Image.open(reference_image_path).convert('RGB')
                ref_array = np.array(ref_img, dtype=np.float32)
                ref_prnu = extract_prnu_pattern(ref_array)

                # Resize if dimensions don't match
                if ref_prnu.shape != prnu_pattern.shape:
                    from scipy.ndimage import zoom
                    zoom_factors = (prnu_pattern.shape[0] / ref_prnu.shape[0],
                                    prnu_pattern.shape[1] / ref_prnu.shape[1],
                                    1)
                    ref_prnu = zoom(ref_prnu, zoom_factors)

                # Compute correlation
                correlation = compute_prnu_correlation(prnu_pattern, ref_prnu)

                result["reference_analysis"] = {
                    "correlation": float(correlation),
                    "same_camera_likelihood": "High" if correlation > 0.7 else "Medium" if correlation > 0.4 else "Low",
                    "interpretation": "Correlation > 0.7 suggests same camera; < 0.3 suggests different cameras"
                }

            except Exception as e:
                result["reference_analysis"] = {"error": str(e)}

        return result

    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


def extract_prnu_pattern(img_array):
    """
    Extracts PRNU pattern from image using noise residual extraction.

    Args:
        img_array (np.array): RGB image array

    Returns:
        np.array: PRNU noise pattern
    """
    # Denoise each channel separately
    channels = []
    for c in range(img_array.shape[2]):
        channel = img_array[:, :, c]

        # Apply Gaussian filter to get denoised version
        denoised = gaussian_filter(channel, sigma=2.0)

        # Noise residual = original - denoised
        noise = channel - denoised

        channels.append(noise)

    # Combine channels
    prnu_pattern = np.stack(channels, axis=2)

    return prnu_pattern


def compute_prnu_correlation(prnu1, prnu2):
    """
    Computes correlation between two PRNU patterns.

    Args:
        prnu1 (np.array): First PRNU pattern
        prnu2 (np.array): Second PRNU pattern

    Returns:
        float: Correlation coefficient (0-1)
    """
    # Flatten arrays
    p1_flat = prnu1.flatten()
    p2_flat = prnu2.flatten()

    # Normalize
    p1_norm = (p1_flat - np.mean(p1_flat)) / (np.std(p1_flat) + 1e-10)
    p2_norm = (p2_flat - np.mean(p2_flat)) / (np.std(p2_flat) + 1e-10)

    # Compute correlation
    correlation = np.abs(np.corrcoef(p1_norm, p2_norm)[0, 1])

    return correlation
