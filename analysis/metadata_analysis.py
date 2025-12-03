import piexif
from PIL import Image
import os
import hashlib
import struct
from datetime import datetime
import json
import re

# ============================================================
# ---------------------- CORE METADATA ------------------------
# ============================================================


def extract_metadata(image_path):
    """
    Extracts and returns comprehensive metadata from an image.

    Returns:
        dict: Dictionary containing organized metadata
    """
    data = {
        "basic_info": {},
        "exif": {},
        "gps": {},
        "camera": {},
        "software": {},
        "timestamps": {},
        "thumbnail": {},
        "warnings": []
    }

    try:
        # Basic file info
        file_stats = os.stat(image_path)
        data["basic_info"] = {
            "filename": os.path.basename(image_path),
            "file_size_bytes": file_stats.st_size,
            "file_size_mb": round(file_stats.st_size / (1024 * 1024), 2),
            "file_created": datetime.fromtimestamp(file_stats.st_ctime).isoformat(),
            "file_modified": datetime.fromtimestamp(file_stats.st_mtime).isoformat(),
            "file_accessed": datetime.fromtimestamp(file_stats.st_atime).isoformat()
        }

        # PIL basic info
        img = Image.open(image_path)
        data["basic_info"].update({
            "format": img.format,
            "size": img.size,
            "width": img.size[0],
            "height": img.size[1],
            "mode": img.mode,
            "megapixels": round((img.size[0] * img.size[1]) / 1_000_000, 2)
        })

        # Try EXIF extraction
        exif_dict = piexif.load(image_path)

        # Helper function to decode bytes
        def decode_tag(v):
            if isinstance(v, bytes):
                try:
                    return v.decode('utf-8', errors='ignore').strip('\x00')
                except:
                    return repr(v)
            elif isinstance(v, tuple):
                return [decode_tag(x) for x in v]
            return v

        # Process 0th IFD (main image tags)
        if "0th" in exif_dict:
            for tag, value in exif_dict["0th"].items():
                tag_name = piexif.TAGS["0th"][tag]["name"]
                decoded = decode_tag(value)

                # Categorize tags
                if tag_name in ["Make", "Model"]:
                    data["camera"][tag_name] = decoded
                elif tag_name in ["Software", "ProcessingSoftware", "HostComputer"]:
                    data["software"][tag_name] = decoded
                elif tag_name in ["DateTime", "DateTimeOriginal", "DateTimeDigitized"]:
                    data["timestamps"][tag_name] = decoded
                else:
                    data["exif"][tag_name] = decoded

        # Process Exif IFD (detailed EXIF)
        if "Exif" in exif_dict:
            for tag, value in exif_dict["Exif"].items():
                tag_name = piexif.TAGS["Exif"][tag]["name"]
                decoded = decode_tag(value)

                if tag_name in ["DateTimeOriginal", "DateTimeDigitized", "SubSecTime"]:
                    data["timestamps"][tag_name] = decoded
                elif tag_name.startswith("Lens") or "Focal" in tag_name or "Aperture" in tag_name:
                    data["camera"][tag_name] = decoded
                else:
                    data["exif"][tag_name] = decoded

        # Process GPS IFD
        if "GPS" in exif_dict and exif_dict["GPS"]:
            for tag, value in exif_dict["GPS"].items():
                tag_name = piexif.TAGS["GPS"][tag]["name"]
                decoded = decode_tag(value)
                data["gps"][tag_name] = decoded

            # Try to extract coordinates
            try:
                gps_coords = extract_gps_coordinates(exif_dict["GPS"])
                if gps_coords:
                    data["gps"]["coordinates"] = gps_coords
            except:
                pass

        # Process 1st IFD (thumbnail)
        if "1st" in exif_dict and exif_dict["1st"]:
            data["thumbnail"]["present"] = True
            for tag, value in exif_dict["1st"].items():
                tag_name = piexif.TAGS["1st"][tag]["name"]
                data["thumbnail"][tag_name] = decode_tag(value)

        # Additional PIL info
        if hasattr(img, 'info') and img.info:
            for key, value in img.info.items():
                if key not in ["exif", "jfif", "jfif_version", "jfif_unit"]:
                    data["exif"][key] = str(value)

    except Exception as e:
        data["warnings"].append(f"Metadata extraction error: {str(e)}")

    return data

