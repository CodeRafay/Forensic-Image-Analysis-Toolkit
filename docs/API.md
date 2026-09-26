# API Documentation - Veritas Forensic Analysis Toolkit

## Analysis Module API Reference

Most analysis modules return a result dictionary containing at least:

- `status`: `"success"` (or `"analysis_complete"` for the deepfake and
  resampling modules) on success, `"error"` otherwise
- `error`: present only when `status` is an error state

The exceptions are noted per function: `ela.perform_ela`,
`steganography_detection.detect_lsb_steganography`,
`hash_verification.verify_image_provenance`, `jpeg_ghost.detect_ghost`,
`histogram_analysis.detect_histogram_anomalies` and
`metadata_analysis.detect_thumbnail_mismatch` return tuples.

Modules catch their own exceptions and report failure in the return value
rather than raising, because the Streamlit app calls them directly.

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

**Returns:** a 3-tuple `(ela_img, ela_overlay, metrics)`, or `(None, None, None)`
on failure.

- `ela_img` (PIL.Image): ELA visualization
- `ela_overlay` (PIL.Image): ELA blended with the original
- `metrics` (dict):
  - `mean_error`: Average error level
  - `max_error`: Maximum error detected
  - `std_error`: Standard deviation of errors
  - `anomaly_score`: `mean + 2*std`
  - `suspicious_areas_percent`: Percentage of pixels above
    `ela.SUSPICIOUS_THRESHOLD` (the same cutoff `threshold_ela()` renders)

**Example:**

```python
from analysis import ela

ela_img, overlay, metrics = ela.perform_ela("image.jpg", quality=90)
if metrics is not None:
    print(f"Mean error: {metrics['mean_error']}")
```

#### `multi_quality_ela(image_path, qualities=[70, 85, 95], error_scale=10, overlay_opacity=0.5)`

Runs ELA at multiple quality levels. Also available under its former name
`ela_multi_quality`.

**Returns:**

- `results` (dict): `{quality: {"ela": PIL.Image, "overlay": PIL.Image, "metrics": dict}}`

#### Other functions

`forensic_analysis()` runs the full pipeline and returns every map at once.
`noise_map()`, `sharpness_map()` (Laplacian) and `entropy_map()` each return a
`PIL.Image`. `block_ela_stats()` returns block statistics, `ssim_map()` returns
`(diff_image, ssim_score)` and `threshold_ela()` returns a binary mask.

---

### 2. Metadata Analysis (`metadata_analysis.py`)

#### `extract_metadata(image_path)`

Extracts comprehensive metadata from an image.

**Returns:**

- `metadata` (dict) with sections `basic_info`, `exif`, `gps`, `camera`,
  `software`, `timestamps`, `thumbnail`, `warnings`. Failures are appended to
  `warnings`; the dict is always returned with all sections present.

**Example:**

```python
from analysis import metadata_analysis

meta = metadata_analysis.extract_metadata("image.jpg")
if meta['gps'].get('coordinates'):
    print(meta['gps']['coordinates']['google_maps'])
```

#### `detect_thumbnail_mismatch(image_path, min_correlation=0.90)`

Checks whether the embedded EXIF thumbnail still matches the main image. A
stale thumbnail can reveal the pre-edit picture.

**Returns:** a 2-tuple `(mismatch, details)`

- `mismatch` (bool): True if the thumbnail disagrees with the image
- `details` (dict): `thumbnail_present`, and when present `thumbnail_size`,
  `main_size`, both aspect ratios, `correlation`, `content_mismatch`,
  `aspect_ratio_mismatch`, `interpretation`

#### Other functions

`full_metadata_analysis()` combines extraction, anomaly detection and file
structure analysis. `detect_anomalies()`, `analyze_file_structure()`,
`extract_gps_coordinates()` and `export_metadata_report()` are also available.

---

### 3. Histogram Analysis (`histogram_analysis.py`)

#### `generate_histogram(image_path)`

Generates an RGB histogram visualization.

**Returns:** `result` (dict)

- `status`, `histogram_path` (str, saved PNG), `statistics` (per-channel
  `mean`/`std`/`min`/`max`/`median`), `warnings`, `interpretation`

**Example:**

```python
from analysis import histogram_analysis

result = histogram_analysis.generate_histogram("image.jpg")
print(f"Red channel mean: {result['statistics']['red']['mean']}")
```

#### `detect_histogram_anomalies(image_path)`

Detects statistical anomalies (comb patterns from level adjustment, and
shadow/highlight clipping).

