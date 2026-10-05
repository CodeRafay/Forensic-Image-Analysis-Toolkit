# PRNU — Sensor Fingerprint

## What it is

Each pixel of a camera sensor converts light with a slightly different gain.
That gain error is fixed for the life of the sensor and multiplies the scene:

    I = I0 + I0·K + noise

`K` (the PRNU) is a fingerprint of the individual sensor, not just the model.
With reference photos from a candidate camera you can test whether a photo
carries that camera's fingerprint, and check whether any region lacks it.

## What the code does

Implementation follows the Camera-Fingerprint reference toolbox:

1. **NoiseExtract** (Lukáš, Fridrich & Goljan 2006): 4-level db4 (8-tap)
   wavelet transform. Each detail coefficient is Wiener-attenuated with a
   local variance, the minimum over 3/5/7/9 windows, and σ0 = 3. The
   approximation band is zeroed. What is left is the noise residual `W`.
2. **ZeroMeanTotal**: removes row and column means on each of the four 2×2
   sub-lattices. This takes out CFA and JPEG row/column artifacts that every
   camera of a model shares.
3. **Fingerprint** (Chen et al. 2008 maximum-likelihood estimate):
   `K = Σ W·I / Σ I²` over the references, with saturated pixels (≥ 250)
   excluded. Then ZeroMeanTotal again.
4. **WienerInDFT** (Goljan et al. 2009), applied to `K` (σ = std K) and to
   the test residual (σ = std W). It Wiener-filters the DFT magnitude and
   keeps the phase, which flattens isolated spectral peaks (periodic,
   model-shared patterns) while white-noise content passes. Checked in the
   unit test: an injected period-8 pattern and a checkerboard drop from
   50–300× the median spectrum to ≤ 3×, and the white part keeps NCC > 0.99.
5. **Matching**: the test residual is correlated with `I_test·K`.
   - **NCC**: normalised correlation.
   - **PCE** (peak-to-correlation energy): `sign(C₀)·C₀² / mean(C²)` over the
     circular cross-correlation `C`, with the 11×11 neighbourhood of the
     zero-shift peak excluded. **Decision: PCE > 60** (the standard
     threshold from Goljan, Fridrich & Filler 2009, which measured a
     false-alarm rate of about 2.4·10⁻⁵ on over a million Flickr images).
6. **Local integrity test** (predictor from Chen, Fridrich, Goljan & Lukáš
   2008; decision from Chierchia, Poggi, Sansone & Verdoliva 2014). This runs
   only when PCE > 60 and at least 2 references are given.
   - The image is split into 128×128 blocks at stride 32. For each block the
     code computes the observed correlation ρ between `W` and `I·K`.
   - A **correlation predictor** ρ̂ (second-order polynomial in Chen's
     intensity, texture and flatness features) is fitted by least squares on
     every reference, each on one 1024×1024 window against its
     leave-one-out fingerprint (windows cycle over the frame).
   - σ0 ("no fingerprint") comes from correlating with circularly shifted
     fingerprints; σ̂ is the predictor's residual spread.
   - Per-block log-likelihood ratio λ = log N(ρ; 0, σ0) − log N(min(ρ, ρ̂);
     ρ̂, σ̂) (one-sided: a block above its prediction never counts as
     missing).
   - **Bayesian MRF**: labels u (1 = fingerprint absent) minimise
     Σ u·(γ − λ) + β·#(disagreeing 8-neighbours), γ = 2, β = 0.5. The
     energy is minimised **exactly by an s–t minimum cut** (scipy
     `maximum_flow`) on the block grid. The paper works per pixel; this
     implementation works on the block grid.
   - A block is **testable** when it is not dark (block mean < 40), saturated
     (> 250) or almost fully flat, and ρ̂ ≥ σ0. Regions of fewer than 16
     labelled testable blocks are dropped.
   - If **fewer than 10 % of blocks are testable**, the local test reports
     *insufficient data* and draws no overlay. Before this change a dark or
     flat image gave the misleading "0 blocks tested, nothing found".

Images are analysed at **full resolution** up to `max_px` per side
(default 4096, so 4000×3000 is uncropped); larger ones are
**centre-cropped**, never resized, because resampling destroys the
pixel-aligned pattern. References are cropped identically and must have the
same original pixel size as the test image. Everything is float32, and the
references are streamed: the running sums ΣW·I and ΣI² are updated one
reference at a time (two in parallel threads).

## Reading the output

| Output | Meaning |
|---|---|
| Residual std | Strength of the extracted noise, in grey levels. Near 0 means flat or synthetic content (`insufficient_data`). |
| No references | Status `ok`, with "no reference fingerprint — camera identification not possible". Only residual statistics are shown. |
| References of a different size | Status `not_applicable`. The fingerprint is pixel-aligned, so rotated, resized or cropped references cannot be used. |
| PCE > 60 | The image carries the reference camera's fingerprint (info). |
| PCE ≤ 60 | Notice: no match. This does **not** exclude the camera, because JPEG, resizing, denoising, digital zoom or a different crop remove the match. |
| NCC | Shown for reference. It depends on image size and content, so the decision uses PCE. |
| Blocks tested / untestable, Testable fraction | How much of the image the local test could actually evaluate. Grey in the overlay means untestable. Below 10 % the local test reports *insufficient data*. |
| Regions lacking the fingerprint | Warning. Testable blocks labelled by the MRF as having a correlation consistent with "no fingerprint" where the predictor expects one. This fits content from another source (splice) or strong local processing. The table gives each region's bounding box in original-image coordinates, with observed and predicted correlation. |

Images returned: the zero-meaned noise residual and, when the local test ran,
an overlay (red = fingerprint missing, grey = untestable).

## Measured performance (camera simulator, hold-out)

