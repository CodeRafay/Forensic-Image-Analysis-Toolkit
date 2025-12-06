from analysis import ela
import unittest
import os
from pathlib import Path
from PIL import Image
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestELA(unittest.TestCase):
    """Unit tests for Error Level Analysis module"""

    @classmethod
    def setUpClass(cls):
        """Create test images"""
        cls.test_dir = Path(__file__).parent / "test_images"
        cls.test_dir.mkdir(exist_ok=True)

        # Create a simple test image
        cls.test_image = cls.test_dir / "test.jpg"
        img = Image.new('RGB', (100, 100), color=(128, 128, 128))
        img.save(cls.test_image, 'JPEG', quality=95)

    @classmethod
    def tearDownClass(cls):
        """Clean up test images"""
        if cls.test_image.exists():
            cls.test_image.unlink()
        if cls.test_dir.exists() and not any(cls.test_dir.iterdir()):
            cls.test_dir.rmdir()

    def test_perform_ela_basic(self):
        """Test basic ELA functionality"""
        result = ela.perform_ela(str(self.test_image))

        self.assertIsNotNone(result)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 3)  # ela_img, overlay, metrics

        ela_img, overlay, metrics = result
        self.assertIsNotNone(ela_img)
        self.assertIsNotNone(overlay)
        self.assertIsInstance(metrics, dict)

    def test_ela_with_quality_parameter(self):
        """Test ELA with different quality settings"""
        result_q90 = ela.perform_ela(str(self.test_image), quality=90)
        result_q70 = ela.perform_ela(str(self.test_image), quality=70)

        _, _, metrics_q90 = result_q90
        _, _, metrics_q70 = result_q70

        # Lower quality should produce higher errors
        self.assertGreater(
            metrics_q70.get('mean_error', 0),
            metrics_q90.get('mean_error', 0)
        )

    def test_ela_metrics(self):
        """Test ELA metrics are present"""
        _, _, metrics = ela.perform_ela(str(self.test_image))

        required_keys = ['mean_error', 'max_error', 'std_error']
        for key in required_keys:
            self.assertIn(key, metrics)
            self.assertIsInstance(metrics[key], (int, float))

    def test_ela_with_invalid_path(self):
        """Test ELA with non-existent file"""
        result = ela.perform_ela("nonexistent.jpg")

        # Should return error dict or raise exception
        if isinstance(result, dict):
            self.assertIn('error', result)

    def test_ela_error_scale(self):
        """Test error scale parameter"""
        result1 = ela.perform_ela(str(self.test_image), error_scale=5)
        result2 = ela.perform_ela(str(self.test_image), error_scale=15)

        self.assertIsNotNone(result1)
        self.assertIsNotNone(result2)

    def test_ela_image_output(self):
        """Test that ELA produces valid PIL images"""
        ela_img, overlay, _ = ela.perform_ela(str(self.test_image))

        self.assertIsInstance(ela_img, Image.Image)
        self.assertIsInstance(overlay, Image.Image)
        self.assertEqual(ela_img.size, (100, 100))

    def test_multi_quality_ela(self):
        """Test multi-quality ELA if implemented"""
        if hasattr(ela, 'multi_quality_ela'):
            results = ela.multi_quality_ela(
                str(self.test_image),
                qualities=[70, 85, 95]
            )

            self.assertIsInstance(results, dict)
            self.assertEqual(len(results), 3)


class TestELAEdgeCases(unittest.TestCase):
    """Test edge cases for ELA"""

    @classmethod
    def setUpClass(cls):
        cls.test_dir = Path(__file__).parent / "test_images"
        cls.test_dir.mkdir(exist_ok=True)

    def test_ela_with_png(self):
        """Test ELA with PNG format"""
        png_path = self.test_dir / "test.png"
        img = Image.new('RGB', (50, 50), color=(255, 0, 0))
        img.save(png_path, 'PNG')

        result = ela.perform_ela(str(png_path))

        if isinstance(result, tuple):
            self.assertEqual(len(result), 3)

        png_path.unlink()

    def test_ela_with_small_image(self):
        """Test ELA with very small image"""
        small_path = self.test_dir / "small.jpg"
        img = Image.new('RGB', (10, 10), color=(128, 128, 128))
        img.save(small_path, 'JPEG')

        result = ela.perform_ela(str(small_path))
        self.assertIsNotNone(result)

        small_path.unlink()

    def test_ela_with_large_image(self):
        """Test ELA with larger image"""
        large_path = self.test_dir / "large.jpg"
        img = Image.new('RGB', (1000, 1000), color=(128, 128, 128))
        img.save(large_path, 'JPEG')

        result = ela.perform_ela(str(large_path))
        self.assertIsNotNone(result)

        large_path.unlink()

    @classmethod
    def tearDownClass(cls):
        if cls.test_dir.exists() and not any(cls.test_dir.iterdir()):
            cls.test_dir.rmdir()


if __name__ == '__main__':
    unittest.main()
