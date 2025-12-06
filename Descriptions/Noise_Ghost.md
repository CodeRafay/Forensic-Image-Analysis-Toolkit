# 👻 Noise Analysis & JPEG Ghost Detection

## What is Noise Analysis?

Digital noise is like the **"fingerprint" of a camera sensor** – every camera produces a unique pattern of random pixel variations. When you edit an image and add content from different sources, the noise patterns won't match, revealing the forgery.

**JPEG Ghost Detection** is a complementary technique that looks for "ghosts" – faint outlines that appear when you save an image at different compression qualities, revealing previous editing.

Think of it like:

- **Noise Analysis** = Checking if fabric threads match across a patched garment
- **JPEG Ghost** = Seeing faint watermarks reappear when you shine light at different angles

## What Does Noise Analysis Measure?

### Noise Analysis:

- **Sensor noise patterns** (unique to each camera)
- **Noise consistency** across image regions
- **Noise variance** (how much random variation exists)
- **Local noise statistics** in different areas

### JPEG Ghost Detection:

- **Compression artifacts** from multiple JPEG saves
- **Quality mismatch** between different image regions
- **Ghost boundaries** where new content was added
- **Double compression signatures**

## How to Interpret Results

### ✅ Normal Patterns (Likely Authentic)

**Noise Analysis:**

- **Uniform noise distribution** across entire image
- **Consistent noise levels** in similar lighting conditions
- **Natural noise variation** matching camera characteristics
- **Higher noise in shadows**, lower in highlights (normal behavior)

**JPEG Ghost:**

- **Minimal ghosting** at all quality levels
- **Uniform appearance** across image
- **No sharp boundaries** in ghost images
- **Consistent compression** throughout

### ⚠️ Suspicious Patterns (Possible Manipulation)

**Noise Analysis:**

1. **Noise Inconsistencies**

   - Some regions too smooth (artificially denoised)
   - Some regions too noisy (added from different camera)
   - Geometric shapes with different noise patterns

2. **Unnatural Smoothness**

   - Copy-pasted objects appear "plastic" or "clean"
   - Background has natural grain, foreground doesn't

3. **Noise Level Mismatch**
   - Dark areas should have more noise than bright areas
   - If reversed, editing likely occurred

**JPEG Ghost:**

1. **Visible Ghost Boundaries**

   - Clear outlines appear at certain quality settings
   - Shows where new content was added

2. **Different Compression Histories**

   - Some regions ghost heavily, others don't
   - Indicates splicing from multiple sources

3. **Quality Mismatch**
   - One part shows double compression, another doesn't

## Common Artifacts Detected

### Noise Analysis Detects:

1. **Splicing/Composite Images**

   - Object pasted from high-quality source onto grainy background
   - Noise patterns don't match at boundaries

2. **Content-Aware Fill**

   - Removed objects leave unnaturally smooth areas
   - Generated pixels lack proper sensor noise

3. **AI-Generated Content**

   - Neural networks produce different noise signatures
   - Too smooth or mathematically perfect patterns

4. **Selective Denoising**

   - Face smoothing filters create noise inconsistencies
   - Skin appears plastic while hair retains natural grain

5. **Copy-Move Forgery**
   - Cloned regions show identical noise patterns
   - Natural photos have unique noise in each area

### JPEG Ghost Detects:

1. **Photoshop Composites**

   - Elements combined from different JPEG files
   - Each element shows different ghosting behavior

2. **Watermark Removal**

   - Ghost reveals faint outline of removed text/logo

3. **Object Insertion**

   - Added objects ghost differently than background

4. **Multiple Editing Sessions**
   - Layer cake of compression from repeated saves

## Visual Analogy

### Noise Analysis:

Imagine examining fabric under a microscope:

- **Authentic photo** = All fabric has same thread density and weave pattern
- **Edited photo** = Patched section has different thread count, obvious seam

### JPEG Ghost:

Like when you erase pencil marks but can still see faint impressions:

- **Original drawing** = Uniform faint impressions everywhere
- **Edited drawing** = New parts show no impressions, old parts have multiple layers

## Real-World Examples

### Case 1: Person Added to Group Photo

**Noise Analysis Shows:**

- Background people: Natural grain pattern
- Added person: Suspiciously smooth, no grain
  **Verdict**: Likely composite

### Case 2: Product Photo with Removed Background

**JPEG Ghost Shows:**

- At Quality 75: Product looks normal
- At Quality 85: Faint outline of original background appears
- At Quality 95: Background ghost very visible
  **Verdict**: Background removed/replaced

### Case 3: Document Forgery

**Noise Analysis Shows:**

- Original text: Normal paper texture noise
- Altered text: Perfectly smooth, mathematical noise
  **Verdict**: Text has been digitally altered

## Limitations

### ⚠️ Important Caveats

1. **Camera Processing**

   - Modern cameras apply heavy in-camera noise reduction
   - This can make even authentic photos look "too smooth"

2. **Low Light vs. Bright Light**

   - Natural photos have noise variation by lighting
   - Dark areas are naturally noisier – not suspicious

3. **Multiple Compressions**

   - Images shared on social media are recompressed
   - This degrades both noise and ghost detection

4. **High-End Cameras**

   - Professional cameras have very low noise even at high ISO
   - Low noise doesn't always mean editing

5. **Intentional Denoising**

   - Photographers often use denoise filters for artistic reasons
   - Not all smoothing indicates forgery

6. **JPEG Ghost False Positives**
   - Complex textures naturally ghost more
   - High-contrast edges produce stronger ghosts

## Best Practices

✔️ **Compare similar regions** (sky to sky, skin to skin)  
✔️ **Test multiple JPEG qualities** (70, 80, 90, 95) for ghosting  
✔️ **Look for boundaries** where noise suddenly changes  
✔️ **Consider lighting** (dark areas should be noisier)  
✔️ **Check for unnatural smoothness** in organic textures  
✔️ **Use with ELA and metadata** for corroboration  
✔️ **Examine high-contrast boundaries** for ghost artifacts

## Key Questions to Ask

### Noise Analysis:

1. Is noise distribution uniform across the image?
2. Do similar lighting conditions show similar noise?
3. Are there unnaturally smooth regions?
4. Does noise level match expected camera behavior?

### JPEG Ghost:

1. Do different quality settings reveal ghost boundaries?
2. Are some regions ghosting while others aren't?
3. Do ghost patterns suggest multiple source images?
4. Can you see faint outlines of removed content?

---

_Noise analysis is like checking if puzzle pieces come from the same puzzle – each camera creates a unique noise "texture." JPEG ghosts are like forensic luminol, revealing the invisible traces of previous editing layers._
