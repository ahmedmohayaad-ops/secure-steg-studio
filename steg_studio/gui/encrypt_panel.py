# steg_studio/gui/encrypt_panel.py
"""Encrypt workspace — v2.1 forensic layout.

Two-column grid (workspace | inspector). Workspace stacks:
  · Embed payload card     (cover + payload droppers, password, algo)
  · Forensic preview card  (image preview + LSB visualizer + progress)
  · Histogram card         (before/after intensity + chi-squared)
Inspector stacks:
  · Operation summary      (3 stats + KV list)
  · Payload diagram        (MAGIC | SIZE | SALT | NONCE | FERNET | MAC)
  · Channel capacity       (R/G/B striped bars)
  · Action card            (Begin encryption / Export stego)
"""
from __future__ import annotations

import os
from tkinter import filedialog, messagebox

import customtkinter as ctk

from steg_studio.core import (
    encode_text, encode_file, encode_audio, get_image_info, estimate_encrypted_size,
)

from . import theme
from .assets import icon
from .components import (
    V2Card, V2Button, V2Badge, V2Stat, V2KV, V2Segmented,
    V2DropZone, V2ProgressBar, CoverPreview, LSBVisualizer,
    PayloadDiagram, CapacityBreakdown, HistogramPanel, session_id,
)
from .workers import run_in_thread