# ============================================================
# -------------------- GPS EXTRACTION -------------------------
# ============================================================


def extract_gps_coordinates(gps_ifd):
    """Extract human-readable GPS coordinates from GPS IFD."""
    try:
        def convert_to_degrees(value):
            d = float(value[0][0]) / float(value[0][1])
            m = float(value[1][0]) / float(value[1][1])
            s = float(value[2][0]) / float(value[2][1])
            return d + (m / 60.0) + (s / 3600.0)

        lat = convert_to_degrees(gps_ifd.get(
            piexif.GPSIFD.GPSLatitude, [(0, 1), (0, 1), (0, 1)]))
        lon = convert_to_degrees(gps_ifd.get(
            piexif.GPSIFD.GPSLongitude, [(0, 1), (0, 1), (0, 1)]))

        lat_ref = gps_ifd.get(piexif.GPSIFD.GPSLatitudeRef, b'N').decode()
        lon_ref = gps_ifd.get(piexif.GPSIFD.GPSLongitudeRef, b'E').decode()

        if lat_ref == 'S':
            lat = -lat
        if lon_ref == 'W':
            lon = -lon

        return {
            "latitude": round(lat, 6),
            "longitude": round(lon, 6),
            "google_maps": f"https://www.google.com/maps?q={lat},{lon}"
        }
    except:
        return None


# ============================================================
# ------------------- FORENSIC CHECKS -------------------------
# ============================================================

def detect_anomalies(metadata):
    """
    Detect suspicious patterns in metadata that suggest manipulation.

    Returns:
        dict: Anomaly findings with severity levels
    """
    anomalies = {
        "critical": [],
        "warning": [],
        "info": [],
        "authenticity_score": 100  # Start at 100, deduct for issues
    }

    score = 100

    # 1. Check for missing EXIF (stripped metadata)
    if not metadata["exif"] and not metadata["camera"]:
        anomalies["critical"].append(
            "No EXIF data found - metadata may have been stripped")
        score -= 30

    # 2. Check for timestamp inconsistencies
    timestamps = metadata["timestamps"]
    if timestamps:
        # File modification should be >= EXIF creation
        try:
            file_mod = datetime.fromisoformat(
                metadata["basic_info"]["file_modified"])

            for key in ["DateTimeOriginal", "DateTimeDigitized", "DateTime"]:
                if key in timestamps:
                    # Parse EXIF date format: "2023:12:25 14:30:45"
                    exif_time_str = timestamps[key]
                    if isinstance(exif_time_str, str) and ":" in exif_time_str:
                        exif_time = datetime.strptime(
                            exif_time_str, "%Y:%m:%d %H:%M:%S")

                        # Check if file is older than photo date (impossible)
                        if file_mod < exif_time:
                            anomalies["warning"].append(
                                f"File modified date ({file_mod}) is before EXIF {key} ({exif_time})"
                            )
                            score -= 15
        except Exception as e:
            anomalies["info"].append(
                f"Could not validate timestamps: {str(e)}")

    # 3. Software/Editor detection
    software = metadata["software"]
    editing_software = [
        "photoshop", "gimp", "paint.net", "affinity", "pixlr",
        "lightroom", "snapseed", "vsco", "facetune"
    ]

    for key, value in software.items():
        value_lower = str(value).lower()
        for editor in editing_software:
            if editor in value_lower:
                anomalies["warning"].append(f"Image edited with: {value}")
                score -= 10
                break

    # 4. Check for thumbnail inconsistencies
    if metadata["thumbnail"].get("present"):
        try:
            main_width = metadata["basic_info"]["width"]
            main_height = metadata["basic_info"]["height"]
            thumb_width = metadata["thumbnail"].get("ImageWidth")
            thumb_height = metadata["thumbnail"].get("ImageLength")

            if thumb_width and thumb_height:
                main_ratio = main_width / main_height
                thumb_ratio = thumb_width / thumb_height

                if abs(main_ratio - thumb_ratio) > 0.1:
                    anomalies["warning"].append(
                        f"Thumbnail aspect ratio mismatch: Main={main_ratio:.2f}, Thumb={thumb_ratio:.2f}"
                    )
                    score -= 10
        except:
            pass

    # 5. Resolution anomalies
    width = metadata["basic_info"]["width"]
    height = metadata["basic_info"]["height"]

    # Check for non-standard resolutions
    if width % 16 != 0 or height % 16 != 0:
        anomalies["info"].append(
            f"Non-standard resolution ({width}x{height}) - may indicate cropping"
        )

    # 6. Camera make/model consistency
    camera = metadata["camera"]
    if camera.get("Make") and camera.get("Model"):
        make = str(camera["Make"]).lower()
        model = str(camera["Model"]).lower()

        # Check if model contains make (it should)
        if make not in model and make != "":
            # Exception for some brands
            exceptions = ["canon", "nikon", "sony", "apple"]
            if make not in exceptions:
                anomalies["info"].append(
                    f"Camera make '{camera['Make']}' not in model '{camera['Model']}'"
                )

    # 7. Check for GPS tampering indicators
    if metadata["gps"]:
        if "coordinates" in metadata["gps"]:
            coords = metadata["gps"]["coordinates"]
            # Check for suspicious coordinates (0,0 or perfect round numbers)
            if coords["latitude"] == 0 and coords["longitude"] == 0:
                anomalies["warning"].append(
                    "GPS coordinates at (0,0) - likely fake")
                score -= 15

    anomalies["authenticity_score"] = max(0, score)
    return anomalies


