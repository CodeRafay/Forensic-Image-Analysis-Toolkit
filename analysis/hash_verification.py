"""
Cryptographic Hash Verification Module
======================================
Implements blockchain-based image provenance tracking using perceptual and cryptographic hashing.

This module provides:
- Perceptual hashing (resistant to minor edits)
- SHA-256 cryptographic hashing (exact matching)
- Simulated blockchain storage for provenance tracking
- Modification history with timestamps
- Authenticity scoring and legal validity assessment
"""

from PIL import Image
import imagehash
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path


# Default database location — directory created lazily on first write.
# Anchored to the project root rather than the CWD so the ledger does not move
# depending on where the app was launched from; every other module resolves its
# temp directory the same way.
_TEMP_DIR = str(Path(__file__).resolve().parent.parent / "temp")
DEFAULT_DB_PATH = os.path.join(_TEMP_DIR, "hash_database.json")


def generate_perceptual_hash(image_path):
    """
    Generate perceptual hashes using multiple algorithms.

    Perceptual hashes are resistant to minor modifications like:
    - Slight compression
    - Resizing
    - Color adjustments
    - Minor cropping

    Args:
        image_path (str): Path to image file

    Returns:
        dict: Multiple perceptual hash types
    """
    img = Image.open(image_path)
    hashes = {
        'phash': str(imagehash.phash(img)),  # Perceptual hash (most robust)
        'ahash': str(imagehash.average_hash(img)),  # Average hash
        'dhash': str(imagehash.dhash(img)),  # Difference hash
        'whash': str(imagehash.whash(img))  # Wavelet hash
    }
    img.close()
    return hashes


def generate_cryptographic_hash(image_path):
    """
    Generate SHA-256 cryptographic hash for exact matching.

    Args:
        image_path (str): Path to image file

    Returns:
        str: SHA-256 hash as hexadecimal string
    """
    sha256_hash = hashlib.sha256()

    with open(image_path, 'rb') as f:
        # Read file in chunks to handle large images
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)

    return sha256_hash.hexdigest()


def calculate_hash_distance(hash1, hash2):
    """
    Calculate Hamming distance between two perceptual hashes.

    Args:
        hash1 (str): First hash string
        hash2 (str): Second hash string

    Returns:
        int: Hamming distance (number of differing bits)
    """
    # Convert hex strings to integers and calculate XOR
    h1 = int(hash1, 16)
    h2 = int(hash2, 16)

    # Count differing bits
    xor = h1 ^ h2
    distance = bin(xor).count('1')

    return distance


