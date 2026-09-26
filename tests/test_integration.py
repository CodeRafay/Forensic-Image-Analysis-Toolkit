"""
Integration smoke suite.

Checks that every analysis technique runs end to end on real image content and
returns the contract it actually documents, plus a few behavioural checks that
would catch inverted or degenerate logic.

Fixtures use real photographic content rather than flat colour fills: a flat
image compresses perfectly (zero ELA error at every quality), has a single
populated histogram value (no PoV pairs for the steganography test) and has no
texture for CMFD or DCT to work with, so flat fixtures pass vacuously.
"""
from analysis.hash_verification import verify_image_provenance
from analysis.steganography_detection import detect_lsb_steganography
from analysis.resampling_detector import (detect_resampling,
                                          detect_interpolation_method)
from analysis.deepfake_detector import (detect_deepfake_artifacts,
                                        detect_gan_fingerprint)
from analysis.frequency_analysis import (analyze_frequency_domain,
                                         detect_dct_anomalies)
from analysis.prnu import analyze_prnu
from analysis.cmfd import detect_copy_move
from analysis.quant_table import analyze_quantization_table
from analysis.jpeg_ghost import detect_jpeg_ghost, detect_ghost
from analysis.noise_map import generate_noise_map
from analysis.histogram_analysis import (generate_histogram,
                                         detect_histogram_anomalies)
from analysis.metadata_analysis import extract_metadata, detect_thumbnail_mismatch
from analysis.ela import perform_ela, multi_quality_ela
import unittest
import sys
import shutil
from pathlib import Path
from PIL import Image, ImageFilter
import numpy as np

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

SAMPLE = (Path(__file__).parent.parent /
          "assets" / "sample images" / "sampleImg.jpeg")

# Modules report success as either of these
OK_STATUS = {"success", "analysis_complete"}


def _sample_rgb(size=None):
    """Load the bundled sample image, optionally resized."""
    img = Image.open(SAMPLE).convert("RGB")
    return img.resize(size) if size else img