Simulator (`scratchpad` scripts, seeded): scene (upscaled skimage photo) →
Bayer RGGB raw · (1 + K) → shot noise (variance 0.3·I) + read noise (σ 2) →
8-bit → OpenCV **bilinear demosaic** → JPEG q. K ~ N(0, σ²) with
realistic σ = 0.003, 0.006 and 0.01. The thresholds were chosen on set A
(scenes astronaut … horse, seeds 1xxx); every number below is from
**set B** (different scenes: clock, moon, camera, brick, grass, gravel,
cell, hubble, text; different seeds).

**Camera matching (PCE > 60)**, same camera, share of 24 test shots
(2 cameras × 4 shots × JPEG q75/85/95), by size and number of references:

| Size | K σ | 1 ref | 4 refs | 8 refs |
|---|---|---|---|---|
| 1 MP | 0.003 | 0 % | 0 % | 0 % |
| 1 MP | 0.006 | 0 % | 46 % | 75 % |
| 1 MP | 0.01 | 38 % | 96 % | 96 % |
| 4 MP | 0.003 | 0 % | 12 % | 38 % |
| 4 MP | 0.006 | 38 % | 96 % | 96 % |
| 4 MP | 0.01 | 46 % | 100 % | 100 % |
| 12 MP | 0.003 | 4 % | 38 % | 83 % |
| 12 MP | 0.006 | 79 % | 100 % | 100 % |
| 12 MP | 0.01 | 92 % | 100 % | 100 % |

Different camera: **0 / 648** comparisons above 60 (max PCE 18.8).
The match rate is driven by pixel count and reference count much more than
by JPEG quality: a weak fingerprint (σ 0.003) is essentially never found
below 4 MP, and one reference is rarely enough. This is why the default no
longer crops to 2048 px.

**Local splice test** (4 MP = 2048×2048, 8 references, a square from the
other camera's shot of the same scene pasted in; "found" = a flagged block
centred inside the square; only shots with PCE > 60):

| K σ, JPEG | clean shots with a false region | 192 px | 256 px | 384 px | 512 px |
|---|---|---|---|---|---|
| 0.01, q95 | 2/11 | 10/11 | 11/11 | 11/11 | 11/11 |
| 0.01, q85 | 0/12 | 2/12 | 8/12 | 12/12 | 10/12 |
| 0.01, q75 | 0/8 (4 insufficient) | 0/8 | 3/8 | 5/8 | 7/8 |
| 0.006, q85 | 1/8 (4 insufficient) | 0/8 | 0/8 | 0/8 | 0/8 |
| 0.003, q85 | 10/12 shots do not match; local test not run | | | | |

Pooled clean false-alarm rate on the hold-out: **3/39 (8 %)**; on the
calibration set it was 0/24. False regions come from content the predictor
models poorly (very textured or dark scenes). **At a realistic σ = 0.006
the local test does not detect splices of any tested size (≤ 512 px).** It
works only when the fingerprint is strong (σ ≈ 0.01) and the image is
lightly compressed. Treat a reported region as a lead to examine, and an
empty result as no evidence either way.

**Cost** at 12 MP (4000×3000 JPEG), 8 references, measured with
tracemalloc on a shared (busy) 8-core machine: 28 s, 650 MB peak; without
references 4 s, 205 MB.

Real cameras differ from this simulation. In-camera denoising, sharpening,
lens correction and firmware artifacts are not modelled. Real-data
calibration (for example on the Dresden database) has not been done here.

`tests/test_prnu.py` reruns a small version (1 MP, σ 0.01, q92, 2 cameras ×
8 references): ≥ 80 % same-camera matches, 0 cross-camera matches, 0 clean
false regions, a 384 px splice found in ≥ 50 % of matched shots. It also
checks that a mostly saturated frame reports *insufficient data* and that
the min-cut is exact on small grids.

## Practical advice

- Use at least 8 reference images, ideally 20 or more. Bright, smooth, in-focus
  shots such as sky or walls give the cleanest fingerprint. All references
  must be the same size and orientation as the test image.
- Use the least-processed originals available: no resizing, no editing, and
  the highest JPEG quality.
- Smartphones with multi-frame or HDR pipelines, digital stabilisation or
  lens-distortion correction may not match at all.

## Limitations

- No geometric search: rotated, scaled, digitally zoomed or re-cropped images
  cannot be matched.
- Strong JPEG compression, denoising and resizing weaken or remove the
  fingerprint. A non-match is not evidence of a different camera.
- Cameras of the same model can share weak non-unique artifacts.
  ZeroMeanTotal and WienerInDFT reduce this but do not remove it.
- The local test has a resolution of about 128 px. Smaller pasted objects are
  missed, and dark, saturated, flat or very textured areas are untestable.
  With a realistic sensor (σ ≈ 0.006) it misses even 512 px splices; it is
  only useful with strong fingerprints and light compression, and gave false
  regions on 8 % of clean hold-out shots.
- A flagged region means the fingerprint is missing there. It does not say
  why: a splice, heavy local retouching or inpainting all look the same.

## References

- J. Lukáš, J. Fridrich, M. Goljan, "Digital camera identification from
  sensor pattern noise", IEEE TIFS 1(2), 2006.
- M. Chen, J. Fridrich, M. Goljan, J. Lukáš, "Determining image origin and
  integrity using sensor noise", IEEE TIFS 3(1), 2008.
- M. Goljan, J. Fridrich, T. Filler, "Large scale test of sensor fingerprint
  camera identification", Proc. SPIE 7254, 2009.
- G. Chierchia, G. Poggi, C. Sansone, L. Verdoliva, "A Bayesian-MRF approach
  for PRNU-based image forgery detection", IEEE TIFS 9(4), 2014.
