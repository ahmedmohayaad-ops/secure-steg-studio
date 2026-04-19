# steg_studio/gui/components.py
"""Neon Studio custom widgets."""
from __future__ import annotations

import datetime
import io
import math
import struct
import threading
import wave as _wave
from typing import Callable

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageTk

from . import theme
from .assets import icon

try:
    import pyaudio
    _PYAUDIO_OK = True
except Exception:  # noqa: BLE001
    pyaudio = None
    _PYAUDIO_OK = False


# ═══════════════════════════════════════════════════════════════════════════
# NeonPanel — glowing card
# ═══════════════════════════════════════════════════════════════════════════

class NeonPanel(ctk.CTkFrame):
    def __init__(self, master, accent: str = theme.CYAN, **kwargs):
        kwargs.setdefault("fg_color", theme.BG_2)
        kwargs.setdefault("corner_radius", 14)
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("border_color", theme.STROKE)
        super().__init__(master, **kwargs)
        self._accent = accent


# ═══════════════════════════════════════════════════════════════════════════
# NeonButton — primary/ghost/danger with halo hover
# ═══════════════════════════════════════════════════════════════════════════

class NeonButton(ctk.CTkButton):
    def __init__(self, master, text: str, command=None, *,
                 variant: str = "primary", accent: str = theme.CYAN,
                 icon_name: str | None = None, width: int = 120,
                 height: int = 34, **kwargs):
        self._accent = accent
        self._variant = variant

        if variant == "primary":
            fg = accent
            hover = theme.CYAN_DIM if accent == theme.CYAN else theme.MAGENTA_DIM
            txt = theme.BG_0
        elif variant == "danger":
            fg = theme.ERR
            hover = "#B73455"
            txt = theme.TEXT_HI
        else:  # ghost
            fg = theme.BG_3
            hover = theme.STROKE_HI
            txt = theme.TEXT_HI

        img = None
        if icon_name:
            ic_color = txt if variant == "primary" else accent
            img = icon(icon_name, size=14, color=ic_color)

        kw = {}
        if img is not None:
            kw["image"] = img
            kw["compound"] = "left"

        super().__init__(
            master, text=text, command=command,
            width=width, height=height,
            font=theme.F_BTN,
            fg_color=fg, hover_color=hover, text_color=txt,
            corner_radius=10, border_width=0,
            **kw, **kwargs,
        )


# ═══════════════════════════════════════════════════════════════════════════
# ModeToggle — sliding segmented control (cyan ⇄ magenta)
# ═══════════════════════════════════════════════════════════════════════════

class ModeToggle(ctk.CTkFrame):
    def __init__(self, master, on_change: Callable[[str], None]):
        super().__init__(master, fg_color=theme.BG_1, corner_radius=10,
                         border_width=1, border_color=theme.STROKE,
                         height=38, width=260)
        self.pack_propagate(False)
        self._on_change = on_change
        self._mode = "encrypt"

        self._enc_btn = ctk.CTkButton(
            self, text="◉  ENCRYPT", width=124, height=30,
            font=theme.F_BTN, corner_radius=8,
            fg_color=theme.CYAN, hover_color=theme.CYAN_DIM,
            text_color=theme.BG_0,
            command=lambda: self.set_mode("encrypt"),
        )
        self._dec_btn = ctk.CTkButton(
            self, text="◌  DECRYPT", width=124, height=30,
            font=theme.F_BTN, corner_radius=8,
            fg_color="transparent", hover_color=theme.BG_3,
            text_color=theme.TEXT_MID,
            command=lambda: self.set_mode("decrypt"),
        )
        self._enc_btn.place(x=4, y=4)
        self._dec_btn.place(x=132, y=4)

    def set_mode(self, mode: str):
        if mode == self._mode:
            return
        self._mode = mode
        if mode == "encrypt":
            self._enc_btn.configure(fg_color=theme.CYAN, hover_color=theme.CYAN_DIM,
                                     text_color=theme.BG_0)
            self._dec_btn.configure(fg_color="transparent", hover_color=theme.BG_3,
                                     text_color=theme.TEXT_MID)
        else:
            self._dec_btn.configure(fg_color=theme.MAGENTA, hover_color=theme.MAGENTA_DIM,
                                     text_color=theme.BG_0)
            self._enc_btn.configure(fg_color="transparent", hover_color=theme.BG_3,
                                     text_color=theme.TEXT_MID)
        self._on_change(mode)

    @property
    def mode(self) -> str:
        return self._mode


# ═══════════════════════════════════════════════════════════════════════════
# DropZone — click-to-browse image area with preview
# ═══════════════════════════════════════════════════════════════════════════

class DropZone(ctk.CTkFrame):
    THUMB_MAX = (520, 200)

    def __init__(self, master, on_select: Callable[[str], None],
                 accent: str = theme.CYAN, hint: str = "DROP OR CLICK TO LOAD COVER",
                 height: int = 220):
        super().__init__(master, fg_color=theme.BG_1, corner_radius=14,
                         border_width=2, border_color=theme.STROKE,
                         height=height)
        self.pack_propagate(False)
        self.grid_propagate(False)
        self._on_select = on_select
        self._accent = accent
        self._hint = hint
        self._photo = None
        self._path: str | None = None

        self._inner = ctk.CTkFrame(self, fg_color="transparent")
        self._inner.pack(fill="both", expand=True, padx=6, pady=6)

        self._label = ctk.CTkLabel(
            self._inner, text=f"[ {hint} ]",
            font=theme.F_HEAD, text_color=theme.TEXT_LO,
            fg_color="transparent",
        )
        self._label.pack(expand=True, fill="both")

        self._bind_click(self)
        self._bind_click(self._inner)
        self._bind_click(self._label)
        self._hover_bind(self)
        self._hover_bind(self._inner)
        self._hover_bind(self._label)

    def _bind_click(self, w):
        w.bind("<Button-1>", lambda _e: self._browse())

    def _hover_bind(self, w):
        w.bind("<Enter>", lambda _e: self.configure(border_color=self._accent))
        w.bind("<Leave>", lambda _e: self.configure(border_color=theme.STROKE))

    def set_accent(self, accent: str, hint: str | None = None):
        self._accent = accent
        if hint is not None:
            self._hint = hint
            if self._path is None:
                self._label.configure(text=f"[ {hint} ]")

    def _browse(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Select image",
            filetypes=[("PNG images", "*.png"),
                       ("Images", "*.png *.bmp *.tif *.tiff"),
                       ("All files", "*.*")],
        )
        if path:
            self.load_path(path)

    def load_path(self, path: str, silent: bool = False):
        try:
            img = Image.open(path).convert("RGB")
        except Exception:
            self._label.configure(text="[ INVALID IMAGE ]", text_color=theme.ERR)
            return
        self._path = path
        img.thumbnail(self.THUMB_MAX)
        self._photo = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
        self._label.configure(image=self._photo, text="")
        if not silent:
            self._on_select(path)

    def clear(self):
        self._path = None
        self._photo = None
        self._label.configure(
            image=ctk.CTkImage(light_image=Image.new("RGB", (1, 1)),
                               dark_image=Image.new("RGB", (1, 1)), size=(1, 1)),
            text=f"[ {self._hint} ]", text_color=theme.TEXT_LO,
        )

    @property
    def path(self) -> str | None:
        return self._path


# ═══════════════════════════════════════════════════════════════════════════
# CapacityRing — circular progress (Pillow)
# ═══════════════════════════════════════════════════════════════════════════

class CapacityRing(ctk.CTkLabel):
    SIZE = 140

    def __init__(self, master, accent: str = theme.CYAN):
        super().__init__(master, text="", width=self.SIZE, height=self.SIZE,
                         fg_color="transparent")
        self._accent = accent
        self._frac = 0.0
        self._pct_text = "0%"
        self._sub_text = "no image"
        self._render()

    def set_accent(self, accent: str):
        self._accent = accent
        self._render()

    def set(self, used: int, total: int):
        if total <= 0:
            self._frac = 0.0
            self._pct_text = "—"
            self._sub_text = "no image"
        else:
            self._frac = min(used / total, 1.0)
            self._pct_text = f"{self._frac * 100:.0f}%"
            self._sub_text = f"{theme.fmt_bytes(used)} / {theme.fmt_bytes(total)}"
        self._render()

    def _color(self) -> str:
        if self._frac >= 1.0:
            return theme.ERR
        if self._frac >= 0.85:
            return theme.WARN
        return self._accent

    def _render(self):
        scale = 3
        s = self.SIZE * scale
        img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        pad = 10 * scale
        box = [pad, pad, s - pad, s - pad]

        d.ellipse(box, outline=theme.STROKE, width=6 * scale)

        if self._frac > 0:
            start = -90
            end = start + 360 * self._frac
            d.arc(box, start=start, end=end, fill=self._color(), width=6 * scale)

        img = img.resize((self.SIZE, self.SIZE), Image.LANCZOS)
        self._ctk_img = ctk.CTkImage(light_image=img, dark_image=img,
                                      size=(self.SIZE, self.SIZE))
        self.configure(image=self._ctk_img, text="")


class CapacityBlock(ctk.CTkFrame):
    """CapacityRing plus numeric readouts."""
    def __init__(self, master, accent: str = theme.CYAN):
        super().__init__(master, fg_color="transparent")
        self.ring = CapacityRing(self, accent=accent)
        self.ring.pack(pady=(4, 6))

        self.pct_lbl = ctk.CTkLabel(self, text="0%",
                                     font=("JetBrains Mono", 18, "bold"),
                                     text_color=theme.TEXT_HI)
        self.pct_lbl.place(relx=0.5, rely=0.36, anchor="center")

        self.sub_lbl = ctk.CTkLabel(self, text="no image",
                                     font=theme.F_TINY, text_color=theme.TEXT_LO)
        self.sub_lbl.place(relx=0.5, rely=0.52, anchor="center")

    def set(self, used: int, total: int):
        self.ring.set(used, total)
        if total <= 0:
            self.pct_lbl.configure(text="—")
            self.sub_lbl.configure(text="no image")
        else:
            frac = min(used / total, 1.0)
            self.pct_lbl.configure(text=f"{frac * 100:.0f}%",
                                    text_color=theme.ERR if frac >= 1.0 else theme.TEXT_HI)
            self.sub_lbl.configure(text=f"{theme.fmt_bytes(used)} / {theme.fmt_bytes(total)}")

    def set_accent(self, accent: str):
        self.ring.set_accent(accent)


# ═══════════════════════════════════════════════════════════════════════════
# HexSpinner — rotating hex ring
# ═══════════════════════════════════════════════════════════════════════════

class HexSpinner(ctk.CTkLabel):
    _FRAMES = ["⬢", "⬡"]
    _GLYPHS = ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"]

    def __init__(self, master, accent: str = theme.CYAN):
        super().__init__(master, text="", font=("Segoe UI", 14, "bold"),
                         text_color=accent, width=20)
        self._accent = accent
        self._running = False
        self._i = 0

    def set_accent(self, accent: str):
        self._accent = accent
        self.configure(text_color=accent)

    def start(self):
        self._running = True
        self._tick()

    def stop(self):
        self._running = False
        self.configure(text="")

    def _tick(self):
        if not self._running:
            return
        self.configure(text=self._GLYPHS[self._i % len(self._GLYPHS)])
        self._i += 1
        self.after(80, self._tick)


# ═══════════════════════════════════════════════════════════════════════════
# ProgressTrack — slim progress bar with neon fill
# ═══════════════════════════════════════════════════════════════════════════

