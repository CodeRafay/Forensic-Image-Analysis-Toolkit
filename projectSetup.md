# 🔍 Forensic Image Analysis Tool (Veritas)

## **Streamlit Development & Setup Guide**

This guide covers the setup for **Veritas**, a web-based forensic tool. We are using **Streamlit** because it allows for rapid UI development, easy deployment, and native support for data visualization (histograms, heatmaps) without complex GUI code.

---

## 🛠️ 1. Environment Setup

### 🧩 Install Python

1.  Ensure **Python 3.9+** is installed.
2.  Open your terminal/command prompt.

### 🧰 Create Project & Virtual Environment

1.  Create your project folder:
    ```bash
    mkdir VeritasForensics
    cd VeritasForensics
    ```
2.  Create and activate the virtual environment:

    ```bash
    # Windows
    python -m venv venv
    venv\Scripts\activate

    # Mac/Linux
    python3 -m venv venv
    source venv/bin/activate
    ```

    ✅ _Your prompt should now show `(venv)`._

### 📦 Install Dependencies

We are replacing PyQt6 with Streamlit. Run this command to install all necessary libraries:

```bash
pip install streamlit Pillow piexif opencv-python-headless scikit-image matplotlib numpy pandas plotly
```

_Note: `opencv-python-headless` is lighter and better for server/cloud environments than standard `opencv-python`._

---

## 🧱 2. Project Structure

We will simplify the structure to suit a web-app workflow.

```text
VeritasForensics/
├── venv/                      # Virtual Environment
├── app.py                     # MAIN ENTRY POINT (Replaces main.py)
│
├── analysis/                  # FORENSIC ALGORITHMS (The Brains)
│   ├── __init__.py
│   │
│   ├── ela.py                    # Error Level Analysis
│   ├── metadata_analysis.py      # EXIF + file structure checks
│   ├── histogram_analysis.py     # Statistical color/brightness features
│   ├── noise_map.py              # Noise inconsistency
│   ├── jpeg_ghost.py             # Multi-compression detection
│   ├── quant_table.py            # JPEG quantization table forensics
│   ├── cmfd.py                   # Copy-move forgery detection
│   ├── prnu.py                   # Sensor fingerprint analysis
│   ├── frequency_analysis.py     # FFT/DCT-based tampering detection
│   ├── deepfake_detector.py      # GAN/deepfake artifact classifier
│   ├── resampling_detector.py    # Resampling interpolation detection
│   │
│   └── util.py                   # Shared helpers
│
├── assets/                    # Static files
│   └── style.css              # Custom CSS (optional)
│
├── .streamlit/                # Streamlit Configuration
│   └── config.toml            # Theme settings (Dark mode, colors)
│
├── temp/                      # Temp folder for processing (ELA needs this)
│   └── .gitkeep
│
└── requirements.txt           # For deployment
```

---

## ⚙️ 3. Configuration & Theming

Create a folder named `.streamlit` and a file inside it named `config.toml`. This gives your app a professional "Forensic/Dark Mode" look immediately.

**File:** `.streamlit/config.toml`

```toml
[theme]
base="dark"
primaryColor="#00ff41"
backgroundColor="#0e1117"
secondaryBackgroundColor="#262730"
textColor="#fafafa"
font="sans serif"

[server]
headless = true
```

---

## 💻 4. Core Application Code (`app.py`)

This is your new "Main Window". It handles the sidebar, file uploading, and tabs.

**File:** `app.py`

