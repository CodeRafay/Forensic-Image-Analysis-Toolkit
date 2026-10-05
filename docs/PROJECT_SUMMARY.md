# Veritas — Project Summary

**Version**: 3.0.0 (2026-09-29) · see [CHANGELOG.md](../CHANGELOG.md)

## What it is

A Streamlit web app that runs published image-forensics techniques on one
JPEG or PNG and shows what each measured. It is a teaching and screening
tool. Every result is an **indicator, not proof**; there is no authenticity
score, no overall verdict, and the hash ledger is not a legal chain of
custody.

## Scope

13 tabs, 14 analysis entry points plus the hash ledger:

| Area | Modules | Methods |
| ---- | ------- | ------- |
| Compression | `ela`, `quant_table`, `double_jpeg`, `jpeg_ghost`, `frequency_analysis.analyze_blocking` | Krawetz 2007; IJG tables; Bianchi & Piva 2012; Farid 2009; Li, Yuan & Yu 2009 |
| Metadata / provenance | `metadata_analysis` (EXIF, XMP, PNG text, C2PA), `hash_verification` | CIPA Exif 2.32, C2PA 2.x; SHA-256, perceptual hashes |
| Pixel statistics | `histogram_analysis`, `noise_map`, `frequency_analysis.analyze_spectrum` | Stamm & Liu 2010; Splicebuster (Cozzolino et al. 2015); radial 1/f² spectrum |
| Geometry | `cmfd`, `resampling_detector` | Amerini et al. 2011 + Cozzolino et al. 2015; Kirchner 2008 / Kirchner & Gloe 2009 |
| Source | `prnu` | Lukáš et al. 2006, Chen et al. 2008, Goljan et al. 2009 (PCE) |
| Hidden data | `steganography_detection` | Weighted Stego, SPA, RS, PoV chi² |
| Experimental | `deepfake_detector` (synthetic traces) | Corvi et al. 2023, Durall et al. 2020 — measurements only |

Full per-technique documentation with measured benchmark numbers:
[`Descriptions/`](../Descriptions/). API: [API.md](API.md).

## Architecture

- **`app.py`** — sidebar upload (or the bundled sample), per-session temp
  directory, 13 tabs, one `render(result)` for every analysis, `run_panel`
  caching results per image, in-app "indicators, not proof" disclaimer.
- **`analysis/util.py`** — the result contract (`make_result`), decoding
  without re-encoding (`load_array`), display helpers, JPEG block-grid
  helpers shared by several modules.
- **`analysis/<module>.py`** — one pure function per technique, path in,
  result dict out, images returned as arrays, never raises.
- **`Descriptions/*.md`** — the in-app guide for each tab.

Design decisions:

1. **Original bytes only.** No tab gets a re-saved or resized copy; the old
   JPEG q95 re-save of large images destroyed the evidence the compression
   tabs look for. Copy-move downscales in memory (2048 px); PRNU and the
   spectrum tabs crop instead of resizing.
2. **One result contract** so the UI cannot read keys a module does not
   return (the cause of several broken tabs before 3.0.0).
3. **Calibrated thresholds.** Every decision constant was set on a seeded
   synthetic benchmark to a stated false-alarm rate; the numbers are in the
   module comments and the Descriptions.
4. **Per-session state.** Uploads and the ledger are private to a browser
   session; exports are HMAC-signed when a server key is configured.

## Testing

142 tests (`python -m unittest discover -s tests -t .`): a
`tests/test_<module>.py` per module with seeded benchmarks asserting
detection and false-alarm rates, and `tests/test_contract.py` running every
entry point on nine input kinds (JPEG, PNG, grayscale, RGBA, palette, tiny,
1×1, flat) and rejecting overclaiming wording.

## Deployment

Streamlit Community Cloud (Python 3.10 via `.python-version`, pinned
`requirements.txt`, optional `LEDGER_KEY` secret) or Docker. See
[DEPLOYMENT.md](DEPLOYMENT.md).

## Known limitations

- Each technique's blind spots are listed in its Description and in the
  app's Limitations expander. Common to most: resizing, strong
  recompression and format conversion (as done by social-media uploads)
  remove the traces.
- The synthetic-traces tab cannot identify AI-generated images.
- Benchmarks are synthetic and seeded; no public-dataset evaluation
  (CoMoFoD, CASIA, RAISE, Dresden) is included.
- The bundled sample image is a fabricated demo, not a clean reference.

## Roadmap

- Report export (PDF/HTML) listing every test run, its findings and its
  limitations.
- Optional evaluation on public forensic datasets.
- Trusted timestamping (RFC 3161) for ledger exports.