**Returns:** a 2-tuple `(anomalies, severity)`

- `anomalies` (list): Detected anomaly descriptions
- `severity` (str): `"low"` (none), `"medium"` (1-2), or `"high"` (3+)

---

### 4. Noise Map (`noise_map.py`)

#### `generate_noise_map(image_path, sigma=2.0)`

Generates a noise map using high-pass filtering.

**Returns:** `result` (dict)

- `status`, `noise_map_path` (str, saved PNG), `metrics`
  (`channel_noise_variance`, `overall_variance`, `block_variance_std`,
  `blocks_analyzed`), `warnings`, `interpretation`

---

### 5. JPEG Ghost (`jpeg_ghost.py`)

#### `detect_jpeg_ghost(image_path, quality_steps=(95, 85, 75, 65, 55))`

Detects JPEG compression ghosts, writing visualizations to `temp/`.

**Returns:** `result` (dict)

- `status`, `combined_ghost_path`, `difference_maps` (`{quality: path}`),
  `difference_scores` (`{quality: mean difference}`),
  `estimated_last_save_quality`, `quality_confidence`, `warnings`,
  `interpretation`

#### `detect_ghost(image_path, quality_steps=(90, 70, 50))`

Same analysis, returned in memory with nothing written to disk.

**Returns:** a 2-tuple `(ghost_img, analysis)`

- `ghost_img` (PIL.Image or None): Combined ghost visualization
- `analysis` (dict): `difference_scores`, `estimated_last_save_quality`,
  `quality_confidence`, `warnings`, `interpretation`

---

### 6. Quantization Table Analysis (`quant_table.py`)

#### `analyze_quantization_table(image_path)`

Analyzes JPEG quantization tables. Returns `status: "not_jpeg"` for non-JPEG
input.

**Returns:** `analysis` (dict)

- `status`, `format`, `image_size`, `warnings`, `interpretation`
- `quantization_tables`: `{"table_<id>": {table_values, min_value, max_value,
  mean_value, estimated_quality, table_size}}`

`estimate_jpeg_quality(qtable, table_id=0)` inverts the IJG scaling and
recovers the original save quality to within ~1 point.
`is_standard_table(qtable, table_id=0)` reports whether the table is a scaled
copy of the standard IJG table, which distinguishes camera output from
custom encoder tables.

---

### 7. Copy-Move Forgery Detection (`cmfd.py`)

#### `detect_copy_move(image_path, block_size=16, threshold=0.99, min_distance=50)`

Detects copied and moved regions using DCT block matching. Features exclude the
DC coefficient, so matching is on texture rather than average brightness.

**Parameters:**

- `block_size` (int): Block size for matching (default: 16)
- `threshold` (float): Cosine similarity, 0-1 (default: 0.99). Genuine clones
  sit near 1.0; below ~0.97 almost everything matches.
- `min_distance` (int): Minimum separation between matched blocks

**Returns:** `result` (dict)

- `status`, `method`, `parameters`, `warnings`, `interpretation`
- `results`: `total_blocks_analyzed`, `matches_found`, `match_groups`,
  `result_image_path`
- `matches`: top 20 matches, each with `block1`, `block2`, `similarity`, `distance`

**Example:**

```python
from analysis import cmfd

result = cmfd.detect_copy_move("image.jpg")
if result['results']['matches_found'] > 0:
    print(f"Found {result['results']['matches_found']} duplicate blocks")
```

---

### 8. PRNU Analysis (`prnu.py`)

#### `analyze_prnu(image_path, reference_image_path=None)`

Analyzes Photo Response Non-Uniformity (sensor fingerprint).

The residual pipeline is wavelet denoising → zero-mean → Wiener filtering, and
matching correlates the residual against `I_test * K` because PRNU is
multiplicative. A plain high-pass residual will not work: on a photograph it is
dominated by scene edges, which makes the comparison measure scene similarity
rather than sensor identity.

**Parameters:**

- `image_path` (str): Test image
- `reference_image_path` (str | list): One or more images from the candidate
  camera. More references give a cleaner fingerprint — measured match strength
  is +0.28 with one reference, +0.47 with two, +0.51 with four, against
  non-matches within ±0.012 of zero. References must share the test image's
  pixel dimensions, since the fingerprint is pixel-aligned.

**Returns:** `analysis` (dict)

- `status`, `method`, `image_shape`, `warnings`, `interpretation`
- `metrics`: `noise_variance`, `noise_mean_abs`, `pattern_strength`,
  `variance_consistency`, `blocks_analyzed`
