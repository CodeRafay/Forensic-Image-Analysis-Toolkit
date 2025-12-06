# Forensic Techniques Guide

Comprehensive guide to understanding and interpreting the forensic analysis techniques implemented in Veritas.

---

## Table of Contents

1. [Error Level Analysis (ELA)](#error-level-analysis)
2. [Metadata Analysis](#metadata-analysis)
3. [Histogram Analysis](#histogram-analysis)
4. [Noise Map Analysis](#noise-map-analysis)
5. [JPEG Ghost Analysis](#jpeg-ghost-analysis)
6. [Quantization Table Analysis](#quantization-table-analysis)
7. [Copy-Move Forgery Detection (CMFD)](#copy-move-forgery-detection)
8. [PRNU Analysis](#prnu-analysis)
9. [Frequency Domain Analysis](#frequency-domain-analysis)
10. [Deepfake Detection](#deepfake-detection)
11. [Resampling Detection](#resampling-detection)

---

## Error Level Analysis (ELA)

### Theory

**Error Level Analysis** reveals differences in compression levels within an image. Since JPEG is a lossy compression format, each resave at a specific quality level introduces predictable errors. Areas that have been edited or spliced into an image will have different error levels compared to the original portions.

**Key Principle**: When an image is resaved as JPEG, areas that were previously compressed will show lower error levels than newly added or edited areas.

### Algorithm

1. **Save image at specific quality** (default: 95)
2. **Calculate pixel-wise difference** between original and recompressed
3. **Scale differences** for visibility (multiply by error_scale, default: 10)
4. **Generate heatmap** overlay

### Interpretation

**What to Look For:**

- **Bright areas** = High error levels = Recently edited or added
- **Dark areas** = Low error levels = Original, previously compressed
- **Uniform brightness** = Likely authentic (consistent compression history)
- **Sharp boundaries** between bright/dark = Potential forgery boundaries

**Example Scenarios:**

✅ **Authentic Image**: Relatively uniform ELA result with gradual variations

⚠️ **Spliced Object**: Bright region with sharp edges over darker background

⚠️ **Text Added**: Very bright text over darker image areas

⚠️ **Clone Tool**: Mismatched error levels in "cloned" vs "source" regions

### Best Practices

- **Quality Parameter**: Use 90-95 for high-quality images, 75-85 for web images
- **Error Scale**: Increase (15-20) for subtle differences, decrease (5-8) for obvious edits
- **Multiple Qualities**: Run analysis at 70, 85, 95 to compare results
- **Combine with Other Techniques**: ELA alone is not conclusive—corroborate with metadata and noise analysis

### Limitations

- **Multiple Resaves**: Images saved many times may show high error everywhere
- **Camera Processing**: Some in-camera processing creates high error areas
- **JPEG Artifacts**: Natural JPEG compression can mimic forgery signatures
- **Non-JPEG Images**: ELA requires JPEG; PNG/TIFF won't show meaningful results

---

## Metadata Analysis

### Theory

**Digital Image Metadata** contains information about how, when, and where an image was captured. Forensic metadata analysis examines EXIF (Exchangeable Image File Format), IPTC, and XMP data for inconsistencies that indicate manipulation.

### What Veritas Extracts

**Basic Information**:

- Filename, format, size, dimensions
- Color mode, bit depth

**EXIF Data**:

- Camera make and model
- Lens information
- Exposure settings (ISO, aperture, shutter speed)
- Flash settings
- Focal length

**GPS Data**:

- Latitude, longitude
- Altitude
- GPS timestamp

**Software**:

- Software used (camera firmware, editing software)
- Processing date

**Timestamps**:

- Original capture time
- Modification time
- Digitization time

**Warnings**:

- Missing EXIF data
- Software editing indicators
- Thumbnail mismatches
- Suspicious timestamps

### Interpretation

**Red Flags:**

🚩 **Missing EXIF**: Authentic camera photos always have EXIF; removal suggests hiding something

🚩 **Software Tags**: Presence of Photoshop, GIMP, or other editing software

🚩 **Timestamp Inconsistencies**:

- Modified date before original date
- GPS timestamp doesn't match capture time
- Future timestamps

🚩 **Thumbnail Mismatch**: Thumbnail shows different content than main image

🚩 **Camera Model Mismatches**:

- Settings impossible for stated camera
- Lens not compatible with camera body

**Green Flags:**

✅ **Complete EXIF**: All standard fields present

✅ **Consistent Timestamps**: Logical time progression

✅ **Realistic Camera Settings**: Exposure triangle makes sense

✅ **GPS Consistency**: Location matches claimed origin

### Use Cases

- **Authentication**: Verify image is from claimed source
- **Timeline Reconstruction**: Establish when image was captured
- **Geolocation**: Confirm where image was taken
- **Chain of Custody**: Track editing history

### Limitations

- **Metadata Can Be Faked**: Tools exist to write arbitrary EXIF data
- **Legitimate Removal**: Privacy tools remove GPS/EXIF for good reasons
- **Camera Variations**: Different models store different fields
- **RAW Conversion**: RAW-to-JPEG conversion modifies metadata

---

## Histogram Analysis

### Theory

A **histogram** shows the distribution of pixel intensities across color channels. Manipulated images often exhibit statistical anomalies in their histograms.

### What to Look For

**Normal Distribution Patterns**:

- Smooth curves without gaps
- Bell-shaped or bimodal distributions
- Consistent spread across channels

**Suspicious Patterns**:

⚠️ **Gaps/Comb Pattern**:

- Indicates stretching (levels/curves adjustment)
- Every Nth value missing

⚠️ **Spikes at Extremes**:

- Clipping (0 or 255 spike) = lost detail
- Indicates poor exposure or aggressive editing

⚠️ **Abrupt Cutoffs**:

- Histogram ends suddenly mid-range
- Suggests level adjustment

⚠️ **Channel Imbalances**:

- One channel significantly different
- May indicate color grading or selective adjustment

### Statistical Metrics

Veritas calculates:

- **Mean**: Average brightness per channel
- **Std Dev**: Spread of values (low = flat image)
- **Min/Max**: Value range

### Use Cases

- **Detect Level Adjustments**: Comb patterns reveal stretching
- **Identify Clipping**: Lost shadow/highlight detail
- **Compare Regions**: Spliced areas may have different histograms
- **Quality Assessment**: Evaluate dynamic range

### Limitations

- **Natural Variation**: Some scenes naturally have unusual histograms
- **JPEG Compression**: Creates minor histogram artifacts
- **Not Definitive**: Histogram alone doesn't prove forgery

---

## Noise Map Analysis

### Theory

**Digital Noise** (sensor noise, photon shot noise) is inherent in digital photography and should be uniform across an authentic image. Edited areas often show inconsistent noise patterns because:

1. **Cloning** copies noise from source to target (creates duplicate patterns)
2. **Smoothing** (blur, healing brush) reduces noise
3. **Splicing** introduces noise from different image with different ISO/sensor

### Algorithm

1. **Apply Gaussian blur** to smooth image
2. **Subtract blurred from original** = high-frequency noise residual
3. **Enhance contrast** for visibility

### Interpretation

**What to Look For:**

✅ **Uniform Texture**: Consistent noise grain = authentic

⚠️ **Smooth Patches**: Areas with less noise = retouching (healing, blur)

⚠️ **Noise Variation**: Different noise levels = potential splice

⚠️ **Noise-Free Edges**: Suspiciously clean boundaries = added objects

### Use Cases

- **Detect Retouching**: Face smoothing, skin airbrushing
- **Find Cloned Regions**: Duplicate noise patterns
- **Identify Splices**: Noise discontinuities at object boundaries

### Limitations

- **Variable ISO**: Cameras adjust noise by ISO; not always uniform in authentic images
- **Compression**: JPEG artifacts affect noise analysis
- **Intentional Blur**: Depth of field creates legitimate noise variations

---

## JPEG Ghost Analysis

### Theory

**JPEG Ghosts** appear when an image is resaved at different quality levels multiple times. Each save at quality Q leaves a "ghost" detectable when resaving at that same quality again.

**Principle**: If an image was previously saved at quality 70, resaving at 70 will show minimal difference. Resaving at 90 will show more difference. The quality level with the _least_ difference indicates previous save quality.

### Algorithm

1. **Resave image at multiple qualities** (e.g., 90, 70, 50)
2. **Calculate difference maps** between original and each resave
3. **Accumulate differences** across iterations
4. **Compare results**: Lowest difference = likely previous save quality

### Interpretation

**Authentic Image (single save)**:

- Similar differences across all quality levels
- Gradual increase in differences with lower qualities

**Edited Image (resaved at specific quality)**:

- One quality level shows significantly lower difference
- That quality = the forgery was saved at this level

**Example**:

- Original camera JPEG saved at quality 95
- Forger edits and saves at quality 85
- Ghost analysis shows lowest difference at 85 = evidence of resave

### Use Cases

- **Determine Editing History**: How many times was image resaved?
- **Identify Forgery Quality**: At what quality was edit made?
- **Corroborate Other Findings**: Combine with ELA and metadata

### Limitations

- **Multiple Edits**: Many resaves obscure ghost patterns
- **PNG/TIFF**: Only works on JPEG images
- **Quality Estimation**: Not always precise

---

## Quantization Table Analysis

### Theory

**JPEG Compression** uses quantization tables (Q-tables) to determine compression quality. Each quality setting (1-100) corresponds to specific Q-table values. Analyzing these tables reveals:

1. **Original save quality**
2. **Software used** (different encoders use different tables)
3. **Editing history** (modified regions may have different tables)

### What Veritas Extracts

- **Luminance (Y) Table**: For brightness information
- **Chrominance (Cb/Cr) Tables**: For color information
- **Quality Estimate**: Reverse-engineered quality setting

### Interpretation

**Consistent Tables**:
✅ Standard tables from camera = likely authentic

**Inconsistent Tables**:
⚠️ Non-standard tables = editing software
⚠️ Multiple tables in one image = potential splicing

**Quality Indicators**:

- **High values (>50)**: Low quality, high compression
- **Low values (<10)**: High quality, minimal compression

### Use Cases

- **Software Fingerprinting**: Identify editing tools
- **Quality Assessment**: Determine compression level
- **Splicing Detection**: Find regions with different Q-tables

### Limitations

- **JPEG Only**: PNG, TIFF don't have Q-tables
- **Standardization**: Many encoders use similar tables
- **Difficult to Parse**: Requires deep JPEG format knowledge

---

## Copy-Move Forgery Detection (CMFD)

### Theory

**Copy-Move Forgery** (cloning) occurs when a region of an image is copied and pasted elsewhere in the same image, often to hide or duplicate objects. CMFD algorithms detect these duplicated regions.

### Algorithm (Block-Matching Approach)

1. **Divide image into overlapping blocks** (e.g., 16x16 pixels)
2. **Extract feature vectors** for each block (color, texture)
3. **Compare all blocks** to find matches
4. **Filter matches** by distance threshold
5. **Highlight duplicated regions**

### Advanced Techniques (Future Enhancement)

- **SIFT/SURF Keypoints**: Robust to rotation/scaling
- **PatchMatch**: Efficient nearest-neighbor search
- **DCT Coefficients**: Frequency-domain matching

### Interpretation

**What to Look For:**

⚠️ **Exact Duplicates**: Identical blocks indicate cloning

⚠️ **Near Matches**: Similar blocks may be clone tool with slight variation

⚠️ **Geometric Consistency**: Duplicated regions should align spatially

### Use Cases

- **Object Removal**: Cloning over unwanted elements
- **Object Duplication**: Copying objects to mislead
- **Pattern Analysis**: Detect repeated textures

### Limitations

- **High Computational Cost**: O(n²) block comparisons
- **False Positives**: Repetitive patterns (windows, tiles) trigger matches
- **Clone Tool Variations**: Advanced tools add noise to avoid detection

---

## PRNU Analysis

### Theory

**Photo Response Non-Uniformity (PRNU)** is a unique "fingerprint" of a camera's sensor caused by manufacturing imperfections. Each pixel responds slightly differently to light, creating a consistent noise pattern across all images from that sensor.

**Applications**:

- **Camera Identification**: Match image to specific camera
- **Forgery Detection**: Spliced regions won't match sensor fingerprint

### Algorithm

1. **Extract noise residual** using Wiener filter
2. **Calculate PRNU pattern** (noise - image content)
3. **Analyze variance and correlation**
4. **Compare patterns** across images

### Interpretation

**Consistent PRNU**:
✅ Uniform pattern = authentic, single-camera image

**Inconsistent PRNU**:
⚠️ Multiple patterns = splicing from different sources
⚠️ Missing PRNU in region = synthetic content

### Metrics

- **Variance**: Strength of PRNU pattern (higher = stronger fingerprint)
- **Mean**: Average PRNU value (should be near zero)
- **Correlation**: Similarity between regions

### Use Cases

- **Source Attribution**: Identify camera that took photo
- **Forgery Detection**: Find spliced content
- **Authentication**: Verify image is from claimed device

### Limitations

- **Requires Multiple Images**: Need reference set from same camera
- **Editing Destroys PRNU**: Heavy processing removes fingerprint
- **Computational Intensity**: Complex signal processing

---

## Frequency Domain Analysis

### Theory

Images can be analyzed in the **frequency domain** using Fourier Transform (FFT) or Discrete Cosine Transform (DCT). Authentic images have predictable frequency characteristics; manipulations disrupt these patterns.

**Key Concepts**:

- **Low Frequencies**: Broad shapes, smooth gradients
- **High Frequencies**: Edges, fine details, noise

### FFT Analysis

**Algorithm**:

1. **Convert to grayscale**
2. **Apply 2D FFT**
3. **Calculate magnitude spectrum**
4. **Analyze symmetry and peaks**

**Interpretation**:

- **Symmetric Spectrum**: Expected for authentic images
- **Asymmetry**: Indicates directional artifacts (resizing, rotation)
- **Unusual Peaks**: May suggest periodic patterns from forgery

### DCT Analysis

**Algorithm**:

1. **Divide into 8x8 blocks** (like JPEG)
2. **Apply DCT to each block**
3. **Analyze high-frequency coefficients**
4. **Detect anomalies**

**Interpretation**:

- **High Variance in HF**: Authentic detail
- **Low Variance in HF**: Smoothing or interpolation
- **Blockiness**: Over-compression or multiple JPEG saves

### Use Cases

- **Detect Resampling**: FFT shows periodic artifacts
- **Identify Interpolation**: High-frequency reduction
- **Find Compression**: DCT block patterns

### Limitations

- **Complex Interpretation**: Requires signal processing expertise
- **Natural Variations**: Some scenes have unusual frequency content
- **Subtle Artifacts**: Small edits may not affect frequency significantly

---

## Deepfake Detection

### Theory

**Deepfakes** and **GAN-generated images** contain subtle artifacts invisible to human eye but detectable through algorithmic analysis:

1. **Frequency Anomalies**: GANs struggle with high-frequency details
2. **Channel Correlations**: Synthetic images have unusual RGB channel relationships
3. **Edge Sharpness**: Inconsistent edge profiles
4. **Radial Frequency**: Circular patterns in FFT unique to GANs

### Techniques in Veritas

**Frequency Analysis**:

- **High-frequency suppression** (GANs smooth more than cameras)
- **Phase consistency** (synthetic images have correlatedphases)

**GAN Fingerprinting**:

- **Radial frequency profile** (GANs leave concentric patterns)
- **Color channel coupling** (RGB correlations differ)

**Edge Analysis**:

- **Sharpness inconsistency** (deepfakes mix sharp/soft edges unnaturally)

### Interpretation

**Deepfake Indicators**:

🚩 **Low High-Frequency Content**: Unnaturally smooth
🚩 **Radial Symmetry in FFT**: GAN signature
🚩 **Low RGB Correlation**: Synthetic color mixing
🚩 **Edge Inconsistency**: Mixed sharpness profiles

**Authentic Indicators**:
✅ **Natural Noise**: Sensor noise present
✅ **Asymmetric Frequency**: Real-world randomness
✅ **Consistent Edges**: Uniform focus characteristics

### Use Cases

- **Social Media Verification**: Detect synthetic profiles
- **News Authentication**: Verify video frames
- **Legal Evidence**: Identify manipulated media

### Limitations

- **Evolving GANs**: New models reduce detectable artifacts
- **Adversarial Training**: Some GANs trained to evade detection
- **Compressed Images**: JPEG artifacts mask GAN signatures
- **High-Quality Deepfakes**: State-of-the-art models increasingly convincing

---

## Resampling Detection

### Theory

**Resampling** (resizing, rotating) requires interpolation to generate new pixel values. This process leaves mathematical traces detectable through frequency analysis.

**Interpolation Methods**:

- **Nearest Neighbor**: Creates blocky artifacts
- **Bilinear**: Linear interpolation, introduces correlations
- **Bicubic**: Smoother, but creates periodic patterns
- **Lanczos**: High-quality, subtle artifacts

### Detection Algorithm

**Periodicity Analysis**:

1. **Compute 2D FFT** of image
2. **Look for periodic peaks** in specific frequencies
3. **Detect interpolation signature**

**Statistical Analysis**:

- **Pixel correlation**: Resampled images have higher correlation
- **Variance patterns**: Interpolation reduces local variance

### Interpretation

**Resampling Indicators**:

⚠️ **Periodic FFT Peaks**: Signature of interpolation
⚠️ **High Correlation**: Nearby pixels too similar
⚠️ **Reduced Variance**: Loss of randomness

**Interpolation Classification**:

- **Blocky Patterns** → Nearest neighbor
- **Linear Correlations** → Bilinear
- **Smooth with Ringing** → Bicubic
- **High Quality, Subtle** → Lanczos/high-order

### Use Cases

- **Detect Resizing**: Was image scaled?
- **Identify Rotation**: Slight rotations leave traces
- **Forgery Evidence**: Spliced objects often resized to fit

### Limitations

- **Camera Processing**: Some cameras internally resample (DNG→JPEG)
- **Slight Resampling**: Small scale changes hard to detect
- **Multiple Operations**: Resampling + compression obscures patterns

---

## Combining Techniques

### Multi-Modal Analysis

**Best Practice**: Use multiple techniques together for robust conclusions.

**Workflow Example**:

1. **Start with Metadata**: Check for obvious red flags
2. **Run ELA**: Look for editing patterns
3. **Analyze Histograms**: Assess statistical manipulation
4. **Check Noise**: Verify consistency
5. **Deepfake Detection**: If portrait, check for GAN artifacts
6. **Frequency Analysis**: Confirm resampling/interpolation
7. **Correlate Findings**: Multiple techniques agreeing = higher confidence

### Confidence Levels

| Findings       | Confidence | Conclusion              |
| -------------- | ---------- | ----------------------- |
| 1 technique    | Low        | Investigate further     |
| 2-3 techniques | Medium     | Likely authentic/forged |
| 4+ techniques  | High       | Strong evidence         |
| All techniques | Very High  | Near certain            |

### Reporting

When presenting findings:

- **List all techniques used**
- **Show evidence from each**
- **Explain contradictions** (if any)
- **Provide confidence assessment**
- **Acknowledge limitations**

---

## References

### Academic Papers

1. **ELA**: Krawetz, N. (2007). "A Picture's Worth: Digital Image Analysis and Forensics"
2. **PRNU**: Lukáš, J. et al. (2006). "Digital Camera Identification from Sensor Pattern Noise"
3. **CMFD**: Fridrich, J. et al. (2003). "Detection of Copy-Move Forgery in Digital Images"
4. **Deepfakes**: McCloskey, S. (2021). "Detecting GAN-generated Imagery Using Saturation Cues"
5. **Resampling**: Popescu, A. (2005). "Exposing Digital Forgeries by Detecting Traces of Resampling"

### Books

- _Digital Image Forensics_ by Husrev Taha Sencar, Nasir Memon (2013)
- _Handbook of Digital Forensics of Multimedia Data and Devices_ by Anthony T.S. Ho (2015)

### Tools & Libraries

- **ExifTool**: Comprehensive metadata extraction
- **FotoForensics**: Online ELA tool
- **Forensically**: Browser-based forensic suite

---

**Last Updated**: December 2025
