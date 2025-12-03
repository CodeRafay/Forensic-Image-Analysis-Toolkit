from PIL import Image, ImageChops, ImageEnhance, ImageOps, ImageFilter
import numpy as np
import io
from math import log2, sqrt

# ============================================================
# ------------------------ ELA CORE ---------------------------
# ============================================================


def perform_ela(image_path, quality=95, error_scale=10, overlay_opacity=0.5):
    """
    Perform Error Level Analysis (ELA) using in-memory operations.

    Key fix: Only compress ONCE at target quality, then compare with original.

    Returns:
        ela_img (PIL.Image)        -> ELA image (grayscale)
        ela_overlay (PIL.Image)    -> ELA blended with original (opacity)
        metrics (dict)
    """
    try:
        # Load original image
        original = Image.open(image_path).convert("RGB")

        # Compress ONCE at target quality
        buffer = io.BytesIO()
        original.save(buffer, "JPEG", quality=quality)
        buffer.seek(0)
        compressed = Image.open(buffer).convert("RGB")

        # Calculate difference between original and compressed
        diff = ImageChops.difference(original, compressed)

        # Enhance the difference with error scale
        extrema = diff.getextrema()
        max_diff = max([ex[1] for ex in extrema])

        if max_diff == 0:
            max_diff = 1  # Avoid division by zero

        scale = 255.0 / max_diff * (error_scale / 10.0)

        # Apply scaling
        ela_img = ImageEnhance.Brightness(diff).enhance(scale)

        # Create overlay on original
        ela_overlay = Image.blend(
            original, ela_img.convert("RGB"), alpha=overlay_opacity)

        # Compute metrics
        diff_np = np.asarray(diff, dtype=np.float32)
        max_val = diff_np.max()
        metrics = {
            "max_diff": float(max_val),
            "mean_diff": float(diff_np.mean()),
            "std_diff": float(diff_np.std()),
            "anomaly_score": float(diff_np.mean() + 2 * diff_np.std())
        }

        return ela_img, ela_overlay, metrics

    except Exception as e:
        print(f"[ELA ERROR] {e}")
        return None, None, None


def ela_multi_quality(image_path, qualities=[75, 85, 95], error_scale=10, overlay_opacity=0.5):
    """Run ELA at multiple JPEG compression levels."""
    results = {}
    for q in qualities:
        ela_img, overlay_img, metrics = perform_ela(
            image_path, quality=q, error_scale=error_scale, overlay_opacity=overlay_opacity
        )
        if ela_img is not None:
            results[q] = {
                "ela": ela_img,
                "overlay": overlay_img,
                "metrics": metrics
            }
    return results


# ============================================================
# --------------------- BLOCK-BASED ELA -----------------------
# ============================================================

def block_ela_stats(ela_img, block=8):
    """Compute block-level anomaly stats (JPEG DCT-grid aligned)."""
    ela = np.asarray(ela_img.convert("L"), dtype=np.float32)
    h, w = ela.shape

    blocks = []
    for y in range(0, h, block):
        for x in range(0, w, block):
            region = ela[y:y+block, x:x+block]
            blocks.append(region.std())

    blocks = np.array(blocks)

    return {
        "block_std_mean": float(blocks.mean()),
        "block_std_std": float(blocks.std()),
        "block_std_max": float(blocks.max())
    }

# ============================================================
# ------------------------ NOISE MAP --------------------------
# ============================================================


def noise_map(image_path):
    """Extract a normalized edge/noise map."""
    try:
        img = Image.open(image_path).convert("L")
        edges = img.filter(ImageFilter.FIND_EDGES)

        edges_np = np.asarray(edges, dtype=np.float32)
        edges_np = 255 * (edges_np - edges_np.min()) / \
            (edges_np.max() - edges_np.min() + 1e-5)

        return Image.fromarray(edges_np.astype(np.uint8))

    except Exception as e:
        print(f"[NOISE MAP ERROR] {e}")
        return None

# ============================================================
# ---------------------- SHARPNESS MAP ------------------------
# ============================================================


def sharpness_map(image_path):
    """Laplacian-like sharpness map."""
    try:
        img = Image.open(image_path).convert("L")
        lap = img.filter(ImageFilter.FIND_EDGES)
        lap_np = np.asarray(lap, dtype=np.float32)
        lap_np = 255 * (lap_np - lap_np.min()) / \
            (lap_np.max() - lap_np.min() + 1e-5)
        return Image.fromarray(lap_np.astype(np.uint8))
    except Exception as e:
        print(f"[SHARPNESS MAP ERROR] {e}")
        return None

