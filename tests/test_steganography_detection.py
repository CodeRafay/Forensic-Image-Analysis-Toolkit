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

        # Use real photographic content. The PoV test keys off histograms
        # being *lumpy*, which is true of photographs but not of synthetic
        # gradients: a smooth ramp plus Gaussian noise has a locally linear
        # histogram, so its PoV pairs are already equal and it reads as
        # embedded even when clean. A flat colour image is worse still — one
        # populated value, nothing to test.
        sample = (Path(__file__).parent.parent /
                  "assets" / "sample images" / "sampleImg.jpeg")
        if not sample.exists():
            raise unittest.SkipTest(f"sample image missing: {sample}")

        base = np.array(Image.open(sample).convert('RGB'))

        # Clean reference: no embedding. Saved as PNG so the round-trip is
        # lossless — re-encoding as JPEG would rewrite every LSB.
        cls.test_image = cls.test_dir / "test_stego.png"
        Image.fromarray(base).save(cls.test_image, 'PNG')
        cls.clean_array = base

        # Steganographic image: LSBs replaced with random data, which is what
        # real LSB embedding does. Forcing LSBs to 1 (the previous fixture)
        # makes the plane maximally lopsided — the opposite of the signature.
        rng = np.random.default_rng(1234)
        stego = base.copy()
        flat = stego.reshape(-1)
        flat[:] = (flat & 0xFE) | rng.integers(
            0, 2, flat.size, dtype=np.uint8)
        cls.stego_image = cls.test_dir / "test_with_stego.png"
        Image.fromarray(stego).save(cls.stego_image, 'PNG')

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

    def test_pov_chi_square_returns_valid_range(self):
        """Test PoV chi-square test output types and range"""
        channel = self.clean_array[:, :, 0]

        chi2_stat, p_value, prob, valid_pairs = \
            steganography_detection.pov_chi_square_test(channel)

        self.assertIsInstance(chi2_stat, float)
        self.assertIsInstance(p_value, float)
        self.assertIsInstance(prob, float)
        self.assertIsInstance(valid_pairs, int)

        self.assertGreaterEqual(prob, 0.0)
        self.assertLessEqual(prob, 100.0)

    def test_pov_chi_square_flags_embedded_data(self):
        """A channel whose LSBs are random reads as embedded; a clean one does not.

        Note the direction: LSB embedding equalises the two members of each
        Pair-of-Values, so a HIGH score means equalised means suspicious.
        A lopsided LSB plane is evidence *against* embedding, not for it.
        """
        clean = self.clean_array[:, :, 0]
        stego = np.array(Image.open(self.stego_image).convert('RGB'))[:, :, 0]

        _, _, clean_prob, _ = steganography_detection.pov_chi_square_test(clean)
        _, _, stego_prob, _ = steganography_detection.pov_chi_square_test(stego)

        self.assertLess(clean_prob, 20.0)
        self.assertGreater(stego_prob, 80.0)

    def test_pov_chi_square_insufficient_data(self):
        """A flat image populates too few pairs to test; report no evidence."""
        flat = np.full((100, 100), 128, dtype=np.uint8)

        chi2_stat, _, prob, valid_pairs = \
            steganography_detection.pov_chi_square_test(flat)

        self.assertLess(valid_pairs, 2)
        self.assertEqual(chi2_stat, 0.0)
        self.assertEqual(prob, 0.0)

    def test_analyze_blocks(self):
        """Test block-based analysis"""
        img_array = self.clean_array

        # analyze_blocks takes full channel values, not the LSB plane
        heatmap = steganography_detection.analyze_blocks(
            img_array[:, :, 0], block_size=32
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
        img_array = self.clean_array

        heatmaps = {
            name: steganography_detection.analyze_blocks(
                img_array[:, :, idx], block_size=32)
            for idx, name in enumerate(('red', 'green', 'blue'))
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
        """An LSB-embedded image must score higher than the clean original."""
        prob_normal, _, _ = steganography_detection.detect_lsb_steganography(
            str(self.test_image)
        )
        prob_stego, _, _ = steganography_detection.detect_lsb_steganography(
            str(self.stego_image)
        )

        self.assertGreater(prob_stego, prob_normal)

    def test_clean_image_not_flagged(self):
        """Regression: a clean image must not be reported as suspicious.

        The previous global 50/50 LSB balance test had a statistic that grew
        with pixel count, so a natural sub-1% imbalance saturated it and clean
        multi-megapixel images scored as "High" risk.
        """
        prob, _, details = steganography_detection.detect_lsb_steganography(
            str(self.test_image)
        )

        self.assertLess(prob, 20.0)
        self.assertEqual(details['interpretation']['risk_level'], 'Low')

    def test_score_is_scale_invariant(self):
        """A clean image must not score higher merely for having more pixels.

        Crops of the same clean photograph, 16x apart in pixel count. The old
        global-balance statistic grew linearly with pixel count, so the larger
        crop would score far higher despite being equally clean.
        """
        probs = []
        for size in (128, 512):
            crop = self.clean_array[:size, :size]
            path = self.test_dir / f"scale_{size}.png"
            Image.fromarray(crop).save(path, 'PNG')
            prob, _, _ = steganography_detection.detect_lsb_steganography(
                str(path))
            probs.append(prob)
            path.unlink()

        for size, prob in zip((128, 512), probs):
            self.assertLess(prob, 20.0, f"clean {size}px crop scored {prob}")


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
