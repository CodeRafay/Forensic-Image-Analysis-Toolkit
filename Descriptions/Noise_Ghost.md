# Noise Consistency & JPEG Ghosts

Both tabs look for regions whose history differs from the rest of the image.
They report measurements and inconsistencies. Neither can show that an image
is unedited.

## 1. Local noise residual (`analysis/noise_map.py`)

### What the code does
Splicebuster: D. Cozzolino, G. Poggi, L. Verdoliva, *Splicebuster: a new
blind image splicing detector*, IEEE WIFS 2015. Every camera and processing
chain (sensor noise, demosaicing, sharpening, JPEG history) leaves its own
texture in the high-pass residual. On luma, at full resolution:

1. Third-order residual `-x[i] + 3x[i+1] - 3x[i+2] + x[i+3]`, horizontal and
   vertical.
2. Quantised with step 2 and truncated to [-1, 1]. The paper uses T = 2. On
   our calibration splices T = 1 separated much better (mean window AUC 0.94
   vs 0.72).
3. Co-occurrence of 4 neighbouring residual values gives one of 81 codes per
   pixel. Horizontal and vertical counts are pooled.
4. A code histogram for every 128×128 window. The stride is 8 px, or 16 px
   on large images (12 MP), so there are at most 50k windows. It is
   normalised and square-rooted, then PCA keeps 25 dimensions.
5. EM fits two Gaussians, a majority ("host") and a minority class. The
   paper's Gaussian–uniform variant found the splices worse (AUC 0.69).
   Windows with mean luma below 8 or above 247 are skipped.
6. **Decision (our addition).** Take the largest connected group of
   minority windows. It is reported as a **notice** when all of these hold:
   - it covers 5–30 % of the usable windows,
   - it holds ≥ 95 % of all minority windows (a splice is one blob; a
     content-driven cluster is usually scattered),
   - its median log-likelihood ratio is ≥ 5.

Images smaller than 256 px, flat images, or images with fewer than 64
usable windows return `insufficient_data`.

### Reading the output
- **Heat map**: log-likelihood ratio, minority vs majority model, per window.
  Bright means "fits the minority class".
- **Candidate region (red)**: the largest minority group, shown only when
  the image is flagged.
- **Metrics**: usable windows, stride, % outlier windows, largest region
  (% of usable windows), its compactness and its median log-likelihood
  ratio.
- The two classes always exist. On an untouched photo they usually split by
  content (sky vs city, shadow vs light), so a large or scattered minority
  is normal. The notice asks for a single compact blob that is clearly
  separated. Still, check whether the region is just different content.

### Measured (hold-out)
Synthetic camera pipeline: photo → RGGB mosaic → shot + read noise → OpenCV
bilinear / EA / VNG demosaic → optional sharpening → PNG / JPEG q75 / q85 /
q92. Plain photos (PNG / q70 / q85 / q95) and the reviewer's 48 skimage
files are also used. Positives: a patch of another photo, passed through a
different camera chain (noise gain ×0.3 or ×3, other demosaic, other JPEG
history), covering 1/16–1/4 of the image. Thresholds were chosen on 8
photos. The numbers below are 7 other photos with other seeds.

| Case | Splicebuster | Old Lyu kurtosis method |
|---|---|---|
| Negatives (132) | 7/132 (5.3 %); 4 are the flat-background skimage `clock` | 0/132 |
| Splices, all finals (56) | 38/56 (68 %) | 2/56 |
| – saved PNG / q92 / q85 / q75 | 9/14, 10/14, 9/14, 10/14 | 1, 1, 0, 0 |
| Mean pixel F1 on splices (empty mask counts 0) | 0.50 | 0.01 |

The old method's 0 false alarms are not a strength. It returned
`insufficient_data` on 28 of the 42 camera-pipeline JPEGs, because it
abstains on most JPEGs. It was removed.

The bundled sample photo is not flagged: its classes split sky / city
(48 %, above the 30 % limit), and its pasted "UFO" (about 360×60 px, see
ELA.md) is not found.

12 MP JPEG (4000×3000): about 7.5 s and 216 MB peak (stride 16 px).

**This is a weak detector.** Treat a notice as a pointer for inspection, not
as evidence.

### Limitations
- A region from the same camera and settings, or re-processed to match, is
  invisible.
- Resizing, denoising or strong JPEG compression of the whole image weaken
  the contrast.
- Content changes the residual too. Large flat, dark, saturated or heavily
  textured areas can form a compact minority on an untouched image (the
  `clock` false alarms).
- Resolution is one 128-px window, and borders are blurred by about half a
  window.
- A splice covering more than ~30 % of the image is not reported. The
  "minority" assumption fails there.

## 2. JPEG ghosts (`analysis/jpeg_ghost.py`)

Method: H. Farid, *Exposing Digital Forgeries from JPEG Ghosts*, IEEE TIFS
4(1), 2009, including its §3 grid-shift recompression.

