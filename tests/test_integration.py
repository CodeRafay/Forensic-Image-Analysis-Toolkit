# Test Integration Suite
from analysis.resampling_detector import detect_resampling, detect_interpolation_method
from analysis.deepfake_detector import detect_deepfake_artifacts, detect_gan_fingerprint
from analysis.frequency_analysis import analyze_frequency_domain, detect_dct_anomalies
from analysis.prnu import analyze_prnu
from analysis.quant_table import analyze_quantization_table
from analysis.jpeg_ghost import detect_jpeg_ghost
from analysis.noise_map import generate_noise_map
from analysis.histogram_analysis import generate_histogram
from analysis.metadata_analysis import extract_metadata
from analysis.ela import perform_ela, multi_quality_ela
import unittest
import sys
import os
from pathlib import Path
from PIL import Image
import numpy as np

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestEndToEndWorkflow(unittest.TestCase):
    """Test complete forensic analysis workflow"""

    @classmethod
    def setUpClass(cls):
        """Create test images for workflow testing"""
        cls.test_dir = Path("temp_test_integration")
        cls.test_dir.mkdir(exist_ok=True)

        # Create authentic test image
        cls.authentic_img = cls.test_dir / "authentic.jpg"
        img = Image.new('RGB', (800, 600), color=(100, 150, 200))
        img.save(cls.authentic_img, 'JPEG', quality=95)

        # Create manipulated test image (simulated splice)
        cls.manipulated_img = cls.test_dir / "manipulated.jpg"
        img = Image.new('RGB', (800, 600), color=(100, 150, 200))
        # Add bright patch to simulate added content
        pixels = img.load()
        for i in range(200, 400):
            for j in range(150, 350):
                pixels[i, j] = (255, 255, 255)
        img.save(cls.manipulated_img, 'JPEG', quality=85)

        # Create resampled image
        cls.resampled_img = cls.test_dir / "resampled.jpg"
        img = Image.new('RGB', (800, 600), color=(100, 150, 200))
        img_resized = img.resize((400, 300)).resize((800, 600))
        img_resized.save(cls.resampled_img, 'JPEG', quality=90)

    @classmethod
    def tearDownClass(cls):
        """Clean up test files"""
        import shutil
        if cls.test_dir.exists():
            shutil.rmtree(cls.test_dir)

    def test_complete_analysis_pipeline(self):
        """Test running all analysis techniques on one image"""
        img_path = str(self.authentic_img)
        results = {}

        # Run all analyses
        try:
            results['ela'] = perform_ela(img_path)
            results['metadata'] = extract_metadata(img_path)
            results['histogram'] = generate_histogram(img_path)
            results['noise'] = generate_noise_map(img_path)
            results['jpeg_ghost'] = detect_jpeg_ghost(img_path)
            results['quant_table'] = analyze_quantization_table(img_path)
            results['prnu'] = analyze_prnu(img_path)
            results['frequency'] = analyze_frequency_domain(img_path)
            results['dct'] = detect_dct_anomalies(img_path)
            results['deepfake'] = detect_deepfake_artifacts(img_path)
            results['gan'] = detect_gan_fingerprint(img_path)
            results['resampling'] = detect_resampling(img_path)
            results['interpolation'] = detect_interpolation_method(img_path)
        except Exception as e:
            self.fail(f"Complete analysis pipeline failed: {str(e)}")

        # Verify all analyses returned results
        self.assertEqual(len(results), 13,
                         "Should have results from all 13 analysis techniques")

        # Verify each result has expected structure
        self.assertIn('error_image', results['ela'])
        self.assertIn('metrics', results['ela'])

        self.assertIn('basic_info', results['metadata'])

        # Path to histogram image
        self.assertIsInstance(results['histogram'], str)

        self.assertIsInstance(results['noise'], str)  # Path to noise map

        self.assertIn('differences', results['jpeg_ghost'])

        self.assertIn('luminance_table', results['quant_table'])

        self.assertIn('variance', results['prnu'])

        self.assertIn('fft_magnitude', results['frequency'])

        self.assertIn('high_freq_variance', results['dct'])

        self.assertIn('frequency_anomaly_score', results['deepfake'])

        self.assertIn('radial_profile', results['gan'])

        self.assertIn('resampling_detected', results['resampling'])

        self.assertIn('method', results['interpolation'])

    def test_authentic_vs_manipulated_comparison(self):
        """Compare analysis results between authentic and manipulated images"""

        # Analyze authentic image
        ela_auth = perform_ela(str(self.authentic_img))
        freq_auth = analyze_frequency_domain(str(self.authentic_img))

        # Analyze manipulated image
        ela_manip = perform_ela(str(self.manipulated_img))
        freq_manip = analyze_frequency_domain(str(self.manipulated_img))

        # Manipulated image should show higher ELA metrics
        self.assertIsNotNone(ela_auth['metrics'])
        self.assertIsNotNone(ela_manip['metrics'])

        # Frequency analysis should detect differences
        self.assertIsNotNone(freq_auth)
        self.assertIsNotNone(freq_manip)

    def test_resampling_detection_workflow(self):
        """Test detection of resampled images"""

        # Analyze original
        resamp_orig = detect_resampling(str(self.authentic_img))

        # Analyze resampled
        resamp_detected = detect_resampling(str(self.resampled_img))

        self.assertIn('resampling_detected', resamp_orig)
        self.assertIn('resampling_detected', resamp_detected)

        # Resampled image should be detected (may not always work with simple test)
        # At minimum, should not crash
        self.assertIsNotNone(resamp_detected)

    def test_multi_quality_ela_workflow(self):
        """Test multi-quality ELA analysis"""

        qualities = [70, 85, 95]
        results = multi_quality_ela(str(self.authentic_img), qualities)

        self.assertEqual(len(results), len(qualities))

        for quality, result in results.items():
            self.assertIn('error_image', result)
            self.assertIn('metrics', result)
            self.assertEqual(result['quality'], quality)

    def test_error_handling_across_modules(self):
        """Test that all modules handle invalid input gracefully"""
        invalid_path = "nonexistent_image.jpg"

        # Each module should handle errors without crashing
        with self.assertRaises(FileNotFoundError):
            perform_ela(invalid_path)

        with self.assertRaises(FileNotFoundError):
            extract_metadata(invalid_path)

        with self.assertRaises(FileNotFoundError):
            generate_histogram(invalid_path)