```python
import streamlit as st
import os
from PIL import Image
from analysis import ela, metadata_analysis

# 1. Page Configuration
st.set_page_config(
    page_title="Veritas - Digital Forensics",
    page_icon="🔍",
    layout="wide"
)

# 2. Helper: Save Uploaded File to Disk (Required for some OpenCV algos)
def save_uploaded_file(uploaded_file):
    if not os.path.exists("temp"):
        os.makedirs("temp")
    file_path = os.path.join("temp", uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return file_path

# 3. Sidebar
st.sidebar.title("🔍 Veritas Tool")
st.sidebar.info("Upload a digital image to perform forensic analysis.")
uploaded_file = st.sidebar.file_uploader("Choose an Image", type=["jpg", "jpeg", "png"])

# 4. Main Logic
if uploaded_file is not None:
    # Save file temporarily
    file_path = save_uploaded_file(uploaded_file)

    # Display Original
    col1, col2 = st.columns([1, 2])
    with col1:
        st.image(file_path, caption="Original Image", width='stretch')
    with col2:
        st.warning(f"Analyzing: {uploaded_file.name}")

    # 5. Analysis Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["🕵️ ELA", "📋 Metadata", "📊 Histogram", "👻 Noise/Ghost"])

    # --- TAB 1: ELA ---
    with tab1:
        st.subheader("Error Level Analysis")
        st.write("Highlights differences in compression levels. White areas suggest potential manipulation.")

        quality = st.slider("ELA JPEG Quality", 50, 95, 90)
        if st.button("Run ELA Analysis"):
            with st.spinner("Processing..."):
                ela_img = ela.perform_ela(file_path, quality)
                st.image(ela_img, caption="ELA Result", width='stretch')

    # --- TAB 2: METADATA ---
    with tab2:
        st.subheader("EXIF Metadata")
        if st.button("Extract Metadata"):
            meta = metadata_analysis.extract_metadata(file_path)
            if meta:
                st.json(meta)
            else:
                st.info("No EXIF data found.")

    # --- TAB 3 & 4 (Placeholders for now) ---
    with tab3:
        st.info("Histogram Analysis coming soon.")
    with tab4:
        st.info("Noise Map & Ghost Analysis coming soon.")

else:
    st.markdown("### Welcome to Veritas")
    st.markdown("""
    This tool allows you to analyze images for forgeries using:
    * **Error Level Analysis (ELA)**
    * **Metadata Extraction**
    * **Noise Variance**
    * **Copy-Move Detection**
    """)
```

---

## 🧠 5. Refactored Backend Modules

Since we are on the web, we want functions that return **Objects** (Images/Dictionaries), not functions that just print to the console.

**File:** `analysis/ela.py`

```python
import os
from PIL import Image, ImageChops, ImageEnhance

def perform_ela(image_path, quality=90):
    """
    Generates an ELA image.
    Returns: PIL Image object
    """
    original = Image.open(image_path).convert("RGB")

    # Save a temporary compressed version
    temp_file = "temp/ela_temp.jpg"
    original.save(temp_file, "JPEG", quality=quality)

    # Open the compressed version
    resaved = Image.open(temp_file)

    # Calculate the difference
    diff = ImageChops.difference(original, resaved)

    # Enhance the difference to make it visible
    extrema = diff.getextrema()
    max_diff = max([ex[1] for ex in extrema])
    scale = 255.0 / max_diff if max_diff != 0 else 1

    ela_image = ImageEnhance.Brightness(diff).enhance(scale)

    return ela_image
```

**File:** `analysis/metadata_analysis.py`

```python
import piexif
from PIL import Image

def extract_metadata(image_path):
    """
    Returns: Dictionary of metadata
    """
    data = {}
    try:
        # Load via Piexif if JPEG
        exif_dict = piexif.load(image_path)

        # Helper to parse bytes to string
        def decode_tag(v):
            if isinstance(v, bytes):
                try: return v.decode('utf-8').strip('\x00')
                except: return str(v)
            return v

        # Iterate over common IFDs
        for ifd in ("0th", "Exif", "GPS", "1st"):
            if ifd in exif_dict:
                for tag in exif_dict[ifd]:
                    tag_name = piexif.TAGS[ifd][tag]["name"]
                    tag_value = exif_dict[ifd][tag]
                    data[tag_name] = decode_tag(tag_value)

    except Exception:
        # Fallback for PNG or non-EXIF images (basic info)
        try:
            img = Image.open(image_path)
            data['Format'] = img.format
            data['Size'] = img.size
            data['Mode'] = img.mode
        except:
            return {"Error": "Could not read image data"}

    return data
```

---

## 🚀 6. Running the App

1.  Make sure your virtual environment is active.
2.  Run the following command in the terminal:
    ```bash
    streamlit run app.py
    ```
3.  A browser window will open automatically at `http://localhost:8501`.

---

## ☁️ 7. Deployment (Future Step)

When you are ready to submit or show your supervisor:

1.  Push your code to **GitHub**.
2.  Go to [share.streamlit.io](https://share.streamlit.io).
3.  Log in with GitHub and click **"New App"**.
4.  Select your `VeritasForensics` repo and the `app.py` file.
5.  Click **Deploy**.

_Your app is now live on the internet\!_
