import numpy as np


def analyze_quantization_table(image_path):
    """
    Analyzes JPEG quantization tables for forensics.
    Abnormal quantization tables can indicate image manipulation.

    Args:
        image_path (str): Path to the JPEG image

    Returns:
        dict: Quantization table analysis results
    """
    try:
        from PIL import Image
        img = Image.open(image_path)

        if img.format != 'JPEG':
            return {
                "status": "not_jpeg",
                "error": "Not a JPEG image - quantization tables only exist in JPEG format",
                "format": img.format
            }

        # Try to extract quantization tables from JPEG markers
        qtables = extract_jpeg_quantization_tables(image_path)

        if not qtables:
            # Fallback: use PIL's quantization info if available
            result = {
                "status": "limited_info",
                "format": "JPEG",
                "image_size": img.size,
                "note": "Quantization tables not directly accessible"
            }

            if hasattr(img, 'quantization'):
                result["pil_quantization_info"] = str(img.quantization)
                result["status"] = "partial"

            return result

        # Analyze extracted quantization tables
        analysis = {
            "status": "success",
            "format": "JPEG",
            "image_size": img.size,
            "quantization_tables": {}
        }

        warnings = []

        for table_id, qtable in qtables.items():
            table_array = np.array(qtable)

            # Estimate quality by inverting the IJG scaling. Table 0 is
            # luminance, the rest chrominance — they use different standards.
            quality_estimate = estimate_jpeg_quality(table_array, table_id)

            # Analyze table characteristics
            table_analysis = {
                "table_values": qtable,
                "min_value": int(np.min(table_array)),
                "max_value": int(np.max(table_array)),
                "mean_value": float(np.mean(table_array)),
                "estimated_quality": quality_estimate,
                "table_size": len(qtable)
            }

            # Check for anomalies
            if quality_estimate < 50:
                warnings.append(
                    f"Table {table_id}: Low quality ({quality_estimate}) - high compression")

            # Check for non-standard tables
            if not is_standard_table(table_array, table_id):
                warnings.append(
                    f"Table {table_id}: Non-standard quantization table detected - possible editing software")

            analysis["quantization_tables"][f"table_{table_id}"] = table_analysis

        analysis["warnings"] = warnings
        analysis["interpretation"] = "Standard tables = camera original; non-standard = editing software used"

        return analysis

    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


def extract_jpeg_quantization_tables(image_path):
    """
    Extracts quantization tables from a JPEG.

    Uses Pillow's JPEG decoder, which walks the marker structure properly.
    A naive byte-scan for the DQT marker (0xFFDB) cannot be used here: that
    byte pair also occurs inside entropy-coded scan data and inside APP
    segments such as XMP, which yields dozens of tables built from unrelated
    bytes. Pillow returns each table de-zigzagged into raster order, which is
    the order `estimate_jpeg_quality` and `is_standard_table` expect.

    Args:
        image_path (str): Path to JPEG file

    Returns:
        dict: Dictionary of quantization tables {table_id: [64 values]}
    """
    try:
        from PIL import Image

        with Image.open(image_path) as img:
            tables = getattr(img, 'quantization', None) or {}
            # array.array -> plain list, and drop anything malformed
            return {
                int(table_id): list(values)
                for table_id, values in tables.items()
                if len(values) == 64
            }

    except Exception:
        return {}


# Standard IJG quantization tables for quality 50, in raster order.
# Pillow returns tables de-zigzagged, so these line up element for element.
STANDARD_LUMINANCE = np.array([
    16, 11, 10, 16, 24, 40, 51, 61,
    12, 12, 14, 19, 26, 58, 60, 55,
    14, 13, 16, 24, 40, 57, 69, 56,
    14, 17, 22, 29, 51, 87, 80, 62,
    18, 22, 37, 56, 68, 109, 103, 77,
    24, 35, 55, 64, 81, 104, 113, 92,
    49, 64, 78, 87, 103, 121, 120, 101,
    72, 92, 95, 98, 112, 100, 103, 99
])

STANDARD_CHROMINANCE = np.array([
    17, 18, 24, 47, 99, 99, 99, 99,
    18, 21, 26, 66, 99, 99, 99, 99,
    24, 26, 56, 99, 99, 99, 99, 99,
    47, 66, 99, 99, 99, 99, 99, 99,
    99, 99, 99, 99, 99, 99, 99, 99,
    99, 99, 99, 99, 99, 99, 99, 99,
    99, 99, 99, 99, 99, 99, 99, 99,
    99, 99, 99, 99, 99, 99, 99, 99
])


def _standard_table(table_id):
    """Table 0 is luminance; any other id is chrominance."""
    return STANDARD_LUMINANCE if table_id == 0 else STANDARD_CHROMINANCE


def estimate_jpeg_quality(qtable, table_id=0):
    """
    Estimates JPEG quality from a quantization table.

    Inverts the IJG scaling that libjpeg applies when building a table:

        scale = 5000/quality        if quality < 50
        scale = 200 - 2*quality     otherwise
        Q[i]  = clip((T50[i]*scale + 50) / 100, 1, 255)

    so scale is recovered per entry as (100*Q[i] - 50) / T50[i] and inverted
    back to a quality. Entries clipped at 1 or 255 carry no scale information
    and are excluded.

    Args:
        qtable: 64-element quantization table (raster order)
        table_id (int): 0 for luminance, otherwise chrominance

    Returns:
        int: Estimated quality (1-100)
    """
    q = np.asarray(qtable, dtype=np.float64).ravel()
    if q.size != 64:
        return 50  # default

    standard = _standard_table(table_id).astype(np.float64)

    # Saturated entries pin to the clip bounds and would bias the estimate
    usable = (q > 1) & (q < 255)
    if not usable.any():
        # Everything saturated: all 1s means maximum quality, all 255s minimum
        return 100 if q.max() <= 1 else 1

    scales = (100.0 * q[usable] - 50.0) / standard[usable]
    scale = float(np.median(scales))  # median resists a few odd entries

    if scale <= 0:
        return 100
    quality = 5000.0 / scale if scale > 100 else (200.0 - scale) / 2.0

    return int(round(min(100.0, max(1.0, quality))))


def is_standard_table(qtable, table_id=0, tolerance=0.02):
    """
    Checks whether a table is a scaled version of the standard IJG table.

    A camera or a standard encoder produces T50 scaled by a single factor, so
    every entry divided by its standard counterpart gives the same ratio.
    Editing software with custom tables breaks that proportionality. The
    previous check only tested that values grow toward high frequencies, which
    nearly every table does, so it flagged almost nothing.

    Args:
        qtable: 64-element quantization table (raster order)
        table_id (int): 0 for luminance, otherwise chrominance
        tolerance (float): Allowed relative spread in the per-entry ratios,
            absorbing the integer rounding libjpeg applies

    Returns:
        bool: True if the table matches the standard family
    """
    q = np.asarray(qtable, dtype=np.float64).ravel()
    if q.size != 64:
        return False

    standard = _standard_table(table_id).astype(np.float64)

    # Clipped entries lost their ratio; judge on the rest
    usable = (q > 1) & (q < 255)
    if usable.sum() < 8:
        return True  # too little information to call it non-standard

    ratios = q[usable] / standard[usable]
    median = np.median(ratios)
    if median <= 0:
        return False

    # Rounding to integers perturbs small quantizer values most, so allow the
    # spread to scale with the rounding step (0.5/standard) as well.
    allowed = tolerance + (0.5 / standard[usable]) / median
    return bool(np.mean(np.abs(ratios - median) / median <= allowed) >= 0.9)
