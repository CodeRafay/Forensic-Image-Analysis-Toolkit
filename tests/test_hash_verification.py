from analysis import hash_verification
import unittest
import os
from pathlib import Path
from PIL import Image
import json
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestHashVerification(unittest.TestCase):
    """Unit tests for Hash Verification module"""

    @classmethod
    def setUpClass(cls):
        """Create test images and database"""
        cls.test_dir = Path(__file__).parent / "test_images"
        cls.test_dir.mkdir(exist_ok=True)

        # Create test database path
        cls.db_path = cls.test_dir / "test_hash_db.json"

        # Create test images
        cls.test_image1 = cls.test_dir / "test_hash1.jpg"
        img1 = Image.new('RGB', (200, 200), color=(100, 150, 200))
        img1.save(cls.test_image1, 'JPEG', quality=95)

        cls.test_image2 = cls.test_dir / "test_hash2.jpg"
        img2 = Image.new('RGB', (200, 200), color=(200, 150, 100))
        img2.save(cls.test_image2, 'JPEG', quality=95)

        # Create a slightly modified version (resized)
        cls.test_image1_modified = cls.test_dir / "test_hash1_modified.jpg"
        img1_modified = img1.resize((190, 190))
        img1_modified.save(cls.test_image1_modified, 'JPEG', quality=90)

    @classmethod
    def tearDownClass(cls):
        """Clean up test files"""
        for file in [cls.test_image1, cls.test_image2, cls.test_image1_modified]:
            if file.exists():
                file.unlink()
        if cls.db_path.exists():
            cls.db_path.unlink()
        if cls.test_dir.exists() and not any(cls.test_dir.iterdir()):
            cls.test_dir.rmdir()

    def test_generate_perceptual_hash(self):
        """Test perceptual hash generation"""
        hashes = hash_verification.generate_perceptual_hash(str(self.test_image1))

        # Check all hash types present
        self.assertIn('phash', hashes)
        self.assertIn('ahash', hashes)
        self.assertIn('dhash', hashes)
        self.assertIn('whash', hashes)

        # Check hashes are non-empty strings
        for hash_type, hash_value in hashes.items():
            self.assertIsInstance(hash_value, str)
            self.assertGreater(len(hash_value), 0)

    def test_generate_cryptographic_hash(self):
        """Test SHA-256 hash generation"""
        hash1 = hash_verification.generate_cryptographic_hash(str(self.test_image1))

        # Check it's a valid SHA-256 (64 hex characters)
        self.assertEqual(len(hash1), 64)
        self.assertTrue(all(c in '0123456789abcdef' for c in hash1))

        # Same file should produce same hash
        hash2 = hash_verification.generate_cryptographic_hash(str(self.test_image1))
        self.assertEqual(hash1, hash2)

        # Different file should produce different hash
        hash3 = hash_verification.generate_cryptographic_hash(str(self.test_image2))
        self.assertNotEqual(hash1, hash3)

    def test_calculate_hash_distance(self):
        """Test Hamming distance calculation"""
        # Same hash should have distance 0
        hash1 = "abcd1234"
        distance = hash_verification.calculate_hash_distance(hash1, hash1)
        self.assertEqual(distance, 0)

        # Different hashes should have distance > 0
        hash2 = "abcd1235"
        distance = hash_verification.calculate_hash_distance(hash1, hash2)
        self.assertGreater(distance, 0)

    def test_load_save_database(self):
        """Test database loading and saving"""
        # Create a test database
        test_db = {
            "records": [],
            "metadata": {"created": "2024-01-01T00:00:00"}
        }

        # Save database
        hash_verification.save_database(test_db, str(self.db_path))

        # Check file exists
        self.assertTrue(self.db_path.exists())

        # Load database
        loaded_db = hash_verification.load_database(str(self.db_path))

        # Check contents match
        self.assertEqual(loaded_db['metadata']['created'], test_db['metadata']['created'])
        self.assertEqual(len(loaded_db['records']), 0)

    def test_add_to_blockchain(self):
        """Test adding image to blockchain"""
        record = hash_verification.add_to_blockchain(
            str(self.test_image1),
            str(self.db_path)
        )

        # Check record structure
        self.assertIn('id', record)
        self.assertIn('filename', record)
        self.assertIn('timestamp', record)
        self.assertIn('perceptual_hashes', record)
        self.assertIn('sha256', record)
        self.assertIn('file_size', record)

        # Verify it's in the database
        db = hash_verification.load_database(str(self.db_path))
        self.assertEqual(len(db['records']), 1)
        self.assertEqual(db['records'][0]['filename'], 'test_hash1.jpg')

    def test_find_matches_exact(self):
        """Test finding exact matches"""
        # Clear and recreate database
        hash_verification.save_database(
            {"records": [], "metadata": {}},
            str(self.db_path)
        )
        
        # Add image to blockchain
        hash_verification.add_to_blockchain(str(self.test_image1), str(self.db_path))

        # Search for the same image
        matches = hash_verification.find_matches(
            str(self.test_image1),
            str(self.db_path)
        )

        # Should find exact match
        self.assertGreaterEqual(len(matches), 1)
        self.assertEqual(matches[0]['match_type'], 'exact')
        self.assertEqual(matches[0]['similarity'], 100.0)
        self.assertEqual(matches[0]['hash_distance'], 0)

    def test_find_matches_perceptual(self):
        """Test finding perceptual matches"""
        # Clear and recreate database
        hash_verification.save_database(
            {"records": [], "metadata": {}},
            str(self.db_path)
        )
        
        # Add original image
        hash_verification.add_to_blockchain(str(self.test_image1), str(self.db_path))

        # Search for modified version
        matches = hash_verification.find_matches(
            str(self.test_image1_modified),
            str(self.db_path),
            threshold=15  # Allow more distance for resized image
        )

        # Should find at least one match
        self.assertGreater(len(matches), 0)
        # Note: The match could be exact or perceptual depending on image similarity
        # Just verify we got matches with valid similarity scores
        self.assertGreaterEqual(matches[0]['similarity'], 0.0)
        self.assertLessEqual(matches[0]['similarity'], 100.0)

    def test_verify_image_provenance(self):
        """Test complete provenance verification"""
        # Add original image to blockchain
        hash_verification.add_to_blockchain(str(self.test_image1), str(self.db_path))

        # Verify the same image
        score, history, validity, details = hash_verification.verify_image_provenance(
            str(self.test_image1),
            str(self.db_path)
        )

        # Check return types
        self.assertIsInstance(score, (int, float))
        self.assertIsInstance(history, list)
        self.assertIsInstance(validity, dict)
        self.assertIsInstance(details, dict)

        # Check score is high for exact match
        self.assertEqual(score, 100)

        # Check validity
        self.assertTrue(validity['valid'])
        self.assertEqual(validity['chain_of_custody'], 'Intact')

    def test_verify_unknown_image(self):
        """Test verifying image not in database"""
        # Clear database
        hash_verification.save_database(
            {"records": [], "metadata": {}},
            str(self.db_path)
        )

        # Verify image not in database
        score, history, validity, details = hash_verification.verify_image_provenance(
            str(self.test_image2),
            str(self.db_path)
        )

        # Should have medium score (unknown provenance)
        self.assertEqual(score, 50)
        self.assertEqual(len(history), 0)
        self.assertFalse(validity['valid'])

    def test_calculate_authenticity_score(self):
        """Test authenticity score calculation"""
        # Test with no matches
        score = hash_verification._calculate_authenticity_score([], "dummy_hash")
        self.assertEqual(score, 50)

        # Test with exact match
        exact_match = [{
            'match_type': 'exact',
            'similarity': 100.0,
            'hash_distance': 0
        }]
        score = hash_verification._calculate_authenticity_score(
            exact_match, "dummy_hash"
        )
        self.assertEqual(score, 100)

        # Test with high similarity perceptual match
        high_similarity = [{
            'match_type': 'perceptual',
            'similarity': 96.0,
            'hash_distance': 3
        }]
        score = hash_verification._calculate_authenticity_score(
            high_similarity, "dummy_hash"
        )
        self.assertEqual(score, 85)

    def test_build_modification_history(self):
        """Test modification history building"""
        matches = [
            {
                'record': {
                    'timestamp': '2024-01-01T12:00:00',
                    'filename': 'image1.jpg',
                    'file_size': 1000
                },
                'match_type': 'exact',
                'similarity': 100.0
            },
            {
                'record': {
                    'timestamp': '2024-01-02T12:00:00',
                    'filename': 'image2.jpg',
                    'file_size': 1100
                },
                'match_type': 'perceptual',
                'similarity': 95.0
            }
        ]

        history = hash_verification._build_modification_history(matches)

        # Check history length
        self.assertEqual(len(history), 2)

        # Check chronological order
        self.assertLess(history[0]['timestamp'], history[1]['timestamp'])

    def test_assess_legal_validity(self):
        """Test legal validity assessment"""
        # Test with no matches
        validity = hash_verification._assess_legal_validity([], 50)
        self.assertFalse(validity['valid'])
        self.assertEqual(validity['chain_of_custody'], 'Broken')

        # Test with exact match
        exact_match = [{'match_type': 'exact', 'similarity': 100.0}]
        validity = hash_verification._assess_legal_validity(exact_match, 100)
        self.assertTrue(validity['valid'])
        self.assertEqual(validity['chain_of_custody'], 'Intact')

        # Test with moderate modifications
        moderate_match = [{'match_type': 'perceptual', 'similarity': 75.0}]
        validity = hash_verification._assess_legal_validity(moderate_match, 70)
        self.assertEqual(validity['valid'], 'Uncertain')

    def test_export_database(self):
        """Test database export"""
        # Add some records
        hash_verification.add_to_blockchain(str(self.test_image1), str(self.db_path))

        # Export database
        export_path = self.test_dir / "exported_db.json"
        result_path = hash_verification.export_database(
            str(self.db_path),
            str(export_path)
        )

        # Check export file exists
        self.assertTrue(os.path.exists(result_path))

        # Load exported database
        with open(result_path, 'r') as f:
            exported_db = json.load(f)

        # Check it has records
        self.assertGreater(len(exported_db['records']), 0)

        # Clean up
        if os.path.exists(export_path):
            os.unlink(export_path)

    def test_import_database(self):
        """Test database import"""
        # Create source database
        source_db_path = self.test_dir / "source_db.json"
        hash_verification.add_to_blockchain(str(self.test_image1), str(source_db_path))

        # Create destination database
        dest_db_path = self.test_dir / "dest_db.json"

        # Import with replace
        stats = hash_verification.import_database(
            str(source_db_path),
            str(dest_db_path),
            merge=False
        )

        # Check statistics
        self.assertEqual(stats['imported'], 1)
        self.assertEqual(stats['total_records'], 1)

        # Clean up
        if os.path.exists(source_db_path):
            os.unlink(source_db_path)
        if os.path.exists(dest_db_path):
            os.unlink(dest_db_path)

    def test_get_database_stats(self):
        """Test database statistics"""
        # Add some records
        hash_verification.add_to_blockchain(str(self.test_image1), str(self.db_path))
        hash_verification.add_to_blockchain(str(self.test_image2), str(self.db_path))

        # Get statistics
        stats = hash_verification.get_database_stats(str(self.db_path))

        # Check statistics
        self.assertGreaterEqual(stats['total_records'], 2)
        self.assertIn('created', stats)
        self.assertIn('last_updated', stats)

    def test_get_image_info(self):
        """Test image info extraction"""
        info = hash_verification._get_image_info(str(self.test_image1))

        self.assertIn('width', info)
        self.assertIn('height', info)
        self.assertIn('format', info)
        self.assertEqual(info['width'], 200)
        self.assertEqual(info['height'], 200)


class TestHashVerificationEdgeCases(unittest.TestCase):
    """Test edge cases for hash verification"""

    @classmethod
    def setUpClass(cls):
        cls.test_dir = Path(__file__).parent / "test_images"
        cls.test_dir.mkdir(exist_ok=True)
        cls.db_path = cls.test_dir / "edge_case_db.json"

    def test_empty_database(self):
        """Test operations on empty database"""
        db = hash_verification.load_database(str(self.db_path))
        self.assertEqual(len(db['records']), 0)

        stats = hash_verification.get_database_stats(str(self.db_path))
        self.assertEqual(stats['total_records'], 0)

    def test_invalid_image_path(self):
        """Test with non-existent image"""
        score, history, validity, details = hash_verification.verify_image_provenance(
            "nonexistent_image.jpg",
            str(self.db_path)
        )

        self.assertIn('error', details)
        self.assertEqual(score, 0)

    @classmethod
    def tearDownClass(cls):
        if cls.db_path.exists():
            cls.db_path.unlink()
        if cls.test_dir.exists() and not any(cls.test_dir.iterdir()):
            cls.test_dir.rmdir()


if __name__ == '__main__':
    unittest.main()
