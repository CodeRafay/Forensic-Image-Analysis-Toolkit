from analysis import metadata_analysis
import unittest
import os
from pathlib import Path
from PIL import Image
import piexif
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestMetadataAnalysis(unittest.TestCase):
    """Unit tests for Metadata Analysis module"""

    @classmethod
    def setUpClass(cls):
        """Create test images with metadata"""
        cls.test_dir = Path(__file__).parent / "test_images"
        cls.test_dir.mkdir(exist_ok=True)

        # Create JPEG with EXIF
        cls.jpeg_with_exif = cls.test_dir / "with_exif.jpg"
        img = Image.new('RGB', (100, 100), color=(255, 255, 255))

        # Add basic EXIF
        exif_dict = {
            "0th": {
                piexif.ImageIFD.Make: b"TestCamera",
                piexif.ImageIFD.Model: b"TestModel v1",
                piexif.ImageIFD.Software: b"TestSoftware 1.0",
            },
            "Exif": {
                piexif.ExifIFD.DateTimeOriginal: b"2024:01:01 12:00:00",
                piexif.ExifIFD.ISO: 100,
            },
        }
        exif_bytes = piexif.dump(exif_dict)
        img.save(cls.jpeg_with_exif, 'JPEG', exif=exif_bytes)

        # Create JPEG without EXIF
        cls.jpeg_without_exif = cls.test_dir / "without_exif.jpg"
        img.save(cls.jpeg_without_exif, 'JPEG')

        # Create PNG (no EXIF support)
        cls.png_file = cls.test_dir / "test.png"
        img.save(cls.png_file, 'PNG')

    @classmethod
    def tearDownClass(cls):
        """Clean up test images"""
        for file in [cls.jpeg_with_exif, cls.jpeg_without_exif, cls.png_file]:
            if file.exists():
                file.unlink()
        if cls.test_dir.exists() and not any(cls.test_dir.iterdir()):
            cls.test_dir.rmdir()

    def test_extract_metadata_with_exif(self):
        """Test metadata extraction from image with EXIF"""
        metadata = metadata_analysis.extract_metadata(str(self.jpeg_with_exif))

        self.assertIsInstance(metadata, dict)
        self.assertIn('basic_info', metadata)
        self.assertIn('exif', metadata)

    def test_extract_metadata_without_exif(self):
        """Test metadata extraction from image without EXIF"""
        metadata = metadata_analysis.extract_metadata(
            str(self.jpeg_without_exif))

        self.assertIsInstance(metadata, dict)
        self.assertIn('basic_info', metadata)
        # Should still have basic info even without EXIF
        self.assertIsNotNone(metadata['basic_info'])

    def test_extract_metadata_from_png(self):
        """Test metadata extraction from PNG"""
        metadata = metadata_analysis.extract_metadata(str(self.png_file))

        self.assertIsInstance(metadata, dict)
        # PNG should have basic info
        self.assertIn('basic_info', metadata)

    def test_metadata_basic_info(self):
        """Test that basic info is present"""
        metadata = metadata_analysis.extract_metadata(str(self.jpeg_with_exif))

        basic_info = metadata.get('basic_info', {})
        self.assertIn('filename', basic_info)
        self.assertIn('file_size_bytes', basic_info)

    def test_metadata_camera_info(self):
        """Test camera information extraction"""
        metadata = metadata_analysis.extract_metadata(str(self.jpeg_with_exif))

        # Check if camera info was extracted
        if 'camera' in metadata and metadata['camera']:
            self.assertIsInstance(metadata['camera'], dict)

    def test_invalid_file_path(self):
        """Test with non-existent file"""
        metadata = metadata_analysis.extract_metadata("nonexistent.jpg")

        # Should return error or empty dict
        self.assertIsInstance(metadata, dict)

    def test_metadata_structure(self):
        """Test metadata dictionary structure"""
        metadata = metadata_analysis.extract_metadata(str(self.jpeg_with_exif))

        expected_sections = [
            'basic_info', 'exif', 'gps', 'camera',
            'software', 'timestamps', 'thumbnail', 'warnings'
        ]

        for section in expected_sections:
            self.assertIn(section, metadata)

    def test_metadata_warnings(self):
        """Test that warnings section exists"""
        metadata = metadata_analysis.extract_metadata(str(self.jpeg_with_exif))

        self.assertIn('warnings', metadata)
        self.assertIsInstance(metadata['warnings'], list)


class TestMetadataHelpers(unittest.TestCase):
    """Test helper functions in metadata module"""

    @classmethod
    def setUpClass(cls):
        cls.test_dir = Path(__file__).parent / "test_images"
        cls.test_dir.mkdir(exist_ok=True)

        cls.test_image = cls.test_dir / "test.jpg"
        img = Image.new('RGB', (100, 100))
        img.save(cls.test_image, 'JPEG')

    @classmethod
    def tearDownClass(cls):
        if cls.test_image.exists():
            cls.test_image.unlink()
        if cls.test_dir.exists() and not any(cls.test_dir.iterdir()):
            cls.test_dir.rmdir()

    def test_thumbnail_detection(self):
        """Test thumbnail detection if function exists"""
        if hasattr(metadata_analysis, 'detect_thumbnail_mismatch'):
            result = metadata_analysis.detect_thumbnail_mismatch(
                str(self.test_image)
            )
            self.assertIsInstance(result, (dict, bool, tuple))


if __name__ == '__main__':
    unittest.main()
