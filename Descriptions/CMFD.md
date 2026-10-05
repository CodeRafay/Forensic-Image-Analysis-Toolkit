# Copy-Move Forgery Detection (CMFD)

## What it looks for

Copy-move forgery means copying part of an image and pasting it somewhere
else in the **same** image, to hide something (paint sky over an object) or
duplicate something (a second crowd, a second cloud). The pasted part may be
rotated, rescaled or mirrored. This tab searches the image for pairs of
regions that are copies of each other under one affine transform (shift +
rotation + scale, optionally mirrored).

It cannot see content pasted from a *different* image (splicing). Use ELA,
JPEG ghost, double-JPEG or noise analysis for that.

## What the code does

The image is decoded without re-encoding and, if its long side exceeds
`max_px` (default 2048), downscaled in memory. The analysed size is shown.

1. **Keypoint branch** (Amerini et al., IEEE TIFS 2011). SIFT keypoints (low
   contrast threshold, up to 20 000, computed at ≤ 1536 px) with RootSIFT
   descriptors are matched against the image itself with the generalised
   2-nearest-neighbour test (ratio 0.5). Descriptors of the **left-right
   flipped** image are matched as well (the MIFT idea, Jaberi et al. 2014), so a
   mirrored copy is matched like a normal one. Pairs closer than 30 px are
   dropped. Matched locations are grouped by Ward clustering and each group
   gets RANSAC affine fits (3 px tolerance, ≥ 4 inliers; a reflection is
   allowed).
2. **Dense branch** (Cozzolino, Poggi & Verdoliva, IEEE TIFS 2015). At
   ≤ 1024 px (and ≤ 0.6 MP), 12 rotation- and mirror-invariant Zernike-moment
   magnitudes (order ≤ 5, 13 px disc) per pixel, projected onto their top
   8 principal axes to save time. PatchMatch finds, for each pixel, its
   most similar pixel at least 30 px away. It uses the paper's first-order
   propagation (a neighbour's offset, and the prediction 2·δ(n′) − δ(n″) so
   rotated and scaled clones, whose offsets change linearly, propagate) and
   random search with the radius halving from the image size down to 1,
   8 iterations. The offset field is median-filtered and a dense linear fit
   is computed in 7×7 windows. Inside a clone the offsets vary smoothly (fit
   error < 1 px²), elsewhere they are random. Flat pixels (local std
   < 2.5 grey levels) are excluded.
3. **Verification** (Amerini et al. 2013, after Pan & Lyu 2010). At analysis
   resolution, each hypothesis warps the image onto itself. Pixels whose 7×7
   ZNCC with their copy is > 0.7 are kept, and so are connected regions
   that touch the hypothesis' own matches and cover ≥ 900 px (or 0.1 % of a
   large image).
4. **Region test** (added here, calibrated on seeded data). A real clone
   differs from its copy only by the resampling the paste implies and by
   JPEG compression applied afterwards. The region's median local |difference|
   must therefore be ≤ 2.0 + 1.5 × *resampling residual* + 0.06 × (100 − JPEG
   quality). The *resampling residual* is measured by warping the region with
   the fitted transform and back. The quality is read from the file's
   quantization table, and is 0 for PNG/TIFF. A near-pure translation is
   rounded to whole pixels first. Natural look-alikes (grass, gravel, text,
   repeated structure) correlate well but differ by more than this. A
   hypothesis found only by the dense branch, with fewer than 4 keypoint
   matches supporting it, also needs ZNCC ≥ 0.85 and ≥ 0.4 grey levels of
   fine detail (noise or texture). Without the detail check, smooth synthetic
   gradients match themselves under many rotations.

A **warning** is only raised when a hypothesis passes steps 3 and 4. Stray
keypoint matches alone produce an `info` line.

## How to read the output

**Image: Duplicated regions.** Green = copy A, red = copy B, yellow lines =
the RANSAC-inlier keypoint matches. The method cannot tell which copy is the
original; the colours only mark the two sides of each match.

