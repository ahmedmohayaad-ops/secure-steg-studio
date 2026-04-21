# steg_studio/gui/assets.py
"""Procedural SVG-style icons drawn with Pillow."""
from __future__ import annotations

import customtkinter as ctk
from PIL import Image, ImageDraw

from . import theme


_CACHE: dict[str, ctk.CTkImage] = {}


def _make(draw_fn, size: int, color: str) -> ctk.CTkImage:
    scale = 4
    big = size * scale
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    draw_fn(d, big, color)
    img = img.resize((size, size), Image.LANCZOS)
    return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))


def _lock(d, s, c):
    m = s // 8
    d.arc([3 * m, m, 5 * m, 4 * m], start=180, end=0, fill=c, width=max(1, m))
    d.rounded_rectangle([2 * m, 3 * m, 6 * m, 7 * m], radius=m // 2, fill=c)


def _unlock(d, s, c):
    m = s // 8
    d.arc([2 * m, m, 4 * m, 4 * m], start=180, end=0, fill=c, width=max(1, m))
    d.rounded_rectangle([2 * m, 3 * m, 6 * m, 7 * m], radius=m // 2, fill=c)


def _image(d, s, c):
    m = s // 8
    d.rounded_rectangle([m, 2 * m, 7 * m, 6 * m], radius=m, outline=c, width=max(1, m // 2))
    d.ellipse([2 * m, 3 * m, 3 * m, 4 * m], fill=c)
    d.polygon([2 * m, 6 * m, 4 * m, 4 * m, 5 * m, 5 * m, 6 * m, 4 * m, 7 * m, 6 * m], fill=c)


def _file(d, s, c):
    m = s // 8
    d.polygon([2 * m, m, 5 * m, m, 6 * m, 2 * m, 6 * m, 7 * m, 2 * m, 7 * m], outline=c, fill=None, width=max(1, m // 2))
    d.line([5 * m, m, 5 * m, 2 * m, 6 * m, 2 * m], fill=c, width=max(1, m // 2))


def _text(d, s, c):
    m = s // 8
    for y in (2, 3, 4, 5):
        d.line([m, y * m, 7 * m, y * m], fill=c, width=max(1, m // 2))


def _mic(d, s, c):
    m = s // 8
    d.rounded_rectangle([3 * m, m, 5 * m, 5 * m], radius=m, fill=c)
    d.arc([2 * m, 3 * m, 6 * m, 6 * m], start=0, end=180, fill=c, width=max(1, m // 2))
    d.line([4 * m, 6 * m, 4 * m, 7 * m], fill=c, width=max(1, m // 2))
    d.line([3 * m, 7 * m, 5 * m, 7 * m], fill=c, width=max(1, m // 2))


def _play(d, s, c):
    m = s // 8
    d.polygon([2 * m, m, 7 * m, 4 * m, 2 * m, 7 * m], fill=c)


def _stop(d, s, c):
    m = s // 8
    d.rectangle([2 * m, 2 * m, 6 * m, 6 * m], fill=c)


def _record(d, s, c):
    m = s // 8
    d.ellipse([m, m, 7 * m, 7 * m], fill=c)


def _save(d, s, c):
    m = s // 8
    d.rounded_rectangle([m, m, 7 * m, 7 * m], radius=m // 2, outline=c, width=max(1, m // 2))
    d.rectangle([2 * m, 4 * m, 6 * m, 7 * m], fill=c)


def _chevron_r(d, s, c):
    m = s // 8
    d.line([3 * m, m, 6 * m, 4 * m, 3 * m, 7 * m], fill=c, width=max(1, m))


def _hex(d, s, c):
    m = s // 8
    pts = [(4 * m, m), (7 * m, 2 * m + m // 2), (7 * m, 5 * m + m // 2),
           (4 * m, 7 * m), (m, 5 * m + m // 2), (m, 2 * m + m // 2)]
    d.polygon(pts, outline=c, fill=None, width=max(1, m // 2))


def _warn(d, s, c):
    m = s // 8
    d.polygon([4 * m, m, 7 * m, 7 * m, m, 7 * m], outline=c, fill=None, width=max(1, m // 2))
    d.line([4 * m, 3 * m, 4 * m, 5 * m], fill=c, width=max(1, m // 2))


def _clear(d, s, c):
    m = s // 8
    d.line([2 * m, 2 * m, 6 * m, 6 * m], fill=c, width=max(1, m))
    d.line([6 * m, 2 * m, 2 * m, 6 * m], fill=c, width=max(1, m))


def _check(d, s, c):
    m = s // 8
    d.line([m, 4 * m, 3 * m, 6 * m, 7 * m, 2 * m], fill=c, width=max(1, m))


def _shield(d, s, c):
    m = s // 8
    d.polygon([(4 * m, m), (7 * m, 2 * m), (7 * m, 4 * m),
               (4 * m, 7 * m), (m, 4 * m), (m, 2 * m)],
              outline=c, fill=None, width=max(1, m // 2))
    d.line([3 * m, 4 * m, 4 * m, 5 * m, 5 * m, 3 * m], fill=c, width=max(1, m // 2))


def _key(d, s, c):
    m = s // 8
    d.ellipse([m, 4 * m, 4 * m, 7 * m], outline=c, width=max(1, m // 2))
    d.line([3 * m + m // 2, 4 * m + m // 2, 7 * m, m], fill=c, width=max(1, m // 2))
    d.line([6 * m, 2 * m, 7 * m, 3 * m], fill=c, width=max(1, m // 2))


def _eye(d, s, c):
    m = s // 8
    d.ellipse([m, 3 * m, 7 * m, 5 * m], outline=c, width=max(1, m // 2))
    d.ellipse([3 * m, 3 * m + m // 2, 5 * m, 4 * m + m // 2 + m], fill=c)


def _eye_off(d, s, c):
    m = s // 8
    d.ellipse([m, 3 * m, 7 * m, 5 * m], outline=c, width=max(1, m // 2))
    d.line([m, 7 * m, 7 * m, m], fill=c, width=max(1, m // 2))


def _embed(d, s, c):
    m = s // 8
    d.rounded_rectangle([m, 2 * m, 7 * m, 7 * m], radius=m // 2,
                         outline=c, width=max(1, m // 2))
    d.line([4 * m, 3 * m, 4 * m, 6 * m], fill=c, width=max(1, m // 2))
    d.line([3 * m, 5 * m, 4 * m, 6 * m, 5 * m, 5 * m], fill=c, width=max(1, m // 2))


def _history(d, s, c):
    m = s // 8
    d.arc([m, m, 7 * m, 7 * m], start=20, end=340, fill=c, width=max(1, m // 2))
    d.line([4 * m, 2 * m, 4 * m, 4 * m, 5 * m + m // 2, 5 * m], fill=c, width=max(1, m // 2))


def _layers(d, s, c):
    m = s // 8
    d.polygon([4 * m, m, 7 * m, 3 * m, 4 * m, 5 * m, m, 3 * m],
              outline=c, fill=None, width=max(1, m // 2))
    d.line([m, 5 * m, 4 * m, 7 * m, 7 * m, 5 * m], fill=c, width=max(1, m // 2))


def _chart(d, s, c):
    m = s // 8
    d.line([m, 7 * m, 7 * m, 7 * m], fill=c, width=max(1, m // 2))
    d.rectangle([m + m // 2, 5 * m, 2 * m + m // 2, 7 * m], fill=c)
    d.rectangle([3 * m + m // 2, 3 * m, 4 * m + m // 2, 7 * m], fill=c)
    d.rectangle([5 * m + m // 2, 4 * m, 6 * m + m // 2, 7 * m], fill=c)


def _cpu(d, s, c):
    m = s // 8
    d.rounded_rectangle([2 * m, 2 * m, 6 * m, 6 * m], radius=m // 2,
                         outline=c, width=max(1, m // 2))
    d.rectangle([3 * m + m // 2, 3 * m + m // 2,
                 4 * m + m // 2, 4 * m + m // 2], fill=c)
    for x in (3 * m, 5 * m):
        d.line([x, m, x, 2 * m], fill=c, width=max(1, m // 2))
        d.line([x, 6 * m, x, 7 * m], fill=c, width=max(1, m // 2))
        d.line([m, x, 2 * m, x], fill=c, width=max(1, m // 2))
        d.line([6 * m, x, 7 * m, x], fill=c, width=max(1, m // 2))


def _terminal(d, s, c):
    m = s // 8
    d.rounded_rectangle([m, 2 * m, 7 * m, 7 * m], radius=m // 2,
                         outline=c, width=max(1, m // 2))
    d.line([2 * m, 4 * m, 3 * m, 5 * m, 2 * m, 6 * m], fill=c, width=max(1, m // 2))
    d.line([4 * m + m // 2, 6 * m, 6 * m, 6 * m], fill=c, width=max(1, m // 2))


def _cog(d, s, c):
    import math as _m
    m = s // 8
    d.ellipse([2 * m, 2 * m, 6 * m, 6 * m], outline=c, width=max(1, m // 2))
    d.ellipse([3 * m + m // 2, 3 * m + m // 2,
               4 * m + m // 2, 4 * m + m // 2], outline=c, width=max(1, m // 2))
    cx, cy = 4 * m, 4 * m
    for ang in (0, 90, 180, 270):
        rx = cx + int(_m.cos(_m.radians(ang)) * 3 * m)
        ry = cy + int(_m.sin(_m.radians(ang)) * 3 * m)
        d.line([cx, cy, rx, ry], fill=c, width=max(1, m // 2))


def _download(d, s, c):
    m = s // 8
    d.line([4 * m, m, 4 * m, 5 * m], fill=c, width=max(1, m // 2))
    d.line([2 * m, 4 * m, 4 * m, 6 * m, 6 * m, 4 * m], fill=c, width=max(1, m // 2))
    d.line([m, 7 * m, 7 * m, 7 * m], fill=c, width=max(1, m // 2))


def _folder(d, s, c):
    m = s // 8
    d.polygon([m, 3 * m, 3 * m, 3 * m, 4 * m, 2 * m, 7 * m, 2 * m,
               7 * m, 7 * m, m, 7 * m],
              outline=c, fill=None, width=max(1, m // 2))


def _activity(d, s, c):
    m = s // 8
    d.line([m, 4 * m, 2 * m + m // 2, 4 * m, 3 * m + m // 2, m,
            4 * m + m // 2, 7 * m, 5 * m + m // 2, 4 * m, 7 * m, 4 * m],
           fill=c, width=max(1, m // 2))


_MAP = {
    "lock": _lock, "unlock": _unlock, "image": _image, "file": _file,
    "text": _text, "mic": _mic, "play": _play, "stop": _stop,
    "record": _record, "save": _save, "chevron_r": _chevron_r,
    "hex": _hex, "warn": _warn, "clear": _clear, "check": _check,
    "shield": _shield, "key": _key, "eye": _eye, "eye_off": _eye_off,
    "embed": _embed,
    "history": _history, "layers": _layers, "chart": _chart, "cpu": _cpu,
    "terminal": _terminal, "cog": _cog, "download": _download,
    "folder": _folder, "activity": _activity,
}


def icon(name: str, size: int = 16, color: str = theme.CYAN) -> ctk.CTkImage | None:
    key = f"{name}|{size}|{color}"
    if key not in _CACHE and name in _MAP:
        _CACHE[key] = _make(_MAP[name], size, color)
    return _CACHE.get(key)