class ProgressTrack(ctk.CTkFrame):
    HEIGHT = 6

    def __init__(self, master, accent: str = theme.CYAN, **kwargs):
        super().__init__(master, height=self.HEIGHT, fg_color=theme.STROKE,
                         corner_radius=3, **kwargs)
        self.pack_propagate(False)
        self._accent = accent
        self._fill = ctk.CTkFrame(self, height=self.HEIGHT, fg_color=accent,
                                   corner_radius=3, width=0)
        self._fill.place(x=0, y=0, relheight=1.0, relwidth=0)

    def set_accent(self, accent: str):
        self._accent = accent
        self._fill.configure(fg_color=accent)

    def set(self, frac: float):
        frac = max(0.0, min(1.0, frac))
        self._fill.place_configure(relwidth=frac)

    def reset(self):
        self._fill.place_configure(relwidth=0)


# ═══════════════════════════════════════════════════════════════════════════
# WaveformCanvas — animated + static
# ═══════════════════════════════════════════════════════════════════════════

class WaveformCanvas(ctk.CTkCanvas):
    BAR_COUNT = 32
    BAR_W = 4
    GAP = 3
    HEIGHT = 60

    def __init__(self, master, accent: str = theme.CYAN, **kwargs):
        w = self.BAR_COUNT * (self.BAR_W + self.GAP) + self.GAP
        kwargs.setdefault("width", w)
        kwargs.setdefault("height", self.HEIGHT)
        kwargs.setdefault("bg", theme.BG_2)
        kwargs.setdefault("highlightthickness", 0)
        super().__init__(master, **kwargs)
        self._accent = accent
        self._recording = False
        self._phase = 0.0
        self._draw_idle()

    def set_accent(self, accent: str):
        self._accent = accent
        if not self._recording:
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
            self.create_rectangle(x, mid - 2, x + self.BAR_W, mid + 2,
                                   fill=theme.STROKE, outline="")

    def _animate(self):
        if not self._recording:
            return
        self._phase += 0.22
        self.delete("all")
        mid = self.HEIGHT // 2
        for i in range(self.BAR_COUNT):
            wave = math.sin(self._phase + i * 0.55) * 0.5 + 0.5
            noise = math.sin(self._phase * 1.7 + i * 1.1) * 0.25
            amp = max(0.08, min(0.95, wave + noise))
            h = int(amp * (self.HEIGHT - 8))
            x = self.GAP + i * (self.BAR_W + self.GAP)
            self.create_rectangle(x, mid - h // 2, x + self.BAR_W, mid + h // 2,
                                   fill=self._accent, outline="")
        self.after(40, self._animate)

    def _draw_static(self, wav_bytes: bytes):
        try:
            buf = io.BytesIO(wav_bytes)
            with _wave.open(buf, "rb") as wf:
                raw = wf.readframes(wf.getnframes())
            samples = struct.unpack(f"<{len(raw)//2}h", raw)
            step = max(1, len(samples) // self.BAR_COUNT)
            amps = [max(abs(s) for s in samples[i:i + step]) / 32768.0
                    for i in range(0, len(samples), step)][:self.BAR_COUNT]
            self.delete("all")
            mid = self.HEIGHT // 2
            for i, amp in enumerate(amps):
                h = max(4, int(amp * (self.HEIGHT - 8)))
                x = self.GAP + i * (self.BAR_W + self.GAP)
                self.create_rectangle(x, mid - h // 2, x + self.BAR_W, mid + h // 2,
                                       fill=self._accent, outline="")
        except Exception:
            self._draw_idle()


# ═══════════════════════════════════════════════════════════════════════════
# AudioRecorder — pyaudio wrapper
# ═══════════════════════════════════════════════════════════════════════════

class AudioRecorder:
    RATE = 44100
    CHANNELS = 1
    CHUNK = 1024
    FORMAT = pyaudio.paInt16 if _PYAUDIO_OK else 8

    available = _PYAUDIO_OK

    def __init__(self):
        self._frames: list[bytes] = []
        self._recording = False
        self._pa = self._stream = self._thread = None
        self._t0 = 0.0
        self.duration = 0.0

    def start(self):
        if not _PYAUDIO_OK:
            return
        import time
        self._frames = []
        self._recording = True
        self.duration = 0.0
        self._t0 = time.time()
        self._pa = pyaudio.PyAudio()
        self._stream = self._pa.open(
            format=self.FORMAT, channels=self.CHANNELS,
            rate=self.RATE, input=True, frames_per_buffer=self.CHUNK,
        )
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._recording = False
        if self._thread:
            self._thread.join(timeout=2)
        if self._stream:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception:
                pass
        if self._pa:
            try:
                self._pa.terminate()
            except Exception:
                pass

    def get_wav_bytes(self) -> bytes:
        if not self._frames or not _PYAUDIO_OK:
            return b""
        buf = io.BytesIO()
        with _wave.open(buf, "wb") as wf:
            wf.setnchannels(self.CHANNELS)
            wf.setsampwidth(pyaudio.PyAudio().get_sample_size(self.FORMAT))
            wf.setframerate(self.RATE)
            wf.writeframes(b"".join(self._frames))
        return buf.getvalue()

    def _loop(self):
        import time
        while self._recording:
            try:
                self._frames.append(self._stream.read(self.CHUNK, exception_on_overflow=False))
            except Exception:
                break
            self.duration = time.time() - self._t0


# ═══════════════════════════════════════════════════════════════════════════
# HistoryPanel — session op log
# ═══════════════════════════════════════════════════════════════════════════

_HISTORY: list[dict] = []


def add_history(op: str, detail: str, ok: bool = True, thumb_path: str | None = None):
    _HISTORY.insert(0, {
        "op": op, "detail": detail, "ok": ok, "thumb": thumb_path,
        "time": datetime.datetime.now().strftime("%H:%M:%S"),
    })
    del _HISTORY[50:]


class HistoryPanel(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=theme.BG_2, corner_radius=14,
                         border_width=1, border_color=theme.STROKE)
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=14, pady=(10, 4))
        ctk.CTkLabel(hdr, text="◈ SESSION LOG", font=theme.F_HEAD,
                     text_color=theme.TEXT_HI).pack(side="left")
        ctk.CTkButton(hdr, text="clear", width=46, height=22, font=theme.F_TINY,
                       fg_color=theme.BG_3, hover_color=theme.STROKE_HI,
                       text_color=theme.TEXT_MID, corner_radius=6,
                       command=self._clear).pack(side="right")

        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent", height=180)
        self._scroll.pack(fill="both", expand=True, padx=6, pady=(0, 10))
        self._rows: list = []
        self.refresh()

    def refresh(self):
        for w in self._rows:
            w.destroy()
        self._rows.clear()
        if not _HISTORY:
            lbl = ctk.CTkLabel(self._scroll, text="— no operations yet —",
                                font=theme.F_SMALL, text_color=theme.TEXT_DIM)
            lbl.pack(anchor="w", padx=8, pady=6)
            self._rows.append(lbl)
            return
        for entry in _HISTORY[:30]:
            row = ctk.CTkFrame(self._scroll, fg_color=theme.BG_1, corner_radius=8)
            row.pack(fill="x", pady=2, padx=4)
            col = theme.OK if entry["ok"] else theme.ERR
            ctk.CTkLabel(row, text="●", text_color=col, width=14,
                          font=("Segoe UI", 10)).pack(side="left", padx=(6, 2), pady=6)
            ctk.CTkLabel(row, text=entry["op"].upper(), font=("JetBrains Mono", 9, "bold"),
                          text_color=col, width=60).pack(side="left", padx=4)
            ctk.CTkLabel(row, text=entry["detail"], font=theme.F_SMALL, anchor="w",
                          text_color=theme.TEXT_MID).pack(side="left", fill="x",
                                                            expand=True, padx=4)
            ctk.CTkLabel(row, text=entry["time"], font=theme.F_TINY,
                          text_color=theme.TEXT_DIM).pack(side="right", padx=8)
            self._rows.append(row)

    def _clear(self):
        _HISTORY.clear()
        self.refresh()


# ═══════════════════════════════════════════════════════════════════════════
# BeforeAfter viewer — click a chip to toggle original/stego
# ═══════════════════════════════════════════════════════════════════════════

class BeforeAfterToggle(ctk.CTkFrame):
    """Tiny chip bar to flip the DropZone's preview between before/after images."""
    def __init__(self, master, drop_zone: DropZone, accent: str = theme.CYAN):
        super().__init__(master, fg_color="transparent")
        self._dz = drop_zone
        self._accent = accent
        self._before: str | None = None
        self._after: str | None = None
        self._showing = "before"

        self._btn_b = ctk.CTkButton(self, text="◀ ORIGINAL", width=110, height=26,
                                     font=theme.F_TINY, corner_radius=6,
                                     fg_color=accent, hover_color=theme.CYAN_DIM,
                                     text_color=theme.BG_0,
                                     command=lambda: self._show("before"))
        self._btn_a = ctk.CTkButton(self, text="STEGO ▶", width=110, height=26,
                                     font=theme.F_TINY, corner_radius=6,
                                     fg_color=theme.BG_3, hover_color=theme.STROKE_HI,
                                     text_color=theme.TEXT_MID,
                                     command=lambda: self._show("after"))

    def set_pair(self, before: str, after: str):
        self._before = before
        self._after = after
        self._btn_b.pack(side="left", padx=(0, 4))
        self._btn_a.pack(side="left")
        self._show("after")

    def clear(self):
        self._before = self._after = None
        self._btn_b.pack_forget()
        self._btn_a.pack_forget()

    def set_accent(self, accent: str):
        self._accent = accent
        self._show(self._showing)

    def _show(self, which: str):
        self._showing = which
        if which == "before" and self._before:
            self._dz.load_path(self._before, silent=True)
            self._btn_b.configure(fg_color=self._accent, text_color=theme.BG_0)
            self._btn_a.configure(fg_color=theme.BG_3, text_color=theme.TEXT_MID)
        elif which == "after" and self._after:
            self._dz.load_path(self._after, silent=True)
            self._btn_a.configure(fg_color=self._accent, text_color=theme.BG_0)
            self._btn_b.configure(fg_color=theme.BG_3, text_color=theme.TEXT_MID)


# ═══════════════════════════════════════════════════════════════════════════
# v2.1 Forensic-workstation widgets — Midnight Teal + Amber
# ═══════════════════════════════════════════════════════════════════════════

import random as _random
import tkinter as _tk


class V2Card(ctk.CTkFrame):
    """Tuxedo card — graphite fill, hairline border, optional rim glow."""
    def __init__(self, master, rim: str | None = None, **kwargs):
        kwargs.setdefault("fg_color", theme.BG_2)
        kwargs.setdefault("corner_radius", 8)
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("border_color", rim or theme.STROKE)
        super().__init__(master, **kwargs)


class V2Button(ctk.CTkButton):
    """Sized v2 button. variant: primary | secondary | ghost | danger."""
    def __init__(self, master, text: str = "", *, variant: str = "secondary",
                 icon_name: str | None = None, size: str = "md",
                 width: int = 0, command=None, **kwargs):
        h = {"sm": 26, "md": 34, "lg": 44}[size]
        fz = {"sm": 11, "md": 12, "lg": 14}[size]
        if variant == "primary":
            fg, hover, txt = theme.AMBER, theme.AMBER_HI, theme.AMBER_INK
        elif variant == "danger":
            fg, hover, txt = theme.ERR, "#F56B6B", "#FFFFFF"
        elif variant == "ghost":
            fg, hover, txt = "transparent", theme.BG_3, theme.TEXT_MID
        else:  # secondary
            fg, hover, txt = theme.BG_5, theme.BG_6, theme.TEXT_MID
        font = ("Segoe UI", fz, "bold" if variant == "primary" else "normal")
        kw = {}
        if icon_name:
            ic_color = txt if variant == "primary" else theme.AMBER
            img = icon(icon_name, size=14, color=ic_color)
            if img is not None:
                kw["image"] = img
                kw["compound"] = "left"
        super().__init__(master, text=text, command=command,
                         width=width or 0, height=h,
                         font=font, fg_color=fg, hover_color=hover,
                         text_color=txt, corner_radius=6,
                         border_width=1 if variant == "secondary" else 0,
                         border_color=theme.STROKE_HI,
                         **kw, **kwargs)


