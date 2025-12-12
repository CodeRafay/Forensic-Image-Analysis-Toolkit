# 🔑 Cryptographic Hash Verification

## What is Hash Verification?

Hash verification is like creating a **digital fingerprint** for an image. Just as your fingerprint uniquely identifies you, a cryptographic hash uniquely identifies a specific file. This module uses two types of hashing:

1. **Cryptographic Hash (SHA-256)**: Exact matching - even one bit changed creates a completely different hash
2. **Perceptual Hash**: Resilient matching - similar images produce similar hashes

Think of it like DNA testing:
- **Cryptographic hash** = Exact DNA match (100% identical twins)
- **Perceptual hash** = Family resemblance (siblings look similar)

## What is Blockchain-Based Provenance?

**Provenance** means the history of ownership and modifications of an image. Our blockchain simulation:

- **Records every registered image** with timestamps
- **Creates an immutable audit trail** (like a notary's ledger)
- **Tracks the chain of custody** for legal validity
- **Detects unauthorized modifications** by comparing hashes

### How It Works:

```
Original Image → Generate Hashes → Store in "Blockchain" → Verify Later
                                          ↓
                     Timestamp + Hashes + Metadata (immutable record)
```

When you later verify an image, it compares current hashes with stored records to determine authenticity.

## Types of Hashing Used

### 1. 🔒 Cryptographic Hash (SHA-256)

**Purpose**: Exact integrity verification

- **How it works**: Processes every single bit of the file
- **Length**: 256 bits (64 hexadecimal characters)
- **Collision resistance**: Virtually impossible to find two different images with same hash
- **Sensitivity**: Changing even ONE pixel completely changes the hash

**Use Cases**:
- Legal evidence verification
- Exact duplicate detection
- Tamper detection
- Digital chain of custody

### 2. 👁️ Perceptual Hash (pHash, aHash, dHash, wHash)

**Purpose**: Find similar images despite minor changes

**pHash (Perceptual Hash)**:
- Most robust against modifications
- Based on discrete cosine transform (DCT)
- Resistant to: compression, resizing, color adjustment

**aHash (Average Hash)**:
- Fast and simple
- Based on average pixel values
- Good for basic similarity matching

**dHash (Difference Hash)**:
- Based on gradient between adjacent pixels
- Resistant to gamma correction and color changes

**wHash (Wavelet Hash)**:
- Uses wavelet transform
- Good for texture similarity

**Common Tolerances**:
- 0-5 bits different: Nearly identical (minor compression/resize)
- 6-10 bits different: Very similar (moderate edits)
- 11-15 bits different: Similar (significant edits)
- 16+ bits different: Possibly different images

## What Does the Analysis Show?

### 📊 Authenticity Score (0-100)

- **100**: Exact cryptographic match - identical file
- **85-99**: Strong perceptual match - minor modifications only
- **70-84**: Moderate match - some modifications detected
- **55-69**: Weak match - significant changes
- **0-54**: No match or unknown provenance

### 🔍 Match Types

**Exact Match**:
- SHA-256 hashes identical
- Byte-for-byte identical file
- Highest confidence (100%)

**Perceptual Match**:
- SHA-256 differs, but perceptual hashes similar
- Indicates modifications like:
  - Format conversion (PNG → JPEG)
  - Compression level change
  - Minor cropping or resizing
  - Color adjustment
  - Watermark addition

**No Match**:
- Neither cryptographic nor perceptual match
- Unknown provenance
- Possibly original (never registered)

### ⚖️ Legal Validity Assessment

**Chain of Custody**: Critical for legal admissibility

- **Intact**: Exact match found, high legal validity
- **Likely Intact**: Minor modifications only, still admissible
- **Questionable**: Moderate modifications, requires explanation
- **Broken**: Significant changes, likely not admissible

## Interpretation Guidelines

### ✅ High Authenticity (Score: 85-100)

**Indicators**:
- Exact SHA-256 match OR
- Perceptual hash distance < 5 bits
- Clear modification history in database
- Timestamps match expected timeline

**Confidence**: High - Image is authentic or minimally modified

### 🟡 Medium Authenticity (Score: 55-84)

**Indicators**:
- Perceptual hash distance 5-15 bits
- Moderate modifications detected
- Some inconsistencies in timeline
- Format or size changes

**Confidence**: Medium - Image may be authentic but edited

### 🔴 Low Authenticity (Score: 0-54)

**Indicators**:
- No perceptual match in database
- Hash distance > 15 bits
- Unknown provenance
- Possible forgery or new image

**Confidence**: Low - Cannot verify authenticity

## Database Management

### Adding Images to Blockchain

When you add an image:
1. Generates all hash types (SHA-256, pHash, aHash, dHash, wHash)
2. Records timestamp (ISO 8601 format)
3. Stores file metadata (size, dimensions, format)
4. Creates immutable record in JSON "blockchain"

### Searching the Database

When you verify an image:
1. Generates current hashes
2. Searches database for matches
3. Calculates similarity scores
4. Returns modification history

### Import/Export Functionality

**Export**: Save database to share with other systems  
**Import**: Load trusted database (merge or replace)  
**Backup**: Regular exports for disaster recovery

## Use Cases

### Digital Forensics:
- **Evidence verification**: Prove image hasn't been tampered
- **Chain of custody**: Track image from capture to court
- **Timeline establishment**: Verify when image was created
- **Duplicate detection**: Find all versions of an image

### Copyright Protection:
- **Proof of ownership**: Establish creation date
- **Infringement detection**: Find unauthorized copies
- **Licensing verification**: Confirm licensed versions

### Journalism & Media:
- **Source verification**: Confirm image origin
- **Deepfake detection**: Check against known authentic images
- **Archive integrity**: Ensure historical images unchanged

### Corporate Security:
- **Data leak prevention**: Track sensitive images
- **Insider threat detection**: Monitor unauthorized distribution
- **Compliance auditing**: Verify document integrity

## Technical Implementation

### Hash Generation:
```
Image File → SHA-256 → Cryptographic Hash (exact)
           → pHash  → Perceptual Hash (similarity)
           → aHash  → Average Hash (fast similarity)
           → dHash  → Difference Hash (gradient)
           → wHash  → Wavelet Hash (texture)
```

### Similarity Calculation:
- **Hamming Distance**: Counts differing bits between hashes
- **Lower distance** = More similar images
- **Threshold**: Typically 10 bits for "similar" classification

### Blockchain Simulation:
- **JSON-based storage**: Simple, portable database
- **Immutable records**: Each entry timestamped
- **Chronological ordering**: Establishes timeline
- **Metadata included**: Full context for each image

## Limitations

### 1. **Not a True Blockchain**
- Simulated blockchain (JSON file, not distributed ledger)
- Not cryptographically chained (no hash linking)
- Suitable for demo/educational purposes
- Production use would require real blockchain

### 2. **Perceptual Hash Limitations**
- Cannot detect all modifications
- Advanced forgery can fool perceptual hashing
- Threshold selection affects accuracy

### 3. **Database Security**
- JSON file can be manually edited (in theory)
- No built-in tamper protection
- Should be stored securely with access controls

### 4. **Initial Registration Required**
- Images must be registered BEFORE verification
- Cannot verify previously unknown images
- Empty database = no verification possible

### 5. **Storage Considerations**
- Database grows with each registered image
- Regular backups recommended
- Export/import for database migration

## Best Practices

✔️ **Register images immediately** upon capture/creation  
✔️ **Regular database backups** to prevent data loss  
✔️ **Secure database storage** with restricted access  
✔️ **Document all modifications** when editing registered images  
✔️ **Use exact match** for legal evidence (SHA-256)  
✔️ **Use perceptual match** for finding similar versions  
✔️ **Export database** before sharing with external parties  
✔️ **Verify timestamps** match expected timeline  
✔️ **Cross-reference** with other forensic techniques

## Legal and Ethical Considerations

### Admissibility in Court:
- **Chain of custody** must be documented
- **Exact hash match** provides strong evidence
- **Modification history** must be explained
- **Database integrity** must be proven

### Privacy Concerns:
- Hash databases may contain sensitive information
- Follow data protection regulations (GDPR, etc.)
- Obtain proper authorization before hashing images

### Ethical Use:
- Don't use for unauthorized surveillance
- Respect copyright and intellectual property
- Maintain transparency in forensic analysis

---

## Educational Context

This module demonstrates critical **Information Security** concepts:

- **Cryptographic Integrity**: Using hashes for verification
- **Digital Provenance**: Tracking asset history
- **Blockchain Technology**: Immutable audit trails
- **Similarity Detection**: Perceptual vs. exact matching
- **Legal Admissibility**: Chain of custody requirements

**Real-World Application**: Similar systems are used by:
- Law enforcement for digital evidence
- Content platforms for copyright detection (YouTube Content ID)
- News organizations for image verification
- Blockchain projects for NFT authenticity

---

_Hash verification is a cornerstone of digital forensics. Understanding both cryptographic and perceptual hashing enables comprehensive image authentication and provenance tracking._
