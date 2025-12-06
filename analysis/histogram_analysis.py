from pathlib import Path
import matplotlib.pyplot as plt
from PIL import Image
import numpy as np
import matplotlib
matplotlib.use('Agg')


def generate_histogram(image_path):
    """
    Generates a histogram visualization of the image with statistical analysis.

    Args:
        image_path (str): Path to the image file

    Returns:
        dict: Contains histogram path and statistical metrics, or error info
    """
    try:
        img = Image.open(image_path).convert('RGB')

        # Create temp directory if needed
        temp_dir = Path(__file__).parent.parent / "temp"
        temp_dir.mkdir(exist_ok=True)

        hist_path = temp_dir / 'temp_histogram.png'

        # Extract channel data
        r, g, b = img.split()
        r_data = np.array(list(r.getdata()))
        g_data = np.array(list(g.getdata()))
        b_data = np.array(list(b.getdata()))

        # Calculate statistics for each channel
        statistics = {
            'red': {
                'mean': float(np.mean(r_data)),
                'std': float(np.std(r_data)),
                'min': int(np.min(r_data)),
                'max': int(np.max(r_data)),
                'median': float(np.median(r_data))
            },
            'green': {
                'mean': float(np.mean(g_data)),
                'std': float(np.std(g_data)),
                'min': int(np.min(g_data)),
                'max': int(np.max(g_data)),
                'median': float(np.median(g_data))
            },
            'blue': {
                'mean': float(np.mean(b_data)),
                'std': float(np.std(b_data)),
                'min': int(np.min(b_data)),
                'max': int(np.max(b_data)),
                'median': float(np.median(b_data))
            }
        }

        # Check for histogram anomalies
        warnings = []

        # Check for gaps (comb pattern - sign of level adjustment)
        for channel_name, channel_data in [('Red', r_data), ('Green', g_data), ('Blue', b_data)]:
            hist, _ = np.histogram(channel_data, bins=256, range=(0, 256))
            zero_bins = np.sum(hist == 0)
            if zero_bins > 50:  # More than 50 empty bins suggests manipulation
                warnings.append(
                    f"{channel_name} channel shows gaps (comb pattern) - possible level adjustment")

        # Check for clipping
        for channel_name, data in [('Red', r_data), ('Green', g_data), ('Blue', b_data)]:
            if np.sum(data == 0) > len(data) * 0.01:  # >1% at minimum
                warnings.append(
                    f"{channel_name} channel clipped at minimum (shadow detail lost)")
            if np.sum(data == 255) > len(data) * 0.01:  # >1% at maximum
                warnings.append(
                    f"{channel_name} channel clipped at maximum (highlight detail lost)")

        # Create histogram visualization
        plt.figure(figsize=(12, 6))

        plt.hist(r_data, bins=256, range=(0, 256),
                 color='r', alpha=0.5, label='Red')
        plt.hist(g_data, bins=256, range=(0, 256),
                 color='g', alpha=0.5, label='Green')
        plt.hist(b_data, bins=256, range=(0, 256),
                 color='b', alpha=0.5, label='Blue')

        plt.xlabel('Pixel Intensity', fontsize=11)
        plt.ylabel('Frequency', fontsize=11)
        plt.title('RGB Histogram Analysis', fontsize=13, fontweight='bold')
        plt.legend(fontsize=10)
        plt.grid(alpha=0.3, linestyle='--')
        plt.tight_layout()
        plt.savefig(str(hist_path), dpi=100, bbox_inches='tight')
        plt.close()

        return {
            'histogram_path': str(hist_path),
            'statistics': statistics,
            'warnings': warnings,
            'status': 'success',
            'interpretation': 'Analyze for gaps (manipulation), clipping (data loss), or unusual distribution'
        }

    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'histogram_path': None
        }
