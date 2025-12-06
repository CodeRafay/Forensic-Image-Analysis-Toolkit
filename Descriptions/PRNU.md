# 📡 PRNU Analysis (Photo Response Non-Uniformity)

## What is PRNU Analysis?

PRNU is like the **"fingerprint of a camera sensor"** – every physical camera sensor has tiny imperfections that create a unique, nearly invisible pattern in every photo it takes. This fingerprint is so distinctive it can identify exactly which camera took the photo.

Think of it like:

- **Ballistics analysis** where every gun creates unique striations on bullets
- **Ink analysis** where every printer produces a unique color pattern
- **Handwriting analysis** where individual quirks identify a person
- **Retinal scan** – each eye is unique, each sensor is unique

## What Does PRNU Analysis Measure?

- **Sensor imperfections** (manufacturing defects)
- **Photo response** (how each pixel responds to light)
- **Noise patterns** unique to specific hardware
- **Camera identification** (which camera took this photo)
- **Forgery detection** (did multiple cameras take this image?)
- **Device matching** (does photo match claimed camera?)

## How to Interpret Results

### ✅ Normal Patterns (Likely Authentic)

1. **Single Camera Fingerprint**

   - Strong PRNU correlation from one camera
   - Consistent pattern throughout image
   - Matches claimed device

2. **High Correlation Score**

   - Typically > 0.010 indicates strong camera match
   - All regions show similar fingerprinting

3. **Device Consistency**
   - Photo matches known PRNU of claimed camera
   - If metadata says "iPhone 13", PRNU matches iPhone 13 characteristic pattern

### ⚠️ Suspicious Patterns (Possible Manipulation)

1. **Multiple Fingerprints**

   - Different regions show different camera signatures
   - Indicates splicing from multiple cameras

2. **Low Correlation**

   - No strong PRNU match to any camera
   - Could indicate heavy editing or compression

3. **Mismatched Device**

   - Metadata claims iPhone 13
   - But PRNU matches Canon EOS pattern
   - Photo not taken by claimed device

4. **Inconsistent Regions**

   - Background shows Camera A fingerprint
   - Foreground shows Camera B fingerprint
   - Clear sign of composite image

5. **Edited Regions**
   - Pasted content lacks proper PRNU
   - Added elements show different fingerprint

## Common Applications

### 1. **Camera Identification**

```
Input: Photo of unknown origin
Output: "This photo was taken by Canon EOS 5D Mark IV, serial #ABC123"
```

**Use case**: Tracing source of leaked images

### 2. **Forgery Detection**

```
Detected PRNU Pattern 1: iPhone 13 (foreground)
Detected PRNU Pattern 2: Android Galaxy (background)
Verdict: Composite image from two cameras
```

**Use case**: Detecting spliced images

### 3. **Image Authentication**

```
Metadata claim: "Shot on iPhone 14 Pro"
PRNU analysis: Matches iPhone 14 Pro ✓
Verdict: Claim is authentic
```

**Use case**: Verifying image source in legal proceedings

### 4. **Content Verification**

```
Multiple photos submitted as "authentic coverage"
PRNU: All from same camera with same settings
Verdict: Likely legitimate series, not cherry-picked
```

**Use case**: Validating journalistic integrity

## Detection Process Explained

### Step 1: Reference PRNU Extraction

- Known camera database contains PRNU fingerprints
- Or: Extract from multiple photos from same camera

### Step 2: Test Image Analysis

- Extract PRNU pattern from analyzed photo
- Compare against reference fingerprints

### Step 3: Correlation Calculation

- Statistical correlation between patterns
- Measures how well test image matches reference camera

### Step 4: Result Interpretation

- High correlation (>0.010) = Strong match
- Low correlation (<0.005) = No match
- Multiple peaks = Multiple cameras

### Step 5: Confidence Scoring

- Account for image size, resolution, compression
- Generate confidence percentage

## Real-World Examples

### Case 1: Evidence Authentication

```
Submitted as evidence: Security camera footage
Metadata: "Unknown source"
PRNU Analysis: Matches Hikvision DS-2CD2143G0 camera
Serial pattern matches: Camera #47 in building database
Verdict: Verified as security camera footage
```

### Case 2: Synthetic Content Detection

```
Social Media Claim: "I took this photo"
Claimed camera: iPhone 15 Pro
PRNU Analysis: No known camera fingerprint detected
Result: Photo is either heavily edited or AI-generated
```

### Case 3: Spliced Composite

```
Analyzed image: Celebrity in compromising situation
Background PRNU: Matches Nikon D850
Foreground PRNU: Matches Canon R5
Verdict: Different camera sources, likely composite
```

## PRNU vs. Other Techniques

| Technique    | Detects                           | Strength                | Limitation                  |
| ------------ | --------------------------------- | ----------------------- | --------------------------- |
| **PRNU**     | Multiple cameras, device matching | Identifies exact camera | Requires reference database |
| **ELA**      | Compression differences           | Shows edited regions    | Doesn't identify camera     |
| **Metadata** | Software history                  | Shows editing software  | Can be faked                |
| **Noise**    | Sensor patterns                   | Detects splicing        | Less precise than PRNU      |

## Limitations

### ⚠️ Important Caveats

1. **Reference Database Required**

   - Need known PRNU fingerprints for comparison
   - Not all cameras have profiles available
   - Custom or rare cameras may not have baseline

2. **Image Processing Reduces PRNU**

   - Heavy compression diminishes fingerprint
   - Resizing or rotation can degrade pattern
   - Multiple JPEG saves progressively weaken PRNU

3. **Sensor Degradation**

   - PRNU changes slightly over time
   - Old camera fingerprints may not match recent photos

4. **Similar Cameras**

   - Cameras from same manufacturer/batch show similar PRNU
   - May not always distinguish between models

5. **Edited Images**

   - Content-aware fill generates new pixels
   - Added pixels won't have consistent PRNU

6. **Social Media Recompression**

   - Platforms recompress heavily
   - Severely damages PRNU signal

7. **Thermal Effects**
   - Sensor temperature affects PRNU slightly
   - Same camera under different conditions shows variation

## Best Practices

✔️ **Use primary reference images** from known camera source  
✔️ **Compare multiple photos** from same camera (builds stronger profile)  
✔️ **Account for compression** (lossless formats preserve PRNU best)  
✔️ **Check for consistency** across image regions  
✔️ **Combine with metadata** analysis for full picture  
✔️ **Build camera fingerprint database** for your organization  
✔️ **Use with other techniques** (especially ELA)  
✔️ **Consider the context** (is camera match logical for claimed source?)

## Key Questions to Ask

1. Does the PRNU signature match the claimed camera?
2. Are there multiple PRNU patterns in one image?
3. Is the correlation score high enough to be conclusive?
4. Do regions show consistent fingerprinting?
5. Could compression or editing explain low PRNU correlation?
6. Does the camera match make sense for the photo's origin?

## Practical Considerations

### PRNU Correlation Scales:

- **> 0.015**: Very strong match, highly reliable
- **0.010 - 0.015**: Strong match, good confidence
- **0.005 - 0.010**: Weak match, suggestive only
- **< 0.005**: Essentially no match

### Image Quality for PRNU:

- **Best**: RAW files, 10+ megapixels, minimal processing
- **Good**: JPEG from camera at original resolution
- **Poor**: Screenshots, heavily compressed, resized
- **Worst**: Multiple JPEG saves, extreme compression

---

_PRNU analysis is the gold standard for camera identification – like matching a bullet to a specific gun through ballistic striations. Each camera sensor has a unique fingerprint that persists across photos, making PRNU one of the most reliable techniques for source authentication._