class V2Badge(ctk.CTkLabel):
    """Pill chip. tone: neutral | ok | warn | crit | accent | info."""
    _TONES = {
        "neutral": (theme.BG_5, theme.TEXT_MID, theme.STROKE_HI),
        "ok":      ("#0A2818", "#8FF0B0", "#1E5C38"),
        "warn":    ("#2C1F08", "#FFD66B", "#6A4818"),
        "crit":    ("#2C0A10", "#FF8A95", "#6A1828"),
        "accent":  ("#3C2A0E", theme.AMBER, "#6A4818"),
        "info":    ("#0A2630", "#8FE4F0", "#1E4C5A"),
    }

    def __init__(self, master, text: str = "", tone: str = "neutral", icon_name=None):
        bg, fg, _bd = self._TONES.get(tone, self._TONES["neutral"])
        kw = {}
        if icon_name:
            img = icon(icon_name, size=10, color=fg)
            if img is not None:
                kw["image"] = img
                kw["compound"] = "left"
        super().__init__(master, text="  " + text + "  " if text else "",
                         font=("Segoe UI", 9, "bold"),
                         fg_color=bg, text_color=fg,
                         corner_radius=4, height=22, **kw)
        self._tone = tone

    def set(self, text: str, tone: str | None = None):
        if tone and tone != self._tone:
            bg, fg, _bd = self._TONES.get(tone, self._TONES["neutral"])
            self.configure(fg_color=bg, text_color=fg)
            self._tone = tone
        self.configure(text="  " + text + "  ")


class V2Stat(ctk.CTkFrame):
    """Boxed statistic — label on top, big mono value below."""
    def __init__(self, master, label: str, value: str = "—", unit: str = "",
                 tone: str = "fg"):
        super().__init__(master, fg_color=theme.BG_3, corner_radius=6,
                         border_width=1, border_color=theme.STROKE)
        self._tones = {
            "fg": theme.TEXT_HI, "ok": theme.OK, "warn": theme.WARN,
            "crit": theme.ERR, "accent": theme.AMBER,
        }
        ctk.CTkLabel(self, text=label.upper(),
                     font=("Segoe UI", 9, "bold"),
                     text_color=theme.TEXT_DIM
                     ).pack(anchor="w", padx=10, pady=(8, 2))
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(anchor="w", padx=10, pady=(0, 8))
        self._val = ctk.CTkLabel(row, text=value,
                                  font=("JetBrains Mono", 18, "bold"),
                                  text_color=self._tones.get(tone, theme.TEXT_HI))
        self._val.pack(side="left")
        self._unit = ctk.CTkLabel(row, text=" " + unit if unit else "",
                                   font=("JetBrains Mono", 10),
                                   text_color=theme.TEXT_LO)
        self._unit.pack(side="left", padx=(2, 0))

    def set(self, value: str, unit: str | None = None, tone: str | None = None):
        self._val.configure(text=value)
        if unit is not None:
            self._unit.configure(text=" " + unit if unit else "")
        if tone:
            self._val.configure(text_color=self._tones.get(tone, theme.TEXT_HI))


class V2KV(ctk.CTkFrame):
    """key : value row — uppercase label, mono value, right-aligned."""
    def __init__(self, master, key: str, value: str = "—", accent: bool = False):
        super().__init__(master, fg_color="transparent", height=22)
        ctk.CTkLabel(self, text=key.upper(),
                     font=("Segoe UI", 9, "bold"),
                     text_color=theme.TEXT_DIM).pack(side="left")
        self._val = ctk.CTkLabel(self, text=value,
                                  font=("JetBrains Mono", 10),
                                  text_color=theme.AMBER if accent else theme.TEXT_HI)
        self._val.pack(side="right")

    def set(self, value: str):
        self._val.configure(text=value)


class V2Segmented(ctk.CTkFrame):
    """Inline pill switch with optional icons."""
    def __init__(self, master, options: list[str], on_change=None,
                 icons: list[str] | None = None):
        super().__init__(master, fg_color=theme.BG_5, corner_radius=6,
                         border_width=1, border_color=theme.STROKE_HI)
        self._on_change = on_change or (lambda _v: None)
        self._buttons: dict[str, ctk.CTkButton] = {}
        self._active = options[0]
        for i, opt in enumerate(options):
            kw = {}
            if icons and i < len(icons):
                img = icon(icons[i], size=12, color=theme.AMBER_INK
                           if opt == self._active else theme.TEXT_MID)
                if img is not None:
                    kw["image"] = img
                    kw["compound"] = "left"
            b = ctk.CTkButton(
                self, text=opt, width=0, height=26,
                font=("Segoe UI", 11, "bold"),
                corner_radius=4, border_width=0,
                fg_color=theme.AMBER if opt == self._active else "transparent",
                hover_color=theme.AMBER_HI if opt == self._active else theme.BG_6,
                text_color=theme.AMBER_INK if opt == self._active else theme.TEXT_MID,
                command=lambda v=opt: self.set(v), **kw,
            )
            b.pack(side="left", padx=2, pady=2)
            self._buttons[opt] = b
        self._icons = icons or []
        self._opts = options

    def set(self, value: str):
        if value not in self._buttons:
            return
        prev = self._active
        self._active = value
        for opt, b in self._buttons.items():
            active = opt == value
            b.configure(
                fg_color=theme.AMBER if active else "transparent",
                hover_color=theme.AMBER_HI if active else theme.BG_6,
                text_color=theme.AMBER_INK if active else theme.TEXT_MID,
            )
            i = self._opts.index(opt)
            if i < len(self._icons):
                img = icon(self._icons[i], size=12,
                           color=theme.AMBER_INK if active else theme.TEXT_MID)
                if img is not None:
                    b.configure(image=img, compound="left")
        if value != prev:
            self._on_change(value)

    @property
    def active(self) -> str:
        return self._active


class V2DropZone(ctk.CTkFrame):
    """Compact dashed drop card — slot for cover or payload."""
    def __init__(self, master, kind: str = "image", on_pick=None,
                 hint: str | None = None, height: int = 90):
        super().__init__(master, fg_color=theme.BG_3, corner_radius=6,
                         border_width=2, border_color=theme.STROKE_HI,
                         height=height)
        self.pack_propagate(False)
        self._kind = kind
        self._on_pick = on_pick or (lambda _p: None)
        self._path: str | None = None
        self._hint = hint or (
            "Drop cover image or browse"
            if kind == "image" else "Drop payload file or browse"
        )
        self._sub_hint = ("PNG · BMP · TIFF  ·  lossless only"
                          if kind == "image"
                          else "Any file type  ·  up to 10 MB")

        self._row = ctk.CTkFrame(self, fg_color="transparent")
        self._row.pack(expand=True, fill="both", padx=10, pady=8)

        self._tile = ctk.CTkLabel(
            self._row, text="",
            image=icon("image" if kind == "image" else "file", 18, theme.TEXT_LO),
            width=44, height=44, fg_color=theme.BG_5,
            corner_radius=6,
        )
        self._tile.pack(side="left", padx=(0, 10))

        info = ctk.CTkFrame(self._row, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True)
        self._title = ctk.CTkLabel(info, text=self._hint,
                                    font=("Segoe UI", 12, "bold"),
                                    text_color=theme.TEXT_HI, anchor="w")
        self._title.pack(anchor="w", fill="x")
        self._meta = ctk.CTkLabel(info, text=self._sub_hint,
                                   font=("JetBrains Mono", 9),
                                   text_color=theme.TEXT_DIM, anchor="w")
        self._meta.pack(anchor="w", fill="x")

        for w in (self, self._row, self._tile, self._title, self._meta, info):
            w.bind("<Button-1>", lambda _e: self._browse())
            w.bind("<Enter>", lambda _e: self.configure(border_color=theme.AMBER))
            w.bind("<Leave>", lambda _e: self.configure(border_color=theme.STROKE_HI))

    def _browse(self):
        from tkinter import filedialog
        if self._kind == "image":
            path = filedialog.askopenfilename(
                title="Select image",
                filetypes=[("PNG/BMP/TIFF", "*.png *.bmp *.tif *.tiff"),
                           ("All files", "*.*")])
        else:
            path = filedialog.askopenfilename(title="Select payload file")
        if path:
            self.set_file(path)
            self._on_pick(path)

    def set_file(self, path: str, meta: str | None = None):
        import os as _os
        self._path = path
        self._title.configure(text=_os.path.basename(path),
                               text_color=theme.TEXT_HI)
        if meta is None:
            try:
                size = _os.path.getsize(path)
                meta = f"{theme.fmt_bytes(size)}  ·  .{_os.path.splitext(path)[1].lstrip('.') or 'bin'}"
            except OSError:
                meta = "—"
        self._meta.configure(text=meta, text_color=theme.AMBER)
        self._tile.configure(image=icon(
            "image" if self._kind == "image" else "file", 18, theme.AMBER))

    def set_meta(self, text: str):
        self._meta.configure(text=text)

    def clear(self):
        self._path = None
        self._title.configure(text=self._hint, text_color=theme.TEXT_HI)
        self._meta.configure(text=self._sub_hint, text_color=theme.TEXT_DIM)
        self._tile.configure(image=icon(
            "image" if self._kind == "image" else "file", 18, theme.TEXT_LO))

    @property
    def path(self) -> str | None:
        return self._path


