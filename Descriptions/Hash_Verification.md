# Hash Ledger (file identity and visual similarity)

## What it does

You add images to a **ledger** kept for this browser session. Later you
check another image against it. Three kinds of comparison are made, from
strongest to weakest:

| Test | What equal values mean | What it misses |
|---|---|---|
| **SHA-256 of the file bytes** | The two files are byte-identical. This is the only identity test. | Nothing about the earlier file: if it was already edited when you added it, the match still holds. |
| **Pixel SHA-256** (decoded pixels + mode + size + palette) | Same pixels, but the file bytes differ, so metadata or container changed (EXIF stripped, PNG chunks rewritten, re-wrapped). | EXIF orientation and all other metadata. |
| **pHash / dHash / aHash** (64-bit perceptual hashes, `imagehash`) | The images *look* similar. | Local edits. See the benchmark below. **Not evidence of integrity.** |

SHA-512 and MD5 are also computed and shown. MD5 is **legacy**: collisions
can be generated on purpose, so use it only to compare against old records.

## Reading the result

Findings:

- **info, "Byte-identical (SHA-256) to record #n (label, date)"**: the file
  is exactly the one you added as record n.
- **notice, "Pixels identical … file bytes differ"**: same picture data,
  different file. Something outside the pixels changed.
- **notice, "Visually similar … (pHash distance d)"**: the image looks like
  record n. It may be a recompressed or resized copy, **or a locally edited
  one**. The hash cannot tell which.
- **info, "Not in this session's ledger"**: no file, pixel or perceptual match.
- **warning, "Ledger hash chain is broken at record index k"**: records from
  k onward were changed after being added. Matches against them are unreliable.

Metrics:

- counts of byte-identical, pixel-identical and visually similar records
- best pHash / dHash / aHash Hamming distance (bits that differ, out of 64;
  0 = same hash)
- the similarity threshold in use (10 bits of pHash)

Tables: *Top matches* (up to 10 records, strongest first, with all three
distances) and *Query hashes* (every hash of the checked image).

## Benchmark (how the 10-bit threshold was chosen)

Reference: `assets/sample images/sampleImg.jpeg` (1024x576). Unrelated images
come from scikit-image. Seed 0.

| Case | pHash distance | Counted as similar (<= 10) |
|---|---|---|
| Recompress JPEG q20-95, resize 0.25-2x, grayscale (16 cases) | 0 for every case | 16 / 16 |
| Unrelated images vs sample (12) and vs each other (152 pairs) | min 20 | 0 / 164 |
| Copy-paste splice 32 px (6 trials, saved q90) | 0-4 | 6 / 6 |
| Splice 48 px | 0-2 | 6 / 6 |
| Splice 64 px | 0-8 | 6 / 6 |
| Splice 100 px | 4-12 | **5 / 6** |
| Splice 150 px | 2-10 | 6 / 6 |

dHash and aHash behave the same way: splices stayed within 0-8 and 0-2 bits.
So a perceptual match **cannot** tell a recompressed copy from a copy with
a pasted-in region. That is why a perceptual match is only ever a *notice*.
It is never reported as integrity.

## The ledger and its hash chain

Each record holds `id`, `created_utc`, `label` (the display name you give it,
never a server path), `note`, `hashes`, `prev_hash` and `record_hash`.
`record_hash` is the SHA-256 of the record's canonical JSON (sorted keys,
without `record_hash` itself). `prev_hash` is the previous record's
`record_hash`; the first record uses 64 zeros.

`verify_chain` walks the records in order. Editing one record breaks its own
hash. If you recompute that one hash, the next record's `prev_hash` breaks
instead. **But anyone who edits a record and recomputes every hash after it
gets a consistent chain again.** The chain catches accidental or partial
edits, not deliberate ones.

## Export and import

`export_ledger` writes JSON: `{"format": "veritas-ledger/1", "exported_utc",
"records", "signature"}`. The signature covers the canonical JSON of
everything except itself:

- **With a server secret** (`LEDGER_KEY`): HMAC-SHA256. Only people who hold
  the key can produce a file that verifies. An edited and re-hashed file
  fails, and so does a file downgraded to a plain digest.
- **Without a secret**: a plain SHA-256 digest, marked *integrity-only*. It
  catches accidental change, such as a corrupted download. Anyone can edit
  the file and recompute the digest, and the import cannot detect that. The
  import report says so.

Import refuses to merge a file if its signature fails, its digest fails, or
its chain is inconsistent. When merging into the current ledger, each new
record is **re-linked** onto the tail: its old hash is kept as
`original_record_hash`, it gets a new `id` and `prev_hash`, and its
`record_hash` is recomputed. Records whose SHA-256 already exists are
skipped. The merged ledger's chain stays valid.

## Limitations

- **Session-only storage.** The ledger lives in this browser session and is
  cleared when the session ends. Export it to keep it. Visitors never see
  each other's ledgers.
- The in-session chain only catches accidental or partial edits (see above).
- Without a server secret, an export is checked only against accidental
  change. With HMAC, a valid file shows only that a key holder produced it.
- `created_utc` is this server's clock, not a trusted timestamp. This is not
  a legal chain of custody. The real mechanisms for that are an **RFC 3161
  Time-Stamp Authority** (trusted timestamps) and **C2PA Content
  Credentials** (signed provenance embedded in the file).
- A byte-identical match says nothing about what happened to the image
  before it was first added.
- Perceptual hashes cannot separate local edits from recompression.
- Pixel SHA-256 ignores metadata, including EXIF orientation.