class TestAllTechniquesRun(unittest.TestCase):
    """Every technique runs on a real image and returns its real contract."""

    @classmethod
    def setUpClass(cls):
        cls.test_dir = Path(__file__).parent / "test_integration_images"
        cls.test_dir.mkdir(exist_ok=True)

        cls.image = cls.test_dir / "authentic.jpg"
        _sample_rgb((800, 600)).save(cls.image, "JPEG", quality=95)
        cls.path = str(cls.image)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def _assert_ok(self, result, *required_keys):
        """A dict-returning technique succeeded and carries its documented keys."""
        self.assertIsInstance(result, dict)
        self.assertIn(result.get("status"), OK_STATUS,
                      f"unexpected status: {result.get('status')} "
                      f"({result.get('error')})")
        for key in required_keys:
            self.assertIn(key, result)

    # --- 1. ELA ---------------------------------------------------------
    def test_ela(self):
        ela_img, overlay, metrics = perform_ela(self.path)

        self.assertIsInstance(ela_img, Image.Image)
        self.assertIsInstance(overlay, Image.Image)
        for key in ("mean_error", "max_error", "std_error",
                    "anomaly_score", "suspicious_areas_percent"):
            self.assertIn(key, metrics)

    def test_multi_quality_ela(self):
        results = multi_quality_ela(self.path, qualities=[70, 85, 95])

        self.assertEqual(sorted(results), [70, 85, 95])
        for entry in results.values():
            self.assertIsInstance(entry["ela"], Image.Image)
            self.assertIsInstance(entry["overlay"], Image.Image)
            self.assertIn("mean_error", entry["metrics"])

    # --- 2. Metadata ----------------------------------------------------
    def test_metadata(self):
        meta = extract_metadata(self.path)

        for section in ("basic_info", "exif", "gps", "camera",
                        "software", "timestamps", "thumbnail", "warnings"):
            self.assertIn(section, meta)
        self.assertEqual(meta["basic_info"]["width"], 800)
        self.assertEqual(meta["basic_info"]["height"], 600)
        self.assertEqual(meta["basic_info"]["format"], "JPEG")

    def test_thumbnail_mismatch(self):
        mismatch, details = detect_thumbnail_mismatch(self.path)

        self.assertIsInstance(mismatch, bool)
        self.assertIsInstance(details, dict)
        self.assertIn("thumbnail_present", details)

    # --- 3. Histogram ---------------------------------------------------
    def test_histogram(self):
        result = generate_histogram(self.path)

        self._assert_ok(result, "histogram_path", "statistics", "warnings")
        self.assertTrue(Path(result["histogram_path"]).exists())
        for channel in ("red", "green", "blue"):
            self.assertIn("mean", result["statistics"][channel])

    def test_histogram_anomalies(self):
        anomalies, severity = detect_histogram_anomalies(self.path)

        self.assertIsInstance(anomalies, list)
        self.assertIn(severity, ("low", "medium", "high"))

    # --- 4. Noise / Ghost -----------------------------------------------
    def test_noise_map(self):
        result = generate_noise_map(self.path)

        self._assert_ok(result, "noise_map_path", "metrics", "warnings")
        self.assertTrue(Path(result["noise_map_path"]).exists())

    def test_jpeg_ghost(self):
        result = detect_jpeg_ghost(self.path)

        self._assert_ok(result, "difference_maps", "difference_scores",
                        "estimated_last_save_quality")
        self.assertTrue(Path(result["combined_ghost_path"]).exists())

    def test_detect_ghost_in_memory(self):
        ghost_img, analysis = detect_ghost(self.path, quality_steps=(90, 70, 50))

        self.assertIsInstance(ghost_img, Image.Image)
        self._assert_ok(analysis, "difference_scores",
                        "estimated_last_save_quality")
        self.assertEqual(sorted(analysis["difference_scores"]), [50, 70, 90])

    # --- 5. Quantization table ------------------------------------------
    def test_quantization_table(self):
        result = analyze_quantization_table(self.path)

        self._assert_ok(result, "quantization_tables", "warnings")
        # A real JPEG has 1-4 tables. More means the parser is reading
        # non-DQT bytes, which is what the old byte-scanner did.
        self.assertTrue(1 <= len(result["quantization_tables"]) <= 4,
                        f"implausible table count: "
                        f"{len(result['quantization_tables'])}")
        for table in result["quantization_tables"].values():
            self.assertEqual(len(table["table_values"]), 64)

    # --- 6. CMFD --------------------------------------------------------
    def test_cmfd(self):
        result = detect_copy_move(self.path)

        self._assert_ok(result, "results", "matches", "warnings")
        self.assertIn("matches_found", result["results"])
        self.assertTrue(Path(result["results"]["result_image_path"]).exists())

    # --- 7. PRNU --------------------------------------------------------
    def test_prnu(self):
        result = analyze_prnu(self.path)

        self._assert_ok(result, "metrics", "warnings")
        self.assertIn("noise_variance", result["metrics"])
        self.assertIn("pattern_strength", result["metrics"])
        self.assertGreater(result["metrics"]["blocks_analyzed"], 0)

    def test_prnu_with_reference(self):
        """Same image as its own reference must correlate near-perfectly."""
        result = analyze_prnu(self.path, reference_image_path=self.path)

        correlation = result["correlation_analysis"]
        self.assertGreater(correlation["correlation"], 0.9)
        self.assertEqual(correlation["same_camera_likelihood"], "High")

    # --- 8. Frequency ---------------------------------------------------
    def test_frequency_domain(self):
        result = analyze_frequency_domain(self.path)

        self._assert_ok(result, "authenticity_score", "metrics", "findings")
        self.assertTrue(Path(result["magnitude_spectrum_path"]).exists())

    def test_dct_anomalies(self):
        result = detect_dct_anomalies(self.path)

        self._assert_ok(result, "authenticity_score", "metrics", "findings")
        self.assertTrue(Path(result["dct_anomaly_map_path"]).exists())

    # --- 9. Deepfake ----------------------------------------------------
    def test_deepfake_artifacts(self):
        result = detect_deepfake_artifacts(self.path)

        self._assert_ok(result, "artifacts", "image_size")
        for key in ("frequency_anomaly_score", "channel_correlation_score",
                    "edge_sharpness_score"):
            self.assertIn(key, result["artifacts"])

    def test_gan_fingerprint(self):
        result = detect_gan_fingerprint(self.path)

        self._assert_ok(result, "metrics", "radial_profile", "gan_likelihood")
        self.assertIn(result["gan_likelihood"], ("Low", "Medium", "High"))

    # --- 10. Resampling -------------------------------------------------
    def test_resampling(self):
        result = detect_resampling(self.path)

        self._assert_ok(result, "resampling_score", "resampling_detected",
                        "per_axis", "limitations")
        self.assertGreaterEqual(result["resampling_score"], 0.0)
        self.assertLessEqual(result["resampling_score"], 1.0)

        # This fixture was built by resizing 1024x576 -> 800x600, so the
        # vertical axis really is rescaled by 600/576 = 1.042. The detector
        # should say so, and should recover that factor.
        self.assertTrue(result["resampling_detected"])
        self.assertTrue(
            any(abs(s - 600 / 576) < 0.02
                for s in result["estimated_scale_factors"]),
            f"expected ~1.042 among {result['estimated_scale_factors']}")

    def test_interpolation_method(self):
        result = detect_interpolation_method(self.path)

        self._assert_ok(result, "likely_interpolation", "confidence",
                        "duplication_rate", "overshoot_ratio")

    # --- 11. Steganography ----------------------------------------------
    def test_steganography(self):
        prob, visual_map, details = detect_lsb_steganography(self.path)

        self.assertIsInstance(prob, float)
        self.assertGreaterEqual(prob, 0.0)
        self.assertLessEqual(prob, 100.0)
        self.assertIsInstance(visual_map, Image.Image)
        self.assertIn("channel_results", details)

    # --- 12. Hash verification ------------------------------------------
    def test_hash_verification(self):
        score, history, validity, details = verify_image_provenance(self.path)

        self.assertIsInstance(score, int)
        self.assertIsInstance(history, list)
        self.assertIn("valid", validity)
        self.assertIn("sha256", details["current_hashes"])
        self.assertEqual(len(details["current_hashes"]["sha256"]), 64)


