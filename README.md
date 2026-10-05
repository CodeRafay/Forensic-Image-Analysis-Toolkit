# 🔍 Veritas - Forensic Image Analysis Toolkit

[![Python 3.10](https://img.shields.io/badge/python-3.10-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/streamlit-1.64-red.svg)](https://streamlit.io)

**Veritas** is a Streamlit web app that runs published image-forensics
techniques on a JPEG or PNG and reports what each one measured: headline
numbers, findings, maps and each test's stated limitations.

> ### ⚠️ Indicators, not proof
>
> Every result is an **indicator, not proof**. Each test detects one kind of
> trace under stated conditions; a clean result means only that *this* test
> found no inconsistency at its sensitivity. Veritas produces **no
> authenticity score and no overall verdict**: no combination of these tests
> can certify that an image is unedited. Its output is not evidence of
> authenticity and the hash ledger is not a legal chain of custody. Combine
> several independent tests with the image's context before drawing
> conclusions.

> ### Classical methods only
>
> Veritas deliberately uses classical (non-learned) methods so it runs on
> CPU within Streamlit Community Cloud's memory limits and ships under a
> permissive licence. Trained networks such as TruFor / Noiseprint++
> (Guillaro et al., CVPR 2023), CAT-Net (Kwon et al., IJCV 2022) and
> CLIP-based synthetic-image detectors (Cozzolino et al., CVPR-W 2024)
> currently outperform these methods, especially after recompression and
> for AI-generated images. They need GPUs or several GB of RAM and their
> weights are mostly licensed for research use only. For high-stakes
> casework, use them alongside — or instead of — this tool.

## 🎯 Techniques

The app has 13 tabs. Each technique implements a published method; its
guide in [`Descriptions/`](Descriptions/) (also shown in the app under "How
this technique works") gives the method, the measured benchmark numbers and
the limitations.

| Tab | Technique | Published method | Guide |
| --- | --------- | ---------------- | ----- |
| ELA | Error Level Analysis | Krawetz 2007; error normalised by local texture energy | [ELA.md](Descriptions/ELA.md) |
| Metadata | EXIF / XMP / PNG text consistency, C2PA Content Credentials | CIPA Exif 2.32, Adobe XMP, C2PA 2.x (`c2pa-python`); Kee, Johnson & Farid 2011 | [Metadata.md](Descriptions/Metadata.md) |
| Histogram | Contrast-enhancement fingerprint | Stamm & Liu 2010 (histogram-DFT HF energy) | [Histogram.md](Descriptions/Histogram.md) |
| Noise | Noise-residual consistency | Splicebuster (Cozzolino, Poggi & Verdoliva 2015): residual co-occurrence features + EM | [Noise_Ghost.md](Descriptions/Noise_Ghost.md) |
| JPEG | Quantization tables | IJG quality estimate and standard-table test (Farid 2006, Kornblum 2008) | [Quantization.md](Descriptions/Quantization.md) |
| JPEG | Double-JPEG localization | Bianchi & Piva 2012 (aligned and non-aligned) | [Quantization.md](Descriptions/Quantization.md) |
| JPEG | JPEG ghosts | Farid 2009, including recompression at an off-grid offset | [Noise_Ghost.md](Descriptions/Noise_Ghost.md) |
| Copy-Move | Copy-move forgery detection | flip-aware SIFT/g2NN + RANSAC affine (Amerini et al. 2011) and dense Zernike/PatchMatch (Cozzolino, Poggi & Verdoliva 2015), ZNCC verification | [CMFD.md](Descriptions/CMFD.md) |
| PRNU | Sensor fingerprint | Lukáš/Fridrich/Goljan 2006, Goljan et al. 2009 (PCE > 60), Chierchia et al. 2014 (correlation predictor + MRF splice localisation) | [PRNU.md](Descriptions/PRNU.md) |
| Frequency | Power spectrum | Radial 1/f² slope and HF share (Field 1987; Torralba & Oliva 2003) | [Frequency.md](Descriptions/Frequency.md) |
| Frequency | JPEG block grid | Block artifact grid (Li, Yuan & Yu 2009): grid origin and misaligned regions | [Frequency.md](Descriptions/Frequency.md) |
| Resampling | Rescaling / rotation | Kirchner 2008 p-map spectrum with JPEG/Nyquist notching (Kirchner & Gloe 2009) fused with a derivative-projection detector (Gallagher 2005; Mahdian & Saic 2008), windowed localisation, NN duplication test | [Resampling.md](Descriptions/Resampling.md) |
| Synthetic traces | **Experimental**: periodic noise-residual peaks | Corvi et al. 2023; Durall et al. 2020. Measurements only, **no AI-image verdict** | [Deepfake.md](Descriptions/Deepfake.md) |
| Steganography | LSB-replacement payload | Weighted Stego (Ker & Böhme 2008), SPA (Dumitrescu 2003), RS (Fridrich 2001), PoV chi² (Westfeld & Pfitzmann 1999) | [Steganography.md](Descriptions/Steganography.md) |
| Hash ledger | File / pixel identity and visual similarity | SHA-256, pixel SHA-256, pHash/dHash/aHash; hash-chained per-session ledger, HMAC-signed export | [Hash_Verification.md](Descriptions/Hash_Verification.md) |
| About | What the app does and does not claim | | |

The synthetic-traces tab cannot tell whether an image is AI-generated:
modern diffusion models, resizing and recompression remove the traces it
measures, and their absence says nothing.

## How the app treats images

- **Original bytes only.** Every technique reads the uploaded file as stored.
  Nothing is downscaled and re-saved before analysis (re-encoding destroys
  compression, noise, resampling and LSB traces).
- **Copy-move** runs on an in-memory downscale to 2048 px on the long side for
  very large images and reports the analysed size. **PRNU** analyses up to 4096 px per
  side, centre-cropping larger images (never resizing); references are
  cropped identically.
- **Per-session storage.** Uploads go to a temporary directory private to the
  browser session, under random file names, so two visitors never see each
  other's files. The hash ledger also lives only in the session; export it to
  keep it.
- **One result format.** Every analysis returns the same result dictionary
  (status, summary, findings, metrics, images, tables, limitations), rendered
  by one function in `app.py`. See [docs/API.md](docs/API.md).

## Bundled sample image

`assets/sample images/sampleImg.jpeg` is loaded when nothing is uploaded. It
is a **known fabricated example**, not a clean reference: its C2PA manifest
declares `compositeWithTrainedAlgorithmicMedia`, the clouds are copy-moved,
and its EXIF thumbnail no longer matches the image. That makes it a good demo
(Metadata, Copy-Move and several JPEG tabs report findings), but do not use
it to judge what a clean photo looks like.

## Example gallery

`assets/examples/` holds nine images, each with one known edit or property
that a technique detects: a recompressed patch (ELA), a JPEG ghost, a cloned
block (Copy-Move), a 1.5x upscale (Resampling), a contrast stretch
(Histogram), an LSB payload (Steganography), contradictory EXIF (Metadata),
a smoothed region (Noise) and a camera match (PRNU). Pick one in the
sidebar's "Or try an example" box; the app says what was done and which tab
detects it, and the PRNU example loads its reference photos itself.

The first seven are edits of the bundled sample. Noise and PRNU need real
full-resolution camera noise, so they use four CC0 iPhone 5c photos from
Wikimedia Commons (credits in `assets/examples/source/CREDITS.md`).
`python scripts/make_examples.py` rebuilds everything and exits non-zero if a
technique stops catching its example.

## 📋 Requirements

- Python 3.10 (pinned in `.python-version`; `requirements.txt` pins the
  versions the tests were run against)
- A modern browser

## 🚀 Quick start

```bash
git clone https://github.com/CodeRafay/Forensic-Image-Analysis-Toolkit.git
cd Forensic-Image-Analysis-Toolkit

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

The app opens at `http://localhost:8501`.

### Tests

The suite uses the standard-library `unittest` runner and needs nothing beyond
`requirements.txt`:

```bash
python -m unittest discover -s tests -t .
```

142 tests: one `tests/test_<module>.py` per analysis module (seeded synthetic
benchmarks that pin detection and false-alarm rates) plus
`tests/test_contract.py`, which runs every entry point on JPEG, PNG,
grayscale, RGBA, palette, 16×16, 1×1 and flat images and checks the result
contract. A full run takes a few minutes.

## 📁 Project structure

```
Forensic-Image-Analysis-Toolkit/
├── app.py                          # Streamlit app: 13 tabs, one shared renderer
├── requirements.txt                # Pinned runtime dependencies
├── requirements-dev.txt            # Optional linters/tools (not needed for tests)
├── .python-version                 # 3.10 (Streamlit Cloud / pyenv)
├── README.md  CHANGELOG.md  CONTRIBUTING.md  LICENSE
├── projectSetup.md                 # Setup notes
├── TECHNIQUE_DESCRIPTIONS_USER_GUIDE.md
├── pytest.ini                      # Optional; pytest is not required
├── .pre-commit-config.yaml
├── .streamlit/config.toml          # Theme, headless server, showErrorDetails="type"
│
├── analysis/
│   ├── __init__.py                 # Lazy sub-module imports
│   ├── util.py                     # Result contract, decoding, JPEG grid (BAG) helpers
│   ├── ela.py                      # analyze_ela
│   ├── metadata_analysis.py        # analyze_metadata, read_c2pa
│   ├── histogram_analysis.py       # analyze_histogram
│   ├── noise_map.py                # analyze_noise
│   ├── quant_table.py              # analyze_quantization_table
│   ├── double_jpeg.py              # analyze_double_jpeg
│   ├── jpeg_ghost.py               # analyze_jpeg_ghost
│   ├── cmfd.py                     # detect_copy_move
│   ├── prnu.py                     # analyze_prnu
│   ├── frequency_analysis.py       # analyze_spectrum, analyze_blocking
│   ├── resampling_detector.py      # detect_resampling
│   ├── deepfake_detector.py        # analyze_synthetic_traces (Experimental)
│   ├── steganography_detection.py  # analyze_lsb
│   └── hash_verification.py        # hashes + per-session ledger
│
├── Descriptions/                   # In-app technique guides (one per tab)
│   ├── ELA.md  Metadata.md  Histogram.md  Noise_Ghost.md  Quantization.md
│   ├── CMFD.md  PRNU.md  Frequency.md  Resampling.md  Deepfake.md
│   └── Steganography.md  Hash_Verification.md
│
├── docs/
│   ├── API.md                      # Result contract and every entry point
│   ├── DEPLOYMENT.md
│   ├── Documentation.md            # Project report with UML diagrams
│   ├── PROJECT_SUMMARY.md
│   └── TECHNIQUES.md
│
├── tests/                          # 142 tests
│   ├── test_contract.py            # Every entry point x every input format
│   ├── test_ela.py  test_metadata.py  test_histogram_analysis.py
│   ├── test_noise_map.py  test_quant_table.py  test_double_jpeg.py
│   ├── test_jpeg_ghost.py  test_cmfd.py  test_prnu.py
│   ├── test_frequency_analysis.py  test_resampling_detector.py
│   ├── test_deepfake_detector.py  test_steganography_detection.py
│   └── test_hash_verification.py
│
└── assets/
    ├── style.css
    ├── sample images/sampleImg.jpeg  # Fabricated demo image (see above)
    └── examples/                     # One known edit per technique (see above)
```

## 🌐 Deployment

Streamlit Community Cloud:

1. Push to GitHub, create a new app at [share.streamlit.io](https://share.streamlit.io), main file `app.py`.
2. Python 3.10 is selected from `.python-version`; dependencies install from the pinned `requirements.txt` (no system packages needed: `opencv-python-headless` and `c2pa-python` ship wheels).
3. Optional: add `LEDGER_KEY = "<random secret>"` under App settings → Secrets. Ledger exports are then signed with HMAC-SHA256 and imports verify the signature; without it exports carry a plain SHA-256 digest that only detects accidental change.

The ledger is per session: it is not shared between visitors and is lost when
the session ends unless exported. Docker and other hosts: see
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). New techniques must return the result
contract, be added to `tests/test_contract.py`, and have their thresholds
calibrated on a seeded benchmark.

## 📝 License

BSD 3-Clause, see [LICENSE](LICENSE).

## 📧 Contact

- **Author**: CodeRafay ([@CodeRafay](https://github.com/CodeRafay))
- **Repository**: [Forensic-Image-Analysis-Toolkit](https://github.com/CodeRafay/Forensic-Image-Analysis-Toolkit)