def load_database(db_path=DEFAULT_DB_PATH):
    """
    Load hash database from JSON file.

    Args:
        db_path (str): Path to database file

    Returns:
        dict: Database contents
    """
    if os.path.exists(db_path):
        try:
            with open(db_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading database: {e}")
            return {"records": [], "metadata": {"created": datetime.now().isoformat()}}
    else:
        return {"records": [], "metadata": {"created": datetime.now().isoformat()}}


def save_database(database, db_path=DEFAULT_DB_PATH):
    """
    Save hash database to JSON file.

    Args:
        database (dict): Database contents
        db_path (str): Path to database file
    """
    # Ensure directory exists (lazily, only when actually writing)
    dir_name = os.path.dirname(
        db_path) if os.path.dirname(db_path) else _TEMP_DIR
    os.makedirs(dir_name, exist_ok=True)

    with open(db_path, 'w') as f:
        json.dump(database, f, indent=2)


# Hash of the (non-existent) block before the first one
GENESIS_HASH = "0" * 64

# Fields excluded from a record's own hash: record_hash is the output itself,
# and chain_valid is a verification annotation added at read time.
_UNHASHED_FIELDS = ("record_hash", "chain_valid")


def compute_record_hash(record, prev_hash):
    """
    Compute a record's block hash: SHA-256 over its content plus its
    predecessor's hash.

    Linking each record to the previous one is what makes the ledger
    tamper-evident. Editing any field of any record changes that record's hash,
    which breaks every hash after it, so a single edit invalidates the whole
    tail of the chain rather than passing silently.

    Args:
        record (dict): The record to hash
        prev_hash (str): Preceding record's `record_hash`

    Returns:
        str: SHA-256 hex digest
    """
    payload = {k: v for k, v in record.items() if k not in _UNHASHED_FIELDS}
    payload["prev_hash"] = prev_hash

    # sort_keys makes the serialization canonical, so the same content always
    # hashes the same regardless of dict insertion order
    canonical = json.dumps(payload, sort_keys=True,
                           separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def verify_chain(db_path=DEFAULT_DB_PATH):
    """
    Walk the ledger and verify every link.

    Returns:
        dict: {
            'valid': bool,              # whole chain intact
            'total_records': int,
            'first_invalid_index': int or None,
            'errors': list of str,
            'legacy_records': int       # records predating chaining
        }
    """
    database = load_database(db_path)
    records = database.get("records", [])

    errors = []
    first_invalid = None
    legacy = 0
    prev_hash = GENESIS_HASH

    for index, record in enumerate(records):
        stored = record.get("record_hash")

        if stored is None:
            # Written before chaining existed; cannot be verified either way
            legacy += 1
            prev_hash = GENESIS_HASH if index == 0 else prev_hash
            continue

        if record.get("prev_hash") != prev_hash:
            errors.append(
                f"Record {index} ({record.get('filename', '?')}): broken link - "
                f"expected prev_hash {prev_hash[:12]}..., "
                f"found {str(record.get('prev_hash'))[:12]}...")
            first_invalid = index if first_invalid is None else first_invalid

        recomputed = compute_record_hash(record, record.get("prev_hash", ""))
        if recomputed != stored:
            errors.append(
                f"Record {index} ({record.get('filename', '?')}): content has been "
                f"altered since it was recorded")
            first_invalid = index if first_invalid is None else first_invalid

        prev_hash = stored

    return {
        "valid": not errors,
        "total_records": len(records),
        "first_invalid_index": first_invalid,
        "errors": errors,
        "legacy_records": legacy,
    }


def add_to_blockchain(image_path, db_path=DEFAULT_DB_PATH):
    """
    Append an image record to the hash chain.

    Each record stores the previous record's hash and its own, so any later
    edit to the ledger is detectable via verify_chain().

    Args:
        image_path (str): Path to image file
        db_path (str): Path to database file

    Returns:
        dict: Record appended to the chain
    """
    # Generate hashes
    perceptual_hashes = generate_perceptual_hash(image_path)
    crypto_hash = generate_cryptographic_hash(image_path)

    # Load database
    database = load_database(db_path)

    # Derive the id from the highest existing one rather than the record
    # count: import_database() merges records in, so a count-based id
    # collides with an imported record after any merge.
    next_id = max((r.get('id', -1)
                   for r in database['records']), default=-1) + 1

    prev_hash = (database['records'][-1].get('record_hash', GENESIS_HASH)
                 if database['records'] else GENESIS_HASH)

    record = {
        'id': next_id,
        'filename': os.path.basename(image_path),
        'timestamp': datetime.now().isoformat(),
        'perceptual_hashes': perceptual_hashes,
        'sha256': crypto_hash,
        'file_size': os.path.getsize(image_path),
        'image_info': _get_image_info(image_path),
        'prev_hash': prev_hash,
    }
    record['record_hash'] = compute_record_hash(record, prev_hash)

    # Append to the chain
    database['records'].append(record)
    database['metadata']['last_updated'] = datetime.now().isoformat()
    database['metadata']['total_records'] = len(database['records'])
    database['metadata']['chain_head'] = record['record_hash']

    # Save database
    save_database(database, db_path)

    return record


def _get_image_info(image_path):
    """
    Extract basic image information.

    Args:
        image_path (str): Path to image file

    Returns:
        dict: Image metadata
    """
    try:
        img = Image.open(image_path)
        info = {
            'width': img.width,
            'height': img.height,
            'format': img.format,
            'mode': img.mode
        }
        img.close()
        return info
    except Exception as e:
        return {'error': str(e)}


def find_matches(image_path, db_path=DEFAULT_DB_PATH, threshold=10,
                 _precomputed_hashes=None, _precomputed_sha256=None):
    """
    Find similar images in database using perceptual hashing.

    Args:
        image_path (str): Path to query image
        db_path (str): Path to database file
        threshold (int): Maximum Hamming distance for match (default: 10)
        _precomputed_hashes: Optional pre-computed perceptual hashes to avoid re-hashing
        _precomputed_sha256: Optional pre-computed SHA-256 hash

    Returns:
        list: Matching records with similarity scores
    """
    # Re-use pre-computed hashes or generate fresh ones
    query_hashes = _precomputed_hashes or generate_perceptual_hash(image_path)
    query_sha256 = _precomputed_sha256 or generate_cryptographic_hash(
        image_path)

    # Load database
    database = load_database(db_path)

    matches = []

    for record in database['records']:
        # Check for exact match first
        if record['sha256'] == query_sha256:
            matches.append({
                'record': record,
                'match_type': 'exact',
                'similarity': 100.0,
                'hash_distance': 0
            })
            continue

        # Calculate perceptual hash distance
        phash_distance = calculate_hash_distance(
            query_hashes['phash'],
            record['perceptual_hashes']['phash']
        )

        if phash_distance <= threshold:
            # Calculate similarity percentage
            # phash is 64-bit, so max distance is 64
            similarity = ((64 - phash_distance) / 64) * 100

            matches.append({
                'record': record,
                'match_type': 'perceptual',
                'similarity': similarity,
                'hash_distance': phash_distance
            })

    # Sort by similarity (highest first)
    matches.sort(key=lambda x: x['similarity'], reverse=True)

    return matches


def verify_image_provenance(image_path, db_path=DEFAULT_DB_PATH):
    """
    Verify image provenance and authenticity using blockchain-based tracking.

    This function:
    1. Generates perceptual and cryptographic hashes
    2. Searches database for matches
    3. Analyzes modification history
    4. Calculates authenticity score
    5. Assesses legal validity

    Args:
        image_path (str): Path to image file
        db_path (str): Path to hash database

    Returns:
        tuple: (authenticity_score, modification_history, legal_validity, detailed_results)
    """
    try:
        # Generate hashes ONCE and pass them to find_matches to avoid redundant work
        perceptual_hashes = generate_perceptual_hash(image_path)
        crypto_hash = generate_cryptographic_hash(image_path)

        # Find matches — pass pre-computed hashes so they aren't regenerated
        matches = find_matches(
            image_path, db_path,
            _precomputed_hashes=perceptual_hashes,
            _precomputed_sha256=crypto_hash
        )

        # Calculate authenticity score
        authenticity_score = _calculate_authenticity_score(
            matches, crypto_hash)

        # Build modification history
        modification_history = _build_modification_history(matches)

        # The ledger only proves anything if it has not itself been edited
        chain_status = verify_chain(db_path)

        # Assess legal validity
        legal_validity = _assess_legal_validity(
            matches, authenticity_score, chain_status)

        # Compile detailed results
        detailed_results = {
            'current_hashes': {
                'perceptual': perceptual_hashes,
                'sha256': crypto_hash
            },
            'matches_found': len(matches),
            'match_details': matches[:5],  # Top 5 matches
            'image_info': _get_image_info(image_path),
            'database_path': db_path,
            'chain_integrity': chain_status,
            'analysis_timestamp': datetime.now().isoformat()
        }

        return authenticity_score, modification_history, legal_validity, detailed_results

    except Exception as e:
        return 0, [], {'valid': False, 'reason': f'Error: {str(e)}'}, {'error': str(e)}


def _calculate_authenticity_score(matches, crypto_hash):
    """
    Calculate authenticity score based on matches found.

    Args:
        matches (list): List of matching records
        crypto_hash (str): SHA-256 hash of current image

    Returns:
        int: Authenticity score (0-100)
    """
    if not matches:
        # No matches found - unknown provenance
        return 50

    best_match = matches[0]

    if best_match['match_type'] == 'exact':
        # Exact match found - very high authenticity
        return 100

    # Perceptual match. find_matches only returns hits within its Hamming
    # threshold, so with the default (10 of 64 bits) similarity cannot fall
    # below 84.4%; bands under that are unreachable at default settings but
    # are kept because the threshold is caller-configurable.
    similarity = best_match['similarity']
    if similarity >= 95:
        return 85      # Very close - likely minor modification
    if similarity >= 85:
        return 70      # Close - moderate modification
    if similarity >= 70:
        return 55      # Partial - significant modification
    return 40          # Low similarity - possibly a different image


def _build_modification_history(matches):
    """
    Build modification history from matches.

    Args:
        matches (list): List of matching records

    Returns:
        list: Chronological modification history
    """
    history = []

    for match in matches:
        record = match['record']
        history.append({
            'timestamp': record['timestamp'],
            'filename': record['filename'],
            'match_type': match['match_type'],
            'similarity': f"{match['similarity']:.1f}%",
            'file_size': record['file_size']
        })

    # Sort by timestamp
    history.sort(key=lambda x: x['timestamp'])

    return history


def _assess_legal_validity(matches, authenticity_score, chain_status=None):
    """
    Assess legal validity based on chain of custody.

    Two independent things must hold: the image must match a record, and the
    ledger holding that record must not itself have been tampered with. A match
    against an altered ledger proves nothing, so a broken chain overrides any
    match result.

    Args:
        matches (list): List of matching records
        authenticity_score (int): Calculated authenticity score
        chain_status (dict): Result of verify_chain()

    Returns:
        dict: Legal validity assessment
    """
    # A tampered ledger invalidates everything built on it
    if chain_status is not None and not chain_status['valid']:
        return {
            'valid': False,
            'reason': 'Ledger integrity check failed - records have been altered',
            'chain_of_custody': 'Compromised',
            'admissible': False,
            'confidence': 'None',
            'chain_errors': chain_status['errors'][:5],
        }

    if not matches:
        return {
            'valid': False,
            'reason': 'No provenance records found in database',
            'chain_of_custody': 'Broken',
            'admissible': False
        }

    # Records written before chaining existed can't be vouched for
    unverifiable = bool(chain_status and chain_status['legacy_records'])

    best_match = matches[0]

    if best_match['match_type'] == 'exact':
        return {
            'valid': True,
            'reason': 'Exact cryptographic match found'
                      + (' (ledger contains unchained legacy records)'
                         if unverifiable else ''),
            'chain_of_custody': 'Intact' if not unverifiable else 'Partially verifiable',
            'admissible': True,
            'confidence': 'High' if not unverifiable else 'Medium',
        }
    elif authenticity_score >= 85:
        return {
            'valid': True,
            'reason': 'Strong perceptual match with minimal modifications',
            'chain_of_custody': 'Likely Intact',
            'admissible': True,
            'confidence': 'Medium-High',
            'modifications': 'Minor (compression, resize, or format conversion)'
        }
    elif authenticity_score >= 70:
        return {
            'valid': 'Uncertain',
            'reason': 'Moderate modifications detected',
            'chain_of_custody': 'Questionable',
            'admissible': False,
            'confidence': 'Medium',
            'modifications': 'Moderate (possible content alterations)'
        }
    else:
        return {
            'valid': False,
            'reason': 'Significant modifications or different image',
            'chain_of_custody': 'Broken',
            'admissible': False,
            'confidence': 'Low'
        }


# ============================================================
# -------------------- DATABASE MANAGEMENT -------------------
# ============================================================

def export_database(db_path=DEFAULT_DB_PATH, export_path=None):
    """
    Export database to a file.

    Args:
        db_path (str): Source database path
        export_path (str): Destination path (defaults to timestamped file)

    Returns:
        str: Path to exported file
    """
    if export_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_path = f"hash_database_export_{timestamp}.json"

    database = load_database(db_path)

    with open(export_path, 'w') as f:
        json.dump(database, f, indent=2)

    return export_path


def import_database(import_path, db_path=DEFAULT_DB_PATH, merge=True):
    """
    Import database from a file.

    Args:
        import_path (str): Path to import file
        db_path (str): Destination database path
        merge (bool): If True, merge with existing; if False, replace

    Returns:
        dict: Import statistics
    """
    with open(import_path, 'r') as f:
        imported_db = json.load(f)

    if merge and os.path.exists(db_path):
        existing_db = load_database(db_path)

        # Merge records (avoid duplicates by SHA-256)
        existing_hashes = {r['sha256'] for r in existing_db['records']}
        new_records = [
            r for r in imported_db['records']
            if r['sha256'] not in existing_hashes
        ]

        existing_db['records'].extend(new_records)
        existing_db['metadata']['last_updated'] = datetime.now().isoformat()
        existing_db['metadata']['total_records'] = len(existing_db['records'])

        save_database(existing_db, db_path)

        return {
            'imported': len(new_records),
            'duplicates_skipped': len(imported_db['records']) - len(new_records),
            'total_records': len(existing_db['records'])
        }
    else:
        # Replace existing database
        save_database(imported_db, db_path)

        return {
            'imported': len(imported_db['records']),
            'duplicates_skipped': 0,
            'total_records': len(imported_db['records'])
        }


def get_database_stats(db_path=DEFAULT_DB_PATH):
    """
    Get statistics about the hash database.

    Args:
        db_path (str): Path to database file

    Returns:
        dict: Database statistics
    """
    database = load_database(db_path)

    if not database['records']:
        return {
            'total_records': 0,
            'created': database['metadata'].get('created', 'Unknown'),
            'last_updated': 'Never'
        }

    return {
        'total_records': len(database['records']),
        'created': database['metadata'].get('created', 'Unknown'),
        'last_updated': database['metadata'].get('last_updated', 'Unknown'),
        'oldest_record': min(r['timestamp'] for r in database['records']),
        'newest_record': max(r['timestamp'] for r in database['records']),
        'total_file_size': sum(r['file_size'] for r in database['records'])
    }