class LSBVisualizer(ctk.CTkFrame):
    """Three-channel real-data bit-grid + byte-anatomy widget.

    Shows one grid per R/G/B channel, each cell = the real LSB of a sampled
    pixel. During encoding, cells whose position has been reached by the
    progress sweep get an amber overlay if the bit would flip.

    A 1-bit / 2-bit toggle shades the "embed zone" in the byte anatomy strip
    so you can see how many bits a deeper LSB write would disturb
    (illustrative — core always writes exactly 1 bit).
    """
    COLS = 24
    ROWS = 3              # per channel
    CELL_H = 14
    CHANNELS = ("R", "G", "B")
    CHANNEL_COLOR = {"R": "#FF6B6B", "G": "#7DF9C0", "B": "#5BE3F0"}

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")

        # Header row with title + depth toggle
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(hdr, text="LSB EMBEDDING — LIVE RGB BIT TRACE",
                     font=("Segoe UI", 10, "bold"),
                     text_color=theme.AMBER).pack(side="left")
        self._depth = 1
        self._depth_toggle = V2Segmented(hdr, ["1-bit", "2-bit"],
                                          on_change=self._on_depth)
        self._depth_toggle.pack(side="right")

        grid_h = 3 * (self.ROWS * (self.CELL_H + 2) + 18) + 6
        self._canvas = _tk.Canvas(self, bg=theme.BG_2, highlightthickness=0,
                                   height=grid_h)
        self._canvas.pack(fill="x")
        self._canvas.bind("<Configure>", lambda _e: self._paint())

        n = self.ROWS * self.COLS
        # Default: deterministic starting state per channel
        self._cover_bits = {
            ch: [((i * seed) >> s) & 1 for i in range(n)]
            for ch, seed, s in (("R", 7919, 0), ("G", 5701, 1), ("B", 3391, 2))
        }
        self._payload_bits = {
            ch: [((i * 2654435761) >> (s + 3)) & 1 for i in range(n)]
            for ch, _, s in (("R", 0, 0), ("G", 0, 1), ("B", 0, 2))
        }
        # Second LSB (bit 1) per channel — used when depth == 2
        self._cover_bits2 = {ch: [(j * 1777 + k) & 1
                                    for k in range(len(bits))]
                              for (ch, bits), j in
                              zip(self._cover_bits.items(), range(3))}
        self._payload_bits2 = {ch: [((k * 9931) >> 2) & 1
                                      for k in range(n)]
                                for ch in self.CHANNELS}
        self._progress = 0.0
        self._running = False

        # Byte anatomy strip — real RGB pixel vs. modified pixel
        anat = ctk.CTkFrame(self, fg_color=theme.BG_3, corner_radius=4,
                             border_width=1, border_color=theme.STROKE)
        anat.pack(fill="x", pady=(10, 0))
        self._anat_rows: dict[str, dict] = {}
        self._sample_pixel = {"R": 0xB6, "G": 0x4C, "B": 0x92}
        self._payload_lsbs = {"R": 1, "G": 0, "B": 1}
        self._payload_lsbs2 = {"R": 0, "G": 1, "B": 0}
        for ch in self.CHANNELS:
            self._anat_rows[ch] = self._build_anat_row(anat, ch)

        self._byte_caption = ctk.CTkLabel(
            self, text="Amber = bit FLIPPED this write ·  Grey-lit = written but unchanged",
            font=("Segoe UI", 9),
            text_color=theme.TEXT_DIM,
        )
        self._byte_caption.pack(anchor="w", pady=(6, 0))

        self._update_byte_anatomy()
        self.after(60, self._paint)

    # ── anatomy row builder ────────────────────────────────────────────────
    def _build_anat_row(self, parent, ch: str) -> dict:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=(6, 6))
        chip = ctk.CTkLabel(row, text=ch, width=22, height=22,
                             corner_radius=3,
                             fg_color=self.CHANNEL_COLOR[ch],
                             text_color="#0A111A",
                             font=("JetBrains Mono", 11, "bold"))
        chip.pack(side="left")
        cover_val = ctk.CTkLabel(row, text="—", width=42,
                                   font=("JetBrains Mono", 10, "bold"),
                                   text_color=theme.TEXT_MID)
        cover_val.pack(side="left", padx=(8, 6))
        read_cells = []
        for i in range(8):
            c = ctk.CTkLabel(row, text="0", width=18, height=20,
                              corner_radius=2, fg_color=theme.BG_5,
                              text_color=theme.TEXT_MID,
                              font=("JetBrains Mono", 10, "bold"))
            c.pack(side="left", padx=1)
            read_cells.append(c)
        ctk.CTkLabel(row, text="→", font=("Segoe UI", 12, "bold"),
                     text_color=theme.AMBER
                     ).pack(side="left", padx=6)
        write_cells = []
        for i in range(8):
            c = ctk.CTkLabel(row, text="0", width=18, height=20,
                              corner_radius=2, fg_color=theme.BG_5,
                              text_color=theme.TEXT_MID,
                              font=("JetBrains Mono", 10, "bold"))
            c.pack(side="left", padx=1)
            write_cells.append(c)
        stego_val = ctk.CTkLabel(row, text="—", width=42,
                                   font=("JetBrains Mono", 10, "bold"),
                                   text_color=theme.AMBER)
        stego_val.pack(side="left", padx=(6, 6))
        badge = ctk.CTkLabel(row, text="·", width=48, height=20,
                              corner_radius=3,
                              fg_color=theme.BG_4,
                              text_color=theme.TEXT_DIM,
                              font=("Segoe UI", 9, "bold"))
        badge.pack(side="left", padx=(4, 0))
        return {"cover_val": cover_val, "read": read_cells,
                "write": write_cells, "stego_val": stego_val,
                "badge": badge}

    def _on_depth(self, value: str):
        self._depth = 2 if value == "2-bit" else 1
        self._update_byte_anatomy()
        self._paint()

    # ── public ─────────────────────────────────────────────────────────────
    def set_cover_sample(self, cover_image):
        """Feed a PIL.Image; R/G/B grids reflect actual per-channel LSBs."""
        try:
            img = cover_image.convert("RGB")
        except Exception:
            return
        w, h = img.size
        n = self.ROWS * self.COLS
        cover_bits = {c: [] for c in self.CHANNELS}
        cover_bits2 = {c: [] for c in self.CHANNELS}
        sample = None
        for i in range(n):
            row, col = divmod(i, self.COLS)
            x = (col * w) // self.COLS
            y = (row * h) // self.ROWS
            r, g, b = img.getpixel((x, y))[:3]
            cover_bits["R"].append(r & 1)
            cover_bits["G"].append(g & 1)
            cover_bits["B"].append(b & 1)
            cover_bits2["R"].append((r >> 1) & 1)
            cover_bits2["G"].append((g >> 1) & 1)
            cover_bits2["B"].append((b >> 1) & 1)
            if sample is None:
                sample = (r, g, b)
        self._cover_bits = cover_bits
        self._cover_bits2 = cover_bits2
        # Deterministic "would-be-written" payload bits per channel.
        self._payload_bits = {
            ch: [((b ^ ((i * 2654435761) >> (24 + s))) & 1)
                 for i, b in enumerate(cover_bits[ch])]
            for ch, s in zip(self.CHANNELS, (0, 1, 2))
        }
        self._payload_bits2 = {
            ch: [((b ^ ((i * 40503) >> 5)) & 1)
                 for i, b in enumerate(cover_bits2[ch])]
            for ch in self.CHANNELS
        }
        sr, sg, sb = sample if sample else (0xB6, 0x4C, 0x92)
        self._sample_pixel = {"R": int(sr), "G": int(sg), "B": int(sb)}
        self._payload_lsbs = {
            "R": self._payload_bits["R"][0],
            "G": self._payload_bits["G"][0],
            "B": self._payload_bits["B"][0],
        }
        self._payload_lsbs2 = {
            "R": self._payload_bits2["R"][0],
            "G": self._payload_bits2["G"][0],
            "B": self._payload_bits2["B"][0],
        }
        self._update_byte_anatomy()
        self._paint()

    def set_progress(self, p: float, running: bool):
        prev = self._progress
        self._progress = max(0.0, min(1.0, p))
        self._running = running
        step = 1.0 / (self.ROWS * self.COLS)
        if running and abs(self._progress - prev) < step and 0 < p < 1:
            return
        self._update_byte_anatomy()
        self._paint()

    # ── internal ───────────────────────────────────────────────────────────
    def _stego_byte(self, cover: int, lsb1: int, lsb2: int) -> int:
        out = (cover & 0xFE) | (lsb1 & 1)
        if self._depth == 2:
            out = (out & 0xFD) | ((lsb2 & 1) << 1)
        return out

    def _update_byte_anatomy(self):
        mask_lo = 0x03 if self._depth == 2 else 0x01
        for ch in self.CHANNELS:
            row = self._anat_rows[ch]
            cov = self._sample_pixel[ch]
            new = self._stego_byte(cov, self._payload_lsbs[ch],
                                    self._payload_lsbs2[ch])
            row["cover_val"].configure(text=f"{cov:>3}")
            row["stego_val"].configure(
                text=f"{new:>3}",
                text_color=theme.AMBER if new != cov else theme.TEXT_MID,
            )
            for i in range(8):
                bit = (cov >> (7 - i)) & 1
                row["read"][i].configure(
                    text=str(bit),
                    fg_color=(theme.BG_4 if i >= (8 - (2 if self._depth == 2 else 1))
                              else theme.BG_5),
                )
            for i in range(8):
                bit = (new >> (7 - i)) & 1
                cell = row["write"][i]
                in_zone = i >= (8 - (2 if self._depth == 2 else 1))
                orig_bit = (cov >> (7 - i)) & 1
                if in_zone:
                    if bit != orig_bit:
                        cell.configure(text=str(bit),
                                        fg_color=theme.AMBER,
                                        text_color=theme.AMBER_INK)
                    else:
                        cell.configure(text=str(bit),
                                        fg_color=theme.AMBER_LO,
                                        text_color=theme.AMBER_INK)
                else:
                    cell.configure(text=str(bit),
                                    fg_color=theme.BG_5,
                                    text_color=theme.TEXT_MID)
            if new != cov:
                row["badge"].configure(text="FLIP",
                                        fg_color=theme.AMBER,
                                        text_color=theme.AMBER_INK)
            else:
                row["badge"].configure(text="SAME",
                                        fg_color=theme.BG_4,
                                        text_color=theme.TEXT_DIM)

    def _paint(self):
        c = self._canvas
        c.delete("all")
        w = c.winfo_width() or 320
        cell_w = max(6, (w - 32 - (self.COLS - 1) * 2) // self.COLS)
        cell_h = self.CELL_H
        n = self.ROWS * self.COLS
        threshold = self._progress
        band_h = self.ROWS * (cell_h + 2) + 18
        for idx, ch in enumerate(self.CHANNELS):
            y0 = idx * band_h + 2
            # Channel label
            c.create_rectangle(0, y0, 22, y0 + 16,
                                fill=self.CHANNEL_COLOR[ch], outline="")
            c.create_text(11, y0 + 8, text=ch,
                           fill="#0A111A",
                           font=("JetBrains Mono", 9, "bold"))
            cov_bits = self._cover_bits[ch]
            pay_bits = self._payload_bits[ch]
            cov_bits2 = self._cover_bits2[ch]
            pay_bits2 = self._payload_bits2[ch]
            flips = 0
            for i in range(n):
                rr, col = divmod(i, self.COLS)
                x = 28 + col * (cell_w + 2)
                y = y0 + 18 + rr * (cell_h + 2)
                cover_bit = cov_bits[i]
                payload_bit = pay_bits[i]
                will_flip = (cover_bit != payload_bit)
                if self._depth == 2:
                    will_flip = will_flip or (cov_bits2[i] != pay_bits2[i])
                in_range = self._running and (i / n) < threshold
                flipped = in_range and will_flip
                touched = in_range and not will_flip
                if flipped:
                    fill = theme.AMBER
                    outline = theme.AMBER_HI
                    txt_col = theme.AMBER_INK
                    txt = "1" if payload_bit else "0"
                    flips += 1
                elif touched:
                    fill = theme.AMBER_LO
                    outline = theme.AMBER
                    txt_col = theme.AMBER_INK
                    txt = str(cover_bit)
                else:
                    fill = theme.BG_3 if cover_bit else theme.BG_5
                    outline = theme.STROKE
                    txt_col = theme.TEXT_LO if cover_bit else theme.TEXT_DIM
                    txt = str(cover_bit)
                c.create_rectangle(x, y, x + cell_w, y + cell_h,
                                    fill=fill, outline=outline)
                if cell_w >= 10:
                    c.create_text(x + cell_w / 2, y + cell_h / 2,
                                   text=txt, fill=txt_col,
                                   font=("JetBrains Mono", 8, "bold"))
            # Per-channel live flip counter
            c.create_text(w - 6, y0 + 8,
                           text=f"flips {flips}/{n}",
                           anchor="e",
                           fill=theme.TEXT_DIM,
                           font=("JetBrains Mono", 8, "bold"))


class PayloadDiagram(ctk.CTkFrame):
    """Real proportional MAGIC | SIZE | SALT | FERNET | MAC strip + legend.

    Sizes are pulled from core.payload constants. The FERNET segment scales
    with the actual ciphertext size set via set_payload_bytes(). A live
    amber sweep traces across during encoding (driven by set_progress).
    """
    # Real on-disk byte counts from core/payload.py + Fernet token framing
    # (Fernet token already includes IV+HMAC inside the ciphertext, but we
    # surface them as separate semantic segments so the user sees structure).
    BASE_SEGMENTS = [
        ("MAGIC",  8,  theme.KX_MAGIC,   "STGSTD02"),
        ("SIZE",   8,  theme.KX_SIZE,    "uint64 LE"),
        ("SALT",  16,  theme.KX_SALT,    "PBKDF2-SHA256"),
        ("NONCE", 16,  theme.KX_NONCE,   "Fernet IV"),
        ("CIPHER", 0,  theme.KX_PAYLOAD, "AES-128-CBC"),
        ("MAC",   32,  theme.KX_MAC,     "HMAC-SHA256"),
    ]

    def __init__(self, master, payload_bytes: int = 2048):
        super().__init__(master, fg_color="transparent")
        self._bytes = payload_bytes
        self._progress = 0.0
        self._running = False

        self._title = ctk.CTkLabel(
            self, text=f"PAYLOAD STRUCTURE — {self._total()} BYTES",
            font=("Segoe UI", 10, "bold"), text_color=theme.AMBER)
        self._title.pack(anchor="w", pady=(0, 8))

        self._canvas = _tk.Canvas(self, bg=theme.BG_1,
                                   height=56, highlightthickness=1,
                                   highlightbackground=theme.STROKE_HI)
        self._canvas.pack(fill="x")
        self._canvas.bind("<Configure>", lambda _e: self._paint())

        legend = ctk.CTkFrame(self, fg_color="transparent")
        legend.pack(fill="x", pady=(8, 0))
        for i, (name, nb, color, note) in enumerate(self._segments()):
            row = ctk.CTkFrame(legend, fg_color="transparent")
            row.grid(row=i // 2, column=i % 2, sticky="w", padx=(0, 14), pady=2)
            ctk.CTkLabel(row, text="  ", width=12, height=12,
                          fg_color=color, corner_radius=2).pack(side="left", padx=(0, 6))
            ctk.CTkLabel(row, text=name, width=58,
                          font=("JetBrains Mono", 10, "bold"),
                          text_color=theme.TEXT_HI, anchor="w"
                          ).pack(side="left")
            ctk.CTkLabel(row, text=f"{nb}B",
                          font=("JetBrains Mono", 9),
                          text_color=theme.TEXT_LO, width=58, anchor="w"
                          ).pack(side="left")
            ctk.CTkLabel(row, text=f"· {note}",
                          font=("Segoe UI", 9),
                          text_color=theme.TEXT_DIM, anchor="w"
                          ).pack(side="left")

        self.after(40, self._paint)

    def _segments(self):
        segs = list(self.BASE_SEGMENTS)
        segs[4] = ("CIPHER", max(0, self._bytes),
                   theme.KX_PAYLOAD, "AES-128-CBC")
        return segs

    def _total(self) -> int:
        return sum(nb for _, nb, _, _ in self._segments())

    def set_payload_bytes(self, n: int):
        self._bytes = max(0, int(n))
        self._title.configure(text=f"PAYLOAD STRUCTURE — {self._total()} BYTES")
        self._paint()

    def set_progress(self, p: float, running: bool):
        prev = self._progress
        self._progress = max(0.0, min(1.0, p))
        self._running = running
        if running and abs(self._progress - prev) < 0.02 and 0 < p < 1:
            return
        self._paint()

    def _paint(self):
        c = self._canvas
        c.delete("all")
        w = c.winfo_width() or 320
        h = int(c.cget("height"))
        segs = self._segments()
        # Use weighted log-scale so tiny header segments stay visible
        # while CIPHER still dominates when payload is large.
        weights = [max(8, math.log2(max(nb, 1) + 8) * 12) for _, nb, _, _ in segs]
        # Force CIPHER to take its real proportional share when payload large
        cipher_real_share = max(0.18, min(0.65,
                                segs[4][1] / max(64, self._total())))
        non_cipher_w = sum(weights) - weights[4]
        weights[4] = (cipher_real_share / max(1e-6, 1 - cipher_real_share)) * non_cipher_w
        total_w = sum(weights)
        x = 0
        for i, ((name, nb, color, _note), wt) in enumerate(zip(segs, weights)):
            seg_w = max(28, int((w - 2) * wt / total_w))
            if i == len(segs) - 1:
                seg_w = max(28, w - x - 1)
            # Body
            c.create_rectangle(x, 0, x + seg_w, h, fill=color, outline="")
            # Top highlight (rim-light, simulated alpha via blended hex)
            hi = _blend(color, "#FFFFFF", 0.18)
            c.create_rectangle(x, 0, x + seg_w, 3, fill=hi, outline="")
            # Bottom shadow
            sh = _blend(color, "#000000", 0.30)
            c.create_rectangle(x, h - 3, x + seg_w, h, fill=sh, outline="")
            # Label
            ink = "#000000" if _luminance(color) > 0.55 else "#FFFFFF"
            if seg_w >= 46:
                c.create_text(x + seg_w / 2, h / 2 - 6, text=name,
                               fill=ink, font=("Segoe UI", 9, "bold"))
                c.create_text(x + seg_w / 2, h / 2 + 8, text=f"{nb}B",
                               fill=ink, font=("JetBrains Mono", 8))
            elif seg_w >= 28:
                c.create_text(x + seg_w / 2, h / 2, text=name[:3],
                               fill=ink, font=("Segoe UI", 8, "bold"))
            if i < len(segs) - 1:
                c.create_line(x + seg_w, 0, x + seg_w, h,
                               fill=theme.BG_0)
            x += seg_w
        # Live sweep
        if self._running and 0.01 < self._progress < 0.99:
            sx = int((w - 2) * self._progress)
            c.create_line(sx, 0, sx, h, fill=theme.AMBER_HI, width=2)
            c.create_line(sx - 4, 0, sx - 4, h, fill=theme.AMBER, width=1)


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{max(0, min(255, r)):02X}{max(0, min(255, g)):02X}{max(0, min(255, b)):02X}"


def _blend(c1: str, c2: str, t: float) -> str:
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    return _rgb_to_hex(int(r1 + (r2 - r1) * t),
                       int(g1 + (g2 - g1) * t),
                       int(b1 + (b2 - b1) * t))


def _luminance(c: str) -> float:
    r, g, b = _hex_to_rgb(c)
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0


class CapacityBreakdown(ctk.CTkFrame):
    """Per-channel R/G/B capacity bars with gradient fills + threshold ticks."""
    CHANNELS = [("R", "#FF6B78"), ("G", "#6EE7A8"), ("B", "#6CC6F5")]

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        ctk.CTkLabel(self, text="CHANNEL CAPACITY — R / G / B",
                     font=("Segoe UI", 10, "bold"),
                     text_color=theme.AMBER
                     ).pack(anchor="w", pady=(0, 8))
        self._rows: list[tuple] = []
        for ch, col in self.CHANNELS:
            row = ctk.CTkFrame(self, fg_color="transparent")
            row.pack(fill="x", pady=4)
            head = ctk.CTkFrame(row, fg_color="transparent")
            head.pack(fill="x")
            ctk.CTkLabel(head, text=f"CHANNEL {ch}",
                         font=("Segoe UI", 9, "bold"),
                         text_color=col).pack(side="left")
            v_lbl = ctk.CTkLabel(head, text="—",
                                  font=("JetBrains Mono", 9),
                                  text_color=theme.TEXT_LO)
            v_lbl.pack(side="right")
            cv = _tk.Canvas(row, bg=theme.BG_4, height=12,
                             highlightthickness=1,
                             highlightbackground=theme.STROKE)
            cv.pack(fill="x", pady=(3, 0))
            cv._color = col
            cv.bind("<Configure>",
                    lambda _e, _cv=cv: self._paint_bar(_cv))
            self._rows.append((v_lbl, cv, col, 0.0, 0, 0))

        foot = ctk.CTkFrame(self, fg_color=theme.BG_3, corner_radius=4)
        foot.pack(fill="x", pady=(10, 0))
        ctk.CTkLabel(foot, text="TOTAL UTILISATION",
                     font=("Segoe UI", 9, "bold"),
                     text_color=theme.TEXT_LO
                     ).pack(side="left", padx=10, pady=6)
        self._foot_val = ctk.CTkLabel(foot, text="—",
                                       font=("JetBrains Mono", 10, "bold"),
                                       text_color=theme.AMBER)
        self._foot_val.pack(side="right", padx=10, pady=6)

    def set(self, used_bytes: int, total_bytes: int):
        if total_bytes <= 0:
            for i, (v_lbl, cv, col, _u, _pu, _pt) in enumerate(self._rows):
                v_lbl.configure(text="—")
                self._rows[i] = (v_lbl, cv, col, 0.0, 0, 0)
                self._paint_bar(cv)
            self._foot_val.configure(text="—", text_color=theme.AMBER)
            return
        per_ch_bytes = total_bytes // 3
        per_ch_used = used_bytes // 3
        usage = used_bytes / total_bytes
        for i, (v_lbl, cv, col, _u, _pu, _pt) in enumerate(self._rows):
            v_lbl.configure(
                text=f"{per_ch_used:,} / {per_ch_bytes:,} B")
            self._rows[i] = (v_lbl, cv, col, usage, per_ch_used, per_ch_bytes)
            self._paint_bar(cv)
        pct = usage * 100
        if pct < 50:
            txt, col = f"{pct:.3f}%  ·  undetectable", theme.OK
        elif pct < 90:
            txt, col = f"{pct:.2f}%  ·  approaching limit", theme.WARN
        else:
            txt, col = f"{pct:.2f}%  ·  over capacity", theme.ERR
        self._foot_val.configure(text=txt, text_color=col)

    def _paint_bar(self, cv):
        cv.delete("all")
        w = cv.winfo_width() or 200
        h = int(cv.cget("height"))
        # Find this canvas in rows
        usage = 0.0
        col = theme.AMBER
        for _v, _cv, _col, u, _pu, _pt in self._rows:
            if _cv is cv:
                usage, col = u, _col
                break
        # Gradient fill up to usage
        if usage > 0:
            fill_w = int((w - 2) * min(1.0, usage))
            # 14 slices for a simple gradient effect
            slices = 14
            for s in range(slices):
                x0 = 1 + int(fill_w * s / slices)
                x1 = 1 + int(fill_w * (s + 1) / slices)
                t = s / max(1, slices - 1)
                c = _blend(_blend(col, "#000000", 0.25),
                           col, t)
                cv.create_rectangle(x0, 1, x1, h - 1, fill=c, outline="")
            # Glint line
            cv.create_line(1, 2, 1 + fill_w, 2,
                            fill=_blend(col, "#FFFFFF", 0.45))
        # Threshold ticks at 70% and 90%
        for frac, tcol in ((0.70, theme.WARN), (0.90, theme.ERR)):
            x = int((w - 2) * frac) + 1
            cv.create_line(x, 0, x, h, fill=tcol, dash=(2, 2))


class HistogramPanel(ctk.CTkFrame):
    """Real per-channel histogram with before/after overlay + per-channel χ².

    Displayed band shows the G channel (dominant steganalysis signal), but
    χ² is computed for all three channels and surfaced in the footer so
    the user can see which channel has the largest deviation.
    """
    BINS = 128  # 256 bins downsampled 2:1 for clarity
    CHANNEL_COLOR = {"R": "#FF6B6B", "G": "#7DF9C0", "B": "#5BE3F0"}

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 6))
        self._title = ctk.CTkLabel(
            hdr, text="PIXEL INTENSITY HISTOGRAM — G CHANNEL",
            font=("Segoe UI", 10, "bold"),
            text_color=theme.AMBER)
        self._title.pack(side="left")
        self._channel = "G"
        # Init bins FIRST so set("G") (which fires _on_channel → _paint) is safe.
        empty = [0.0] * self.BINS
        self._bins_before = {"R": list(empty), "G": list(empty), "B": list(empty)}
        self._bins_after = {"R": list(empty), "G": list(empty), "B": list(empty)}

        self._canvas_placeholder = True  # guard during ctor

        self._chan_toggle = V2Segmented(hdr, ["R", "G", "B"],
                                          on_change=self._on_channel)
        self._chan_toggle.pack(side="right")

        self._canvas = _tk.Canvas(self, bg=theme.BG_1, height=96,
                                   highlightthickness=1,
                                   highlightbackground=theme.STROKE_HI)
        self._canvas.pack(fill="x")
        self._canvas.bind("<Configure>", lambda _e: self._paint())

        # Legend row
        leg = ctk.CTkFrame(self, fg_color="transparent")
        leg.pack(fill="x", pady=(6, 0))
        ctk.CTkLabel(leg, text="■", text_color=theme.TEXT_DIM,
                     font=("Segoe UI", 11)).pack(side="left")
        ctk.CTkLabel(leg, text="cover",
                     font=("Segoe UI", 9),
                     text_color=theme.TEXT_LO).pack(side="left", padx=(2, 10))
        ctk.CTkLabel(leg, text="■", text_color=theme.AMBER,
                     font=("Segoe UI", 11)).pack(side="left")
        ctk.CTkLabel(leg, text="stego",
                     font=("Segoe UI", 9),
                     text_color=theme.AMBER).pack(side="left", padx=(2, 10))
        ctk.CTkLabel(leg, text="log-scale Y  ·  0–255",
                     font=("Segoe UI", 9),
                     text_color=theme.TEXT_DIM).pack(side="left")

        foot = ctk.CTkFrame(self, fg_color=theme.BG_3, corner_radius=4)
        foot.pack(fill="x", pady=(10, 0))
        self._chi_labels: dict[str, ctk.CTkLabel] = {}
        for ch in ("R", "G", "B"):
            cell = ctk.CTkFrame(foot, fg_color="transparent")
            cell.pack(side="left", padx=10, pady=6)
            ctk.CTkLabel(cell, text=f"χ²({ch})",
                         font=("Segoe UI", 9, "bold"),
                         text_color=self.CHANNEL_COLOR[ch]
                         ).pack(side="left")
            lbl = ctk.CTkLabel(cell, text="—",
                                 font=("JetBrains Mono", 10),
                                 text_color=theme.TEXT_MID)
            lbl.pack(side="left", padx=(4, 0))
            self._chi_labels[ch] = lbl
        self._verdict = ctk.CTkLabel(
            foot, text="awaiting cover",
            font=("Segoe UI", 9, "bold"),
            text_color=theme.TEXT_DIM)
        self._verdict.pack(side="right", padx=10, pady=6)

        self._has_cover = False
        self._has_stego = False
        self._progress = 0.0
        self._running = False
        self._canvas_placeholder = False
        self._chan_toggle.set("G")
        self.after(60, self._paint)

    def _on_channel(self, value: str):
        self._channel = value
        self._title.configure(
            text=f"PIXEL INTENSITY HISTOGRAM — {value} CHANNEL")
        self._paint()

    # ── public API ─────────────────────────────────────────────────────────
    def set_cover(self, image):
        bins = self._compute_bins(image)
        if bins is None:
            return
        self._bins_before = bins
        self._bins_after = {ch: list(v) for ch, v in bins.items()}
        self._has_cover = True
        self._has_stego = False
        self._update_chi()
        self._paint()

    def set_stego(self, image):
        bins = self._compute_bins(image)
        if bins is None:
            return
        self._bins_after = bins
        self._has_stego = True
        self._update_chi()
        self._paint()

    def set_progress(self, p: float, running: bool):
        # Coarse throttle: only repaint when the sweep has moved >=2% of
        # the canvas width. Avoid recomputing bins here — the real
        # before/after is only meaningful once set_stego() runs at end.
        prev = self._progress
        self._progress = max(0.0, min(1.0, p))
        self._running = running
        if running and abs(self._progress - prev) < 0.02 and 0 < p < 1:
            return
        self._paint()

    # ── internal ───────────────────────────────────────────────────────────
    def _compute_bins(self, image) -> dict[str, list[float]] | None:
        try:
            img = image.convert("RGB")
        except Exception:
            return None
        hist = img.histogram()  # 256 R, 256 G, 256 B
        step = 256 // self.BINS
        out: dict[str, list[float]] = {}
        for idx, ch in enumerate(("R", "G", "B")):
            raw = hist[idx * 256:(idx + 1) * 256]
            ds = [sum(raw[i * step:(i + 1) * step]) for i in range(self.BINS)]
            total = sum(ds) or 1
            out[ch] = [v / total for v in ds]
        return out

    def _chi_value(self, ch: str) -> float:
        chi = 0.0
        for bv, av in zip(self._bins_before[ch], self._bins_after[ch]):
            denom = bv + av
            if denom > 0:
                chi += (bv - av) ** 2 / denom
        return chi

    def _update_chi(self):
        if not self._has_cover:
            for lbl in self._chi_labels.values():
                lbl.configure(text="—", text_color=theme.TEXT_MID)
            self._verdict.configure(text="awaiting cover",
                                      text_color=theme.TEXT_DIM)
            return
        chis = {ch: self._chi_value(ch) for ch in ("R", "G", "B")}
        for ch, chi in chis.items():
            self._chi_labels[ch].configure(
                text=f"{chi:.5f}",
                text_color=theme.TEXT_HI)
        peak = max(chis.values())
        if peak < 0.001:
            status, col = "below detection threshold", theme.OK
        elif peak < 0.01:
            status, col = "marginal", theme.WARN
        else:
            status, col = "DETECTABLE", theme.ERR
        self._verdict.configure(text=status, text_color=col)

    def _paint(self):
        c = self._canvas
        c.delete("all")
        w = c.winfo_width() or 320
        h = int(c.cget("height"))
        n = self.BINS
        bar_w = (w - 8) / n
        before = self._bins_before[self._channel]
        after = self._bins_after[self._channel]
        peak = max(max(before or [1e-9]),
                   max(after or [1e-9]),
                   1e-9)
        log_peak = math.log1p(peak * 1000)

        c.create_line(4, h - 4, w - 4, h - 4, fill=theme.STROKE_HI)

        ch_col = self.CHANNEL_COLOR[self._channel]
        for i in range(n):
            bv = before[i]
            av = after[i]
            x0 = 4 + i * bar_w
            x1 = x0 + max(1, bar_w - 0.5)
            bh = (math.log1p(bv * 1000) / log_peak) * (h - 8)
            c.create_rectangle(x0, h - 4 - bh, x1, h - 4,
                                fill=theme.TEXT_DIM, outline="")
            if av != bv and av > 0:
                ah = (math.log1p(av * 1000) / log_peak) * (h - 8)
                col = ch_col if av >= bv else _blend(ch_col, "#000000", 0.35)
                c.create_rectangle(x0, h - 4 - ah, x1, h - 4,
                                    fill=col, outline="")
        for frac in (0.25, 0.5, 0.75):
            y = h - 4 - frac * (h - 8)
            c.create_line(0, y, w, y, fill="#1a2a3a", dash=(1, 3))

        if self._running and 0.01 < self._progress < 0.99:
            sx = 4 + int((w - 8) * self._progress)
            c.create_line(sx, 0, sx, h, fill=theme.AMBER_HI, width=1)


