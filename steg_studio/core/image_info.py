# steg_studio/core/image_info.py
"""
Helpers that the GUI uses to display capacity and size estimates.
"""
from __future__ import annotations

import os
from PIL import Image

from .lsb     import capacity_bytes
from .payload import OUTER_HEADER_SIZE
from .crypto  import SALT_LEN


# Fernet adds ~57-byte overhead (version + timestamp + IV + HMAC)
_FERNET_OVERHEAD = 57


def get_image_info(path: str) -> dict:
    """
    Return a dict with keys:
      path, width, height, mode, capacity_bytes
    """
    img = Image.open(path)
    return {
        "path":           path,
        "width":          img.width,
        "height":         img.height,
        "mode":           img.mode,
        "capacity_bytes": capacity_bytes(img),
    }


def estimate_encrypted_size(plaintext_size: int) -> int:
    """
    Estimate total bytes that will be written into the image for a given
    number of *plaintext_size* raw (pre-encryption) data bytes.

    Layout:
      outer_header  (MAGIC + PAYLOAD_SIZE + SALT = 32 bytes)
      fernet_token  (comp_flag + plaintext_size + inner_header + fernet_overhead)

    The compression flag adds 1 byte.  Actual size may be smaller than this
    estimate when zlib compresses the payload (conservative upper bound).
    """
    # Inner header: 1 (type) + 4 (meta_len) + ~40 (typical meta JSON)
    inner_header_est  = 1 + 4 + 40
    comp_flag         = 1   # compression flag byte prepended before encryption
    fernet_token_size = comp_flag + plaintext_size + inner_header_est + _FERNET_OVERHEAD
    return OUTER_HEADER_SIZE + fernet_token_size
