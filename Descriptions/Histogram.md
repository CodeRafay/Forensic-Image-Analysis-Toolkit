# Histogram Analysis (contrast-enhancement fingerprint)

Method: M. C. Stamm and K. J. R. Liu, "Forensic detection of image manipulation
using statistical intrinsic fingerprints", IEEE TIFS 5(3), 2010.
Code: `analysis/histogram_analysis.py`, entry point `analyze_histogram(path)`.

## What the code does

A pixel-value mapping (gamma, levels/curves, linear stretch, histogram
equalisation) applied to an 8-bit image turns a smooth histogram into one
with isolated peaks and empty bins. Those add high-frequency energy to the
histogram's DFT. The code computes this per channel, on every stored pixel
(no downscaling):

    g(x) = h(x) * p(x)      p = pinch-off window (N = 8) that suppresses
                            saturation spikes at 0 and 255
    G(k) = DFT(g) / sum(g)
    F    = mean |G(k)| for 112 <= k <= 128

A channel with **F > 20e-3** gives a *warning*. Grayscale files are analysed
as one channel.

Also reported:
- **Empty bins inside the occupied range**: gaps are counted only between the
  0.1th and 99.9th percentile of that channel. A dark photo that uses values
  0-60 no longer counts about 195 "gaps".
- **Clipping**: share of pixels at 0 and at 255. Above 1 % this is an *info*
  note, because clipping comes from exposure and is not by itself an edit.

## Outputs

- Image: per-channel histogram (% of pixels per value).
- Metrics: F (x1000) and interior empty bins per channel.
- Table: F, occupied range, gaps, % at 0/255, mean and std per channel.

## Measured performance

16 photos (sample + scikit-image), using the maximum F over channels:

| Case | Flagged |
|---|---|
| Negatives: PNG, JPEG q70-100, 0.5x downscale, dark (x0.3 + sensor-like noise), bright | 5/96 (5.2 %) |
| - excluding skimage `retina` (mostly black background) | 0/90 |
| Gamma 0.7, lossless | 15/16 |
| Gamma 1.4, lossless | 13/16 |
| 2-98 % linear stretch, lossless | 14/16 |
| Histogram equalisation, lossless | 16/16 |
| Same four, then saved as JPEG q90 | 1-3/16 each |

### Hold-out re-measurement (fix round)

7 photos not used for calibration, other seeds. Camera-like pipeline: RGGB
mosaic at 12 bit, shot + read noise, OpenCV demosaic, gamma to 8 bit,
optional sharpening, saved PNG / JPEG q75 / q85 / q92.

| Case (hold-out) | Flagged |
|---|---|
| Camera pipeline, 12-bit raw (56) | 1/56 (one PNG of skimage `hubble_deep_field`) |
| Plain photos PNG / q70 / q85 / q95 (28) | 4/28, all skimage `retina` (black background) |
| Reviewer's skimage files (48) | 2/48, both the synthetic `logo` |
| Total negatives | 7/132 (5.3 %), 6 of them large-uniform-background or synthetic images |
| Gamma 0.7 / gamma 1.4 / 2-98 % stretch, lossless (14 each) | 14/14, 14/14, 13/14 |
| Same, saved as JPEG q92 | 0/14 each |

Note: a pipeline that quantises the *linear* raw to 8 bit and then applies
gamma is a real pixel-value mapping, and the detector flags it (6/56 PNGs of
such a pipeline). Real cameras apply the tone curve at 12-14 bit.

12 MP JPEG (4000×3000): about 5 s and 144 MB peak. Pixels are read as
uint8 straight from the decoder; channel mean/std come from the histogram.

Negatives have median F of about 3e-3 (dark variants reach at most 8e-3).
Lossless enhancements have median F of about 40-100e-3. The cutoff c = 112
is what separates them: at c = 32 or 64, the smooth but narrow histograms of
dark photos reached up to 97e-3.

## Limitations

- Detects only global value mappings. Local edits, splicing and geometric
  changes leave the histogram smooth.
- JPEG compression after the enhancement smooths the histogram. At q90 most
  enhancements are no longer detected (see the table above).
- Linear gains whose gap pattern repeats every 3-5 values (x1.25, x1.5, x3)
  put their energy below the cutoff and are missed (F 2.7-8.9e-3). Gains of
  x1.2, x1.7 and x2 are detected.
- Contrast reduction, and mappings followed by resizing or added noise, are
  harder to see.
- Graphics, screenshots, palette images and images with one dominant value
  (a large uniform background) have spiky histograms without any enhancement.