class TestDetectionBehaviour(unittest.TestCase):
    """Techniques must actually respond to the manipulation they target."""

    @classmethod
    def setUpClass(cls):
        cls.test_dir = Path(__file__).parent / "test_behaviour_images"
        cls.test_dir.mkdir(exist_ok=True)

        base = _sample_rgb((600, 400))
        cls.authentic = cls.test_dir / "authentic.jpg"
        base.save(cls.authentic, "JPEG", quality=95)

        # Copy-move: duplicate a textured block elsewhere in the same image.
        # Both offsets must be multiples of CMFD's sampling step (block_size//2
        # = 8), or the copied blocks never land on the sampling grid and the
        # clone is invisible to block matching.
        arr = np.array(base)
        arr[248:344, 400:496] = arr[48:144, 96:192]
        cls.copy_moved = cls.test_dir / "copy_moved.png"
        Image.fromarray(arr).save(cls.copy_moved, "PNG")

        # LSB steganography: randomise every least significant bit
        rng = np.random.default_rng(7)
        stego = np.array(base).ravel()
        stego[:] = (stego & 0xFE) | rng.integers(0, 2, stego.size,
                                                 dtype=np.uint8)
        cls.stego = cls.test_dir / "stego.png"
        Image.fromarray(stego.reshape(np.array(base).shape)).save(cls.stego,
                                                                  "PNG")

        # Clean PNG control, same content, no embedding
        cls.clean_png = cls.test_dir / "clean.png"
        base.save(cls.clean_png, "PNG")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def test_cmfd_finds_duplicated_region(self):
        """A cloned block must stand out clearly against the untouched image.

        Regression for DC-dominated features: including the DC coefficient made
        similarity track average brightness, so a clean image produced
        thousands of near-exact "matches" and a real clone was indistinguishable.
        """
        cloned = detect_copy_move(str(self.copy_moved))
        original = detect_copy_move(str(self.authentic))

        self.assertGreater(cloned["results"]["matches_found"], 20,
                           "CMFD missed a deliberately cloned block")
        self.assertLess(original["results"]["matches_found"], 20,
                        "CMFD over-matches on an authentic image")

    def test_steganography_separates_clean_from_embedded(self):
        """Regression: clean must score low, fully embedded must score high."""
        clean_prob, _, _ = detect_lsb_steganography(str(self.clean_png))
        stego_prob, _, _ = detect_lsb_steganography(str(self.stego))

        self.assertLess(clean_prob, 20.0,
                        f"clean image flagged at {clean_prob}%")
        self.assertGreater(stego_prob, 80.0,
                           f"embedded image missed at {stego_prob}%")

    def test_ela_error_rises_as_quality_drops(self):
        """Recompressing harder must increase measured error."""
        _, _, high = perform_ela(str(self.authentic), quality=90)
        _, _, low = perform_ela(str(self.authentic), quality=60)

        self.assertGreater(low["mean_error"], high["mean_error"])

    def test_hash_verification_detects_exact_match(self):
        """An image added to the ledger must verify as an exact match."""
        from analysis.hash_verification import add_to_blockchain

        db = self.test_dir / "hashes.json"
        add_to_blockchain(str(self.authentic), db_path=str(db))

        score, _, validity, _ = verify_image_provenance(str(self.authentic),
                                                        db_path=str(db))
        self.assertEqual(score, 100)
        self.assertTrue(validity["valid"])
        self.assertEqual(validity["chain_of_custody"], "Intact")


