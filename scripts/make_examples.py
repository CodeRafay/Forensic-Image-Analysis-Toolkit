"""Build the demonstration gallery in assets/examples/ from the bundled sample.

Every example is the sample image with one known edit, so the app can show
each technique catching something specific. Run from the repo root:

    python scripts/make_examples.py

It rewrites the images and examples.json, then runs each example's technique
and prints whether it raised a warning/notice (an example that is not caught
should be fixed or dropped, not shipped).
"""
import io
import json
import os
import sys

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import analysis  # noqa: E402

SRC = os.path.join("assets", "sample images", "sampleImg.jpeg")
OUT = os.path.join("assets", "examples")
rng = np.random.default_rng(2024)  # fixed: rebuilds are byte-identical


def jpeg(arr, q):
    """Pixels after one JPEG save at quality q."""
    b = io.BytesIO()
    Image.fromarray(arr).save(b, "JPEG", quality=q)
    return np.array(Image.open(b).convert("RGB"))


base = np.array(Image.open(SRC).convert("RGB"))
H, W = base.shape[:2]
# Patch on the city, away from the UFO and the clouds
Y0, X0, PH, PW = 400, 120, 128, 192
examples = []
os.makedirs(OUT, exist_ok=True)


def add(file, tab, title, edit, fn, save):
    path = os.path.join(OUT, file)
    save(path)
    examples.append({"file": file, "tab": tab, "title": title, "edit": edit,
                     "_fn": fn})


# ELA / JPEG ghost: a patch that went through a low-quality save, pasted
# into an image saved at high quality.
a = base.copy()
a[Y0:Y0 + PH, X0:X0 + PW] = jpeg(base, 50)[Y0:Y0 + PH, X0:X0 + PW]
add("ela_recompressed_patch.jpg", "ELA", "Patch with a different compression history",
    f"A {PW}x{PH} px patch at x={X0}, y={Y0} was saved at JPEG quality 50, "
    "pasted back, and the whole image saved at quality 95.",
    lambda p: analysis.ela.analyze_ela(p, quality=90),
    lambda p: Image.fromarray(a).save(p, quality=95))

gh = base.copy()
gh[Y0:Y0 + PH, X0:X0 + PW] = jpeg(base, 60)[Y0:Y0 + PH, X0:X0 + PW]
add("ghost_q60_patch.jpg", "JPEG", "JPEG ghost of an earlier quality-60 save",
    f"Same kind of edit: a {PW}x{PH} px patch at x={X0}, y={Y0} saved at "
    "quality 60, pasted in, whole image saved at quality 90.",
    analysis.jpeg_ghost.analyze_jpeg_ghost,
    lambda p: Image.fromarray(gh).save(p, quality=90))

# Noise and PRNU need real camera noise at full resolution, which the sample
# lacks (and its sky/city split dominates Splicebuster). They use CC0 iPhone
# 5c photos in source/ (credits in source/CREDITS.md). On two real outdoor
# phone photos (Motorola, Commons) Splicebuster false-alarmed on one clean
# file and missed edits on the other, so the host here is chosen, not typical.
SRC_DIR = os.path.join(OUT, "source")
host = np.array(Image.open(os.path.join(SRC_DIR, "iphone5c_15.jpg")).convert("RGB"))
# Local smoothing, as from a denoise/retouch brush, over 800x600 px
sm = host.copy()
sm[900:1500, 1300:2100] = cv2.GaussianBlur(host, (0, 0), 1.5)[900:1500, 1300:2100]
add("noise_smoothed_region.jpg", "Noise", "Region smoothed with a retouch brush",
    "An iPhone 5c photo (of a watercolour painting) with an 800x600 px region "
    "at x=1300, y=900 smoothed by a Gaussian blur (sigma 1.5), as a denoise "
    "or retouch brush would. Saved at quality 92.",
    analysis.noise_map.analyze_noise,
    lambda p: Image.fromarray(sm).save(p, quality=92))

PRNU_REFS = ["source/iphone5c_10.jpg", "source/iphone5c_27.jpg", "source/iphone5c_15.jpg"]
add("source/iphone5c_01.jpg", "PRNU", "Matched to its camera by sensor noise",
    "An unedited iPhone 5c photo. Its sensor fingerprint is compared with "
    "one built from three other photos taken with the same phone, which the "
    "app loads as references automatically.",
    lambda p: analysis.prnu.analyze_prnu(
        p, reference_paths=[os.path.join(OUT, r) for r in PRNU_REFS]),
    lambda p: None)  # the original camera file, unchanged
