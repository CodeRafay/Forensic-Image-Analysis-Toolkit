import numpy as np
from PIL import Image
from scipy.fft import fft2, fftshift
from scipy.ndimage import gaussian_filter


def analyze_frequency_domain(image_path):
    """
    Analyzes image in frequency domain using FFT/DCT for tampering detection.
    Manipulated regions may show different frequency characteristics.

    Args:
        image_path (str): Path to the image file

    Returns:
        dict: Frequency analysis results
    """
    try:
        img = Image.open(image_path).convert('L')
        img_array = np.array(img, dtype=np.float32)

        # Apply FFT
        fft_result = fft2(img_array)
        fft_shifted = fftshift(fft_result)
        magnitude_spectrum = np.abs(fft_shifted)
        phase_spectrum = np.angle(fft_shifted)

        # Calculate statistics
        magnitude_mean = np.mean(magnitude_spectrum)
        magnitude_std = np.std(magnitude_spectrum)

        # Analyze phase consistency (uniform phase suggests less manipulation)
        phase_consistency = np.std(phase_spectrum)

        result = {
            "status": "analysis_complete",
            "method": "FFT Frequency Domain Analysis",
            "image_size": img_array.shape,
            "frequency_magnitude_mean": float(magnitude_mean),
            "frequency_magnitude_std": float(magnitude_std),
            "phase_consistency_metric": float(phase_consistency),
            "interpretation": "High phase consistency indicates natural image, irregular patterns suggest manipulation"
        }

        return result

    except Exception as e:
        return {"error": str(e), "status": "analysis_failed"}


def detect_dct_anomalies(image_path):
    """
    Detects DCT (Discrete Cosine Transform) anomalies.
    JPEG compression uses DCT; manipulation leaves traces in DCT coefficients.

    Args:
        image_path (str): Path to image file

    Returns:
        dict: DCT anomaly analysis
    """
    try:
        from scipy.fftpack import dct

        img = Image.open(image_path).convert('L')
        img_array = np.array(img, dtype=np.float32)

        # Apply 2D DCT
        dct_result = dct(dct(img_array.T, norm='ortho').T, norm='ortho')

        # Analyze DCT coefficients
        dct_mean = np.mean(np.abs(dct_result))
        dct_std = np.std(np.abs(dct_result))

        # High frequency anomalies
        # bottom-right corner (high freq)
        dct_high_freq = np.abs(dct_result[-50:, -50:])
        high_freq_variance = np.var(dct_high_freq)

        result = {
            "status": "analysis_complete",
            "method": "DCT Coefficient Analysis",
            "dct_coefficient_mean": float(dct_mean),
            "dct_coefficient_std": float(dct_std),
            "high_frequency_variance": float(high_freq_variance),
            "interpretation": "Anomalies in high-frequency coefficients may indicate tampering"
        }

        return result

    except Exception as e:
        return {"error": str(e), "status": "analysis_failed"}
