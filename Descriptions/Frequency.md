# Frequency Analysis (power spectrum and JPEG block grid)

Code: `analysis/frequency_analysis.py`, with the grid helpers in `analysis/util.py`.
Entry points: `analyze_spectrum(path)`, `analyze_blocking(path)`.

## 1. Power spectrum: `analyze_spectrum`

In natural images, power falls off roughly as 1/f^2 (Field 1987; Torralba and
Oliva 2003). The code:

1. Takes the luminance at full resolution and cuts a centre square crop of at
   most 2048 px. Cropping keeps the spectrum; resizing would change it.
2. Subtracts the mean and applies a 2-D Hann window. Because of the mean
   subtraction, a brightness shift no longer changes the result (it used to
   move HF% from 1.06 to 0.24).
3. Radially averages |FFT|^2 and fits the log-log **slope** on 24
   log-spaced frequency bins, so each octave counts equally (a fit over every
   radius is dominated by the high-frequency end, where most radii lie and
   noise / JPEG sets the level). A synthetic 1/f^2 image reads about -1.8,
   1/f^3 about -2.9. It also reports the share of power above half-Nyquist
   (**HF share**).
4. Returns `insufficient_data` for images under 16 px or uniform images.

Both numbers are measurements. A value outside the range measured on unedited
photos gives only a *notice*. There is no score and no verdict.

Calibration set: sample + 8 skimage photos + 8 camera-pipeline scenes (Bayer
mosaic, shot/read noise, OpenCV demosaic, some sharpened), each as PNG and
JPEG q70/85/95 (68 cases): slope -3.01 to -1.08, HF 0.19 to 28.6 %.

| Metric | Notice when |
|---|---|
| Spectral slope | < -3.5 or > -1.0 |
| Power above half-Nyquist | < 0.05 % or > 30 % |

Hold-out (6 other skimage images, 8 other camera seeds):

| Case | Notice |
|---|---|
| Unedited (60) | 8/60 = 13 % (all versions of `cat`, slope -4.3, and `colorwheel`, HF 0.02 %) |
| Gaussian blur sigma 1.5 | 13/15 |
| 2x bicubic upscale | 3/15 |
| Gaussian noise sigma 8 | 0/15 |

The notice is weak: one in eight clean images of an unusual scene (smooth,
out of focus, flat graphics) triggers it. Only strong blur is reliably seen.

Bundled sample: slope -2.19, HF share 5.4 %.

Images: the log power spectrum, and the radial profile with its fit.

Limitations: scene content (sky vs foliage, focus) moves both numbers as much
as editing does. Upscaling, sharpening and added noise usually stay inside
the range. A whole-image spectrum cannot localise an edit.

## 2. JPEG block grid: `analyze_blocking`

Method: W. Li, Y. Yuan and N. Yu, "Passive detection of doctored JPEG image via
block artifact grid extraction", Signal Processing 89(9), 2009.

1. **BAG extraction** (`util.bag_maps`)
   - Takes second-order differences |2f(x) - f(x-1) - f(x+1)| across each
     column and row gap. The two pixels either side of a gap are summed, so
     the grid phase is unambiguous.
   - Sets values above an adaptive threshold T = max(4, 8 x median) to zero,
     which removes object edges.
   - Accumulates the rest over 33 px along the boundary, then subtracts a
     33-px running median across it.
2. **Global grid** (`util.jpeg_grid_offset`)
   - Computes the energy for each phase 0-7 on each axis.
   - Strength = (best / second-best phase on x) x (best / second-best on y).
     A grid is reported when strength >= 1.4.
   - A grid origin (x, y) other than (0, 0) gives an *info* finding. It is
     consistent with (8 - x) mod 8 columns and (8 - y) mod 8 rows removed
     from the left/top after compression, or with the image itself being a
     pasted JPEG region.
   - A PNG that carries a grid is noted as having been JPEG-compressed before.
3. **Upscale vs grid**
   - The autocorrelation of the |first difference| profile (lags 2-32) is
     reported when it is >= 0.5.
   - A period other than 8 is reported as upscaling/resampling, not as a JPEG
     grid.
   - A nearest-neighbour 2x upscale gives equal peaks at 4 phases, so its grid
     strength is about 1.
4. **Local grid** (only when a global grid exists)
   - Uses 64x64 windows on a 32-px step.
   - A window is misaligned when its strongest phase pair differs from the
     global one and beats the global phase by 2x on some axis.
   - 5 or more touching windows with the **same** phase pair give a
     *warning*: texture produces random phases, a pasted JPEG produces one
     consistent phase.
   - A second grid covering >= 50 % of the image gives a *notice* instead: the
     whole image was cropped and recompressed.

Images:
- BAG map.
- Local alignment heatmap: green = aligned, red = another phase dominates,
  dark = no measurable grid.

Metrics: grid strength, grid origin, periodicity x / y, misaligned area %.

### Measured performance (16 photos, seeded)

| Case | Result |
|---|---|
| Never-compressed, NN 2x and bicubic 1.5x images | 0/48 false grids |
| Cropped JPEG, grid found with the correct crop offset, at q50 / 60 / 70 / 80 / 90 / 95 | 15 / 15 / 14 / 12 / 9 / 5 of 16 (73 %) |
| Periodicity reported on clean photos / NN 2x / NN 3x / bilinear 2x | 0 / 16 / 16 / 10 of 16 |
| Local warning on clean cropped JPEGs q50-95 | 2/48 (both are the bundled sample, itself a q95 JPEG, so the crop created a real second grid) |
| Patch from a q50-80 JPEG pasted off-grid into a q70-95 JPEG, localised, saved at q95 / q100 / as PNG | 6 / 7 / 8 of 16 (44 %) |

Bundled sample: grid at (0, 0), strength 1.83, no local inconsistency.

### Limitations

- At quality >= 90 the grid is weak and often not measurable, especially in
  small or smooth images.
- Resizing, rotation, filtering or noise after compression erase the grid. An
  image with no measurable grid may still have been a JPEG.
- A pasted region is visible only if it carries its own grid at a different
  phase and was not recompressed at a lower quality afterwards. Final saves
  at q <= 90 hide it.
- Flat regions have no measurable local grid.