**Image: Dense offset-field consistency.** Bright pixels have locally
consistent nearest-neighbour offsets (dense-branch scale). Large bright areas
without a verified clone usually mean repetitive texture or flat areas.

| Metric | Meaning |
| --- | --- |
| Analysed size (px) | Resolution actually analysed (after `max_px`). |
| SIFT keypoints | Keypoints in the original image; very few (< ~200) means the keypoint branch had little to work with. |
| g2NN matches | Self-matches (direct + mirrored) that passed the 0.5 ratio test and the 30 px distance. Not evidence on its own. |
| Verified clones | Hypotheses that passed verification and the region test. |
| Duplicated area (% of image) | Union of both copies of all verified clones. |

**Table: Clone hypotheses**: one row per verified clone, with:

- **branch**: keypoint or dense.
- **RANSAC inliers**: 0 for dense.
- **Centres of both copies**, in original image pixels.
- **Shift B − A**.
- **rotation A->B (deg, CCW +)**, **scale A->B**, **mirrored A->B**: the
  convention is `B = scale · R(rotation) · [mirror left-right] · A`, with the
  rotation counter-clockwise on screen (the OpenCV `getRotationMatrix2D`
  sign). Because A/B is arbitrary, an unmirrored clone rotated +20° and
  scaled 1.05 may be reported as −20° and 0.95. For a mirrored clone, the
  angle is the same in both directions.
- **ZNCC**: median local correlation over the region.
- **mean |diff|**: median local difference in grey levels.
- **resampling |diff|**: the part of that difference the transform alone
  explains.
- **fine detail**.
- **keypoint support**: keypoint inliers consistent with this transform.

A clone with ZNCC near 1 and |diff| near 0 is a pixel-exact copy.

## Measured performance

The thresholds were calibrated on one seeded set. The numbers below come from
**different** photos and seeds (hold-out). "Found" means the predicted mask
overlaps the ground truth with pixel F1 > 0.3 (set A) or a reported clone
centre lies on a ground-truth copy (set B). Hold-out sizes are small (n = 8–18
per cell), so treat each number as ±0.1–0.15.

**Hold-out A**: an independent reviewer's benchmark. 72 clones in
coffee/chelsea/rocket/motorcycle/immunohistochemistry/bundled sample, size
40–128 px, rotation −45..180°, scale 0.8–1.2, 25 % mirrored, PNG or JPEG
q60–95. The previous version is shown for comparison:

| Subset | n | Found (old) | Found (now) | Mean pixel F1 (now) |
| --- | --- | --- | --- | --- |
| 40 px clones | 18 | 0.17 | 0.44 | 0.39 |
| 64 px | 18 | 0.33 | 0.61 | 0.54 |
| 96 px | 18 | 0.50 | 0.72 | 0.61 |
| 128 px | 18 | 0.67 | 0.78 | 0.72 |
| mirrored, ≥ 64 px | 18 | 0.22 | 0.89 | 0.75 |
| not mirrored, ≥ 64 px | 36 | 0.64 | 0.61 | 0.56 |
| JPEG q60–75, ≥ 64 px | 15 | 0.33 | 0.67 | 0.61 |

The one non-mirrored case that dropped is on the bundled sample, which has
real cloned clouds of its own. Those clouds are now also found by the dense
branch, which lowers F1 against the synthetic ground truth. Pure-translation
clones in the smooth sky of `rocket` are missed.

**Hold-out B**: camera-like renders (scene → Bayer RGGB → shot + read noise →
bilinear demosaic → optional sharpening) of coffee, chelsea, rocket,
motorcycle and immunohistochemistry, seed 99. Clones as in set A:

