import numpy as np
from PIL import Image


def detect_deepfake_artifacts(image_path):
    """
    Detects common deepfake/GAN artifacts:
    - Blurry boundaries between face and background
    - Unnatural skin texture
    - Inconsistent lighting
    - Face warping artifacts

    Args:
        image_path (str): Path to image file

    Returns:
        dict: Deepfake artifact detection results
    """
    try:
        img = Image.open(image_path).convert('RGB')
        img_array = np.array(img, dtype=np.float32)

        # Check for common GAN artifacts
        # 1. Frequency anomalies (GANs produce artifacts in specific frequency bands)
        from scipy.fft import fft2, fftshift

        gray = np.mean(img_array, axis=2)
        fft_result = fft2(gray)
        magnitude = np.abs(fftshift(fft_result))

        # Analyze specific frequency bands used by GANs
        h, w = magnitude.shape
        center_h, center_w = h // 2, w // 2

        # High frequency analysis (often shows GAN artifacts)
        high_freq_ring = magnitude[center_h -
                                   20:center_h+20, center_w-20:center_w+20]
        high_freq_variance = np.var(high_freq_ring)

        # 2. Texture consistency check
        # GANs often produce subtle texture inconsistencies
        r, g, b = img_array[:, :, 0], img_array[:, :, 1], img_array[:, :, 2]

        # Channel correlation
        rg_correlation = np.corrcoef(r.flatten(), g.flatten())[0, 1]
        rb_correlation = np.corrcoef(r.flatten(), b.flatten())[0, 1]
        gb_correlation = np.corrcoef(g.flatten(), b.flatten())[0, 1]

        avg_channel_correlation = np.mean(
            [rg_correlation, rb_correlation, gb_correlation])

        # 3. Boundary blur detection
        # Calculate gradient magnitude
        from scipy.ndimage import sobel
        gradient_x = sobel(gray, axis=1)
        gradient_y = sobel(gray, axis=0)
        gradient_magnitude = np.sqrt(gradient_x**2 + gradient_y**2)

        # High gradient at edges is natural; too uniform suggests blurring
        edge_sharpness = np.std(gradient_magnitude)

        result = {
            "status": "analysis_complete",
            "method": "GAN/Deepfake Artifact Detection",
            "image_size": img_array.shape,
            "artifacts": {
                "frequency_anomaly_score": float(high_freq_variance),
                "channel_correlation_score": float(avg_channel_correlation),
                "edge_sharpness_score": float(edge_sharpness)
            },
            "interpretation": "Scores help identify GAN-generated or deepfake artifacts",
            "note": "This is a simplified heuristic detector; professional deepfake detection requires deep learning models"
        }

        return result

    except Exception as e:
        return {"error": str(e), "status": "analysis_failed"}


def detect_gan_fingerprint(image_path):
    """
    Detects specific fingerprints left by popular GAN architectures (StyleGAN, ProGAN, etc).
    GANs leave characteristic patterns in the frequency domain.

    Args:
        image_path (str): Path to image file

    Returns:
        dict: GAN fingerprint detection results with radial frequency analysis
    """
    try:
        img = Image.open(image_path).convert('RGB')
        img_array = np.array(img, dtype=np.float32)

        # Analyze spectral properties unique to GANs
        from scipy.fft import fft2, fftshift

        gray = np.mean(img_array, axis=2)
        fft_result = fft2(gray)
        magnitude = np.abs(fftshift(fft_result))

        # Apply log scale for better visualization
        magnitude_log = np.log(magnitude + 1)

        # Look for characteristic "blob" patterns in frequency domain
        h, w = magnitude.shape
        center_h, center_w = h // 2, w // 2

        # Radial frequency analysis (GANs produce specific radial patterns)
        y, x = np.ogrid[:h, :w]
        distance = np.sqrt((y - center_h)**2 + (x - center_w)**2)

        # Sample radial profile at different frequencies
        max_radius = min(center_h, center_w)
        radial_bins = 50
        radial_profile = []
        radial_profile_normalized = []

        for i in range(radial_bins):
            r_inner = int(i * max_radius / radial_bins)
            r_outer = int((i + 1) * max_radius / radial_bins)

            mask = (distance >= r_inner) & (distance < r_outer)
            if np.any(mask):
                avg_magnitude = np.mean(magnitude_log[mask])
                radial_profile.append(float(avg_magnitude))

        # Normalize radial profile
        if radial_profile:
            profile_array = np.array(radial_profile)
            profile_normalized = (
                profile_array - np.mean(profile_array)) / (np.std(profile_array) + 1e-10)
            radial_profile_normalized = profile_normalized.tolist()

        # Analyze characteristics
        radial_variance = float(np.var(radial_profile)
                                ) if radial_profile else 0

        # Look for periodic peaks (characteristic of GANs)
        peak_count = 0
        if len(radial_profile) > 3:
            for i in range(1, len(radial_profile) - 1):
                if radial_profile[i] > radial_profile[i-1] and radial_profile[i] > radial_profile[i+1]:
                    if radial_profile[i] > np.mean(radial_profile) + np.std(radial_profile):
                        peak_count += 1

        # GAN likelihood assessment
        gan_score = 0
        gan_indicators = []

        if radial_variance > 1.5:
            gan_score += 0.3
            gan_indicators.append("High radial frequency variance")

        if peak_count > 5:
            gan_score += 0.4
            gan_indicators.append(
                f"Multiple spectral peaks detected ({peak_count})")

        # Check for symmetric artifacts
        quadrant_means = []
        quad_h, quad_w = h // 2, w // 2
        quadrant_means.append(np.mean(magnitude[:quad_h, :quad_w]))
        quadrant_means.append(np.mean(magnitude[:quad_h, quad_w:]))
        quadrant_means.append(np.mean(magnitude[quad_h:, :quad_w]))
        quadrant_means.append(np.mean(magnitude[quad_h:, quad_w:]))

        quadrant_symmetry = float(
            np.std(quadrant_means) / (np.mean(quadrant_means) + 1e-10))

        if quadrant_symmetry < 0.1:
            gan_score += 0.3
            gan_indicators.append(
                "Highly symmetric frequency distribution (GAN characteristic)")

        # Determine likelihood
        if gan_score > 0.7:
            likelihood = "High"
        elif gan_score > 0.4:
            likelihood = "Medium"
        else:
            likelihood = "Low"

        result = {
            "status": "success",
            "method": "GAN Fingerprint Detection (Spectral Analysis)",
            "metrics": {
                "radial_frequency_variance": radial_variance,
                "spectral_peaks_detected": peak_count,
                "quadrant_symmetry": quadrant_symmetry,
                "gan_score": float(gan_score)
            },
            # First 20 values for reference
            "radial_profile": radial_profile[:20],
            "gan_indicators": gan_indicators,
            "gan_likelihood": likelihood,
            "interpretation": f"{likelihood} likelihood of GAN generation. Score: {gan_score:.2f}",
            "note": "This is a heuristic detector; professional detection requires deep learning models"
        }

        return result

    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }
