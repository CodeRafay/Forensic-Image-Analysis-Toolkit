"""
Steganography Detection Module
===============================
Detects LSB (Least Significant Bit) steganography in images using statistical analysis.

This module implements chi-square testing to identify non-natural bit patterns that may
indicate hidden data embedded in image LSB planes.
"""

from PIL import Image
import numpy as np
from scipy import stats
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import io


def extract_lsb_planes(image_array):
    """
    Extract LSB planes from RGB channels.
    
    Args:
        image_array (numpy.ndarray): Image array (H, W, 3) in RGB format
        
    Returns:
        dict: LSB planes for each channel
    """
    lsb_planes = {
        'red': (image_array[:, :, 0] & 1).astype(np.uint8),
        'green': (image_array[:, :, 1] & 1).astype(np.uint8),
        'blue': (image_array[:, :, 2] & 1).astype(np.uint8)
    }
    return lsb_planes


def chi_square_test(lsb_plane):
    """
    Perform chi-square test on LSB plane to detect randomness anomalies.
    
    In natural images, LSB bits should be approximately 50/50 distributed.
    Hidden data creates statistical anomalies detectable via chi-square test.
    
    Args:
        lsb_plane (numpy.ndarray): Binary LSB plane
        
    Returns:
        tuple: (chi_square_statistic, p_value, steganography_probability)
    """
    # Count 0s and 1s
    unique, counts = np.unique(lsb_plane, return_counts=True)
    
    # Expected distribution (50/50 for natural images)
    total = lsb_plane.size
    expected = total / 2
    
    # Handle edge case where only one value exists
    if len(unique) == 1:
        observed = [counts[0], 0] if unique[0] == 0 else [0, counts[0]]
    else:
        observed = [counts[0], counts[1]] if unique[0] == 0 else [counts[1], counts[0]]
    
    # Perform chi-square test
    chi2_stat = sum((obs - expected) ** 2 / expected for obs in observed)
    
    # Calculate p-value (degrees of freedom = 1 for binary data)
    p_value = 1 - stats.chi2.cdf(chi2_stat, df=1)
    
    # Convert to steganography probability (lower p-value = higher suspicion)
    # p-value < 0.05 is typically suspicious
    steganography_probability = (1 - p_value) * 100
    
    return chi2_stat, p_value, steganography_probability


def analyze_blocks(lsb_plane, block_size=32):
    """
    Analyze LSB plane in blocks to create spatial heatmap of suspicious regions.
    
    Args:
        lsb_plane (numpy.ndarray): Binary LSB plane
        block_size (int): Size of blocks for analysis
        
    Returns:
        numpy.ndarray: Heatmap of steganography probability per block
    """
    h, w = lsb_plane.shape
    
    # Calculate number of blocks
    blocks_h = h // block_size
    blocks_w = w // block_size
    
    # Create heatmap
    heatmap = np.zeros((blocks_h, blocks_w))
    
    for i in range(blocks_h):
        for j in range(blocks_w):
            # Extract block
            block = lsb_plane[
                i * block_size:(i + 1) * block_size,
                j * block_size:(j + 1) * block_size
            ]
            
            # Perform chi-square test on block
            _, _, prob = chi_square_test(block)
            heatmap[i, j] = prob
    
    return heatmap


def create_visual_analysis_map(image_array, heatmaps):
    """
    Create a comprehensive visual analysis map showing suspicious regions.
    
    Args:
        image_array (numpy.ndarray): Original image array
        heatmaps (dict): Heatmaps for each channel
        
    Returns:
        PIL.Image: Visual analysis map
    """
    fig, axes = plt.subplots(2, 2, figsize=(12, 12))
    
    # Original image
    axes[0, 0].imshow(image_array)
    axes[0, 0].set_title('Original Image', fontsize=12, fontweight='bold')
    axes[0, 0].axis('off')
    
    # RGB channel heatmaps
    channels = ['red', 'green', 'blue']
    titles = ['Red Channel LSB Analysis', 'Green Channel LSB Analysis', 'Blue Channel LSB Analysis']
    positions = [(0, 1), (1, 0), (1, 1)]
    
    for idx, (channel, title, pos) in enumerate(zip(channels, titles, positions)):
        im = axes[pos].imshow(heatmaps[channel], cmap='hot', interpolation='nearest')
        axes[pos].set_title(title, fontsize=10, fontweight='bold')
        axes[pos].axis('off')
        plt.colorbar(im, ax=axes[pos], label='Steganography Probability (%)')
    
    plt.tight_layout()
    
    # Convert to PIL Image
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    
    return Image.open(buf)


