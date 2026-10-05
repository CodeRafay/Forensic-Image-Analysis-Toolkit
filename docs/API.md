# API Reference — Veritas analysis modules

Every technique lives in its own module under `analysis/`. The package imports
sub-modules lazily (`import analysis; analysis.ela.analyze_ela(...)` loads
only `ela`). This file documents the public entry points as implemented;
method details and measured benchmark numbers are in each
[`Descriptions/*.md`](../Descriptions/).

All results are **indicators, not proof**. No function returns an
authenticity score or verdict.

---

## The result contract (`analysis/util.py`)

Every analysis entry point returns `make_result(...)`:

```python
{
    "status":      "ok" | "insufficient_data" | "not_applicable" | "error",
    "summary":     str,     # one neutral sentence describing what was measured
    "findings":    [{"level": "info" | "notice" | "warning", "text": str}],
    "metrics":     {label: int | float | str},   # headline numbers
    "images":      {caption: np.ndarray},        # uint8, (H, W) or (H, W, 3)
    "tables":      {title: list[dict] | dict},
    "limitations": [str],   # what this technique cannot see; always shown
    "details":     {...},   # raw JSON-serialisable values (tests, power users)
}
```

- `status`: `insufficient_data` = too small/flat to measure;
  `not_applicable` = wrong input kind (e.g. a PNG for a JPEG-only test);
  `error` = the analysis failed (`summary` says why).
- Finding levels: `info` = neutral, `notice` = weak indicator,
  `warning` = inconsistency found.
- Metric and image keys are human-readable labels (they are what the app
  displays), e.g. `"Area above 4x median (%)"`. Use `details` for stable
  programmatic access.
- Analysis entry points never raise; exceptions become
  `error_result(exc, limitations)`. Images are returned in memory; nothing is
  written to disk.
- `tests/test_contract.py` checks all of this for every entry point on JPEG,
  PNG, grayscale, RGBA, palette, 16×16, 1×1 and flat images.

The app renders any result with `render()` in `app.py`: metrics as
`st.metric`, findings by level, images two per row, tables in expanders, then
limitations and raw `details`.

### Other `util` helpers

| Function | Purpose |
| -------- | ------- |
| `make_result(status, summary, findings=(), metrics=None, images=None, tables=None, limitations=(), details=None)` | Build and validate a result |
| `error_result(exc, limitations=())` | `status="error"` result |
| `load_array(path, mode="RGB", max_px=None)` → `(float64 array, scale)` | Decode without re-encoding; EXIF orientation **not** applied; optional in-memory BOX downscale for analyses that do not depend on compression traces |
| `image_format(path)` | Pillow format name (`"JPEG"`, `"PNG"`, …) |
| `to_uint8(arr, stretch=True)` | Display conversion (0.5–99.5 % percentile stretch) |
| `fig_to_array(fig)` | Rasterise and close a matplotlib figure |
| `overlay_mask(rgb, mask, color=(255, 0, 0), alpha=0.45)` | Mask overlay |
| `bag_diffs`, `bag_maps`, `phase_energy`, `blockiness_by_offset`, `grid_uniqueness`, `jpeg_grid_offset(gray)` → `(dy, dx, strength)` | JPEG block artifact grid (Li, Yuan & Yu 2009); `strength ≈ 1` = no grid |

---

## Entry points

Metric/image names below are the labels returned for the bundled sample
image; a few appear only in some cases (noted).

### `ela.analyze_ela(image_path, quality=90)`

Error Level Analysis (Krawetz 2007). Re-saves once as JPEG at `quality` (app
slider 50–95) and measures max-over-RGB |original − resaved| in 16-px windows,
content-normalised: each window's error is divided by the median error of
windows with the same local detail (16 |Laplacian| quantile bins).
Guide: [ELA.md](../Descriptions/ELA.md).

- **metrics**: `Mean error at q90 (grey levels)`, `95th pct error at q90 (grey levels)`, `Median smoothed error (grey levels)`, `Area above 2x expected error (%)`, `Max error / expected for its texture`
- **images**: ELA error (contrast-stretched), regions above 2× expected error (red overlay)
- **details**: `quality`, `median_error`, `mean_error`, `area_above_k_pct`, `region_pct`, `n_regions`, `max_ratio`, `k`
- PNG input adds an info finding (the map shows the first JPEG compression).

