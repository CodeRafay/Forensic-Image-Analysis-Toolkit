# Resampling Detection

Tests whether the pixels were produced by interpolation, i.e. the image (or
a pasted part of it) was enlarged, shrunk or rotated after capture. A result
is an **indicator, not proof**: resizing is routine (web publishing,
thumbnails) and a detection says nothing about whether the content was
altered.

## Method

M. Kirchner, *Fast and reliable resampling detection by spectral analysis of
fixed linear predictor residue*, ACM MM&Sec 2008, with the JPEG-aware peak
masking of M. Kirchner & T. Gloe, *On resampling detection in re-compressed
images*, IEEE WIFS 2009.

1. The image is decoded to grayscale at **full resolution** (never resized).
2. Each pixel is predicted from its 8 neighbours by Kirchner's fixed filter
   (0.5 x edge neighbours, -0.25 x corner neighbours); `e` is the residual.
3. p-map `p = exp(-e^2 / 8)`: close to 1 where the pixel is a linear
   combination of its neighbours. After interpolation this happens in a
   pattern that repeats with the resampling period.
4. The p-map (mean removed, Hann window; central 2048x2048 crop for very large
   images) is Fourier-transformed. Each spectrum bin is divided by the
   geometric mean of its 9x9 neighbourhood, so a periodic component shows up
   as an isolated peak.
5. **Statistic = the largest normalised peak** outside the low-frequency disc
   (radius 0.06 cycles/px, image content), after a **narrow notch** at
   lattice points (Kirchner & Gloe 2009): always at (0.5, 0), (0, 0.5),
   (0.5, 0.5), because camera demosaicing has period 2 (without this, 7 of
   16 clean demosaiced PNGs read as resized); and at every (k/8, l/8) when the
   file is a JPEG or shows a measurable 8x8 grid (grid strength >= 1.4, the
   threshold calibrated in frequency_analysis). Notch half-width: 2.5 bins,
   at least 0.01 cycles/px (texture smears JPEG peaks by a few bins).
6. **Derivative projection** (Gallagher 2005; the axis-aligned case of
   Mahdian & Saic, IEEE TIFS 2008): mean |second derivative| of every column
   (and every row), 1-D spectrum, contrast against the local log-spectrum,
   same lattice notch (2.5 bins). Averaging a whole column keeps the
   interpolation period after JPEG, where the 2-D p-map loses it. It sees
   axis-aligned scaling only, not rotation.
7. **Decision**: flagged if either the p-map peak >= 12 or the projection
   peak >= 7.8 (each calibrated separately; combined false-alarm rate below).
8. **Nearest-neighbour test**: share of adjacent pixel columns/rows that are
   exact copies, counted only if the copies lie on a regular lattice.
   Needed because a centre-aligned 2x enlargement is symmetric in both
   phases and leaves no p-map periodicity.
9. **Localisation**: the p-map statistic in 128x128 windows (stride 64;
   doubled on very large images so there are at most 1500 windows).

## Reading the output

| Metric | Meaning |
| --- | --- |
| Peak ratio (x local background) | Strongest 2-D p-map peak. >= 12 is a warning. |
| Peak frequency (vertical, horizontal) | Where the peak is, in cycles/pixel. |
| Projection peak ratio | Strongest 1-D derivative-projection peak. >= 7.8 is a warning. |
| Projection peak frequency | Its frequency and axis (horizontal = column profile). |
| Duplicated columns / rows (%) | Nearest-neighbour enlargement by s duplicates 100(1-1/s) %: 1.25x -> 20 %, 2x -> 50 %. |
| Windows above threshold (%) | Share of 128x128 windows with window ratio >= 10. |

**Scale factor.** An up-scaling by s peaks at f = 1 - 1/s (1.25x -> 0.200,
1.5x -> 0.333). The spectrum is aliased, so the same peak also fits 1/f and
1/(1+f) (down-scaling): all are listed. A uniform scaling peaks on both axes,
and the strongest 2-D bin is often the diagonal (f, f); that is read as a
uniform scale, not a rotation. A rotation by t peaks at radius 2 sin(t/2),
slightly off-axis; such peaks get a rotation reading.

