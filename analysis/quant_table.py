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
            return {"error": "Not a JPEG image"}

        # Extract quantization tables if available
        result = {
            "format": img.format,
            "has_quantization_info": hasattr(img, 'quantization'),
            "image_size": img.size,
            "analysis": "JPEG quantization table forensics pending",
            "note": "Detailed quantization analysis requires JPEG marker parsing"
        }

        if hasattr(img, 'quantization'):
            result["quantization_tables"] = img.quantization

        return result

    except Exception as e:
        return {"error": str(e), "analysis": "Failed to analyze quantization table"}
