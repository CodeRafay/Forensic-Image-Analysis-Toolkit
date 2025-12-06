# 🔀 Resampling Detection

## What is Resampling Detection?

Resampling is when an image is **scaled up or down and then saved**. When you resize an image, interpolation algorithms create new pixels, leaving telltale patterns. Resampling detection finds these patterns to reveal image manipulation.

Think of it like:

- **Document examiner** detecting when text was enlarged with a copy machine
- **Handwriting expert** spotting when writing was scaled/stretched
- **Print forensics** detecting offset printing press patterns
- **Audio forensics** detecting when sound was pitch-shifted

## What Does Resampling Detection Measure?

- **Interpolation patterns** (nearest neighbor, bilinear, bicubic algorithms)
- **Scaling factors** (how much the image was enlarged/reduced)
- **Resampling artifacts** (characteristic grid patterns)
- **Frequency anomalies** (unusual periodic patterns)
- **Directional artifacts** (horizontal vs. vertical patterns)
- **Compression consistency** (uniform vs. localized resampling)

## How to Interpret Results

### ✅ Normal Patterns (Likely Authentic)

1. **No Resampling Detected**

   - Image at original resolution
   - No interpolation artifacts
   - **Score**: 85-100 (Original resolution)

2. **Uniform Scaling**

   - If resampled, entire image shows consistent pattern
   - Scaling factor detectable and reasonable
   - No suspicious regions

3. **Natural Interpolation**
   - Bilinear or bicubic interpolation used
   - Professional quality resampling
   - Artifacts minimal and uniform

### ⚠️ Suspicious Patterns (Possible Manipulation)

1. **Undetectable Scaling Factor**

   - Cannot determine original resolution
   - Suggests complex processing
   - **Warning**: "Unclear scaling history"

2. **Inconsistent Resampling**

   - Different regions show different scaling
   - Some areas upscaled, others downscaled
   - **Warning**: "Region-specific scaling detected"

3. **Suspicious Scaling Ratio**

   - Impossible scaling factor for claimed image
   - **Example**: Claimed 24MP image shows 8MP scaling
   - **Warning**: "Incompatible with claimed source"

4. **Multiple Resampling Passes**

   - Multiple scaling operations detected
   - Cumulative quality degradation
   - **Warning**: "Multiple resampling cycles detected"

5. **Localized Artifacts**
   - Only certain regions show resampling
   - Others appear original resolution
   - **Warning**: "Possible insertion of rescaled content"

## How Resampling Happens

### Normal Scenario (Single Original):

```
Camera captures: 4000×3000 pixels
Saved as JPEG: 4000×3000 pixels (original)
Analysis: No resampling patterns detected
```

### Suspicious Scenario (Manipulation):

```
Original image: 4000×3000 pixels
Extracted object: 500×400 pixels
Scaled up: 1000×800 pixels (interpolated)
Inserted into new image
Analysis: Resampling patterns detected in object region
```

## Common Artifacts Detected

### 1. **Nearest Neighbor Interpolation**

Easiest to detect:

- Blocky patterns
- Visible "stair-stepping" at edges
- Regular grid artifacts
- Often used for quick/careless edits
- **Suspicion level: Very High**

### 2. **Bilinear Interpolation**

Medium difficulty:

- Smoother than nearest neighbor
- Characteristic diagonal artifacts
- Professional editing tools often use this
- **Suspicion level: Medium**

### 3. **Bicubic Interpolation**

Hardest to detect:

- Very smooth scaling
- Minimal artifacts
- Professional quality
- Used by Photoshop and similar tools
- **Suspicion level: Lower** (but still detectable)

### 4. **Directional Artifacts**

**Horizontal Artifacts**:

- Lines run left-right
- Suggests horizontal stretching
- Typical of landscape scaling

**Vertical Artifacts**:

- Lines run top-bottom
- Suggests vertical stretching
- Typical of portrait modifications

**Diagonal Artifacts**:

- 45-degree patterns
- Suggests non-uniform scaling
- Indicates suspicious distortion

## Real-World Examples

### Case 1: Enlarged Logo

