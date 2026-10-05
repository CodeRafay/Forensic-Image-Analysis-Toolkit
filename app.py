import hashlib
import os
import shutil
import tempfile
import time
import uuid
import warnings

import streamlit as st
from PIL import Image

import analysis  # lazy sub-module imports via __getattr__

# One huge (but tiny-on-disk) image must not exhaust the shared container's
# RAM: refuse anything above 40 MP instead of Pillow's 179 MP default.
MAX_PIXELS = 40_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS
warnings.simplefilter("error", Image.DecompressionBombWarning)
MAX_CACHED_RESULTS = 3  # results hold image arrays; bound per-session memory
STALE_SESSION_S = 3600  # sweep other sessions' temp dirs older than this

st.set_page_config(page_title="Veritas - Digital Forensics",
                   page_icon="🔍", layout="wide")

DEFAULT_SAMPLE_IMAGE = os.path.join("assets", "sample images", "sampleImg.jpeg")
HEAVY_MAX_PX = 2048  # in-memory cap for dense CMFD; never a JPEG re-save
LEVEL_ICON = {"warning": "⚠️", "notice": "🔎", "info": "ℹ️"}


# ── Session storage ───────────────────────────────────────────────
# Each browser session gets its own directory, so two visitors uploading
# "image.jpg" never see each other's files.
def workdir():
    d = st.session_state.get("workdir")
    if not d or not os.path.isdir(d):
        _sweep_stale_workdirs()
        d = tempfile.mkdtemp(prefix="veritas_")
        st.session_state.workdir = d
    return d


def _sweep_stale_workdirs():
    """Streamlit has no reliable session-end hook, so each new session
    removes other sessions' directories untouched for an hour."""
    root = tempfile.gettempdir()
    now = time.time()
    for name in os.listdir(root):
        p = os.path.join(root, name)
        try:
            if name.startswith("veritas_") and os.path.isdir(p) \
                    and now - os.path.getmtime(p) > STALE_SESSION_S:
                shutil.rmtree(p, ignore_errors=True)
        except OSError:
            pass


def save_upload(uploaded, subdir=""):
    d = os.path.join(workdir(), subdir)
    os.makedirs(d, exist_ok=True)
    ext = os.path.splitext(uploaded.name)[1].lower() or ".img"
    path = os.path.join(d, uuid.uuid4().hex + ext)
    with open(path, "wb") as f:
        f.write(uploaded.getbuffer())
    return path


def load_description(name):
    path = os.path.join("Descriptions", f"{name}.md")
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return f"Description file not found: {path}"


# ── One renderer for every analysis ───────────────────────────────
_MD_SPECIAL = "\`*_{}[]()<>#+-.!|~$"


def esc(text):
    """Escape markdown so filenames and ledger labels (user input) can't
    inject links or images that would load from third-party servers."""
    return "".join("\\" + c if c in _MD_SPECIAL else c for c in str(text))


def render(result):
    status = result["status"]
    if status == "error":
        st.error(esc(result["summary"]))
    elif status in ("insufficient_data", "not_applicable"):
        st.warning(f"{status.replace('_', ' ').capitalize()}: {esc(result['summary'])}")
    else:
        st.markdown(f"**{esc(result['summary'])}**")

    metrics = list(result["metrics"].items())
    for i in range(0, len(metrics), 4):
        for col, (label, value) in zip(st.columns(4), metrics[i:i + 4]):
            if isinstance(value, float):
                value = f"{value:.4g}"
            col.metric(label, value)

    for f in result["findings"]:
        text = f"{LEVEL_ICON[f['level']]} {esc(f['text'])}"
        if f["level"] == "warning":
            st.warning(text)
        elif f["level"] == "notice":
            st.info(text)
        else:
            st.markdown(text)

    images = list(result["images"].items())
    for i in range(0, len(images), 2):
        for col, (caption, img) in zip(st.columns(2), images[i:i + 2]):
            col.image(img, caption=caption, width="stretch")

    for title, table in result["tables"].items():
        with st.expander(title):
            if isinstance(table, list) and table and isinstance(table[0], dict):
                # Modules mix numbers and "-" in a column; Arrow can't type
                # those, so show every cell as text.
                st.dataframe([{k: "" if v is None else str(v)
                               for k, v in row.items()} for row in table],
                             width="stretch")
            else:
                st.json(table)

    if result["limitations"]:
        with st.expander("Limitations — what this test cannot see"):
            for lim in result["limitations"]:
                st.markdown(f"- {esc(lim)}")
    if result["details"]:
        with st.expander("Raw values"):
            st.json(result["details"])


def run_panel(key, label, fn, *args, **kwargs):
    """Button + cached result, so reruns (slider moves etc.) keep the output
    until the user runs again. Results are cleared when the image changes."""
    results = st.session_state.setdefault("results", {})
    if st.button(label, key=f"btn_{key}", type="primary"):
        with st.spinner("Analysing…"):
            try:
                result = fn(*args, **kwargs)
            except Exception as e:  # a module bug must not take down the app
                result = analysis.util.error_result(e)
        results.pop(key, None)
        results[key] = result
        evicted = st.session_state.setdefault("evicted", set())
        evicted.discard(key)
        while len(results) > MAX_CACHED_RESULTS:  # drop the oldest
            evicted.add(next(iter(results)))
            results.pop(next(iter(results)))
    if key in results:
        render(results[key])
    elif key in st.session_state.get("evicted", ()):
        st.caption("Result cleared to save memory — run again to see it.")


