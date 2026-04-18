# steg_studio/gui/theme.py
"""Steg Studio v2.1 design tokens — Midnight Teal + Amber 'Tuxedo'.

Deep teal-tinted graphite base with a signature amber accent. Decrypt mode
flips to electric cyan so the two operations read as visually distinct
forensic surfaces. Token *names* preserve the prior API (BG_0..BG_3,
CYAN/MAGENTA, OK/WARN/ERR, TEXT_*, F_*) so existing callers in
components.py / app.py / encrypt_panel.py / decrypt_panel.py adopt the new
look without code changes.
"""
from __future__ import annotations

# ── Base surfaces (midnight teal ramp) ───────────────────────────────────────
BG_0 = "#03070B"   # void / status bar / page
BG_1 = "#0A111A"   # top bar / sidebar / panel
BG_2 = "#16212F"   # card
BG_3 = "#1E2D3F"   # raised / nested / hover-base
BG_4 = "#26374B"   # input surface
BG_5 = "#324558"   # button / track
BG_6 = "#3F546A"   # hover

STROKE = "#22324A"
STROKE_HI = "#384E69"
RIM = "#1A2A3D"    # 1px top rim-light on cards

# ── Signature accent: amber / antique gold (encrypt + primary CTAs) ──────────
AMBER = "#FFC247"
AMBER_HI = "#FFE08A"
AMBER_LO = "#B07A1F"
AMBER_INK = "#14110A"

# Backwards-compat aliases — encrypt mode wears amber where the old code
# expected cyan. All call sites that referenced CYAN/CYAN_DIM keep working.
CYAN = AMBER
CYAN_DIM = AMBER_LO

# ── Decrypt accent: electric cyan (bi-chromatic forensic split) ──────────────
INFO = "#5BE3F0"
INFO_DIM = "#247F8E"

MAGENTA = INFO        # decrypt mode alias
MAGENTA_DIM = INFO_DIM

# ── Semantic state ───────────────────────────────────────────────────────────
OK = "#4ADE80"
WARN = "#F0B93A"   # warn aliases the accent
ERR = "#FF5C6B"

# ── Crypto-primitive accents (for payload diagrams, key/salt/nonce chips) ────
KX_KEY = "#FFD166"     # warm gold (distinct from AMBER body)
KX_SALT = "#B89BFF"    # lifted violet
KX_NONCE = "#FF7AD9"   # hot pink
KX_MAC = "#FF8A4C"     # orange-red (frees pure red for ERR only)
KX_PAYLOAD = "#7DF9C0" # mint (clear separation from INFO cyan)
KX_MAGIC = "#9BB0C6"   # neutral steel for header magic bytes
KX_SIZE = "#5BE3F0"    # cyan for the size field

# ── Text ramp ────────────────────────────────────────────────────────────────
TEXT_HI = "#F3F6FA"
TEXT_MID = "#CBD3DE"
TEXT_LO = "#8893A4"
TEXT_DIM = "#5B6778"

# ── Fonts ────────────────────────────────────────────────────────────────────
# Spec calls for Inter Tight; on Windows Segoe UI is the original chrome font
# and renders nearly identical metrics, so we keep it as the practical default.
F_DISPLAY = ("Segoe UI", 20, "bold")
F_HEAD = ("Segoe UI", 13, "bold")
F_LABEL_B = ("Segoe UI", 11, "bold")
F_LABEL = ("Segoe UI", 11)
F_SMALL = ("Segoe UI", 10)
F_TINY = ("Segoe UI", 9)
F_MONO = ("JetBrains Mono", 11)
F_MONO_S = ("JetBrains Mono", 10)
F_BTN = ("Segoe UI", 11, "bold")


def mode_accent(mode: str) -> tuple[str, str]:
    """Return (accent, accent_dim) for the current mode.

    Encrypt → amber (signature). Decrypt → cyan (forensic scan).
    """
    if mode == "decrypt":
        return (INFO, INFO_DIM)
    return (AMBER, AMBER_LO)


def fmt_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 ** 2:
        return f"{n / 1024:.1f} KB"
    if n < 1024 ** 3:
        return f"{n / 1024 ** 2:.2f} MB"
    return f"{n / 1024 ** 3:.2f} GB"
