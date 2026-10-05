# Quantization Tables & Double-JPEG Localization

Two tabs work from the JPEG file's own compression data. Neither can say an
image is genuine; they report what the last encoder was and whether parts of
the image carry a different compression history.

## 1. Quantization table (`analysis/quant_table.py`)

### What the code does
- Reads the DQT tables through Pillow's JPEG decoder (a raw byte search for
  `FFDB` finds fake tables inside scan data and XMP).
- **Estimated quality**: the tables libjpeg builds for q = 1…100
  (`scale = 5000/q` below 50, `200 − 2q` above; `Q = (T50·scale + 50)/100`,
  clipped to 1…255) are compared entry for entry; an exact match gives that
  q (exact for every libjpeg quality; chroma q1–3 share one table, reported
  as 3). Other tables fall back to inverting the scaling with the median
  over non-clipped entries — a rough equivalent only.
- **IJG-standard?** Checks whether the table is one scale factor times the
  ITU-T T.81 Annex K reference table (within integer rounding).
- **Encoder family hint**
  - all tables IJG-scaled → *IJG/libjpeg family*: typical of software saves
    (PIL, OpenCV, GIMP, many web and AI pipelines). Some cameras also use them.
  - any table not IJG-scaled → *custom tables*: typical of camera vendor
    firmware or an editor with its own tables such as Photoshop.
  - all entries 1 (quality ≈ 100) → *cannot classify*: every encoder produces
    this table.
- EXIF Make / Model / Software (Pillow `getexif`) are listed beside the hint
  as context only. EXIF can be edited, and no camera-table database is used,
  so a camera claim can't be confirmed or refuted from the tables.

### Reading the output
| Item | Meaning |
|---|---|
| `Table N estimated quality (IJG)` | IJG quality that produces this table (exact for libjpeg tables). Only an approximate equivalent for custom tables |
| `Table N IJG-standard` | yes/no, see above |
| Tables | the 8×8 tables in raster order (top-left = DC / low frequencies) |

Non-JPEG files return `not_applicable`.

### What it cannot tell you
- Only the **last** save is visible. Earlier saves, edits made before that
  save, and lossless edits don't show up here.
- An IJG table on a file whose EXIF names a camera can mean a later software
  re-save, or a camera that uses IJG tables. It is not proof of editing.

## 2. Double-JPEG localization (`analysis/double_jpeg.py`)

Method: T. Bianchi & A. Piva, *Image Forgery Localization via Block-Grained
Analysis of JPEG Artifacts*, IEEE TIFS 7(3), 2012. Grid search for the
non-aligned case follows Bianchi & Piva, *Detection of Nonaligned Double JPEG
Compression Based on Integer Periodicity Maps*, IEEE TIFS 2012.

### Idea
When a JPEG (first quantization step Q1) is edited and saved again (Q2), the
untouched areas are quantized twice. A pasted region, once decoded onto the
file's grid, is quantized only once. Doubly quantized coefficients cluster
on the Q1 lattice, seen through the Q2 bins; singly quantized (tampered)
blocks follow the smooth single-compression histogram.

### What the code does
1. Decodes the **luminance exactly as stored** (Pillow `draft("YCbCr")`, no
   RGB round trip), takes the 8×8 DCT on the file's grid and divides by the
   stored luminance table Q2 to get the coefficient indices x.
2. Estimates the unquantized coefficient density from the image itself: the
   DCT on a grid shifted by (4, 4) px (calibration).
