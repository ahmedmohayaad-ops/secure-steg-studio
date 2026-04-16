# steg_studio/core/lsb.py
"""
LSB steganography engine.

Embedding strategy
──────────────────
We modify the least-significant bit of each colour channel of each pixel
(R, G, B — alpha is left untouched for RGBA images).
One pixel holds 3 bits → capacity = (W × H × 3) // 8  bytes.

The first 64 bits (8 bytes) encode the total number of data bytes so the
extractor knows when to stop.

Scatter mode (when *password* is supplied)
──────────────────────────────────────────
The 64-bit length prefix is always written sequentially at channel indices
0–63 so that extraction can read the size without knowing the password.
The remaining data bits are placed at indices chosen by
``random.sample(range(available), n_data_bits)`` seeded from the password
(O(k) time, where k = payload bits — efficient even for large images).
"""
from __future__ import annotations

import hashlib
import random
from typing import Callable

import numpy as np
from PIL import Image


_CHANNELS      = 3       # R, G, B  (not alpha)
_PREFIX_BITS   = 64      # 8-byte length prefix, always sequential at idx 0–63
_PROGRESS_STEP = 5_000   # call progress_callback every N bits


def _data_scatter_indices(total_channels: int, password: str, n_data_bits: int) -> list[int]:
    """
    Return *n_data_bits* unique channel indices drawn from [64, total_channels)
    in a deterministic order seeded from *password*.

    Uses ``random.sample`` which runs in O(n_data_bits) — fast regardless
    of image size, because it never builds a full-length shuffle list.
    """
    available = total_channels - _PREFIX_BITS
    digest    = hashlib.sha256(b"scatter_v2:" + password.encode()).digest()
    seed      = int.from_bytes(digest, "big")
    rng       = random.Random(seed)
    raw       = rng.sample(range(available), n_data_bits)
    # Offset by _PREFIX_BITS so indices are in [64, total_channels)
    return [i + _PREFIX_BITS for i in raw]


def capacity_bytes(img: Image.Image) -> int:
    """Maximum number of data bytes that fit in *img*."""
    w, h  = img.size
    total_bits = w * h * _CHANNELS
    # First 64 bits are used for the length prefix
    return (total_bits - _PREFIX_BITS) // 8


def _to_rgb(img: Image.Image) -> np.ndarray:
    """Return a (H, W, ≥3) uint8 array in RGB(A) order."""
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    return np.array(img, dtype=np.uint8)


def embed(
    img: Image.Image,
    data: bytes,
    password: str | None = None,
    progress_callback: Callable[[float], None] | None = None,
) -> Image.Image:
    """
    Return a new PIL image with *data* hidden in the LSBs.

    Parameters
    ----------
    img:
        Cover image.
    data:
        Bytes to hide.
    password:
        When supplied, data bits are scattered across the image using a
        PRNG seeded from the password.  The 64-bit length prefix always
        stays at channels 0–63 so the size can be read without the password.
        The same password must be passed to :func:`extract`.
    progress_callback:
        Optional callable receiving a float in [0.0, 1.0] as embedding
        progresses.  Called every ~5 000 bits and once at completion.

    Raises
    ------
    ValueError
        If *data* is larger than the image capacity.
    """
    cap = capacity_bytes(img)
    if len(data) > cap:
        raise ValueError(
            f"Data too large: {len(data):,} bytes > capacity {cap:,} bytes."
        )

    pixels = _to_rgb(img).copy()
    H, W   = pixels.shape[:2]

    # Build the bit-stream components
    length_bits = _int_to_bits(len(data), _PREFIX_BITS)
    data_bits   = _bytes_to_bits(data)

    # Flatten the RGB channels into a 1-D view
    flat = pixels[:, :, :_CHANNELS].reshape(-1)   # shape: H*W*3

    # ── Write length prefix sequentially at channels 0..63 ───────────────────
    for i, bit in enumerate(length_bits):
        flat[i] = (flat[i] & 0xFE) | bit

    # ── Write data bits at scatter or sequential positions ────────────────────
    if password is not None:
        data_indices = _data_scatter_indices(len(flat), password, len(data_bits))
    else:
        data_indices = list(range(_PREFIX_BITS, _PREFIX_BITS + len(data_bits)))

    n_data_bits = len(data_bits)
    for i, (bit, chan_idx) in enumerate(zip(data_bits, data_indices)):
        flat[chan_idx] = (flat[chan_idx] & 0xFE) | bit
        if progress_callback and i % _PROGRESS_STEP == 0:
            progress_callback(i / n_data_bits)

    if progress_callback:
        progress_callback(1.0)

    # Write modified values back
    pixels[:, :, :_CHANNELS] = flat.reshape(H, W, _CHANNELS)

    mode = img.mode if img.mode in ("RGB", "RGBA") else "RGB"
    return Image.fromarray(pixels, mode)


def extract(
    img: Image.Image,
    password: str | None = None,
    progress_callback: Callable[[float], None] | None = None,
) -> bytes:
    """
    Extract hidden data from *img*.

    Parameters
    ----------
    img:
        Stego image to read from.
    password:
        Must match the password used during :func:`embed` when scatter mode
        was active.  Pass ``None`` for images embedded without scatter (v1).
    progress_callback:
        Optional callable receiving a float in [0.0, 1.0].

    Returns the raw bytes.  Raises ValueError if the image carries no
    recognisable payload (the caller checks the MAGIC signature separately).
    """
    pixels = _to_rgb(img)
    flat   = pixels[:, :, :_CHANNELS].reshape(-1)

    # ── Read 64-bit length prefix (always at channels 0..63) ─────────────────
    length_bits = [int(flat[i] & 1) for i in range(_PREFIX_BITS)]
    n_bytes     = _bits_to_int(length_bits)

    if n_bytes == 0 or n_bytes > len(flat) // 8:
        raise ValueError("No hidden data found.")

    # ── Read data bits at scatter or sequential positions ─────────────────────
    n_data_bits = n_bytes * 8

    if password is not None:
        data_indices = _data_scatter_indices(len(flat), password, n_data_bits)
    else:
        data_indices = list(range(_PREFIX_BITS, _PREFIX_BITS + n_data_bits))

    data_bits = []
    for i, chan_idx in enumerate(data_indices):
        data_bits.append(int(flat[chan_idx] & 1))
        if progress_callback and i % _PROGRESS_STEP == 0:
            progress_callback(i / n_data_bits)

    if progress_callback:
        progress_callback(1.0)

    return _bits_to_bytes(data_bits)


# ── Bit helpers ───────────────────────────────────────────────────────────────

def _int_to_bits(value: int, width: int) -> list[int]:
    return [(value >> (width - 1 - i)) & 1 for i in range(width)]


def _bits_to_int(bits: list[int]) -> int:
    v = 0
    for b in bits:
        v = (v << 1) | b
    return v


def _bytes_to_bits(data: bytes) -> list[int]:
    bits: list[int] = []
    for byte in data:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    return bits


def _bits_to_bytes(bits: list[int]) -> bytes:
    out = bytearray()
    for i in range(0, len(bits), 8):
        chunk = bits[i:i + 8]
        if len(chunk) < 8:
            break
        out.append(_bits_to_int(chunk))
    return bytes(out)
