# 📈 Frequency Domain Analysis (FFT & DCT)

## What is Frequency Domain Analysis?

Frequency analysis examines images in "frequency space" rather than pixel space – like analyzing music by frequency (bass, treble) instead of by individual sound waves.

**FFT (Fast Fourier Transform)** breaks down an image into frequency components, revealing how much "smoothness" vs. "detail" exists.

**DCT (Discrete Cosine Transform)** analyzes JPEG compression patterns by looking at the coefficients JPEG uses internally.

Think of it like:

- **X-ray vision** that sees underlying structure instead of surface appearance
- **Radio spectrum analyzer** showing what frequencies dominate
- **Doctor's MRI** revealing what's happening inside rather than just looking at skin

## What Does FFT Measure?

- **Power-law slope** — real photographs lose detail at a characteristic rate
  (a 1/f² falloff, slope near **-2.0**). This is the primary signal.
- **High-frequency content** (sharp edges, details, noise) as a share of total power
- **Low-frequency content** (smooth areas, gradients)
- **Natural patterns** (how real images should look)

> **Note on phase:** earlier versions scored "phase consistency". That metric was
> removed because it is mathematically constant — the standard deviation of a
> spectrum's phase converges to 1.814 for *every* image, so it never carried any
> information. It is still reported under technical details, but not scored.

## What Does DCT Measure?

- **JPEG blockiness** — how much stronger edges are *on* the 8×8 grid than
  elsewhere. 1.00 means no grid is visible.
- **Compression artifacts** (quantization patterns)
- **Frequency distribution** (smooth vs. detailed vs. noisy content)
- **High-frequency anomalies** (sharpening, noise)
- **Per-block texture energy** (shown as the block map)

## How to Interpret Results

### ✅ Normal FFT Patterns (Likely Authentic)

1. **Balanced Frequency Content**

   - Both high and low frequencies present
   - Natural mix of detail and smoothness
   - **Authenticity Score: 75+**

2. **Natural Power-Law Falloff**

   - Spectrum slope between **-3.0 and -1.5** (natural photos sit near -2.0)
   - Detail fades with frequency the way real optics and sensors produce
   - **Risk Level: Low**
   - For reference: white noise measures ~0.0, a heavily blurred image ~-3.3

3. **Smooth Spectral Distribution**
   - No strange spikes or peaks
   - Energy distributed naturally across spectrum
   - **Interpretation**: "Natural image composition"

### ⚠️ Suspicious FFT Patterns

1. **Excessive High Frequencies**

   - Too much sharpness and detail
   - Over-sharpened filters applied
   - **Authenticity Score: 45-60**
   - **Warning**: "Artificial sharpening detected"

2. **Abnormally Smooth (Low Frequencies)**

   - Too much smoothing
   - Over-processed or AI-generated
   - **Risk Level: Medium/High**
   - **Warning**: "Excessive smoothing or possible AI generation"

3. **Spectrum Departs From the Power Law**
   - Slope flatter than -1.5 → added noise, sharpening, or synthetic content
   - Slope steeper than -3.0 → blur, heavy denoising, or upscaling
   - **Verdict**: "Suspicious frequency characteristics"

### ✅ Normal DCT Patterns (Likely Authentic)

1. **Natural Content Mix**

   - Smooth areas (%): 30-40
   - Textures (%): 40-50
   - Edges/Noise (%): 15-25
   - **Score: 70+**

2. **No Visible JPEG Grid**

   - Blockiness ratio below **1.10** (1.00 = no grid at all)
   - Edges on the 8×8 boundaries are no stronger than edges elsewhere
   - Consistent with light or no recompression

3. **Good Compression Quality**
   - Quality indicator: 7-10
   - No excessive quantization artifacts
   - Clean frequency transitions

### ⚠️ Suspicious DCT Patterns

1. **Unnatural Content Distribution**

   - Too much smoothness (>60% low-freq)
   - Too much noise (>30% high-freq)
   - **Score: 40-65**
   - **Warning**: "Artificial content generation suspected"

2. **Strong JPEG Grid**

   - Blockiness ratio above **1.30**
   - Edges line up on the 8×8 compression grid
   - For reference: a clean photo measures ~1.01, the same photo resaved at
     quality 50 measures ~1.23, and at quality 20 ~1.63
   - Suggests heavy or repeated compression

3. **Compression Artifacts**
   - Excessive quantization patterns
   - Grid-like artifacts visible
   - **Anomaly**: "JPEG grid artifacts detected"
   - Suggests multiple compressions or aggressive editing

## Common Artifacts Detected

### FFT Detects:

1. **AI-Generated Content**

   - Overly smooth, mathematically perfect patterns
   - Power-law slope outside the natural -3.0 to -1.5 band
   - **Authentic Score: 30-50**

2. **Artificial Sharpening**

   - Excessive high-frequency spikes
   - Halos around edges
   - **Warning**: "Over-sharpening detected"

3. **Excessive Smoothing/Blurring**

   - Suppressed high frequencies
   - Plastic or artificial appearance
   - **Warning**: "Artificial blur filter applied"