# ============================================================
# ------------------- FILE STRUCTURE CHECKS -------------------
# ============================================================

def analyze_file_structure(image_path):
    """
    Deep analysis of file structure and binary signatures.

    Returns:
        dict: File structure analysis
    """
    analysis = {
        "signature": {},
        "jpeg_structure": {},
        "integrity": {},
        "warnings": []
    }

    try:
        with open(image_path, 'rb') as f:
            # Read first 12 bytes for signature
            header = f.read(12)

            # Detect file signature
            if header[:2] == b'\xff\xd8':
                analysis["signature"]["type"] = "JPEG"
                analysis["signature"]["valid"] = True

                # Check JPEG end marker
                f.seek(-2, 2)
                end_marker = f.read(2)
                analysis["signature"]["has_eoi"] = (end_marker == b'\xff\xd9')

                if not analysis["signature"]["has_eoi"]:
                    analysis["warnings"].append(
                        "JPEG missing End-Of-Image marker (FFD9)")

                # Analyze JPEG segments
                f.seek(0)
                jpeg_info = parse_jpeg_segments(f)
                analysis["jpeg_structure"] = jpeg_info

            elif header[:8] == b'\x89PNG\r\n\x1a\n':
                analysis["signature"]["type"] = "PNG"
                analysis["signature"]["valid"] = True

            elif header[:2] in [b'II', b'MM']:
                analysis["signature"]["type"] = "TIFF"
                analysis["signature"]["valid"] = True

            elif header[:6] in [b'GIF87a', b'GIF89a']:
                analysis["signature"]["type"] = "GIF"
                analysis["signature"]["valid"] = True

            elif header[:4] == b'RIFF' and header[8:12] == b'WEBP':
                analysis["signature"]["type"] = "WEBP"
                analysis["signature"]["valid"] = True

            else:
                analysis["signature"]["type"] = "Unknown"
                analysis["signature"]["valid"] = False
                analysis["warnings"].append(
                    f"Unknown file signature: {header[:4].hex()}")

        # File hash
        analysis["integrity"]["md5"] = compute_hash(image_path, "md5")
        analysis["integrity"]["sha256"] = compute_hash(image_path, "sha256")

    except Exception as e:
        analysis["warnings"].append(f"File structure analysis error: {str(e)}")

    return analysis