class ConsoleLog(ctk.CTkFrame):
    """Timestamped event log — syslog-style, scrolling."""
    LEVEL_COLORS = {
        "info":   theme.TEXT_LO,
        "ok":     theme.OK,
        "warn":   theme.WARN,
        "crit":   theme.ERR,
        "accent": theme.AMBER,
    }

    def __init__(self, master):
        super().__init__(master, fg_color="#07080A", corner_radius=6,
                         border_width=1, border_color=theme.STROKE)
        self._txt = ctk.CTkTextbox(self, fg_color="#07080A",
                                    text_color=theme.TEXT_LO,
                                    font=("JetBrains Mono", 10),
                                    border_width=0, corner_radius=6,
                                    wrap="none")
        self._txt.pack(fill="both", expand=True, padx=8, pady=6)
        for lvl, col in self.LEVEL_COLORS.items():
            self._txt.tag_config(f"lvl-{lvl}", foreground=col)
        self._txt.tag_config("ts", foreground=theme.TEXT_DIM)
        self._txt.tag_config("msg", foreground=theme.TEXT_HI)
        self._txt.configure(state="disabled")
        self._count = 0

    def add(self, msg: str, level: str = "info"):
        import datetime as _dt
        ts = _dt.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self._txt.configure(state="normal")
        self._txt.insert("end", f"{ts}  ", "ts")
        self._txt.insert("end", f"[{level.upper():>6}]  ", f"lvl-{level}")
        self._txt.insert("end", f"{msg}\n", "msg")
        self._txt.see("end")
        self._txt.configure(state="disabled")
        self._count += 1

    def clear(self):
        self._txt.configure(state="normal")
        self._txt.delete("1.0", "end")
        self._txt.configure(state="disabled")
        self._count = 0

    @property
    def count(self) -> int:
        return self._count