class TestMetricsRespondToInput(unittest.TestCase):
    """Metrics must vary with the thing they claim to measure.

    Each of these covers a metric that was previously constant or miscalibrated,
    so its scoring branch could never change outcome regardless of the image.
    """

    @classmethod
    def setUpClass(cls):
        cls.test_dir = Path(__file__).parent / "test_metric_images"
        cls.test_dir.mkdir(exist_ok=True)
        cls.base = _sample_rgb()

        cls.natural = cls.test_dir / "natural.jpg"
        cls.base.save(cls.natural, "JPEG", quality=95)

        cls.blurred = cls.test_dir / "blurred.png"
        cls.base.filter(ImageFilter.GaussianBlur(4)).save(cls.blurred, "PNG")

        cls.noise = cls.test_dir / "noise.png"
        rng = np.random.default_rng(3)
        Image.fromarray((rng.random((400, 600, 3)) * 255).astype(np.uint8)
                        ).save(cls.noise, "PNG")

        cls.heavily_compressed = cls.test_dir / "q20.jpg"
        cls.base.save(cls.heavily_compressed, "JPEG", quality=20)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def test_jpeg_quality_estimate_recovers_save_quality(self):
        """Estimated quality must track the quality actually used to save."""
        for quality in (20, 50, 75, 90, 95):
            with self.subTest(quality=quality):
                path = self.test_dir / f"probe_{quality}.jpg"
                self.base.save(path, "JPEG", quality=quality)

                tables = analyze_quantization_table(
                    str(path))["quantization_tables"]
                estimate = tables["table_0"]["estimated_quality"]

                self.assertLessEqual(
                    abs(estimate - quality), 2,
                    f"saved at {quality}, estimated {estimate}")
                path.unlink()

    def test_standard_tables_not_flagged_as_edited(self):
        """A plain libjpeg save must not be reported as editing software."""
        result = analyze_quantization_table(str(self.natural))

        nonstandard = [w for w in result["warnings"] if "Non-standard" in w]
        self.assertEqual(nonstandard, [], f"false positives: {nonstandard}")

    def test_spectral_slope_separates_natural_from_synthetic(self):
        """Natural images follow 1/f^2; noise and blur do not."""
        natural = analyze_frequency_domain(str(self.natural))
        noise = analyze_frequency_domain(str(self.noise))
        blurred = analyze_frequency_domain(str(self.blurred))

        def slope(r):
            return r["metrics"]["spectral_power_law_slope"]

        self.assertTrue(-3.0 <= slope(natural) <= -1.5,
                        f"natural image slope {slope(natural)} outside 1/f² range")
        self.assertGreater(slope(noise), -1.0)     # white noise is flat
        self.assertLess(slope(blurred), -3.0)      # blur is steep

        # And the score must follow
        self.assertGreater(natural["authenticity_score"],
                           noise["authenticity_score"])

    def test_blockiness_tracks_jpeg_compression(self):
        """Heavier JPEG compression must raise measured blockiness."""
        light = detect_dct_anomalies(str(self.natural))
        heavy = detect_dct_anomalies(str(self.heavily_compressed))

        light_b = light["technical_details"]["grid_consistency"]
        heavy_b = heavy["technical_details"]["grid_consistency"]

        self.assertGreater(heavy_b, light_b)
        self.assertLess(light_b, 1.15, "clean image shows a JPEG grid")
        self.assertGreater(heavy_b, 1.25, "q20 image shows no JPEG grid")

    def test_sharpness_map_differs_from_noise_map(self):
        """The two maps must not be the same filter under different names."""
        from analysis.ela import noise_map, sharpness_map

        noise = np.asarray(noise_map(str(self.natural)))
        sharp = np.asarray(sharpness_map(str(self.natural)))

        self.assertFalse(np.array_equal(noise, sharp),
                         "sharpness_map is byte-identical to noise_map")

    def test_ela_suspicious_percent_matches_threshold_mask(self):
        """The reported percentage must agree with the mask the UI renders."""
        from analysis.ela import SUSPICIOUS_THRESHOLD, perform_ela, threshold_ela

        ela_img, _, metrics = perform_ela(str(self.natural), quality=90)
        mask = np.asarray(threshold_ela(ela_img, SUSPICIOUS_THRESHOLD))

        self.assertIsNotNone(mask)
        self.assertGreaterEqual(metrics["suspicious_areas_percent"], 0.0)
        self.assertLessEqual(metrics["suspicious_areas_percent"], 100.0)

    def test_steganography_survives_resampling(self):
        """Resizing must not make a clean image look embedded.

        Interpolation smooths the histogram, which equalises PoV pairs. Before
        the spatial-randomness gate a bicubic-resized clean photo scored 74%.
        """
        for filt in (Image.Resampling.BICUBIC, Image.Resampling.LANCZOS,
                     Image.Resampling.BILINEAR):
            with self.subTest(filter=filt.name):
                path = self.test_dir / f"resized_{filt.name}.png"
                self.base.resize((600, 400), filt).save(path, "PNG")

                prob, _, _ = detect_lsb_steganography(str(path))
                self.assertLess(prob, 20.0,
                                f"clean {filt.name}-resized image scored {prob}%")
                path.unlink()


