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


# Default database location - ensure temp directory exists
_TEMP_DIR = "temp"
os.makedirs(_TEMP_DIR, exist_ok=True)
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
    
    return {
        'phash': str(imagehash.phash(img)),  # Perceptual hash (most robust)
        'ahash': str(imagehash.average_hash(img)),  # Average hash
        'dhash': str(imagehash.dhash(img)),  # Difference hash
        'whash': str(imagehash.whash(img))  # Wavelet hash
    }


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
    # Ensure directory exists
    os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
    
    with open(db_path, 'w') as f:
        json.dump(database, f, indent=2)


def add_to_blockchain(image_path, db_path=DEFAULT_DB_PATH):
    """
    Add image record to simulated blockchain.
    
    Args:
        image_path (str): Path to image file
        db_path (str): Path to database file
        
    Returns:
        dict: Record added to blockchain
    """
    # Generate hashes
    perceptual_hashes = generate_perceptual_hash(image_path)
    crypto_hash = generate_cryptographic_hash(image_path)
    
    # Load database
    database = load_database(db_path)
    
    # Create record
    record = {
        'id': len(database['records']),
        'filename': os.path.basename(image_path),
        'timestamp': datetime.now().isoformat(),
        'perceptual_hashes': perceptual_hashes,
        'sha256': crypto_hash,
        'file_size': os.path.getsize(image_path),
        'image_info': _get_image_info(image_path)
    }
    
    # Add to blockchain
    database['records'].append(record)
    database['metadata']['last_updated'] = datetime.now().isoformat()
    database['metadata']['total_records'] = len(database['records'])
    
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
        return {
            'width': img.width,
            'height': img.height,
            'format': img.format,
            'mode': img.mode
        }
    except Exception as e:
        return {'error': str(e)}


def find_matches(image_path, db_path=DEFAULT_DB_PATH, threshold=10):
    """
    Find similar images in database using perceptual hashing.
    
    Args:
        image_path (str): Path to query image
        db_path (str): Path to database file
        threshold (int): Maximum Hamming distance for match (default: 10)
        
    Returns:
        list: Matching records with similarity scores
    """
    # Generate hashes for query image
    query_hashes = generate_perceptual_hash(image_path)
    query_sha256 = generate_cryptographic_hash(image_path)
    
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
        # Generate hashes for the image
        perceptual_hashes = generate_perceptual_hash(image_path)
        crypto_hash = generate_cryptographic_hash(image_path)
        
        # Find matches in database
        matches = find_matches(image_path, db_path)
        
        # Calculate authenticity score
        authenticity_score = _calculate_authenticity_score(matches, crypto_hash)
        
        # Build modification history
        modification_history = _build_modification_history(matches)
        
        # Assess legal validity
        legal_validity = _assess_legal_validity(matches, authenticity_score)
        
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
    elif best_match['similarity'] >= 95:
        # Very close match - likely minor modification
        return 85
    elif best_match['similarity'] >= 85:
        # Close match - moderate modification
        return 70
    elif best_match['similarity'] >= 70:
        # Partial match - significant modification
        return 55
    else:
        # Low similarity - possibly different image
        return 40


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


def _assess_legal_validity(matches, authenticity_score):
    """
    Assess legal validity based on chain of custody.
    
    Args:
        matches (list): List of matching records
        authenticity_score (int): Calculated authenticity score
        
    Returns:
        dict: Legal validity assessment
    """
    if not matches:
        return {
            'valid': False,
            'reason': 'No provenance records found in database',
            'chain_of_custody': 'Broken',
            'admissible': False
        }
    
    best_match = matches[0]
    
    if best_match['match_type'] == 'exact':
        return {
            'valid': True,
            'reason': 'Exact cryptographic match found',
            'chain_of_custody': 'Intact',
            'admissible': True,
            'confidence': 'High'
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
