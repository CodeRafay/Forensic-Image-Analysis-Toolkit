# Changelog

All notable changes to Veritas Forensic Image Analysis Toolkit will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned Features

- Batch processing mode for multiple images
- Report generation (PDF/HTML export)
- Command-line interface (CLI)
- Optional manual calibration on public datasets (CoMoFoD, CASIA v2,
  Columbia, RAISE, Dresden) alongside the seeded synthetic benchmarks
- Trusted timestamping (RFC 3161) for ledger exports

---

## [3.0.0] - 2026-09-29

Forensic rebuild. Every analysis module was re-implemented on a published
method, with each threshold calibrated on a seeded synthetic benchmark to a
stated false-alarm rate (the measured numbers are in each
`Descriptions/*.md`). The guiding rule: report measurements and "inconsistency
found / not found", never "authentic". The pre-release review had found tabs
giving falsely reassuring verdicts (the hash tab said "Admissible" for a
splice; metadata called stripped and Photoshop files "LIKELY AUTHENTIC"),
tabs reading keys their module never returned, and every image over 2048 px
being re-saved at JPEG q95 before analysis, destroying the compression
evidence the JPEG tabs look for.

### Changed - Per module

- **ELA** (`ela.py`) — Krawetz 2007 with one error definition (max over RGB of
  |original − recompressed|, 16-px window). Fixed: the percentage and mask were
  computed from the display-stretched image, so they depended on brightness
  and quality; "high error" is now relative to the image's own median error.
