# steg_studio/core/payload.py
"""
Binary payload layout (v2 format)
──────────────────────────────────
Outer (written into image pixels via scattered LSB):
  MAGIC          8  bytes  — b'STGSTD02'  (v1 legacy: b'STGSTD01')
  PAYLOAD_SIZE   8  bytes  — uint64 LE, size of ENCRYPTED_PAYLOAD in bytes
  SALT          16  bytes  — PBKDF2 salt
  ENCRYPTED_PAYLOAD        — Fernet token

Inner (after decryption):
  COMP_FLAG      1  byte   — 0x01 = zlib-compressed, 0x00 = raw
                             (old v1 images have no flag; first byte is T/F/A)
  TYPE           1  byte   — b'T' text | b'F' file | b'A' audio
  META_LEN       4  bytes  — uint32 LE, length of metadata JSON
  META           N  bytes  — UTF-8 JSON string
  DATA                     — raw (or compressed) payload bytes
"""
import struct
import json

MAGIC_V1 = b"STGSTD01"   # legacy sequential embedding (read-only)
MAGIC_V2 = b"STGSTD02"   # scatter embedding (current write format)
MAGIC    = MAGIC_V2       # alias used by build_outer

_MAGIC_LEN        = 8
_PAYLOAD_SIZE_LEN = 8   # uint64
_SALT_LEN         = 16

OUTER_HEADER_SIZE = _MAGIC_LEN + _PAYLOAD_SIZE_LEN + _SALT_LEN  # 32 bytes

# Inner type tags
TYPE_TEXT  = b"T"
TYPE_FILE  = b"F"
TYPE_AUDIO = b"A"


# ── Outer layer ───────────────────────────────────────────────────────────────

def build_outer(encrypted_payload: bytes, salt: bytes) -> bytes:
    size = struct.pack("<Q", len(encrypted_payload))
    return MAGIC + size + salt + encrypted_payload


def parse_outer(raw: bytes) -> tuple[bytes, bytes, int]:
    """
    Validate magic, return (encrypted_payload, salt, version).
    version is 2 for MAGIC_V2 (scatter) or 1 for MAGIC_V1 (sequential).
    Raises ValueError on bad magic or truncated data.
    """
    if len(raw) < OUTER_HEADER_SIZE:
        raise ValueError("Data too short — no valid header.")
    magic = raw[:_MAGIC_LEN]
    if magic == MAGIC_V2:
        version = 2
    elif magic == MAGIC_V1:
        version = 1
    else:
        raise ValueError("No hidden data found.")          # surfaced in GUI
    payload_size = struct.unpack("<Q", raw[_MAGIC_LEN:_MAGIC_LEN + _PAYLOAD_SIZE_LEN])[0]
    salt_start   = _MAGIC_LEN + _PAYLOAD_SIZE_LEN
    salt         = raw[salt_start: salt_start + _SALT_LEN]
    enc_start    = salt_start + _SALT_LEN
    enc_end      = enc_start + payload_size
    if len(raw) < enc_end:
        raise ValueError("Corrupted data — payload truncated.")
    return raw[enc_start:enc_end], salt, version


# ── Inner layer ───────────────────────────────────────────────────────────────

def build_inner(type_tag: bytes, meta: dict, data: bytes) -> bytes:
    meta_bytes = json.dumps(meta, ensure_ascii=False).encode("utf-8")
    meta_len   = struct.pack("<I", len(meta_bytes))
    return type_tag + meta_len + meta_bytes + data


def parse_inner(plaintext: bytes) -> tuple[str, dict, bytes]:
    """
    Returns (type_str, meta_dict, data_bytes).
    type_str is one of 'text', 'file', 'audio'.
    """
    _TAG_MAP = {b"T": "text", b"F": "file", b"A": "audio"}
    if len(plaintext) < 5:
        raise ValueError("Corrupted inner payload.")
    tag = plaintext[:1]
    if tag not in _TAG_MAP:
        raise ValueError(f"Unknown payload type tag: {tag!r}")
    meta_len  = struct.unpack("<I", plaintext[1:5])[0]
    meta_end  = 5 + meta_len
    if len(plaintext) < meta_end:
        raise ValueError("Corrupted inner payload — metadata truncated.")
    meta      = json.loads(plaintext[5:meta_end].decode("utf-8"))
    data      = plaintext[meta_end:]
    return _TAG_MAP[tag], meta, data
