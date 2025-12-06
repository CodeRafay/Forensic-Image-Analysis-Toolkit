import cv2
import numpy as np
from pathlib import Path
from collections import defaultdict


def detect_copy_move(image_path, block_size=16, threshold=0.95, min_distance=50):
    """
    Detects copy-move forgery using block matching with PCA-based feature extraction.
    Identifies duplicated regions within the same image (cloning).

    Args:
        image_path (str): Path to the image file
        block_size (int): Size of blocks for matching (default 16)
        threshold (float): Similarity threshold 0-1 (default 0.95, higher = more strict)
        min_distance (int): Minimum distance between matched blocks to avoid false positives

    Returns:
        dict: Results dictionary with matched regions and visualization
    """
    try:
        # Read image
        img = cv2.imread(image_path)
        if img is None:
            return {"status": "error", "error": "Could not read image"}

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape

        # Create temp directory
        temp_dir = Path(__file__).parent.parent / "temp"
        temp_dir.mkdir(exist_ok=True)

        # Extract overlapping blocks
        blocks = []
        positions = []

        step = block_size // 2  # 50% overlap

        for i in range(0, h - block_size, step):
            for j in range(0, w - block_size, step):
                block = gray[i:i+block_size, j:j+block_size]

                # Use DCT coefficients as features (more robust than pixels)
                block_float = np.float32(block)
                dct_block = cv2.dct(block_float)

                # Use low-frequency coefficients (top-left 8x8)
                features = dct_block[:8, :8].flatten()

                blocks.append(features)
                positions.append((i, j))

        blocks = np.array(blocks)

        # Normalize features
        blocks_normalized = blocks / \
            (np.linalg.norm(blocks, axis=1, keepdims=True) + 1e-10)

        # Find similar blocks using correlation
        matches = []
        similarity_matrix = np.dot(blocks_normalized, blocks_normalized.T)

        for i in range(len(blocks)):
            for j in range(i + 1, len(blocks)):
                similarity = similarity_matrix[i, j]

                if similarity > threshold:
                    # Check distance between blocks
                    pos1 = positions[i]
                    pos2 = positions[j]
                    distance = np.sqrt(
                        (pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)

                    if distance > min_distance:
                        matches.append({
                            'block1': pos1,
                            'block2': pos2,
                            'similarity': float(similarity),
                            'distance': float(distance)
                        })

        # Create visualization
        result_img = img.copy()

        # Group nearby matches
        match_groups = group_nearby_matches(matches, block_size)

        # Draw rectangles around matched regions
        # Limit to top 10 groups
        for idx, group in enumerate(match_groups[:10]):
            color = (0, 255, 0) if idx % 2 == 0 else (255, 0, 0)
            for match in group:
                y1, x1 = match['block1']
                y2, x2 = match['block2']
                cv2.rectangle(result_img, (x1, y1),
                              (x1 + block_size, y1 + block_size), color, 2)
                cv2.rectangle(result_img, (x2, y2),
                              (x2 + block_size, y2 + block_size), color, 2)
                # Draw line connecting matched regions
                cv2.line(result_img,
                         (x1 + block_size//2, y1 + block_size//2),
                         (x2 + block_size//2, y2 + block_size//2),
                         color, 1)

        # Save result
        result_path = temp_dir / 'temp_cmfd_result.png'
        cv2.imwrite(str(result_path), result_img)

        # Generate warnings
        warnings = []
        if len(matches) > 100:
            warnings.append(
                f"High number of matches ({len(matches)}) - may include false positives from repetitive patterns")

        if len(matches) > 0 and len(matches) < 5:
            warnings.append(
                "Few matches found - potential targeted cloning detected")

        # Analyze match distribution
        if len(matches) > 0:
            similarities = [m['similarity'] for m in matches]
            avg_similarity = np.mean(similarities)
            if avg_similarity > 0.98:
                warnings.append(
                    "Very high similarity matches - possible exact cloning")

        return {
            "status": "success",
            "method": "Block Matching with DCT Features",
            "parameters": {
                "block_size": block_size,
                "threshold": threshold,
                "min_distance": min_distance
            },
            "results": {
                "total_blocks_analyzed": len(blocks),
                "matches_found": len(matches),
                "match_groups": len(match_groups),
                "result_image_path": str(result_path)
            },
            "matches": matches[:20],  # Return top 20 matches
            "warnings": warnings,
            "interpretation": "Green/red rectangles show matched regions. Connected boxes indicate copied areas."
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


def group_nearby_matches(matches, block_size, distance_threshold=50):
    """
    Groups nearby matches into regions (to reduce clutter).

    Args:
        matches (list): List of match dictionaries
        block_size (int): Size of blocks
        distance_threshold (int): Maximum distance to group

    Returns:
        list: List of match groups
    """
    if not matches:
        return []

    groups = []
    used = set()

    for i, match in enumerate(matches):
        if i in used:
            continue

        group = [match]
        used.add(i)

        # Find nearby matches
        for j, other_match in enumerate(matches):
            if j in used:
                continue

            # Check if matches are nearby
            dist1 = np.sqrt(
                (match['block1'][0] - other_match['block1'][0])**2 +
                (match['block1'][1] - other_match['block1'][1])**2
            )
            dist2 = np.sqrt(
                (match['block2'][0] - other_match['block2'][0])**2 +
                (match['block2'][1] - other_match['block2'][1])**2
            )

            if dist1 < distance_threshold and dist2 < distance_threshold:
                group.append(other_match)
                used.add(j)

        groups.append(group)

    # Sort by group size
    groups.sort(key=len, reverse=True)
    return groups