- **Metadata** (`metadata_analysis.py`) — true EXIF IFDs separated from
  Pillow `info`; format-aware (no EXIF expected in PNG); editor match against
  a list of editors, date consistency with OffsetTime, thumbnail comparison,
  GPS only when both coordinates exist, MakerNote, XMP history and **C2PA
  Content Credentials** (`read_c2pa`, offline). Fixed: the "LIKELY AUTHENTIC"
  score, file-system timestamps (those were the server copy's) and the
  DQT-count "double compression" claim are gone.
- **Histogram** (`histogram_analysis.py`) — Stamm & Liu 2010
  contrast-enhancement detector (HF energy of the histogram DFT). Fixed: gaps
  were counted outside the occupied range, so every image with a narrow
  histogram looked edited; clipping is now an informational note.
- **Noise** (`noise_map.py`) — Splicebuster (Cozzolino, Poggi & Verdoliva
  2015): residual co-occurrence features, PCA and two-class EM. (A Lyu, Pan &
  Zhang 2014 noise-level version was tried and dropped: it found 2/56 splices
  and abstained on most JPEGs.) Replaces a
  squared high-pass difference map that showed edges, not noise.
- **Quantization tables** (`quant_table.py`) — IJG quality estimate,
  standard-table test and encoder family vs EXIF Make/Software. Fixed: the tab
  read keys the module did not return.
- **Double-JPEG localization** (new, `double_jpeg.py`) — Bianchi & Piva 2012
  per-block likelihood map, aligned (EM-estimated Q1) and non-aligned (grid
  shift search).
- **JPEG ghosts** (`jpeg_ghost.py`) — Farid 2009 with 16×16-window differences
  normalised per pixel and compared against a (4, 4)-shifted reference. Fixed:
  the primary quality came from the argmin of the difference curve (biased to
  the highest tested quality); it now comes from the stored quantization
  table. The "resaved many times" warnings are gone.
- **Copy-move** (`cmfd.py`) — SIFT/RootSIFT g2NN matching, Ward clustering and
  RANSAC affine (Amerini et al. 2011) plus a dense Zernike-moment PatchMatch
  branch (Cozzolino, Poggi & Verdoliva 2015), each hypothesis verified by a
  local ZNCC map. Fixed: block matching only found clones at 8-px-aligned
  offsets; any shift, rotation and scale is now handled.
- **PRNU** (`prnu.py`) — Goljan's ZeroMeanTotal and WienerInDFT, PCE alongside
  NCC (PCE > 60 decision), local splice test with the Chen et al. 2008
  correlation predictor skipping dark/saturated blocks. Large images are
  centre-cropped, never resized. The "Pattern Strength" colours are gone.
- **Frequency** (`frequency_analysis.py`) — `analyze_spectrum` (mean-subtracted,
  Hann-windowed radial spectrum slope and HF share) and `analyze_blocking`
  (block artifact grid, Li, Yuan & Yu 2009: grid origin, i.e. crop offset,
  and misaligned-grid regions). Fixed: the DC term dominated the spectrum
  because the mean was not subtracted, and blockiness was only measured at
  grid offset (0, 0). "Compression Quality" and the /100 scores are gone.
- **Resampling** (`resampling_detector.py`) — Kirchner 2008 fixed-predictor
  p-map spectrum with the JPEG lattice notched out (Kirchner & Gloe 2009),
  128×128 window heatmap, explicit nearest-neighbour duplication test. Fixed:
  every JPEG at q ≤ 50 was reported as resized, and images under 32 px raised
  `KeyError`.
- **Synthetic traces** (`deepfake_detector.py`, Experimental) — periodic peaks
  in the noise-residual power spectrum and autocorrelation (Corvi et al.
  2023) and the azimuthal spectrum (Durall et al. 2020), reported as
  measurements. The quadrant-symmetry check, the centre-of-spectrum "HF"
  metric, the Low/Medium/High verdict and "✅ No GAN indicators" are gone;
  the tab keys that did not match the module are fixed.
- **Steganography** (`steganography_detection.py`) — Weighted Stego (Ker &
  Böhme 2008) as decision statistic, Sample Pairs (Dumitrescu 2003) and RS
  analysis as cross-checks, PoV chi² as a sequential-embedding curve, local
  WS heatmap. Fixed: the interpretation text was inverted (a high PoV p-value
  is the stego sign). JPEG input states that DCT-domain stego is invisible.
- **Hash ledger** (`hash_verification.py`) — identity is SHA-256 of the file
  bytes (plus a pixel SHA-256 that survives metadata-only changes);
  pHash/dHash/aHash are reported as "visually similar (distance d)", never as
  integrity. Fixed: a copy-paste splice matched by pHash was reported as
  "✅ Admissible"; merging an imported ledger broke the chain (imports are now
  re-linked onto the current tail and deduplicated).
- **App** (`app.py`) — 13 tabs rendered by one `render()` function, so a tab
  can no longer read keys its module does not return; per-session temporary
  directory with random file names (two visitors uploading `image.jpg` no
  longer collide); in-app "indicators, not proof" disclaimer; results cached
  per image. Fixed: the > 2048 px JPEG q95 re-save before analysis is gone —
  all tabs read the original bytes; copy-move uses an in-memory downscale to
  2048 px and reports the analysed size.

### Changed - Breaking

- **Result contract.** Every public analysis function returns
  `analysis.util.make_result(...)`:
  `{status, summary, findings, metrics, images, tables, limitations, details}`
  with `status` in `ok | insufficient_data | not_applicable | error` and
  findings levelled `info | notice | warning`. Images are uint8 arrays
  returned in memory; no module writes PNGs to disk any more. Analysis entry points never
  raise; failures come back as `status: "error"`. See `docs/API.md`.
- **Old entry points removed → replacements:**
  - `perform_ela`, `multi_quality_ela`, `forensic_analysis`, `threshold_ela`,
    `noise_map`, `sharpness_map`, `ssim_map`, `entropy_map` → `ela.analyze_ela(path, quality=90)`
  - `extract_metadata`, `full_metadata_analysis`, `detect_thumbnail_mismatch`,
    `analyze_file_structure`, `export_metadata_report` → `metadata_analysis.analyze_metadata(path)`, `read_c2pa(path)`
  - `generate_histogram`, `detect_histogram_anomalies` → `histogram_analysis.analyze_histogram(path)`
  - `generate_noise_map` → `noise_map.analyze_noise(path)`
  - `detect_jpeg_ghost`, `detect_ghost` → `jpeg_ghost.analyze_jpeg_ghost(path, qualities=range(50, 100, 5))`
  - (new) `double_jpeg.analyze_double_jpeg(path)`
  - `detect_copy_move(path, block_size, threshold, min_distance)` → `cmfd.detect_copy_move(path, max_px=2048)`
  - `analyze_prnu(path, reference_image_path)`, `extract_prnu_pattern`,
    `compute_prnu_correlation` → `prnu.analyze_prnu(path, reference_paths=None, max_px=2048)`
  - `analyze_frequency_domain`, `detect_dct_anomalies` → `frequency_analysis.analyze_spectrum(path)`, `analyze_blocking(path)`
  - `detect_deepfake_artifacts`, `detect_gan_fingerprint` → `deepfake_detector.analyze_synthetic_traces(path)`
  - `detect_resampling` keeps its name with the new contract;
    `detect_interpolation_method` removed
  - `detect_lsb_steganography`, `batch_detect`, `analyze_blocks` → `steganography_detection.analyze_lsb(path)`
  - `verify_image_provenance`, `add_to_blockchain`, `load_database`,
    `save_database`, `export_database`, `import_database`,
    `get_database_stats`, `compute_record_hash`, `generate_*_hash` →
    `hash_verification.compute_hashes`, `new_ledger`, `add_record`,
    `verify_chain(ledger)`, `verify_image(ledger, path)`,
    `export_ledger(ledger, key)`, `import_ledger(data, key, into)`,
    `ledger_stats(ledger)` — pure functions over an in-memory ledger list
  - `util.resize_image`, `convert_to_grayscale`, `load_image_cv`,
    `get_image_info` → `util.load_array(path, mode, max_px)` (decode without
    re-encoding), `make_result`, `error_result`, grid helpers

### Removed

- Authenticity scores, risk levels and verdicts in every module.
- Legal-admissibility and chain-of-custody wording ("Admissible", "Legal
  Status"). The ledger states that it is not a legal chain of custody.
- The shared on-disk hash database (`temp/hash_database.json`); the ledger is
  per session, exported as JSON.
- The interpolation-method detector (`detect_interpolation_method`).
- The "Run All Analyses" stub checkbox.

### Testing

- 142 tests, run with `python -m unittest discover -s tests -t .` (no pytest
  needed). `tests/test_integration.py` was deleted; each module has
  `tests/test_<module>.py` with a seeded synthetic benchmark asserting its
  detection rate and false-alarm rate, and `tests/test_contract.py` runs every
  entry point on JPEG, PNG, grayscale, RGBA, palette, 16×16, 1×1 and flat
  images, asserting the contract and banning overclaiming wording.

### Deployment

- `requirements.txt` pinned to the versions the suite was run against
  (Python 3.10). Added `PyWavelets` (PRNU/noise residuals) and `c2pa-python`
  (Content Credentials); dropped `plotly` and `pandas`.
- `.python-version` (3.10) for Streamlit Cloud and pyenv.
- Optional `st.secrets["LEDGER_KEY"]` enables HMAC-SHA256-signed ledger
  exports.
- `.streamlit/config.toml`: `showErrorDetails = "type"` (no tracebacks shown
  to visitors).

---

## [2.0.0] - 2026-09-27

Correctness release. Every analysis technique was tested against ground truth
rather than trusted, and several were found to be measuring the wrong thing.
Five modules produced demonstrably incorrect forensic conclusions; two did the
opposite of what their name claimed. All are fixed and covered by regression
tests. The major version reflects breaking API changes made in the process.

### Fixed - Incorrect Forensic Logic

- **PRNU was inverted** — it correlated *scene content* instead of sensor
  fingerprint, because the noise residual came from a Gaussian high-pass, whose
  output on a photograph is dominated by scene edges. Two photos of the same
  scene from *different* cameras scored 0.97 ("High"); the same camera on a
  different scene scored 0.02 ("Low"). Replaced with the standard pipeline:
  wavelet denoising, zero-mean row/column suppression, Wiener filtering in the
  DFT domain, and intensity-modulated correlation against a maximum-likelihood
  fingerprint. The same case now measures +0.234 ("High") and −0.005 ("Low").

- **Resampling detection was structurally saturated** — the test asked whether
  *any* pixel in a frequency ring exceeded the 95th percentile. Since 5% of all
  pixels exceed it by construction, 17 of 19 rings fired on a clean image,
  scoring 0.944 against a stated threshold of 0.5. Replaced with
  second-derivative periodicity (Gallagher), which additionally *recovers the
  scale factor*.

- **Copy-Move Forgery Detection matched on brightness, not texture** — the DC
  coefficient accounted for 95–99.9% of each feature vector's length, so two
  unrelated blocks scored 0.945 similarity. A clean image produced 16,137 false
  near-exact matches. Excluding DC cut that to **0** while a genuine cloned
  region still matches at 1.0.

- **Quantization table parser read non-table bytes** — it byte-scanned for the
  DQT marker, which also occurs inside entropy-coded scan data and XMP
  metadata. On the sample image it reported 16 tables where the file has 2,
  with 14 built from XMP text, generating 24 fabricated "possible editing
  software" warnings. Now parsed through the JPEG decoder: 2 tables, 0 warnings.

- **Steganography detection flagged clean images** — the chi-square statistic
  grew linearly with pixel count, so a natural 0.43% LSB imbalance scored a
  clean photo at 71.5% ("High"). Replaced with the Westfeld–Pfitzmann
  Pair-of-Values attack, corroborated by an LSB spatial-randomness check.
  Clean images now score 0%, fully embedded images 100%.

- **Deepfake artifact detection always crashed** — `img_array` was freed before
  its shape was read, so every call returned `{"error": ...}`.

### Fixed - Metrics That Could Not Vary

Several scoring branches were unreachable because their metric was effectively
constant for every input:

- **FFT phase consistency** was `std(angle(FFT))`, which converges to 1.814
  (the standard deviation of a uniform distribution over [−π, π]) for *all*
  images. Replaced with the radial power-law slope: natural photographs follow
  1/f² at ≈ −2.04, white noise ≈ 0.0, heavy blur ≈ −3.3.
- **DCT "block consistency"** took 8×8 windows of a *global* DCT, where the
  top-left block holds nearly all the energy — it measured ~90 against
  thresholds of 0.5 and 1.0. Replaced with a real JPEG blockiness ratio:
  1.01 clean, 1.23 at quality 50, 1.63 at quality 20.
- **FFT high-frequency energy** summed magnitudes over most of the frequency
  plane, returning ~0.76 against a "natural" band of 0.1–0.3, so every
  authentic image was marked as having elevated detail and scored 50/100
  ("High" risk). Redefined as power above half-Nyquist and calibrated from
  measurement; an authentic photo now scores 100/100.
- **JPEG quality estimation** divided by a single standard-table entry instead
  of the matching mean, biasing results ~1.8×, and bucketed to five discrete
  values. Replaced with inversion of the IJG scaling formula — recovers the
  true save quality to within 1 point across Q10–Q98.
- **`is_standard_table`** only checked that values grow toward high
  frequencies, which nearly every table does, so it flagged almost nothing. Now
  tests proportionality against the standard IJG luminance and chrominance
  tables.
- **`sharpness_map` was byte-identical to `noise_map`** (both applied PIL's
  `FIND_EDGES`) while the UI presented them as independent evidence. Now a real
  Laplacian.

### Fixed - Application

- **The Resampling tab rendered nothing** — it checked `status == 'success'`
  but the module returns `'analysis_complete'`, so every run fell through to
  the error branch.
- **The PRNU correlation panel never displayed** — the app read
  `correlation_analysis` while the module returned `reference_analysis`.
- Three tabs would have raised `KeyError` on renamed metrics; a test class now
  asserts every dict key the UI reads unguarded actually exists.
- Metadata extraction no longer aborts on PNG. `piexif` raises on non-EXIF
  formats, and a single broad `try` discarded everything after that call,
  including the PNG-specific info block.
- CMFD similarity slider re-ranged to 0.95–0.999 (default 0.99); with
  texture-only features, anything below ~0.97 matches almost everything.

### Added

- **Tamper-evident hash chain** — ledger records now carry `prev_hash` and
  `record_hash`, with `verify_chain()` and `compute_record_hash()`. Editing a
  record breaks its own hash; recomputing that hash breaks the next record's
  link. A compromised chain overrides any image match, so
  "chain of custody: Intact" is now a meaningful claim.
- **PRNU splice localisation** — per-block correlation against the fingerprint
  identifies regions carrying no sensor pattern. Validated on a controlled
  splice: exactly the 24 affected blocks flagged, zero false positives on the
  clean original.
- **PRNU multi-image fingerprints** — `analyze_prnu` accepts a list of
  references. Match strength: +0.28 with one, +0.47 with two, +0.51 with four,
  against non-matches within ±0.012 of zero. The UI now accepts multiple
  uploads.
- **Scale-factor recovery** — resampling detection reports how much an image
  was rescaled, not just whether it was. The periodicity sits at exactly
  `1 − 1/s`; measured recovery is exact (1.05→1.05, 1.25→1.25, 1.5→1.50,
  1.9→1.90). Two candidates are reported above 2×, where the signature aliases.
- **Four previously documented-but-missing functions**, each built on existing
  logic rather than duplicated: `multi_quality_ela`, `detect_ghost`,
  `detect_histogram_anomalies`, `detect_thumbnail_mismatch`.
- `suspicious_areas_percent` ELA metric, sharing `threshold_ela`'s cutoff so
  the reported figure matches the mask the UI renders.
- Explicit `limitations` in resampling output — integer scaling and
  downscaling are genuine blind spots, now stated rather than hidden.

### Changed - Breaking

- ELA metrics renamed `max_diff`/`mean_diff`/`std_diff` →
  `max_error`/`mean_error`/`std_error`, matching the documentation and tests.
- `ela_multi_quality` renamed to `multi_quality_ela` (alias retained), default
  qualities `[75, 85, 95]` → `[70, 85, 95]`.
- `chi_square_test(lsb_plane)` replaced by `pov_chi_square_test(channel)` — it
  takes full channel values, returns a 4-tuple, and **the score direction is
  inverted**: a high value now means embedding.
- `analyze_prnu` returns `correlation_analysis` (was `reference_analysis`);
  metrics renamed `prnu_variance`/`prnu_mean`/`prnu_std` →
  `noise_variance`/`noise_mean_abs`.
- `detect_resampling` return shape replaced; `artifacts_detected` and the old
  `resampling_score` semantics are gone.
- `detect_interpolation_method` returns `likely_interpolation` with an explicit
  confidence level, and no longer returns `gradient_std`/`ringing_score`.
- `detect_copy_move` default threshold 0.95 → 0.99.
- FFT metrics: `phase_consistency_score` and `frequency_uniformity` removed
  from `metrics` (the latter moved to `technical_details`); added
  `spectral_power_law_slope`. DCT `block_consistency_score` →
  `jpeg_blockiness_ratio`.
- `estimate_jpeg_quality` and `is_standard_table` take an optional `table_id`
  to select the luminance or chrominance standard.
- `DEFAULT_DB_PATH` resolves relative to the project root rather than the
  working directory, so the ledger no longer moves with the launch location.
- Record IDs derive from the highest existing ID rather than the record count,
  which collided after `import_database()` merges.

### Documentation

- Corrected `docs/API.md` throughout — it documented four functions that were
  never implemented and several wrong return types. The test suite had been
  written from it rather than from the code, which is the root cause of the
  broken test files below.
- Rewrote the in-app technique guides that contradicted the code:
  `Descriptions/Steganography.md` (taught the inverted detection model),
  `Frequency.md` (documented removed metrics), plus `CMFD.md`,
  `Quantization.md`, `PRNU.md`, `Resampling.md` and `Hash_Verification.md`.
- README gains a Scope and Limitations section stating each technique's real
  boundaries, and a test-setup step — `pytest` lives in `requirements-dev.txt`,
  so the suite was silently unrunnable from a default install.
- CONTRIBUTING gains guidance on verifying that a new metric actually varies
  with what it measures, and on keeping `Descriptions/` in sync.

### Testing

- **115 passing tests**, up from 41 passing with 2 failures, 8 errors and one
  file that could not be imported.
- `tests/test_integration.py` rewritten — every assertion had targeted an API
  that never existed (`perform_ela` returning a dict, `generate_histogram`
  returning a string, and so on).
- `tests/test_metadata.py` fixture used `piexif.ExifIFD.ISO`, which does not
  exist in piexif 1.1.3, erroring all 8 tests in the class.
- `tests/test_ela.py` used a flat-grey fixture that compresses perfectly and
  yields zero error at every quality, making its assertions vacuous.
- Steganography tests had encoded the inverted model, asserting that a
  90%-ones LSB plane indicates hidden data — random embedding *balances* the
  plane, so this was backwards.
- New regression classes: `TestPrnuIdentifiesCameras`,
  `TestResamplingRecoversScale`, `TestLedgerIsTamperEvident`,
  `TestMetricsRespondToInput` and `TestAppRendersResults`.
- `.gitignore` broadened to cover all test fixture directories; an interrupted
  run had committed fixture images.

### Dependencies

- `scikit-image` (already present) now used for wavelet denoising in PRNU.
- `pytest` and `pytest-cov` must be installed from `requirements-dev.txt` to
  run the suite.

---

## [1.1.0] - 2025-12-12

### Added - Information Security Modules

- **🔐 Steganography Detection Module**:
  - LSB (Least Significant Bit) statistical analysis
  - Chi-square testing for randomness detection
  - Per-channel (RGB) probability scoring
  - Block-based spatial analysis with heatmaps
  - Visual analysis maps highlighting suspicious regions
  - Batch processing capability
  - Comprehensive interpretation guidelines
  - Educational documentation (Descriptions/Steganography.md)
  - Full test coverage (tests/test_steganography_detection.py)

- **🔑 Cryptographic Hash Verification Module**:
  - Perceptual hashing (pHash, aHash, dHash, wHash) using imagehash
  - SHA-256 cryptographic hashing for exact matching
  - JSON-based blockchain simulation for provenance tracking
  - Modification history with timestamps
  - Authenticity scoring (0-100 scale)
  - Legal chain of custody assessment
  - Database management (import/export functionality)
  - Hamming distance calculation for similarity matching
  - Educational documentation (Descriptions/Hash_Verification.md)
  - Full test coverage (tests/test_hash_verification.py)

- **UI Integration**:
  - Two new tabs in Streamlit interface (🔐 Steganography, 🔑 Hash Verify)
  - Interactive analysis workflows with progress indicators
  - Visual heatmaps and detailed results display
  - Database management interface for hash verification
  - Consistent error handling and user feedback
  - Educational tooltips and interpretation guides

### Changed

- Updated tab count from 12 to 14 in main application
- Enhanced TECHNIQUES dictionary with new modules
- Updated README.md with new feature descriptions
- Expanded project structure documentation

### Dependencies

- Added `imagehash` for perceptual hashing (pip install imagehash)
- Confirmed `scipy` already present for statistical tests

### Testing

- 14 passing tests for steganography detection (98% coverage)
- 18 passing tests for hash verification (84% coverage)
- Edge case handling for invalid inputs and small images

---

## [1.0.0] - 2025-12-XX

### Added

- **11 Forensic Analysis Techniques**:

  - Error Level Analysis (ELA) with multi-quality comparison
  - Comprehensive EXIF/metadata extraction
  - RGB histogram analysis with statistics
  - Noise map analysis for inconsistency detection
  - JPEG ghost detection
  - Quantization table forensics
  - Copy-Move Forgery Detection (CMFD)
  - PRNU (Photo Response Non-Uniformity) analysis
  - Frequency domain analysis (FFT/DCT)
  - Deepfake detection with GAN fingerprinting
  - Resampling and interpolation detection

- **Web-Based Interface**:

  - Streamlit-powered interactive GUI
  - 12-tab navigation system (now 14 tabs)
  - Real-time parameter adjustment
  - Image upload and preview
  - Dark theme with neon green accents

- **Comprehensive Documentation**:

  - README.md with quick start guide
  - API documentation (docs/API.md)
  - Forensic techniques guide (docs/TECHNIQUES.md)
  - Deployment guide (docs/DEPLOYMENT.md)
  - Contributing guidelines (CONTRIBUTING.md)

- **Testing Infrastructure**:

  - Unit tests for ELA module (11 test cases)
  - Unit tests for metadata module (9 test cases)
  - Integration tests (5 test suites, 15+ test cases)
  - Performance tests for different image sizes
  - Format compatibility tests (JPEG, PNG, grayscale, RGBA)
  - Pytest configuration with coverage reporting
  - Pre-commit hooks for code quality

- **Development Tools**:

  - requirements-dev.txt with testing/linting tools
  - pytest.ini with coverage configuration
  - .pre-commit-config.yaml for automated checks
  - Black, isort, flake8, mypy integration

- **Deployment Support**:
  - Streamlit Cloud deployment guide
  - Heroku deployment with Procfile
  - Docker support with Dockerfile and docker-compose.yml
  - AWS EC2 and Elastic Beanstalk instructions

### Technical Specifications

- **Python Version**: 3.9+
- **Core Dependencies**:
  - Streamlit 1.28.1
  - Pillow 10.1.0
  - OpenCV 4.8.1.78
  - SciPy 1.11.4
  - scikit-image 0.22.0
  - NumPy 1.24.3
  - Matplotlib 3.8.2
  - Plotly 5.18.0

### Design Choices

- **Streamlit over PyQt6**: Web-based approach for better accessibility, easier deployment, and faster development
- **In-memory Processing**: BytesIO for JPEG operations to avoid disk I/O overhead
- **Modular Architecture**: Separate modules for each technique enable easy extension
- **Dark Theme**: Professional forensic tool aesthetic with high visibility
- **Comprehensive Error Handling**: Graceful degradation when features unavailable

---

## [0.9.0] - 2025-11-XX (Beta)

### Added

- Initial project structure
- Core ELA implementation (basic version)
- Metadata extraction (basic EXIF)
- Basic Streamlit interface
- 5 initial analysis techniques

### Changed

- Framework selection from PyQt6 to Streamlit

---

## Version History

- **v3.0.0**: Forensic rebuild — published methods, result contract, per-session ledger, C2PA
- **v2.0.0**: Correctness release — six modules fixed, metric API changes
- **v1.1.0**: Steganography detection and hash verification
- **v1.0.0**: Full production release with 11 techniques, comprehensive docs, testing
- **v0.9.0**: Beta release with core features
- **v0.1.0**: Initial prototype

---

## Upgrade Guide

### From 2.0.0 to 3.0.0

**Breaking Changes**: Yes — every analysis function was replaced (see
"Changed - Breaking" under 3.0.0). The Streamlit app needs no action.

1. `pip install -r requirements.txt` (new pins; adds `PyWavelets`,
   `c2pa-python`) on Python 3.10.
2. Code calling `analysis/` directly: switch to the new entry points and read
   `result["status"]`, `result["metrics"]`, `result["findings"]` instead of
   module-specific keys. There are no scores to migrate.
3. The shared `temp/hash_database.json` is no longer read. Re-add images in a
   session and export the ledger; old database files are not importable.
4. Run the tests with `python -m unittest discover -s tests -t .`.

### From 1.1.0 to 2.0.0

**Breaking Changes**: Yes — see "Changed - Breaking" above. The Streamlit app
needs no action; only code calling the `analysis/` modules directly is affected.

**Results will differ, and that is the point.** Images previously reported as
suspicious may now read as clean, and vice versa. Re-run any analysis whose
conclusion mattered, particularly for PRNU camera matching (the verdict was
inverted), resampling (the score was saturated) and steganography (clean images
were flagged).

**Migration Steps**:

1. Pull latest code: `git pull origin main`
2. Update dependencies: `pip install -r requirements.txt --upgrade`
3. Rename ELA metric keys in any calling code: `mean_diff` → `mean_error`,
   `max_diff` → `max_error`, `std_diff` → `std_error`
4. Replace `chi_square_test(lsb_plane)` with `pov_chi_square_test(channel)`,
   noting the inverted score direction and the 4-tuple return
5. Replace `reference_analysis` with `correlation_analysis` for PRNU results
6. Existing hash ledgers keep working — records written before chaining are
   reported as `legacy_records` and marked "Partially verifiable" rather than
   failing verification. Re-register images to obtain a fully chained ledger.

---

## Contributors

- **CodeRafay** - Initial work and primary development

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to contribute.

---

## License

This project is licensed under the BSD 3-Clause License - see [LICENSE](LICENSE) file for details.

---

**Note**: For security vulnerabilities, please email [rafayadeel1999@gmail.com] instead of using the issue tracker.