- `prnu_pattern_path`: Rendered noise residual
- `correlation_analysis` (only with a reference): `correlation`,
  `same_camera_likelihood` (`Low`/`Medium`/`High`), `verdict`,
  `reference_images_used`, `match_threshold`, `interpretation`, and
  `suspicious_blocks` listing regions that carry no fingerprint — i.e. content
  spliced in from a different sensor

Helpers: `extract_noise_residual()`, `estimate_fingerprint()`,
`normalized_correlation()`.

---

### 9. Frequency Analysis (`frequency_analysis.py`)

#### `analyze_frequency_domain(image_path)`

FFT analysis for tampering detection.

**Returns:** `analysis` (dict)

- `status`, `method`, `authenticity_score` (0-100), `risk_level`, `verdict`,
  `findings`, `warnings`, `magnitude_spectrum_path`, `interpretation`
- `metrics`: `high_frequency_energy_percentage` (power above half-Nyquist),
  `spectral_power_law_slope` (near -2.0 for natural photographs),
  `spectral_complexity`
- `technical_details`: `magnitude_mean`, `magnitude_std`, `phase_std`,
  `frequency_uniformity`, `peaks_detected`

`phase_std` and `frequency_uniformity` are reported but not scored: both are
effectively constant across images.

#### `detect_dct_anomalies(image_path)`

Analyzes DCT coefficients and JPEG grid artifacts.

**Returns:** `analysis` (dict)

- `status`, `method`, `authenticity_score`, `risk_level`, `verdict`,
  `findings`, `warnings`, `anomalies`, `dct_anomaly_map_path`, `interpretation`
- `metrics`: `smooth_content_percentage`, `detail_content_percentage`,
  `noise_edge_percentage`, `jpeg_blockiness_ratio`,
  `compression_quality_indicator`
- `technical_details`: includes `grid_consistency`, the blockiness ratio where
  1.0 means no visible 8x8 grid

Helpers `radial_power_slope(magnitude_spectrum)` and `jpeg_blockiness(gray)`
are exposed for direct use.

---

### 10. Deepfake Detection (`deepfake_detector.py`)

#### `detect_deepfake_artifacts(image_path)`

Detects common GAN/deepfake artifacts.

**Returns:** `analysis` (dict)

- `status` (`"analysis_complete"`), `method`, `image_size`, `interpretation`, `note`
- `artifacts`: `frequency_anomaly_score`, `channel_correlation_score`,
  `edge_sharpness_score`

#### `detect_gan_fingerprint(image_path)`

Detects GAN architecture fingerprints via spectral analysis.

**Returns:** `fingerprint` (dict)

- `status`, `method`, `radial_profile`, `gan_indicators`,
  `gan_likelihood` (`"Low"`/`"Medium"`/`"High"`), `interpretation`, `note`
- `metrics`: `radial_frequency_variance`, `spectral_peaks_detected`,
  `quadrant_symmetry`, `gan_score`

Both are heuristic detectors; reliable deepfake detection needs a trained model.

---

### 11. Resampling Detection (`resampling_detector.py`)

#### `detect_resampling(image_path)`

Detects rescaling and recovers the scale factor.

Interpolation makes the variance of the second derivative periodic, at a
frequency of exactly `1 - 1/s` for scale factor `s`. Measured recovery is
exact: 1.05 -> 1.05, 1.25 -> 1.25, 1.5 -> 1.50, 1.9 -> 1.90.

**Returns:** `analysis` (dict)

- `status` (`"analysis_complete"`), `method`, `image_size`
- `resampling_detected` (bool), `resampling_score` (0.0-1.0),
  `peak_prominence`, `detection_threshold`
- `detected_axis`, `estimated_scale_factors` — often two candidates, because
  above 2x the signature aliases and both readings fit the measurement
- `per_axis`: per-axis prominence, frequency and scale candidates
- `limitations`: stated in the result, since a negative is weak evidence.
  Exact integer scaling lands on the Nyquist limit and downscaling leaves
  little to detect.

#### `detect_interpolation_method(image_path)`

Identifies the interpolation kernel where the evidence supports it.

**Returns:** `method` (dict)

- `status`, `method`, `likely_interpolation`, `confidence`,
  `duplication_rate`, `duplication_periodicity`, `overshoot_ratio`, `note`

Nearest-neighbour is identified reliably (`confidence: "High"`) because it
duplicates pixels on a regular lattice. Bilinear, bicubic and Lanczos are not
reliably separable on a single image, so they are reported as a family with
`confidence: "Low"`. When no resampling is present the confidence is `"N/A"`
rather than a guessed kernel.

