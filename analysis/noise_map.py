from PIL import Image, ImageFilter, ImageChops
from pathlib import Path
import numpy as np


def generate_noise_map(image_path, sigma=2.0):
    """
    Generates a noise map by detecting high-frequency components.
    Useful for detecting retouching, splicing, and cloning.

    Args:
        image_path (str): Path to the image file
        sigma (float): Gaussian blur radius (default 2.0)

    Returns:
        dict: Noise map path and analysis metrics
    """
    try:
        img = Image.open(image_path).convert('RGB')

        # Create temp directory
        temp_dir = Path(__file__).parent.parent / "temp"
        temp_dir.mkdir(exist_ok=True)

        # Process each channel separately for better analysis
        channels = img.split()
        noise_maps = []
        variance_per_channel = []

        for channel in channels:
            blurred = channel.filter(ImageFilter.GaussianBlur(radius=sigma))
            diff = ImageChops.difference(channel, blurred)
            enhanced = ImageChops.multiply(diff, diff)
            noise_maps.append(enhanced)
            noise_array = np.asarray(diff, dtype=np.float32)
            variance_per_channel.append(float(np.var(noise_array)))

        img.close()

        noise_map = Image.merge('RGB', noise_maps)

        noise_path = temp_dir / 'temp_noise_map.png'
        noise_map.save(str(noise_path))

        # Analyse noise consistency
        noise_array_full = np.asarray(noise_map, dtype=np.float32)

        # Divide image into blocks and check noise variance
        h, w = noise_array_full.shape[:2]
        block_size = 64
        block_variances = []

        for i in range(0, h - block_size, block_size):
            for j in range(0, w - block_size, block_size):
                block = noise_array_full[i:i+block_size, j:j+block_size]
                block_variances.append(np.var(block))

        variance_std = float(np.std(block_variances))

        del noise_array_full  # free large array
        noise_map.close()

        # Generate warnings
        warnings = []
        if variance_std > np.mean(block_variances) * 0.5:
            warnings.append(
                "High noise inconsistency detected - possible manipulation")

        if np.mean(variance_per_channel) < 10:
            warnings.append(
                "Very low noise levels - possible heavy smoothing/retouching")

        return {
            'noise_map_path': str(noise_path),
            'status': 'success',
            'metrics': {
                'channel_noise_variance': {
                    'red': variance_per_channel[0],
                    'green': variance_per_channel[1],
                    'blue': variance_per_channel[2]
                },
                'overall_variance': float(np.mean(variance_per_channel)),
                'block_variance_std': variance_std,
                'blocks_analyzed': len(block_variances)
            },
            'warnings': warnings,
            'interpretation': 'Uniform noise = authentic; inconsistent noise = possible tampering'
        }

    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'noise_map_path': None
        }
