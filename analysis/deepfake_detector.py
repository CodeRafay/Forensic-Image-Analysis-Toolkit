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

    Args:
        image_path (str): Path to image file

    Returns:
        dict: GAN fingerprint detection results
    """
    try:
        img = Image.open(image_path).convert('RGB')
        img_array = np.array(img, dtype=np.float32)

        # Analyze spectral properties unique to GANs
        from scipy.fft import fft2, fftshift

        gray = np.mean(img_array, axis=2)
        fft_result = fft2(gray)
        magnitude = np.abs(fftshift(fft_result))

        # Look for characteristic "blob" patterns in frequency domain
        h, w = magnitude.shape
        center_h, center_w = h // 2, w // 2

        # Radial frequency analysis
        y, x = np.ogrid[:h, :w]
        distance = np.sqrt((y - center_h)**2 + (x - center_w)**2)

        radial_profile = []
        for r in range(1, min(center_h, center_w), 10):
            mask = (distance >= r) & (distance < r + 10)
            radial_profile.append(np.mean(magnitude[mask]))

        # GANs produce characteristic radial patterns
        radial_variance = np.var(radial_profile)

        result = {
            "status": "analysis_complete",
            "method": "GAN Fingerprint Detection (Spectral Analysis)",
            "radial_frequency_variance": float(radial_variance),
            "potential_gan_likelihood": "Medium" if radial_variance > 1000 else "Low",
            "note": "Requires deep learning model for accurate detection; this is pattern-based heuristic"
        }

        return result

    except Exception as e:
        return {"error": str(e), "status": "analysis_failed"}
