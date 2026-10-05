# Metadata & Content Credentials

Code: `analysis/metadata_analysis.py` — entry points `analyze_metadata(path)`
and `read_c2pa(path)`.

## What it does

Reads what the file says about itself and looks for internal
contradictions. It does **not** produce a score or a verdict: metadata is
written by software, is trivially edited or removed, and a clean record says
nothing about the pixels.

Sources read (the file is never re-encoded):

| Source | How |
|---|---|
| EXIF IFD0, Exif IFD, GPS IFD, Interop, IFD1 (thumbnail) | Pillow `getexif()` / `get_ifd()` |
| EXIF thumbnail bytes | piexif |
| XMP packet (JPEG APP1, PNG iTXt, WebP, TIFF tag 700) | parsed with ElementTree; packets containing a DTD/entities are refused |
| PNG tEXt / iTXt / zTXt / eXIf chunks | Pillow `img.text`, `info["exif"]` |
| C2PA manifest store | c2pa-python `Reader`, offline (no remote manifest fetch, no OCSP) |

Pillow's `info` fields such as `jfif`, `dpi`, `progressive` are container
properties, not EXIF, and are not counted as EXIF.

## Checks and how to read them

Levels: **info** = neutral fact, **notice** = weak indicator, **warning** =
inconsistency found.

- **EXIF presence.** JPEG/TIFF without EXIF → notice: stripped by software or
  messaging apps, or never written. Absence is not evidence either way. PNG,
  WebP, GIF without EXIF → info (normal for the format).
- **Software.** EXIF `Software`, `ProcessingSoftware`, XMP `CreatorTool`,
  XMP History `softwareAgent`, PNG `Software` are matched against a list of
  known editors (Photoshop, GIMP, Affinity, Pixelmator, Snapseed, PicsArt,
  Paint.NET, Pixlr, Canva, Luminar, Facetune, Photopea, …) → notice "written
  by image editor". Raw developers (Lightroom, Camera Raw, darktable,
  RawTherapee, Capture One, DxO, …) → notice "processed with raw
  developer/editor" — normal for photographers. Anything else (e.g. phone
  firmware strings) → info. An editor tag says the file was saved by that
  program, not what was changed.
- **Dates.** `DateTime` (last modified), `DateTimeOriginal`,
  `DateTimeDigitized`, with `OffsetTime*` (used when both sides of a
  comparison carry one) and `SubSecTime*`.
  - unparseable, before 1839 or in the future → warning (impossible date);
  - Digitized earlier than Original → warning;
  - Modified earlier than Original → warning;
  - Modified more than 2 s after Original → notice (file written again after
    capture: editing, raw development, re-export).
  Blank or all-zero dates are treated as "not set". A wrong camera clock
  produces the same patterns.
- **EXIF thumbnail.** The embedded IFD1 thumbnail is compared with the main
  image downscaled to the thumbnail size. Both are blurred (σ = 1 px),
  one gain/offset is fitted, and the residual is measured per 8×8
  thumbnail block. Warning "thumbnail differs from main image — image content
  changed after the thumbnail was written" when correlation < 0.90 or the
  worst block's residual is > 9× the median block's. Different aspect ratio →
  notice only (cropping, or cameras that letterbox thumbnails). The figure
  shows thumbnail | downscaled main image | residual.
- **Pixel dimensions.** Image size vs EXIF `PixelXDimension/YDimension`
  (either orientation) → notice when they differ (resized or cropped after the
  EXIF was written).
- **MakerNote.** Absent while `Make` is a maker whose cameras normally write
  one (Canon, Nikon, Sony, Fujifilm, Olympus/OM, Panasonic, Pentax/Ricoh,
  Leica, Apple) → notice: software that rewrites EXIF often drops it.
- **GPS.** Coordinates are reported only when both latitude and longitude are
  present. A GPS block with only a version ID is reported as "no fix", never
  as (0, 0).