def parse_jpeg_segments(file_obj):
    """Parse JPEG file segments for forensic analysis."""
    segments = []
    double_compressed = False
    has_thumbnail = False

    try:
        while True:
            marker = file_obj.read(2)
            if not marker or marker[0] != 0xFF:
                break

            marker_type = marker[1]

            # SOI (Start of Image)
            if marker_type == 0xD8:
                segments.append("SOI")

            # EOI (End of Image)
            elif marker_type == 0xD9:
                segments.append("EOI")
                break

            # APP segments
            elif 0xE0 <= marker_type <= 0xEF:
                length_bytes = file_obj.read(2)
                length = struct.unpack('>H', length_bytes)[0]
                segment_data = file_obj.read(length - 2)

                app_name = f"APP{marker_type - 0xE0}"
                segments.append(app_name)

                # Check for thumbnail in APP1
                if marker_type == 0xE1 and b'Exif' in segment_data[:6]:
                    has_thumbnail = b'\xff\xd8' in segment_data[6:]

            # DQT (Quantization Table) - multiple DQTs suggest recompression
            elif marker_type == 0xDB:
                segments.append("DQT")
                length_bytes = file_obj.read(2)
                length = struct.unpack('>H', length_bytes)[0]
                file_obj.read(length - 2)

                # Count DQTs
                dqt_count = segments.count("DQT")
                if dqt_count > 2:
                    double_compressed = True

            # SOF (Start of Frame)
            elif 0xC0 <= marker_type <= 0xCF and marker_type not in [0xC4, 0xC8, 0xCC]:
                segments.append(f"SOF{marker_type - 0xC0}")
                length_bytes = file_obj.read(2)
                length = struct.unpack('>H', length_bytes)[0]
                file_obj.read(length - 2)

            # Other markers
            else:
                if marker_type not in [0x00, 0x01]:  # Skip padding
                    length_bytes = file_obj.read(2)
                    if len(length_bytes) == 2:
                        length = struct.unpack('>H', length_bytes)[0]
                        file_obj.read(length - 2)

    except Exception as e:
        pass

    return {
        "segment_sequence": segments,
        "total_segments": len(segments),
        "double_compressed_indicator": double_compressed,
        "has_embedded_thumbnail": has_thumbnail
    }


def compute_hash(file_path, algorithm="md5"):
    """Compute file hash for integrity verification."""
    hash_func = hashlib.new(algorithm)

    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            hash_func.update(chunk)

    return hash_func.hexdigest()


# ============================================================
# -------------------- MASTER FUNCTION ------------------------
# ============================================================

def full_metadata_analysis(image_path):
    """
    Complete metadata forensic analysis.

    Returns:
        dict: Comprehensive metadata report
    """
    report = {
        "metadata": extract_metadata(image_path),
        "anomalies": {},
        "file_structure": {},
        "summary": {}
    }

    # Get anomalies
    report["anomalies"] = detect_anomalies(report["metadata"])

    # File structure analysis
    report["file_structure"] = analyze_file_structure(image_path)

    # Generate summary
    score = report["anomalies"]["authenticity_score"]
    total_warnings = (
        len(report["anomalies"]["critical"]) +
        len(report["anomalies"]["warning"]) +
        len(report["file_structure"]["warnings"])
    )

    if score >= 80:
        verdict = "LIKELY AUTHENTIC"
    elif score >= 50:
        verdict = "SUSPICIOUS"
    else:
        verdict = "LIKELY MANIPULATED"

    report["summary"] = {
        "authenticity_score": score,
        "verdict": verdict,
        "total_warnings": total_warnings,
        "has_exif": bool(report["metadata"]["exif"]),
        "has_gps": bool(report["metadata"]["gps"]),
        "edited": bool(report["metadata"]["software"]),
        "file_type": report["file_structure"]["signature"].get("type", "Unknown")
    }

    return report


# ============================================================
# -------------------- EXPORT FUNCTIONS -----------------------
# ============================================================

def export_metadata_report(report, output_path):
    """Export full report as JSON."""
    try:
        # Convert non-serializable objects
        def convert(obj):
            if isinstance(obj, bytes):
                return obj.decode('utf-8', errors='ignore')
            return obj

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, default=convert)

        return True
    except Exception as e:
        print(f"Export error: {e}")
        return False