4. **Splicing Effects**
   - Different frequency components in different regions
   - Spliced areas may carry a different power-law slope than the host image
   - **Risk**: "Possible splicing detected"

### DCT Detects:

1. **Multiple JPEG Compressions**

   - Block-level variance inconsistencies
   - Layered quantization patterns
   - **Anomaly**: "Multiple compression cycles detected"

2. **Content-Aware Edits**

   - Fill regions show different DCT patterns
   - Filled areas often lack the host image's compression grid
   - **Warning**: "Generated/filled content detected"

3. **Unnatural Texture Distribution**

   - Percentages outside natural ranges
   - Too smooth or too noisy
   - **Verdict**: "Possible synthetic content"

4. **Selective Processing**
   - Different blocks show different quality
   - Suggests region-by-region editing
   - **Anomaly**: "Region-specific compression detected"

## Visual Examples

### FFT Visualization Interpretation:

```
Natural Photo:          Over-Sharpened:         Over-Smoothed:
  Bright ring            Spiky halo              Flat center
  Center & edges mix     Extreme edges           Darkened edges
  Balanced pattern       Concentrated at top     Concentrated at bottom
```

**Analysis**: Natural photo shows balanced energy; processed images show concentrated patterns

### DCT Visualization Interpretation:

**Left image** (DCT Coefficients):

- Brightness = coefficient magnitude
- Center = low frequencies (smooth)
- Edges = high frequencies (detail)
- **Natural**: Gradual brightness fall-off
- **Suspicious**: Uneven or blocky patterns

**Right image** (Block Texture Map):

- Green = Flat, low-detail blocks
- Yellow = Moderate texture
- Red = High-detail blocks
- This map shows **where the detail is**, mirroring the image's own content —
  it is a texture overview, not a suspicion score. Sky reads green, foliage
  reads red, and that is expected. Judge compression from the blockiness ratio
  above, not from this map's colours.

## Authenticity Scoring Explained

### FFT Score (0-100):

- **Power-Law Slope (0-50 pts)**
  - 50 pts when the slope sits between -3.0 and -1.5
  - 25 pts for a near miss, 0 for a sharp departure
- **High-Frequency Content (0-50 pts)**
  - 50 pts when 0.2%-3% of spectral power sits above half-Nyquist
  - 20 pts when it is well below (over-smooth) or well above (noisy/sharpened)

**Overall Scores:**

- 80-100: Likely authentic
- 60-79: Uncertain, requires other techniques
- <60: Suspicious, possible manipulation

For reference, measured on the bundled sample: an authentic photo scores **100**,
a heavily blurred copy **45**, an oversharpened copy **45**, and pure noise **20**.

### DCT Score (0-100):

- **Frequency Distribution (0-30 pts)**
- **High-Frequency Content (0-30 pts)**
- **JPEG Blockiness (0-25 pts)** — 25 below 1.10, 15 below 1.30, 5 above
- **Quantization Patterns (0-15 pts)**

## Limitations

### ⚠️ FFT Limitations

1. **AI-Generated Detection Hard**

   - Modern AI creates surprisingly natural-looking frequency patterns
   - May pass FFT analysis even if synthetic

2. **Compression Obscures Patterns**

   - JPEG compression degrades frequency information
   - Heavy compression can mask manipulation signs

3. **Context-Dependent**

   - Scene type affects natural frequency content
   - Texture-heavy scenes naturally have high frequencies
   - Sky-dominated scenes naturally smooth

4. **False Positives**
   - Artistic photography may have unusual patterns
   - High-contrast scenes create edge artifacts

### ⚠️ DCT Limitations

1. **JPEG-Specific**

   - Only works well on JPEG images
   - PNG and other formats don't use DCT

2. **Social Media Compression**

   - Platforms recompress to near-invisibility
   - Original DCT patterns destroyed

3. **Professional Editing**

   - Skilled editors can preserve natural DCT patterns
   - Modern tools make DCT forgery easier

4. **Multiple Sources**
   - Can't always identify source of edited regions
   - Just shows _that_ editing occurred

## Best Practices

✔️ **Use both FFT and DCT** for comprehensive analysis  
✔️ **Consider image type** (what should this scene look like?)  
✔️ **Look at specific regions** (is whole image suspicious or just parts?)  
✔️ **Compare authenticity score** with other techniques  
✔️ **Examine visualizations** for obvious anomalies  
✔️ **Check warnings** for specific issues detected  
✔️ **Read interpretations** for context-aware analysis  
✔️ **Remember: These are supporting tools**, not definitive proof

## Key Questions to Ask

### FFT:

1. Is the authenticity score above 75?
2. Do the findings show mostly ✓ (normal) or ⚠ (suspicious) items?
3. Are warnings specific to known manipulation types?
4. Does the interpretation match what you see visually?

### DCT:

1. Are the content percentages in natural ranges?
2. Is the JPEG blockiness ratio below 1.10?
3. Do anomalies make sense for this image source?
4. Are there signs of multiple compressions?

---

_Frequency analysis is like X-ray vision for images – it reveals underlying structure and patterns invisible to the eye. Combined with visual analysis and other techniques, FFT and DCT provide powerful evidence for authentication or manipulation detection._
