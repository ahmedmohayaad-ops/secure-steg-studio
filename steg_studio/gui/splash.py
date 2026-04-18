"""Branded splash screen shown before the main App window appears."""
from __future__ import annotations

import customtkinter as ctk
import tkinter as _tk
from PIL import Image, ImageDraw

from . import theme


def _logo_image(size: int = 128) -> ctk.CTkImage:
    """Render an amber lock-shield mark composed at high res then downscaled."""
    scale = 4
    big = size * scale
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Outer shield
    pad = big // 10
    pts = [
        (big // 2, pad),
        (big - pad, pad + big // 6),
        (big - pad, big // 2 + big // 8),
        (big // 2, big - pad),
        (pad, big // 2 + big // 8),
        (pad, pad + big // 6),
    ]
    d.polygon(pts, fill=theme.AMBER)
    d.line(pts + [pts[0]], fill=theme.AMBER_HI, width=max(2, big // 80))

    # Inner lock body
    cx, cy = big // 2, big // 2 + big // 16
    bw, bh = big // 3, big // 4
    d.rounded_rectangle(
        [cx - bw // 2, cy - bh // 4, cx + bw // 2, cy + bh // 2 + bh // 4],
        radius=big // 32, fill=theme.AMBER_INK,
    )
    # Shackle
    sw = bw // 2
    d.arc(
        [cx - sw, cy - bh, cx + sw, cy - bh // 5],
        start=180, end=0, fill=theme.AMBER_INK, width=max(3, big // 32),
    )
    # Keyhole
    kr = big // 40
    d.ellipse([cx - kr, cy - kr, cx + kr, cy + kr], fill=theme.AMBER)
    d.rectangle([cx - kr // 2, cy, cx + kr // 2, cy + kr * 3], fill=theme.AMBER)

    img = img.resize((size, size), Image.LANCZOS)
    return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))


class SplashScreen(ctk.CTkToplevel):
    def __init__(self, master, on_done, hold_ms: int = 1200):
        super().__init__(master)
        self.overrideredirect(True)
        self.configure(fg_color=theme.BG_0)
        self._on_done = on_done
        self._hold_ms = hold_ms

        w, h = 520, 320
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")
        self.attributes("-topmost", True)

        # 1px amber rim
        rim = ctk.CTkFrame(self, fg_color=theme.AMBER, corner_radius=0)
        rim.pack(fill="both", expand=True)
        body = ctk.CTkFrame(rim, fg_color=theme.BG_1, corner_radius=0)
        body.pack(fill="both", expand=True, padx=1, pady=1)

        # Logo
        self._logo = _logo_image(128)
        ctk.CTkLabel(body, text="", image=self._logo).pack(pady=(36, 12))

        ctk.CTkLabel(
            body, text="Steg Studio",
            font=("Segoe UI", 24, "bold"),
            text_color=theme.TEXT_HI,
        ).pack()
        ctk.CTkLabel(
            body, text="Forensic Steganography Workstation",
            font=("Segoe UI", 11),
            text_color=theme.TEXT_LO,
        ).pack(pady=(2, 18))

        # Progress
        self._bar_outer = ctk.CTkFrame(
            body, fg_color=theme.BG_3, corner_radius=2,
            width=320, height=4,
        )
        self._bar_outer.pack(pady=(0, 8))
        self._bar_outer.pack_propagate(False)
        self._bar = ctk.CTkFrame(
            self._bar_outer, fg_color=theme.AMBER,
            corner_radius=2, width=0, height=4,
        )
        self._bar.place(x=0, y=0)

        ctk.CTkLabel(
            body, text="v2.1.0  ·  initialising forensic core",
            font=("JetBrains Mono", 9),
            text_color=theme.TEXT_DIM,
        ).pack()

        self._step = 0
        self._steps = 24
        self.after(40, self._tick)

    def _tick(self):
        self._step += 1
        frac = min(1.0, self._step / self._steps)
        self._bar.configure(width=int(320 * frac))
        if self._step < self._steps:
            self.after(self._hold_ms // self._steps, self._tick)
        else:
            self.after(120, self._finish)

    def _finish(self):
        try:
            self.destroy()
        except _tk.TclError:
            pass
        self._on_done()