def describe(name):
    with st.expander("How this technique works"):
        st.markdown(load_description(name))


# ── Sidebar ───────────────────────────────────────────────────────
st.sidebar.markdown("#### 🔍 Veritas")
uploaded = st.sidebar.file_uploader("Upload an image to analyse",
                                    type=["jpg", "jpeg", "png"])
if uploaded is None and os.path.exists(DEFAULT_SAMPLE_IMAGE):
    st.sidebar.caption("📸 No upload — using the bundled sample image.")

# ── Image selection ───────────────────────────────────────────────
if uploaded is not None:
    digest = hashlib.sha256(uploaded.getbuffer()).hexdigest()
    if st.session_state.get("image_digest") != digest:
        old = st.session_state.get("image_path")
        if old and old.startswith(workdir()) and os.path.exists(old):
            os.remove(old)
        st.session_state.image_path = save_upload(uploaded)
        st.session_state.image_digest = digest
        st.session_state.image_name = uploaded.name
        st.session_state.results = {}
        st.session_state.evicted = set()
    file_path = st.session_state.image_path
    image_name = st.session_state.image_name
elif os.path.exists(DEFAULT_SAMPLE_IMAGE):
    if st.session_state.get("image_digest") != "sample":
        st.session_state.image_digest = "sample"
        st.session_state.results = {}
        st.session_state.evicted = set()
    file_path, image_name = DEFAULT_SAMPLE_IMAGE, "Sample image (bundled)"
else:
    file_path = image_name = None

# Refuse decompression bombs before anything decodes the pixels
if file_path is not None:
    try:
        with Image.open(file_path) as _im:
            _w, _h = _im.size
        if _w * _h > MAX_PIXELS:
            raise Image.DecompressionBombError(f"{_w}x{_h}")
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as e:
        st.error(f"Image too large to analyse here ({e}); the limit is "
                 f"{MAX_PIXELS // 1_000_000} MP.")
        st.stop()
    except Exception as e:
        st.error(f"Could not read this file as an image: {e}")
        st.stop()

st.title("Veritas — image forensics")
st.info(
    "Every result here is an **indicator, not proof**. Each test detects one "
    "kind of trace under stated conditions; a clean result means only that "
    "this test found no inconsistency at its sensitivity. Combine several "
    "independent tests and the image's context before drawing conclusions.")

if file_path is None:
    st.markdown("Upload a JPEG or PNG in the sidebar to begin.")
    st.stop()

col_img, col_info = st.columns([1, 2])
col_img.image(file_path, caption=image_name, width="stretch")
with col_info:
    st.markdown(f"**Analysing:** {esc(image_name)}")
    st.caption("All analyses read the original file bytes. Nothing is "
               "re-encoded before analysis.")

tabs = st.tabs([
    "🕵️ ELA", "📋 Metadata", "📊 Histogram", "🌫️ Noise", "💾 JPEG",
    "🔄 Copy-Move", "📡 PRNU", "📈 Frequency", "🔀 Resampling",
    "🧪 Synthetic traces", "🔐 Steganography", "🔑 Hash ledger", "ℹ️ About",
])

with tabs[0]:
    st.subheader("Error Level Analysis")
    describe("ELA")
    q = st.slider("Recompression quality", 50, 95, 90, key="ela_q")
    run_panel("ela", "Run ELA", analysis.ela.analyze_ela, file_path, quality=q)

with tabs[1]:
    st.subheader("Metadata & Content Credentials (C2PA)")
    describe("Metadata")
    run_panel("meta", "Analyse metadata",
              analysis.metadata_analysis.analyze_metadata, file_path)

with tabs[2]:
    st.subheader("Histogram analysis")
    describe("Histogram")
    run_panel("hist", "Analyse histogram",
              analysis.histogram_analysis.analyze_histogram, file_path)

with tabs[3]:
    st.subheader("Noise-residual consistency (Splicebuster)")
    describe("Noise_Ghost")
    run_panel("noise", "Analyse noise residual",
              analysis.noise_map.analyze_noise, file_path)

with tabs[4]:
    st.subheader("JPEG compression forensics")
    describe("Quantization")
    st.markdown("##### Quantization tables")
    run_panel("quant", "Read quantization tables",
              analysis.quant_table.analyze_quantization_table, file_path)
    st.markdown("##### Double-compression localization")
    run_panel("djpeg", "Map double compression",
              analysis.double_jpeg.analyze_double_jpeg, file_path)
    st.markdown("##### JPEG ghosts")
    run_panel("ghost", "Search for JPEG ghosts",
              analysis.jpeg_ghost.analyze_jpeg_ghost, file_path)

