# steg_studio/gui/inspector_panel.py
"""Forensic Inspector — auto-mirrors the last encrypt/decrypt operation."""
from __future__ import annotations

import datetime as _dt
from typing import Any

import customtkinter as ctk
from PIL import Image

from . import theme
from .components import (
    CapacityBreakdown,
    CoverPreview,
    HistogramPanel,
    LSBVisualizer,
    PayloadDiagram,
    V2Badge,
)


def _capacity_total(img: Image.Image) -> int:
    # 1 LSB per channel, 3 channels per pixel.
    w, h = img.size
    return w * h * 3 // 8


class InspectorPanel(ctk.CTkScrollableFrame):
    """Single scrollable column with the full forensic stack.

    Public API:
        set_state(state: dict)
            keys: mode ("encrypt"|"decrypt"), cover_image, stego_image,
                  payload_bytes, label, timestamp.
    """

    def __init__(self, master):
        super().__init__(master, fg_color=theme.BG_1)
        self._state: dict[str, Any] | None = None

        # ── Hero banner ──────────────────────────────────────────────────
        hero = ctk.CTkFrame(self, fg_color=theme.BG_2,
                            corner_radius=theme.RADIUS_MD,
                            border_width=1, border_color=theme.STROKE)
        hero.pack(fill="x", padx=theme.PAD_MD, pady=(theme.PAD_MD,
                                                     theme.PAD_SM))
        inner = ctk.CTkFrame(hero, fg_color="transparent")
        inner.pack(fill="x", padx=theme.PAD_LG, pady=theme.PAD_MD)

        self._mode_badge = V2Badge(inner, text="—", tone="neutral")
        self._mode_badge.pack(side="left", padx=(0, theme.PAD_MD))

        text_col = ctk.CTkFrame(inner, fg_color="transparent")
        text_col.pack(side="left", fill="x", expand=True)
        self._hero_title = ctk.CTkLabel(
            text_col,
            text="No operation yet — run an encrypt or decrypt to populate",
            font=theme.H3, text_color=theme.TEXT_HI, anchor="w")
        self._hero_title.pack(fill="x")
        self._hero_sub = ctk.CTkLabel(
            text_col, text="Inspector mirrors the most recent run.",
            font=theme.BODY_SM, text_color=theme.TEXT_LO, anchor="w")
        self._hero_sub.pack(fill="x")

        # ── Two-col top: preview + (payload diagram, capacity) ───────────
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=theme.PAD_MD, pady=theme.PAD_SM)
        top.grid_columnconfigure(0, weight=1, uniform="col")
        top.grid_columnconfigure(1, weight=1, uniform="col")

        left_card = self._card(top, "Image")
        left_card.grid(row=0, column=0, sticky="nsew",
                       padx=(0, theme.PAD_SM))
        self._preview = CoverPreview(left_card, accent=theme.AMBER)
        self._preview.pack(fill="both", expand=True,
                           padx=theme.PAD_MD, pady=(0, theme.PAD_MD))

        right_card = self._card(top, "Payload & Capacity")
        right_card.grid(row=0, column=1, sticky="nsew",
                        padx=(theme.PAD_SM, 0))
        self._diagram = PayloadDiagram(right_card)
        self._diagram.pack(fill="x", padx=theme.PAD_MD,
                           pady=(0, theme.PAD_SM))
        self._cap = CapacityBreakdown(right_card)
        self._cap.pack(fill="x", padx=theme.PAD_MD,
                       pady=(0, theme.PAD_MD))

        # ── Full-width LSB grid ──────────────────────────────────────────
        lsb_card = self._card(self, "LSB Visualizer — R / G / B")
        lsb_card.pack(fill="x", padx=theme.PAD_MD, pady=theme.PAD_SM)
        self._lsb = LSBVisualizer(lsb_card)
        self._lsb.pack(fill="x", padx=theme.PAD_MD,
                       pady=(0, theme.PAD_MD))

        # ── Full-width histogram ─────────────────────────────────────────
        hist_card = self._card(self, "Histogram — cover vs stego")
        hist_card.pack(fill="x", padx=theme.PAD_MD,
                       pady=(theme.PAD_SM, theme.PAD_MD))
        self._hist = HistogramPanel(hist_card)
        self._hist.pack(fill="x", padx=theme.PAD_MD,
                        pady=(0, theme.PAD_MD))

    def _card(self, parent, title: str) -> ctk.CTkFrame:
        card = ctk.CTkFrame(parent, fg_color=theme.BG_2,
                            corner_radius=theme.RADIUS_MD,
                            border_width=1, border_color=theme.STROKE)
        ctk.CTkLabel(card, text=title, font=theme.H3,
                     text_color=theme.TEXT_HI, anchor="w").pack(
            fill="x", padx=theme.PAD_MD, pady=(theme.PAD_MD,
                                               theme.PAD_SM))
        return card

    # ── Public API ───────────────────────────────────────────────────────
    def set_state(self, state: dict[str, Any]) -> None:
        self._state = state
        mode = state.get("mode", "encrypt")
        cover_img: Image.Image = state["cover_image"]
        stego_img: Image.Image | None = state.get("stego_image")
        payload_bytes = int(state.get("payload_bytes", 0))
        label = state.get("label", "")
        ts = state.get("timestamp") or _dt.datetime.now().strftime("%H:%M:%S")

        # Hero
        if mode == "decrypt":
            self._mode_badge.set("DECRYPT", tone="info")
            self._hero_title.configure(
                text=f"Last decryption · {label}")
        else:
            self._mode_badge.set("ENCRYPT", tone="accent")
            self._hero_title.configure(
                text=f"Last encryption · {label}")
        self._hero_sub.configure(
            text=f"{payload_bytes:,} B payload · {ts}")

        # Preview — show stego when available (encrypt result),
        # otherwise the cover/stego we loaded.
        display = stego_img if stego_img is not None else cover_img
        try:
            self._preview._raw = display.convert("RGB")
            self._preview._dims = display.size
            self._preview._mode = "RGB"
            self._preview._placeholder = "STEGO" if stego_img else "IMAGE"
            self._preview._render()
        except Exception:
            pass

        # LSB visualizer — sample from the cover image
        try:
            self._lsb.set_cover_sample(cover_img)
            self._lsb.set_progress(1.0, False)
        except Exception:
            pass

        # Payload diagram
        try:
            self._diagram.set_payload_bytes(payload_bytes)
            self._diagram.set_progress(1.0, False)
        except Exception:
            pass

        # Capacity
        try:
            total = _capacity_total(cover_img)
            self._cap.set(payload_bytes, total)
        except Exception:
            pass

        # Histogram
        try:
            self._hist.set_cover(cover_img)
            if stego_img is not None:
                self._hist.set_stego(stego_img)
            self._hist.set_progress(1.0, False)
        except Exception:
            pass
