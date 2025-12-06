import numpy as np
from PIL import Image
from scipy.fft import fft2, fftshift
from pathlib import Path
import matplotlib.pyplot as plt


def analyze_frequency_domain(image_path):
    """
    Analyzes image in frequency domain using FFT for tampering detection.
    Manipulated regions may show different frequency characteristics.

    Args:
        image_path (str): Path to the image file

    Returns:
        dict: Frequency analysis results with human-readable interpretation
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
        magnitude_max = np.max(magnitude_spectrum)

        # Analyze phase consistency (uniform phase suggests less manipulation)
        phase_std = np.std(phase_spectrum)

        # Calculate high-frequency energy (edges and details)
        h, w = magnitude_spectrum.shape
        center_h, center_w = h // 2, w // 2
        radius = min(center_h, center_w) // 3

        # Create mask for high frequencies (outer region)
        y, x = np.ogrid[:h, :w]
        mask = (x - center_w)**2 + (y - center_h)**2 > radius**2
        high_freq_energy = np.sum(
            magnitude_spectrum[mask]) / np.sum(magnitude_spectrum)

        # Detect periodic patterns (common in manipulation)
        # Look for unexpected peaks in frequency domain
        spectrum_normalized = magnitude_spectrum / magnitude_max
        peaks_count = np.sum(spectrum_normalized > 0.5)

        # Calculate frequency distribution uniformity
        freq_histogram = np.histogram(magnitude_spectrum.flatten(), bins=50)[0]
        freq_uniformity = np.std(freq_histogram) / \
            (np.mean(freq_histogram) + 1e-10)

        # Generate human-readable interpretation
        authenticity_score = 0
        findings = []
        warnings = []
        risk_level = "Low"

        # Score based on phase consistency (0-30 points)
        if phase_std < 1.0:
            authenticity_score += 30
            findings.append(
                "✓ Phase pattern is highly uniform (natural characteristic)")
        elif phase_std < 1.5:
            authenticity_score += 20
            findings.append("✓ Phase pattern is reasonably consistent")
        else:
            findings.append("⚠ Phase pattern shows irregularities")
            warnings.append(
                "Irregular phase patterns detected - may indicate editing or filtering")

        # Score based on high-frequency content (0-35 points)
        if 0.1 < high_freq_energy < 0.3:
            authenticity_score += 35
            findings.append("✓ Natural amount of fine details and edges")
        elif high_freq_energy < 0.1:
            authenticity_score += 15
            findings.append(
                "⚠ Reduced fine details (possible smoothing or compression)")
            warnings.append(
                "Image appears overly smooth - may have been heavily processed")
        else:
            authenticity_score += 20
            findings.append("⚠ Elevated high-frequency content")
            warnings.append(
                "Unusual amount of sharp edges - may indicate sharpening or artificial enhancement")

        # Score based on frequency distribution (0-35 points)
        if freq_uniformity < 2.0:
            authenticity_score += 35
            findings.append("✓ Frequency distribution looks natural")
        elif freq_uniformity < 3.5:
            authenticity_score += 20
            findings.append(
                "⚠ Frequency distribution shows minor irregularities")
        else:
            findings.append("⚠ Frequency distribution is unusual")
            warnings.append(
                "Abnormal frequency patterns detected - may indicate manipulation or filters")

        # Determine risk level
        if authenticity_score >= 80:
            risk_level = "Low"
            verdict = "Image frequency patterns appear natural"
        elif authenticity_score >= 60:
            risk_level = "Medium"
            verdict = "Some frequency irregularities detected"
        else:
            risk_level = "High"
            verdict = "Significant frequency anomalies detected"

        # Create temp directory for visualizations
        temp_dir = Path(__file__).parent.parent / "temp"
        temp_dir.mkdir(exist_ok=True)

        # Save magnitude spectrum visualization
        magnitude_vis_path = temp_dir / 'fft_magnitude_spectrum.png'
        plt.figure(figsize=(8, 6))
        plt.imshow(np.log(magnitude_spectrum + 1), cmap='hot')
        plt.colorbar(label='Log Magnitude')
        plt.title('FFT Magnitude Spectrum\n(Brighter areas = stronger frequencies)')
        plt.axis('off')
        plt.tight_layout()
        plt.savefig(magnitude_vis_path, dpi=100, bbox_inches='tight')
        plt.close()

        result = {
            "status": "success",
            "method": "FFT Frequency Domain Analysis",
            "authenticity_score": authenticity_score,
            "risk_level": risk_level,
            "verdict": verdict,
            "metrics": {
                "high_frequency_energy_percentage": float(high_freq_energy * 100),
                # Higher is better
                "phase_consistency_score": float(10 - min(phase_std, 10)),
                "frequency_uniformity": float(freq_uniformity),
                "spectral_complexity": float(magnitude_std / magnitude_mean)
            },
            "findings": findings,
            "warnings": warnings,
            "magnitude_spectrum_path": str(magnitude_vis_path),
            "technical_details": {
                "magnitude_mean": float(magnitude_mean),
                "magnitude_std": float(magnitude_std),
                "phase_std": float(phase_std),
                "peaks_detected": int(peaks_count)
            },
            "interpretation": _generate_fft_interpretation(authenticity_score, high_freq_energy, phase_std, freq_uniformity)
        }

        return result

    except Exception as e:
        return {"error": str(e), "status": "error"}


def _generate_fft_interpretation(score, high_freq_energy, phase_std, freq_uniformity):
    """Generate detailed human-readable interpretation for FFT analysis."""

    interpretation = []

    # Overall assessment
    if score >= 80:
        interpretation.append(
            "🟢 **Overall Assessment:** The image's frequency characteristics appear natural and consistent with authentic photos.")
    elif score >= 60:
        interpretation.append(
            "🟡 **Overall Assessment:** Some frequency patterns show minor irregularities that warrant closer examination.")
    else:
        interpretation.append(
            "🔴 **Overall Assessment:** Significant frequency anomalies detected that suggest possible manipulation.")

    # High frequency explanation
    interpretation.append("\n📊 **Detail Analysis:**")
    if 0.1 < high_freq_energy < 0.3:
        interpretation.append(
            "• The amount of fine details (like textures and edges) is typical for natural photos.")
    elif high_freq_energy < 0.1:
        interpretation.append(
            "• The image has fewer fine details than normal - this often happens with:")
        interpretation.append("  - Heavy compression or resaving")
        interpretation.append("  - Blur or smoothing filters")
        interpretation.append("  - AI-generated content")
    else:
        interpretation.append(
            "• The image has more sharp details than typical - this may indicate:")
        interpretation.append("  - Artificial sharpening filters")
        interpretation.append("  - Edge enhancement")
        interpretation.append("  - Composite images from multiple sources")

    # Phase consistency explanation
    interpretation.append("\n🌊 **Pattern Consistency:**")
    if phase_std < 1.0:
        interpretation.append(
            "• The image patterns flow naturally across the entire photo.")
    elif phase_std < 1.5:
        interpretation.append(
            "• Minor pattern inconsistencies detected, which could be normal variations.")
    else:
        interpretation.append(
            "• Pattern disruptions detected - common causes include:")
        interpretation.append("  - Copy-paste edits")
        interpretation.append("  - Object removal/insertion")
        interpretation.append("  - Different lighting on spliced regions")

    return "\n".join(interpretation)


def detect_dct_anomalies(image_path):
    """
    Detects DCT (Discrete Cosine Transform) anomalies.
    JPEG compression uses DCT; manipulation leaves traces in DCT coefficients.

    Args:
        image_path (str): Path to image file

    Returns:
        dict: DCT anomaly analysis with human-readable interpretation
    """
    try:
        from scipy.fftpack import dct
        import cv2

        img = Image.open(image_path).convert('L')
        img_array = np.array(img, dtype=np.float32)

        # Apply 2D DCT
        dct_result = dct(dct(img_array.T, norm='ortho').T, norm='ortho')

        # Analyze DCT coefficients
        dct_mean = np.mean(np.abs(dct_result))
        dct_std = np.std(np.abs(dct_result))
        dct_max = np.max(np.abs(dct_result))

        # Analyze by frequency regions
        h, w = dct_result.shape

        # DC coefficient (top-left) - represents average brightness
        dc_coefficient = np.abs(dct_result[0, 0])

        # Low frequency region (top-left quadrant) - smooth areas
        low_freq_region = np.abs(dct_result[:h//4, :w//4])
        low_freq_energy = np.sum(low_freq_region) / np.sum(np.abs(dct_result))

        # Mid frequency region - texture and details
        mid_freq_region = np.abs(dct_result[h//4:h//2, w//4:w//2])
        mid_freq_energy = np.sum(mid_freq_region) / np.sum(np.abs(dct_result))

        # High frequency region (bottom-right) - edges and noise
        high_freq_region = np.abs(dct_result[-h//4:, -w//4:])
        high_freq_variance = np.var(high_freq_region)
        high_freq_energy = np.sum(high_freq_region) / \
            np.sum(np.abs(dct_result))

        # Block-based analysis (8x8 blocks like JPEG)
        block_size = 8
        block_variances = []

        for i in range(0, h - block_size, block_size):
            for j in range(0, w - block_size, block_size):
                block = dct_result[i:i+block_size, j:j+block_size]
                block_variances.append(np.var(block))

        block_variance_std = np.std(block_variances)
        block_variance_mean = np.mean(block_variances)

        # Detect grid patterns (common in JPEG manipulation)
        grid_consistency = block_variance_std / (block_variance_mean + 1e-10)

        # Detect quantization artifacts
        # JPEG quantization leaves step patterns in DCT coefficients
        coeff_histogram = np.histogram(dct_result.flatten(), bins=100)[0]
        quantization_score = np.sum(coeff_histogram > np.mean(
            coeff_histogram) * 2) / len(coeff_histogram)

        # Generate human-readable interpretation
        authenticity_score = 0
        findings = []
        warnings = []
        anomalies = []
        risk_level = "Low"

        # Score based on frequency distribution (0-30 points)
        if 0.4 < low_freq_energy < 0.7:
            authenticity_score += 30
            findings.append(
                "✓ Natural balance between smooth areas and details")
        elif low_freq_energy > 0.8:
            authenticity_score += 10
            findings.append("⚠ Image is very smooth (low detail)")
            warnings.append(
                "Excessive smoothing detected - may indicate blur filters or AI generation")
        else:
            authenticity_score += 15
            findings.append("⚠ Unusual frequency distribution")
            warnings.append("Abnormal distribution of image details")

        # Score based on high-frequency content (0-30 points)
        if high_freq_energy < 0.05:
            authenticity_score += 30
            findings.append("✓ Normal noise levels typical of camera sensors")
        elif high_freq_energy < 0.1:
            authenticity_score += 20
            findings.append("⚠ Slightly elevated noise/edge content")
        else:
            authenticity_score += 5
            findings.append("⚠ High noise or artificial sharpening detected")
            warnings.append(
                "Excessive high-frequency content - may indicate sharpening filters or noise")
            anomalies.append("Artificial sharpening")

        # Score based on block consistency (0-25 points)
        if grid_consistency < 0.5:
            authenticity_score += 25
            findings.append("✓ Image blocks show natural variation")
        elif grid_consistency < 1.0:
            authenticity_score += 15
            findings.append("⚠ Minor block-level inconsistencies")
        else:
            authenticity_score += 5
            findings.append("⚠ Significant block-level patterns detected")
            warnings.append("Grid-like patterns detected - common in:")
            warnings.append("  • Images edited after JPEG compression")
            warnings.append("  • Copy-paste from different sources")
            warnings.append("  • Multiple compression cycles")
            anomalies.append("JPEG grid artifacts")

        # Score based on quantization (0-15 points)
        if quantization_score < 0.15:
            authenticity_score += 15
            findings.append("✓ No obvious quantization artifacts")
        elif quantization_score < 0.25:
            authenticity_score += 10
            findings.append("⚠ Minor quantization patterns")
        else:
            findings.append("⚠ Strong quantization artifacts detected")
            warnings.append(
                "Unusual JPEG compression patterns - may indicate re-compression after editing")
            anomalies.append("Multiple JPEG compressions")

        # Determine risk level
        if authenticity_score >= 80:
            risk_level = "Low"
            verdict = "DCT analysis shows natural compression patterns"
        elif authenticity_score >= 60:
            risk_level = "Medium"
            verdict = "Some DCT irregularities detected"
        else:
            risk_level = "High"
            verdict = "Significant DCT anomalies suggest manipulation"

        # Create visualization
        temp_dir = Path(__file__).parent.parent / "temp"
        temp_dir.mkdir(exist_ok=True)

        dct_vis_path = temp_dir / 'dct_anomaly_map.png'

        # Create DCT coefficient visualization
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))

        # Log-scaled DCT coefficients
        dct_log = np.log(np.abs(dct_result) + 1)
        im1 = axes[0].imshow(dct_log, cmap='viridis')
        axes[0].set_title(
            'DCT Coefficients\n(Low freq: top-left, High freq: bottom-right)')
        axes[0].axis('off')
        plt.colorbar(im1, ax=axes[0], label='Log Magnitude')

        # Block variance map
        block_map = np.zeros((h // block_size, w // block_size))
        idx = 0
        for i in range(0, h - block_size, block_size):
            for j in range(0, w - block_size, block_size):
                block_map[i // block_size, j //
                          block_size] = block_variances[idx]
                idx += 1
                if idx >= len(block_variances):
                    break
            if idx >= len(block_variances):
                break

        im2 = axes[1].imshow(block_map, cmap='RdYlGn_r')
        axes[1].set_title(
            'Block Consistency Map\n(Red = inconsistent, Green = consistent)')
        axes[1].axis('off')
        plt.colorbar(im2, ax=axes[1], label='Variance')

        plt.tight_layout()
        plt.savefig(dct_vis_path, dpi=100, bbox_inches='tight')
        plt.close()

        result = {
            "status": "success",
            "method": "DCT Coefficient Analysis",
            "authenticity_score": authenticity_score,
            "risk_level": risk_level,
            "verdict": verdict,
            "metrics": {
                "smooth_content_percentage": float(low_freq_energy * 100),
                "detail_content_percentage": float(mid_freq_energy * 100),
                "noise_edge_percentage": float(high_freq_energy * 100),
                # Higher is better
                "block_consistency_score": float(max(0, 10 - grid_consistency)),
                # Higher is better
                "compression_quality_indicator": float((1 - quantization_score) * 10)
            },
            "findings": findings,
            "warnings": warnings,
            "anomalies": anomalies,
            "dct_anomaly_map_path": str(dct_vis_path),
            "technical_details": {
                "dct_coefficient_mean": float(dct_mean),
                "dct_coefficient_std": float(dct_std),
                "high_frequency_variance": float(high_freq_variance),
                "grid_consistency": float(grid_consistency),
                "quantization_score": float(quantization_score)
            },
            "interpretation": _generate_dct_interpretation(
                authenticity_score, low_freq_energy, high_freq_energy,
                grid_consistency, anomalies
            )
        }

        return result

    except Exception as e:
        return {"error": str(e), "status": "error"}


def _generate_dct_interpretation(score, low_freq, high_freq, grid_consistency, anomalies):
    """Generate detailed human-readable interpretation for DCT analysis."""

    interpretation = []

    # Overall assessment
    if score >= 80:
        interpretation.append(
            "🟢 **Overall Assessment:** The image's compression patterns look natural and consistent with authentic photos.")
    elif score >= 60:
        interpretation.append(
            "🟡 **Overall Assessment:** Some compression irregularities detected that may indicate editing.")
    else:
        interpretation.append(
            "🔴 **Overall Assessment:** Significant compression anomalies strongly suggest manipulation.")

    # Frequency content explanation
    interpretation.append("\n📊 **Content Analysis:**")
    if 0.4 < low_freq < 0.7:
        interpretation.append(
            "• The image has a healthy mix of smooth areas and detailed textures.")
    elif low_freq > 0.8:
        interpretation.append("• The image is unusually smooth, suggesting:")
        interpretation.append("  - Aggressive blur or smoothing filters")
        interpretation.append("  - Heavy noise reduction")
        interpretation.append(
            "  - AI-generated content (often lacks natural texture)")
    else:
        interpretation.append(
            "• Unusual distribution of smooth vs. detailed content.")

    # High frequency explanation
    interpretation.append("\n🔍 **Edge & Noise Analysis:**")
    if high_freq < 0.05:
        interpretation.append(
            "• Natural amount of camera noise and fine edges present.")
    elif high_freq < 0.1:
        interpretation.append(
            "• Slightly elevated sharpness - may be from camera settings or light editing.")
    else:
        interpretation.append(
            "• Excessive sharpness or noise detected - common causes:")
        interpretation.append("  - Artificial sharpening filters applied")
        interpretation.append("  - Noise added to hide manipulation")
        interpretation.append("  - Over-processed image")

    # Block analysis explanation
    interpretation.append("\n🎯 **JPEG Compression Analysis:**")
    if grid_consistency < 0.5:
        interpretation.append(
            "• Compression blocks show consistent patterns throughout.")
    elif grid_consistency < 1.0:
        interpretation.append(
            "• Minor block inconsistencies detected - possible normal variations.")
    else:
        interpretation.append(
            "• Strong grid patterns detected - this typically happens when:")
        interpretation.append("  - Image is edited then re-saved as JPEG")
        interpretation.append(
            "  - Different parts have different compression levels")
        interpretation.append("  - Objects copied from other images")

    # Specific anomalies
    if anomalies:
        interpretation.append("\n⚠️ **Specific Issues Found:**")
        for anomaly in anomalies:
            interpretation.append(f"• {anomaly}")

    return "\n".join(interpretation)
