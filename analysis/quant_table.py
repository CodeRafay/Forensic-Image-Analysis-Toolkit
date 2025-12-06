import struct
import numpy as np
from pathlib import Path


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

            # Estimate quality from quantization table
            # Standard JPEG tables scale linearly with quality
            quality_estimate = estimate_jpeg_quality(table_array)

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
            if not is_standard_table(table_array):
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
    Extracts quantization tables by parsing JPEG markers.

    Args:
        image_path (str): Path to JPEG file

    Returns:
        dict: Dictionary of quantization tables {table_id: [64 values]}
    """
    try:
        with open(image_path, 'rb') as f:
            data = f.read()

        qtables = {}
        pos = 0

        # Look for DQT (Define Quantization Table) markers (0xFFDB)
        while pos < len(data) - 1:
            if data[pos] == 0xFF and data[pos + 1] == 0xDB:
                # Found DQT marker
                pos += 2

                # Read length
                if pos + 2 > len(data):
                    break
                length = struct.unpack('>H', data[pos:pos+2])[0]
                pos += 2

                # Read table data
                table_data = data[pos:pos+length-2]

                # Parse table(s)
                idx = 0
                while idx < len(table_data):
                    if idx >= len(table_data):
                        break

                    # Precision and table ID
                    pq_tq = table_data[idx]
                    precision = (pq_tq >> 4) & 0x0F  # 0 = 8-bit, 1 = 16-bit
                    table_id = pq_tq & 0x0F
                    idx += 1

                    # Read 64 values
                    table_size = 64
                    value_size = 2 if precision == 1 else 1

                    table_values = []
                    for i in range(table_size):
                        if idx >= len(table_data):
                            break
                        if value_size == 2:
                            if idx + 1 < len(table_data):
                                val = struct.unpack(
                                    '>H', table_data[idx:idx+2])[0]
                                idx += 2
                            else:
                                break
                        else:
                            val = table_data[idx]
                            idx += 1
                        table_values.append(val)

                    if len(table_values) == 64:
                        qtables[table_id] = table_values

                pos += length - 2
            else:
                pos += 1

        return qtables

    except Exception:
        return {}


def estimate_jpeg_quality(qtable):
    """
    Estimates JPEG quality from quantization table.

    Args:
        qtable (np.array): 64-element quantization table

    Returns:
        int: Estimated quality (0-100)
    """
    # Standard JPEG quantization table for quality 50
    standard_luminance = np.array([
        16, 11, 10, 16, 24, 40, 51, 61,
        12, 12, 14, 19, 26, 58, 60, 55,
        14, 13, 16, 24, 40, 57, 69, 56,
        14, 17, 22, 29, 51, 87, 80, 62,
        18, 22, 37, 56, 68, 109, 103, 77,
        24, 35, 55, 64, 81, 104, 113, 92,
        49, 64, 78, 87, 103, 121, 120, 101,
        72, 92, 95, 98, 112, 100, 103, 99
    ])

    if len(qtable) != 64:
        return 50  # default

    qtable_flat = qtable.flatten() if hasattr(qtable, 'flatten') else qtable

    # Compare with standard table
    # Quality = 100 when qtable values are minimal
    # Quality = 0 when qtable values are very high

    # Compare first few values
    avg_ratio = np.mean(qtable_flat[:8]) / standard_luminance[0]

    if avg_ratio < 0.5:
        quality = 95
    elif avg_ratio < 1.0:
        quality = 85
    elif avg_ratio < 2.0:
        quality = 70
    elif avg_ratio < 3.0:
        quality = 50
    else:
        quality = 30

    return quality


def is_standard_table(qtable):
    """
    Checks if quantization table follows standard JPEG patterns.

    Args:
        qtable (np.array): Quantization table

    Returns:
        bool: True if appears to be standard
    """
    # Check if values increase towards bottom-right (standard pattern)
    # This is a simplified check
    if len(qtable) != 64:
        return False

    try:
        # Reshape to 8x8 if flat
        if hasattr(qtable, 'shape') and len(qtable.shape) == 1:
            qtable_2d = qtable.reshape(8, 8)
        else:
            qtable_2d = np.array(qtable).reshape(8, 8)

        # Check if top-left (DC) is smaller than bottom-right (high freq)
        # Standard tables have lower values for low frequencies
        top_left_avg = np.mean(qtable_2d[:2, :2])
        bottom_right_avg = np.mean(qtable_2d[-2:, -2:])

        return top_left_avg < bottom_right_avg * 0.8
    except:
        return True  # Assume standard if can't verify
