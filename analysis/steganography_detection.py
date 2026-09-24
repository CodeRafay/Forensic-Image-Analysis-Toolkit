"""
Steganography Detection Module
===============================
Detects LSB (Least Significant Bit) steganography in images using statistical analysis.

This module implements the Westfeld-Pfitzmann Pair-of-Values (PoV) chi-square attack
to identify the histogram signature that LSB embedding leaves behind.
"""

import io
import matplotlib.pyplot as plt
from PIL import Image
import numpy as np
from scipy import stats
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend


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


# A channel whose LSB plane is this many sigma away from spatially random
# cannot be carrying a random payload at capacity. 4 sigma is deliberately
# conservative; measured values are ~18-62 for clean images and ~0-1.5 for
# embedded ones, so the exact cut is not sensitive.
RANDOMNESS_Z_THRESHOLD = 4.0


def lsb_spatial_randomness_z(channel):
    """
    How far the LSB plane sits from spatially random, in standard deviations.

    LSB replacement writes independent uniform bits, so an embedded plane has
    adjacent bits agreeing 50% of the time. Natural and — importantly —
    *interpolated* images do not: resizing averages neighbouring pixels, which
    leaves the LSB plane spatially correlated.

    This is the companion check to the PoV test. Interpolation also smooths the
    histogram, which equalises PoV pairs and makes a clean resized image look
    embedded (measured: a bicubic-resized clean photo scores 74% on PoV alone).
    Requiring the plane to also be spatially random rules that out.

    Args:
        channel (numpy.ndarray): Full 8-bit channel values

    Returns:
        float: z-score. ~0 means consistent with random (embedded); large
            positive means correlated (clean). Can be mildly negative by chance.
    """
    bits = (np.asarray(channel) & 1).astype(np.uint8)
    if bits.shape[0] < 2 or bits.shape[1] < 2:
        return 0.0

    agreements = np.concatenate([
        (bits[:, :-1] == bits[:, 1:]).ravel(),
        (bits[:-1, :] == bits[1:, :]).ravel(),
    ])
    n = agreements.size
    if n == 0:
        return 0.0

    # Under random bits, agreement ~ Binomial(n, 0.5)
    return float((agreements.mean() - 0.5) / np.sqrt(0.25 / n))


def pov_chi_square_test(channel, min_expected=5):
    """
    Westfeld-Pfitzmann Pair-of-Values (PoV) chi-square test for LSB embedding.

    LSB embedding of random data does not change how many 1-bits a plane has
    overall — it makes the counts *within each PoV pair* converge. A pair is
    the two values that differ only in their LSB: (0,1), (2,3), ... (254,255).
    Flipping LSBs moves pixels between the members of a pair but never out of
    it, so as embedding approaches capacity the pair members equalise.

    The test therefore compares each pair's observed split against an even
    split. A HIGH p-value means the "already equalised" hypothesis cannot be
    rejected, which is the signature of embedding; a natural image has lopsided
    pairs and yields a p-value near zero.

    Note this is the opposite direction from a naive "is the LSB plane 50/50?"
    check. That check is also scale-dependent — its statistic grows linearly
    with pixel count, so on a multi-megapixel image a natural sub-1% imbalance
    saturates it and every image reads as suspicious. The PoV statistic is
    scale-stable because its degrees of freedom grow with the number of
    populated pairs.

    Args:
        channel (numpy.ndarray): Full 8-bit channel values (NOT the LSB plane)
        min_expected (int): Pairs whose expected count falls below this are
            excluded, per the usual chi-square small-sample requirement

    Returns:
        tuple: (chi_square_statistic, p_value, steganography_probability,
                valid_pairs)
    """
    hist = np.bincount(np.asarray(channel).ravel(),
                       minlength=256).astype(np.float64)

    # Pair (2i, 2i+1): values differing only in the LSB
    even = hist[0::2]
    odd = hist[1::2]
    expected = (even + odd) / 2.0

    # Drop sparsely populated pairs — chi-square is invalid there
    valid = expected >= min_expected
    valid_pairs = int(valid.sum())

    # Need at least 2 pairs for a meaningful test (df >= 1)
    if valid_pairs < 2:
        return 0.0, 0.0, 0.0, valid_pairs

    # One member per pair; the other is its mirror and would only double chi2
    chi2_stat = float(
        np.sum((even[valid] - expected[valid]) ** 2 / expected[valid]))

    df = valid_pairs - 1
    p_value = float(stats.chi2.sf(chi2_stat, df))

    # High p-value == pairs are equalised == embedding likely
    steganography_probability = p_value * 100.0

    return chi2_stat, p_value, steganography_probability, valid_pairs