- **XMP.** `xmpMM:History` events (action, softwareAgent, when, changed) →
  notice with a table; `photoshop:DocumentAncestors` → notice (content from
  other documents was placed in this one); `xmpMM:DerivedFrom` → info;
  `Iptc4xmpExt:DigitalSourceType` of `trainedAlgorithmicMedia` /
  `compositeWithTrainedAlgorithmicMedia` → warning (declared AI-generated).
- **PNG text.** Keys written by image-generation front ends (`parameters`,
  `prompt`, `workflow`, `Dream`, `sd-metadata`, `invokeai_metadata`, …) →
  warning "likely AI-generated output".
- **C2PA Content Credentials.** Claim generator, signer / issuer, signing
  time, actions, ingredients, validation state and failure codes.
  - hash mismatch codes (e.g. `assertion.dataHash.mismatch`) → warning: the
    file was changed after it was signed;
  - any other failure (except `signingCredential.untrusted`, which is expected
    because no trust list is configured) → warning;
  - otherwise info "signature and hashes intact; signer identity unconfirmed";
  - an action with a `trainedAlgorithmicMedia` digital source type → warning
    (declared AI-generated content).

If no notice or warning is raised, the result says which checks ran and
"no inconsistency found at this sensitivity".

## Output

- **metrics:** format, width/height (px), EXIF tag count, XMP history event
  count, software entry count, C2PA manifest count, and when a thumbnail is
  compared: thumbnail correlation and worst-block residual (× median).
- **tables** (only those with content): Camera, Software, Timestamps, GPS,
  XMP history, PNG text chunks, Full EXIF (stringified, binary values shown
  as `<N bytes>`), C2PA, C2PA actions.
- **images:** thumbnail comparison strip (when an EXIF thumbnail exists).
- **details:** the same data as plain JSON (`exif`, `xmp`, `c2pa`,
  `thumbnail`, `png_text`).

`read_c2pa(path)` returns a plain dict: `present`, `validation_state`,
`valid`, `claim_generator`, `title`, `signer`, `issuer`, `signing_time`,
`actions`, `ai_generated`, `ai_indicators`, `ingredients`, `manifests`,
`failures`, `errors`.

## Measured performance (thumbnail check)

Seeded benchmark, 8 photos (`assets/sample images/sampleImg.jpeg` + 7
scikit-image photos) × 40 trials:

| Case | Flagged |
|---|---|
| Genuine 160-px thumbnail (nearest/bilinear/bicubic/Lanczos/box, thumb q50–95, main re-saved q20–100), n = 320 | 0 % |
| Stale thumbnail, pasted patch 2 % of frame | 98.1 % |
| … 5 % | 99.4 % |
| … 10 % | 98.8 % |
| … 20 % | 99.1 % |

Correlation alone (the previous check) caught only 7–78 % of these. The bundled
sample image carries a real stale thumbnail (the object in the main image is
missing from the thumbnail): correlation 0.953, worst block 11.4× → flagged.
`tests/test_metadata.py` re-runs a 20-case subset (FPR ≤ 5 %, TPR ≥ 90 %).

The other checks are rule-based and have no threshold to calibrate; they are
covered by fixture tests (camera EXIF, Photoshop/Lightroom/firmware Software
tags, stale thumbnail, GPS version only, PNG text chunks, XMP history, date
inconsistencies, time-zone offsets, C2PA present / absent / tampered).

## Limitations

- Metadata can be edited, copied from another file or stripped; an
  inconsistency can have an innocent cause (wrong camera clock, batch tools,
  messaging apps), and consistency proves nothing about the pixels.
- The thumbnail check only works when an editor left the old thumbnail in
  place, and only sees edits large enough to survive downscaling (≈ 2 % of
  the frame and up). Global tone edits are not detected (gain/offset is fitted
  out).
- The editor and maker-note lists are finite; an unknown editor is reported
  as "not a known editor".
- C2PA is validated offline with no trust list: signer identity is never
  confirmed, remote manifests and certificate revocation are not checked. An
  absent manifest is the normal case.
