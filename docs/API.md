# API Documentation - Veritas Forensic Analysis Toolkit

## Analysis Module API Reference

All analysis modules follow a consistent pattern and return standardized result dictionaries.

---

## Core Modules

### 1. Error Level Analysis (`ela.py`)

#### `perform_ela(image_path, quality=95, error_scale=10, overlay_opacity=0.5)`

Performs Error Level Analysis on an image.

**Parameters:**

- `image_path` (str): Path to the image file
- `quality` (int, optional): JPEG quality for recompression (default: 95)
- `error_scale` (int, optional): Scale factor for error visualization (default: 10)
- `overlay_opacity` (float, optional): Opacity for overlay blend (default: 0.5)

**Returns:**

- `ela_img` (PIL.Image): ELA visualization (grayscale)
- `ela_overlay` (PIL.Image): ELA blended with original
- `metrics` (dict): Analysis metrics including:
  - `mean_error`: Average error level
  - `max_error`: Maximum error detected
  - `std_error`: Standard deviation of errors
  - `suspicious_areas_percent`: Percentage of high-error regions

**Example:**

```python
from analysis import ela

ela_img, overlay, metrics = ela.perform_ela("image.jpg", quality=90)
print(f"Mean error: {metrics['mean_error']}")
```

#### `multi_quality_ela(image_path, qualities=[70, 85, 95])`

Runs ELA at multiple quality levels for comparison.

**Parameters:**

- `image_path` (str): Path to the image
- `qualities` (list): List of JPEG quality values

**Returns:**

- `results` (dict): Dictionary mapping quality → ELA results

---

### 2. Metadata Analysis (`metadata_analysis.py`)

#### `extract_metadata(image_path)`

Extracts comprehensive metadata from an image.

**Parameters:**

- `image_path` (str): Path to the image file

**Returns:**

- `metadata` (dict): Organized metadata with sections:
  - `basic_info`: File size, format, dimensions
  - `exif`: Camera settings, ISO, aperture, etc.
  - `gps`: GPS coordinates if available
  - `camera`: Camera make, model, serial
  - `software`: Editing software used
  - `timestamps`: Creation, modification dates
  - `thumbnail`: Embedded thumbnail info
  - `warnings`: List of suspicious findings

**Example:**

```python
from analysis import metadata_analysis

meta = metadata_analysis.extract_metadata("image.jpg")
if meta['gps']:
    print(f"Location: {meta['gps']['latitude']}, {meta['gps']['longitude']}")
```

#### `detect_thumbnail_mismatch(image_path)`

Checks if embedded thumbnail matches the main image.

**Returns:**

- `mismatch` (bool): True if mismatch detected
- `details` (dict): Comparison metrics

---

### 3. Histogram Analysis (`histogram_analysis.py`)

#### `generate_histogram(image_path)`

Generates RGB histogram visualization.

**Parameters:**

- `image_path` (str): Path to the image

**Returns:**

- `hist_path` (str): Path to saved histogram image
- `stats` (dict): Statistical metrics per channel

**Example:**

```python
from analysis import histogram_analysis

hist_path, stats = histogram_analysis.generate_histogram("image.jpg")
print(f"Red channel mean: {stats['red']['mean']}")
```

#### `detect_histogram_anomalies(image_path)`

Detects statistical anomalies in histogram.

**Returns:**

- `anomalies` (list): List of detected anomalies
- `severity` (str): "low", "medium", or "high"

---

### 4. Noise Map (`noise_map.py`)

#### `generate_noise_map(image_path)`

Generates noise map using high-pass filtering.

**Parameters:**

- `image_path` (str): Path to the image

**Returns:**

- `noise_img` (PIL.Image): Noise map visualization
- `metrics` (dict): Noise consistency metrics

---

### 5. JPEG Ghost (`jpeg_ghost.py`)

#### `detect_ghost(image_path, quality_steps=(90, 70, 50))`

Detects JPEG compression ghosts.

**Parameters:**

- `image_path` (str): Path to the image
- `quality_steps` (tuple): Quality levels to test

**Returns:**

- `ghost_img` (PIL.Image): Ghost visualization
- `analysis` (dict): Detected compression levels

---

### 6. Quantization Table Analysis (`quant_table.py`)

#### `analyze_quantization_table(image_path)`

Analyzes JPEG quantization tables.

**Parameters:**

- `image_path` (str): Path to JPEG image

**Returns:**

- `analysis` (dict): Quantization table analysis
  - `tables`: Extracted Q-tables
  - `anomalies`: Detected irregularities
  - `likely_quality`: Estimated original quality

---

### 7. Copy-Move Forgery Detection (`cmfd.py`)

#### `detect_copy_move(image_path, block_size=32, threshold=100)`

