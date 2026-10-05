# Synthetic-Image Traces (Experimental)

> **This tab cannot tell you whether an image is AI-generated.** There is no
> trained detector and no verdict, only a spectral measurement. Modern
> diffusion models, resizing and JPEG remove these traces, so a low reading
> says nothing about how an image was made. A high reading has many ordinary
> causes.

## Idea

Many image generators build the picture by repeated upsampling with
(transposed) convolutions. That can leave a faint periodic pattern in the
high-frequency noise residual, which shows up as:

- sharp **peaks in the residual power spectrum**;
- a periodic **autocorrelation** of the residual;
- an unusual **high-frequency end of the azimuthally averaged spectrum**.

These signs were described by Corvi et al. (ICASSP 2023) for GAN and
diffusion images, and by Durall et al. (CVPR 2020) for up-convolution
spectra. Detectors in those papers are *trained* on these patterns. This
module only measures them.

## What the code does

1. Loads the image as greyscale. Images larger than 1024 px are
   **centre-cropped**, never resized, because resampling creates and
   destroys exactly these peaks. Images under 256 px, or flat images, return
   `insufficient_data`.
2. Computes the noise residual with the PRNU module's wavelet NoiseExtract
   (db4, 4 levels).
3. Estimates the power spectrum by Welch averaging: 128×128 Hann-windowed
   tiles at stride 64, `|FFT|²` averaged over tiles.
4. **Peak strength**: for each frequency, the log power minus the 9×9 local
   median of the log power, in dB. The maximum is taken after excluding
   these bins:
   - DC and the two frequency axes (within ±1 bin);
   - the **Nyquist rows and columns** (within ±1 bin of ±0.5 cycles/px).
     Bayer demosaicing leaves energy there in ordinary camera images: before
     this exclusion, 4 of 15 clean demosaiced PNGs gave a notice (up to
     18 dB at (−0.5, 0.445)). The largest value there is reported as the
     "Nyquist-line peak" (info only);
   - multiples of 1/8 cycle/px (±1 bin), when the file is JPEG or shows a
     JPEG block grid (`util.jpeg_grid_offset` strength > 1.15). Those peaks
     come from 8×8 DCT blocks. They are reported separately as the
     "8-px-grid peak" and not treated as generation traces.
5. **Azimuthal average** of the image's log power spectrum (Durall). The
   code reports mean power at 0.9–1.0 of Nyquist minus power at 0.4–0.5
   (dB), as an informational number.

## Reading the output

| Output | Meaning |
|---|---|
| Off-grid residual peak (dB) | Strongest isolated periodic component of the residual. Above **9 dB** gives a *notice*; otherwise *info*. |
| Peak frequency / period | Where that peak is. Period 3 suggests ×1.5 or ×3 resampling or upsampling. |
| Nyquist-line peak (dB, demosaicing/CFA) | Strongest peak on the ±0.5 cycles/px rows/columns. Demosaicing, stride-2 transposed convolution (2-px checkerboard) and 2× upsampling all land here and cannot be told apart, so it is info only (a finding appears above 9 dB). |
| 8-px-grid peak (dB) | Peak at k/8 cycles/px. On JPEG files this is compression, and it grows as quality drops. |
| Azimuthal 0.9–1.0 vs 0.4–0.5 Nyquist (dB) | High-frequency roll-off. Very negative after JPEG, blur or downscaling. No threshold is applied. |
| Tiles averaged | More tiles give a steadier spectrum. |

Images:

- the residual spectrum (dB above local median), with the peak marked;
- the residual autocorrelation (±16 px, zero lag hidden);
- the azimuthal-average plot.

Findings are only ever *info* or *notice*, never *warning* and never a
verdict.

## Calibration and hold-out

Threshold 9 dB (chosen on the original 107 in-repo negatives: skimage photos
and the bundled sample as PNG, JPEG q20–100 and 0.5× downscale; max 8.5 dB).

Hold-out negatives built with a camera simulator: scene → Bayer RGGB raw
(with PRNU) → shot + read noise → OpenCV bilinear demosaic → half of them
mildly sharpened (unsharp mask 0.6, σ 1) → PNG and JPEG q75/85/92, 1024 px.

| Set | Negatives | Max peak | Above 9 dB |
|---|---|---|---|
| Simulator set A (calibration scenes) | 80 | 5.1 dB | 0/80 |
| Simulator set B (other scenes, other seeds) + the reviewer's 30 demosaiced PNG/JPEG files | 110 | 10.7 dB | **1/110 (0.9 %)** |

Positives on the same simulator images (set B): a period-3 pattern (±1.5
grey) added before saving is found in 20/20 PNG and 20/20 JPEG q92 cases.

What is no longer detectable by design: the 2×2 checkerboard (Nyquist)
pattern. It now shows only in the Nyquist-line number, because ordinary
demosaicing produces the same peak.

`tests/test_deepfake_detector.py` re-checks: FPR ≤ 5 % on PNG/q50/q75/q95
in-repo negatives; demosaiced camera PNGs stay below 9 dB; a checkerboard is
reported on the Nyquist lines and never as the main peak; ≥ 90 % detection
of the period-3 pattern.

These are **synthetic artifacts**, not real generator outputs. No claim is
made about detection rates on real GAN or diffusion images.

## Limitations

- Cannot reliably identify AI-generated images. A trained, up-to-date
  detector plus provenance data (C2PA Content Credentials, see the Metadata tab)
  are the appropriate tools.
- Modern diffusion models, post-resizing, cropping plus rescaling and JPEG
  compression remove or mask periodic traces. **Absence of peaks says
  nothing.**
- Peaks also come from resampling, demosaicing, sharpening, screen or print
  re-capture, halftoning and periodic scene texture such as fabric, brick,
  grids or microscopy.
- On JPEG files, generator peaks at multiples of 1/8 cycle/px cannot be
  separated from compression.
- Period-2 patterns (2× upsampling, stride-2 checkerboards) sit on the
  Nyquist lines with demosaicing and are not evaluated.

## References

- R. Corvi, D. Cozzolino, G. Zingarini, G. Poggi, K. Nagano, L. Verdoliva,
  "On the detection of synthetic images generated by diffusion models",
  ICASSP 2023.
- R. Durall, M. Keuper, J. Keuper, "Watch your up-convolution: CNN based
  generative deep neural networks are failing to reproduce spectral
  distributions", CVPR 2020.
