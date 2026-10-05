# Forensic Techniques — Overview

One paragraph per technique with a link to its full guide in
[`Descriptions/`](../Descriptions/). The guides are the reference: they state
the method, how to read the output, the measured benchmark numbers and the
limitations. Function signatures and returned keys are in [API.md](API.md).

> Every technique is an **indicator, not proof**. Each detects one kind of
> trace under stated conditions; "no inconsistency found" means only that
> this test, at its sensitivity, saw nothing. No technique here, alone or
> combined, certifies an image as unedited.

---

## Error Level Analysis — [ELA.md](../Descriptions/ELA.md)

Krawetz 2007. The image is re-saved once as JPEG and the per-pixel change is
measured (max over RGB, 16-px windows). Regions with a different compression
history change more or less than the rest. "High error" is relative to the
image's own median, so the result does not depend on brightness or the chosen
quality. Strong edges and texture also raise error; ELA is a screening tool.

## Metadata & C2PA — [Metadata.md](../Descriptions/Metadata.md)

Reads true EXIF, XMP, PNG text chunks and C2PA Content Credentials and
reports internal inconsistencies: editor tags, date disagreements, an EXIF
thumbnail that no longer matches the image, XMP edit history, AI-generation
declarations in C2PA. Metadata is trivially stripped or forged, so it can
raise questions and never settles them. A valid C2PA manifest is the only
cryptographic provenance signal the app reads.

## Histogram — [Histogram.md](../Descriptions/Histogram.md)

Stamm & Liu 2010. Contrast enhancement (gamma, stretch, equalisation) leaves
periodic peaks and gaps in the 8-bit histogram, measured as high-frequency
energy of the histogram's DFT. Clipping is reported as information only.

## Noise consistency & JPEG ghosts — [Noise_Ghost.md](../Descriptions/Noise_Ghost.md)

Noise: Splicebuster (Cozzolino, Poggi & Verdoliva 2015) — co-occurrence
features of a quantised high-pass residual, PCA, and a two-class EM; one
compact minority region with a high likelihood ratio is reported. JPEG ghosts: Farid 2009;
recompressing at a range of qualities reveals regions that were earlier
compressed at a lower quality than the rest.

## Quantization tables & double-JPEG — [Quantization.md](../Descriptions/Quantization.md)

The stored quantization tables identify the encoder family that saved the
file last (IJG/libjpeg-scaled or custom) and its quality; this says nothing
about pixel edits. Double-JPEG localization (Bianchi & Piva 2012) maps, per
8×8 block, whether the coefficients follow a double-compression model;
regions that do not (e.g. pasted content) are reported.

## Copy-move — [CMFD.md](../Descriptions/CMFD.md)

Finds regions duplicated within the same image, with any shift, rotation and
scale: SIFT keypoints with g2NN matching and RANSAC affine fits (Amerini et
al. 2011), a dense Zernike-moment PatchMatch field for low-texture clones
(Cozzolino, Poggi & Verdoliva 2015), and ZNCC verification of every
hypothesis. Naturally repeated, pixel-identical content (tileable textures,
repeated logos) is reported too; flat, featureless clones cannot be found.

## PRNU sensor fingerprint — [PRNU.md](../Descriptions/PRNU.md)

Given reference images from a candidate camera (same pixel size), estimates
the sensor's photo-response non-uniformity and tests the image by NCC and
PCE (decision PCE > 60, Goljan et al. 2009). With ≥ 2 references, a local
block test (Chen et al. 2008 correlation predictor) marks regions that lack
the fingerprint. Without references only the noise residual is shown.

## Frequency — [Frequency.md](../Descriptions/Frequency.md)

Power spectrum: the radial log-log slope (natural images ≈ 1/f²) and the
share of power above half-Nyquist, as measurements. Block grid: the JPEG
block artifact grid (Li, Yuan & Yu 2009) gives the grid origin (a non-zero
origin means cropping after compression) and windows whose grid disagrees
with the global one.

## Resampling — [Resampling.md](../Descriptions/Resampling.md)

Kirchner 2008: interpolation makes a fixed linear predictor's residual
periodic; the spectrum of its p-map shows peaks. JPEG lattice peaks are
masked first (Kirchner & Gloe 2009). A window heatmap localises resampled
regions, and an exact row/column duplication test catches nearest-neighbour
enlargement. Strong downscaling and heavy JPEG after resizing are largely
undetectable.

## Synthetic-image traces (Experimental) — [Deepfake.md](../Descriptions/Deepfake.md)

Measures periodic peaks in the noise-residual spectrum and autocorrelation
(Corvi et al. 2023) and the azimuthal spectrum (Durall et al. 2020). **There
is no AI-image verdict.** Modern diffusion models, resizing and
recompression remove these traces; their absence says nothing, and
resampling, demosaicing, sharpening and periodic texture also create peaks.

## Steganography (LSB replacement) — [Steganography.md](../Descriptions/Steganography.md)

Estimates the LSB-replacement payload per channel with Weighted Stego (Ker &
Böhme 2008), Sample Pairs (Dumitrescu 2003) and RS analysis, plus a
Pair-of-Values chi² curve for sequential embedding. LSB matching and all
JPEG-domain stego (JSteg, F5, OutGuess, J-UNIWARD) are invisible to these
tests.

## Hash ledger — [Hash_Verification.md](../Descriptions/Hash_Verification.md)

SHA-256 of the file bytes is the only identity test; a pixel SHA-256 survives
metadata-only changes; pHash/dHash/aHash report visual similarity and cannot
distinguish local edits from recompression. Records are hash-chained in a
per-session ledger; exports can be HMAC-signed. It is not a trusted
timestamp or a legal chain of custody.

---

## Combining techniques

- Prefer agreement between **independent** traces (e.g. copy-move + noise
  outlier + double-JPEG region at the same place) over any single finding.
- Read each tab's **Limitations**: many techniques are blind after resizing,
  strong recompression or format conversion, which social-media uploads apply.
- Record what was run and what each test reported, including clean results
  and the stated limitations; do not summarise them as a score.
- Context (source, capture circumstances, other copies of the image) usually
  matters more than any pixel statistic.

## Further reading

- H. Farid, *Photo Forensics*, MIT Press, 2016.
- M. C. Stamm, M. Wu, K. J. R. Liu, "Information forensics: an overview of the
  first decade", IEEE Access 1, 2013.
- L. Verdoliva, "Media forensics and deepfakes: an overview", IEEE JSTSP
  14(5), 2020.
- Per-technique papers are cited in each `Descriptions/*.md` and module
  docstring.
