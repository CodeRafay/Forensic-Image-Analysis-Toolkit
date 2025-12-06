# 🕵️ Error Level Analysis (ELA)

## What is ELA?

Error Level Analysis is like a **detective looking for touch-ups in a photograph**. When you edit a digital image and save it as JPEG, the edited areas compress differently than the original areas. ELA highlights these compression differences to reveal potential manipulations.

Think of it like this: Imagine a painting where some areas have been repainted. The new paint (edited regions) will look slightly different from the old paint (original regions) under special lighting. ELA is that "special lighting" for digital images.

## What Does ELA Measure?

- **Compression inconsistencies** across the image
- **Difference in error levels** between original and edited regions
- **Block-level anomalies** in 8×8 JPEG compression blocks
- **Noise patterns** that deviate from camera sensor characteristics

## How to Interpret Results

### ✅ Normal Patterns (Likely Authentic)

- **Uniform brightness** across the entire ELA image
- **Consistent error levels** in similar texture regions
- **Natural noise distribution** matching camera characteristics
- **Low overall error scores** (typically < 20)

### ⚠️ Suspicious Patterns (Possible Manipulation)

- **Bright spots or regions** standing out dramatically
- **Sharp boundaries** between high and low error areas
- **Inconsistent compression** in regions that should be similar
- **Geometric shapes** with different error levels than surroundings
- **High error scores** (> 30) in specific regions

## Common Artifacts Detected

1. **Copy-Paste Forgeries**

   - Pasted regions show different compression levels
   - Bright outlines around inserted objects

2. **Content Addition/Removal**

   - Edited areas glow brighter than untouched regions
   - "Halo effects" around manipulated objects

3. **Splicing Attacks**

   - Images combined from multiple sources show error level boundaries
   - Different compression histories become visible

4. **Enhancement Filters**

   - Sharpening, blurring, or color adjustments create error patterns
   - Processed regions show higher error levels

5. **Cloning/Stamp Tool**
   - Cloned regions may show different error levels than source
   - Repeated patterns with varying compression

## Visual Analogy

Imagine you have a document that's been photocopied multiple times:

- **Original text** (never edited) = uniform, consistent quality
- **Whited-out and retyped sections** = obvious differences in ink darkness
- **Cut-and-paste sections** = visible boundaries and quality mismatches

ELA works similarly, but for digital compression instead of photocopy quality.

## Limitations

### ⚠️ Important Caveats

1. **Not Foolproof**

   - High error levels don't always mean forgery
   - Complex textures naturally produce higher errors

2. **Quality Dependent**

   - Works best on JPEG images that haven't been heavily compressed
   - Multiple saves degrade detection capability

3. **Can Produce False Positives**

   - Text overlays (watermarks, captions) often glow bright
   - High-contrast edges (windows, signs) may appear suspicious
   - Highly textured areas (grass, fabric) show naturally high errors

4. **Resolution Matters**

   - Low-resolution images are harder to analyze
   - Downscaling can mask manipulation evidence

5. **Professional Forgeries**
   - Skilled forgers can match compression levels
   - Double-compression at same quality reduces detection

## Best Practices

✔️ **Use ELA as part of a multi-technique analysis**  
✔️ **Compare with other tools** (metadata, noise analysis, copy-move detection)  
✔️ **Consider context** (what should the image look like naturally?)  
✔️ **Test multiple quality settings** (70, 85, 90, 95)  
✔️ **Look for patterns**, not just bright spots

---

_ELA is a powerful first-pass tool but should never be used in isolation for forensic conclusions._