### `metadata_analysis.analyze_metadata(image_path)`

True EXIF IFDs, XMP packet, PNG text chunks and C2PA, checked for internal
inconsistencies (editor tags, date consistency incl. OffsetTime, thumbnail vs
image, MakerNote, pixel dimensions, XMP history, AI-text keys, C2PA). No score.
Guide: [Metadata.md](../Descriptions/Metadata.md).

- **metrics**: `Format`, `Width (px)`, `Height (px)`, `EXIF tags (count)`, `XMP history events (count)`, `Software entries (count)`, `C2PA manifests (count)`; with an EXIF thumbnail also `Thumbnail correlation`, `Thumbnail worst-block residual (× median)`
- **images**: `Embedded thumbnail | main image downscaled | residual` (when a thumbnail exists)
- **tables** (only those with content): `Camera`, `Software`, `Timestamps`, `GPS`, `XMP history`, `PNG text chunks`, `Full EXIF`, `C2PA`, `C2PA actions`
- **details**: `format`, `size`, `exif`, `xmp`, `c2pa`, `thumbnail`, `png_text`

### `metadata_analysis.read_c2pa(path)` → `dict`

Offline C2PA Content Credentials reader (`c2pa-python`; remote manifests and
OCSP are not fetched). Not a result contract; a plain dict:
`present`, `validation_state` (`"Valid" | "Invalid" | "Trusted" | None`),
`valid`, `claim_generator`, `title`, `signer`, `issuer`, `signing_time`,
`actions` (list of `{action, softwareAgent, digitalSourceType, when}`),
`ai_generated`, `ai_indicators`, `ingredients`, `manifests`, `failures`
(`{code, explanation}`), `errors`.

### `histogram_analysis.analyze_histogram(image_path)`

Stamm & Liu 2010 contrast-enhancement fingerprint: HF energy `F` of the
pinched histogram's DFT per channel, flagged above `ETA = 0.020`; interior
gaps counted inside the 0.1–99.9 percentile range; clipping is informational.
Guide: [Histogram.md](../Descriptions/Histogram.md).

- **metrics**: per channel `<Ch> HF energy F (x1000)`, `<Ch> empty bins inside occupied range`
- **images**: `Histogram (% of pixels per value)`
- **tables**: `Per-channel statistics`
- **details**: `F`, `eta`, `flagged`, `channels`

### `noise_map.analyze_noise(image_path)`

Splicebuster (Cozzolino, Poggi & Verdoliva 2015): co-occurrence histograms of
the quantised 3rd-order residual of luma in 128-px windows (stride 8 px, 16 px
on large images), PCA to 25 dims, two-Gaussian EM; the largest compact
minority region is a notice. Full resolution. `insufficient_data` below
256 px, for flat images or < 64 usable windows.
Guide: [Noise_Ghost.md](../Descriptions/Noise_Ghost.md).

- **metrics**: `Usable windows`, `Window stride (px)`, `Outlier windows (%)`, `Largest candidate region (% of usable windows)`, `Region compactness (share of outlier windows)`, `Region median log-likelihood ratio`
- **images**: Splicebuster heat map (minority vs majority residual model), candidate region (red)
- **details**: `flagged`, `region`, `compact`, `llr`, `stride`, `heat`, `post` (window maps as lists)

### `quant_table.analyze_quantization_table(image_path)`

Reads the DQT tables through Pillow's decoder, estimates the IJG quality,
tests proportionality to the ITU-T T.81 Annex K tables and compares the
encoder family with EXIF Make/Model/Software. Says which encoder family saved
the file last, not whether pixels were edited. `not_applicable` for non-JPEG.
Guide: [Quantization.md](../Descriptions/Quantization.md).