class V2ProgressBar(ctk.CTkFrame):
    """Slim amber progress with optional shimmer + glow."""
    HEIGHT = 6

    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", theme.BG_5)
        kwargs.setdefault("corner_radius", 3)
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("border_color", theme.STROKE)
        kwargs.setdefault("height", self.HEIGHT)
        super().__init__(master, **kwargs)
        self.pack_propagate(False)
        self._fill = ctk.CTkFrame(self, fg_color=theme.AMBER,
                                   corner_radius=3, height=self.HEIGHT)
        self._fill.place(x=0, y=0, relheight=1, relwidth=0)
        self._frac = 0.0

    def set(self, frac: float, color: str | None = None):
        frac = max(0.0, min(1.0, frac))
        self._frac = frac
        self._fill.place_configure(relwidth=frac)
        if color:
            self._fill.configure(fg_color=color)

    def reset(self):
        self.set(0.0, color=theme.AMBER)


class CoverPreview(ctk.CTkFrame):
    """Image preview tile with corner labels + scan overlay during run."""
    HEIGHT = 220

    def __init__(self, master, accent: str = theme.AMBER, height: int | None = None):
        super().__init__(master, fg_color="#0a0a0a", corner_radius=6,
                         border_width=1, border_color=theme.STROKE_HI,
                         height=height or self.HEIGHT)
        self.pack_propagate(False)
        self._accent = accent
        self._photo = None
        self._path: str | None = None
        self._dims = (0, 0)
        self._mode = "RGB"

        self._canvas = _tk.Canvas(self, bg="#0a0a0a", highlightthickness=0)
        self._canvas.pack(fill="both", expand=True)
        self._canvas.bind("<Configure>", lambda _e: self._render())

        # Overlays managed inside canvas
        self._scan_y = None
        self._progress = 0.0
        self._running = False
        self._placeholder = "NO IMAGE"

    def set_accent(self, accent: str):
        self._accent = accent
        self._render()

    def load(self, path: str, dims: tuple[int, int] | None = None,
             mode: str | None = None):
        try:
            img = Image.open(path).convert("RGB")
        except Exception:
            self._placeholder = "INVALID IMAGE"
            self._photo = None
            self._render()
            return
        self._path = path
        self._dims = dims or img.size
        self._mode = mode or "RGB"
        self._raw = img
        self._render()

    def clear(self):
        self._path = None
        self._photo = None
        self._raw = None
        self._dims = (0, 0)
        self._placeholder = "NO IMAGE"
        self._render()

    def set_progress(self, p: float, running: bool):
        # The preview image itself doesn't change during encode/decode;
        # only redraw at transitions (start/finish) to avoid re-thumbnailing
        # the source image on every progress tick.
        was_running = self._running
        self._progress = max(0.0, min(1.0, p))
        self._running = running
        if was_running != running:
            self._render()

    def _render(self):
        c = self._canvas
        c.delete("all")
        w = c.winfo_width() or 320
        h = c.winfo_height() or self.HEIGHT
        if not self._path or not getattr(self, "_raw", None):
            c.create_text(w / 2, h / 2,
                           text=self._placeholder,
                           fill=theme.TEXT_DIM,
                           font=("Segoe UI", 11, "bold"))
        else:
            img = self._raw.copy()
            img.thumbnail((w, h), Image.LANCZOS)
            self._photo = ImageTk.PhotoImage(img)
            c.create_image(w / 2, h / 2, image=self._photo)

        # Corner labels
        if self._path:
            import os as _os
            name = _os.path.basename(self._path).upper()
            c.create_rectangle(8, 6, 8 + len(name) * 7 + 12, 24,
                                fill="#000000", outline="")
            c.create_text(14, 15, anchor="w", text=name,
                           fill=self._accent,
                           font=("JetBrains Mono", 9, "bold"))
            dim_lbl = f"{self._dims[0]}×{self._dims[1]} · {self._mode} · 24bpp"
            c.create_rectangle(w - len(dim_lbl) * 6 - 16, h - 24,
                                w - 8, h - 6,
                                fill="#000000", outline="")
            c.create_text(w - 14, h - 15, anchor="e", text=dim_lbl,
                           fill=theme.TEXT_LO,
                           font=("JetBrains Mono", 9))
            # R G B chips
            for i, (ch, col) in enumerate([("R", "#FF5C6B"),
                                            ("G", "#4ADE80"),
                                            ("B", "#4DD0E1")]):
                cx = 12 + i * 18
                cy = h - 14
                c.create_rectangle(cx - 7, cy - 7, cx + 7, cy + 7,
                                    fill=col, outline="")
                c.create_text(cx, cy, text=ch, fill="#000",
                               font=("JetBrains Mono", 8, "bold"))

        # Scan overlay
        if self._running:
            y = int(h * self._progress)
            c.create_rectangle(0, 0, w, y,
                                fill=self._accent, stipple="gray12",
                                outline="")
            c.create_line(0, y, w, y, fill=self._accent, width=2)


