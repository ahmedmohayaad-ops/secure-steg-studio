# steg_studio/gui/widgets.py
"""
Reusable widget helpers — enhanced with animations, history panel,
capacity warnings, SVG-style icons, progress bar, and spinner.
"""
from __future__ import annotations

import datetime
import math
import struct
import wave as _wave
import io

import customtkinter as ctk
from PIL import Image, ImageDraw


# ── Design Tokens ─────────────────────────────────────────────────────────────

FONT_MONO    = ("JetBrains Mono", 11)
FONT_MONO_S  = ("JetBrains Mono", 10)
FONT_LABEL   = ("Segoe UI", 12)
FONT_LABEL_B = ("Segoe UI", 12, "bold")
FONT_SMALL   = ("Segoe UI", 10)

ACCENT      = "#00C9A7"
ACCENT_DIM  = "#007A65"
RED         = "#FF4C4C"
ORANGE      = "#FF8C00"
GREEN       = "#00C9A7"
YELLOW      = "#FFD600"

CARD_DARK   = ("gray92", "#1A1D23")
CARD_MID    = ("gray85", "#22262F")
BORDER      = ("gray75", "#2E3340")


# ── SVG-style icon helpers ────────────────────────────────────────────────────

def _make_icon(draw_fn, size: int = 18, color: str = ACCENT) -> ctk.CTkImage:
    scale = 4
    big   = size * scale
    img   = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d     = ImageDraw.Draw(img)
    draw_fn(d, big, color)
    img   = img.resize((size, size), Image.LANCZOS)
    return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))


