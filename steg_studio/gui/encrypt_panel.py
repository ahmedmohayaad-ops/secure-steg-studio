# steg_studio/gui/encrypt_panel.py
"""Simplified Encrypt workspace.

Single column: inputs → summary → action card.
"""
from __future__ import annotations

import math
import os
from tkinter import filedialog

import customtkinter as ctk
from PIL import Image as _PI

from steg_studio.core import (
    check_magic, encode_text, encode_file, encode_audio,
    get_image_info, estimate_encrypted_size,
)

from . import theme
from .assets import icon
from .components import (
    CapacityRing,
    CoverPreview,
    HexSpinner,
    Tooltip,
    V2Badge,
    V2Button,
    V2Card,
    V2DropZone,
    V2KV,
    V2ProgressBar,
    V2Segmented,
    V2VoiceCard,
    password_strength,
    show_toast,
    themed_message,
)
from .workers import run_in_thread


def _estimate_bits(pw: str) -> float:
    pool = 0
    if any(c.islower() for c in pw): pool += 26
    if any(c.isupper() for c in pw): pool += 26
    if any(c.isdigit() for c in pw): pool += 10
    if any(not c.isalnum() for c in pw): pool += 32
    return len(pw) * math.log2(pool) if pool else 0.0


def _entropy_band(bits: float) -> tuple[str, str]:
    if bits < 28:   return ("weak",      "#FF4C4C")
    if bits < 60:   return ("fair",      "#FFD600")
    if bits < 80:   return ("strong",    "#00C9A7")
    return            ("excellent", "#4ADE80")


class EntropyBar(ctk.CTkFrame):
    """4px horizontal track with linearly-animated fill. No easing."""
    _STEP_PX = 6  # pixels moved per 16ms tick

    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", theme.BG_3)
        kwargs.setdefault("height", 4)
        kwargs.setdefault("corner_radius", 2)
        super().__init__(master, **kwargs)
        self.pack_propagate(False)
        self._fill = ctk.CTkFrame(
            self, fg_color="#FF4C4C", corner_radius=2,
            width=0, height=4)
        self._fill.place(x=0, y=0)
        self._track_w = 1
        self._target_px = 0
        self._current_px = 0
        self._tick_id: str | None = None
        self.bind("<Configure>", self._on_resize)

    def _on_resize(self, ev):
        self._track_w = max(1, ev.width)
        self._fill.configure(height=max(1, ev.height))

    def set(self, ratio: float, color: str):
        ratio = max(0.0, min(1.0, ratio))
        self._fill.configure(fg_color=color)
        self._target_px = int(self._track_w * ratio)
        if self._tick_id is None:
            self._tick()

    def _tick(self):
        self._tick_id = None
        if self._current_px == self._target_px:
            return
        if self._current_px < self._target_px:
            self._current_px = min(
                self._target_px, self._current_px + self._STEP_PX)
        else:
            self._current_px = max(
                self._target_px, self._current_px - self._STEP_PX)
        if self._current_px <= 0:
            self._fill.place_forget()
        else:
            self._fill.configure(width=self._current_px)
            if not self._fill.winfo_ismapped():
                self._fill.place(x=0, y=0)
        self._tick_id = self.after(16, self._tick)


