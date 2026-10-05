# Deployment Guide — Veritas

Veritas is a single Streamlit app (`app.py`) with no database and no external
services. Everything a visitor does (uploads, results, hash ledger) lives in
their Streamlit session.

---

## Local

Python 3.10 (see `.python-version`).

```bash
git clone https://github.com/CodeRafay/Forensic-Image-Analysis-Toolkit.git
cd Forensic-Image-Analysis-Toolkit
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS/Linux
pip install -r requirements.txt
streamlit run app.py            # http://localhost:8501
```

Check the install with `python -m unittest discover -s tests -t .` (142 tests).

---

## Streamlit Community Cloud

1. Push the repository to GitHub.
2. At [share.streamlit.io](https://share.streamlit.io): **New app** → repository,
   branch, main file `app.py` → **Deploy**.
3. Python 3.10 is taken from `.python-version`. Dependencies install from the
   pinned `requirements.txt`; no `packages.txt` is needed
   (`opencv-python-headless`, `c2pa-python` and the rest ship wheels).
4. **Optional secret** — App settings → Secrets:

   ```toml
   LEDGER_KEY = "a long random string"
   ```

   With it, ledger exports are signed with HMAC-SHA256 and imports verify the
   signature. Without it, exports carry a plain SHA-256 digest labelled
   "detects accidental change only". Rotating the key invalidates old
   signatures. Locally, the same key goes in `.streamlit/secrets.toml`
   (gitignored).

Notes:

- **The ledger is per session.** It is not shared between visitors and is
  lost when the session ends unless the visitor exports it.
- Uploads go to a per-session directory under the system temp dir with random
  names; nothing is shared between sessions. The container's temp storage is
  discarded on restart.
- `.streamlit/config.toml` sets `showErrorDetails = "type"`, so visitors see
  the exception type, not a traceback.
- Resource limits on the free tier are tight (about 1 GB RAM). The heaviest
  tabs are Copy-Move (in-memory downscale to 2048 px), PRNU (centre crop to
  2048 px) and JPEG ghosts (10 recompressions).

---

## Docker

`Dockerfile`:

```dockerfile
FROM python:3.10-slim
WORKDIR /app
# No system packages needed: all dependencies ship manylinux wheels.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8501
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

```bash
docker build -t veritas .
docker run -p 8501:8501 veritas
# optional HMAC key for ledger exports:
docker run -p 8501:8501 -v "$PWD/secrets.toml:/app/.streamlit/secrets.toml:ro" veritas
```

No volumes are required: the app keeps no state on disk between sessions.

---

## Own server (VM) behind nginx

Run `streamlit run app.py --server.port 8501` under a process manager
(systemd, supervisor) and proxy it. Streamlit uses WebSockets, so forward the
upgrade headers:

```nginx
server {
    listen 80;
    server_name your-domain.com;
    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
}
```

Add TLS (e.g. Let's Encrypt).

---

## Production considerations

- **Upload size**: Streamlit's default limit is 200 MB; lower it with
  `server.maxUploadSize` in `config.toml` if memory is tight.
- **Several instances**: session state (results, ledger) is in process memory,
  so a load balancer needs sticky sessions.
- **Temp cleanup**: per-session directories are created with
  `tempfile.mkdtemp`; on a long-running server, clean old `veritas_*`
  directories in the temp dir periodically.
- **Secrets**: keep `LEDGER_KEY` in the host's secret store, never in git.
- **What the ledger is not**: server-clock timestamps and an HMAC key held by
  the operator do not make a trusted timestamp or a legal chain of custody
  (see [Hash_Verification.md](../Descriptions/Hash_Verification.md)).

---

## Troubleshooting

- **Port in use**: `streamlit run app.py --server.port 8502`.
- **`ModuleNotFoundError`**: `pip install -r requirements.txt` in the active
  environment, on Python 3.10.
- **`c2pa` import fails**: the Metadata tab still runs; C2PA reading reports
  the error in its findings. Reinstall `c2pa-python` for your platform.
- **Out of memory on large images**: use a host with more RAM; Copy-Move and
  PRNU already bound their working size to 2048 px.

---

**Last updated**: September 2026 (v3.0.0)
