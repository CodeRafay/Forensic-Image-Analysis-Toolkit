# Technique Descriptions — User Guide

Every analysis tab in the app starts with a collapsed **"How this technique
works"** expander. It renders the matching Markdown file from
[`Descriptions/`](Descriptions/). Each file describes only what the code does:
the published method, what the output means, the measured benchmark numbers
(detection and false-alarm rates on seeded synthetic tests) and the
limitations.

> Every result is an **indicator, not proof**. A clean result means only that
> this test found no inconsistency at its sensitivity. No tab says an image
> is authentic.

## Which file each tab shows

| Tab | Description file |
| --- | ---------------- |
| 🕵️ ELA | [ELA.md](Descriptions/ELA.md) |
| 📋 Metadata (incl. C2PA) | [Metadata.md](Descriptions/Metadata.md) |
| 📊 Histogram | [Histogram.md](Descriptions/Histogram.md) |
| 🌫️ Noise | [Noise_Ghost.md](Descriptions/Noise_Ghost.md) |
| 💾 JPEG (quantization tables, double-JPEG, JPEG ghosts) | [Quantization.md](Descriptions/Quantization.md) (ghosts: [Noise_Ghost.md](Descriptions/Noise_Ghost.md)) |
| 🔄 Copy-Move | [CMFD.md](Descriptions/CMFD.md) |
| 📡 PRNU | [PRNU.md](Descriptions/PRNU.md) |
| 📈 Frequency (spectrum, block grid) | [Frequency.md](Descriptions/Frequency.md) |
| 🔀 Resampling | [Resampling.md](Descriptions/Resampling.md) |
| 🧪 Synthetic traces (Experimental) | [Deepfake.md](Descriptions/Deepfake.md) |
| 🔐 Steganography | [Steganography.md](Descriptions/Steganography.md) |
| 🔑 Hash ledger | [Hash_Verification.md](Descriptions/Hash_Verification.md) |

## Reading results

Each run shows, in order: a one-sentence summary of what was measured,
headline metrics, findings (ℹ️ info, 🔎 notice = weak indicator,
⚠️ warning = inconsistency found), images, expandable tables, the
**Limitations** expander (what the test cannot see) and the raw values.

A useful workflow:

1. Read the description before the first run of a tab.
2. Run the test and read its limitations, not only the findings.
3. Look for agreement between *independent* tests (e.g. a copy-move finding
   plus a noise inconsistency in the same region) and weigh it against what
   you know about the image's origin.
4. Treat the Synthetic-traces tab as a measurement only: it cannot tell
   whether an image is AI-generated, and absence of traces says nothing.

The bundled sample image is a known fabricated example (C2PA declares
`compositeWithTrainedAlgorithmicMedia`, copy-moved clouds, stale EXIF
thumbnail), useful for seeing what findings look like.

## Maintaining the descriptions

- The app loads `Descriptions/<Name>.md` via `describe("<Name>")` in
  `app.py`; a missing file shows "Description file not found".
- When a module's behaviour or thresholds change, update its description and
  the benchmark numbers in the same change (see
  [CONTRIBUTING.md](CONTRIBUTING.md)).