- **metrics**: `Table N estimated quality (IJG)`, `Table N IJG-standard`
- **tables**: `Table N (luminance|chrominance)`: 8 rows of `{"0".."7": value}`
- **details**: `quantization_tables` (`{id: [64 ints]}`), `qualities`, `standard`, `exif`, `encoder_family`

Helpers (reused by `double_jpeg` and `jpeg_ghost`):
`extract_jpeg_quantization_tables(path)` → `{table_id: [64 values]}` (raster order, empty if not JPEG);
`estimate_jpeg_quality(qtable, table_id=0)` (exact match against libjpeg tables q = 1…100, IJG-scale inversion otherwise); `ijg_table(quality, table_id=0)` → the 64-entry libjpeg table; `is_standard_table(qtable, table_id=0, tolerance=0.02)`.

### `double_jpeg.analyze_double_jpeg(image_path)`

Bianchi & Piva 2012 per-8×8-block double-compression likelihood map. Aligned
model with the paper's rounding-error term (one IJG primary quality and the
error variance fitted jointly over 9 frequencies by maximum likelihood,
mixture weight by EM, calibration on a (4, 4)-shifted grid; only blocks with
≥ 4 non-zero AC coefficients vote); non-aligned model after a primary-grid
shift search.
`not_applicable` for non-JPEG. Guide: [Quantization.md](../Descriptions/Quantization.md).

- **metrics**: `Final quality (IJG est.)`, `Estimated primary quality (IJG)`, `Non-aligned search z`, `Primary grid shift (dy,dx)`, `Model` (aligned / non-aligned / none), `Frequencies with double-JPEG evidence`, `Blocks with p(tampered)>0.5 (%)`, `Largest inconsistent region (% of blocks)`
- **images**: probability of single compression (red = high), blocks with p > 0.5 after median filter (when there is evidence); block resolution, ≤ ~1200 px
- **tables**: `Per-frequency estimates` (Q2, estimated Q1, mixture weight, likelihood gain)
- **details**: `model`, `fraction`, `region`, `prob_map` (list of lists per block), `na_z`, `na_shift`

### `jpeg_ghost.analyze_jpeg_ghost(image_path, qualities=range(50, 100, 5))`

Farid 2009 JPEG ghosts on the stored luminance: recompress at each quality
below the final one, on the file grid and on the one off-grid offset where a
DCT-domain lattice test finds most blocks (Farid §3), 16×16-window squared
difference compared with a (4, 4)-shifted reference. The whole-image test is
relative to a simulated single compression. Primary quality comes from the
stored table (PNG: none, all qualities tested). `insufficient_data` if no
tested quality is below the final one. Guide: [Noise_Ghost.md](../Descriptions/Noise_Ghost.md).

- **metrics**: `Primary quality (from table)`, `Tested qualities`, `Tested grid offsets`, `Ghost region (% of windows)`, `Ghost quality`, `Ghost grid offset (dy,dx)`, `Whole-image ghost quality` (when found)
- **images**: normalised difference at the ghost / highest tested quality (dark = ghost), quality of minimum difference, ghost overlay (when a ghost region is found); block resolution, ≤ ~1200 px
- **details**: `curve` (`{q: mean d}`), `ghost_q`, `whole_image_ghost_q`, `region`, `primary_q`, `grid_offset`, `tested_offsets`, `offgrid_excess_share`

### `cmfd.detect_copy_move(image_path, max_px=2048)`