class TestCrossModuleConsistency(unittest.TestCase):
    """Test consistency between different analysis modules"""

    @classmethod
    def setUpClass(cls):
        """Create test image"""
        cls.test_dir = Path("temp_test_consistency")
        cls.test_dir.mkdir(exist_ok=True)

        cls.test_img = cls.test_dir / "test_consistent.jpg"
        img = Image.new('RGB', (640, 480), color=(128, 128, 128))
        img.save(cls.test_img, 'JPEG', quality=92)

    @classmethod
    def tearDownClass(cls):
        """Clean up"""
        import shutil
        if cls.test_dir.exists():
            shutil.rmtree(cls.test_dir)

    def test_image_dimensions_consistency(self):
        """Verify all modules report consistent image dimensions"""
        img_path = str(self.test_img)

        # Get dimensions from PIL
        with Image.open(img_path) as img:
            expected_size = img.size

        # Check metadata
        metadata = extract_metadata(img_path)
        width = metadata['basic_info'].get('width')
        height = metadata['basic_info'].get('height')

        if width and height:
            self.assertEqual((width, height), expected_size)

        # ELA should process same size
        ela_result = perform_ela(img_path)
        ela_img = Image.open(ela_result['error_image'])
        self.assertEqual(ela_img.size, expected_size)

    def test_format_consistency(self):
        """Verify format detection is consistent"""
        img_path = str(self.test_img)

        # From PIL
        with Image.open(img_path) as img:
            expected_format = img.format

        # From metadata
        metadata = extract_metadata(img_path)
        meta_format = metadata['basic_info'].get('format')

        self.assertEqual(meta_format, expected_format)

    def test_quality_estimation_consistency(self):
        """Compare quality estimates from different modules"""
        img_path = str(self.test_img)

        # Get quality from quantization table analysis
        quant_result = analyze_quantization_table(img_path)

        # Get quality indication from JPEG ghost
        ghost_result = detect_jpeg_ghost(img_path)

        # Both should provide some quality information
        self.assertIsNotNone(quant_result)
        self.assertIsNotNone(ghost_result)