# ============================================================
# ------------------------ ENTROPY MAP ------------------------
# ============================================================


def patch_entropy(patch):
    """Shannon entropy for a grayscale patch."""
    hist, _ = np.histogram(patch.flatten(), bins=256, range=(0, 255))
    p = hist / (hist.sum() + 1e-5)
    p = p[p > 0]
    return -np.sum(p * np.log2(p))


def entropy_map(image_path, patch_size=16):
    """Compute local Shannon entropy over sliding patches."""
    img = Image.open(image_path).convert("L")
    arr = np.asarray(img, dtype=np.uint8)

    h, w = arr.shape
    ent = np.zeros((h, w), dtype=np.float32)

    for y in range(0, h - patch_size, patch_size):
        for x in range(0, w - patch_size, patch_size):
            patch = arr[y:y+patch_size, x:x+patch_size]
            e = patch_entropy(patch)
            ent[y:y+patch_size, x:x+patch_size] = e

    ent = 255 * (ent - ent.min()) / (ent.max() - ent.min() + 1e-5)
    return Image.fromarray(ent.astype(np.uint8))

# ============================================================
# -------------------------- SSIM MAP -------------------------
# ============================================================


def ssim_map(original_img, compressed_img):
    """Compute SSIM-like difference surface."""
    A = np.asarray(original_img.convert("L"), dtype=np.float32)
    B = np.asarray(compressed_img.convert("L"), dtype=np.float32)

    C1, C2 = 6.5025, 58.5225
    muA = A.mean()
    muB = B.mean()
    sigmaA = A.std()
    sigmaB = B.std()
    covariance = ((A - muA) * (B - muB)).mean()

    ssim_val = ((2 * muA * muB + C1) * (2 * covariance + C2)) / \
               ((muA**2 + muB**2 + C1) * (sigmaA**2 + sigmaB**2 + C2))

    diff = np.abs(A - B)
    diff = (255 * diff / (diff.max() + 1e-5)).astype(np.uint8)
    diff_img = Image.fromarray(diff)

    return diff_img, float(ssim_val)

# ============================================================
# ------------------------ THRESHOLD MASK ---------------------
# ============================================================


def threshold_ela(ela_img, threshold=40):
    """Generate binary mask of high-error areas."""
    ela_np = np.asarray(ela_img.convert("L"))
    mask = (ela_np > threshold).astype(np.uint8) * 255
    return Image.fromarray(mask)

# ============================================================
# ----------------------- MASTER REPORT -----------------------
# ============================================================


def forensic_analysis(image_path, qualities=[75, 85, 95], error_scale=10, overlay_opacity=0.5):
    """
    Full forensic pipeline returning all maps + metrics in one dictionary.
    Streamlit-ready.
    """
    # ---------- ELA ----------
    ela_results = ela_multi_quality(
        image_path, qualities, error_scale=error_scale, overlay_opacity=overlay_opacity
    )

    # Use first quality in list as primary quality
    primary_quality = qualities[0] if qualities else 90

    # Primary ELA for downstream use
    ela_primary, overlay_primary, metrics_primary = perform_ela(
        image_path, quality=primary_quality, error_scale=error_scale, overlay_opacity=overlay_opacity
    )

    # Block-based statistics
    block_stats = block_ela_stats(ela_primary)

    # Noise / Sharpness / Entropy
    noise = noise_map(image_path)
    sharp = sharpness_map(image_path)
    entropy = entropy_map(image_path)

    # SSIM
    original = Image.open(image_path)
    buffer = io.BytesIO()
    original.save(buffer, "JPEG", quality=primary_quality)
    buffer.seek(0)
    compressed_primary = Image.open(buffer)
    ssim_img, ssim_score = ssim_map(original, compressed_primary)

    # Combined Report - using consistent key names
    report = {
        "ela_multi_quality": ela_results,
        "ela_90": ela_primary,  # Keep "ela_90" key for backward compatibility
        "ela_90_overlay": overlay_primary,
        "ela_90_metrics": metrics_primary,
        "block_stats": block_stats,
        "noise_map": noise,
        "sharpness_map": sharp,
        "entropy_map": entropy,
        "ssim_img": ssim_img,
        "ssim_score": ssim_score,
        "threshold_mask": threshold_ela(ela_primary, 40)
    }

    return report
