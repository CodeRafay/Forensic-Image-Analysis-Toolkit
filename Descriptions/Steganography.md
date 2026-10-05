# Steganography (LSB replacement) Analysis

## What it looks for

LSB **replacement** hides a message by overwriting the least significant bit
of pixel values. The module estimates **how much** was hidden (payload in
bits per pixel of a channel, bpp) and flags the image only when that estimate
is larger than what clean photos produce.

It analyses the decoded pixels at full resolution, per channel (R, G, B, or a
single channel for grayscale).

## Methods

| Method | Paper | What it measures |
|---|---|---|
| **Weighted Stego (WS)** | Fridrich & Goljan 2004; Ker & Böhme, *Revisiting weighted stego-image steganalysis*, SPIE 2008 | Predicts each pixel from its 8 neighbours (KB filter), weights smooth areas more (moderated weights 1/(5+σ²)), bias-corrected. Saturated pixels (0/255) and their neighbours are excluded. |
| **Sample Pairs Analysis (SPA)** | Dumitrescu, Wu & Wang, IEEE TSP 2003 | Counts adjacent pixel pairs by difference and "trace" (value with LSB dropped); embedding breaks the natural symmetry between two pair classes, solved as a quadratic in p. |
| **RS analysis** | Fridrich, Goljan & Du, ACM MM&Sec 2001 | 1×4 pixel groups, mask [0,1,1,0], flips F1 / F−1, regular/singular group counts, quadratic in z. Reported for comparison; unstable near 100 % payload. |
| **Pair-of-Values χ²** | Westfeld & Pfitzmann, IH 1999 | Whether the counts of values 2i and 2i+1 have been equalised. Run cumulatively over the raster scan to find **sequential** embedding. |

### Decision statistic

For each channel the score is **min(WS, SPA)**. The two rely on different
cover assumptions (local predictability vs. pair symmetry); a clean texture
can fool one (the `grass` crop reads WS 0.215 but SPA 0.048) but rarely both,
while under real embedding both track the true payload.

**Exception: WS unreliable.** When fewer than half of the pixels keep a WS
weight (saturated 0/255 pixels and their neighbours are excluded), or WS lands
outside [-0.5, 1.5], the score is **SPA alone**. Line art, binary images and
clipped skies break the WS predictor (a review found WS -55 at p = 0 and
-2.5 at p = 0.25 on such a cover while SPA read 0.28), and min(WS, SPA) then
hid real embedding. On skimage `horse` and `checkerboard` the fallback reads
p = 0.10 / 0.25 within 0.05. The per-channel table shows which rule was used.

The image score is the highest channel. It is compared with a single threshold, **0.05 bpp**.

### Sequential embedding

The PoV p-value is computed on the first 1 %, 2 %, …, 100 % of samples in
raster order (channels interleaved, as sequential tools write them). The
extent is the last prefix where p ≥ 0.5. PoV alone is unreliable — smooth
histograms (textures, resized images) keep p high on clean images (it flagged
24 of 53 clean covers) — so a sequential finding also requires the rows in
that prefix to score > 0.5 bpp and at least 0.25 bpp above the rows below.

## How to read the output

- **Payload estimate, highest channel (bpp)** — the decision score. 0.10 means
  roughly 10 % of that channel's samples carry message bits. Small negative
  values are estimator noise on a clean image.
- **Mean WS payload over channels** — overall estimate.
- **Per-channel table** — WS, SPA, RS and PoV p-value for each channel.
  Agreement between WS, SPA and RS strengthens an estimate.
- **PoV p-value**: HIGH (near 1) = pairs equalised = sign of embedding;
  natural images give ≈ 0. (The old UI text had this backwards.)
- **Local WS payload heatmap** (64×64 blocks) — where the payload sits.
  Localisation aid only: on 8 clean photos 6 % of blocks read > 0.2 bpp and
  2.4 % > 0.5 bpp.
- **PoV cumulative p-value curve** — a plateau near 1 followed by a drop
  indicates sequential embedding ending at that point (the drop lags the true
  end: a 30 % sequential embed plateaus to ~36 %).

Findings: *warning* when the score exceeds the threshold or sequential
embedding is confirmed; otherwise *info* stating the estimate, the threshold,
and that smaller payloads and LSB matching cannot be detected.

## Measured performance

**Hold-out (fix round, threshold fixed before this set was run).**
Calibration set: sample + 8 skimage photos + 8 camera-pipeline scenes (Bayer
RGGB mosaic, shot + read noise, OpenCV bilinear demosaic, half sharpened) + 3
of them with clipped highlights/shadows: clean max 0.039 (PNG) / 0.036 (JPEG),
FPR 0/80. Hold-out set: 6 other skimage images (hubble, immunohistochemistry,
retina, colorwheel, cat, logo) + 8 other camera seeds + 3 clipped:

| Hold-out case | n | flagged at 0.05 bpp |
|---|---|---|
| Clean lossless | 18 | 1 (5.6 %, hubble_deep_field 0.052) |
| Clean decoded JPEG q75/85/92 | 54 | 3 (5.6 %, all one camera scene, max 0.078) |
| Random LSB replacement 3 % | 18 | 6 (33 %) |
| 5 % | 18 | 15 (83 %) |
| 10 % | 18 | 18 (100 %) |
| 25 % | 18 | 18 (100 %) |

Mean absolute error of the score: 0.014-0.016 bpp at 3-25 %. The hold-out
false-alarm rate (4/72 = 5.6 %) is above the 3 % target; treat a score of
0.05-0.08 bpp as weak, especially on a decoded JPEG.

Run time at 12 MP (4000x3000 JPEG): 12 s, 366 MB peak (tracemalloc). WS terms
are computed once per channel and reused for the global, prefix and block
estimates; float32 / int16 / uint8 throughout.

Ker's Triples analysis (2005) and the optimally weighted WS (Ker 2007) were
not added; they would mainly help below 5 % payload.

**Earlier calibration (first round).** Seeded benchmark: covers = bundled sample + 14 skimage photos (astronaut,
coffee, chelsea, camera, rocket, immunohistochemistry, hubble_deep_field,
coins, moon, brick, grass, gravel, retina, clock).

**False positives at 0.05 bpp**

| Clean covers | n | FPR | 95th pct | max |
|---|---|---|---|---|
| Lossless (PNG, grayscale, bicubic 0.6×, crops) | 53 | 1.9 % | 0.041 | 0.116 (resized grass) |
| Decoded JPEG q75/85/95/100 | 60 | 3.3 % | 0.024 | 0.067 (grass q100) |

Saturation exclusion in WS brought the lossless 95th percentile from 0.096
to 0.053; using min(WS, SPA) brought it to 0.041.

**Detection (23 lossless covers: PNG + grayscale)**

| Embedding | 5 % | 10 % | 25 % | 50 % | 100 % |
|---|---|---|---|---|---|
| Random LSB replacement, TPR | 70 % | 100 % | 100 % | 100 % | 100 % |
| Sequential LSB replacement, TPR (score or PoV) | 87 % | 100 % | 100 % | 100 % | 100 % |
| LSB matching (±1), TPR | 0 % | 0 % | 0 % | 4 % | 0 % |

**Estimator error (mean absolute error of p̂, bpp)**

| Embedding | payload | WS | SPA | RS (median) |
|---|---|---|---|---|
| Random | 5 % | 0.010 | 0.016 | 0.014 |
| Random | 10 % | 0.013 | 0.016 | 0.013 |
| Random | 25 % | 0.019 | 0.017 | 0.014 |
| Random | 50 % | 0.025 | 0.013 | 0.013 |
| Random | 100 % | 0.011 | 0.019 | 0.091 |
| Sequential | 10 % | 0.035 | 0.029 | 0.022 |
| Sequential | 50 % | 0.113 | 0.117 | 0.085 |

Embedding concentrated in part of the image (sequential, one region) is
estimated less accurately, because the estimators assume the payload is spread
evenly and WS gives smooth regions more weight: a fully embedded quadrant
(25 % of pixels) of the sample reads 0.42 bpp. The detection still fires;
treat the number as an order of magnitude.

`tests/test_steganography_detection.py` re-runs a smaller version (9 covers,
clean PNG + decoded JPEG, 10 % random, 25 % matching) and asserts FPR ≤ 6 %,
TPR ≥ 90 %, MAE < 0.03.

## Limitations

- **LSB matching (±1)** leaves no pair structure; none of these tests
  detect it at any payload (table above). Adaptive spatial schemes (HUGO,
  WOW, S-UNIWARD) are ±1 schemes too and are not modelled (not benchmarked).
- **JPEG files**: JPEG steganography (JSteg, F5, OutGuess, J-UNIWARD) hides
  data in DCT coefficients, which pixel-LSB tests cannot see. Pixel LSB
  replacement does not survive JPEG saving, so on a JPEG this analysis only
  matters if decoded pixels were edited and re-saved losslessly. JPEG input
  still gets a status "ok" result with this caveat as the first finding; the
  clean decoded-JPEG FPR (3.3 %) was measured separately.
- **Small payloads**: below ~0.05 bpp a payload cannot be told apart from the
  estimators' error on clean covers.
- **Unusual covers**: strongly textured or resampled images (the `grass`
  texture) can give estimates up to ~0.12 bpp without any embedding.
- **Palette images** are analysed after conversion to RGB; palette-index
  embedding (EzStego) is not modelled.
- **Only pixel values** are examined. Metadata, appended data and file
  structure cannot change these scores, and are not checked here.
- It estimates the amount of hidden data; it does not extract or decode it.