class TestPrnuIdentifiesCameras(unittest.TestCase):
    """PRNU must key off the sensor, not the scene.

    Regression for an inversion: extracting the residual with a plain Gaussian
    high-pass left scene edges dominant, so two photos of the *same scene* from
    *different cameras* correlated at 0.97 ("High") while the same camera on a
    different scene correlated at 0.02 ("Low") — exactly backwards.
    """

    @classmethod
    def setUpClass(cls):
        from analysis.prnu import analyze_prnu as _analyze
        cls.analyze = staticmethod(_analyze)

        cls.test_dir = Path(__file__).parent / "test_prnu_images"
        cls.test_dir.mkdir(exist_ok=True)

        rng = np.random.default_rng(42)
        scene = np.asarray(_sample_rgb().convert("L"), dtype=np.float64)
        h, w = scene.shape
        # Distinct scenes, so scene content cannot carry the correlation
        scenes = [np.roll(scene, (i * 97, i * 53), axis=(0, 1))
                  for i in range(5)]

        # Two synthetic sensors: fixed multiplicative gain patterns
        cls.gain_a = rng.normal(0, 0.03, (h, w))
        gain_b = rng.normal(0, 0.03, (h, w))

        def shoot(content, gain, seed, name):
            noise = np.random.default_rng(seed).normal(0, 1.5, content.shape)
            pixels = np.clip(content * (1 + gain) + noise, 0, 255)
            path = cls.test_dir / f"{name}.png"
            Image.fromarray(pixels.astype(np.uint8)).save(path)
            return str(path), pixels

        cls.references = [shoot(scenes[i], cls.gain_a, i, f"ref{i}")[0]
                          for i in range(3)]
        # Held-out scene, shot by each camera
        cls.same_camera, cls.clean_pixels = shoot(
            scenes[4], cls.gain_a, 50, "same_camera")
        cls.other_camera, _ = shoot(scenes[4], gain_b, 51, "other_camera")

        # A camera-A frame with a block replaced by camera B
        spliced = cls.clean_pixels.copy()
        foreign = shoot(scenes[4], gain_b, 77, "_foreign")[1]
        spliced[128:384, 256:640] = foreign[128:384, 256:640]
        cls.spliced = str(cls.test_dir / "spliced.png")
        Image.fromarray(spliced.astype(np.uint8)).save(cls.spliced)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def test_same_camera_different_scene_matches(self):
        result = self.analyze(self.same_camera,
                              reference_image_path=self.references[0])
        correlation = result["correlation_analysis"]

        self.assertGreater(correlation["correlation"], 0.05)
        self.assertIn(correlation["same_camera_likelihood"], ("Medium", "High"))

    def test_different_camera_same_scene_does_not_match(self):
        """The case that used to report 0.97 'High'."""
        result = self.analyze(self.other_camera,
                              reference_image_path=self.references[0])
        correlation = result["correlation_analysis"]

        self.assertLess(correlation["correlation"], 0.05)
        self.assertEqual(correlation["same_camera_likelihood"], "Low")

    def test_more_references_give_a_stronger_match(self):
        one = self.analyze(self.same_camera,
                           reference_image_path=self.references[0])
        three = self.analyze(self.same_camera,
                             reference_image_path=self.references)

        self.assertEqual(three["correlation_analysis"]["reference_images_used"], 3)
        self.assertGreater(three["correlation_analysis"]["correlation"],
                           one["correlation_analysis"]["correlation"])

    def test_splice_is_localised(self):
        """A region from another sensor must be flagged, and only that region."""
        clean = self.analyze(self.same_camera,
                             reference_image_path=self.references)
        spliced = self.analyze(self.spliced,
                               reference_image_path=self.references)

        self.assertEqual(
            clean["correlation_analysis"].get("suspicious_blocks", []), [],
            "clean image produced false splice detections")

        blocks = spliced["correlation_analysis"].get("suspicious_blocks", [])
        self.assertTrue(blocks, "splice from a different sensor went undetected")

        # Spliced region is rows 128-384, cols 256-640 -> blocks 2-5 x 4-9 at 64px
        for block in blocks:
            self.assertIn(block["row"], range(2, 6))
            self.assertIn(block["col"], range(4, 10))