def _icon_lock(d, s, c):
    m = s // 8
    d.arc([3*m, m, 5*m, 4*m], start=180, end=0, fill=c, width=max(1, m))
    d.rounded_rectangle([2*m, 3*m, 6*m, 7*m], radius=m//2, fill=c)

def _icon_image(d, s, c):
    m = s // 8
    d.rounded_rectangle([m, 2*m, 7*m, 6*m], radius=m, outline=c, width=max(1, m//2))
    d.ellipse([2*m, 3*m, 3*m, 4*m], fill=c)
    d.polygon([2*m, 6*m, 4*m, 4*m, 5*m, 5*m, 6*m, 4*m, 7*m, 6*m], fill=c)

def _icon_file(d, s, c):
    m = s // 8
    d.polygon([2*m, m, 5*m, m, 6*m, 2*m, 6*m, 7*m, 2*m, 7*m], fill=c)

def _icon_mic(d, s, c):
    m = s // 8
    d.rounded_rectangle([3*m, m, 5*m, 5*m], radius=m, fill=c)
    d.arc([2*m, 3*m, 6*m, 6*m], start=0, end=180, fill=c, width=max(1, m//2))
    d.line([4*m, 6*m, 4*m, 7*m], fill=c, width=max(1, m//2))
    d.line([3*m, 7*m, 5*m, 7*m], fill=c, width=max(1, m//2))

def _icon_history(d, s, c):
    m = s // 8
    d.arc([m, m, 7*m, 7*m], start=60, end=350, fill=c, width=max(1, m//2))
    d.polygon([m, 3*m, 3*m, m, 3*m, 3*m], fill=c)
    d.line([4*m, 3*m, 4*m, 5*m], fill=c, width=max(1, m//2))
    d.line([4*m, 5*m, 5*m, 5*m], fill=c, width=max(1, m//2))

def _icon_check(d, s, c):
    m = s // 8
    d.line([m, 4*m, 3*m, 6*m, 7*m, 2*m], fill=c, width=max(1, m))

def _icon_warn(d, s, c):
    m = s // 8
    d.polygon([4*m, m, 7*m, 7*m, m, 7*m], outline=c, fill=None, width=max(1, m//2))
    d.line([4*m, 3*m, 4*m, 5*m], fill=c, width=max(1, m//2))

def _icon_play(d, s, c):
    m = s // 8
    d.polygon([2*m, m, 7*m, 4*m, 2*m, 7*m], fill=c)

def _icon_stop(d, s, c):
    m = s // 8
    d.rectangle([2*m, 2*m, 6*m, 6*m], fill=c)

def _icon_record(d, s, c):
    m = s // 8
    d.ellipse([m, m, 7*m, 7*m], fill=c)

def _icon_save(d, s, c):
    m = s // 8
    d.rounded_rectangle([m, m, 7*m, 7*m], radius=m//2, outline=c, width=max(1, m//2))
    d.rectangle([2*m, 4*m, 6*m, 7*m], fill=c)
    d.rectangle([3*m, 5*m, 5*m, 7*m], fill="#1A1D23")

def _icon_embed(d, s, c):
    m = s // 8
    d.rectangle([m, 2*m, 7*m, 6*m], outline=c, width=max(1, m//2))
    d.line([4*m, 3*m, 4*m, 5*m], fill=c, width=max(1, m//2))
    d.polygon([3*m, 5*m, 4*m, 7*m, 5*m, 5*m], fill=c)

def _icon_batch(d, s, c):
    m = s // 8
    for i, ox in enumerate([0, m, 2*m]):
        d.rounded_rectangle([ox+m, m+i*m//2, ox+5*m, 5*m+i*m//2],
                             radius=m//2, outline=c, width=max(1, m//2))

def _icon_clear(d, s, c):
    m = s // 8
    d.line([2*m, 2*m, 6*m, 6*m], fill=c, width=max(1, m))
    d.line([6*m, 2*m, 2*m, 6*m], fill=c, width=max(1, m))


_ICON_CACHE: dict[str, ctk.CTkImage] = {}
_ICON_FN_MAP = {
    "lock": _icon_lock, "image": _icon_image,
    "file": _icon_file, "mic": _icon_mic,
    "history": _icon_history, "check": _icon_check,
    "warn": _icon_warn, "play": _icon_play,
    "stop": _icon_stop, "record": _icon_record,
    "save": _icon_save, "embed": _icon_embed,
    "batch": _icon_batch, "clear": _icon_clear,
}

def get_icon(name: str, size: int = 16, color: str = ACCENT) -> ctk.CTkImage | None:
    key = f"{name}_{size}_{color}"
    if key not in _ICON_CACHE and name in _ICON_FN_MAP:
        _ICON_CACHE[key] = _make_icon(_ICON_FN_MAP[name], size, color)
    return _ICON_CACHE.get(key)


# ── Section Header ────────────────────────────────────────────────────────────

class SectionHeader(ctk.CTkFrame):
    def __init__(self, master, text: str, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        bar = ctk.CTkFrame(self, width=3, height=18, fg_color=ACCENT, corner_radius=2)
        bar.pack(side="left", padx=(0, 8))
        bar.pack_propagate(False)
        ctk.CTkLabel(self, text=text.upper(), font=("Segoe UI", 10, "bold"),
                     text_color=(ACCENT_DIM, ACCENT)).pack(side="left")


# ── Card Frame ────────────────────────────────────────────────────────────────

class Card(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", CARD_DARK)
        kwargs.setdefault("corner_radius", 10)
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("border_color", BORDER)
        super().__init__(master, **kwargs)


# ── Animated Progress Bar ────────────────────────────────────────────────────

class ProgressBar(ctk.CTkFrame):
    """Indeterminate animated progress bar. Call start() / stop()."""
    HEIGHT = 4

    def __init__(self, master, **kwargs):
        super().__init__(master, height=self.HEIGHT,
                         fg_color=("gray78", "#2E3340"), corner_radius=2, **kwargs)
        self.pack_propagate(False)
        self._fill = ctk.CTkFrame(self, height=self.HEIGHT,
                                   fg_color=ACCENT, corner_radius=2, width=0)
        self._fill.place(x=0, y=0, relheight=1.0)
        self._running = False
        self._phase   = 0.0

    def start(self):
        self._running = True
        self._animate()

    def stop(self):
        self._running = False
        self._fill.place_configure(x=0, relwidth=0, width=0)

    def set_fraction(self, frac: float):
        self.update_idletasks()
        w = self.winfo_width()
        self._fill.place_configure(x=0, width=max(0, int(w * min(frac, 1.0))), relwidth=0)

    def _animate(self):
        if not self._running:
            return
        self.update_idletasks()
        w = self.winfo_width()
        if w < 4:
            self.after(80, self._animate)
            return
        self._phase = (self._phase + 0.04) % 1.0
        fill_w = int(w * 0.35)
        x = int((w + fill_w) * self._phase) - fill_w
        self._fill.place_configure(x=x, width=fill_w, relwidth=0)
        self.after(30, self._animate)


# ── Spinner ───────────────────────────────────────────────────────────────────

class Spinner(ctk.CTkLabel):
    """Braille-frame spinner label. Call start() / stop()."""
    _FRAMES = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]

    def __init__(self, master, **kwargs):
        kwargs.setdefault("text", "")
        kwargs.setdefault("font", ("Segoe UI", 13))
        kwargs.setdefault("text_color", (ACCENT_DIM, ACCENT))
        kwargs.setdefault("width", 20)
        super().__init__(master, **kwargs)
        self._running = False
        self._idx     = 0

    def start(self):
        self._running = True
        self._tick()

    def stop(self):
        self._running = False
        self.configure(text="")

    def _tick(self):
        if not self._running:
            return
        self.configure(text=self._FRAMES[self._idx % len(self._FRAMES)])
        self._idx += 1
        self.after(80, self._tick)


# ── Capacity Warning Banner ───────────────────────────────────────────────────

class CapacityWarning(ctk.CTkFrame):
    """Auto-show/hide warning when capacity usage exceeds threshold."""
    WARN_PCT = 0.80
    CRIT_PCT = 1.00

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._inner = ctk.CTkFrame(self, corner_radius=8,
                                    fg_color=("#FFF3CD", "#3A2F00"),
                                    border_width=1, border_color=("#FFD600", "#7A5F00"))
        row = ctk.CTkFrame(self._inner, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=7)
        self._icon_lbl = ctk.CTkLabel(row, text="⚠", font=("Segoe UI", 13),
                                       text_color=("#7A5F00", YELLOW), width=20)
        self._icon_lbl.pack(side="left")
        self._msg = ctk.CTkLabel(row, text="", anchor="w", font=("Segoe UI", 11),
                                  text_color=("#5C4400", YELLOW))
        self._msg.pack(side="left", padx=(4, 0), fill="x", expand=True)
        ctk.CTkButton(row, text="✕", width=22, height=22, font=("Segoe UI", 10),
                      fg_color="transparent", hover_color=("#FFE580", "#5C4A00"),
                      text_color=("#7A5F00", YELLOW),
                      command=self._dismiss).pack(side="right")
        self._visible = False

    def check(self, used: int, total: int):
        if total <= 0:
            self._hide(); return
        pct = used / total
        if pct >= self.CRIT_PCT:
            self._show(f"Image too small — data exceeds capacity by {_fmt_bytes(used - total)}", critical=True)
        elif pct >= self.WARN_PCT:
            self._show(f"Approaching capacity — {pct*100:.0f}% used  ({_fmt_bytes(total - used)} remaining)")
        else:
            self._hide()

    def _show(self, msg: str, critical: bool = False):
        self._msg.configure(text=msg)
        if critical:
            self._inner.configure(fg_color=("#FFE5E5", "#3A0000"),
                                   border_color=("#FF4C4C", "#7A0000"))
            self._icon_lbl.configure(text="✖", text_color=("#C62828", RED))
            self._msg.configure(text_color=("#7A0000", RED))
        else:
            self._inner.configure(fg_color=("#FFF3CD", "#3A2F00"),
                                   border_color=("#FFD600", "#7A5F00"))
            self._icon_lbl.configure(text="⚠", text_color=("#7A5F00", YELLOW))
            self._msg.configure(text_color=("#5C4400", YELLOW))
        if not self._visible:
            self._inner.pack(fill="x")
            self._visible = True

    def _hide(self):
        if self._visible:
            self._inner.pack_forget()
            self._visible = False

    def _dismiss(self):
        self._hide()


# ── Image Info Panel ──────────────────────────────────────────────────────────

class ImageInfoPanel(Card):
    THUMB_SIZE = (220, 180)

    def __init__(self, master, show_info: bool = True, **kwargs):
        super().__init__(master, **kwargs)
        self._show_info = show_info
        self._photo     = None
        self._capacity  = 0
        self._build_ui()

    def _build_ui(self):
        self._img_label = ctk.CTkLabel(
            self, text="No image selected", font=FONT_SMALL,
            width=220, height=180, fg_color=("gray80", "#2A2F3A"),
            corner_radius=8, text_color=("gray50", "gray55"))
        self._img_label.pack(pady=(12, 8), padx=12)

        if not self._show_info:
            return

        self._info_var = ctk.StringVar(value="")
        ctk.CTkLabel(self, textvariable=self._info_var, justify="left",
                     font=FONT_MONO_S, text_color=("gray40", "gray65")).pack(anchor="w", padx=14, pady=(0, 2))

        self._msg_raw_var = ctk.StringVar(value="Message    : 0 B")
        self._msg_enc_var = ctk.StringVar(value="Encrypted  : 0 B")
        ctk.CTkLabel(self, textvariable=self._msg_raw_var, justify="left",
                     font=FONT_MONO_S, text_color=("gray40", "gray65")).pack(anchor="w", padx=14)
        ctk.CTkLabel(self, textvariable=self._msg_enc_var, justify="left",
                     font=FONT_MONO_S, text_color=("gray55", "gray50")).pack(anchor="w", padx=14)

        ctk.CTkFrame(self, height=1, fg_color=BORDER).pack(fill="x", padx=14, pady=(10, 8))

        bar_hdr = ctk.CTkFrame(self, fg_color="transparent")
        bar_hdr.pack(fill="x", padx=14)
        ctk.CTkLabel(bar_hdr, text="CAPACITY", font=("Segoe UI", 9, "bold"),
                     text_color=("gray55", "gray50")).pack(side="left")
        self._pct_label = ctk.CTkLabel(bar_hdr, text="0%", font=("Segoe UI", 9, "bold"),
                                        text_color=(ACCENT_DIM, ACCENT))
        self._pct_label.pack(side="right")

        self._bar_bg = ctk.CTkFrame(self, height=6, fg_color=("gray78", "#2E3340"), corner_radius=3)
        self._bar_bg.pack(fill="x", padx=14, pady=(4, 14))
        self._bar_bg.pack_propagate(False)

        self._bar_fill = ctk.CTkFrame(self._bar_bg, height=6, fg_color=GREEN, corner_radius=3, width=0)
        self._bar_fill.place(x=0, y=0, relheight=1.0)

    def set_image(self, path: str, capacity: int):
        img = Image.open(path)
        img.thumbnail(self.THUMB_SIZE)
        self._photo = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
        self._img_label.configure(image=self._photo, text="")
        if self._show_info:
            self._capacity = capacity
            self._info_var.set(f"Resolution : {img.width} × {img.height}\nCapacity   : {_fmt_bytes(capacity)}")
            self._msg_raw_var.set("Message    : 0 B")
            self._msg_enc_var.set("Encrypted  : 0 B")
            self._update_bar(0, capacity)

    def update_data_size(self, raw_bytes: int, enc_bytes: int, capacity: int):
        if not self._show_info:
            return
        self._msg_raw_var.set(f"Message    : {_fmt_bytes(raw_bytes)}")
        self._msg_enc_var.set(f"Encrypted  : {_fmt_bytes(enc_bytes)}")
        self._update_bar(enc_bytes, capacity)

    def clear(self):
        self._photo = None
        self._img_label.configure(
            image=ctk.CTkImage(light_image=Image.new("RGB", (1, 1)),
                               dark_image=Image.new("RGB", (1, 1)), size=(1, 1)),
            text="No image selected")
        if self._show_info:
            self._capacity = 0
            self._info_var.set("")
            self._msg_raw_var.set("Message    : 0 B")
            self._msg_enc_var.set("Encrypted  : 0 B")
            self._update_bar(0, 1)

    def _update_bar(self, used: int, total: int):
        if not self._show_info:
            return
        pct    = min(used / total, 1.0) if total > 0 else 0.0
        colour = GREEN if pct < 0.75 else ORANGE if pct < 1.0 else RED
        self._bar_fill.configure(fg_color=colour)
        self._bar_bg.update_idletasks()
        bar_w = self._bar_bg.winfo_width()
        self._bar_fill.place_configure(width=max(0, int(bar_w * pct)))
        self._pct_label.configure(text=f"{pct * 100:.1f}%")


# ── Before / After Preview Popup ─────────────────────────────────────────────

class BeforeAfterPreview(ctk.CTkToplevel):
    """Side-by-side original vs stego image comparison window."""
    THUMB = (340, 280)

    def __init__(self, master, before_path: str, after_path: str):
        super().__init__(master)
        self.title("Before / After — Image Comparison")
        self.geometry("780x400")
        self.resizable(False, False)
        self.configure(fg_color=("#F0F2F5", "#1A1D23"))
        self._photos = []   # keep references
        self._build(before_path, after_path)

    def _build(self, bp: str, ap: str):
        import os
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=20, pady=16)

        for path, label in [(bp, "Original"), (ap, "Stego  (after embed)")]:
            col = ctk.CTkFrame(main, fg_color="transparent")
            col.pack(side="left", fill="both", expand=True, padx=8)

            hdr = ctk.CTkFrame(col, fg_color="transparent")
            hdr.pack(fill="x", pady=(0, 6))
            ctk.CTkLabel(hdr, text=label.upper(), font=("Segoe UI", 10, "bold"),
                         text_color=(ACCENT_DIM, ACCENT)).pack(side="left")

            card = Card(col)
            card.pack(fill="both", expand=True)

            img = Image.open(path)
            img.thumbnail(self.THUMB)
            photo = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
            self._photos.append(photo)
            ctk.CTkLabel(card, image=photo, text="").pack(pady=12, padx=12)

            size = os.path.getsize(path)
            ctk.CTkLabel(card, text=f"{_fmt_bytes(size)}  ·  {img.width}×{img.height}",
                         font=FONT_MONO_S, text_color=("gray45", "gray55")).pack(pady=(0, 10))


# ── Session History ───────────────────────────────────────────────────────────

_HISTORY: list[dict] = []


def add_history(op_type: str, detail: str, ok: bool = True):
    _HISTORY.insert(0, {
        "type":   op_type,
        "detail": detail,
        "ok":     ok,
        "time":   datetime.datetime.now().strftime("%H:%M:%S"),
    })
    if len(_HISTORY) > 50:
        _HISTORY.pop()


class HistoryPanel(Card):
    """Scrollable session history card."""
    MAX_SHOW = 30

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._rows: list = []
        self._build_ui()

    def _build_ui(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(hdr, text="SESSION HISTORY", font=("Segoe UI", 9, "bold"),
                     text_color=("gray50", "gray50")).pack(side="left")
        ctk.CTkButton(hdr, text="Clear", width=46, height=20, font=("Segoe UI", 9),
                      fg_color=("gray78", "#2A2F3A"), hover_color=("gray70", "#343B48"),
                      text_color=("gray20", "gray70"), command=self._clear).pack(side="right")

        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent", height=160)
        self._scroll.pack(fill="both", expand=True, padx=4, pady=(0, 8))
        self.refresh()

    def refresh(self):
        for w in self._rows:
            w.destroy()
        self._rows.clear()

        if not _HISTORY:
            lbl = ctk.CTkLabel(self._scroll, text="No operations yet",
                               font=FONT_SMALL, text_color=("gray55", "gray50"))
            lbl.pack(anchor="w", padx=8, pady=4)
            self._rows.append(lbl)
            return

        for entry in _HISTORY[:self.MAX_SHOW]:
            row = ctk.CTkFrame(self._scroll, fg_color=("gray88", "#22262F"), corner_radius=6)
            row.pack(fill="x", pady=2, padx=4)

            dot_col = (ACCENT_DIM, ACCENT) if entry["ok"] else ("#C62828", RED)
            ctk.CTkLabel(row, text="●", font=("Segoe UI", 9),
                         text_color=dot_col, width=14).pack(side="left", padx=(6, 0), pady=5)

            ctk.CTkLabel(row, text=entry["type"].upper(), font=("Segoe UI", 8, "bold"),
                         text_color=dot_col, fg_color=("gray78", "#2E3340"),
                         corner_radius=4, width=52, height=18).pack(side="left", padx=5, pady=5)

            ctk.CTkLabel(row, text=entry["detail"], font=FONT_SMALL, anchor="w",
                         text_color=("gray25", "gray75")).pack(side="left", fill="x", expand=True, pady=5)

            ctk.CTkLabel(row, text=entry["time"], font=("Segoe UI", 9),
                         text_color=("gray55", "gray50")).pack(side="right", padx=8, pady=5)

            self._rows.append(row)

    def _clear(self):
        _HISTORY.clear()
        self.refresh()


# ── Animated Waveform (Audio tab) ─────────────────────────────────────────────

class WaveformCanvas(ctk.CTkCanvas):
    """
    Animated waveform: pulses while recording, shows static shape after stop.
    """
    BAR_COUNT = 26
    BAR_W     = 4
    GAP       = 3
    HEIGHT    = 56

    def __init__(self, master, **kwargs):
        w = self.BAR_COUNT * (self.BAR_W + self.GAP) + self.GAP
        kwargs.setdefault("width", w)
        kwargs.setdefault("height", self.HEIGHT)
        kwargs.setdefault("bg", "#22262F")
        kwargs.setdefault("highlightthickness", 0)
        super().__init__(master, **kwargs)
        self._recording = False
        self._phase     = 0.0
        self._draw_idle()

    def start_recording(self):
        self._recording = True
        self._animate()

    def stop_recording(self, wav_bytes: bytes | None = None):
        self._recording = False
        if wav_bytes:
            self._draw_static(wav_bytes)
        else:
            self._draw_idle()

    def clear(self):
        self._recording = False
        self._draw_idle()

    def _draw_idle(self):
        self.delete("all")
        mid = self.HEIGHT // 2
        for i in range(self.BAR_COUNT):
            x = self.GAP + i * (self.BAR_W + self.GAP)
            self.create_rectangle(x, mid - 2, x + self.BAR_W, mid + 2, fill="#2E3340", outline="")

    def _animate(self):
        if not self._recording:
            return
        self._phase += 0.18
        self.delete("all")
        mid = self.HEIGHT // 2
        for i in range(self.BAR_COUNT):
            wave  = math.sin(self._phase + i * 0.55) * 0.5 + 0.5
            noise = math.sin(self._phase * 1.7 + i * 1.1) * 0.25
            amp   = max(0.08, min(0.9, wave + noise))
            h     = int(amp * (self.HEIGHT - 8))
            x     = self.GAP + i * (self.BAR_W + self.GAP)
            g     = min(255, int(60 + 165 * amp))
            b     = min(255, int(50 + 117 * amp))
            col   = f"#00{g:02x}{b:02x}"
            self.create_rectangle(x, mid - h // 2, x + self.BAR_W, mid + h // 2, fill=col, outline="")
        self.after(40, self._animate)

    def _draw_static(self, wav_bytes: bytes):
        try:
            buf     = io.BytesIO(wav_bytes)
            with _wave.open(buf, "rb") as wf:
                raw     = wf.readframes(wf.getnframes())
            samples = struct.unpack(f"<{len(raw)//2}h", raw)
            step    = max(1, len(samples) // self.BAR_COUNT)
            amps    = [max(abs(s) for s in samples[i:i+step]) / 32768.0
                       for i in range(0, len(samples), step)][:self.BAR_COUNT]
            self.delete("all")
            mid = self.HEIGHT // 2
            for i, amp in enumerate(amps):
                h   = max(4, int(amp * (self.HEIGHT - 8)))
                x   = self.GAP + i * (self.BAR_W + self.GAP)
                self.create_rectangle(x, mid - h // 2, x + self.BAR_W, mid + h // 2,
                                      fill=ACCENT, outline="")
        except Exception:
            self._draw_idle()


# ── Status Bar ────────────────────────────────────────────────────────────────

class StatusBar(ctk.CTkFrame):
    _COLOURS = {
        "ready": ("gray55", "gray50"), "info": ("#1565C0", "#5C9EE8"),
        "ok":    (ACCENT_DIM, ACCENT), "warn": ("#C67600", "#FFB300"),
        "error": ("#C62828", "#EF5350"),
    }
    _DOTS = {"ready": "○", "info": "◉", "ok": "●", "warn": "◈", "error": "◆"}

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._dot_lbl = ctk.CTkLabel(self, text="○", font=("Segoe UI", 11),
                                      text_color=("gray55", "gray50"), width=16)
        self._dot_lbl.pack(side="left")
        self._msg_lbl = ctk.CTkLabel(self, text="Ready", anchor="w",
                                      font=("Segoe UI", 11), text_color=("gray55", "gray50"))
        self._msg_lbl.pack(side="left", padx=(2, 0))

    def set(self, message: str, level: str = "info"):
        colours = self._COLOURS.get(level, self._COLOURS["info"])
        dot     = self._DOTS.get(level, "●")
        self._dot_lbl.configure(text=dot, text_color=colours)
        self._msg_lbl.configure(text=message, text_color=colours)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt_bytes(n: int) -> str:
    if n < 1024:      return f"{n} B"
    if n < 1024**2:   return f"{n / 1024:.1f} KB"
    return f"{n / 1024**2:.2f} MB"