**Images**: the p-map spectrum (bright isolated dots = periodicity), a
heatmap of the window statistic, and the image with windows above threshold
in red. A pasted rescaled object shows as a red cluster while the rest of the
image stays clean; the global test usually stays below threshold then, so
the finding is a *notice*.

## Measured performance

Thresholds were chosen on calibration set A and then measured, unchanged, on
a different hold-out set B and on the reviewer's independent set.

- **A** (calibration): 8 photos (sample, coffee, chelsea, rocket, brick,
  page, grass, gravel) + 10 camera-pipeline scenes (synthetic scene, Bayer
  RGGB mosaic, shot + read noise, OpenCV bilinear demosaic, half sharpened).
  Negatives: PNG, JPEG q75/85/92/95, crop of a q80 JPEG re-saved at q90
  (108). Highest p-map 11.49 (brick q85), highest projection 7.68 (page).
- **B** (hold-out): 7 other skimage images + 10 other camera seeds, same
  cases (102 negatives); positives on the 10 camera hosts.

**False alarms**: A 0/108, B 1/102 (`hubble_deep_field` PNG, p-map 26.8;
that image is probably resampled at source), reviewer set 0/64 (16
demosaiced hosts, PNG and JPEG q75/90/95), no flagged windows on the
reviewer negatives.

**Detection, hold-out B (of 10)** and **reviewer set (of 16)**:

| Condition | B: PNG / q95 / q90 / q80 | Reviewer: PNG / q95 / q90 / q80 |
| --- | --- | --- |
| up 1.1x bicubic | 10 / 10 / 10 / 9 | 14 / 9 / 6 / 0 |
| up 1.25x bicubic | 10 / 10 / 10 / 10 | - |
| up 1.3x bilinear | 10 / 10 / 10 / 9 | 16 / 12 / 8 / 1 |
| up 1.7x bicubic | 10 / 10 / 10 / 10 | 16 / 14 / 11 / 9 |
| down 0.8x bicubic | 10 / 0 / 0 / 0 | 14 / 0 / 0 / 0 |
| rotation 7 deg bilinear | 10 / 8 / 0 / 0 | 13 / 0 / 0 / 0 |
| rotation 7 deg bicubic | 9 / 8 / 1 / 0 | 13 / 0 / 0 / 0 |

After JPEG almost all enlargement detections come from the projection test
(e.g. B 1.1x q80: p-map 0/10, projection 9/10). The two sets differ in
difficulty (the reviewer hosts are smaller and smoother); expect the lower
numbers on real photos.

Run time at 12 MP (4000x3000 JPEG): about 20 s, 490 MB peak (tracemalloc).

Not implemented: Mahdian & Saic's Radon projections at several angles, which
would extend the projection test to rotation after JPEG.

## Limitations

- **Down-scaling** is found only in lossless files; after any JPEG, never.
- **Rotation** is found in lossless files and sometimes at q95; at q90 and
  below almost never.
- **JPEG after enlargement**: most 1.1-1.7x enlargements are found at
  q90-95; at q80 small factors (1.1-1.3x) are often missed.
- **Smooth 2x** (bilinear/bicubic/Lanczos, centre-aligned) leaves no
  periodicity. Nearest-neighbour is found by duplication only up to 2x and
  only in lossless files.
- In JPEG images the 2-D test cannot see factors whose peak lies within
  0.01 cycles/px of a multiple of 1/8 (about 1.14x, 1.33x, 1.6x, 2x and
  aliases); the projection test has a narrower (2.5-bin) blind band.
- The scale factor is ambiguous by aliasing; all readings are listed.
- Periodic textures (brick, fabric, screens, halftone) can produce peaks
  unrelated to resampling. Brick JPEGs came closest to the threshold.
- A clean result means no periodicity was found at this sensitivity, not
  that the image was never resized.