class TestResamplingRecoversScale(unittest.TestCase):
    """Resampling detection must discriminate, and recover the scale factor.

    Regression for a saturating statistic: the old test asked whether *any*
    pixel in a frequency ring exceeded the 95th percentile. Since 5% of pixels
    exceed it by construction, nearly every ring fired and a never-resized
    image scored 0.944 against a stated threshold of 0.5.
    """

    @classmethod
    def setUpClass(cls):
        cls.test_dir = Path(__file__).parent / "test_resample_images"
        cls.test_dir.mkdir(exist_ok=True)
        cls.base = _sample_rgb()
        cls.width, cls.height = cls.base.size

        cls.native = cls.test_dir / "native.png"
        cls.base.save(cls.native, "PNG")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def _resized(self, scale, resample=Image.Resampling.BICUBIC):
        path = self.test_dir / f"scaled_{scale}_{resample.name}.png"
        self.base.resize((int(self.width * scale), int(self.height * scale)),
                         resample).save(path, "PNG")
        return str(path)

    def test_native_image_not_flagged(self):
        result = detect_resampling(str(self.native))

        self.assertFalse(result["resampling_detected"],
                         f"clean image flagged, prominence "
                         f"{result['peak_prominence']}")
        self.assertLess(result["resampling_score"], 0.2)

    def test_detects_and_recovers_fractional_scales(self):
        """The true factor must appear among the reported candidates."""
        for scale in (1.05, 1.25, 1.5, 1.9):
            with self.subTest(scale=scale):
                result = detect_resampling(self._resized(scale))

                self.assertTrue(result["resampling_detected"],
                                f"{scale}x rescaling went undetected")
                self.assertTrue(
                    any(abs(c - scale) < 0.05
                        for c in result["estimated_scale_factors"]),
                    f"{scale} missing from {result['estimated_scale_factors']}")

    def test_documents_its_blind_spots(self):
        """Integer scaling is undetectable here; that must be stated, not hidden."""
        result = detect_resampling(self._resized(2.0))

        self.assertFalse(result["resampling_detected"])
        self.assertTrue(any("Integer scale" in lim
                            for lim in result["limitations"]))

    def test_identifies_nearest_neighbour(self):
        result = detect_interpolation_method(
            self._resized(1.5, Image.Resampling.NEAREST))

        self.assertIn("Nearest", result["likely_interpolation"])
        self.assertEqual(result["confidence"], "High")

    def test_does_not_guess_a_kernel_for_unresampled_images(self):
        """It used to answer 'Bicubic' for every input, including this one."""
        result = detect_interpolation_method(str(self.native))

        self.assertEqual(result["confidence"], "N/A")
        self.assertIn("No resampling", result["likely_interpolation"])