class ResultBox(ctk.CTkFrame):
    """Decrypted-payload viewer with success / failure / idle states."""
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self._inner = None

    def _clear(self):
        if self._inner is not None:
            self._inner.destroy()
            self._inner = None

    def show_idle(self):
        self._clear()
        self._inner = ctk.CTkLabel(
            self, text="Payload will appear here after successful HMAC verification.",
            font=("JetBrains Mono", 10),
            text_color=theme.TEXT_DIM, height=120)
        self._inner.pack(fill="both", expand=True, padx=14, pady=14)

    def show_text(self, text: str):
        self._clear()
        self._inner = ctk.CTkTextbox(
            self, fg_color="#07080A",
            text_color=theme.TEXT_HI,
            font=("JetBrains Mono", 11),
            border_width=1, border_color="#1E5C38",
            corner_radius=6, height=160)
        self._inner.pack(fill="both", expand=True, padx=14, pady=14)
        self._inner.insert("1.0", text)
        self._inner.configure(state="disabled")

    def show_error(self, msg: str):
        self._clear()
        wrap = ctk.CTkFrame(self, fg_color="#2C0A10",
                             border_width=1, border_color="#6A1828",
                             corner_radius=6)
        wrap.pack(fill="x", padx=14, pady=14)
        row = ctk.CTkFrame(wrap, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=14)
        ctk.CTkLabel(row, text="", image=icon("warn", 18, theme.ERR),
                      width=18).pack(side="left", padx=(0, 12))
        col = ctk.CTkFrame(row, fg_color="transparent")
        col.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(col, text="Authentication failed",
                     font=("Segoe UI", 13, "bold"),
                     text_color="#FF8A95",
                     anchor="w").pack(anchor="w")
        ctk.CTkLabel(col, text=msg,
                     font=("Segoe UI", 11),
                     text_color=theme.TEXT_MID,
                     anchor="w", justify="left",
                     wraplength=480).pack(anchor="w", pady=(2, 0))
        self._inner = wrap


# ═══════════════════════════════════════════════════════════════════════════
# V2VoiceCard — record / play / load WAV for the Voice payload mode.
# ═══════════════════════════════════════════════════════════════════════════

class V2VoiceCard(ctk.CTkFrame):
    """Compact voice-input card: Record/Stop/Play + waveform + Load WAV."""
    def __init__(self, master, on_change=None, accent: str | None = None):
        super().__init__(master, fg_color=theme.BG_3, corner_radius=6,
                         border_width=1, border_color=theme.STROKE_HI)
        self._on_change = on_change or (lambda _b: None)
        self._accent = accent or theme.AMBER
        self._rec = AudioRecorder()
        self._wav_bytes: bytes = b""
        self._playing = False
        self._pa_play = None
        self._stream_play = None

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=(10, 4))
        ctk.CTkLabel(
            top, text="", image=icon("mic", 14, self._accent), width=18,
        ).pack(side="left")
        ctk.CTkLabel(
            top, text="VOICE PAYLOAD",
            font=("Segoe UI", 10, "bold"),
            text_color=self._accent,
        ).pack(side="left", padx=(4, 0))
        self._time_lbl = ctk.CTkLabel(
            top, text="0.0 s · —",
            font=("JetBrains Mono", 10),
            text_color=theme.TEXT_LO,
        )
        self._time_lbl.pack(side="right")

        self._wave = WaveformCanvas(self, accent=self._accent)
        self._wave.pack(padx=10, pady=6)

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x", padx=10, pady=(2, 10))
        self._rec_btn = ctk.CTkButton(
            btns, text="Record", image=icon("record", 12, "#FFFFFF"),
            compound="left", width=0, height=30,
            fg_color="#8B1E2A", hover_color="#A9293A", text_color="#FFFFFF",
            font=("Segoe UI", 11, "bold"),
            command=self._toggle_record,
        )
        self._rec_btn.pack(side="left", padx=(0, 6))
        self._play_btn = ctk.CTkButton(
            btns, text="Play", image=icon("play", 12, theme.AMBER_INK),
            compound="left", width=0, height=30,
            fg_color=self._accent, hover_color=theme.AMBER_HI,
            text_color=theme.AMBER_INK,
            font=("Segoe UI", 11, "bold"), state="disabled",
            command=self._play,
        )
        self._play_btn.pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            btns, text="Load WAV…", image=icon("folder", 12, theme.TEXT_MID),
            compound="left", width=0, height=30,
            fg_color="transparent", hover_color=theme.BG_4,
            text_color=theme.TEXT_MID, border_width=1,
            border_color=theme.STROKE_HI,
            font=("Segoe UI", 11),
            command=self._load,
        ).pack(side="left", padx=(0, 6))
        self._clear_btn = ctk.CTkButton(
            btns, text="Clear",
            fg_color="transparent", hover_color=theme.BG_4,
            text_color=theme.TEXT_DIM, border_width=0,
            font=("Segoe UI", 10), width=0, height=30,
            command=self._clear, state="disabled",
        )
        self._clear_btn.pack(side="left")

        if not _PYAUDIO_OK:
            self._rec_btn.configure(
                state="disabled", fg_color=theme.BG_4, text_color=theme.TEXT_DIM,
            )
            ctk.CTkLabel(
                self, text="Mic unavailable — install PyAudio or load a WAV file",
                font=("Segoe UI", 9),
                text_color=theme.WARN,
            ).pack(anchor="w", padx=10, pady=(0, 8))

    # ── public ────────────────────────────────────────────────────────────
    def get_wav_bytes(self) -> bytes:
        return self._wav_bytes

    def wav_size(self) -> int:
        return len(self._wav_bytes)

    def wav_duration(self) -> float:
        return _wav_duration(self._wav_bytes)

    # ── internal ──────────────────────────────────────────────────────────
    def _toggle_record(self):
        if self._rec._recording:
            self._rec.stop()
            self._wav_bytes = self._rec.get_wav_bytes()
            self._rec_btn.configure(
                text="Record", image=icon("record", 12, "#FFFFFF"),
                fg_color="#8B1E2A",
            )
            self._wave.stop_recording(self._wav_bytes)
            self._refresh_info()
            self._on_change(self._wav_bytes)
        else:
            if not _PYAUDIO_OK:
                return
            self._wav_bytes = b""
            self._rec.start()
            self._rec_btn.configure(
                text="Stop", image=icon("stop", 12, "#FFFFFF"),
                fg_color="#C0392B",
            )
            self._wave.start_recording()
            self.after(100, self._tick)

    def _tick(self):
        if self._rec._recording:
            self._time_lbl.configure(
                text=f"{self._rec.duration:4.1f} s · recording",
            )
            self.after(100, self._tick)

    def _load(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Load WAV", filetypes=[("WAV audio", "*.wav")])
        if not path:
            return
        try:
            with open(path, "rb") as fh:
                self._wav_bytes = fh.read()
        except Exception:
            return
        self._wave.stop_recording(self._wav_bytes)
        self._refresh_info()
        self._on_change(self._wav_bytes)

    def _clear(self):
        self._wav_bytes = b""
        self._wave.clear()
        self._refresh_info()
        self._on_change(b"")

    def _refresh_info(self):
        if not self._wav_bytes:
            self._time_lbl.configure(text="0.0 s · —")
            self._play_btn.configure(state="disabled")
            self._clear_btn.configure(state="disabled")
            return
        dur = _wav_duration(self._wav_bytes)
        self._time_lbl.configure(
            text=f"{dur:.1f} s · {len(self._wav_bytes) / 1024:.1f} KB",
            text_color=theme.TEXT_MID,
        )
        self._play_btn.configure(state="normal")
        self._clear_btn.configure(state="normal")

    def _play(self):
        if not self._wav_bytes or not _PYAUDIO_OK or self._playing:
            return
        self._playing = True
        t = threading.Thread(target=self._play_loop, daemon=True)
        t.start()

    def _play_loop(self):
        try:
            buf = io.BytesIO(self._wav_bytes)
            with _wave.open(buf, "rb") as wf:
                pa = pyaudio.PyAudio()
                stream = pa.open(
                    format=pa.get_format_from_width(wf.getsampwidth()),
                    channels=wf.getnchannels(),
                    rate=wf.getframerate(),
                    output=True,
                )
                data = wf.readframes(1024)
                while data and self._playing:
                    stream.write(data)
                    data = wf.readframes(1024)
                stream.stop_stream()
                stream.close()
                pa.terminate()
        except Exception:
            pass
        finally:
            self._playing = False


def _wav_duration(wav_bytes: bytes) -> float:
    if not wav_bytes:
        return 0.0
    try:
        buf = io.BytesIO(wav_bytes)
        with _wave.open(buf, "rb") as wf:
            return wf.getnframes() / max(1, wf.getframerate())
    except Exception:
        return 0.0


class V2AudioResult(ctk.CTkFrame):
    """Decrypt-side audio result card: waveform + play + save."""
    def __init__(self, master, accent: str | None = None):
        super().__init__(master, fg_color=theme.BG_3, corner_radius=6,
                         border_width=1, border_color=theme.STROKE_HI)
        self._accent = accent or theme.INFO
        self._wav: bytes = b""
        self._ext: str = "wav"
        self._playing = False

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=(10, 4))
        ctk.CTkLabel(
            top, text="", image=icon("mic", 14, self._accent), width=18,
        ).pack(side="left")
        ctk.CTkLabel(
            top, text="RECOVERED AUDIO",
            font=("Segoe UI", 10, "bold"),
            text_color=self._accent,
        ).pack(side="left", padx=(4, 0))
        self._meta = ctk.CTkLabel(
            top, text="—",
            font=("JetBrains Mono", 10),
            text_color=theme.TEXT_LO,
        )
        self._meta.pack(side="right")

        self._wave = WaveformCanvas(self, accent=self._accent)
        self._wave.pack(padx=10, pady=6)

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x", padx=10, pady=(2, 10))
        self._play_btn = ctk.CTkButton(
            btns, text="Play", image=icon("play", 12, theme.AMBER_INK),
            compound="left", width=0, height=30,
            fg_color=self._accent, hover_color="#7DF0FF",
            text_color=theme.AMBER_INK,
            font=("Segoe UI", 11, "bold"), state="disabled",
            command=self._play,
        )
        self._play_btn.pack(side="left", padx=(0, 6))
        self._save_btn = ctk.CTkButton(
            btns, text="Save WAV…", image=icon("save", 12, theme.TEXT_MID),
            compound="left", width=0, height=30,
            fg_color="transparent", hover_color=theme.BG_4,
            text_color=theme.TEXT_MID, border_width=1,
            border_color=theme.STROKE_HI,
            font=("Segoe UI", 11), state="disabled",
            command=self._save,
        )
        self._save_btn.pack(side="left")

    def set_audio(self, wav_bytes: bytes, ext: str = "wav"):
        self._wav = wav_bytes or b""
        self._ext = (ext or "wav").lstrip(".")
        self._wave.stop_recording(self._wav)
        if self._wav:
            dur = _wav_duration(self._wav)
            self._meta.configure(
                text=f"{dur:.1f} s · {len(self._wav) / 1024:.1f} KB",
                text_color=theme.TEXT_MID,
            )
            self._play_btn.configure(state="normal")
            self._save_btn.configure(state="normal")
        else:
            self._meta.configure(text="—")
            self._play_btn.configure(state="disabled")
            self._save_btn.configure(state="disabled")

    def clear(self):
        self.set_audio(b"", "wav")

    def _play(self):
        if not self._wav or not _PYAUDIO_OK or self._playing:
            return
        self._playing = True
        threading.Thread(target=self._play_loop, daemon=True).start()

    def _play_loop(self):
        try:
            buf = io.BytesIO(self._wav)
            with _wave.open(buf, "rb") as wf:
                pa = pyaudio.PyAudio()
                stream = pa.open(
                    format=pa.get_format_from_width(wf.getsampwidth()),
                    channels=wf.getnchannels(),
                    rate=wf.getframerate(),
                    output=True,
                )
                data = wf.readframes(1024)
                while data and self._playing:
                    stream.write(data)
                    data = wf.readframes(1024)
                stream.stop_stream()
                stream.close()
                pa.terminate()
        except Exception:
            pass
        finally:
            self._playing = False

    def _save(self):
        if not self._wav:
            return
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            title="Save audio", defaultextension=f".{self._ext}",
            initialfile=f"recovered.{self._ext}",
            filetypes=[("Audio", f"*.{self._ext}")])
        if not path:
            return
        try:
            with open(path, "wb") as fh:
                fh.write(self._wav)
        except Exception:
            pass


