"""
Hash ledger: file identity (SHA-256), pixel identity, and visual similarity.

Pure functions over an in-memory, per-session ledger (a list of records). The
app keeps the list in st.session_state; nothing here touches disk except
reading the image being hashed.

What each hash can say:
- SHA-256 of the file bytes (FIPS 180-4): the only identity test. Equal
  digests = byte-identical files.
- pixel_sha256: SHA-256 over the decoded pixels + mode + size (+ palette).
  Survives metadata-only / container changes (EXIF strip, PNG re-chunking),
  changes with any pixel edit.
- pHash / dHash / aHash (imagehash; Zauner 2010, "Implementation and
  Benchmarking of Perceptual Image Hash Functions"): visual similarity only.
  They are designed to ignore small changes, so they also ignore small local
  edits (measured below) - never evidence of integrity.

Ledger records are hash-chained (prev_hash -> record_hash). The chain catches
accidental or partial edits; anyone who edits a record and recomputes every
hash gets a consistent chain again. Only an HMAC-signed export (server secret)
stops people without the key from producing a valid file.
"""
import hashlib
import hmac
import json
from datetime import datetime, timezone

import imagehash
from PIL import Image

from .util import error_result, make_result

GENESIS_HASH = "0" * 64
FORMAT = "veritas-ledger/1"
PERCEPTUAL = {"phash": imagehash.phash, "dhash": imagehash.dhash,
              "ahash": imagehash.average_hash}

# pHash Hamming distance (bits of 64) counted as "visually similar".
# Calibrated on assets/sample images/sampleImg.jpeg + skimage images (seed 0):
#   recompress q20-95, resize 0.25-2x, grayscale: 16/16 at distance 0
#   unrelated images (12 vs sample, 152 cross pairs): min distance 20, 0 matches
#   copy-paste splices 32/48/64/100/150 px (6 each, re-saved q90): 28/30
#   within 10 bits, 5/6 of the 100x100 splices, 14/18 of <=64 px at distance <=2.
# So a "similar" result cannot separate recompression from a local edit.
SIMILAR_BITS = 10

LIMITATIONS = [
    "Session-only storage: the ledger lives in this browser session and is "
    "cleared when the session ends. Export it to keep it.",
    "The hash chain detects accidental or partial edits only; anyone can edit "
    "records and recompute every hash to get a consistent chain.",
    "Without a server secret the export carries a plain SHA-256 digest: it "
    "catches accidental change, but anyone can edit the file and re-hash it.",
    "With an HMAC-SHA256 signature only holders of the key can produce a file "
    "that verifies; it says nothing about who holds the key.",
    "Timestamps are this server's clock, not a trusted timestamp. This is not "
    "a legal chain of custody; real mechanisms are an RFC 3161 Time-Stamp "
    "Authority and C2PA Content Credentials.",
    "A byte-identical match shows the file equals the one recorded earlier in "
    "this ledger; it says nothing about whether that earlier file was edited.",
    "Perceptual hashes cannot tell local edits from recompression or resizing: "
    "a 100x100 px splice into a 1024x576 photo stayed within "
    f"{SIMILAR_BITS} bits in 5 of 6 trials.",
    "pixel_sha256 ignores EXIF orientation and other metadata, so a changed "
    "orientation tag still counts as pixel-identical.",
]


# ── Hashing ───────────────────────────────────────────────────────
def compute_hashes(path):
    """File, pixel and perceptual hashes of one image file."""
    with open(path, "rb") as f:
        data = f.read()
    with Image.open(path) as img:
        img.load()
        px = hashlib.sha256(f"{img.mode}|{img.width}x{img.height}|".encode())
        px.update(img.tobytes())
        if img.mode == "P" and img.getpalette():
            px.update(bytes(img.getpalette()))  # same indices, new palette = new look
        out = {
            "sha256": hashlib.sha256(data).hexdigest(),
            "sha512": hashlib.sha512(data).hexdigest(),
            "md5": hashlib.md5(data).hexdigest(),  # legacy: collision-broken
            "pixel_sha256": px.hexdigest(),
            "size": len(data),
            "format": img.format or "unknown",
            "dimensions": [img.width, img.height],
        }
        rgb = img.convert("RGB")
    for k, fn in PERCEPTUAL.items():
        out[k] = str(fn(rgb))
    return out


def _hamming(a, b):
    return bin(int(a, 16) ^ int(b, 16)).count("1")


# ── Ledger ────────────────────────────────────────────────────────
def _canonical(obj):
    # sort_keys + compact separators: same content always hashes the same
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def _record_hash(record):
    return hashlib.sha256(_canonical(
        {k: v for k, v in record.items() if k != "record_hash"})).hexdigest()


