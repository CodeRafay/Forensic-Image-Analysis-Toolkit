# 💾 Quantization Table Analysis

## What is a Quantization Table?

The quantization table is the **"recipe" JPEG uses to compress images**. It's a hidden grid of numbers that tells the compression algorithm how much to simplify different frequencies in the image. Every JPEG editor and camera uses slightly different recipes.

Think of it like a **fingerprint of the compression process**:

- Each camera brand has unique quantization tables
- Photo editors have their own tables
- Analyzing these tables reveals the image's compression history

## What Does Quantization Table Analysis Measure?

- **Quantization matrix values** (8×8 grid of compression coefficients)
- **Quality estimation** (approximate JPEG quality level: 0-100)
- **Compression history** (single vs. double compression)
- **Software signatures** (identifies camera/editor used)
- **Table consistency** (does the table match claimed source?)

## How to Interpret Results

### ✅ Normal Patterns (Likely Authentic)

1. **Single Compression**

   - Clean quantization table matching camera manufacturer
   - Quality estimate aligns with camera settings
   - No signs of re-compression

2. **Consistent Software**

   - Table matches known camera brand (Canon, Nikon, Sony)
   - Or matches claimed editing software (if metadata shows editing)

3. **Reasonable Quality**
   - Quality level appropriate for image source
   - Professional cameras: 90-100
   - Phone cameras: 85-95
   - Social media: 70-85

### ⚠️ Suspicious Patterns (Possible Manipulation)

1. **Double Compression**

   - Evidence of two different quantization tables
   - Suggests image was edited and re-saved
   - Different quality levels detected

2. **Quality Mismatch**

   - Low quality (60-70) but metadata claims high-end camera
   - Or suspiciously high quality (95-100) for a phone photo

3. **Software Mismatch**

   - Table indicates Adobe Photoshop
   - But metadata claims "never edited"

4. **Inconsistent Tables**

   - Different parts of image show different quantization
   - Clear sign of splicing from multiple sources

5. **Generic/Unknown Tables**
   - Table doesn't match any known camera or software
   - May indicate custom editing or forgery tools

## Common Artifacts Detected

### 1. **Double Compression (Strongest Indicator)**

**What happens:**

- Original image saved at Quality 95 (Camera)
- Image edited and re-saved at Quality 85 (Photoshop)
- Two overlapping quantization patterns detected

**Visual example:**

```
First Compression:  [Canon EOS table, Q=95]
Second Compression: [Photoshop table, Q=85]
```

**Analysis**: Image was edited after capture

### 2. **Software Fingerprinting**

**Camera Tables:**

- Canon: Characteristic values [16, 11, 10, 16, ...]
- Nikon: Different pattern [8, 6, 5, 8, ...]
- iPhone: Apple-specific tables

**Editor Tables:**

- Photoshop: IJG (Independent JPEG Group) standard
- GIMP: LibJPEG defaults
- Online tools: Generic web-optimized tables

**Detection:**
If metadata says "iPhone 14 Pro" but table shows Photoshop signature → edited!

### 3. **Quality Degradation Chain**

```
Original:     Quality 100 (Camera)
   ↓
Edit 1:       Quality 90  (Photoshop)
   ↓
Edit 2:       Quality 80  (GIMP)
   ↓
Upload:       Quality 70  (Social Media)
```

**Analysis**: Each re-save leaves quantization traces

### 4. **Splicing Detection**

- **Top half of image**: Canon quantization table
- **Bottom half of image**: iPhone quantization table
  **Analysis**: Two images merged together

### 5. **Quality "Too Good to Be True"**

- **Claimed source**: Instagram screenshot
- **Detected quality**: 98 (nearly lossless)
  **Analysis**: Quality impossibly high for claimed source

## Real-World Examples

### Case 1: Fake Celebrity Photo

```
Metadata: "iPhone 13, never edited"
Quantization Analysis:
  - Primary table: iPhone (matches claim)
  - Secondary table: Photoshop detected
  - Quality: 90 → 75 (double compression)
```

**Verdict**: Photo was edited despite metadata claim

### Case 2: Forged Document

```
Claimed: "Scanned from paper at 300 DPI"
Quantization Analysis:
  - Table: Canon DSLR signature
  - Quality: 95 (too high for scanner)
```

**Verdict**: Not a scan, photographed with DSLR, then altered

### Case 3: Social Media Evidence

```
Claimed: "Original photo from Samsung Galaxy"
Quantization Analysis:
  - Table: Twitter/X recompression signature
  - Quality: 85 (social media quality)
```

**Verdict**: This is a downloaded social media copy, not original

## Visual Analogy

Imagine quantization tables like **compression "DNA"**:

**Camera brands** = Different species (Canon DNA vs. Nikon DNA)
**Photo editors** = Lab-created modifications (Photoshop DNA)
**Double compression** = Hybrid DNA showing two parent sources
**Quality level** = DNA completeness (100% vs. 70% intact)

When you find:

- Canon DNA + Photoshop DNA → Photo was edited
- Two different camera DNA patterns → Two photos spliced together
- DNA quality drops → Multiple editing generations

## Limitations

### ⚠️ Important Caveats

1. **Social Media Strips Tables**

   - Platforms like Facebook, Twitter recompress everything
   - Original quantization tables are lost
   - Can only analyze platform's compression

2. **Modern Cameras Pre-Process**

   - In-camera processing applies initial quantization
   - Some editing may be "legitimate" camera processing

3. **Can't Distinguish Why**

   - Table shows editing occurred
   - But can't tell if editing was innocent (crop, rotate) or malicious (forgery)

4. **Lossless Edits Are Invisible**

   - If someone edits using lossless PNG, then converts to JPEG
   - Only final JPEG quantization is visible

5. **Quality Estimates Are Approximate**

   - "Quality 85" is an estimate, not exact
   - Range of ±5 is normal

6. **Custom Tables Possible**
   - Advanced users can use custom quantization tables
   - This can obscure software fingerprints

## Best Practices

✔️ **Compare table to metadata** (does camera match claimed device?)  
✔️ **Look for double compression** (strongest manipulation indicator)  
✔️ **Check quality estimates** (reasonable for source?)  
✔️ **Cross-reference with software tags** in metadata  
✔️ **Test consistency** across image regions  
✔️ **Use with other techniques** (ELA, histogram) for full picture

## Key Questions to Ask

1. Does the quantization table match the claimed camera/source?
2. Is there evidence of double compression?
3. Is the quality level reasonable for this source?
4. Do metadata and quantization table tell the same story?
5. Are different parts of the image using different tables?
6. Does the compression history make logical sense?

## Practical Tips

### Reading Quantization Tables:

- **Lower numbers** = Less compression (higher quality)
- **Higher numbers** = More compression (lower quality)
- **Top-left values** = Most important (low frequencies)
- **Bottom-right values** = Less important (high frequencies)

### Quality Scale:

- **95-100**: Professional/archival quality
- **85-94**: High-quality photos, good cameras
- **75-84**: Standard web quality, social media
- **60-74**: Heavy compression, quality loss visible
- **Below 60**: Severe compression, obvious artifacts

---

_Quantization table analysis is like forensic chemistry – each camera and editor leaves a unique molecular signature. By analyzing these signatures, we can trace the image's journey from capture to current state._