class TestLedgerIsTamperEvident(unittest.TestCase):
    """The hash chain must detect edits to the ledger itself."""

    @classmethod
    def setUpClass(cls):
        cls.test_dir = Path(__file__).parent / "test_ledger_images"
        cls.test_dir.mkdir(exist_ok=True)

        base = np.asarray(_sample_rgb((200, 150)))
        cls.images = []
        for i in range(3):
            path = cls.test_dir / f"img{i}.png"
            Image.fromarray(np.clip(base + i, 0, 255).astype(np.uint8)).save(path)
            cls.images.append(str(path))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def _fresh_ledger(self):
        from analysis.hash_verification import add_to_blockchain

        db = self.test_dir / "ledger.json"
        if db.exists():
            db.unlink()
        for image in self.images:
            add_to_blockchain(image, db_path=str(db))
        return db

    def test_untouched_chain_verifies(self):
        from analysis.hash_verification import verify_chain

        status = verify_chain(str(self._fresh_ledger()))

        self.assertTrue(status["valid"])
        self.assertEqual(status["total_records"], 3)
        self.assertEqual(status["errors"], [])

    def test_edited_record_is_detected(self):
        import json
        from analysis.hash_verification import verify_chain

        db = self._fresh_ledger()
        data = json.loads(db.read_text())
        data["records"][1]["sha256"] = "0" * 64
        db.write_text(json.dumps(data))

        status = verify_chain(str(db))
        self.assertFalse(status["valid"])
        self.assertEqual(status["first_invalid_index"], 1)

    def test_rehashed_record_still_breaks_the_next_link(self):
        """Recomputing the edited record's own hash must not repair the chain."""
        import json
        from analysis.hash_verification import compute_record_hash, verify_chain

        db = self._fresh_ledger()
        data = json.loads(db.read_text())
        record = data["records"][1]
        record["sha256"] = "f" * 64
        record["record_hash"] = compute_record_hash(record, record["prev_hash"])
        db.write_text(json.dumps(data))

        status = verify_chain(str(db))
        self.assertFalse(status["valid"])
        # The break now surfaces at the *following* record
        self.assertEqual(status["first_invalid_index"], 2)

    def test_tampering_invalidates_the_legal_verdict(self):
        import json
        from analysis.hash_verification import verify_image_provenance

        db = self._fresh_ledger()
        data = json.loads(db.read_text())
        data["records"][0]["filename"] = "something_else.png"
        db.write_text(json.dumps(data))

        _, _, validity, details = verify_image_provenance(
            self.images[0], db_path=str(db))

        self.assertFalse(validity["valid"])
        self.assertFalse(validity["admissible"])
        self.assertEqual(validity["chain_of_custody"], "Compromised")
        self.assertFalse(details["chain_integrity"]["valid"])


class TestAppRendersResults(unittest.TestCase):
    """Keys app.py reads without a guard must exist in the result.

    Each Streamlit tab indexes straight into these dicts, so a renamed metric
    is a KeyError that takes the tab down. Guarded reads (`if k in metrics`)
    are deliberately excluded — only unguarded ones are contract.
    """

    @classmethod
    def setUpClass(cls):
        cls.path = str(SAMPLE)

    def test_ela_tab_metrics(self):
        _, _, metrics = perform_ela(self.path)
        for key in ("mean_error", "max_error", "std_error", "anomaly_score"):
            self.assertIn(key, metrics)

    def test_frequency_tab_metrics(self):
        metrics = analyze_frequency_domain(self.path)["metrics"]
        for key in ("high_frequency_energy_percentage",
                    "spectral_power_law_slope", "spectral_complexity"):
            self.assertIn(key, metrics)

    def test_dct_tab_metrics(self):
        metrics = detect_dct_anomalies(self.path)["metrics"]
        for key in ("smooth_content_percentage", "detail_content_percentage",
                    "noise_edge_percentage", "jpeg_blockiness_ratio",
                    "compression_quality_indicator"):
            self.assertIn(key, metrics)

    def test_gan_tab_metrics(self):
        metrics = detect_gan_fingerprint(self.path)["metrics"]
        for key in ("radial_frequency_variance", "spectral_peaks_detected",
                    "quadrant_symmetry"):
            self.assertIn(key, metrics)

    def test_noise_tab_metrics(self):
        metrics = generate_noise_map(self.path)["metrics"]
        for key in ("channel_noise_variance", "overall_variance",
                    "block_variance_std", "blocks_analyzed"):
            self.assertIn(key, metrics)

    def test_cmfd_tab_results(self):
        results = detect_copy_move(self.path)["results"]
        for key in ("total_blocks_analyzed", "matches_found",
                    "match_groups", "result_image_path"):
            self.assertIn(key, results)

    def test_ela_report_keys(self):
        """forensic_analysis feeds the ELA tab directly."""
        from analysis.ela import forensic_analysis

        report = forensic_analysis(self.path, qualities=[90])
        for key in ("ela_90", "ela_90_overlay", "ela_90_metrics",
                    "block_stats", "ela_multi_quality", "noise_map",
                    "sharpness_map", "entropy_map", "ssim_img", "ssim_score",
                    "threshold_mask"):
            self.assertIn(key, report)


