# 🔍 Veritas — Development & Setup Notes

Short setup guide. For the feature overview see [README.md](README.md); for
module APIs see [docs/API.md](docs/API.md).

## 1. Environment

Python 3.10 (pinned in `.python-version`).

```bash
git clone https://github.com/CodeRafay/Forensic-Image-Analysis-Toolkit.git
cd Forensic-Image-Analysis-Toolkit

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

`requirements.txt` pins the versions the tests were run against: streamlit,
numpy, scipy, scikit-image, opencv-python-headless, Pillow, PyWavelets,
matplotlib, piexif, ImageHash, c2pa-python. `requirements-dev.txt` holds
optional linters and is not needed to run the app or the tests.

## 2. Layout

```
app.py               Streamlit UI: sidebar upload, 13 tabs, one render() for all results
analysis/            One module per technique; util.py holds the result contract
Descriptions/        Per-technique guides shown in each tab
tests/               test_<module>.py per module + test_contract.py (142 tests)
assets/              style.css, sample images/sampleImg.jpeg (fabricated demo image)
.streamlit/          config.toml (dark theme, headless, showErrorDetails="type")
docs/                API, deployment, project report
```

## 3. How `app.py` works

- **Uploads** are written to a per-session temporary directory
  (`tempfile.mkdtemp(prefix="veritas_")`) under a random file name. The
  previous upload is deleted when a new one arrives; results are cleared when
  the image changes (tracked by SHA-256 of the upload).
- **No preprocessing.** Every tab receives the path of the original file.
  Nothing is downscaled or re-saved first. `cmfd.detect_copy_move` downscales
  in memory to 2048 px (`HEAVY_MAX_PX`); `prnu.analyze_prnu` centre-crops.
- **One renderer.** `run_panel(key, label, fn, *args, **kwargs)` draws a
  button, calls the analysis, caches the result in `st.session_state.results`
  and passes it to `render(result)`. A module exception becomes an `error`
  result instead of crashing the page.
- **Disclaimer.** An "indicators, not proof" notice sits under the title; the
  Synthetic-traces tab carries an additional Experimental warning.
- **Hash ledger** lives in `st.session_state.ledger`; exports are signed with
  HMAC-SHA256 when `st.secrets["LEDGER_KEY"]` exists.

## 4. Run

```bash
streamlit run app.py                                  # http://localhost:8501
python -m unittest discover -s tests -t .             # full suite, a few minutes
```

## 5. Deploy

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) (Streamlit Community Cloud,
Docker).