with tabs[5]:
    st.subheader("Copy-move forgery detection")
    describe("CMFD")
    run_panel("cmfd", "Detect copy-move",
              analysis.cmfd.detect_copy_move, file_path, max_px=HEAVY_MAX_PX)

with tabs[6]:
    st.subheader("PRNU sensor fingerprint")
    describe("PRNU")
    refs = st.file_uploader(
        "Reference images from the claimed camera (same resolution, "
        "unrotated; more references = stronger fingerprint)",
        type=["jpg", "jpeg", "png"], accept_multiple_files=True, key="prnu_refs")
    # Save each reference once, not on every rerun
    saved = st.session_state.setdefault("prnu_saved", {})
    ref_paths = []
    for r in refs or []:
        digest = hashlib.sha256(r.getbuffer()).hexdigest()
        if digest not in saved or not os.path.exists(saved[digest]):
            saved[digest] = save_upload(r, "prnu_refs")
        ref_paths.append(saved[digest])
    ref_paths = ref_paths or None
    run_panel("prnu", "Analyse PRNU", analysis.prnu.analyze_prnu,
              file_path, reference_paths=ref_paths)

with tabs[7]:
    st.subheader("Frequency-domain measurements")
    describe("Frequency")
    st.markdown("##### Power spectrum")
    run_panel("fft", "Measure spectrum",
              analysis.frequency_analysis.analyze_spectrum, file_path)
    st.markdown("##### JPEG block grid")
    run_panel("grid", "Extract block grid",
              analysis.frequency_analysis.analyze_blocking, file_path)

with tabs[8]:
    st.subheader("Resampling detection")
    describe("Resampling")
    run_panel("resample", "Detect resampling",
              analysis.resampling_detector.detect_resampling, file_path)

with tabs[9]:
    st.subheader("Synthetic-image traces — Experimental")
    st.warning(
        "Experimental. This tab measures spectral traces that some generators "
        "leave. It cannot reliably tell whether an image is AI-generated: "
        "modern diffusion models, resizing and recompression remove these "
        "traces, and their absence says nothing.")
    describe("Deepfake")
    run_panel("synthetic", "Measure spectral traces",
              analysis.deepfake_detector.analyze_synthetic_traces, file_path)

with tabs[10]:
    st.subheader("LSB steganalysis")
    describe("Steganography")
    run_panel("stego", "Estimate LSB payload",
              analysis.steganography_detection.analyze_lsb, file_path)

with tabs[11]:
    hv = analysis.hash_verification
    st.subheader("Hash ledger (this session only)")
    describe("Hash_Verification")
    st.caption(
        "The ledger lives only in this browser session and is not shared with "
        "other visitors. Export it to keep it. A ledger records that you saw "
        "a file with these hashes; it is not a trusted timestamp or a legal "
        "chain of custody.")
    ledger = st.session_state.setdefault("ledger", hv.new_ledger())
    try:
        key = st.secrets.get("LEDGER_KEY")
    except Exception:  # no secrets.toml configured
        key = None
    key = str(key).encode() if key else None

    c1, c2 = st.columns(2)
    with c1:
        label = st.text_input("Label for this image", value=image_name,
                              key=f"ledger_label_{st.session_state.image_digest}")
        note = st.text_input("Note (optional)", key="ledger_note")
        if st.button("➕ Add current image to ledger"):
            ledger, rec = hv.add_record(ledger, file_path, label=label, note=note)
            st.session_state.ledger = ledger
            st.success(f"Added record #{rec['id']}")
    with c2:
        run_panel("hash_verify", "🔎 Check current image against ledger",
                  hv.verify_image, ledger, file_path)

    st.markdown("---")
    st.json(hv.ledger_stats(ledger))
    e1, e2 = st.columns(2)
    with e1:
        st.download_button(
            "📤 Export ledger", hv.export_ledger(ledger, key),
            file_name="veritas-ledger.json", mime="application/json",
            disabled=not ledger)
        st.caption("Signed with HMAC-SHA256 (server key)" if key else
                   "Unkeyed SHA-256 digest: detects accidental change only — "
                   "anyone can re-sign an edited file.")
    with e2:
        imp = st.file_uploader("📥 Import a ledger", type=["json"],
                               key="ledger_import")
        if imp is not None and st.button("Merge imported ledger"):
            try:
                ledger, report = hv.import_ledger(imp.getvalue(), key=key,
                                                  into=ledger)
                st.session_state.ledger = ledger
                (st.success if report["accepted"] else st.error)(report["message"])
                st.json(report)
            except Exception as e:
                st.error(f"Import failed: {e}")

with tabs[12]:
    st.subheader("About Veritas")
    st.markdown("""
Veritas runs published image-forensics techniques and reports what each one
measured. It does not output an overall authenticity verdict: no combination
of these tests can certify that an image is unedited.

Techniques use the original file bytes (compression, noise, resampling and
LSB traces are destroyed by re-encoding). Copy-move detection may work on an
in-memory downscale of very large images; its tab reports the analysed size.

Uploaded files are stored in a temporary directory private to your session.
""")
