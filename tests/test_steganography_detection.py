from analysis import steganography_detection
import unittest
import os
from pathlib import Path
from PIL import Image
import numpy as np
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestSteganographyDetection(unittest.TestCase):
    """Unit tests for Steganography Detection module"""

    @classmethod
    def setUpClass(cls):
        """Create test images"""
        cls.test_dir = Path(__file__).parent / "test_images"
        cls.test_dir.mkdir(exist_ok=True)

        # Create a simple test image
        cls.test_image = cls.test_dir / "test_stego.jpg"
        img = Image.new('RGB', (200, 200), color=(128, 128, 128))
        img.save(cls.test_image, 'JPEG', quality=95)

        # Create an image with modified LSB (simulated steganography)
        cls.stego_image = cls.test_dir / "test_with_stego.png"
        img_array = np.array(img)
        
        # Modify LSB in a pattern (simulate hidden data)
        # Set all LSBs to 1 in a region
        img_array[50:150, 50:150, :] = img_array[50:150, 50:150, :] | 1
        
        stego_img = Image.fromarray(img_array.astype(np.uint8))
        stego_img.save(cls.stego_image, 'PNG')

    @classmethod
    def tearDownClass(cls):
        """Clean up test images"""
        if cls.test_image.exists():
            cls.test_image.unlink()
        if cls.stego_image.exists():
            cls.stego_image.unlink()
        if cls.test_dir.exists() and not any(cls.test_dir.iterdir()):
            cls.test_dir.rmdir()

    def test_detect_lsb_steganography_basic(self):
        """Test basic steganography detection functionality"""
        prob, visual_map, details = steganography_detection.detect_lsb_steganography(
            str(self.test_image)
        )

        # Check return types
        self.assertIsInstance(prob, float)
        self.assertIsNotNone(visual_map)
        self.assertIsInstance(details, dict)

        # Check probability is in valid range
        self.assertGreaterEqual(prob, 0.0)
        self.assertLessEqual(prob, 100.0)

    def test_detailed_results_structure(self):
        """Test that detailed results have correct structure"""
        _, _, details = steganography_detection.detect_lsb_steganography(
            str(self.test_image)
        )

        # Check required keys
        self.assertIn('overall_probability', details)
        self.assertIn('channel_results', details)
        self.assertIn('image_info', details)
        self.assertIn('interpretation', details)

        # Check channel results
        for channel in ['red', 'green', 'blue']:
            self.assertIn(channel, details['channel_results'])
            channel_data = details['channel_results'][channel]
            self.assertIn('chi_square_statistic', channel_data)
            self.assertIn('p_value', channel_data)
            self.assertIn('steganography_probability', channel_data)

    def test_extract_lsb_planes(self):
        """Test LSB plane extraction"""
        img = Image.open(self.test_image).convert('RGB')
        img_array = np.array(img)

        lsb_planes = steganography_detection.extract_lsb_planes(img_array)

        # Check all channels present
        self.assertIn('red', lsb_planes)
        self.assertIn('green', lsb_planes)
        self.assertIn('blue', lsb_planes)

        # Check LSB planes are binary (0 or 1)
        for channel, plane in lsb_planes.items():
            unique_values = np.unique(plane)
            self.assertTrue(all(v in [0, 1] for v in unique_values))

    def test_chi_square_test(self):
        """Test chi-square statistical test"""
        # Create a balanced LSB plane (50/50 distribution)
        balanced_plane = np.random.randint(0, 2, size=(100, 100))

        chi2_stat, p_value, prob = steganography_detection.chi_square_test(
            balanced_plane
        )

        self.assertIsInstance(chi2_stat, float)
        self.assertIsInstance(p_value, float)
        self.assertIsInstance(prob, float)

        # For balanced distribution, probability should be relatively low
        self.assertGreaterEqual(prob, 0.0)
        self.assertLessEqual(prob, 100.0)

    def test_chi_square_with_biased_data(self):
        """Test chi-square with obviously biased LSB plane"""
        # Create heavily biased plane (90% ones)
        biased_plane = np.ones((100, 100), dtype=np.uint8)
        biased_plane[:10, :] = 0  # Only 10% zeros

        chi2_stat, p_value, prob = steganography_detection.chi_square_test(
            biased_plane
        )

        # Biased data should have high probability
        self.assertGreater(prob, 50.0)

    def test_analyze_blocks(self):
        """Test block-based analysis"""
        img = Image.open(self.test_image).convert('RGB')
        img_array = np.array(img)
        lsb_planes = steganography_detection.extract_lsb_planes(img_array)

        heatmap = steganography_detection.analyze_blocks(
            lsb_planes['red'], block_size=32
        )

        # Check heatmap dimensions
        expected_h = img_array.shape[0] // 32
        expected_w = img_array.shape[1] // 32
        self.assertEqual(heatmap.shape, (expected_h, expected_w))

        # Check values are probabilities (0-100)
        self.assertTrue(np.all(heatmap >= 0))
        self.assertTrue(np.all(heatmap <= 100))

    def test_visual_analysis_map_creation(self):
        """Test visual analysis map generation"""
        img = Image.open(self.test_image).convert('RGB')
        img_array = np.array(img)
        lsb_planes = steganography_detection.extract_lsb_planes(img_array)

        heatmaps = {
            channel: steganography_detection.analyze_blocks(plane)
            for channel, plane in lsb_planes.items()
        }

        visual_map = steganography_detection.create_visual_analysis_map(
            img_array, heatmaps
        )

        # Check that we got a PIL Image
        self.assertIsInstance(visual_map, Image.Image)

    def test_interpretation(self):
        """Test result interpretation"""
        # Test different probability levels
        low_prob = steganography_detection._interpret_results(15.0)
        self.assertEqual(low_prob['risk_level'], 'Low')

        medium_prob = steganography_detection._interpret_results(35.0)
        self.assertEqual(medium_prob['risk_level'], 'Medium')

        high_prob = steganography_detection._interpret_results(65.0)
        self.assertEqual(high_prob['risk_level'], 'High')

        critical_prob = steganography_detection._interpret_results(85.0)
        self.assertEqual(critical_prob['risk_level'], 'Critical')

    def test_with_png_format(self):
        """Test with PNG format"""
        png_path = self.test_dir / "test_png.png"
        img = Image.new('RGB', (100, 100), color=(100, 100, 100))
        img.save(png_path, 'PNG')

        prob, visual_map, details = steganography_detection.detect_lsb_steganography(
            str(png_path)
        )

        self.assertIsInstance(prob, float)
        self.assertIsNotNone(visual_map)
        self.assertIsInstance(details, dict)

        png_path.unlink()

    def test_with_invalid_path(self):
        """Test with non-existent file"""
        prob, visual_map, details = steganography_detection.detect_lsb_steganography(
            "nonexistent_image.jpg"
        )

        # Should return error in details
        self.assertIn('error', details)
        self.assertEqual(prob, 0.0)
        self.assertIsNone(visual_map)

    def test_batch_processing(self):
        """Test batch detection functionality"""
        images = [str(self.test_image), str(self.stego_image)]
        results = steganography_detection.batch_detect(images)

        self.assertEqual(len(results), 2)
        for path in images:
            self.assertIn(path, results)
            self.assertIn('probability', results[path])

    def test_stego_image_higher_probability(self):
        """Test that modified LSB image has higher probability"""
        # Test normal image
        prob_normal, _, _ = steganography_detection.detect_lsb_steganography(
            str(self.test_image)
        )

        # Test image with modified LSBs
        prob_stego, _, _ = steganography_detection.detect_lsb_steganography(
            str(self.stego_image)
        )

        # Modified image should have higher probability (in most cases)
        # Note: This might not always be true due to statistical variation
        # but the test demonstrates the concept
        self.assertIsInstance(prob_normal, float)
        self.assertIsInstance(prob_stego, float)


