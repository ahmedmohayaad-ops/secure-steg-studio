# steg_studio/gui/decrypt_panel.py
"""Simplified Decrypt workspace.

Single column: stego dropzone + password + Decrypt → BytePeek →
ResultBox / V2AudioResult. Forensic dashboards live in Inspector tab.
"""
from __future__ import annotations

import datetime as _dt
import os
import threading
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image as _PI

from steg_studio.core import check_magic, decode, get_image_info

from . import theme
from .assets import icon
from .components import (
    BytePeek,
    ResultBox,
    V2AudioResult,
    V2Badge,
    V2Button,
    V2Card,
    V2DropZone,
    V2KV,
    V2ProgressBar,
    show_toast,
)
from .workers import run_in_thread


class DecryptPanel(ctk.CTkFrame):
    def __init__(self, master, *, log=None, on_status=None,
                 on_inspect=None, **kwargs):
        kwargs.setdefault("fg_color", theme.BG_1)
        super().__init__(master, **kwargs)
        self._log = log or (lambda *_a, **_k: None)
        self._on_status = on_status or (lambda *_a, **_k: None)
        self._on_inspect = on_inspect or (lambda _state: None)

        self._stego_path: str | None = None
        self._stego_info: dict | None = None
        self._stego_img: _PI.Image | None = None
        self._sample_xy: tuple[int, int] | None = None
        self._running = False
        self._result: dict | None = None

        self._build()
        self._refresh()

    def _build(self):
        wrap = ctk.CTkScrollableFrame(
            self, fg_color=theme.BG_1,
            scrollbar_button_color=theme.BG_5,
            scrollbar_button_hover_color=theme.BG_6)
        wrap.pack(fill="both", expand=True)

        self._build_inputs_card(wrap).pack(
            fill="x", padx=theme.PAD_LG, pady=(theme.PAD_LG, theme.PAD_MD))
        self._peek = BytePeek(wrap, mode="decrypt")
        self._peek.pack(fill="x", padx=theme.PAD_LG, pady=(0, theme.PAD_MD))
        self._build_result_card(wrap).pack(
            fill="x", padx=theme.PAD_LG, pady=(0, theme.PAD_LG))

    def _build_inputs_card(self, parent) -> V2Card:
        card = V2Card(parent)
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=theme.PAD_MD, pady=(theme.PAD_MD,
                                                     theme.PAD_SM))
        ctk.CTkLabel(head, text="Extract payload", font=theme.H3,
                     text_color=theme.TEXT_HI).pack(side="left")
        self._status_badge = V2Badge(head, "READY", "neutral")
        self._status_badge.pack(side="right")

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=theme.PAD_MD, pady=(0, theme.PAD_MD))
        body.grid_columnconfigure(0, weight=1, uniform="d")
        body.grid_columnconfigure(1, weight=1, uniform="d")

        c1 = ctk.CTkFrame(body, fg_color="transparent")
        c1.grid(row=0, column=0, sticky="ew", padx=(0, theme.PAD_SM))
        ctk.CTkLabel(c1, text="STEGO IMAGE", font=theme.LABEL,
                     text_color=theme.TEXT_DIM, anchor="w").pack(
            anchor="w", pady=(0, theme.PAD_XS))
        self._stego_dz = V2DropZone(c1, kind="image", on_pick=self._on_stego)
        self._stego_dz.pack(fill="x")

        c2 = ctk.CTkFrame(body, fg_color="transparent")
        c2.grid(row=0, column=1, sticky="ew", padx=(theme.PAD_SM, 0))
        ctk.CTkLabel(c2, text="PASSPHRASE", font=theme.LABEL,
                     text_color=theme.TEXT_DIM, anchor="w").pack(
            anchor="w", pady=(0, theme.PAD_XS))
        self._pw_var = ctk.StringVar()
        self._pw_var.trace_add("write", lambda *_: self._refresh())
        self._pw = ctk.CTkEntry(
            c2, textvariable=self._pw_var, show="●", height=36,
            fg_color=theme.BG_4, border_color=theme.STROKE_HI,
            border_width=1, text_color=theme.TEXT_HI,
            font=theme.MONO, placeholder_text="enter decryption key",
            corner_radius=theme.RADIUS_SM)
        self._pw.pack(fill="x")
        self._pw.bind("<Return>", lambda _e: self._run())

        self._prog = V2ProgressBar(card)
        self._prog.pack(fill="x", padx=theme.PAD_MD, pady=(0, theme.PAD_SM))

        self._run_btn = V2Button(card, "Decrypt", variant="primary",
                                 icon_name="play", size="lg",
                                 command=self._run)
        self._run_btn.pack(fill="x", padx=theme.PAD_MD,
                           pady=(0, theme.PAD_MD))
        return card

    def _build_result_card(self, parent) -> V2Card:
        card = V2Card(parent)
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=theme.PAD_MD, pady=(theme.PAD_MD,
                                                     theme.PAD_SM))
        self._result_icon = ctk.CTkLabel(
            head, text="", image=icon("terminal", 14, theme.AMBER), width=18)
        self._result_icon.pack(side="left", padx=(0, theme.PAD_SM))
        ctk.CTkLabel(head, text="Recovered payload", font=theme.H3,
                     text_color=theme.TEXT_HI).pack(side="left")
        self._save_btn = V2Button(head, "Save payload",
                                  variant="secondary", icon_name="save",
                                  command=self._save)
        self._save_btn.pack(side="right")
        self._save_btn.configure(state="disabled")

        self._result_box = ResultBox(card)
        self._result_box.pack(fill="x", padx=theme.PAD_MD,
                              pady=(0, theme.PAD_MD))
        self._result_box.show_idle()
        self._audio_result = V2AudioResult(card, accent=theme.INFO)
        return card

    # ── handlers ──────────────────────────────────────────────────────────
    def _on_stego(self, path: str):
        self._stego_path = path
        try:
            info = get_image_info(path)
            self._stego_info = info
            try:
                stego_img = _PI.open(path).convert("RGB")
                stego_img.load()
                self._stego_img = stego_img
                w, h = stego_img.size
                xy = (w // 2, h // 2)
                self._sample_xy = xy
                self._peek.set_cover_pixel(stego_img.getpixel(xy))
            except Exception:
                pass
            self._stego_dz.set_meta(
                f"{info['width']}×{info['height']} · "
                f"{info.get('mode','RGB')}")
        except Exception:
            pass
        self._result = None
        self._result_box.show_idle()

        def _probe():
            try:
                v1 = check_magic(path)
                txt = "LEGACY v1 DETECTED" if v1 else "ENCRYPTED — KEY REQUIRED"
                self.after(0, lambda: self._log(
                    f"Probe · {os.path.basename(path)} · {txt}", "info"))
            except Exception:
                pass
        threading.Thread(target=_probe, daemon=True).start()
        self._refresh()

    def _refresh(self):
        ok = bool(self._stego_path and self._pw_var.get())
        if self._running:
            self._run_btn.configure(state="disabled", text="Working…")
        else:
            self._run_btn.configure(
                state="normal" if ok else "disabled",
                text="Decrypt again" if self._result else "Decrypt")
        self._save_btn.configure(
            state="normal" if (self._result and self._result.get("ok"))
            else "disabled")

    def _run(self):
        if self._running or not self._stego_path or not self._pw_var.get():
            return
        path = self._stego_path
        pwd = self._pw_var.get()

        self._running = True
        self._result = None
        self._prog.reset()
        self._status_badge.set("SCANNING LSB", "warn")
        self._result_box.show_idle()
        self._log(f"▶ Begin decryption · {os.path.basename(path)}", "accent")
        self._refresh()

        fn = lambda progress_callback: decode(path, pwd, progress_callback)
        run_in_thread(self, fn,
                      on_progress=self._on_progress,
                      on_done=self._on_done,
                      on_error=self._on_error)

    def _on_progress(self, p: float):
        self._prog.set(p)

    def _on_done(self, result: dict):
        self._running = False
        self._result = {"ok": True, "data": result}
        self._prog.set(1.0, color=theme.OK)
        self._status_badge.set("AUTHENTICATED", "ok")
        self._result_icon.configure(image=icon("check", 14, theme.OK))

        typ = result["type"]
        data = result["data"]
        size = len(data)
        self._log(f"✓ Payload authenticated · {size:,} B recovered", "ok")

        if typ == "audio":
            self._result_box.pack_forget()
            meta = result.get("meta", {})
            ext = meta.get("ext", "wav")
            self._audio_result.set_audio(data, ext=ext)
            self._audio_result.pack(
                fill="x", padx=theme.PAD_MD, pady=(0, theme.PAD_MD))
        else:
            self._audio_result.pack_forget()
            self._result_box.pack(
                fill="x", padx=theme.PAD_MD, pady=(0, theme.PAD_MD))
            if typ == "text":
                try:
                    txt = data.decode("utf-8")
                except UnicodeDecodeError:
                    txt = f"<{len(data)} non-UTF-8 bytes>"
                self._result_box.show_text(txt)
            else:
                meta = result.get("meta", {})
                name = meta.get("filename") or f"extracted.{typ}"
                self._result_box.show_text(
                    f"[{typ.upper()} payload]\n\n"
                    f"filename : {name}\n"
                    f"size     : {theme.fmt_bytes(size)}\n\n"
                    f"Use 'Save payload' to export to disk.")
        try:
            show_toast(self.winfo_toplevel(),
                       f"Decrypted · {theme.fmt_bytes(size)}", kind="ok")
        except Exception:
            pass
        self._push_inspector(size, typ)
        self._refresh()

    def _push_inspector(self, size: int, typ: str):
        if self._stego_img is None:
            return
        label = (f"{os.path.basename(self._stego_path or 'stego')} · "
                 f"{typ} · {theme.fmt_bytes(size)}")
        state = {
            "mode": "decrypt",
            "cover_image": self._stego_img,  # the stego is the carrier here
            "stego_image": None,
            "payload_bytes": size,
            "label": label,
            "timestamp": _dt.datetime.now().strftime("%H:%M:%S"),
        }
        try:
            self._on_inspect(state)
        except Exception:
            pass

    def _on_error(self, exc: BaseException):
        self._running = False
        self._result = {"ok": False, "err": str(exc)}
        self._prog.set(1.0, color=theme.ERR)
        self._status_badge.set("HMAC FAILED", "crit")
        self._result_icon.configure(image=icon("warn", 14, theme.ERR))
        self._result_box.show_error(
            f"HMAC verification failed — wrong passphrase or corrupted stego.\n"
            f"Detail: {exc}")
        self._log(f"✗ HMAC mismatch · {exc}", "crit")
        try:
            show_toast(self.winfo_toplevel(),
                       "Decryption failed", kind="err")
        except Exception:
            pass
        self._refresh()

    def _save(self):
        if not (self._result and self._result.get("ok")):
            return
        result = self._result["data"]
        typ = result["type"]
        data = result["data"]
        meta = result.get("meta", {})
        if typ == "text":
            initial = "message.txt"
            types = [("Text", "*.txt"), ("All", "*.*")]
        elif typ == "audio":
            ext = meta.get("ext", "wav")
            initial = f"extracted.{ext}"
            types = [(ext.upper(), f"*.{ext}"), ("All", "*.*")]
        else:
            initial = meta.get("filename", "extracted.bin")
            types = [("All files", "*.*")]
        path = filedialog.asksaveasfilename(
            title="Save payload", initialfile=initial, filetypes=types)
        if not path:
            return
        try:
            with open(path, "wb") as f:
                f.write(data if isinstance(data, (bytes, bytearray))
                        else data.encode("utf-8"))
            self._log(f"Payload saved → {path}", "ok")
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc))