3. **Full H0 model** (paper's version with the error term): a twice
   compressed coefficient is `Q1·k + e`, e the rounding/truncation error of
   the first decompression (Gaussian, variance s²), then binned by Q2:
   `p(x|H0) = Σ_k P(Q1 cell k) · P(Q2(x−½) ≤ Q1·k + e < Q2(x+½))`.
   H1 is the calibrated density in Q2 bins. The earlier hard model
   (`n(x)`, zero probability off the lattice) scored any odd coefficient of
   a smooth block as "tampered" when Q1 = 2·Q2 (90 → 95) — the source of
   the false regions on unspliced files.
4. **Q1 jointly**: one IJG primary quality (1…100, i.e. a whole luminance
   table) is chosen by maximum likelihood over the first 9 AC frequencies
   together, then s² from {0.1, 0.2, 0.35, 0.6, 1.0}. Per frequency the
   mixture weight is fitted by EM; frequencies where Q1 divides Q2 are
   skipped. A frequency counts when the model gains ≥ 0.05 log-likelihood
   per coefficient. Neighbouring qualities can share these 9 entries, so the
   reported earlier quality can be off by 1 (75 → reported 74).
5. Fit and per-block score use **non-zero** coefficients only, and only
   blocks with **≥ 4 non-zero AC coefficients** vote (flat blocks carry no
   lattice evidence). Per block `log L = Σ_f log(p1/p0)`, 5×5-block median
   filter, `p = sigmoid(log L)`.
6. **Non-aligned case** (cropped or shifted between saves). Integer
   periodicity `|E exp(2πi·y/Q)|` of the DCT coefficients is measured on all
   49 grid shifts with dy, dx ≠ 0. If the best shift's robust z ≥ 8, H0 is a
   Q1 lattice plus Gaussian noise of the second compression and H1 the
   calibrated density at that shift.

### Reading the output
| Metric | Meaning |
|---|---|
| Model | `aligned`, `non-aligned` (with primary grid shift), or `none` |
| Estimated primary quality (IJG) | earlier save quality (aligned model) |
| Frequencies with double-JPEG evidence | out of 9; the table gives Q2, Q1, mixture weight, gain |
| Blocks with p(tampered)>0.5 | share of voting blocks |
| Largest inconsistent region | largest connected p > 0.5 region, share of all blocks |

- **warning**: a connected region ≥ 4.5 % of the blocks doesn't follow the
  double-compression pattern, and ≥ 6/9 frequencies carry the trace.
- **notice**: evidence in only 1–5 frequencies — a weak double compression
  or a chance fit on a singly compressed file. No map-based finding.
- **info / none**: no double-compression trace (singly compressed, or the
  blind spot below).

### Measured (hold-out set)
Thresholds were set on a calibration set (4 skimage photos + 4
camera-pipeline images: Bayer RGGB mosaic, shot + read noise, bilinear
demosaic, optional sharpening; seed 11). Numbers below are from a different
set: the sample image, 4 other skimage photos and 4 camera-pipeline images
of other scenes/seeds (9 hosts). Splices are 1/9 of the area, pasted from an
uncompressed other host.

| Case | Result |
|---|---|
| Single JPEG q75/85/92 (27) | 0 warnings, 0 frequencies with evidence |
| Aligned double JPEG, no splice: 70→90, 85→95, **90→95**, **80→85**, 60→75, 75→92 (54) | 0 warnings (largest region 1.2 %; review had 2/11, 2/11, 5/11, 5/11 on four of these) |
| Splice, aligned, 65→90 / 75→95 / 90→95 / 80→85 / 60→80 (45) | 40/45 warned (80→85: 6/9), median block IoU 0.84 |
| Crop (r, c ≥ 1) between saves + splice, 70→90 (9) | 5/9 warned, median IoU 0.39 — weak |
| Same crop, no splice (9) | 1/9 warned (12.9 % region) |

The sample image host is the main miss: its splices reach only 3–5 %
regions (IoU ≈ 0.3). On the calibration set the largest unspliced region was
3.9 % (90 → 95).

12 MP JPEG (4000×3000, 70 → 90 with splice): about 10 s, ~240 MB peak traced
memory. The quantization-table tab takes 0.1 s.

### The bundled sample image
`sampleImg.jpeg` (darktable export, q95) shows a trace in 9/9 frequencies
with earlier quality ≈ 90. The map marks the composited saucer and the area
under it, but **also** sky and dark-corner regions of similar size; the
largest region reported in the warning (11.4 %, top-left sky) is not the
saucer. At this q90 → 95 setting, unspliced files gave 0/9 hold-out (max
1.2 %) and 0/8 calibration (max 3.9 %) false warnings, so an 11 % region is
unusual — but the map does not single out the saucer and should not be read
as locating it.

### Limitations
- **Blind spot**: earlier quality ≥ final quality (Q1 ≤ Q2). Q1 = Q2, or Q1
  dividing Q2, leaves no trace by construction; other Q1 < Q2 leave a weak
  trace this model does not use (95 → 75, 90 → 70: no trace found). Close
  qualities (80 → 85) give a weak, partial map.
- The primary table is assumed IJG-scaled; camera vendor tables are matched
  to the nearest IJG quality, which can lose frequencies.
- A region pasted from another JPEG with the same grid and quality looks
  untouched.
- Flat or saturated areas carry no evidence and don't vote.
- Resizing, rotation or strong filtering after the first save erases the
  trace.
- Non-aligned localization is weak (median IoU 0.39) and has false regions;
  crops that keep one grid axis aligned aren't searched.
- Resolution is one 8×8 block; regions under about 5×5 blocks are removed by
  the median filter.