class EncryptPanel(ctk.CTkFrame):
    def __init__(self, master, *, log=None, on_status=None, **kwargs):
        kwargs.setdefault("fg_color", theme.BG_1)
        super().__init__(master, **kwargs)
        self._log = log or (lambda *_a, **_k: None)
        self._on_status = on_status or (lambda *_a, **_k: None)

        self._cover_path: str | None = None
        self._cover_info: dict | None = None
        self._payload_path: str | None = None
        self._payload_text: str = ""
        self._payload_kind = "file"   # file | text
        self._running = False
        self._complete = False
        self._stego_out: str | None = None

        self._build()
        self._refresh()

    # ── layout ───────────────────────────────────────────────────────────────
    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0, minsize=360)
        self.grid_rowconfigure(0, weight=1)

        # ────── LEFT: workspace stack ──────
        left = ctk.CTkScrollableFrame(self, fg_color=theme.BG_1,
                                       scrollbar_button_color=theme.BG_5,
                                       scrollbar_button_hover_color=theme.BG_6)
        left.grid(row=0, column=0, sticky="nsew",
                   padx=(16, 8), pady=(16, 8))
        left.grid_columnconfigure(0, weight=1)

        self._build_inputs_card(left).grid(row=0, column=0, sticky="ew",
                                              pady=(0, 14))
        self._build_preview_card(left).grid(row=1, column=0, sticky="ew",
                                              pady=(0, 14))
        self._build_histogram_card(left).grid(row=2, column=0, sticky="ew",
                                                pady=(0, 4))

        # ────── RIGHT: inspector stack ──────
        right = ctk.CTkScrollableFrame(self, fg_color=theme.BG_1,
                                        scrollbar_button_color=theme.BG_5,
                                        scrollbar_button_hover_color=theme.BG_6)
        right.grid(row=0, column=1, sticky="nsew",
                    padx=(8, 16), pady=(16, 8))
        right.grid_columnconfigure(0, weight=1)

        self._build_summary_card(right).grid(row=0, column=0, sticky="ew",
                                               pady=(0, 14))
        self._build_payload_diagram_card(right).grid(row=1, column=0, sticky="ew",
                                                        pady=(0, 14))
        self._build_capacity_card(right).grid(row=2, column=0, sticky="ew",
                                                 pady=(0, 14))
        self._build_action_card(right).grid(row=3, column=0, sticky="ew")

    # ── cards ────────────────────────────────────────────────────────────────
    def _card_header(self, parent, title: str, badge_text: str | None = None,
                      badge_tone: str = "accent",
                      icon_name: str | None = "embed"):
        head = ctk.CTkFrame(parent, fg_color="transparent", height=44)
        head.pack(fill="x", padx=14, pady=(12, 8))
        if icon_name:
            ctk.CTkLabel(head, text="",
                          image=icon(icon_name, 14, theme.AMBER),
                          width=18).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(head, text=title,
                      font=("Segoe UI", 13, "bold"),
                      text_color=theme.TEXT_HI
                      ).pack(side="left")
        if badge_text:
            V2Badge(head, badge_text, badge_tone, icon_name="shield"
                     ).pack(side="left", padx=10)
        ctk.CTkLabel(head,
                      text=f"session#{session_id()}",
                      font=("JetBrains Mono", 10),
                      text_color=theme.TEXT_DIM
                      ).pack(side="right")
        return head

    def _build_inputs_card(self, parent) -> V2Card:
        card = V2Card(parent)
        self._card_header(card, "Embed payload",
                           badge_text="FERNET · PBKDF2",
                           badge_tone="accent")
        ctk.CTkFrame(card, height=1, fg_color=theme.STROKE
                      ).pack(fill="x", padx=14)

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=14, pady=14)
        body.grid_columnconfigure(0, weight=1, uniform="dz")
        body.grid_columnconfigure(1, weight=1, uniform="dz")

        # 01 cover
        c1 = ctk.CTkFrame(body, fg_color="transparent")
        c1.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkLabel(c1, text="01 · COVER CARRIER",
                     font=("Segoe UI", 9, "bold"),
                     text_color=theme.TEXT_DIM, anchor="w"
                     ).pack(anchor="w", pady=(0, 6))
        self._cover_dz = V2DropZone(c1, kind="image",
                                       on_pick=self._on_cover)
        self._cover_dz.pack(fill="x")

        # 02 payload
        c2 = ctk.CTkFrame(body, fg_color="transparent")
        c2.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        head2 = ctk.CTkFrame(c2, fg_color="transparent")
        head2.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(head2, text="02 · SECRET PAYLOAD",
                     font=("Segoe UI", 9, "bold"),
                     text_color=theme.TEXT_DIM, anchor="w"
                     ).pack(side="left")
        self._payload_seg = V2Segmented(
            head2, ["File", "Text", "Voice"],
            on_change=self._on_payload_kind,
            icons=["file", "text", "mic"])
        self._payload_seg.pack(side="right")

        # File dropzone (default)
        self._payload_dz = V2DropZone(c2, kind="file",
                                        on_pick=self._on_payload_file)
        self._payload_dz.pack(fill="x")

        # Text payload (hidden until selected)
        self._text_payload = ctk.CTkTextbox(
            c2, height=90, fg_color=theme.BG_3,
            text_color=theme.TEXT_HI, border_color=theme.STROKE_HI,
            border_width=1, corner_radius=6,
            font=("JetBrains Mono", 11))
        self._text_payload.bind(
            "<KeyRelease>", lambda _e: self._on_payload_text())

        # Voice payload (hidden until selected)
        from .components import V2VoiceCard
        self._voice_card = V2VoiceCard(
            c2, on_change=lambda _b: self._refresh(),
            accent=theme.AMBER)

        # Row 2: passphrase + confirm + algorithm
        row2 = ctk.CTkFrame(card, fg_color="transparent")
        row2.pack(fill="x", padx=14, pady=(0, 14))
        row2.grid_columnconfigure(0, weight=1, uniform="r2")
        row2.grid_columnconfigure(1, weight=1, uniform="r2")
        row2.grid_columnconfigure(2, weight=0)

        # 03 password
        p1 = ctk.CTkFrame(row2, fg_color="transparent")
        p1.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkLabel(p1, text="03 · PASSPHRASE",
                     font=("Segoe UI", 9, "bold"),
                     text_color=theme.TEXT_DIM, anchor="w"
                     ).pack(anchor="w", pady=(0, 6))
        self._pw_var = ctk.StringVar()
        self._pw_var.trace_add("write", lambda *_: self._refresh())
        self._pw = ctk.CTkEntry(
            p1, textvariable=self._pw_var, show="●",
            height=34, fg_color=theme.BG_4,
            border_color=theme.STROKE_HI, border_width=1,
            text_color=theme.TEXT_HI,
            font=("JetBrains Mono", 12),
            placeholder_text="min. 6 chars")
        self._pw.pack(fill="x")

        # 04 confirm
        p2 = ctk.CTkFrame(row2, fg_color="transparent")
        p2.grid(row=0, column=1, sticky="ew", padx=(8, 8))
        ctk.CTkLabel(p2, text="04 · CONFIRM",
                     font=("Segoe UI", 9, "bold"),
                     text_color=theme.TEXT_DIM, anchor="w"
                     ).pack(anchor="w", pady=(0, 6))
        self._pw2_var = ctk.StringVar()
        self._pw2_var.trace_add("write", lambda *_: self._refresh())
        self._pw2 = ctk.CTkEntry(
            p2, textvariable=self._pw2_var, show="●",
            height=34, fg_color=theme.BG_4,
            border_color=theme.STROKE_HI, border_width=1,
            text_color=theme.TEXT_HI,
            font=("JetBrains Mono", 12),
            placeholder_text="re-enter")
        self._pw2.pack(fill="x")

        # algorithm
        p3 = ctk.CTkFrame(row2, fg_color="transparent")
        p3.grid(row=0, column=2, sticky="ew", padx=(8, 0))
        ctk.CTkLabel(p3, text="ALGORITHM",
                     font=("Segoe UI", 9, "bold"),
                     text_color=theme.TEXT_DIM, anchor="w"
                     ).pack(anchor="w", pady=(0, 6))
        self._algo_seg = V2Segmented(p3, ["LSB · 1-bit", "LSB · 2-bit"])
        self._algo_seg.pack()

        return card

    def _build_preview_card(self, parent) -> V2Card:
        card = V2Card(parent)
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=14, pady=(12, 8))
        ctk.CTkLabel(head, text="",
                      image=icon("eye", 14, theme.AMBER), width=18
                      ).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(head, text="Forensic preview",
                      font=("Segoe UI", 13, "bold"),
                      text_color=theme.TEXT_HI
                      ).pack(side="left")
        self._status_badge = V2Badge(head, "IDLE", "neutral")
        self._status_badge.pack(side="right")

        ctk.CTkFrame(card, height=1, fg_color=theme.STROKE
                      ).pack(fill="x", padx=14)

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=14, pady=12)
        body.grid_columnconfigure(0, weight=11, uniform="prev")
        body.grid_columnconfigure(1, weight=10, uniform="prev")

        self._preview = CoverPreview(body, accent=theme.AMBER, height=240)
        self._preview.grid(row=0, column=0, sticky="ew", padx=(0, 7))

        self._lsb = LSBVisualizer(body)
        self._lsb.grid(row=0, column=1, sticky="nsew", padx=(7, 0))

        # Progress strip
        ctk.CTkFrame(card, height=1, fg_color=theme.STROKE
                      ).pack(fill="x", padx=14)
        prog_wrap = ctk.CTkFrame(card, fg_color="transparent")
        prog_wrap.pack(fill="x", padx=14, pady=(10, 14))
        prog_head = ctk.CTkFrame(prog_wrap, fg_color="transparent")
        prog_head.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(prog_head, text="EMBEDDING PROGRESS",
                     font=("Segoe UI", 9, "bold"),
                     text_color=theme.TEXT_DIM
                     ).pack(side="left")
        self._prog_lbl = ctk.CTkLabel(prog_head, text="0.0%  ·  0 bits",
                                       font=("JetBrains Mono", 10),
                                       text_color=theme.AMBER)
        self._prog_lbl.pack(side="right")
        self._prog = V2ProgressBar(prog_wrap)
        self._prog.pack(fill="x")
        return card

    def _build_histogram_card(self, parent) -> V2Card:
        card = V2Card(parent)
        wrap = ctk.CTkFrame(card, fg_color="transparent")
        wrap.pack(fill="x", padx=14, pady=14)
        self._hist = HistogramPanel(wrap)
        self._hist.pack(fill="x")
        return card

    def _build_summary_card(self, parent) -> V2Card:
        card = V2Card(parent)
        h = ctk.CTkFrame(card, fg_color="transparent")
        h.pack(fill="x", padx=14, pady=(12, 6))
        ctk.CTkLabel(h, text="Operation summary",
                     font=("Segoe UI", 13, "bold"),
                     text_color=theme.TEXT_HI
                     ).pack(anchor="w")
        ctk.CTkLabel(h, text="Auto-validated before run",
                     font=("JetBrains Mono", 10),
                     text_color=theme.TEXT_DIM
                     ).pack(anchor="w", pady=(2, 0))

        stats = ctk.CTkFrame(card, fg_color="transparent")
        stats.pack(fill="x", padx=14, pady=(8, 6))
        stats.grid_columnconfigure(0, weight=1, uniform="s")
        stats.grid_columnconfigure(1, weight=1, uniform="s")
        stats.grid_columnconfigure(2, weight=1, uniform="s")
        self._stat_capacity = V2Stat(stats, "Capacity", "—", "B", "ok")
        self._stat_capacity.grid(row=0, column=0, sticky="ew", padx=2)
        self._stat_required = V2Stat(stats, "Required", "—", "B", "warn")
        self._stat_required.grid(row=0, column=1, sticky="ew", padx=2)
        self._stat_margin = V2Stat(stats, "Margin", "—", "%", "ok")
        self._stat_margin.grid(row=0, column=2, sticky="ew", padx=2)

        kv_wrap = ctk.CTkFrame(card, fg_color="transparent")
        kv_wrap.pack(fill="x", padx=14, pady=(6, 14))
        self._kv_cover = V2KV(kv_wrap, "Cover", "—")
        self._kv_cover.pack(fill="x", pady=2)
        self._kv_payload = V2KV(kv_wrap, "Payload", "—")
        self._kv_payload.pack(fill="x", pady=2)
        self._kv_algo = V2KV(kv_wrap, "Algorithm", "LSB · 1-bit", accent=True)
        self._kv_algo.pack(fill="x", pady=2)
        V2KV(kv_wrap, "KDF", "PBKDF2 · 480K").pack(fill="x", pady=2)
        V2KV(kv_wrap, "Cipher", "Fernet (AES-128)").pack(fill="x", pady=2)
        self._kv_output = V2KV(kv_wrap, "Output", "—")
        self._kv_output.pack(fill="x", pady=2)
        return card

    def _build_payload_diagram_card(self, parent) -> V2Card:
        card = V2Card(parent)
        wrap = ctk.CTkFrame(card, fg_color="transparent")
        wrap.pack(fill="x", padx=14, pady=14)
        self._diagram = PayloadDiagram(wrap, payload_bytes=2048)
        self._diagram.pack(fill="x")
        return card

    def _build_capacity_card(self, parent) -> V2Card:
        card = V2Card(parent)
        wrap = ctk.CTkFrame(card, fg_color="transparent")
        wrap.pack(fill="x", padx=14, pady=14)
        self._capacity = CapacityBreakdown(wrap)
        self._capacity.pack(fill="x")
        return card

    def _build_action_card(self, parent) -> V2Card:
        card = V2Card(parent, fg_color=theme.BG_3)
        wrap = ctk.CTkFrame(card, fg_color="transparent")
        wrap.pack(fill="x", padx=14, pady=14)

        self._mismatch = ctk.CTkFrame(
            wrap, fg_color="#2C0A10", border_width=1,
            border_color="#6A1828", corner_radius=4)
        # shown only when password mismatch
        ctk.CTkLabel(self._mismatch, text="",
                      image=icon("warn", 12, theme.ERR), width=14
                      ).pack(side="left", padx=(10, 6), pady=8)
        ctk.CTkLabel(self._mismatch,
                      text="Passphrase and confirmation do not match.",
                      font=("Segoe UI", 11),
                      text_color="#FF8A95"
                      ).pack(side="left", pady=8)

        self._run_btn = V2Button(wrap, "Begin encryption",
                                   variant="primary", icon_name="play",
                                   size="lg", command=self._run)
        self._run_btn.pack(fill="x", pady=(0, 8))

        row = ctk.CTkFrame(wrap, fg_color="transparent")
        row.pack(fill="x")
        self._export_btn = V2Button(row, "Export stego",
                                      variant="secondary", icon_name="download",
                                      command=self._export)
        self._export_btn.pack(side="left", fill="x", expand=True, padx=(0, 6))
        V2Button(row, "Advanced", variant="ghost", icon_name="cog"
                  ).pack(side="left")
        return card

    # ── handlers ─────────────────────────────────────────────────────────────
    def _on_cover(self, path: str):
        try:
            info = get_image_info(path)
        except Exception as exc:
            messagebox.showerror("Invalid image", str(exc))
            return
        self._cover_path = path
        self._cover_info = info
        self._preview.load(path,
                            dims=(info["width"], info["height"]),
                            mode=info.get("mode", "RGB"))
        self._cover_dz.set_meta(
            f"{info['width']}×{info['height']} · {info.get('mode','RGB')}  ·  "
            f"{theme.fmt_bytes(info['capacity_bytes'])} cap")
        # Feed real cover pixels into the forensic visualizers.
        try:
            from PIL import Image as _PI
            cover_img = _PI.open(path)
            cover_img.load()
            self._lsb.set_cover_sample(cover_img)
            self._hist.set_cover(cover_img)
        except Exception:
            pass
        self._log(f"Cover loaded · {os.path.basename(path)} · "
                   f"{theme.fmt_bytes(info['capacity_bytes'])} capacity",
                   "info")
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

        # Inspector stats
        if cap:
            self._stat_capacity.set(theme.fmt_bytes(cap).split()[0],
                                      theme.fmt_bytes(cap).split()[-1],
                                      "ok")
        else:
            self._stat_capacity.set("—", "B", "ok")
        if raw:
            self._stat_required.set(theme.fmt_bytes(enc).split()[0],
                                      theme.fmt_bytes(enc).split()[-1],
                                      "warn" if enc < cap else "crit")
        else:
            self._stat_required.set("—", "B", "warn")
        if cap and raw:
            margin = max(0.0, (1 - enc / cap) * 100)
            self._stat_margin.set(f"{margin:.1f}", "%",
                                    "ok" if margin > 5 else "crit")
        else:
            self._stat_margin.set("—", "%", "ok")

        # KV
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
                f"{os.path.basename(self._payload_path)} · {theme.fmt_bytes(raw)}")
        else:
            self._kv_payload.set("—")
        self._kv_algo.set(self._algo_seg.active)
        if self._cover_path and not self._stego_out:
            stem = os.path.splitext(os.path.basename(self._cover_path))[0]
            self._kv_output.set(f"{stem}_stego.png")
        elif self._stego_out:
            self._kv_output.set(os.path.basename(self._stego_out))

        # Capacity / payload diagram
        self._capacity.set(enc, cap)
        self._diagram.set_payload_bytes(max(64, enc))

        # Mismatch banner
        if self._pw_var.get() and self._pw2_var.get() and \
                self._pw_var.get() != self._pw2_var.get():
            self._mismatch.pack(fill="x", pady=(0, 8))
        else:
            self._mismatch.pack_forget()

        # Run button enable state
        ok = bool(self._cover_path
                   and raw
                   and self._pw_var.get()
                   and self._pw_var.get() == self._pw2_var.get()
                   and (not cap or enc <= cap))
        if self._running:
            self._run_btn.configure(state="normal", text="Abort operation")
        else:
            self._run_btn.configure(
                state="normal" if ok else "disabled",
                text=("Reset & run again" if self._complete
                       else "Begin encryption"))
        self._export_btn.configure(
            state="normal" if self._complete else "disabled")

    # ── encode run ───────────────────────────────────────────────────────────
    def _run(self):
        if self._running:
            return  # abort not supported by core; ignore
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
        self._lsb.set_progress(0.0, True)
        self._preview.set_progress(0.0, True)
        self._hist.set_progress(0.0, True)
        self._status_badge.set("RUNNING", "warn")
        self._refresh()

        self._log(f"▶ Begin encryption · {label}", "accent")
        self._log("Derive key: PBKDF2-HMAC-SHA256 · 480,000 iters · 16B salt",
                   "info")
        self._log("Encrypt payload: Fernet (AES-128-CBC + HMAC-SHA256)",
                   "info")

        run_in_thread(self, fn,
                       on_progress=self._on_progress,
                       on_done=self._on_done,
                       on_error=self._on_error)

    def _on_progress(self, p: float):
        self._prog.set(p)
        total_bits = max(1, self._payload_size() * 8)
        bits = int(p * total_bits)
        self._prog_lbl.configure(
            text=f"{p*100:.1f}%  ·  {bits:,} / {total_bits:,} bits")
        self._lsb.set_progress(p, True)
        self._preview.set_progress(p, True)
        self._hist.set_progress(p, True)
        self._diagram.set_progress(p, True)

    def _on_done(self, stego_img):
        self._running = False
        self._complete = True
        self._prog.set(1.0, color=theme.OK)
        self._lsb.set_progress(1.0, False)
        self._preview.set_progress(1.0, False)
        self._hist.set_stego(stego_img)
        self._hist.set_progress(1.0, False)
        self._diagram.set_progress(1.0, False)
        self._status_badge.set("STEGO READY", "ok")
        self._log("✓ Embedded payload across R/G/B · stego ready", "ok")
        self._pending_image = stego_img
        self._refresh()

    def _on_error(self, exc: BaseException):
        self._running = False
        self._complete = False
        self._prog.reset()
        self._lsb.set_progress(0.0, False)
        self._preview.set_progress(0.0, False)
        self._hist.set_progress(0.0, False)
        self._status_badge.set("FAILED", "crit")
        self._log(f"✗ Encryption failed · {exc}", "crit")
        messagebox.showerror("Encryption failed", str(exc))
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
            messagebox.showerror("Save failed", str(exc))
            return
        self._stego_out = path
        self._kv_output.set(os.path.basename(path))
        self._log(f"Stego saved → {path}", "ok")

    def _reset_run(self):
        self._complete = False
        self._stego_out = None
        self._pending_image = None
        self._prog.reset()
        self._lsb.set_progress(0.0, False)
        self._preview.set_progress(0.0, False)
        self._hist.set_progress(0.0, False)
        self._status_badge.set("IDLE", "neutral")
        self._prog_lbl.configure(text="0.0%  ·  0 bits")
        self._refresh()