def analyze_blocks(channel, block_size=192):
    """
    Analyze a channel in blocks to create a spatial heatmap of suspicious
    regions. Localises embedding that covers only part of the image, which the
    whole-image test misses: a 10%-capacity embed scores 0 globally but lights
    up the blocks it actually occupies.

    Treat this map as a localisation aid, not a verdict — the overall score
    from `detect_lsb_steganography` is the verdict. Per-block PoV is far weaker
    than the whole-image test, and on JPEG-sourced images it retains a real
    false positive rate: decompressed JPEG has locally smooth histograms, so
    pairs in busy regions equalise on their own, and the randomness gate has
    less statistical power over a block than over a whole channel. Measured on
    the bundled sample at this block size: ~33% of blocks in a clean image read
    above 80%, versus ~93% in a fully embedded one, and a quadrant-only embed
    is localised correctly. Separating the rest needs a calibrated detector
    such as RS analysis or Sample Pair Analysis.

    Block size trades localisation resolution against statistical power —
    measured clean false positives run ~49% at 64px, ~41% at 128px, ~33% at
    192px and ~25% at 256px, while the grid gets coarser at every step.

    Args:
        channel (numpy.ndarray): Full 8-bit channel values (NOT the LSB plane)
        block_size (int): Size of blocks for analysis

    Returns:
        numpy.ndarray: Heatmap of steganography probability per block
    """
    h, w = channel.shape

    # Calculate number of blocks
    blocks_h = h // block_size
    blocks_w = w // block_size

    # Create heatmap
    heatmap = np.zeros((blocks_h, blocks_w))

    for i in range(blocks_h):
        for j in range(blocks_w):
            # Extract block
            block = channel[
                i * block_size:(i + 1) * block_size,
                j * block_size:(j + 1) * block_size
            ]

            # A block whose LSB plane is clearly not random cannot be
            # carrying a payload, whatever its PoV pairs look like.
            if lsb_spatial_randomness_z(block) > RANDOMNESS_Z_THRESHOLD:
                heatmap[i, j] = 0.0
                continue

            _, _, prob, _ = pov_chi_square_test(block)
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
    titles = ['Red Channel LSB Analysis',
              'Green Channel LSB Analysis', 'Blue Channel LSB Analysis']
    positions = [(0, 1), (1, 0), (1, 1)]

    for idx, (channel, title, pos) in enumerate(zip(channels, titles, positions)):
        im = axes[pos].imshow(
            heatmaps[channel], cmap='hot', interpolation='nearest')
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
    1. PoV chi-square testing per RGB channel (the verdict)
    2. Block-based spatial analysis to localise partial embedding
    3. Visual heatmap generation
    4. LSB plane extraction, reported for reference

    Detection power scales with how much of the LSB capacity is used. Measured
    on the bundled sample: a clean image scores 0%, a fully embedded one 100%,
    a 50% embed ~20%, and a 10% embed is invisible to the whole-image test —
    look at the block heatmap for sparse or partial embedding.

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
        img.close()

        # Channel values drive the PoV test; LSB planes are kept for reporting
        channels = {
            'red': img_array[:, :, 0],
            'green': img_array[:, :, 1],
            'blue': img_array[:, :, 2]
        }
        lsb_planes = extract_lsb_planes(img_array)

        # Perform PoV chi-square tests on each channel
        results = {}
        channel_probabilities = []

        for channel, values in channels.items():
            chi2_stat, p_value, prob, valid_pairs = pov_chi_square_test(values)
            plane = lsb_planes[channel]

            # Corroborating check: a payload of random bits must leave the LSB
            # plane spatially random. If it plainly isn't, the PoV result is an
            # artefact of a smooth histogram (interpolation does this), not
            # evidence of embedding.
            randomness_z = lsb_spatial_randomness_z(values)
            plane_is_random = randomness_z <= RANDOMNESS_Z_THRESHOLD
            if not plane_is_random:
                prob = 0.0

            results[channel] = {
                'chi_square_statistic': float(chi2_stat),
                'p_value': float(p_value),
                'steganography_probability': float(prob),
                'pov_probability_before_gate': float(p_value * 100.0),
                'lsb_randomness_z': round(randomness_z, 2),
                'lsb_plane_is_random': plane_is_random,
                'valid_pairs': valid_pairs,
                'lsb_distribution': {
                    'zeros': int(np.sum(plane == 0)),
                    'ones': int(np.sum(plane == 1)),
                    'total': int(plane.size)
                }
            }
            channel_probabilities.append(prob)

        # Overall score is the strongest channel, not the average: data hidden
        # in a single channel would be diluted to a third by averaging.
        overall_probability = float(max(channel_probabilities))

        # Create block-based heatmaps
        heatmaps = {}
        for channel, values in channels.items():
            heatmaps[channel] = analyze_blocks(values)

        # Create visual analysis map
        visual_map = create_visual_analysis_map(img_array, heatmaps)

        # Compile detailed results
        detailed_results = {
            'overall_probability': overall_probability,
            'mean_channel_probability': float(np.mean(channel_probabilities)),
            'channel_results': results,
            'image_info': {
                'width': img_array.shape[1],
                'height': img_array.shape[0],
                'total_pixels': int(img_array.shape[0] * img_array.shape[1])
            },
            'method': 'Westfeld-Pfitzmann PoV chi-square',
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