| Subset | n | Found |
| --- | --- | --- |
| 40 px | 15 | 0.40 |
| 64 / 96 / 128 px | 15 each | 0.87 / 0.87 / 0.93 |
| mirrored, ≥ 64 px | 12 | 1.00 |
| JPEG q60–75, ≥ 64 px | 16 | 0.88 |
| clean renders (PNG, JPEG q92/85/75/60) | 25 | **0 false alarms** |
| wrong-place clones in forged images | 60 | 0 |

**Negatives in hold-out A** (the reviewer's sets):

- 6 clean photos × (PNG, q95/85/75/60): no detection except on the bundled
  sample. That image contains genuinely cloned clouds, shifted 317 px and
  90 px with ZNCC ≥ 0.98, and they are reported at every quality.
- Textures and graphics (grass, gravel, brick, checkerboard, horse
  silhouette, colour wheel; PNG and q70): 0 false alarms. Before this change,
  grass, gravel and the colour wheel gave 18.6 %, 2.9 % and 12 %.

With 25–40 negatives per set, a 0 count means a false-alarm rate below
roughly 5–10 %, not zero.

Repeated content **is** reported, because it is repeated: a tiled photo
after JPEG (99 %), a scene made of a photo and its mirror image (86 %),
lines of identical text (36–48 %). Those are duplicates; the method cannot
know they are harmless.

Calibration set (for reference, not a performance claim): camera-pipeline
renders of astronaut/camera/retina/cat with 96 clones gave TPR 0.71. Its
40 clean renders plus brick/moon/coins/Hubble/page gave 0 false alarms.

**Runtime and memory.** For a 12 MP JPEG (4000×3000, analysed at 2048×1536),
the run took 16 s with a peak of 489 MB (tracemalloc) and a 603 MB process
working set. For 0.3–0.7 MP images it takes 5–10 s. The dense PatchMatch
dominates.

## Limitations

- **Small clones are weak**: about half of 40 px clones are missed, and
  more are missed after JPEG. Large photos are analysed at 2048 px, so a
  clone must be ≥ ~60 px *after* that downscale.
- Clones of **flat, featureless areas** (clear sky, plain walls) cannot be
  detected. A copy of nothing looks the same as nothing.
- **Naturally repeated content** that really is near-identical (tiled
  textures, repeated logos, text, symmetric scenes) is reported. Look at every
  hypothesis before drawing a conclusion.
- **Heavy JPEG** (q < 60), blur, added noise or strong rescaling after pasting
  weakens both keypoints and correlation. The region test also assumes the
  file's own JPEG quality: a clone pasted, saved at q60, then re-saved at q95
  is judged against q95 and may be rejected.
- Each clone is modelled as **one affine transform**. Perspective warps,
  non-rigid edits and clones assembled from several pieces may come out as
  several small regions or not at all.
- Copies closer than 30 px to their source are not searched.
- Mask edges are approximate: flat surroundings that also match under the
  same transform get included.

## References

- I. Amerini, L. Ballan, R. Caldelli, A. Del Bimbo, G. Serra, "A SIFT-based
  forensic method for copy-move attack detection and transformation recovery",
  IEEE TIFS 6(3), 2011.
- I. Amerini, L. Ballan, R. Caldelli, A. Del Bimbo, L. Del Tongo, G. Serra,
  "Copy-move forgery detection and localization by means of robust clustering
  with J-Linkage", Signal Processing: Image Communication 28(6), 2013.
- D. Cozzolino, G. Poggi, L. Verdoliva, "Efficient dense-field copy-move
  forgery detection", IEEE TIFS 10(11), 2015.
- M. Jaberi, G. Bebis, M. Hussain, G. Muhammad, "Accurate and robust localization of
  duplicated region in copy-move image forgery" (MIFT), Machine Vision and
  Applications 25, 2014.
- X. Pan, S. Lyu, "Region duplication detection using image feature
  matching", IEEE TIFS 5(4), 2010.
- R. Arandjelović, A. Zisserman, "Three things everyone should know to improve
  object retrieval" (RootSIFT), CVPR 2012.
