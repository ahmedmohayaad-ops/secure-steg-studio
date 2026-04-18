# steg_studio/gui/decrypt_panel.py
"""Decrypt workspace — v2.1 forensic layout.

Two-column grid (workspace | inspector). Workspace stacks:
  · Extract payload card  (stego dropzone + passphrase + Decrypt button)
  · Signal inspection     (image preview + LSB visualizer + progress)
  · Recovered payload     (decoded text or auth-failed banner)
Inspector stacks:
  · Carrier analysis      (3 stats + KV list — payload size, χ², integrity)
  · Payload diagram
  · Histogram
"""
from __future__ import annotations

import io
import os
import threading
import wave as _wave
from tkinter import filedialog, messagebox

import customtkinter as ctk

from steg_studio.core import check_magic, decode, get_image_info

from . import theme
from .assets import icon
from .components import (
    V2Card, V2Button, V2Badge, V2Stat, V2KV, V2DropZone, V2ProgressBar,
    CoverPreview, LSBVisualizer, PayloadDiagram, HistogramPanel, ResultBox,
    session_id,
)
from .workers import run_in_thread


class DecryptPanel(ctk.CTkFrame):
    def __init__(self, master, *, log=None, on_status=None, **kwargs):
        kwargs.setdefault("fg_color", theme.BG_1)
        super().__init__(master, **kwargs)
        self._log = log or (lambda *_a, **_k: None)
        self._on_status = on_status or (lambda *_a, **_k: None)

        self._stego_path: str | None = None
        self._stego_info: dict | None = None
        self._running = False
        self._result: dict | None = None
        self._error: str | None = None

        self._build()
        self._refresh()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0, minsize=360)
        self.grid_rowconfigure(0, weight=1)

        left = ctk.CTkScrollableFrame(self, fg_color=theme.BG_1,
                                       scrollbar_button_color=theme.BG_5,
                                       scrollbar_button_hover_color=theme.BG_6)
        left.grid(row=0, column=0, sticky="nsew",
                   padx=(16, 8), pady=(16, 8))
        left.grid_columnconfigure(0, weight=1)

        self._build_inputs_card(left).grid(row=0, column=0, sticky="ew",
                                              pady=(0, 14))
        self._build_inspection_card(left).grid(row=1, column=0, sticky="ew",
                                                  pady=(0, 14))
        self._build_result_card(left).grid(row=2, column=0, sticky="ew",
                                              pady=(0, 4))

        right = ctk.CTkScrollableFrame(self, fg_color=theme.BG_1,
                                        scrollbar_button_color=theme.BG_5,
                                        scrollbar_button_hover_color=theme.BG_6)
        right.grid(row=0, column=1, sticky="nsew",
                    padx=(8, 16), pady=(16, 8))
        right.grid_columnconfigure(0, weight=1)

        self._build_carrier_card(right).grid(row=0, column=0, sticky="ew",
                                                pady=(0, 14))
        self._build_diagram_card(right).grid(row=1, column=0, sticky="ew",
                                                pady=(0, 14))
        self._build_histogram_card(right).grid(row=2, column=0, sticky="ew")

    # ── workspace cards ──────────────────────────────────────────────────────
    def _build_inputs_card(self, parent) -> V2Card:
        card = V2Card(parent)
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=14, pady=(12, 8))
        ctk.CTkLabel(head, text="",
                      image=icon("unlock", 14, theme.AMBER), width=18
                      ).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(head, text="Extract payload",
                      font=("Segoe UI", 13, "bold"),
                      text_color=theme.TEXT_HI
                      ).pack(side="left")
        V2Badge(head, "FERNET", "accent", icon_name="shield"
                 ).pack(side="left", padx=10)
        ctk.CTkLabel(head,
                      text=f"session#{session_id()}",
                      font=("JetBrains Mono", 10),
                      text_color=theme.TEXT_DIM
                      ).pack(side="right")
        ctk.CTkFrame(card, height=1, fg_color=theme.STROKE
                      ).pack(fill="x", padx=14)

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=14, pady=14)
        body.grid_columnconfigure(0, weight=12, uniform="d")
        body.grid_columnconfigure(1, weight=10, uniform="d")

        c1 = ctk.CTkFrame(body, fg_color="transparent")
        c1.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkLabel(c1, text="01 · STEGO IMAGE",
                     font=("Segoe UI", 9, "bold"),
                     text_color=theme.TEXT_DIM, anchor="w"
                     ).pack(anchor="w", pady=(0, 6))
        self._stego_dz = V2DropZone(c1, kind="image", on_pick=self._on_stego)
        self._stego_dz.pack(fill="x")

        c2 = ctk.CTkFrame(body, fg_color="transparent")
        c2.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        ctk.CTkLabel(c2, text="02 · PASSPHRASE",
                     font=("Segoe UI", 9, "bold"),
                     text_color=theme.TEXT_DIM, anchor="w"
                     ).pack(anchor="w", pady=(0, 6))
        self._pw_var = ctk.StringVar()
        self._pw_var.trace_add("write", lambda *_: self._refresh())
        self._pw = ctk.CTkEntry(
            c2, textvariable=self._pw_var, show="●",
            height=34, fg_color=theme.BG_4,
            border_color=theme.STROKE_HI, border_width=1,
            text_color=theme.TEXT_HI,
            font=("JetBrains Mono", 12),
            placeholder_text="enter decryption key")
        self._pw.pack(fill="x")
        self._pw.bind("<Return>", lambda _e: self._run())

        self._run_btn = V2Button(c2, "Decrypt", variant="primary",
                                   icon_name="play", size="md",
                                   command=self._run)
        self._run_btn.pack(fill="x", pady=(10, 0))
        return card

    def _build_inspection_card(self, parent) -> V2Card:
        card = V2Card(parent)
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=14, pady=(12, 8))
        ctk.CTkLabel(head, text="",
                      image=icon("eye", 14, theme.AMBER), width=18
                      ).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(head, text="Signal inspection",
                      font=("Segoe UI", 13, "bold"),
                      text_color=theme.TEXT_HI
                      ).pack(side="left")
        self._status_badge = V2Badge(head, "READY", "neutral")
        self._status_badge.pack(side="right")
        ctk.CTkFrame(card, height=1, fg_color=theme.STROKE
                      ).pack(fill="x", padx=14)

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=14, pady=12)
        body.grid_columnconfigure(0, weight=11, uniform="prev")
        body.grid_columnconfigure(1, weight=10, uniform="prev")

        # Decrypt mode wears cyan accents on the preview overlay
        self._preview = CoverPreview(body, accent=theme.INFO, height=240)
        self._preview.grid(row=0, column=0, sticky="ew", padx=(0, 7))

        self._lsb = LSBVisualizer(body)
        self._lsb.grid(row=0, column=1, sticky="nsew", padx=(7, 0))

        ctk.CTkFrame(card, height=1, fg_color=theme.STROKE
                      ).pack(fill="x", padx=14)
        prog_wrap = ctk.CTkFrame(card, fg_color="transparent")
        prog_wrap.pack(fill="x", padx=14, pady=(10, 14))
        head2 = ctk.CTkFrame(prog_wrap, fg_color="transparent")
        head2.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(head2, text="LSB EXTRACTION",
                     font=("Segoe UI", 9, "bold"),
                     text_color=theme.TEXT_DIM
                     ).pack(side="left")
        self._prog_lbl = ctk.CTkLabel(head2, text="0.0%",
                                       font=("JetBrains Mono", 10),
                                       text_color=theme.AMBER)
        self._prog_lbl.pack(side="right")
        self._prog = V2ProgressBar(prog_wrap)
        self._prog.pack(fill="x")
        return card

    def _build_result_card(self, parent) -> V2Card:
        card = V2Card(parent)
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=14, pady=(12, 8))
        self._result_icon = ctk.CTkLabel(
            head, text="", image=icon("terminal", 14, theme.AMBER), width=18)
        self._result_icon.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(head, text="Recovered payload",
                      font=("Segoe UI", 13, "bold"),
                      text_color=theme.TEXT_HI
                      ).pack(side="left")
        self._save_btn = V2Button(head, "Save payload",
                                    variant="secondary", icon_name="save",
                                    command=self._save)
        self._save_btn.pack(side="right")
        self._save_btn.configure(state="disabled")
        ctk.CTkFrame(card, height=1, fg_color=theme.STROKE
                      ).pack(fill="x", padx=14)
        self._result_box = ResultBox(card)
        self._result_box.pack(fill="x")
        self._result_box.show_idle()
        from .components import V2AudioResult
        self._audio_result = V2AudioResult(card, accent=theme.INFO)
        # Audio result hidden until an audio payload is recovered
        return card

    # ── inspector cards ──────────────────────────────────────────────────────
    def _build_carrier_card(self, parent) -> V2Card:
        card = V2Card(parent)
        ctk.CTkLabel(card, text="Carrier analysis",
                     font=("Segoe UI", 13, "bold"),
                     text_color=theme.TEXT_HI
                     ).pack(anchor="w", padx=14, pady=(12, 6))

        stats = ctk.CTkFrame(card, fg_color="transparent")
        stats.pack(fill="x", padx=14, pady=(4, 6))
        stats.grid_columnconfigure(0, weight=1, uniform="s")
        stats.grid_columnconfigure(1, weight=1, uniform="s")
        stats.grid_columnconfigure(2, weight=1, uniform="s")
        self._stat_payload = V2Stat(stats, "Payload", "—", "B", "ok")
        self._stat_payload.grid(row=0, column=0, sticky="ew", padx=2)
        self._stat_chi = V2Stat(stats, "χ²", "—", tone="warn")
        self._stat_chi.grid(row=0, column=1, sticky="ew", padx=2)
        self._stat_int = V2Stat(stats, "Integrity", "—", tone="warn")
        self._stat_int.grid(row=0, column=2, sticky="ew", padx=2)

        kv_wrap = ctk.CTkFrame(card, fg_color="transparent")
        kv_wrap.pack(fill="x", padx=14, pady=(6, 14))
        self._kv_stego = V2KV(kv_wrap, "Stego", "—")
        self._kv_stego.pack(fill="x", pady=2)
        self._kv_dims = V2KV(kv_wrap, "Dims", "—")
        self._kv_dims.pack(fill="x", pady=2)
        V2KV(kv_wrap, "MAGIC", "0x53544731", accent=True).pack(fill="x", pady=2)
        V2KV(kv_wrap, "Cipher", "Fernet").pack(fill="x", pady=2)
        self._kv_hmac = V2KV(kv_wrap, "HMAC", "pending")
        self._kv_hmac.pack(fill="x", pady=2)
        return card

    def _build_diagram_card(self, parent) -> V2Card:
        card = V2Card(parent)
        wrap = ctk.CTkFrame(card, fg_color="transparent")
        wrap.pack(fill="x", padx=14, pady=14)
        self._diagram = PayloadDiagram(wrap, payload_bytes=2048)
        self._diagram.pack(fill="x")
        return card

    def _build_histogram_card(self, parent) -> V2Card:
        card = V2Card(parent)
        wrap = ctk.CTkFrame(card, fg_color="transparent")
        wrap.pack(fill="x", padx=14, pady=14)
        self._hist = HistogramPanel(wrap)
        self._hist.pack(fill="x")
        return card

    # ── handlers ─────────────────────────────────────────────────────────────
    def _on_stego(self, path: str):
        self._stego_path = path
        try:
            info = get_image_info(path)
            self._stego_info = info
            self._preview.load(path,
                                dims=(info["width"], info["height"]),
                                mode=info.get("mode", "RGB"))
            self._kv_stego.set(os.path.basename(path))
            self._kv_dims.set(f"{info['width']}×{info['height']}")
            try:
                from PIL import Image as _PI
                stego_img = _PI.open(path)
                stego_img.load()
                self._lsb.set_cover_sample(stego_img)
                self._hist.set_cover(stego_img)
            except Exception:
                pass
        except Exception:
            self._kv_stego.set(os.path.basename(path))
        self._result = None
        self._error = None
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
            self._run_btn.configure(state="normal", text="Working…")
        else:
            self._run_btn.configure(
                state="normal" if ok else "disabled",
                text="Decrypt again" if self._result else "Decrypt")
        self._save_btn.configure(
            state="normal" if (self._result and self._result.get("ok")) else "disabled")

    def _run(self):
        if self._running or not self._stego_path or not self._pw_var.get():
            return
        path = self._stego_path
        pwd = self._pw_var.get()

        self._running = True
        self._result = None
        self._error = None
        self._prog.reset()
        self._lsb.set_progress(0.0, True)
        self._preview.set_progress(0.0, True)
        self._hist.set_progress(0.0, True)
        self._status_badge.set("SCANNING LSB", "warn")
        self._stat_int.set("…", tone="warn")
        self._kv_hmac.set("verifying…")
        self._result_box.show_idle()
        self._log(f"▶ Begin decryption · {os.path.basename(path)}", "accent")
        self._log("Scan LSB plane for MAGIC=STG1", "info")
        self._refresh()

        fn = lambda progress_callback: decode(path, pwd, progress_callback)
        run_in_thread(self, fn,
                       on_progress=self._on_progress,
                       on_done=self._on_done,
                       on_error=self._on_error)

    def _on_progress(self, p: float):
        self._prog.set(p)
        self._prog_lbl.configure(text=f"{p*100:.1f}%")
        self._lsb.set_progress(p, True)
        self._preview.set_progress(p, True)
        self._hist.set_progress(p, True)
        self._diagram.set_progress(p, True)

    def _on_done(self, result: dict):
        self._running = False
        self._result = {"ok": True, "data": result}
        self._prog.set(1.0, color=theme.OK)
        self._lsb.set_progress(1.0, False)
        self._preview.set_progress(1.0, False)
        self._hist.set_progress(1.0, False)
        self._status_badge.set("AUTHENTICATED", "ok")
        self._kv_hmac.set("verified")
        self._stat_int.set("OK", tone="ok")

        typ = result["type"]
        data = result["data"]
        size = len(data)
        self._stat_payload.set(theme.fmt_bytes(size).split()[0],
                                 theme.fmt_bytes(size).split()[-1], "ok")
        self._diagram.set_payload_bytes(max(64, size))
        self._result_icon.configure(image=icon("check", 14, theme.OK))
        self._log(f"✓ Payload authenticated · HMAC verified · {size:,} B recovered",
                   "ok")

        if typ == "audio":
            self._result_box.pack_forget()
            meta = result.get("meta", {})
            ext = meta.get("ext", "wav")
            self._audio_result.set_audio(data, ext=ext)
            self._audio_result.pack(fill="x", padx=14, pady=(0, 14))
        else:
            self._audio_result.pack_forget()
            self._result_box.pack(fill="x")
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
        self._refresh()

    def _on_error(self, exc: BaseException):
        self._running = False
        self._result = {"ok": False, "err": str(exc)}
        self._prog.set(1.0, color=theme.ERR)
        self._lsb.set_progress(1.0, False)
        self._preview.set_progress(0.0, False)
        self._hist.set_progress(0.0, False)
        self._status_badge.set("HMAC FAILED", "crit")
        self._kv_hmac.set("MISMATCH")
        self._stat_int.set("FAIL", tone="crit")
        self._result_icon.configure(image=icon("warn", 14, theme.ERR))
        self._result_box.show_error(
            f"HMAC verification failed — wrong passphrase or corrupted stego.\n"
            f"Detail: {exc}")
        self._log(f"✗ HMAC mismatch · authentication failed · {exc}", "crit")
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
