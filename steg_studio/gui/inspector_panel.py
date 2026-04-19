# steg_studio/gui/inspector_panel.py
"""Forensic Inspector — auto-mirrors the last encrypt/decrypt operation."""
from __future__ import annotations

import datetime as _dt
from typing import Any

import customtkinter as ctk
from PIL import Image

from . import theme
from .components import (
    ActivityLog,
    BytePeek,
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


class _OverheadBar(ctk.CTkFrame):
    """Visual comparison: raw payload vs what actually gets embedded.

    Shows two bars (raw / encrypted) scaled against the cover capacity, and
    the % overhead added by the envelope + cipher padding.
    """

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        ctk.CTkLabel(self, text="RAW vs ENCRYPTED",
                     font=("Segoe UI", 10, "bold"),
                     text_color=theme.AMBER
                     ).pack(anchor="w", pady=(0, 6))

        self._raw_row, self._raw_cv, self._raw_lbl = self._build_row("RAW")
        self._enc_row, self._enc_cv, self._enc_lbl = self._build_row("ENCRYPTED")

        foot = ctk.CTkFrame(self, fg_color=theme.BG_3, corner_radius=4)
        foot.pack(fill="x", pady=(6, 0))
        ctk.CTkLabel(foot, text="OVERHEAD",
                     font=("Segoe UI", 9, "bold"),
                     text_color=theme.TEXT_LO
                     ).pack(side="left", padx=10, pady=6)
        self._ov_val = ctk.CTkLabel(foot, text="—",
                                    font=("JetBrains Mono", 10, "bold"),
                                    text_color=theme.AMBER)
        self._ov_val.pack(side="right", padx=10, pady=6)

        self._state = (0, 0, 0)  # (raw, enc, cap)
        for cv in (self._raw_cv, self._enc_cv):
            cv.bind("<Configure>", lambda _e, _cv=cv: self._paint(_cv))

    def _build_row(self, label: str):
        import tkinter as _tk
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", pady=3)
        head = ctk.CTkFrame(row, fg_color="transparent")
        head.pack(fill="x")
        ctk.CTkLabel(head, text=label,
                     font=("Segoe UI", 9, "bold"),
                     text_color=theme.TEXT_LO).pack(side="left")
        val = ctk.CTkLabel(head, text="—",
                           font=("JetBrains Mono", 9),
                           text_color=theme.TEXT_LO)
        val.pack(side="right")
        cv = _tk.Canvas(row, bg=theme.BG_4, height=10,
                        highlightthickness=1,
                        highlightbackground=theme.STROKE)
        cv.pack(fill="x", pady=(2, 0))
        return row, cv, val

    def set(self, raw: int, enc: int, capacity: int) -> None:
        self._state = (raw, enc, capacity)
        self._raw_lbl.configure(text=theme.fmt_bytes(raw) if raw else "—")
        self._enc_lbl.configure(text=theme.fmt_bytes(enc) if enc else "—")
        if raw > 0:
            pct = ((enc - raw) / raw) * 100
            self._ov_val.configure(
                text=f"+{enc - raw:,} B  ·  {pct:.1f}% larger",
                text_color=theme.AMBER)
        else:
            self._ov_val.configure(text="—", text_color=theme.AMBER)
        self._paint(self._raw_cv)
        self._paint(self._enc_cv)

    def _paint(self, cv) -> None:
        cv.delete("all")
        w = cv.winfo_width() or 200
        h = int(cv.cget("height"))
        raw, enc, cap = self._state
        if cap <= 0:
            return
        val = raw if cv is self._raw_cv else enc
        col = theme.OK if cv is self._raw_cv else theme.AMBER
        frac = min(1.0, val / cap) if cap else 0
        fw = max(0, int((w - 2) * frac))
        if fw > 0:
            cv.create_rectangle(1, 1, 1 + fw, h - 1, fill=col, outline="")
        # Over-capacity warning stripe
        if val > cap:
            cv.create_line(w - 2, 1, w - 2, h - 1,
                           fill=theme.ERR, width=2)


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
            text="No image loaded — pick a cover or stego to begin",
            font=theme.H3, text_color=theme.TEXT_HI, anchor="w")
        self._hero_title.pack(fill="x")
        self._hero_sub = ctk.CTkLabel(
            text_col, text="Inspector updates live as you pick images and run operations.",
            font=theme.BODY_SM, text_color=theme.TEXT_LO, anchor="w")
        self._hero_sub.pack(fill="x")

        self._enc_badge = V2Badge(inner, text="—", tone="neutral")
        self._enc_badge.pack(side="right", padx=(theme.PAD_MD, 0))

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
        self._overhead = _OverheadBar(right_card)
        self._overhead.pack(fill="x", padx=theme.PAD_MD,
                            pady=(0, theme.PAD_SM))
        self._cap = CapacityBreakdown(right_card)
        self._cap.pack(fill="x", padx=theme.PAD_MD,
                       pady=(0, theme.PAD_MD))

        # ── What happened narration ──────────────────────────────────────
        log_card = self._card(self, "What happened — live pipeline narration")
        log_card.pack(fill="x", padx=theme.PAD_MD, pady=theme.PAD_SM)
        self._activity = ActivityLog(log_card)
        self._activity.pack(fill="x", padx=theme.PAD_MD,
                            pady=(0, theme.PAD_MD))

        # ── Full-width LSB grid ──────────────────────────────────────────
        lsb_card = self._card(self, "LSB Visualizer — R / G / B")
        lsb_card.pack(fill="x", padx=theme.PAD_MD, pady=theme.PAD_SM)
        self._lsb = LSBVisualizer(lsb_card)
        self._lsb.pack(fill="x", padx=theme.PAD_MD,
                       pady=(0, theme.PAD_MD))

        # ── Bit-level preview (1 sample pixel) ───────────────────────────
        peek_card = self._card(self, "Bit-level preview — 1 sample pixel")
        peek_card.pack(fill="x", padx=theme.PAD_MD, pady=theme.PAD_SM)
        self._peek = BytePeek(peek_card, mode="encrypt")
        self._peek.pack(fill="x", padx=theme.PAD_MD,
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
        # Completed ops carry a stego for encrypts, and for decrypts the
        # input itself is encrypted — in both cases the badge is "encrypted".
        self._enc_badge.set("ENCRYPTED", tone="ok")

        # Preview — show stego when available (encrypt result),
        # otherwise the cover/stego we loaded.
        display = stego_img if stego_img is not None else cover_img
        try:
            self._preview.show_image(
                display, label="STEGO" if stego_img else "IMAGE")
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

        # Capacity + overhead (payload_bytes here is the encrypted envelope size)
        try:
            total = _capacity_total(cover_img)
            self._cap.set(payload_bytes, total)
            raw_guess = int(state.get("raw_bytes", 0)) or max(0,
                payload_bytes - 80)  # rough: envelope overhead (MAGIC+SIZE+SALT+NONCE+MAC)
            self._overhead.set(raw_guess, payload_bytes, total)
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

        # BytePeek — sample center pixel
        try:
            w, h = cover_img.size
            xy = (w // 2, h // 2)
            self._peek.clear()
            self._peek.set_cover_pixel(cover_img.convert("RGB").getpixel(xy))
            if stego_img is not None:
                self._peek.set_stego_pixel(
                    stego_img.convert("RGB").getpixel(xy))
        except Exception:
            pass

    def set_preview_state(self, state: dict[str, Any]) -> None:
        """Populate Inspector from a freshly-picked image, no run yet."""
        self._state = state
        mode = state.get("mode", "encrypt")
        cover_img: Image.Image = state["cover_image"]
        payload_bytes = int(state.get("payload_bytes", 0))
        label = state.get("label", "") or "image loaded"
        encrypted = state.get("encrypted")

        if mode == "decrypt":
            self._mode_badge.set("DECRYPT · PREVIEW", tone="info")
            self._hero_title.configure(text=f"Stego loaded · {label}")
        else:
            self._mode_badge.set("ENCRYPT · PREVIEW", tone="accent")
            self._hero_title.configure(text=f"Cover loaded · {label}")
        self._hero_sub.configure(
            text="Preview — pick a payload and run to see the full trace.")

        if encrypted is True:
            self._enc_badge.set("ENCRYPTED", tone="ok")
        elif encrypted is False:
            self._enc_badge.set("NOT ENCRYPTED", tone="neutral")
        else:
            self._enc_badge.set("—", tone="neutral")

        try:
            self._preview.show_image(
                cover_img, label="STEGO" if encrypted else "COVER")
        except Exception:
            pass
        try:
            total = _capacity_total(cover_img)
            self._cap.set(payload_bytes, total)
            self._overhead.set(payload_bytes, payload_bytes, total)
        except Exception:
            pass
        try:
            self._diagram.set_payload_bytes(payload_bytes)
            self._diagram.set_progress(0.0, False)
        except Exception:
            pass
        try:
            self._lsb.set_cover_sample(cover_img)
            self._lsb.set_progress(0.0, False)
        except Exception:
            pass
        try:
            self._hist.set_cover(cover_img)
            self._hist.set_progress(0.0, False)
        except Exception:
            pass
        try:
            w, h = cover_img.size
            xy = (w // 2, h // 2)
            self._peek.clear()
            self._peek.set_cover_pixel(cover_img.convert("RGB").getpixel(xy))
        except Exception:
            pass

    def update_capacity(self, state: dict[str, Any]) -> None:
        """Lightweight update from live payload edits — no image redraw."""
        try:
            raw = int(state.get("raw_bytes", 0))
            enc = int(state.get("encrypted_bytes", 0))
            cap = int(state.get("capacity_bytes", 0))
            self._cap.set(enc, cap)
            self._diagram.set_payload_bytes(raw)
            self._overhead.set(raw, enc, cap)
        except Exception:
            pass

    def narrate(self, msg: str, tone: str = "info") -> None:
        """Append a line to the What happened narration card."""
        try:
            self._activity.add(msg, tone)
        except Exception:
            pass

    def reset_narration(self) -> None:
        try:
            self._activity.reset()
        except Exception:
            pass