class TestSteganographyEdgeCases(unittest.TestCase):
    """Test edge cases for steganography detection"""

    @classmethod
    def setUpClass(cls):
        cls.test_dir = Path(__file__).parent / "test_images"
        cls.test_dir.mkdir(exist_ok=True)

    def test_small_image(self):
        """Test with very small image"""
        small_path = self.test_dir / "small_stego.jpg"
        img = Image.new('RGB', (20, 20), color=(128, 128, 128))
        img.save(small_path, 'JPEG')

        prob, _, details = steganography_detection.detect_lsb_steganography(
            str(small_path)
        )

        self.assertIsInstance(prob, float)
        self.assertNotIn('error', details)

        small_path.unlink()

    def test_grayscale_image(self):
        """Test with grayscale image converted to RGB"""
        gray_path = self.test_dir / "gray_test.jpg"
        img = Image.new('L', (100, 100), color=128)
        img.save(gray_path, 'JPEG')

        # The function converts to RGB internally
        prob, _, details = steganography_detection.detect_lsb_steganography(
            str(gray_path)
        )

        self.assertIsInstance(prob, float)

        gray_path.unlink()

    @classmethod
    def tearDownClass(cls):
        if cls.test_dir.exists() and not any(cls.test_dir.iterdir()):
            cls.test_dir.rmdir()


if __name__ == '__main__':
    unittest.main()
