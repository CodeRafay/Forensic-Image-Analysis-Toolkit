# Next steps

Handover notes for whoever picks this project up next. Last updated
October 2026, at release v3.0.0.

## Where things stand

- v3.0.0 is released and merged to `main`. The live app
  (https://veritas-forensics.streamlit.app) deploys from `main` on Streamlit
  Cloud.
- Tests: `pip install -r requirements-dev.txt`, then `pytest` (142 tests).
- After changing any detector, run `python scripts/make_examples.py`. It
  rebuilds the example gallery and exits non-zero if a technique stops
  catching its example.
- `CHANGELOG.md` has the full history; each `Descriptions/*.md` file has the
  method, thresholds and measured rates for one technique.

## Unfinished work, most important first

1. **Validate on real datasets.** Every accuracy number so far comes from
   test images generated for this project, so treat them as optimistic.
   - Copy-move: CoMoFoD small set (3.2 GB `.rar`, direct download at
     https://www.vcl.fer.hr/comofod/download.html). Research use only, no
     redistribution, cite Tralic et al., ELMAR 2013. Keep the images outside
     the repo and publish only scores.
   - Splicing (ELA, Noise, Double JPEG, JPEG ghost): CASIA v2, available on
     Kaggle (needs a Kaggle API token).
   - PRNU: Dresden. The official site was down in October 2026; mirrors are
     tens of GB.
   - Columbia's server returned 403 in October 2026.
2. **Document Splicebuster's weakness on real phone photos.** On two real
   outdoor photos from a Motorola phone (Wikimedia Commons, Gerda Arendt,
   CC0), it raised a false alarm on one unedited file and missed every
   planted edit on the other. Add this to the Noise limitations in
   `analysis/noise_map.py` and `Descriptions/Noise_Ghost.md`.
3. **Known weak spots** (already documented): steganography (5.6 %) and
   Splicebuster (5.3 %) false-alarm rates just above the 5 % target; the
   PRNU spliced-region test is blind at realistic fingerprint strength;
   non-aligned double JPEG is weak; resampling cannot see rotation or
   downscaling after JPEG.
4. Smaller ideas: no gallery example yet for Frequency or Synthetic traces.
   Planned features are listed under "Unreleased" in `CHANGELOG.md`.

## Things that will catch you out

- **Python version.** `.python-version` pins 3.10 and `requirements.txt`
  pins exact versions. If Streamlit Cloud drops Python 3.10, the live app
  will stop building; update the pins and re-run the tests and
  `scripts/make_examples.py`.
- **The bundled sample is not a clean photo.** `assets/sample images/sampleImg.jpeg`
  is a known composite (UFO added, clouds cloned), so several tabs report
  findings on it by design.
- **Example photos.** The Noise and PRNU examples use four CC0 iPhone 5c
  photos of watercolour paintings. Credits and original links are in
  `assets/examples/source/CREDITS.md`. Keep them byte-identical: PRNU
  depends on the untouched camera files.
- **Memory limits.** The app caches at most 3 results per session
  (`MAX_CACHED_RESULTS` in `app.py`) to stay within Streamlit Cloud's
  memory. Every entry point is budgeted at 30 s and 800 MB for a 12 MP image.
- **Network.** Some dataset hosts and `commons.wikimedia.org` were blocked
  on the original development network; the Wikipedia API and
  `upload.wikimedia.org` worked as a route to Commons files.
