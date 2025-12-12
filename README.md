# 🔍 Veritas - Forensic Image Analysis Toolkit

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/streamlit-1.28+-red.svg)](https://streamlit.io)

**Veritas** is a comprehensive web-based digital forensics tool for detecting image forgeries and manipulations using 13 advanced analysis techniques.

## 🎯 Features

### Core Analysis Techniques

1. **Error Level Analysis (ELA)** - Multi-quality compression artifact detection
2. **Metadata Forensics** - EXIF analysis, GPS extraction, thumbnail inconsistencies
3. **Histogram Analysis** - Statistical color distribution patterns
4. **Noise Inconsistency** - High-pass filtering for tampered regions
5. **JPEG Ghost Detection** - Multi-level compression artifacts
6. **Quantization Table Analysis** - JPEG compression table forensics
7. **Copy-Move Forgery Detection (CMFD)** - Duplicated region detection
8. **PRNU Analysis** - Photo Response Non-Uniformity (sensor fingerprints)
9. **Frequency Domain Analysis** - FFT/DCT-based tampering detection
10. **Deepfake Detection** - GAN artifact classification
11. **Resampling Detection** - Image resizing and interpolation artifacts
12. **Steganography Detection** - LSB statistical analysis for hidden data detection
13. **Hash Verification** - Cryptographic provenance tracking and authentication

### Information Security Features

- **🔐 LSB Steganography Detection** - Chi-square testing for hidden data in Least Significant Bits
- **🔑 Blockchain-Based Provenance** - Cryptographic and perceptual hash verification
- **⚖️ Legal Chain of Custody** - Track image modifications with timestamps
- **🔒 SHA-256 Integrity** - Exact file matching for evidence verification
- **👁️ Perceptual Hashing** - Detect similar images despite minor modifications

### Additional Features

- **Technique Descriptions** - Built-in educational guides for each analysis method
- **Default Sample Image** - Preloaded image for instant testing without upload
- **Web-based Interface** - No installation required, runs in browser
- **Dark Theme** - Professional forensic UI with neon accents
- **14 Analysis Tabs** - Organized, intuitive workflow
- **Human-Readable Results** - Authenticity scoring (0-100) and risk levels
- **Real-time Processing** - Instant visual feedback
- **Cloud Deployment Ready** - Deploy to Streamlit Cloud in minutes

## 📋 Requirements

- Python 3.9 or higher
- 2GB RAM minimum
- Modern web browser (Chrome, Firefox, Edge)

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/CodeRafay/Forensic-Image-Analysis-Toolkit.git
cd Forensic-Image-Analysis-Toolkit
```

### 2. Create Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the Application

```bash
streamlit run app.py
```

The application will automatically open in your default browser at `http://localhost:8501`

## 📁 Project Structure

```
VeritasForensics/
├── app.py                          # Main Streamlit application
├── requirements.txt                # Python dependencies
├── requirements-dev.txt            # Development dependencies
├── projectSetup.md                 # Detailed setup guide
├── README.md                       # This file
├── CHANGELOG.md                    # Version history
├── CONTRIBUTING.md                 # Contribution guidelines
├── LICENSE                         # BSD 3-Clause License
├── pytest.ini                      # Test configuration
├── .gitignore                      # Git ignore rules
├── .pre-commit-config.yaml         # Pre-commit hooks
├── TECHNIQUE_DESCRIPTIONS_USER_GUIDE.md  # User guide for descriptions
│
├── analysis/                       # Forensic analysis modules
│   ├── __init__.py
│   ├── ela.py                      # Error Level Analysis
│   ├── metadata_analysis.py        # EXIF + file forensics
│   ├── histogram_analysis.py       # Statistical analysis
│   ├── noise_map.py                # Noise inconsistency
│   ├── jpeg_ghost.py               # Compression artifacts
│   ├── quant_table.py              # JPEG quantization
│   ├── cmfd.py                     # Copy-move detection
│   ├── prnu.py                     # Sensor fingerprint
│   ├── frequency_analysis.py       # FFT/DCT analysis
│   ├── deepfake_detector.py        # GAN detection
│   ├── resampling_detector.py      # Resampling detection
│   ├── steganography_detection.py  # LSB steganography detection
│   ├── hash_verification.py        # Cryptographic provenance
│   └── util.py                     # Helper functions
│
├── Descriptions/                   # Technique education module (NEW)
│   ├── ELA.md                      # ELA guide
│   ├── Metadata.md                 # Metadata guide
│   ├── Steganography.md            # Steganography detection guide
│   ├── Hash_Verification.md        # Hash verification guide
│   ├── Histogram.md                # Histogram guide
│   ├── Noise_Ghost.md              # Noise/Ghost guide
│   ├── Quantization.md             # Quantization guide
│   ├── CMFD.md                     # CMFD guide
│   ├── PRNU.md                     # PRNU guide
│   ├── Frequency.md                # FFT/DCT guide
│   ├── Deepfake.md                 # Deepfake guide
│   └── Resampling.md               # Resampling guide
│
├── docs/                           # Documentation
│   ├── API.md                      # API documentation
│   ├── DEPLOYMENT.md               # Deployment guide
│   ├── PROJECT_SUMMARY.md          # Project overview
│   └── TECHNIQUES.md               # Techniques reference
│
├── tests/                          # Unit tests
│   ├── __init__.py
│   ├── test_ela.py                 # ELA tests
│   ├── test_metadata.py            # Metadata tests
│   └── test_integration.py         # Integration tests
│
├── assets/                         # Static files
│   ├── style.css                   # Custom CSS
│   └── sample images/              # Sample test images
│       └── sampleImg.jpeg          # Default sample image
│
├── .streamlit/                     # Streamlit config
│   └── config.toml                 # Theme & server settings
│
└── temp/                           # Temporary processing files
    └── .gitkeep
```

## 🔬 Usage Guide

### Basic Workflow

1. **View Sample Image**: App loads with default sample image automatically
2. **Upload Your Image** (Optional): Click "Choose an Image" in sidebar to analyze your own
3. **Learn About Techniques**: Click technique description buttons in sidebar for guidance
4. **Select Analysis Tab**: Navigate to the technique you want to use
5. **Configure Parameters**: Adjust sliders/options as needed
6. **Run Analysis**: Click the analysis button
7. **Review Results**: View visualizations, authenticity scores, and interpretations

### Technique Descriptions (NEW)

Access built-in educational guides via sidebar buttons:

- **📚 Technique Descriptions Section** - Click any technique to learn
- **Non-technical explanations** - Understand what each tool does
- **Interpretation guides** - Learn to read results (normal vs. suspicious)
- **Real-world examples** - See practical use cases
- **Limitations explained** - Understand reliability and caveats

### Analysis Techniques Explained

#### Error Level Analysis (ELA)

Detects compression artifacts by comparing the original image with a recompressed version. Manipulated regions show different error levels.

**Use Case**: Quick initial screening for tampering

#### Metadata Forensics

Examines EXIF data, timestamps, GPS coordinates, and software signatures for inconsistencies.

**Use Case**: Verify image authenticity and origin

#### Histogram Analysis

Analyzes color distribution patterns. Manipulated regions often show statistical anomalies.

**Use Case**: Detect color/brightness adjustments

#### Noise Inconsistency

Uses high-pass filtering to detect regions with different noise characteristics.

**Use Case**: Identify spliced or cloned regions

#### JPEG Ghost Detection

Performs multiple recompressions to detect prior editing cycles.

**Use Case**: Determine editing history

#### Copy-Move Forgery Detection (CMFD)

Identifies duplicated regions within the same image.

**Use Case**: Detect cloning tools usage

#### PRNU Analysis

Extracts sensor-specific noise patterns unique to each camera.

**Use Case**: Verify camera source consistency

#### Frequency Domain Analysis

Analyzes FFT/DCT coefficients for manipulation artifacts.

**Use Case**: Detect advanced editing techniques

#### Deepfake Detection

Identifies GAN-generated or AI-manipulated faces.

**Use Case**: Detect synthetic or deepfake images

#### Resampling Detection

Identifies traces of image resizing or interpolation.

**Use Case**: Detect resolution manipulation

## ⚙️ Configuration

### Theme Customization

Edit `.streamlit/config.toml`:

```toml
[theme]
base="dark"
primaryColor="#00ff41"  # Neon green accent
backgroundColor="#0e1117"
secondaryBackgroundColor="#262730"
textColor="#fafafa"
```

## 🌐 Deployment

### Deploy to Streamlit Cloud

1. Push code to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repository
4. Select `app.py` as the main file
5. Click "Deploy"

## 📊 Performance

- **ELA**: ~2-5 seconds per image
- **Metadata**: <1 second
- **Histogram**: ~1-2 seconds
- **CMFD**: ~10-30 seconds (depending on image size)
- **Deepfake**: ~5-10 seconds
- **PRNU**: ~15-30 seconds

_Benchmarked on Intel i5, 8GB RAM, 1920x1080 images_

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the BSD 3-Clause License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- **Streamlit** - For the excellent web framework
- **PIL/Pillow** - Image processing library
- **OpenCV** - Computer vision algorithms
- **SciPy** - Scientific computing tools

## 📚 References

1. Farid, H. (2009). "Image Forgery Detection"
2. Fridrich, J. (2009). "Digital Image Forensics"
3. Bayar, B. & Stamm, M. (2018). "Constrained Convolutional Neural Networks"

## 📧 Contact

- **Author**: CodeRafay
- **GitHub**: [@CodeRafay](https://github.com/CodeRafay)
- **Repository**: [Forensic-Image-Analysis-Toolkit](https://github.com/CodeRafay/Forensic-Image-Analysis-Toolkit)

## 🔮 Roadmap

- [ ] Batch processing for multiple images
- [ ] PDF report generation
- [ ] Machine learning-based forgery classifier
- [ ] Video frame analysis
- [ ] REST API for integration

---

**⭐ If you find this project useful, please star it on GitHub!**