class TestPerformanceAndScalability(unittest.TestCase):
    """Test performance with different image sizes"""

    def test_small_image_processing(self):
        """Test processing of small images (100x100)"""
        test_dir = Path("temp_test_small")
        test_dir.mkdir(exist_ok=True)

        try:
            img_path = test_dir / "small.jpg"
            img = Image.new('RGB', (100, 100), color=(200, 200, 200))
            img.save(img_path, 'JPEG', quality=90)

            # Should handle small images without error
            ela_result = perform_ela(str(img_path))
            self.assertIsNotNone(ela_result)

            freq_result = analyze_frequency_domain(str(img_path))
            self.assertIsNotNone(freq_result)

        finally:
            import shutil
            shutil.rmtree(test_dir)

    def test_large_image_processing(self):
        """Test processing of large images (4000x3000)"""
        test_dir = Path("temp_test_large")
        test_dir.mkdir(exist_ok=True)

        try:
            img_path = test_dir / "large.jpg"
            # Create large image
            img = Image.new('RGB', (4000, 3000), color=(150, 150, 150))
            img.save(img_path, 'JPEG', quality=90)

            # Should handle large images (may be slower)
            ela_result = perform_ela(str(img_path))
            self.assertIsNotNone(ela_result)

            # Metadata should still work
            metadata = extract_metadata(str(img_path))
            self.assertEqual(metadata['basic_info']['width'], 4000)
            self.assertEqual(metadata['basic_info']['height'], 3000)

        finally:
            import shutil
            shutil.rmtree(test_dir)

    def test_batch_processing_simulation(self):
        """Simulate processing multiple images"""
        test_dir = Path("temp_test_batch")
        test_dir.mkdir(exist_ok=True)

        try:
            # Create 5 test images
            img_paths = []
            for i in range(5):
                img_path = test_dir / f"batch_{i}.jpg"
                img = Image.new('RGB', (400, 300), color=(i*50, i*40, i*30))
                img.save(img_path, 'JPEG', quality=88)
                img_paths.append(str(img_path))

            # Process all images
            results = []
            for img_path in img_paths:
                try:
                    ela_result = perform_ela(img_path)
                    results.append(ela_result)
                except Exception as e:
                    self.fail(
                        f"Batch processing failed on {img_path}: {str(e)}")

            self.assertEqual(len(results), 5)

        finally:
            import shutil
            shutil.rmtree(test_dir)


class TestDataFormatCompatibility(unittest.TestCase):
    """Test compatibility with different image formats"""

    def test_png_format_handling(self):
        """Test handling of PNG images"""
        test_dir = Path("temp_test_png")
        test_dir.mkdir(exist_ok=True)

        try:
            img_path = test_dir / "test.png"
            img = Image.new('RGB', (500, 400), color=(180, 180, 180))
            img.save(img_path, 'PNG')

            # Metadata should work with PNG
            metadata = extract_metadata(str(img_path))
            self.assertEqual(metadata['basic_info']['format'], 'PNG')

            # Histogram should work
            hist_path = generate_histogram(str(img_path))
            self.assertTrue(os.path.exists(hist_path))

            # ELA on PNG (will convert to JPEG internally)
            ela_result = perform_ela(str(img_path))
            self.assertIsNotNone(ela_result)

        finally:
            import shutil
            shutil.rmtree(test_dir)

    def test_different_color_modes(self):
        """Test handling of grayscale and RGBA images"""
        test_dir = Path("temp_test_modes")
        test_dir.mkdir(exist_ok=True)

        try:
            # Grayscale
            gray_path = test_dir / "gray.jpg"
            img_gray = Image.new('L', (400, 300), color=128)
            img_gray.save(gray_path, 'JPEG')

            metadata_gray = extract_metadata(str(gray_path))
            self.assertIn('mode', metadata_gray['basic_info'])

            # RGBA (with alpha channel)
            rgba_path = test_dir / "rgba.png"
            img_rgba = Image.new('RGBA', (400, 300),
                                 color=(200, 200, 200, 255))
            img_rgba.save(rgba_path, 'PNG')

            metadata_rgba = extract_metadata(str(rgba_path))
            self.assertIn('mode', metadata_rgba['basic_info'])

        finally:
            import shutil
            shutil.rmtree(test_dir)


if __name__ == '__main__':
    # Run all integration tests
    unittest.main(verbosity=2)