_session_log: list[str] = []


def session_id() -> str:
    """Generate a stable 4-hex session id once per app run."""
    if not _session_log:
        _session_log.append(
            "".join(_random.choices("0123456789ABCDEF", k=4)))
    return _session_log[0]


# ─────────────────────────────────────────────────────────────────────────────
# BytePeek — focused 1-pixel "before -> after" affordance
# ─────────────────────────────────────────────────────────────────────────────

class BytePeek(ctk.CTkFrame):
    """Three R/G/B rows showing exactly what happens to one sample pixel.

    encrypt mode badge: FLIP / SAME (did the LSB write change the byte?)
    decrypt mode badge: BIT 0 / BIT 1 (the recovered payload bit per channel)
    """

    CHANNELS = ("R", "G", "B")
    CHANNEL_COLOR = {"R": "#FF6B6B", "G": "#7DF9C0", "B": "#5BE3F0"}

    def __init__(self, master, *, mode: str = "encrypt"):
        super().__init__(master, fg_color=theme.BG_2,
                         corner_radius=theme.RADIUS_MD,
                         border_width=1, border_color=theme.STROKE)
        self._mode = mode
        self._cover: tuple[int, int, int] | None = None
        self._stego: tuple[int, int, int] | None = None
        self._row_w: dict[str, dict] = {}

        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.pack(fill="x", padx=theme.PAD_MD, pady=theme.PAD_MD)

        title = ("Bit-level preview - 1 sample pixel" if mode == "encrypt"
                 else "Bit-level recovery - 1 sample pixel")
        ctk.CTkLabel(wrap, text=title, font=theme.H3,
                     text_color=theme.TEXT_HI, anchor="w").pack(
            fill="x")
        sub = ("This is exactly what gets written to one pixel."
               if mode == "encrypt"
               else "What we read from the stego pixel and the LSB recovered.")
        ctk.CTkLabel(wrap, text=sub, font=theme.BODY_SM,
                     text_color=theme.TEXT_LO, anchor="w").pack(
            fill="x", pady=(0, theme.PAD_SM))

        for ch in self.CHANNELS:
            self._row_w[ch] = self._build_row(wrap, ch)

    def _build_row(self, parent, ch: str) -> dict:
        row = ctk.CTkFrame(parent, fg_color=theme.BG_3,
                           corner_radius=theme.RADIUS_SM)
        row.pack(fill="x", pady=2)
        inner = ctk.CTkFrame(row, fg_color="transparent")
        inner.pack(fill="x", padx=theme.PAD_SM, pady=6)

        chip = ctk.CTkLabel(inner, text=f" {ch} ", font=theme.F_LABEL_B,
                            fg_color=self.CHANNEL_COLOR[ch],
                            text_color="#0A0F18",
                            corner_radius=theme.RADIUS_SM, width=24)
        chip.pack(side="left")

        cover_dec = ctk.CTkLabel(inner, text="-", font=theme.MONO,
                                 text_color=theme.TEXT_HI, width=36)
        cover_dec.pack(side="left", padx=(theme.PAD_SM, theme.PAD_XS))

        cover_bits = ctk.CTkLabel(inner, text="--------", font=theme.MONO,
                                  text_color=theme.TEXT_MID)
        cover_bits.pack(side="left", padx=theme.PAD_XS)

        ctk.CTkLabel(inner, text="->", font=theme.BODY,
                     text_color=theme.TEXT_DIM).pack(
            side="left", padx=theme.PAD_SM)

        stego_bits = ctk.CTkLabel(inner, text="--------", font=theme.MONO,
                                  text_color=theme.TEXT_MID)
        stego_bits.pack(side="left", padx=theme.PAD_XS)

        stego_dec = ctk.CTkLabel(inner, text="-", font=theme.MONO,
                                 text_color=theme.TEXT_HI, width=36)
        stego_dec.pack(side="left", padx=theme.PAD_XS)

        badge = ctk.CTkLabel(inner, text="-", font=theme.F_LABEL_B,
                             fg_color=theme.BG_4, text_color=theme.TEXT_LO,
                             corner_radius=theme.RADIUS_SM, width=64)
        badge.pack(side="right")

        return {"cover_dec": cover_dec, "cover_bits": cover_bits,
                "stego_bits": stego_bits, "stego_dec": stego_dec,
                "badge": badge}

    @staticmethod
    def _bits(n: int) -> str:
        return format(n & 0xFF, "08b")

    def set_cover_pixel(self, rgb: tuple[int, int, int]) -> None:
        self._cover = (int(rgb[0]) & 0xFF, int(rgb[1]) & 0xFF,
                       int(rgb[2]) & 0xFF)
        for i, ch in enumerate(self.CHANNELS):
            v = self._cover[i]
            w = self._row_w[ch]
            w["cover_dec"].configure(text=str(v))
            w["cover_bits"].configure(text=self._bits(v))
        self._refresh_badges()

    def set_stego_pixel(self, rgb: tuple[int, int, int]) -> None:
        self._stego = (int(rgb[0]) & 0xFF, int(rgb[1]) & 0xFF,
                       int(rgb[2]) & 0xFF)
        for i, ch in enumerate(self.CHANNELS):
            v = self._stego[i]
            w = self._row_w[ch]
            w["stego_dec"].configure(text=str(v))
            w["stego_bits"].configure(text=self._bits(v))
        self._refresh_badges()

    def clear(self) -> None:
        self._cover = None
        self._stego = None
        for ch in self.CHANNELS:
            w = self._row_w[ch]
            w["cover_dec"].configure(text="-")
            w["cover_bits"].configure(text="--------")
            w["stego_dec"].configure(text="-")
            w["stego_bits"].configure(text="--------")
            w["badge"].configure(text="-", fg_color=theme.BG_4,
                                 text_color=theme.TEXT_LO)

    def _refresh_badges(self) -> None:
        if self._cover is None:
            return
        for i, ch in enumerate(self.CHANNELS):
            badge = self._row_w[ch]["badge"]
            cv = self._cover[i]
            if self._mode == "decrypt":
                bit = cv & 1
                badge.configure(
                    text=f"BIT {bit}",
                    fg_color=theme.AMBER if bit else theme.BG_5,
                    text_color=theme.AMBER_INK if bit else theme.TEXT_HI)
            else:
                if self._stego is None:
                    badge.configure(text="...", fg_color=theme.BG_4,
                                    text_color=theme.TEXT_LO)
                    continue
                sv = self._stego[i]
                if (cv & 1) != (sv & 1):
                    badge.configure(text="FLIP", fg_color=theme.AMBER,
                                    text_color=theme.AMBER_INK)
                else:
                    badge.configure(text="SAME", fg_color=theme.BG_5,
                                    text_color=theme.TEXT_MID)


# ─────────────────────────────────────────────────────────────────────────────
# Toast — bottom-right transient notification with alpha fade
# ─────────────────────────────────────────────────────────────────────────────

class Toast(ctk.CTkToplevel):
    def __init__(self, parent, message: str, *, ms: int = 2400,
                 kind: str = "info"):
        super().__init__(parent)
        self.overrideredirect(True)
        try:
            self.attributes("-topmost", True)
            self.attributes("-alpha", 0.0)
        except Exception:
            pass
        accent = {"info": theme.AMBER, "ok": theme.OK,
                  "warn": theme.WARN, "err": theme.ERR}.get(kind, theme.AMBER)
        self.configure(fg_color=theme.BG_2)

        ctk.CTkFrame(self, fg_color=accent, width=4,
                     corner_radius=0).pack(side="left", fill="y")
        body = ctk.CTkFrame(self, fg_color=theme.BG_2,
                            border_width=1, border_color=theme.STROKE)
        body.pack(side="left", fill="both", expand=True)
        ctk.CTkLabel(body, text=message, font=theme.BODY,
                     text_color=theme.TEXT_HI, anchor="w").pack(
            padx=theme.PAD_MD, pady=theme.PAD_SM)

        self.update_idletasks()
        try:
            px = parent.winfo_rootx() + parent.winfo_width()
            py = parent.winfo_rooty() + parent.winfo_height()
            w = self.winfo_reqwidth()
            h = self.winfo_reqheight()
            self.geometry(f"+{px - w - 24}+{py - h - 24}")
        except Exception:
            pass

        self._fade_in(0.0)
        self.after(ms, self._fade_out)

    def _fade_in(self, a: float) -> None:
        try:
            self.attributes("-alpha", a)
        except Exception:
            return
        if a < 0.95:
            self.after(20, lambda: self._fade_in(a + 0.15))

    def _fade_out(self, a: float = 1.0) -> None:
        try:
            self.attributes("-alpha", a)
        except Exception:
            self.destroy()
            return
        if a <= 0.05:
            self.destroy()
            return
        self.after(20, lambda: self._fade_out(a - 0.15))


def show_toast(parent, message: str, *, kind: str = "info",
               ms: int = 2400) -> Toast:
    return Toast(parent, message, ms=ms, kind=kind)
