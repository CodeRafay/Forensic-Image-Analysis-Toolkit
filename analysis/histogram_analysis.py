from pathlib import Path
import matplotlib.pyplot as plt
from PIL import Image
import matplotlib
matplotlib.use('Agg')


def generate_histogram(image_path):
    """
    Generates a histogram visualization of the image.

    Args:
        image_path (str): Path to the image file

    Returns:
        str: Path to the saved histogram image, or None on error
    """
    try:
        img = Image.open(image_path).convert('RGB')

        # Create temp directory if needed
        temp_dir = Path(__file__).parent.parent / "temp"
        temp_dir.mkdir(exist_ok=True)

        hist_path = temp_dir / 'temp_histogram.png'

        # Create histogram
        plt.figure(figsize=(10, 5))

        # Extract channel data
        r, g, b = img.split()

        plt.hist(list(r.getdata()), bins=256,
                 color='r', alpha=0.5, label='Red')
        plt.hist(list(g.getdata()), bins=256,
                 color='g', alpha=0.5, label='Green')
        plt.hist(list(b.getdata()), bins=256,
                 color='b', alpha=0.5, label='Blue')

        plt.xlabel('Pixel Intensity')
        plt.ylabel('Frequency')
        plt.title('RGB Histogram Analysis')
        plt.legend()
        plt.tight_layout()
        plt.savefig(str(hist_path), dpi=100)
        plt.close()

        return str(hist_path)

    except Exception as e:
        print(f"Error in histogram analysis: {e}")
        return None