```
Situation: Counterfeit document with copied logo
Analysis: Logo region shows:
  - Nearest neighbor resampling
  - Scaling factor: 2.5x enlargement
  - Artifacts: Clear blocky patterns
Conclusion: Logo was taken from lower-res source and enlarged
```

### Case 2: Inserted Photo

```
Situation: Person added to group photo
Analysis:
  - Background: Original 12MP resolution
  - Person: 8MP resolution resampled to fit
  - Scaling factor: 1.3x enlargement
Conclusion: Person image from different source, upscaled to fit
```

### Case 3: Multiple Compressions

```
Situation: Suspected multiple edits
Analysis:
  - First layer: 3000×2000 resampling
  - Second layer: 1500×1000 resampling
  - Third layer: Upsampled to 2400×1600
Conclusion: Image went through multiple edit cycles
```

## Resampling vs. Other Techniques

| Technique      | Detects                 | Strength                  | Weakness                 |
| -------------- | ----------------------- | ------------------------- | ------------------------ |
| **Resampling** | Scaling, interpolation  | Shows original resolution | Requires reference       |
| **ELA**        | Compression differences | Shows edited regions      | Doesn't show why         |
| **Noise**      | Camera fingerprint      | Identifies camera         | Sensitive to compression |
| **FFT/DCT**    | Frequency anomalies     | Shows artificial patterns | Generic (many causes)    |

## Limitations

### ⚠️ Important Caveats

1. **Original Resolution Unknown**

   - Can detect resampling but not always original size
   - Requires reference or metadata

2. **JPEG Compression Masks Patterns**

   - Heavy compression obscures resampling artifacts
   - Multiple JPEG saves degrade detection
   - Social media compression destroys evidence

3. **Modern Interpolation**

   - Professional tools use sophisticated algorithms
   - AI-based upscaling very hard to detect
   - Artifacts increasingly subtle

4. **Legitimate Uses**

   - Photographers often resize for social media
   - Cropping requires resampling
   - Thumbnail creation involves scaling
   - Not all resampling indicates forgery

5. **Multiple Scaling Types**

   - Camera may use internal scaling
   - Software may downsample for display
   - Chain of scaling operations obscures original

6. **Aspect Ratio Changes**

   - Non-uniform scaling (stretching)
   - Creates different artifacts
   - Can be confused with distortion

7. **Filters and Processing**
   - Blur filters reduce resampling visibility
   - Sharpening can mask patterns
   - Noise addition covers artifacts

## Best Practices

✔️ **Look for consistency** (entire image vs. specific regions)  
✔️ **Check for uniform scaling** (expected vs. suspicious)  
✔️ **Identify interpolation type** (nearest neighbor = suspicious)  
✔️ **Compare with metadata** (resolution should match)  
✔️ **Look for directional artifacts** (indicate stretching)  
✔️ **Use with other techniques** (especially ELA)  
✔️ **Consider context** (legitimate reasons for resizing exist)  
✔️ **Check original source** if available  
✔️ **Examine boundaries** (edges often show clearest patterns)

## Key Questions to Ask

1. Does the scaling factor match claimed image source?
2. Are resampling artifacts present in suspicious regions only?
3. Is the interpolation method consistent throughout?
4. Could the resampling be legitimate (crop, resize, thumbnail)?
5. Are multiple resampling layers detected?
6. Do directional artifacts indicate suspicious stretching?
7. Is compression obscuring the complete picture?

## Practical Indicator Scales

### Resampling Score (0-100):

- **85-100**: No resampling detected (original resolution)
- **70-84**: Uniform scaling only (likely legitimate)
- **50-69**: Inconsistent scaling (suspicious)
- **30-49**: Multiple resampling passes (very suspicious)
- **Below 30**: Region-specific scaling (likely composite)

### Interpolation Quality Assessment:

- **Nearest Neighbor**: Very basic (suspicious if professional image)
- **Bilinear**: Professional quality (acceptable)
- **Bicubic**: High quality (expected for Photoshop)
- **AI/ML Upscaling**: Very smooth (can't distinguish if artificial)

---

_Resampling detection reveals the "growth rings" of image modification – like counting tree rings to determine age. Every time an image is scaled and saved, it leaves characteristic patterns. Analysts can trace these patterns to reconstruct the image's scaling history and detect suspicious insertion of rescaled content._