### What the code does
1. Decodes the stored luminance (no RGB round trip) and recompresses it as a
   greyscale JPEG at each tested quality q (default 50, 55 … 95) **below the
   final quality**. Only luminance is used (a deviation from Farid's
   3-channel average): that is where the quantization traces are, at a third
   of the cost.
2. `d(q) = mean over a 16×16 window of (f − f_q)²`, sampled on an 8-px
   stride, and normalised per window across q to [0, 1] for display.
3. The **final quality** comes from the stored quantization table
   (`quant_table.estimate_jpeg_quality`, exact for libjpeg tables).
4. **Grid shift.** A ghost appears only when the recompression grid lines up
   with the region's earlier JPEG grid. Besides the file grid (0, 0), one
   other offset is tested: for all 63 offsets, sampled 8×8 blocks are
   DCT-transformed and requantized with the IJG table of each tested
   quality; the offset where most blocks sit on a quantization lattice
   (normalised requantization error < 0.03 instead of 1/12) gets the second
   full recompression pass. This always runs (about 2× the cost).
5. Automatic decision (our addition; Farid inspects the maps by eye). Each
   pass is repeated on a grid shifted by (4, 4) px from it, where an earlier
   quantization no longer lines up (for an offset pass whose (4, 4) partner
   would be the file grid, a 2-px shift is used). For each window,
   `log(d / d_shifted)` is smoothed over 3×3 windows.
   - **Whole image.** A singly-compressed file is already closer to its
     recompression just below its own quality, so the image median of the
     log ratio is compared with the same median on a simulated single save
     (central ≤1024-px crop, taken 4 px off the grid, saved once at the
     final quality). More than 1.0 below it at some q = the whole image was
     saved at about that quality before (info, not a warning).
   - **Local.** Otherwise windows lying 0.7 below the median are ghost
     candidates. The largest connected group, if it covers ≥ 3 % of the
     textured windows, becomes a **warning** with the ghost quality, grid
     offset and location.
6. PNG and other non-JPEG files still run (all qualities tested), since they
   can hold the ghost of an earlier JPEG compression.

### Reading the output
| Item | Meaning |
|---|---|
| Primary quality (from table) | final save quality |
| Tested grid offsets | (0,0) and the off-grid offset chosen in step 4 |
| Ghost quality / Ghost grid offset | quality and grid where a local region shows its earlier compression |
| Whole-image ghost quality | the entire image was probably saved at about this quality (nearest tested step) before |
| Maps | normalised difference at the ghost quality (dark = ghost), quality of minimum difference per window, ghost region overlay; all at block resolution (≤ ~1200 px) |

### Measured (hold-out set)
Thresholds were set on a calibration set (4 skimage photos + 4
camera-pipeline images: Bayer RGGB mosaic, shot + read noise, bilinear
demosaic, optional sharpening; seed 11). The numbers below are from a
different set: the sample image, 4 other skimage photos and 4
camera-pipeline images from other scenes and seeds (9 hosts, seed 222).
Patches are 1/9 of the image, taken from another host compressed at q1,
pasted on an 8-px boundary; "off-grid" means the donor's JPEG grid is
offset by (3,3), (4,4) or (2,5) px from the file grid.

| Case | Result |
|---|---|
| Single JPEG q75/85/92/95 + PNG (45 files) | local warning 1/45 (single q92 sample image, 3.1 % region at q90); false whole-image ghost 0/45 |
| Whole-image double JPEG 60 → 90 | whole-image ghost at q60 in 9/9 |
| Whole-image double JPEG 90 → 95 | whole-image ghost at q90 in 8/9 (previously reported as "about q85") |
| On-grid patch, q60→90, q70→95, q60→85, q80→95 | 33/36 warned |
| Off-grid patch, q60→90, q70→95, q80→95 | 62/81 warned (previously 0/11) |
| Off-grid patch, final q85 (q1 = 60) | 9/27 warned — weak |

Hosts with little texture (immunohistochemistry, the small `coins`
camera image) account for most misses.

12 MP JPEG (4000×3000, q90): about 18 s and ~210 MB peak traced memory
(previously 17.7 s / 975 MB with RGB and one grid).

### Limitations
- Only earlier compressions at a **lower** quality than the final save are
  found; q1 ≥ q2 leaves no ghost, and q1 within about 5 of q2 a weak one.
- Only the single strongest off-grid offset is tested. Several pasted regions
  on different offsets are not all covered, and an off-grid region at a final
  quality near its own (e.g. 60 → 85) is often missed.
- Flat and saturated areas don't change under recompression and are excluded.
- Resizing or filtering after the earlier save removes the ghost.
- The sample image (q95) shows a whole-image ghost at q90 and no local ghost,
  consistent with the Double-JPEG tab's earlier quality ≈ 90.
