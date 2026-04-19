# steg_studio/gui/theme.py
"""Steg Studio v2.1 design tokens — dual palette (Dark / Light) + web-style scale.

Two palette dicts (DARK, LIGHT) get copied into module-level globals at runtime
via `set_mode("dark"|"light")`. Widgets register a callback through `on_change`
to repaint themselves (CTk widgets via `configure(...)`, raw Tk Canvas via
`cv.configure(bg=theme.BG_X)`). Token *names* preserve the prior API so old
call sites adopt the new look without changes.
"""
from __future__ import annotations

from typing import Callable

# ── Palettes ─────────────────────────────────────────────────────────────────
DARK = {
    # surfaces
    "BG_0": "#03070B", "BG_1": "#0A111A", "BG_2": "#16212F",
    "BG_3": "#1E2D3F", "BG_4": "#26374B", "BG_5": "#324558",
    "BG_6": "#3F546A",
    "STROKE": "#22324A", "STROKE_HI": "#384E69", "RIM": "#1A2A3D",
    # text
    "TEXT_HI": "#F3F6FA", "TEXT_MID": "#CBD3DE",
    "TEXT_LO": "#8893A4", "TEXT_DIM": "#5B6778",
    # amber accent
    "AMBER": "#FFC247", "AMBER_HI": "#FFE08A",
    "AMBER_LO": "#B07A1F", "AMBER_INK": "#14110A",
    # info / decrypt accent
    "INFO": "#5BE3F0", "INFO_DIM": "#247F8E",
    # semantic
    "OK": "#4ADE80", "WARN": "#F0B93A", "ERR": "#FF5C6B",
    # crypto-primitive accents
    "KX_KEY": "#FFD166", "KX_SALT": "#B89BFF",
    "KX_NONCE": "#FF7AD9", "KX_MAC": "#FF8A4C",
    "KX_PAYLOAD": "#7DF9C0", "KX_MAGIC": "#9BB0C6", "KX_SIZE": "#5BE3F0",
}

LIGHT = {
    # surfaces — near-white with hairline contrast
    "BG_0": "#FFFFFF", "BG_1": "#FAFAFB", "BG_2": "#FFFFFF",
    "BG_3": "#F4F5F7", "BG_4": "#EBECF0", "BG_5": "#E2E4EA",
    "BG_6": "#D5D8E0",
    "STROKE": "#ECEDF0", "STROKE_HI": "#DEE0E6", "RIM": "#F2F3F5",
    # text — slate ramp
    "TEXT_HI": "#0F172A", "TEXT_MID": "#334155",
    "TEXT_LO": "#64748B", "TEXT_DIM": "#94A3B8",
    # amber — slightly deeper for AA on white
    "AMBER": "#F59E0B", "AMBER_HI": "#FBBF24",
    "AMBER_LO": "#D97706", "AMBER_INK": "#FFFFFF",
    # info / decrypt accent
    "INFO": "#0EA5E9", "INFO_DIM": "#0369A1",
    # semantic
    "OK": "#10B981", "WARN": "#F59E0B", "ERR": "#EF4444",
    # crypto-primitive accents (saturated for white bg)
    "KX_KEY": "#A16207", "KX_SALT": "#7C3AED",
    "KX_NONCE": "#DB2777", "KX_MAC": "#EA580C",
    "KX_PAYLOAD": "#059669", "KX_MAGIC": "#475569", "KX_SIZE": "#0EA5E9",
}

MODE: str = "dark"

# ── Listener registry ────────────────────────────────────────────────────────
_LISTENERS: list[Callable[[], None]] = []


def on_change(cb: Callable[[], None]) -> None:
    """Register a repaint callback. Fired after every set_mode()."""
    _LISTENERS.append(cb)


def off_change(cb: Callable[[], None]) -> None:
    try:
        _LISTENERS.remove(cb)
    except ValueError:
        pass


def set_mode(mode: str) -> None:
    """Swap palette into module globals and fire all listeners."""
    pal = LIGHT if mode == "light" else DARK
    g = globals()
    for k, v in pal.items():
        g[k] = v
    g["MODE"] = mode
    # backwards-compat aliases
    g["CYAN"] = g["AMBER"]
    g["CYAN_DIM"] = g["AMBER_LO"]
    g["MAGENTA"] = g["INFO"]
    g["MAGENTA_DIM"] = g["INFO_DIM"]
    for cb in list(_LISTENERS):
        try:
            cb()
        except Exception:
            pass


# Apply default palette eagerly so module-level imports see real values.
set_mode("dark")


# ── Type scale (web-app feel) ────────────────────────────────────────────────
FONT_FAMILY = "Segoe UI"           # Inter falls back to Segoe UI on Windows
FONT_FAMILY_MONO = "JetBrains Mono"

H1 = (FONT_FAMILY, 28, "bold")
H2 = (FONT_FAMILY, 20, "bold")
H3 = (FONT_FAMILY, 15, "bold")
BODY = (FONT_FAMILY, 13)
BODY_SM = (FONT_FAMILY, 11)
LABEL = (FONT_FAMILY, 10, "bold")  # uppercase eyebrows
MONO = (FONT_FAMILY_MONO, 11)
MONO_SM = (FONT_FAMILY_MONO, 10)

# Backwards-compat font tokens
F_DISPLAY = H2
F_HEAD = H3
F_LABEL_B = (FONT_FAMILY, 11, "bold")
F_LABEL = BODY_SM
F_SMALL = (FONT_FAMILY, 10)
F_TINY = (FONT_FAMILY, 9)
F_MONO = MONO
F_MONO_S = MONO_SM
F_BTN = (FONT_FAMILY, 11, "bold")

# ── Spacing + radius ─────────────────────────────────────────────────────────
PAD_XS, PAD_SM, PAD_MD, PAD_LG, PAD_XL = 4, 8, 16, 24, 40
RADIUS_SM, RADIUS_MD, RADIUS_LG = 6, 10, 16


def mode_accent(mode: str) -> tuple[str, str]:
    """Return (accent, accent_dim) for the operation mode.

    Encrypt → amber. Decrypt → info/cyan.
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
