# 🔄 Copy-Move Forgery Detection (CMFD)

## What is Copy-Move Forgery Detection?

Copy-move forgery is when someone **copies one part of an image and pastes it elsewhere** to hide, duplicate, or alter content. CMFD is like a **fingerprint comparison system** – it finds regions that are suspiciously identical, revealing where copying occurred.

Think of it like:

- **Detective checking photos** for the same person appearing twice in impossible places
- **Art authenticator** spotting when an artist used the same brush stroke twice
- **Forensic examiner** finding duplicate fingerprints at a crime scene

## What Does CMFD Measure?

- **Block similarities** across the image (8×8 pixel blocks)
- **Feature matching** between regions
- **Spatial relationships** of matching blocks
- **Distortion patterns** (rotated, scaled, or skewed copies)
- **DCT coefficient matching** for JPEG images
- **Keypoint descriptors** (SIFT-like features)

## How to Interpret Results

### ✅ Normal Patterns (Likely Authentic)

- **No matching blocks** detected
- **Unique feature descriptors** throughout image
- **No suspicious clustering** patterns
- **Natural variations** in repeated elements (leaves, tiles, ripples)

### ⚠️ Suspicious Patterns (Possible Manipulation)

1. **Exact Block Matches**

   - Identical 8×8 blocks at different locations
   - Perfect correlation indicates copying

2. **Clustered Matches**

   - Large groups of matching blocks in specific regions
   - Shows where copy-paste occurred

3. **Geometric Patterns**

   - Rectangular regions of matches
   - Indicates deliberate copy operation

4. **Edge Detection**

   - Sharp boundaries between matched regions
   - Shows artificial boundaries of pasted content

5. **Distortion Artifacts**
   - Slightly rotated or scaled copies
   - Suggests attempt to disguise duplication

## Common Artifacts Detected

### 1. **Simple Copy-Paste (Easiest to Detect)**

```
Original Region: Person A at location X
Copied Region:   Person A at location Y (identical pixels)
```

**Analysis**: Exact duplicate indicates forgery

### 2. **Object Duplication**

- Tree cloned multiple times to make forest look denser
- Repeated person in group photo
- Duplicate building or vehicle

### 3. **Content Concealment**

- Unwanted person copied over with background
- Undesirable object hidden by pasting grass/sky over it

### 4. **Background Manipulation**

- Repeated texture to remove unwanted elements
- Cloned sky to hide airplanes or birds

### 5. **Sophisticated Forgeries**

- Rotated or scaled copies (more subtle)
- Blurred edges to hide copying boundaries
- Combined with other regions for natural blending

## Detection Process Explained

**Step 1: Block Division**

- Image divided into 8×8 pixel blocks (JPEG-sized)

**Step 2: Feature Extraction**

- Each block analyzed for distinctive characteristics
- DCT coefficients or keypoint descriptors calculated

**Step 3: Matching**

- Similar blocks compared across entire image
- Similarity scores calculated (0-100)

**Step 4: Clustering**

- Matching blocks grouped together
- Geographic clusters identified

**Step 5: Visualization**

- Matching regions highlighted with colored outlines
- Heatmap shows confidence of matches

## Real-World Examples

### Case 1: Crowd Photo Faker

**What happened**: Person added themselves to group photo by copying
**CMFD Detection**:

- Head region matches person from another photo exactly
- Shoulders show perfect alignment of duplicated blocks
- Body shows repeat of same texture pattern

**Verdict**: Clear copy-move forgery

### Case 2: Landscape Manipulation

**What happened**: Forest made to look denser by copying trees
**CMFD Detection**:

- Same tree cluster appears multiple times
- Identical branch patterns at different locations
- Geometric alignment too perfect to be natural coincidence

**Verdict**: Artificial enhancement through copying

### Case 3: Evidence Tampering

**What happened**: Unwanted person in crime scene photo covered up
**CMFD Detection**:

- Background region appears twice (original + copied over person)
- Edge discontinuities where copy boundaries don't align
- Lighting inconsistencies at paste edges

**Verdict**: Content removal via copy-paste

## Limitations

### ⚠️ Important Caveats

1. **Natural Repetition**

   - Brick patterns, tile floors, leaf clusters
   - Naturally identical blocks aren't forgery
   - Algorithm must distinguish between natural and artificial repetition

2. **Rotation & Scaling**

   - Simple block matching misses rotated copies
   - Advanced algorithms can detect these, but with lower confidence

3. **Blending Techniques**

   - Skilled forgers blend copy boundaries
   - Partially blurred edges reduce match confidence

4. **Multiple Copies**

   - Source region copied many times
   - Hard to identify which is original

5. **JPEG Compression**

   - Compression reduces block distinctiveness
   - Can cause false negatives on heavily compressed images

6. **Image Resolution**

   - Low-resolution images have fewer blocks
   - Small copies hard to detect

7. **Sophisticated Edits**
   - Content-aware fill creates new pixels
   - Not technically "copied" but looks forged

## Best Practices

✔️ **Use for initial screening** of suspected forgeries  
✔️ **Examine clustered regions** carefully (strongest evidence)  
✔️ **Consider context** (is this repetition natural for this scene?)  
✔️ **Look for edge artifacts** (blurring, boundary misalignment)  
✔️ **Combine with other techniques** (ELA often corroborates)  
✔️ **Analyze at multiple scales** (zoom in and out)  
✔️ **Consider likelihood** (would a real scene have this pattern?)

## Key Questions to Ask

1. Are matching blocks in geometrically suspicious locations?
2. Could the repetition be natural for this type of scene?
3. Are there edge artifacts or boundary discontinuities?
4. Is lighting consistent across matched regions?
5. Do the copy positions align with logical forgery goals?
6. Are there other forensic indicators supporting copy-move evidence?

---

_CMFD is like a forensic fingerprint system – it finds exact matches that reveal where copying occurred. While natural repetition can complicate analysis, true forgeries leave geometric and spatial patterns that are difficult to hide._
