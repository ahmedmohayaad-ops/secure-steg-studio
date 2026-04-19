# steg_studio/gui/encrypt_panel.py
"""Simplified Encrypt workspace.

Single column: inputs → BytePeek (1-pixel before/after) → summary →
action card. Forensic dashboards live in the Inspector tab.
"""
from __future__ import annotations

import datetime as _dt
import os
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image as _PI

from steg_studio.core import (
    check_magic, encode_text, encode_file, encode_audio,
    get_image_info, estimate_encrypted_size,
)

from . import theme
from .assets import icon
from .components import (
    V2Badge,
    V2Button,
    V2Card,
    V2DropZone,
    V2KV,
    V2ProgressBar,
    V2Segmented,
    V2VoiceCard,
    show_toast,
)
from .workers import run_in_thread


class EncryptPanel(ctk.CTkFrame):
    def __init__(self, master, *, log=None, on_status=None,
                 on_inspect=None, **kwargs):
        kwargs.setdefault("fg_color", theme.BG_1)
        super().__init__(master, **kwargs)
        self._log = log or (lambda *_a, **_k: None)
        self._on_status = on_status or (lambda *_a, **_k: None)
        self._on_inspect = on_inspect or (lambda _state: None)

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
        self._last_preview_size: int = -1

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

        # Passwords row
        row2 = ctk.CTkFrame(card, fg_color="transparent")
        row2.pack(fill="x", padx=theme.PAD_MD, pady=(0, theme.PAD_MD))
        row2.grid_columnconfigure(0, weight=1, uniform="r2")
        row2.grid_columnconfigure(1, weight=1, uniform="r2")

        p1 = ctk.CTkFrame(row2, fg_color="transparent")
        p1.grid(row=0, column=0, sticky="ew", padx=(0, theme.PAD_SM))
        ctk.CTkLabel(p1, text="PASSPHRASE", font=theme.LABEL,
                     text_color=theme.TEXT_DIM, anchor="w").pack(
            anchor="w", pady=(0, theme.PAD_XS))
        self._pw_var = ctk.StringVar()
        self._pw_var.trace_add("write", lambda *_: self._refresh())
        self._pw = ctk.CTkEntry(
            p1, textvariable=self._pw_var, show="●", height=36,
            fg_color=theme.BG_4, border_color=theme.STROKE_HI,
            border_width=1, text_color=theme.TEXT_HI,
            font=theme.MONO, placeholder_text="min. 6 chars",
            corner_radius=theme.RADIUS_SM)
        self._pw.pack(fill="x")

        p2 = ctk.CTkFrame(row2, fg_color="transparent")
        p2.grid(row=0, column=1, sticky="ew", padx=(theme.PAD_SM, 0))
        ctk.CTkLabel(p2, text="CONFIRM", font=theme.LABEL,
                     text_color=theme.TEXT_DIM, anchor="w").pack(
            anchor="w", pady=(0, theme.PAD_XS))
        self._pw2_var = ctk.StringVar()
        self._pw2_var.trace_add("write", lambda *_: self._refresh())
        self._pw2 = ctk.CTkEntry(
            p2, textvariable=self._pw2_var, show="●", height=36,
            fg_color=theme.BG_4, border_color=theme.STROKE_HI,
            border_width=1, text_color=theme.TEXT_HI,
            font=theme.MONO, placeholder_text="re-enter",
            corner_radius=theme.RADIUS_SM)
        self._pw2.pack(fill="x")

        return card

    def _build_summary_card(self, parent) -> V2Card:
        card = V2Card(parent)
        h = ctk.CTkFrame(card, fg_color="transparent")
        h.pack(fill="x", padx=theme.PAD_MD, pady=(theme.PAD_MD,
                                                  theme.PAD_SM))
        ctk.CTkLabel(h, text="Summary", font=theme.H3,
                     text_color=theme.TEXT_HI).pack(side="left")
        self._fit_badge = V2Badge(h, "—", "neutral")
        self._fit_badge.pack(side="right")

        kv_wrap = ctk.CTkFrame(card, fg_color="transparent")
        kv_wrap.pack(fill="x", padx=theme.PAD_MD, pady=(0, theme.PAD_MD))
        self._kv_cover = V2KV(kv_wrap, "Cover", "—")
        self._kv_cover.pack(fill="x", pady=2)
        self._kv_payload = V2KV(kv_wrap, "Payload", "—")
        self._kv_payload.pack(fill="x", pady=2)
        self._kv_output = V2KV(kv_wrap, "Output", "—")
        self._kv_output.pack(fill="x", pady=2)
        return card

    def _build_action_card(self, parent) -> V2Card:
        card = V2Card(parent, fg_color=theme.BG_3)
        wrap = ctk.CTkFrame(card, fg_color="transparent")
        wrap.pack(fill="x", padx=theme.PAD_MD, pady=theme.PAD_MD)

        self._mismatch = ctk.CTkFrame(
            wrap, fg_color="#2C0A10", border_width=1,
            border_color="#6A1828", corner_radius=theme.RADIUS_SM)
        ctk.CTkLabel(self._mismatch, text="",
                     image=icon("warn", 12, theme.ERR), width=14
                     ).pack(side="left", padx=(10, 6), pady=8)
        ctk.CTkLabel(self._mismatch,
                     text="Passphrase and confirmation do not match.",
                     font=theme.BODY,
                     text_color="#FF8A95"
                     ).pack(side="left", pady=8)

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
    def _on_cover(self, path: str):
        try:
            info = get_image_info(path)
        except Exception as exc:
            messagebox.showerror("Invalid image", str(exc))
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
        except Exception:
            pass
        self._log(f"Cover loaded · {os.path.basename(path)} · "
                  f"{theme.fmt_bytes(info['capacity_bytes'])} capacity",
                  "info")
        try:
            encrypted = check_magic(path)
        except Exception:
            encrypted = None
        self._push_preview(encrypted=encrypted)
        try:
            self._on_inspect({
                "kind": "narrate",
                "msg": (f"Loaded {os.path.basename(path)} · "
                        f"{info['width']}×{info['height']} · "
                        f"capacity {theme.fmt_bytes(info['capacity_bytes'])} · "
                        f"encrypted={'yes' if encrypted else 'no'}"),
                "tone": "info",
            })
        except Exception:
            pass
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

    def _push_capacity_only(self):
        if self._cover_info is None:
            return
        try:
            self._on_inspect({
                "kind": "update_capacity",
                "payload_bytes": self._payload_size(),
                "raw_bytes": self._payload_size(),
                "encrypted_bytes": (estimate_encrypted_size(self._payload_size())
                                    if self._payload_size() else 0),
                "capacity_bytes": self._cover_info["capacity_bytes"],
            })
        except Exception:
            pass

    def _push_preview(self, *, encrypted: bool | None = None):
        if self._cover_img is None:
            return
        label = os.path.basename(self._cover_path or "cover")
        state = {
            "mode": "encrypt",
            "preview": True,
            "cover_image": self._cover_img,
            "payload_bytes": self._payload_size(),
            "label": label,
        }
        if encrypted is not None:
            state["encrypted"] = encrypted
        try:
            self._on_inspect(state)
        except Exception:
            pass

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

        if self._pw_var.get() and self._pw2_var.get() and \
                self._pw_var.get() != self._pw2_var.get():
            self._mismatch.pack(fill="x", pady=(0, theme.PAD_SM))
        else:
            self._mismatch.pack_forget()

        ok = bool(self._cover_path
                  and raw
                  and self._pw_var.get()
                  and self._pw_var.get() == self._pw2_var.get()
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

        # Keep Inspector capacity bars in sync with the payload size
        # while the user types / picks files (legacy behavior) — but only
        # push when the payload size actually changed, to avoid re-rendering
        # the canvas thumbnail on every keystroke.
        if self._cover_img is not None and not self._running:
            cur = self._payload_size()
            if cur != self._last_preview_size:
                self._last_preview_size = cur
                self._push_capacity_only()

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
        self._last_stage = 0  # 0=idle,1=kdf,2=cipher,3=mac,4=embed
        self._prog.reset()
        self._refresh()

        self._log(f"▶ Begin encryption · {label}", "accent")
        self._narrate("reset", "")
        self._narrate(
            f"Starting encryption · {label} · "
            f"cover {os.path.basename(self._cover_path or '')}", "accent")
        run_in_thread(self, fn,
                      on_progress=self._on_progress,
                      on_done=self._on_done,
                      on_error=self._on_error)

    def _narrate(self, msg: str, tone: str = "info"):
        try:
            if msg == "reset":
                self._on_inspect({"kind": "reset_narration"})
            else:
                self._on_inspect({"kind": "narrate", "msg": msg, "tone": tone})
        except Exception:
            pass

    def _on_progress(self, p: float):
        self._prog.set(p)
        # Derive narration stages from progress breakpoints so the user
        # sees the crypto pipeline advance without threading events from core.
        stage = self._last_stage
        if p > 0 and stage < 1:
            self._narrate(
                "Deriving 128-bit key · PBKDF2-HMAC-SHA256 · "
                "16 B salt · 480,000 iterations", "info")
            self._last_stage = 1
        if p >= 0.05 and stage < 2:
            self._narrate(
                "Encrypting payload · AES-128-CBC · 16 B IV (nonce)",
                "info")
            self._last_stage = 2
        if p >= 0.15 and stage < 3:
            self._narrate(
                "Authenticating · HMAC-SHA256 · 32 B tag",
                "info")
            self._last_stage = 3
        if p >= 0.20 and stage < 4:
            cap = (self._cover_info or {}).get("capacity_bytes", 0)
            raw = estimate_encrypted_size(self._payload_size()) \
                if self._payload_size() else 0
            pct = (raw / cap * 100) if cap else 0
            self._narrate(
                f"Embedding {theme.fmt_bytes(raw)} into R/G/B LSBs · "
                f"{pct:.1f}% of capacity", "info")
            self._last_stage = 4

    def _on_done(self, stego_img):
        self._running = False
        self._complete = True
        self._prog.set(1.0, color=theme.OK)
        self._pending_image = stego_img
        self._narrate("Done · stego ready", "ok")
        self._log("✓ Embedded payload across R/G/B · stego ready", "ok")
        try:
            show_toast(self.winfo_toplevel(), "Stego ready", kind="ok")
        except Exception:
            pass
        # Push state to Inspector tab.
        self._push_inspector(stego_img)
        self._refresh()

    def _push_inspector(self, stego_img):
        if self._cover_img is None:
            return
        label = (f"{os.path.basename(self._cover_path or 'cover')} → "
                 f"stego · {theme.fmt_bytes(self._payload_size())}")
        state = {
            "mode": "encrypt",
            "cover_image": self._cover_img,
            "stego_image": stego_img,
            "payload_bytes": self._payload_size(),
            "label": label,
            "timestamp": _dt.datetime.now().strftime("%H:%M:%S"),
        }
        try:
            self._on_inspect(state)
        except Exception:
            pass

    def _on_error(self, exc: BaseException):
        self._running = False
        self._complete = False
        self._prog.reset()
        self._narrate(f"Encryption failed · {exc}", "crit")
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
        self._push_preview()
        self._refresh()