def _link(record, prev_hash):
    record = {k: v for k, v in record.items() if k != "record_hash"}
    record["prev_hash"] = prev_hash
    record["record_hash"] = _record_hash(record)
    return record


def new_ledger():
    return []


def add_record(ledger, path, label="", note=""):
    """Return (new_ledger, record). The input list is not modified."""
    # display name only - strip any directory so server paths never land here
    label = str(label).replace("\\", "/").rsplit("/", 1)[-1][:200]
    record = _link({
        "id": max((r["id"] for r in ledger), default=0) + 1,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "label": label,
        "note": str(note)[:1000],
        "hashes": compute_hashes(path),
    }, ledger[-1]["record_hash"] if ledger else GENESIS_HASH)
    return ledger + [record], record


def verify_chain(ledger):
    """{valid, broken_at (index or None), n}. Consistency check only - see
    module docstring for what it cannot catch."""
    prev = GENESIS_HASH
    for i, r in enumerate(ledger):
        if r.get("prev_hash") != prev or _record_hash(r) != r.get("record_hash"):
            return {"valid": False, "broken_at": i, "n": len(ledger)}
        prev = r["record_hash"]
    return {"valid": True, "broken_at": None, "n": len(ledger)}


def ledger_stats(ledger):
    times = [r["created_utc"] for r in ledger]
    return {
        "records": len(ledger),
        "first_utc": min(times) if times else None,
        "last_utc": max(times) if times else None,
        "total_bytes": sum(r["hashes"]["size"] for r in ledger),
        "chain_valid": verify_chain(ledger)["valid"],
    }


# ── Verification ──────────────────────────────────────────────────
def _describe(r):
    return f"record #{r['id']} ({r['label'] or 'unlabelled'}, {r['created_utc']})"


def verify_image(ledger, path, threshold=SIMILAR_BITS):
    try:
        q = compute_hashes(path)
        chain = verify_chain(ledger)
        rows = []
        for r in ledger:
            h = r["hashes"]
            d = {k: _hamming(q[k], h[k]) for k in PERCEPTUAL}
            if h["sha256"] == q["sha256"]:
                kind = "byte-identical"
            elif h["pixel_sha256"] == q["pixel_sha256"]:
                kind = "pixel-identical"
            elif d["phash"] <= threshold:
                kind = "visually similar"
            else:
                kind = "no match"
            rows.append((r, kind, d))
        order = ("byte-identical", "pixel-identical", "visually similar", "no match")
        rows.sort(key=lambda x: (order.index(x[1]), x[2]["phash"]))
        count = {k: sum(1 for x in rows if x[1] == k) for k in order}

        findings = []
        if not chain["valid"]:
            findings.append(("warning",
                             f"Ledger hash chain is broken at record index "
                             f"{chain['broken_at']}: records from there on were "
                             "changed after being added, so matches against "
                             "them are unreliable."))
        for r, kind, d in rows[:5]:
            if kind == "byte-identical":
                findings.append(("info", f"Byte-identical (SHA-256) to {_describe(r)}."))
            elif kind == "pixel-identical":
                findings.append(("notice", f"Pixels identical to {_describe(r)}, "
                                 "but file bytes differ (metadata/container changed)."))
            elif kind == "visually similar":
                findings.append(("notice",
                                 f"Visually similar to {_describe(r)} (pHash distance "
                                 f"{d['phash']} of 64 bits) - NOT evidence of "
                                 "integrity; perceptual hashes cannot distinguish "
                                 "local edits from recompression. Measured: a "
                                 "100x100 px splice still matched in 5 of 6 trials."))
        if count["no match"] == len(rows):
            findings.append(("info", "Not in this session's ledger "
                             f"({len(rows)} records checked; no file, pixel or "
                             f"pHash match within {threshold} bits)."))
        if chain["valid"] and ledger:
            findings.append(("info", f"Ledger hash chain is consistent ({chain['n']} "
                             "records). This catches accidental edits only."))

        metrics = {
            "Ledger records": len(ledger),
            "Byte-identical matches": count["byte-identical"],
            "Pixel-identical matches": count["pixel-identical"],
            "Visually similar matches": count["visually similar"],
            "Similarity threshold (bits of 64)": threshold,
        }
        if rows:
            for k in PERCEPTUAL:
                metrics[f"Best {k} distance (bits of 64)"] = min(x[2][k] for x in rows)
        top = [{"record": r["id"], "label": r["label"], "created_utc": r["created_utc"],
                "match": kind, **{f"{k} distance": d[k] for k in PERCEPTUAL}}
               for r, kind, d in rows[:10]]
        query_table = {"SHA-256": q["sha256"], "SHA-512": q["sha512"],
                       "MD5 (legacy, collision-broken)": q["md5"],
                       "Pixel SHA-256": q["pixel_sha256"], "pHash": q["phash"],
                       "dHash": q["dhash"], "aHash": q["ahash"],
                       "Size (bytes)": q["size"], "Format": q["format"],
                       "Dimensions": f"{q['dimensions'][0]}x{q['dimensions'][1]}"}
        if not ledger:
            status = "insufficient_data"
            findings = [("info", "This session's ledger is empty; add records "
                         "before comparing.")]
        else:
            status = "ok"
        return make_result(
            status,
            f"Compared file, pixel and perceptual hashes against {len(ledger)} "
            "ledger records from this session.",
            findings, metrics,
            tables={"Top matches": top, "Query hashes": query_table},
            limitations=LIMITATIONS,
            details={"query": q, "chain": chain,
                     "matches": [{"id": r["id"], "match": kind, "distances": d}
                                 for r, kind, d in rows]})
    except Exception as e:
        return error_result(e, LIMITATIONS)