Detects copied and moved regions.

**Parameters:**

- `image_path` (str): Path to the image
- `block_size` (int): Block size for matching (default: 32)
- `threshold` (int): Similarity threshold (default: 100)

**Returns:**

- `result` (dict): Detection results
  - `duplicates_found` (bool): Whether duplicates detected
  - `regions` (list): List of matched regions
  - `confidence` (float): Detection confidence

**Example:**

```python
from analysis import cmfd

result = cmfd.detect_copy_move("image.jpg", block_size=16)
if result['duplicates_found']:
    print(f"Found {len(result['regions'])} duplicate regions")
```

---

### 8. PRNU Analysis (`prnu.py`)

#### `analyze_prnu(image_path, reference_image_path=None)`

Analyzes Photo Response Non-Uniformity.

**Parameters:**

- `image_path` (str): Path to test image
- `reference_image_path` (str, optional): Reference from same camera

**Returns:**

- `analysis` (dict): PRNU metrics
  - `noise_residual_variance`: PRNU strength
  - `correlation`: Correlation with reference (if provided)
  - `camera_match`: Boolean indicating likely same camera

---

### 9. Frequency Analysis (`frequency_analysis.py`)

#### `analyze_frequency_domain(image_path)`

Performs FFT analysis for tampering detection.

**Parameters:**

- `image_path` (str): Path to the image

**Returns:**

- `analysis` (dict): Frequency domain metrics
  - `magnitude_spectrum`: FFT magnitude stats
  - `phase_consistency`: Phase uniformity metric
  - `anomaly_score`: Tampering likelihood

#### `detect_dct_anomalies(image_path)`

Analyzes DCT coefficients for irregularities.

**Returns:**

- `anomalies` (dict): DCT anomaly metrics

---

### 10. Deepfake Detection (`deepfake_detector.py`)

#### `detect_deepfake_artifacts(image_path)`

Detects common GAN/deepfake artifacts.

**Parameters:**

- `image_path` (str): Path to the image

**Returns:**

- `analysis` (dict): Deepfake detection results
  - `artifacts`: Dictionary of detected artifacts
  - `likelihood`: "low", "medium", or "high"
  - `confidence`: 0.0-1.0 confidence score

#### `detect_gan_fingerprint(image_path)`

Detects specific GAN architecture fingerprints.

**Returns:**

- `fingerprint` (dict): GAN fingerprint analysis

---

### 11. Resampling Detection (`resampling_detector.py`)

#### `detect_resampling(image_path)`

Detects image resampling artifacts.

**Parameters:**

- `image_path` (str): Path to the image

**Returns:**

- `analysis` (dict): Resampling detection results
  - `resampling_score`: 0.0-1.0 likelihood
  - `interpretation`: Human-readable result

#### `detect_interpolation_method(image_path)`

Identifies interpolation method used.

**Returns:**

- `method` (dict): Detected interpolation method
  - `likely_method`: "nearest", "bilinear", or "bicubic"
  - `confidence`: Detection confidence

---

## Utility Functions (`util.py`)

### `resize_image(image_path, max_width=1000, max_height=1000)`

Resizes image maintaining aspect ratio.

### `convert_to_grayscale(image_path)`

Converts image to grayscale.

### `load_image_cv(image_path)`

Loads image using OpenCV (BGR format).

### `get_image_info(image_path)`

Returns basic image properties.

---

## Error Handling

All functions use consistent error handling:

```python
try:
    result = analysis_function(image_path)
except FileNotFoundError:
    return {"error": "File not found"}
except Exception as e:
    return {"error": str(e), "status": "analysis_failed"}
```

Always check for `"error"` key in returned dictionaries.

---

## Common Patterns

### Checking for Errors

```python
result = ela.perform_ela("image.jpg")
if "error" in result:
    print(f"Error: {result['error']}")
else:
    # Process result
    pass
```

### Batch Processing

```python
from pathlib import Path
from analysis import ela

images = Path("images/").glob("*.jpg")
results = {}

for img in images:
    ela_img, overlay, metrics = ela.perform_ela(str(img))
    results[img.name] = metrics
```

---

## Performance Tips

1. **Resize large images** before analysis using `util.resize_image()`
2. **Use grayscale** for algorithms that don't need color
3. **Cache results** to avoid reprocessing
4. **Process in batches** for multiple images
5. **Use multiprocessing** for independent analyses

---

## Version Compatibility

- **Python**: 3.9+
- **PIL/Pillow**: 10.0+
- **NumPy**: 1.24+
- **SciPy**: 1.11+
- **OpenCV**: 4.8+

---

## Support

For issues or questions, please open an issue on GitHub:
https://github.com/CodeRafay/Forensic-Image-Analysis-Toolkit/issues