def detect_lsb_steganography(image_path):
    """
    Detect LSB steganography in an image using statistical analysis.
    
    This function performs:
    1. LSB plane extraction from RGB channels
    2. Chi-square statistical testing for randomness
    3. Block-based spatial analysis
    4. Visual heatmap generation
    
    Args:
        image_path (str): Path to the image file
        
    Returns:
        tuple: (steganography_probability, visual_analysis_map, detailed_results)
            - steganography_probability (float): Overall probability score (0-100%)
            - visual_analysis_map (PIL.Image): Heatmap showing suspicious regions
            - detailed_results (dict): Detailed analysis metrics
    """
    try:
        # Load image
        img = Image.open(image_path).convert('RGB')
        img_array = np.array(img)
        
        # Extract LSB planes
        lsb_planes = extract_lsb_planes(img_array)
        
        # Perform chi-square tests on each channel
        results = {}
        channel_probabilities = []
        
        for channel, plane in lsb_planes.items():
            chi2_stat, p_value, prob = chi_square_test(plane)
            
            results[channel] = {
                'chi_square_statistic': float(chi2_stat),
                'p_value': float(p_value),
                'steganography_probability': float(prob),
                'lsb_distribution': {
                    'zeros': int(np.sum(plane == 0)),
                    'ones': int(np.sum(plane == 1)),
                    'total': int(plane.size)
                }
            }
            channel_probabilities.append(prob)
        
        # Calculate overall probability (average of channels)
        overall_probability = np.mean(channel_probabilities)
        
        # Create block-based heatmaps
        heatmaps = {}
        for channel, plane in lsb_planes.items():
            heatmaps[channel] = analyze_blocks(plane)
        
        # Create visual analysis map
        visual_map = create_visual_analysis_map(img_array, heatmaps)
        
        # Compile detailed results
        detailed_results = {
            'overall_probability': float(overall_probability),
            'channel_results': results,
            'image_info': {
                'width': img_array.shape[1],
                'height': img_array.shape[0],
                'total_pixels': int(img_array.shape[0] * img_array.shape[1])
            },
            'interpretation': _interpret_results(overall_probability)
        }
        
        return overall_probability, visual_map, detailed_results
        
    except Exception as e:
        # Return error information
        return 0.0, None, {'error': str(e)}


def _interpret_results(probability):
    """
    Interpret steganography probability score.
    
    Args:
        probability (float): Steganography probability (0-100)
        
    Returns:
        dict: Interpretation with risk level and description
    """
    if probability < 20:
        risk_level = "Low"
        description = "LSB distribution appears natural. No strong evidence of steganography detected."
        color = "🟢"
    elif probability < 50:
        risk_level = "Medium"
        description = "Some statistical anomalies detected. Further investigation recommended."
        color = "🟡"
    elif probability < 80:
        risk_level = "High"
        description = "Significant LSB anomalies detected. Strong indication of hidden data."
        color = "🟠"
    else:
        risk_level = "Critical"
        description = "Severe LSB distribution anomalies. Very high likelihood of steganography."
        color = "🔴"
    
    return {
        'risk_level': risk_level,
        'description': description,
        'color': color,
        'confidence': f"{min(probability, 100):.1f}%"
    }


# ============================================================
# -------------------- BATCH PROCESSING ----------------------
# ============================================================

def batch_detect(image_paths):
    """
    Process multiple images for steganography detection.
    
    Args:
        image_paths (list): List of image file paths
        
    Returns:
        dict: Results for each image
    """
    results = {}
    
    for path in image_paths:
        try:
            prob, _, details = detect_lsb_steganography(path)
            results[path] = {
                'probability': prob,
                'details': details
            }
        except Exception as e:
            results[path] = {
                'error': str(e)
            }
    
    return results