examples[-1]["references"] = PRNU_REFS
examples[-1]["_ok"] = lambda r: r["metrics"].get("PCE", 0) > r["metrics"].get("PCE threshold", 60)

# Copy-move: a block of the city cloned elsewhere
c = base.copy()
c[300:300 + PH, 700:700 + PW] = base[Y0:Y0 + PH, X0:X0 + PW]
add("copy_move_clone.jpg", "Copy-Move", "Cloned block of the city",
    f"The {PW}x{PH} px block at x={X0}, y={Y0} was copied to x=700, y=300. "
    "Saved at quality 95. The two smaller cloud clones it also finds were "
    "already in the original sample, which is itself a composite.",
    lambda p: analysis.cmfd.detect_copy_move(p, max_px=2048),
    lambda p: Image.fromarray(c).save(p, quality=95))

# Resampling: whole image enlarged 1.5x, saved lossless
add("resampled_upscale.png", "Resampling", "Image enlarged 1.5x",
    "The whole image was enlarged 1.5x with bicubic interpolation and saved as PNG.",
    analysis.resampling_detector.detect_resampling,
    lambda p: Image.fromarray(base).resize((W * 3 // 2, H * 3 // 2),
                                           Image.BICUBIC).save(p))

# Histogram: contrast stretch, saved lossless
s = np.clip((base.astype(float) - 60) * 1.6, 0, 255).astype(np.uint8)
add("histogram_contrast.png", "Histogram", "Contrast stretched",
    "Levels were stretched (value = (value - 60) x 1.6) and the result saved as PNG.",
    analysis.histogram_analysis.analyze_histogram,
    lambda p: Image.fromarray(s).save(p))

# Steganography: random bits written into the LSB of 40 % of the pixels
g = base.copy()
mask = rng.random(g.shape) < 0.4
g[mask] = (g[mask] & 0xFE) | rng.integers(0, 2, mask.sum(), dtype=np.uint8)
add("stego_lsb.png", "Steganography", "Data hidden in the lowest bits",
    "Random bits were written into the least significant bit of 40 % of the "
    "pixel values (a payload of 0.4 bits per pixel), saved as PNG.",
    analysis.steganography_detection.analyze_lsb,
    lambda p: Image.fromarray(g).save(p))


# Metadata: EXIF that contradicts itself
def save_meta(p):
    exif = Image.Exif()
    exif[0x010F] = "Canon"                        # Make
    exif[0x0110] = "Canon EOS 5D Mark IV"         # Model
    exif[0x0131] = "Adobe Photoshop 25.0"         # Software
    exif[0x0132] = "2023:05:01 10:00:00"          # DateTime (modified)
    ifd = exif.get_ifd(0x8769)
    ifd[0x9003] = "2023:06:15 14:30:00"           # DateTimeOriginal
    ifd[0x9004] = "2023:06:15 14:30:00"           # DateTimeDigitized
    Image.fromarray(base).save(p, quality=95, exif=exif)


add("metadata_inconsistent.jpg", "Metadata", "Contradictory camera metadata",
    "EXIF claims a Canon EOS 5D Mark IV, names Adobe Photoshop as the "
    "software, and gives a modification date six weeks before the capture date.",
    analysis.metadata_analysis.analyze_metadata, save_meta)

if __name__ == "__main__":
    caught_all = True
    for e in examples:
        r = e.pop("_fn")(os.path.join(OUT, e["file"]))
        ok = e.pop("_ok", None)
        hits = [f["text"] for f in r["findings"]
                if (ok and ok(r)) or (not ok and f["level"] in ("warning", "notice"))]
        caught_all &= bool(hits)
        print(f"{'CAUGHT' if hits else 'MISSED'}  {e['file']}: "
              f"{hits[0][:110] if hits else r['summary'][:110]}")
    with open(os.path.join(OUT, "examples.json"), "w", encoding="utf-8") as f:
        json.dump(examples, f, indent=2)
    sys.exit(0 if caught_all else 1)