---

### 12. Steganography Detection (`steganography_detection.py`)

#### `detect_lsb_steganography(image_path)`

Detects LSB steganography using the Westfeld-Pfitzmann Pair-of-Values
chi-square attack, gated on the LSB plane also being spatially random.

**Returns:** a 3-tuple `(probability, visual_map, details)`

- `probability` (float): 0-100, the strongest channel
- `visual_map` (PIL.Image or None): Per-channel block heatmaps
- `details` (dict): `overall_probability`, `mean_channel_probability`,
  `channel_results` (per channel: `chi_square_statistic`, `p_value`,
  `steganography_probability`, `pov_probability_before_gate`,
  `lsb_randomness_z`, `lsb_plane_is_random`, `valid_pairs`,
  `lsb_distribution`), `image_info`, `method`, `interpretation`

Detection scales with how much LSB capacity is used: a fully embedded image
scores ~100, a 50% embed ~20, and sparse embedding is invisible to the
whole-image test — use the block heatmap for that. The heatmap is a
localisation aid, not a verdict; it retains a measurable false positive rate on
JPEG-sourced images.

`pov_chi_square_test(channel)` and `lsb_spatial_randomness_z(channel)` are
exposed individually, as are `extract_lsb_planes()`, `analyze_blocks()` and
`batch_detect()`.

---

### 13. Hash Verification (`hash_verification.py`)

#### `verify_image_provenance(image_path, db_path=DEFAULT_DB_PATH)`

Verifies provenance against the local hash ledger.

**Returns:** a 4-tuple `(authenticity_score, modification_history, legal_validity, details)`

- `authenticity_score` (int): 0-100 (100 exact match, 50 no record)
- `modification_history` (list): Chronological match records
- `legal_validity` (dict): `valid`, `reason`, `chain_of_custody`, `admissible`
- `details` (dict): `current_hashes`, `matches_found`, `match_details`,
  `image_info`, `database_path`, `chain_integrity`, `analysis_timestamp`

The ledger's own integrity is checked on every lookup. A broken chain overrides
any image match — matching against an altered ledger proves nothing — so
`legal_validity` becomes `chain_of_custody: "Compromised"`, `admissible: False`.

#### `verify_chain(db_path=DEFAULT_DB_PATH)`

Walks the ledger and verifies every link.

**Returns:** dict with `valid`, `total_records`, `first_invalid_index`,
`errors`, and `legacy_records` (entries written before chaining existed, which
can be neither confirmed nor refuted).

#### `compute_record_hash(record, prev_hash)`

SHA-256 over a record's canonical serialization plus its predecessor's hash.
Editing a record breaks its own hash; recomputing that hash breaks the *next*
record's `prev_hash`, so tampering surfaces either way.

#### Other functions

`generate_perceptual_hash()` (phash/ahash/dhash/whash),
`generate_cryptographic_hash()` (SHA-256), `add_to_blockchain()`,
`find_matches()`, `calculate_hash_distance()`, `export_database()`,
`import_database()` and `get_database_stats()`.

The ledger is a local hash chain, not a distributed blockchain: it is
tamper-evident but has no network or consensus, so nothing prevents deleting
the file and rebuilding it. `DEFAULT_DB_PATH` resolves relative to the project
root rather than the working directory.

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

Modules do not raise on bad input; they report failure in the return value so a
caller can render it. Check the return shape for the function you called:

```python
from analysis import histogram_analysis, ela

result = histogram_analysis.generate_histogram("missing.jpg")
if result["status"] != "success":
    print(f"Error: {result['error']}")

ela_img, overlay, metrics = ela.perform_ela("missing.jpg")
if ela_img is None:
    print("ELA failed")
```

---

## Common Patterns

### Batch Processing

```python
from pathlib import Path
from analysis import ela

results = {}
for img in Path("images/").glob("*.jpg"):
    _, _, metrics = ela.perform_ela(str(img))
    if metrics is not None:
        results[img.name] = metrics
```

---

## Performance Tips

1. **Resize large images** before analysis using `util.resize_image()`. The app
   caps analysis input at 2048px for this reason — but note that the
   steganography, resampling and JPEG ghost modules must see the *original*
   file, since resizing destroys the very artifacts they measure.
2. **Use grayscale** for algorithms that don't need color
3. **Cache results** to avoid reprocessing
4. **Use multiprocessing** for independent analyses

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