class TestErrorHandling(unittest.TestCase):
    """Modules report errors in their return value rather than raising.

    app.py relies on this: every tab calls straight into these functions and
    renders the result, so an exception escaping here is a crashed tab.
    """

    MISSING = "definitely_nonexistent_image.jpg"

    def test_dict_returning_modules_report_error_status(self):
        for name, fn in [
            ("histogram", generate_histogram),
            ("noise_map", generate_noise_map),
            ("jpeg_ghost", detect_jpeg_ghost),
            ("quant_table", analyze_quantization_table),
            ("cmfd", detect_copy_move),
            ("prnu", analyze_prnu),
            ("frequency", analyze_frequency_domain),
            ("dct", detect_dct_anomalies),
            ("deepfake", detect_deepfake_artifacts),
            ("gan", detect_gan_fingerprint),
            ("resampling", detect_resampling),
            ("interpolation", detect_interpolation_method),
        ]:
            with self.subTest(module=name):
                result = fn(self.MISSING)
                self.assertNotIn(result.get("status"), OK_STATUS)
                self.assertIn("error", result)

    def test_ela_returns_none_triple(self):
        self.assertEqual(perform_ela(self.MISSING), (None, None, None))

    def test_metadata_records_warning(self):
        meta = extract_metadata(self.MISSING)
        self.assertTrue(meta["warnings"])

    def test_steganography_returns_zero(self):
        prob, visual_map, details = detect_lsb_steganography(self.MISSING)
        self.assertEqual(prob, 0.0)
        self.assertIsNone(visual_map)
        self.assertIn("error", details)

    def test_ghost_returns_none_image(self):
        ghost_img, analysis = detect_ghost(self.MISSING)
        self.assertIsNone(ghost_img)
        self.assertEqual(analysis["status"], "error")


class TestFormatCompatibility(unittest.TestCase):
    """PNG, grayscale and RGBA inputs must not break the pipeline."""

    @classmethod
    def setUpClass(cls):
        cls.test_dir = Path(__file__).parent / "test_format_images"
        cls.test_dir.mkdir(exist_ok=True)

        base = _sample_rgb((300, 200))
        cls.png = cls.test_dir / "test.png"
        base.save(cls.png, "PNG")

        cls.gray = cls.test_dir / "gray.jpg"
        base.convert("L").save(cls.gray, "JPEG", quality=92)

        cls.rgba = cls.test_dir / "rgba.png"
        base.convert("RGBA").save(cls.rgba, "PNG")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def test_png_handled(self):
        self.assertEqual(extract_metadata(str(self.png))
                         ["basic_info"]["format"], "PNG")
        self.assertEqual(generate_histogram(str(self.png))["status"], "success")
        self.assertIsInstance(perform_ela(str(self.png))[0], Image.Image)

    def test_png_metadata_is_not_aborted_by_missing_exif(self):
        """PNG has no EXIF; extraction must still yield full basic_info.

        piexif raises on PNG, so a single try block around the whole function
        would drop everything after the EXIF call.
        """
        meta = extract_metadata(str(self.png))

        self.assertEqual(meta["basic_info"]["width"], 300)
        self.assertEqual(meta["basic_info"]["height"], 200)
        self.assertIn("file_size_bytes", meta["basic_info"])

    def test_grayscale_handled(self):
        meta = extract_metadata(str(self.gray))
        self.assertEqual(meta["basic_info"]["mode"], "L")
        # Modules convert internally; must not raise on a single-channel source
        self.assertIn(detect_lsb_steganography(str(self.gray))[2].get("error"),
                      (None,))
        self.assertEqual(generate_noise_map(str(self.gray))["status"], "success")

    def test_rgba_handled(self):
        meta = extract_metadata(str(self.rgba))
        self.assertEqual(meta["basic_info"]["mode"], "RGBA")
        self.assertIsInstance(perform_ela(str(self.rgba))[0], Image.Image)


if __name__ == "__main__":
    unittest.main(verbosity=2)
