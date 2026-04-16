# steg_studio/core/encoder.py
"""
High-level encode functions called by the GUI.

Each function:
  1. Builds the inner payload (type tag + metadata + raw data)
  2. Optionally compresses the inner payload with zlib (Feature B)
  3. Encrypts it
  4. Wraps in the outer structure (MAGIC + size + salt + ciphertext)
  5. Embeds into the cover image via LSB with password-seeded scatter (Feature A)
  6. Returns the stego PIL.Image
"""
from __future__ import annotations

import os
import zlib
from typing import Callable

from PIL import Image

from .crypto  import encrypt
from .payload import (
    build_inner, build_outer,
    TYPE_TEXT, TYPE_FILE, TYPE_AUDIO,
)
from .lsb     import embed


# ── Public API ────────────────────────────────────────────────────────────────

def encode_text(
    cover_path: str,
    text: str,
    password: str,
    progress_callback: Callable[[float], None] | None = None,
) -> Image.Image:
    """Embed a UTF-8 text message into *cover_path*."""
    raw_data = text.encode("utf-8")
    inner    = build_inner(TYPE_TEXT, {}, raw_data)
    return _encrypt_and_embed(cover_path, inner, password, progress_callback)


def encode_file(
    cover_path: str,
    file_path: str,
    password: str,
    progress_callback: Callable[[float], None] | None = None,
) -> Image.Image:
    """Embed an arbitrary file into *cover_path*."""
    filename = os.path.basename(file_path)
    ext      = os.path.splitext(filename)[1].lstrip(".")
    with open(file_path, "rb") as fh:
        raw_data = fh.read()
    meta  = {"filename": filename, "ext": ext}
    inner = build_inner(TYPE_FILE, meta, raw_data)
    return _encrypt_and_embed(cover_path, inner, password, progress_callback)


def encode_audio(
    cover_path: str,
    audio_bytes: bytes,
    password: str,
    ext: str = "wav",
    progress_callback: Callable[[float], None] | None = None,
) -> Image.Image:
    """Embed *audio_bytes* (e.g. WAV) into *cover_path*."""
    meta  = {"ext": ext}
    inner = build_inner(TYPE_AUDIO, meta, audio_bytes)
    return _encrypt_and_embed(cover_path, inner, password, progress_callback)


# ── Internal ──────────────────────────────────────────────────────────────────

def _encrypt_and_embed(
    cover_path: str,
    inner_payload: bytes,
    password: str,
    progress_callback: Callable[[float], None] | None = None,
) -> Image.Image:
    # Feature B: try zlib compression; prepend flag byte 0x01 (compressed) or 0x00 (raw)
    compressed = zlib.compress(inner_payload, level=6)
    if len(compressed) < len(inner_payload):
        payload_to_encrypt = b"\x01" + compressed
    else:
        payload_to_encrypt = b"\x00" + inner_payload

    ciphertext, salt = encrypt(payload_to_encrypt, password)
    outer            = build_outer(ciphertext, salt)
    cover            = Image.open(cover_path).convert("RGB")
    # Feature A: pass password for scatter; Feature C: forward progress callback
    return embed(cover, outer, password=password, progress_callback=progress_callback)