# ── Export / import ───────────────────────────────────────────────
def _sign(body, key):
    payload = _canonical(body)
    if key:
        return {"alg": "HMAC-SHA256",
                "value": hmac.new(key, payload, hashlib.sha256).hexdigest()}
    return {"alg": "SHA-256", "value": hashlib.sha256(payload).hexdigest(),
            "note": "integrity-only: detects accidental change; anyone can "
                    "edit this file and recompute the digest"}


def export_ledger(ledger, key=None):
    """JSON bytes. key (bytes) -> HMAC-SHA256 signature; None -> plain digest."""
    body = {"format": FORMAT,
            "exported_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "records": list(ledger)}
    return json.dumps({**body, "signature": _sign(body, key)}, indent=2).encode()


def import_ledger(data, key=None, into=None):
    """
    Returns (ledger, report). Nothing is merged when the signature or digest
    fails, or when the imported chain is inconsistent; `into` comes back
    unchanged. Merged records are re-linked onto `into`'s tail (their old
    record_hash kept as original_record_hash) and deduplicated by SHA-256.

    report: signature_valid True/False/None (None = unsigned or no key to
    check), digest_ok, signature_alg, chain_valid, accepted, merged,
    duplicates_skipped, message.
    """
    doc = json.loads(data)
    if not isinstance(doc, dict) or doc.get("format") != FORMAT:
        raise ValueError(f"not a {FORMAT} file")
    records = doc.get("records")
    need = {"sha256", "pixel_sha256", "size", *PERCEPTUAL}
    if not isinstance(records, list) or not all(
            isinstance(r, dict) and isinstance(r.get("id"), int)
            and isinstance(r.get("record_hash"), str)
            and isinstance(r.get("hashes"), dict) and need <= r["hashes"].keys()
            for r in records):
        raise ValueError("malformed records")

    body = {k: v for k, v in doc.items() if k != "signature"}
    sig = doc.get("signature") or {}
    alg = sig.get("alg")
    value = str(sig.get("value", ""))
    digest_ok = False
    if alg == "HMAC-SHA256" and key:
        sig_valid = digest_ok = hmac.compare_digest(value, _sign(body, key)["value"])
        msg = "HMAC signature " + ("verified with this server's key."
                                   if sig_valid else "does NOT match this server's key.")
    elif alg == "HMAC-SHA256":
        sig_valid = None
        msg = "File is HMAC-signed but no key is configured here, so it cannot be checked."
    else:
        if alg == "SHA-256":
            digest_ok = hmac.compare_digest(value, _sign(body, None)["value"])
        sig_valid = False if key else None
        msg = ("Unsigned file (plain SHA-256 digest "
               + ("matches" if digest_ok else "does NOT match")
               + "): anyone can edit and re-hash such a file, so this only "
                 "catches accidental change.")
        if key:
            msg += " This server expects an HMAC signature."
    chain_valid = verify_chain(records)["valid"]
    accepted = sig_valid is not False and digest_ok and chain_valid
    base = list(into or [])
    report = {"signature_valid": sig_valid, "digest_ok": digest_ok,
              "signature_alg": alg, "chain_valid": chain_valid,
              "accepted": accepted, "merged": 0, "duplicates_skipped": 0,
              "message": msg if chain_valid else msg + " Imported chain is broken."}
    if not accepted:
        return base, report
    if into is None:
        report["merged"] = len(records)
        return records, report

    seen = {r["hashes"]["sha256"] for r in base}
    next_id = max((r["id"] for r in base), default=0) + 1
    for r in records:
        if r["hashes"]["sha256"] in seen:
            report["duplicates_skipped"] += 1
            continue
        seen.add(r["hashes"]["sha256"])
        r = {**r, "id": next_id,
             "original_record_hash": r.get("original_record_hash", r["record_hash"])}
        base.append(_link(r, base[-1]["record_hash"] if base else GENESIS_HASH))
        next_id += 1
        report["merged"] += 1
    return base, report
