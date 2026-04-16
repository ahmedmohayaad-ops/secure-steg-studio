# steg_studio/core/decoder.py
"""
High-level decode function called by the GUI.

Returns a dict:
  {
    "type":     "text" | "file" | "audio",
    "data":     bytes,
    "meta":     dict,      # filename, ext, etc.
  }

Supports both v1 images (sequential LSB, MAGIC_V1) and v2 images
(password-scattered LSB, MAGIC_V2).  v2 is tried first; if the magic
check fails the function falls back to sequential extraction for v1
backward compatibility.
"""
from __future__ import annotations

import zlib
from typing import Callable

from PIL import Image

from .lsb     import extract
from .payload import parse_outer, parse_inner, MAGIC_V1, MAGIC_V2, OUTER_HEADER_SIZE
from .crypto  import decrypt


def decode(
    stego_path: str,
    password: str,
    progress_callback: Callable[[float], None] | None = None,
) -> dict:
    """
    Extract, decrypt, and parse hidden data from *stego_path*.

    Parameters
    ----------
    stego_path:
        Path to the stego image.
    password:
        Decryption password (also used as scatter seed for v2 images).
    progress_callback:
        Optional callable receiving a float in [0.0, 1.0] as extraction
        progresses through the LSB loop.

    Raises
    ------
    ValueError
        Propagated from parse_outer  → "No hidden data found."
        Propagated from crypto.decrypt → "Decryption failed …"
        Propagated from parse_inner  → "Corrupted data …"
    """
    img = Image.open(stego_path)

    # Feature A: try scatter (v2) first, fall back to sequential (v1).
    # v2 images succeed on the first try (one callback pass).
    # v1 images fail the scatter check and retry sequentially (two passes,
    # so the progress bar fills twice — acceptable for a legacy edge case).
    try:
        raw = extract(img, password=password, progress_callback=progress_callback)
        enc, salt, version = parse_outer(raw)
        if version != 2:
            # parse_outer accepted v1 magic from a scatter extract — means it's
            # actually a v1 image; re-extract sequentially for correctness.
            raise ValueError("v1 magic from scatter extract — retry sequential")
    except ValueError:
        # Fall back to sequential extraction (handles v1 legacy images).
        raw = extract(img, password=None, progress_callback=progress_callback)
        enc, salt, version = parse_outer(raw)   # raises naturally if still bad

    plaintext = decrypt(enc, password, salt)

    # Feature B: decompress by flag byte
    #   0x01 → zlib compressed (new format)
    #   0x00 → raw (new format, no compression win)
    #   else → old format without flag byte (first byte is T/F/A type tag)
    flag = plaintext[:1]
    if flag == b"\x01":
        try:
            inner = zlib.decompress(plaintext[1:])
        except zlib.error as exc:
            raise ValueError("Corrupted compressed payload.") from exc
    elif flag == b"\x00":
        inner = plaintext[1:]
    else:
        # Legacy format: no flag byte, type tag is the first byte
        inner = plaintext

    type_str, meta, data = parse_inner(inner)
    return {"type": type_str, "meta": meta, "data": data}


def check_magic(stego_path: str) -> bool:
    """
    Return True if *stego_path* contains a valid MAGIC signature,
    False otherwise.  Does NOT require a password.

    Note: v2 (scatter) images will return False here since their bits are
    scattered by the password and cannot be read without it.  This is an
    intentional security property — scatter hides even the magic marker.
    """
    try:
        img = Image.open(stego_path)
        raw = extract(img, password=None)
        return len(raw) >= OUTER_HEADER_SIZE and raw[:8] in (MAGIC_V1, MAGIC_V2)
    except Exception:
        return False
