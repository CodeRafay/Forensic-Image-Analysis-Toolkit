# Error Level Analysis (ELA)

Method: N. Krawetz, *A Picture's Worth* (Black Hat 2007). Code: `analysis/ela.py`,
entry point `analyze_ela(path, quality=90)`.

## What the code does

1. Decodes the stored pixels (no resizing, no EXIF rotation).
2. Re-saves them once, in memory, as JPEG at `quality` (UI slider, default 90).
3. Error per pixel = max over R, G, B of |original - re-saved| (grey levels).
4. Averages the error over a 16×16 window.
5. **Content normalisation.** Raw error grows with local detail: edges and
   texture always change more on resave than sky. So each window is put into
   one of 16 bins by its local detail (mean |Laplacian| of luma over the same
   16×16 window). Its error is divided by the median error of its bin. A ratio
   of 1 means "as much error as other parts of this image with the same
   amount of detail". The bin median is floored at 1 grey level.
6. Pixels with a ratio above **2** form the mask. A connected region covering
   **≥ 1 % of the image** gives a *notice*. Otherwise the finding says what
   was tested and that no inconsistency was found at this sensitivity.

The metrics, the mask and the red overlay all come from that one ratio map.
The displayed ELA image is the raw error, contrast-stretched for visibility
only.

## Outputs

| Output | Meaning |
|---|---|
| ELA error at qNN | raw per-pixel error, stretched for display |
| Regions above 2x expected error (red) | the mask behind the "Area above" metric |
| Mean / 95th pct error at qNN | raw error, grey levels |
| Median smoothed error | the image's typical error level |
| Area above 2x expected error (%) | share of pixels in the mask (what is drawn red) |
| Max error / expected for its texture | strongest local ratio |

Labels carry the quality actually used (q70, q90, ...).

## How to read it

ELA works on one premise: a region whose compression history differs from
the rest (e.g. a patch from a less-compressed source) changes more on resave
than other areas with similar detail. A red region is such an area. Look at
it: if it follows a kind of content found nowhere else in the image (text,
a sharp graphic), that content can explain it.

## Measured performance (q = 90)

Synthetic camera pipeline: photo → RGGB Bayer mosaic → shot + read noise →
OpenCV demosaic (bilinear / EA / VNG) → optional sharpening → PNG or JPEG.
Thresholds were chosen on 8 photos (plus the reviewer's 48 skimage files).
Numbers below are the **hold-out** set: 7 different photos, different seeds.

| Case (hold-out) | New | Old rule (4× image median) |
|---|---|---|
| Negatives: camera pipeline PNG / q75 / q85 / q92 + plain photos PNG / q70 / q85 / q95 (84) | 0/84 | 0/84 |
| Reviewer's skimage negatives (48, used for calibration) | 0/48 | 9/48 |
| Same-quality resave: clean JPEG q88 / q90, all 15 photos (60) | 1/60 (`retina`, black background) | – |
| Raw camera patch (1/16–1/4 area, other photo) in a q70–90 JPEG, saved PNG | 14/21 | – |
| same, saved q95 | 13/21 | – |
| same, saved q92 | 5/21 | – |
| all three together | 32/63 (51 %) | 31/63 |
| Mixed-history splices (host/donor JPEG history random, final PNG / q75 / q85 / q92) | 6/56 (11 %) | 7/56 |

So detection is about as good as before, and the false alarms on photos with
large smooth areas dropped from 9/48 to 0/48. ELA only sees a pasted region when the
background was JPEG-compressed before and the final save is at a higher
quality (or lossless). In every other case it is weak, which is the method's
nature.

The bundled sample image (`assets/sample images/sampleImg.jpeg`) contains a
pasted object (the disc-shaped "UFO" above the city). ELA marks it (a
notice, a region of about 7 % of the image, on the original JPEG and on a PNG copy), so
the sample is not a clean negative.

12 MP JPEG (4000×3000): about 7 s and 400 MB peak (tracemalloc).

## Limitations

- Error is only compared between windows with similar detail. A region whose
  detail differs in kind (text, sharp graphics, a smooth gradient next to
  foliage) can still stand out on an untouched image.
- Resaving the whole image, or saving the composite at the background's
  quality or lower, equalises error levels.
- A patch that shares the background's compression history and sits on the
  same grid gives no contrast.
- Smooth or dark regions have near-zero error whatever their history. Absence
  of red regions is not evidence of an unedited image.
- On PNG and other lossless files, ELA shows the first JPEG compression, not a
  history. This is reported as an info finding.