Copy-move detection: SIFT/RootSIFT g2NN + Ward clustering + RANSAC affine
(Amerini et al. 2011), also matched against the flipped image so mirrored
clones are found, and dense Zernike-moment PatchMatch (first-order
propagation, radius-halving random search) with dense linear fitting
(Cozzolino, Poggi & Verdoliva 2015); each hypothesis verified by a local ZNCC
map and a region test (difference must be explained by resampling + the
file's JPEG quality). Any shift, rotation, scale and mirroring. Images larger than `max_px` are
downscaled **in memory**; the analysed size is reported. `insufficient_data`
below 64 px. Guide: [CMFD.md](../Descriptions/CMFD.md).

- **metrics**: `Analysed size (px)`, `SIFT keypoints`, `g2NN matches`, `Verified clones`, `Duplicated area (% of image)`
- **images**: duplicated regions (green copy A, red copy B, yellow keypoint matches), dense offset-field consistency
- **tables**: `Clone hypotheses (B = scale * R(rotation) * [mirror] * A; ...)` (per-clone affine parameters; columns `rotation A->B (deg, CCW +)`, `scale A->B`, `mirrored A->B`, ZNCC, |diff|, resampling |diff|, fine detail, keypoint support)
- **details**: `scale`, `clones` (same rows, keys `rotation (deg)`, `scale`, `mirrored`), `n_keypoints`, `n_matches`, `keypoint_hypotheses`, `dense_hypotheses`, `jpeg_quality`

### `prnu.analyze_prnu(image_path, reference_paths=None, max_px=4096)`

Sensor fingerprint (Lukáš/Fridrich/Goljan 2006; Chen et al. 2008; Goljan et
al. 2009): wavelet NoiseExtract → ZeroMeanTotal → WienerInDFT; ML fingerprint
from the references (streamed one at a time, float32); NCC and PCE (decision
PCE > 60); with ≥ 2 references and a match, a local 128-px block test: Chen
2008 correlation predictor + Chierchia et al. 2014 Bayesian-MRF decision
(exact min-cut). Images larger than `max_px` per side are **centre-cropped**
(never resized; the default analyses a 4000×3000 image in full); references
are cropped identically and must have the test image's pixel dimensions
(others are skipped and listed). `reference_paths` accepts a path or a list.
If fewer than 10 % of blocks are testable the local test reports
insufficient data instead of "nothing found".
Guide: [PRNU.md](../Descriptions/PRNU.md).

- **metrics**: `Analysed region (px)`, `Residual std (grey levels)`; with references `References used`, `NCC`, `PCE`, `PCE threshold`; with the local test `Blocks tested (128 px, stride 32)`, `Blocks untestable`, `Testable fraction (%)`, `Blocks lacking fingerprint`
- **images**: noise residual; with the local test (when ≥ 10 % testable) `Local test (red: fingerprint missing, grey: untestable)`
- **tables**: `Skipped references`, `Regions lacking the fingerprint` (when present)
- **details**: `crop_offset`, `shape`, `residual_std`; with references `ncc`, `pce`, `references_used`; with the local test `local_test` (`"ok"` / `"insufficient_data"`), `testable_fraction`, `sigma0`, `sigma_hat`, `regions`, `blocks_tested`, `blocks_flagged`
- Status: `not_applicable` when no reference has matching dimensions.
- Cost at 12 MP with 8 references: see PRNU.md (≈ 30 s, ≈ 700 MB peak).

Lower-level functions: `noise_extract`, `zero_mean_total`, `wiener_dft`,
`residual`, `accumulate`, `finalize`, `ncc`, `pce`, `local_test`,
`train_predictor`.

### `frequency_analysis.analyze_spectrum(image_path)`

Radially averaged power spectrum of the mean-subtracted, Hann-windowed
luminance of a centre square crop (≤ 2048 px; cropped, never resized): log-log
slope and share of power above half-Nyquist, compared with ranges measured on
unedited photos (notice only). Guide: [Frequency.md](../Descriptions/Frequency.md).

- **metrics**: `Spectral slope (log power / log freq)`, `Power above half-Nyquist (%)`, `Analysed size (px)`
- **images**: log power spectrum, radial power profile
- **details**: `slope`, `hf_share`, `size`, `slope_range`, `hf_range`

### `frequency_analysis.analyze_blocking(image_path)`

Block artifact grid (Li, Yuan & Yu 2009): global 8×8 grid origin (non-zero =
cropped after compression, or a pasted JPEG region), grid strength, non-8
periodicities (e.g. nearest-neighbour upscaling) and local windows whose grid
phase disagrees with the global grid. Guide: [Frequency.md](../Descriptions/Frequency.md).

- **metrics**: `Grid strength (1 = none)`, `Grid origin (x, y) px`, `Periodicity x / y (px)`, `Misaligned-grid area (%)`
- **images**: BAG map, local grid alignment (green aligned, red misaligned)
- **details**: `grid`, `strength`, `origin`, `period`, `autocorr`, `format`, `misaligned_pct`, `n_misaligned_regions`

### `resampling_detector.detect_resampling(image_path)`

Two global detectors, flagged if either fires: Kirchner 2008 fixed-linear-
predictor p-map |DFT| peak (threshold 12) with a narrow notch at Nyquist
(demosaicing) and, for JPEG files or images with a measurable 8×8 grid, at the
whole k/8 lattice (Kirchner & Gloe 2009); and an axis-aligned derivative-
projection detector (Gallagher 2005 / Mahdian & Saic 2008, threshold 7.8)
that survives JPEG. Plus a 128×128 window heatmap (stride 64, coarser on very
large images) and an exact row/column duplication test for nearest-neighbour
enlargement. `insufficient_data` below 64 px.
Guide: [Resampling.md](../Descriptions/Resampling.md).

- **metrics**: `Peak ratio (x local background)`, `Detection threshold (ratio)`, `Peak frequency (vertical, horizontal) cycles/px`, `Projection peak ratio (x local background)`, `Projection threshold (ratio)`, `Projection peak frequency (cycles/px)`, `Duplicated columns (%)`, `Duplicated rows (%)`, `Windows above threshold (%)`
- **images**: p-map spectrum, window peak ratio, windows above threshold (red)
- **details**: `window_grid`, `window_stride`, `resampling_detected`, `kirchner_detected`, `projection_detected`, `nearest_neighbour`, `peak_ratio`, `peak_frequency`, `scale_candidates`, `rotation_deg`, `projection_ratio`, `projection_frequency`, `projection_axis`, `projection_scale_candidates`, `duplication_rate`, `jpeg_notch`, `grid_strength`, `flagged_windows_pct`

### `deepfake_detector.analyze_synthetic_traces(image_path)` — Experimental

Periodic peaks in the noise-residual power spectrum and autocorrelation
(Corvi et al. 2023) and the azimuthal image spectrum (Durall et al. 2020).
Welch average of 128×128 tiles over a centre crop ≤ 1024 px; peaks on the
k/8 JPEG lattice are excluded for JPEG/gridded images, and the Nyquist
rows/columns (±1 bin of 0.5 cycles/px, where Bayer demosaicing puts energy)
are always excluded; both are reported separately. **Measurements only — no AI-image classifier, no verdict.**
Guide: [Deepfake.md](../Descriptions/Deepfake.md).

- **metrics**: `Off-grid residual peak (dB above local median)`, `Peak frequency (cycles/px, vertical, horizontal)`, `Peak period (px)`, `8-px-grid peak (dB)`, `Nyquist-line peak (dB, demosaicing/CFA)`, `Azimuthal power 0.9–1.0 vs 0.4–0.5 Nyquist (dB)`, `Tiles averaged`, `Analysed region (px)`
- **images**: residual power spectrum (excess over local median), residual autocorrelation (±16 px), azimuthally averaged spectrum
- **details**: `peak_db`, `peak_freq`, `grid_peak_db`, `nyquist_peak_db`, `grid_excluded`, `jpeg_grid_strength`, `tiles`, `radial_freq`, `radial_db`

### `steganography_detection.analyze_lsb(image_path)`

Quantitative LSB-replacement steganalysis. Decision statistic per channel:
min(Weighted Stego (Ker & Böhme 2008), Sample Pairs (Dumitrescu 2003)), or
SPA alone when WS is unreliable (< 50 % of pixels keep a WS weight, or WS
outside [-0.5, 1.5]); image score = highest channel, threshold 0.05 bpp. RS
(Fridrich, Goljan & Du 2001) is reported as a cross-check, PoV chi² (Westfeld &
Pfitzmann 1999) as a sequential-embedding curve, 64×64 local WS map. JPEG
input gets a finding that DCT-domain stego (JSteg, F5, OutGuess, J-UNIWARD)
is invisible to pixel-LSB tests. Guide: [Steganography.md](../Descriptions/Steganography.md).

- **metrics**: `Payload estimate, highest channel (bpp)`, `Mean WS payload over channels (bpp)`, `Detection threshold (bpp)`, `PoV equalised prefix (% of scan)`, `PoV p-value, whole image`
- **images**: local WS payload per 64×64 block, PoV cumulative p-value
- **tables**: `Per-channel payload estimates` (incl. the `rule` used)
- **details**: `format`, `threshold_bpp`, `estimates` (per channel: `ws`, `spa`, `rs`, `pov_p`, `ws_valid_share`, `score`, `rule`), `score`, `max_channel`, `combined_ws`, `pov_curve`, `sequential_fraction`, `sequential_local_bpp`, `sequential_rest_bpp`, `sequential_detected`, `block_map`

Estimator functions: `weighted_stego(x)`, `spa(x)`, `rs_analysis(x)`,
`pov_chi_square_test(channel, min_expected=5)`, `pov_curve(arr, steps=100)`,
`ws_block_map(x)` (64×64), `WSTerms(x)` (WS terms computed once:
`.estimate(r0, r1)`, `.blocks`, `.valid`), `decision_score(ws, spa, valid)`.

---

## Hash ledger (`analysis/hash_verification.py`)

Pure functions over an in-memory ledger (a `list` of record dicts). The app
keeps it in `st.session_state`; nothing is shared between sessions or written
to disk. The ledger records that a file with these hashes was seen; it is not
a trusted timestamp or a legal chain of custody.
Guide: [Hash_Verification.md](../Descriptions/Hash_Verification.md).

| Function | Returns |
| -------- | ------- |
| `compute_hashes(path)` | `{sha256, sha512, md5 (legacy), pixel_sha256, size, format, dimensions, phash, dhash, ahash}`. `pixel_sha256` covers decoded pixels + mode + size (+ palette). |
| `new_ledger()` | `[]` |
| `add_record(ledger, path, label="", note="")` | `(new_ledger, record)`; input list unchanged. Record: `id`, `created_utc`, `label` (basename only), `note`, `hashes`, `prev_hash`, `record_hash`. |
| `verify_chain(ledger)` | `{valid, broken_at, n}` — consistency check; anyone can recompute a whole chain. |
| `ledger_stats(ledger)` | `{records, first_utc, last_utc, total_bytes, chain_valid}` |
| `verify_image(ledger, path, threshold=10)` | Result contract. Each record is `byte-identical` (SHA-256), `pixel-identical`, `visually similar` (pHash distance ≤ `threshold` bits of 64 — **not** integrity) or `no match`. Metrics: `Ledger records`, `Byte-identical matches`, `Pixel-identical matches`, `Visually similar matches`, `Similarity threshold (bits of 64)`, `Best phash/dhash/ahash distance (bits of 64)`. Tables: `Top matches`, `Query hashes`. `insufficient_data` for an empty ledger. |
| `export_ledger(ledger, key=None)` | JSON `bytes` (`format: "veritas-ledger/1"`). With `key` (bytes) signed HMAC-SHA256; without, a plain SHA-256 digest that detects accidental change only. |
| `import_ledger(data, key=None, into=None)` | `(ledger, report)`. Nothing merges if the signature/digest or imported chain fails. Merged records are re-linked onto `into`'s tail (old hash kept as `original_record_hash`) and deduplicated by SHA-256. `report`: `signature_valid` (True/False/None), `digest_ok`, `signature_alg`, `chain_valid`, `accepted`, `merged`, `duplicates_skipped`, `message`. Raises `ValueError` on a file that is not a veritas ledger. |

The app reads the HMAC key from `st.secrets["LEDGER_KEY"]` when configured.

---

## Example

```python
import analysis

r = analysis.cmfd.detect_copy_move("photo.jpg")
print(r["status"], "-", r["summary"])
for f in r["findings"]:
    print(f"[{f['level']}] {f['text']}")
for label, value in r["metrics"].items():
    print(f"{label}: {value}")
for lim in r["limitations"]:
    print("limitation:", lim)
```

Batch use is a loop over paths; every entry point is independent and
stateless.