class EncryptPanel(ctk.CTkFrame):
    def __init__(self, master, *, log=None, on_status=None, **kwargs):
        kwargs.setdefault("fg_color", theme.BG_1)
        super().__init__(master, **kwargs)
        self._log = log or (lambda *_a, **_k: None)
        self._on_status = on_status or (lambda *_a, **_k: None)

        self._cover_path: str | None = None
        self._cover_info: dict | None = None
        self._cover_img: _PI.Image | None = None
        self._payload_path: str | None = None
        self._payload_text: str = ""
        self._payload_kind = "file"
        self._running = False
        self._complete = False
        self._stego_out: str | None = None
        self._pending_image: _PI.Image | None = None
        self._sample_xy: tuple[int, int] | None = None

        self._build()
        self._refresh()

    # ── layout ────────────────────────────────────────────────────────────
    def _build(self):
        wrap = ctk.CTkScrollableFrame(
            self, fg_color=theme.BG_1,
            scrollbar_button_color=theme.BG_5,
            scrollbar_button_hover_color=theme.BG_6)
        wrap.pack(fill="both", expand=True)

        self._build_inputs_card(wrap).pack(
            fill="x", padx=theme.PAD_LG, pady=(theme.PAD_LG, theme.PAD_MD))
        self._build_preview_card(wrap).pack(
            fill="x", padx=theme.PAD_LG, pady=(0, theme.PAD_MD))
        self._build_summary_card(wrap).pack(
            fill="x", padx=theme.PAD_LG, pady=(0, theme.PAD_MD))
        self._build_action_card(wrap).pack(
            fill="x", padx=theme.PAD_LG, pady=(0, theme.PAD_LG))

    def _build_inputs_card(self, parent) -> V2Card:
        card = V2Card(parent)
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=theme.PAD_MD, pady=(theme.PAD_MD,
                                                     theme.PAD_SM))
        ctk.CTkLabel(head, text="Embed payload", font=theme.H3,
                     text_color=theme.TEXT_HI).pack(side="left")
        V2Badge(head, "FERNET · PBKDF2", "accent").pack(
            side="right")

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=theme.PAD_MD, pady=(0, theme.PAD_MD))
        body.grid_columnconfigure(0, weight=1, uniform="dz")
        body.grid_columnconfigure(1, weight=1, uniform="dz")

        # Cover
        c1 = ctk.CTkFrame(body, fg_color="transparent")
        c1.grid(row=0, column=0, sticky="ew", padx=(0, theme.PAD_SM))
        ctk.CTkLabel(c1, text="COVER CARRIER", font=theme.LABEL,
                     text_color=theme.TEXT_DIM, anchor="w").pack(
            anchor="w", pady=(0, theme.PAD_XS))
        self._cover_dz = V2DropZone(c1, kind="image", on_pick=self._on_cover)
        self._cover_dz.pack(fill="x")

        # Payload
        c2 = ctk.CTkFrame(body, fg_color="transparent")
        c2.grid(row=0, column=1, sticky="ew", padx=(theme.PAD_SM, 0))
        h2 = ctk.CTkFrame(c2, fg_color="transparent")
        h2.pack(fill="x", pady=(0, theme.PAD_XS))
        ctk.CTkLabel(h2, text="SECRET PAYLOAD", font=theme.LABEL,
                     text_color=theme.TEXT_DIM, anchor="w").pack(side="left")
        self._payload_seg = V2Segmented(
            h2, ["File", "Text", "Voice"],
            on_change=self._on_payload_kind,
            icons=["file", "text", "mic"])
        self._payload_seg.pack(side="right")

        self._payload_dz = V2DropZone(c2, kind="file",
                                      on_pick=self._on_payload_file)
        self._payload_dz.pack(fill="x")

        self._text_payload = ctk.CTkTextbox(
            c2, height=90, fg_color=theme.BG_3,
            text_color=theme.TEXT_HI, border_color=theme.STROKE_HI,
            border_width=1, corner_radius=theme.RADIUS_SM,
            font=theme.MONO)
        self._text_payload.bind(
            "<KeyRelease>", lambda _e: self._on_payload_text())

        self._voice_card = V2VoiceCard(
            c2, on_change=lambda _b: self._refresh(),
            accent=theme.AMBER)

        # Passphrase row
        row2 = ctk.CTkFrame(card, fg_color="transparent")
        row2.pack(fill="x", padx=theme.PAD_MD, pady=(0, theme.PAD_MD))

        self._pw_var = ctk.StringVar()
        self._pw_var.trace_add("write", lambda *_: self._refresh())
        self._pw_shown = False

        p1 = ctk.CTkFrame(row2, fg_color="transparent")
        p1.pack(fill="x")
        ctk.CTkLabel(p1, text="PASSPHRASE", font=theme.LABEL,
                     text_color=theme.TEXT_DIM, anchor="w").pack(
            anchor="w", pady=(0, theme.PAD_XS))
        pw_wrap = ctk.CTkFrame(p1, fg_color="transparent")
        pw_wrap.pack(fill="x")
        self._pw = ctk.CTkEntry(
            pw_wrap, textvariable=self._pw_var, show="●", height=36,
            fg_color=theme.BG_4, border_color=theme.STROKE_HI,
            border_width=1, text_color=theme.TEXT_HI,
            font=theme.MONO, placeholder_text="min. 6 chars",
            corner_radius=theme.RADIUS_SM)
        self._pw.pack(side="left", fill="x", expand=True)
        self._pw_eye = ctk.CTkButton(
            pw_wrap, text="", width=34, height=36,
            image=icon("eye", 16, theme.TEXT_LO),
            fg_color=theme.BG_4, hover_color=theme.BG_5,
            corner_radius=theme.RADIUS_SM, border_width=1,
            border_color=theme.STROKE_HI,
            command=lambda: self._toggle_pw_show(1))
        self._pw_eye.pack(side="left", padx=(6, 0))
        Tooltip(self._pw_eye, "Show/hide passphrase")

        # Entropy bar + mono caption
        strength_row = ctk.CTkFrame(card, fg_color="transparent")
        strength_row.pack(fill="x", padx=theme.PAD_MD,
                          pady=(0, theme.PAD_MD))
        self._pw_entropy = EntropyBar(strength_row)
        self._pw_entropy.pack(side="left", fill="x", expand=True)
        self._pw_entropy_caption = ctk.CTkLabel(
            strength_row, text="entropy:    0 bits",
            font=theme.MONO, text_color=theme.TEXT_DIM, anchor="e")
        self._pw_entropy_caption.pack(
            side="left", padx=(theme.PAD_SM, 0))

        return card

    def _toggle_pw_show(self, which: int):
        self._pw_shown = not self._pw_shown
        self._pw.configure(show="" if self._pw_shown else "●")
        self._pw_eye.configure(
            image=icon("eye_off" if self._pw_shown else "eye",
                       16, theme.AMBER if self._pw_shown else theme.TEXT_LO))

    def _build_preview_card(self, parent) -> V2Card:
        card = V2Card(parent)
        h = ctk.CTkFrame(card, fg_color="transparent")
        h.pack(fill="x", padx=theme.PAD_MD, pady=(theme.PAD_MD, theme.PAD_SM))
        ctk.CTkLabel(h, text="Cover preview", font=theme.H3,
                     text_color=theme.TEXT_HI).pack(side="left")
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=theme.PAD_MD, pady=(0, theme.PAD_MD))
        self._cover_preview = CoverPreview(body, accent=theme.AMBER)
        self._cover_preview.pack(fill="x")
        return card

    def _build_summary_card(self, parent) -> V2Card:
        card = V2Card(parent)
        h = ctk.CTkFrame(card, fg_color="transparent")
        h.pack(fill="x", padx=theme.PAD_MD, pady=(theme.PAD_MD,
                                                  theme.PAD_SM))
        ctk.CTkLabel(h, text="Summary", font=theme.H3,
                     text_color=theme.TEXT_HI).pack(side="left")
        self._spinner = HexSpinner(h, accent=theme.AMBER)
        self._spinner.pack(side="left", padx=(theme.PAD_SM, 0))
        self._fit_badge = V2Badge(h, "—", "neutral")
        self._fit_badge.pack(side="right")

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=theme.PAD_MD, pady=(0, theme.PAD_MD))
        kv_wrap = ctk.CTkFrame(body, fg_color="transparent")
        kv_wrap.pack(side="left", fill="x", expand=True)
        self._kv_cover = V2KV(kv_wrap, "Cover", "—")
        self._kv_cover.pack(fill="x", pady=2)
        self._kv_payload = V2KV(kv_wrap, "Payload", "—")
        self._kv_payload.pack(fill="x", pady=2)
        self._kv_output = V2KV(kv_wrap, "Output", "—")
        self._kv_output.pack(fill="x", pady=2)

        ring_wrap = ctk.CTkFrame(body, fg_color="transparent",
                                  width=100, height=100)
        ring_wrap.pack(side="right", padx=(theme.PAD_MD, 0))
        ring_wrap.pack_propagate(False)
        self._cap_ring = CapacityRing(ring_wrap, accent=theme.AMBER)
        self._cap_ring.SIZE = 96
        self._cap_ring.configure(width=96, height=96)
        self._cap_ring.pack()
        self._cap_ring.set(0, 0)

        return card

    def _build_action_card(self, parent) -> V2Card:
        card = V2Card(parent, fg_color=theme.BG_3)
        wrap = ctk.CTkFrame(card, fg_color="transparent")
        wrap.pack(fill="x", padx=theme.PAD_MD, pady=theme.PAD_MD)

        self._prog = V2ProgressBar(wrap)
        self._prog.pack(fill="x", pady=(0, theme.PAD_SM))

        self._run_btn = V2Button(wrap, "Begin encryption",
                                 variant="primary", icon_name="play",
                                 size="lg", command=self._run)
        self._run_btn.pack(fill="x", pady=(0, theme.PAD_SM))

        self._export_btn = V2Button(wrap, "Export stego",
                                    variant="secondary",
                                    icon_name="download",
                                    command=self._export)
        self._export_btn.pack(fill="x")
        return card

    # ── handlers ──────────────────────────────────────────────────────────
    _SUPPORTED_EXTS = {".png", ".bmp", ".tiff", ".tif", ".jpg", ".jpeg"}
    _LOSSY_EXTS = {".jpg", ".jpeg"}

    def _on_cover(self, path: str):
        ext = os.path.splitext(path)[1].lower()
        if ext not in self._SUPPORTED_EXTS:
            themed_message(
                self, "Unsupported Format",
                "Use PNG, BMP, TIFF, or JPEG. "
                "(JPEG is decoded to pixels; the stego output is saved as PNG.)",
                "error")
            return
        try:
            info = get_image_info(path)
        except Exception as exc:
            themed_message(self, "Invalid image", str(exc), "error")
            return
        self._cover_path = path
        self._cover_info = info
        self._cover_dz.set_meta(
            f"{info['width']}×{info['height']} · {info.get('mode','RGB')}  ·  "
            f"{theme.fmt_bytes(info['capacity_bytes'])} cap")
        try:
            cover = _PI.open(path).convert("RGB")
            cover.load()
            self._cover_img = cover
            w, h = cover.size
            self._sample_xy = (w // 2, h // 2)
            self._cover_preview.show_image(
                cover, label=os.path.basename(path).upper(),
                mode=info.get("mode", "RGB"))
        except Exception:
            pass
        self._log(f"Cover loaded · {os.path.basename(path)} · "
                  f"{theme.fmt_bytes(info['capacity_bytes'])} capacity",
                  "info")
        if ext in self._LOSSY_EXTS:
            self._log("JPEG cover · output stego will be saved as PNG "
                      "(JPEG would destroy the hidden bits).", "warn")
        self._refresh()

    def _on_payload_file(self, path: str):
        self._payload_path = path
        self._payload_kind = "file"
        self._refresh()

    def _on_payload_text(self):
        self._payload_text = self._text_payload.get("1.0", "end-1c")
        self._payload_kind = "text"
        self._refresh()

    def _on_payload_kind(self, value: str):
        self._payload_dz.pack_forget()
        self._text_payload.pack_forget()
        self._voice_card.pack_forget()
        if value == "Text":
            self._text_payload.pack(fill="x")
            self._payload_kind = "text"
        elif value == "Voice":
            self._voice_card.pack(fill="x")
            self._payload_kind = "voice"
        else:
            self._payload_dz.pack(fill="x")
            self._payload_kind = "file"
        self._refresh()

    def _payload_size(self) -> int:
        if self._payload_kind == "text":
            return len(self._payload_text.encode("utf-8"))
        if self._payload_kind == "voice":
            return self._voice_card.wav_size()
        if self._payload_path and os.path.isfile(self._payload_path):
            return os.path.getsize(self._payload_path)
        return 0

    def _refresh(self):
        raw = self._payload_size()
        enc = estimate_encrypted_size(raw) if raw else 0
        cap = self._cover_info["capacity_bytes"] if self._cover_info else 0

        if self._cover_info:
            self._kv_cover.set(
                f"{self._cover_info['width']}×{self._cover_info['height']}")
        else:
            self._kv_cover.set("—")
        if self._payload_kind == "text" and raw:
            self._kv_payload.set(f"text · {theme.fmt_bytes(raw)}")
        elif self._payload_kind == "voice" and raw:
            dur = self._voice_card.wav_duration()
            self._kv_payload.set(
                f"voice · {dur:.1f}s · {theme.fmt_bytes(raw)}")
        elif self._payload_path:
            self._kv_payload.set(
                f"{os.path.basename(self._payload_path)} · "
                f"{theme.fmt_bytes(raw)}")
        else:
            self._kv_payload.set("—")
        if self._cover_path and not self._stego_out:
            stem = os.path.splitext(os.path.basename(self._cover_path))[0]
            self._kv_output.set(f"{stem}_stego.png")
        elif self._stego_out:
            self._kv_output.set(os.path.basename(self._stego_out))

        # Capacity ring
        try:
            self._cap_ring.set(enc, cap)
        except Exception:
            pass

        # Fit badge
        if cap and raw:
            pct = enc / cap * 100
            if enc <= cap:
                self._fit_badge.set(
                    f"Payload fits ✓ · {pct:.1f}% capacity used", "ok")
            else:
                over = enc - cap
                self._fit_badge.set(
                    f"Over capacity by {theme.fmt_bytes(over)}", "crit")
        else:
            self._fit_badge.set("—", "neutral")

        # Passphrase entropy bar
        pw = self._pw_var.get()
        bits = _estimate_bits(pw)
        # Cap ratio at 128 bits — anything past that already pegs "excellent"
        ratio = min(bits / 128.0, 1.0) if bits else 0.0
        if pw:
            band, color = _entropy_band(bits)
            self._pw_entropy.set(ratio, color)
            self._pw_entropy_caption.configure(
                text=f"entropy: {int(bits):>4d} bits · {band}",
                text_color=color)
        else:
            self._pw_entropy.set(0.0, "#FF4C4C")
            self._pw_entropy_caption.configure(
                text="entropy:    0 bits",
                text_color=theme.TEXT_DIM)

        ok = bool(self._cover_path
                  and raw
                  and self._pw_var.get()
                  and (not cap or enc <= cap))
        if self._running:
            self._run_btn.configure(state="disabled", text="Encrypting…")
        else:
            self._run_btn.configure(
                state="normal" if ok else "disabled",
                text=("Reset & run again" if self._complete
                      else "Begin encryption"))
        self._export_btn.configure(
            state="normal" if self._complete else "disabled")

    # ── run ───────────────────────────────────────────────────────────────
    def _run(self):
        if self._running:
            return
        if self._complete:
            self._reset_run()
            return
        if not self._cover_path:
            return
        pwd = self._pw_var.get()
        cover = self._cover_path

        if self._payload_kind == "text":
            text = self._payload_text
            fn = lambda progress_callback: encode_text(
                cover, text, pwd, progress_callback)
            label = f"text · {theme.fmt_bytes(len(text.encode('utf-8')))}"
        elif self._payload_kind == "voice":
            wav_bytes = self._voice_card.get_wav_bytes()
            fn = lambda progress_callback: encode_audio(
                cover, wav_bytes, pwd, "wav", progress_callback)
            label = f"voice · {self._voice_card.wav_duration():.1f}s"
        else:
            path = self._payload_path
            fn = lambda progress_callback: encode_file(
                cover, path, pwd, progress_callback)
            label = f"file · {os.path.basename(path)}"

        self._running = True
        self._complete = False
        self._stego_out = None
        self._prog.reset()
        try:
            self._spinner.start()
        except Exception:
            pass
        self._refresh()

        self._log(f"▶ Begin encryption · {label}", "accent")
        run_in_thread(self, fn,
                      on_progress=self._on_progress,
                      on_done=self._on_done,
                      on_error=self._on_error)

    def _on_progress(self, p: float):
        self._prog.set(p)

    def _on_done(self, stego_img):
        self._running = False
        self._complete = True
        self._prog.set(1.0, color=theme.OK)
        try:
            self._spinner.stop()
        except Exception:
            pass
        self._pending_image = stego_img
        self._log("✓ Embedded payload across R/G/B · stego ready", "ok")
        try:
            show_toast(self.winfo_toplevel(), "Stego ready", kind="ok")
        except Exception:
            pass
        self._refresh()

    def _on_error(self, exc: BaseException):
        self._running = False
        self._complete = False
        self._prog.reset()
        try:
            self._spinner.stop()
        except Exception:
            pass
        self._log(f"✗ Encryption failed · {exc}", "crit")
        themed_message(self, "Encryption failed", str(exc), "error")
        self._refresh()

    def _export(self):
        if not getattr(self, "_pending_image", None):
            return
        default = "stego.png"
        if self._cover_path:
            stem = os.path.splitext(os.path.basename(self._cover_path))[0]
            default = f"{stem}_stego.png"
        path = filedialog.asksaveasfilename(
            title="Save stego image", defaultextension=".png",
            initialfile=default, filetypes=[("PNG", "*.png")])
        if not path:
            return
        try:
            self._pending_image.save(path, "PNG")
        except Exception as exc:
            themed_message(self, "Save failed", str(exc), "error")
            return
        self._stego_out = path
        self._kv_output.set(os.path.basename(path))
        self._log(f"Stego saved → {path}", "ok")
        try:
            show_toast(self.winfo_toplevel(),
                       f"Stego saved → {os.path.basename(path)}", kind="ok")
        except Exception:
            pass

    def _reset_run(self):
        self._complete = False
        self._stego_out = None
        self._pending_image = None
        self._prog.reset()
        self._refresh()
