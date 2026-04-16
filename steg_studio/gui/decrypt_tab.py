# steg_studio/gui/decrypt_tab.py
"""
Decrypt tab — with progress bar, spinner, history integration, SVG icons.
"""
from __future__ import annotations

import os
import threading
import tempfile
import wave

try:
    import pyaudio
    _PYAUDIO_OK = True
except ImportError:
    pyaudio = None       # type: ignore[assignment]
    _PYAUDIO_OK = False

import customtkinter as ctk
from tkinter import filedialog, messagebox

from steg_studio.core        import decode, get_image_info, check_magic
from steg_studio.gui.widgets import (
    ImageInfoPanel, SectionHeader, Card,
    ProgressBar, Spinner,
    get_icon, add_history,
    ACCENT, ACCENT_DIM, BORDER,
    FONT_MONO, FONT_MONO_S,
)
from steg_studio.gui.encrypt_tab import _btn


class DecryptTab(ctk.CTkFrame):
    def __init__(self, master, status_bar, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)
        self._status     = status_bar
        self._image_path: str | None = None
        self._result: dict | None    = None
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Left column
        left = ctk.CTkFrame(self, width=264, fg_color="transparent")
        left.pack(side="left", fill="y", padx=(0, 8))
        left.pack_propagate(False)

        SectionHeader(left, "Stego Image").pack(anchor="w", pady=(0, 6))
        self._img_panel = ImageInfoPanel(left, show_info=False)
        self._img_panel.pack(fill="x")

        btn_row = ctk.CTkFrame(left, fg_color="transparent")
        btn_row.pack(fill="x", pady=(8, 0))
        _btn(btn_row, " Select Image", self._select_image, primary=True, icon="image").pack(side="left", padx=(0, 4))
        _btn(btn_row, "Clear", self._clear_image, icon="clear", width=70).pack(side="left")

        # Detection badge
        self._detect_var = ctk.StringVar(value="")
        self._detect_lbl = ctk.CTkLabel(left, textvariable=self._detect_var,
                                         font=("Segoe UI", 10, "bold"),
                                         corner_radius=6, fg_color="transparent",
                                         text_color=("gray45", "gray55"))
        self._detect_lbl.pack(anchor="w", pady=(8, 0))

        # Right column
        right = ctk.CTkFrame(self, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True)

        # Security card
        SectionHeader(right, "Security").pack(anchor="w", pady=(0, 6))
        sec_card = Card(right)
        sec_card.pack(fill="x")
        pw_inner = ctk.CTkFrame(sec_card, fg_color="transparent")
        pw_inner.pack(fill="x", padx=14, pady=12)
        ctk.CTkLabel(pw_inner, text="PASSWORD", width=90, anchor="w",
                     font=("Segoe UI", 9, "bold"),
                     text_color=("gray45", "gray55")).pack(side="left")
        self._pw_var = ctk.StringVar()
        ctk.CTkEntry(pw_inner, textvariable=self._pw_var, show="●",
                     placeholder_text="Enter decryption password…",
                     border_color=BORDER, fg_color=("gray88", "#2A2F3A"),
                     text_color=("gray10", "gray90")).pack(side="left", fill="x", expand=True, padx=(6, 0))

        # Action row
        act_row = ctk.CTkFrame(right, fg_color="transparent")
        act_row.pack(fill="x", pady=(10, 0))
        _btn(act_row, " Preview Info", self._preview, icon="image", width=130).pack(side="left", padx=(0, 6))
        _btn(act_row, " Decrypt", self._decrypt, primary=True, icon="lock", width=110).pack(side="left")

        # Progress row
        prog_row = ctk.CTkFrame(right, fg_color="transparent")
        prog_row.pack(fill="x", pady=(8, 0))
        self._spinner  = Spinner(prog_row)
        self._spinner.pack(side="left")
        self._progress = ProgressBar(prog_row)
        self._progress.pack(side="left", fill="x", expand=True, padx=(6, 0))

        # Output section
        SectionHeader(right, "Extracted Payload").pack(anchor="w", pady=(14, 6))
        out_card = Card(right)
        out_card.pack(fill="both", expand=True)

        self._preview_var = ctk.StringVar(value="")
        ctk.CTkLabel(out_card, textvariable=self._preview_var,
                     font=FONT_MONO_S, justify="left", anchor="w",
                     text_color=("gray45", "gray55")).pack(anchor="w", padx=14, pady=(10, 0))

        self._out_box = ctk.CTkTextbox(out_card, font=FONT_MONO,
                                        fg_color=("gray88", "#1A1D23"),
                                        border_color=BORDER, border_width=1,
                                        corner_radius=6, text_color=("gray10", "gray88"),
                                        state="disabled")
        self._out_box.pack(fill="both", expand=True, padx=14, pady=(6, 8))

        # Action strip
        action_strip = ctk.CTkFrame(out_card, fg_color="transparent")
        action_strip.pack(fill="x", padx=14, pady=(0, 12))
        self._play_btn      = _btn(action_strip, " Play Audio",   self._play_audio, icon="play",   state="disabled", width=115)
        self._save_audio_btn = _btn(action_strip, " Save Audio",  self._save_audio, icon="save",   state="disabled", width=115)
        self._save_file_btn  = _btn(action_strip, " Save File",   self._save_file,  icon="save",   state="disabled", width=115)
        self._play_btn.pack(side="left", padx=(0, 4))
        self._save_audio_btn.pack(side="left", padx=(0, 4))
        self._save_file_btn.pack(side="left")

    # ── Image selection ───────────────────────────────────────────────────────

    def _select_image(self):
        path = filedialog.askopenfilename(
            title="Select stego image",
            filetypes=[("Images", "*.png *.bmp *.tiff"), ("All", "*.*")],
        )
        if not path:
            return
        self._image_path = path
        self._result     = None
        self._preview_var.set("")
        self._detect_var.set("")
        self._reset_output()
        info = get_image_info(path)
        self._img_panel.set_image(path, info["capacity_bytes"])
        self._status.set("Image loaded — scanning for hidden data…", "info")
        self._spinner.start()
        threading.Thread(target=lambda: (
            check_magic(path),
            self.after(0, lambda hd=check_magic(path): self._on_magic_checked(hd))
        ), daemon=True).start()

    def _on_magic_checked(self, has_data: bool):
        self._spinner.stop()
        if has_data:
            self._detect_var.set("✅  Hidden data detected")
            self._detect_lbl.configure(text_color=(ACCENT_DIM, ACCENT))
            self._set_out_box("Hidden data found.\nEnter the password above and click Decrypt.")
            self._status.set("Hidden data detected", "ok")
        else:
            self._detect_var.set("○  No hidden data found")
            self._detect_lbl.configure(text_color=("gray50", "gray50"))
            self._set_out_box("No hidden data detected in this image.")
            self._status.set("No hidden data found", "warn")

    def _clear_image(self):
        self._image_path = None
        self._result     = None
        self._preview_var.set("")
        self._detect_var.set("")
        self._reset_output()
        self._img_panel.clear()
        self._status.set("Ready", "ready")

    # ── Preview ───────────────────────────────────────────────────────────────

    def _preview(self):
        if not self._image_path:
            messagebox.showwarning("No Image", "Please select a stego image first.")
            return
        size = os.path.getsize(self._image_path)
        self._preview_var.set(
            f"File  :  {os.path.basename(self._image_path)}   │   Size  :  {size:,} bytes"
        )
        self._status.set("Preview shown", "info")

    # ── Decrypt ───────────────────────────────────────────────────────────────

    def _decrypt(self):
        if not self._image_path:
            messagebox.showwarning("No Image", "Please select a stego image first.")
            return
        password = self._pw_var.get()
        if not password:
            messagebox.showwarning("No Password", "Please enter the decryption password.")
            return

        self._status.set("Decrypting…", "warn")
        self._reset_output()
        self._spinner.start()
        # Do NOT call self._progress.start() — set_fraction() drives the bar now
        self.update()

        def _progress_cb(frac: float):
            self.after(0, lambda f=frac: self._progress.set_fraction(f))

        def _work():
            try:
                result = decode(self._image_path, password,
                                progress_callback=_progress_cb)
                self._result = result
                add_history("Decrypt", os.path.basename(self._image_path), ok=True)
                self.after(0, lambda: (self._stop_op(), self._show_result()))
            except ValueError as exc:
                msg = str(exc)
                ok  = False
                add_history("Decrypt", msg[:50], ok=False)
                if "No hidden data" in msg:
                    self.after(0, lambda: (
                        self._stop_op(),
                        self._status.set("No hidden data found", "warn"),
                        self._set_out_box("No hidden data found."),
                    ))
                elif "Decryption failed" in msg or "wrong password" in msg.lower():
                    self.after(0, lambda: (
                        self._stop_op(),
                        self._status.set("Decryption failed — invalid password", "error"),
                        self._set_out_box("Decryption failed — incorrect password."),
                    ))
                else:
                    self.after(0, lambda m=msg: (
                        self._stop_op(),
                        self._status.set(f"Corrupted data: {m}", "error"),
                        messagebox.showerror("Corrupted Data", m),
                    ))
            except Exception as exc:
                add_history("Decrypt", str(exc)[:50], ok=False)
                self.after(0, lambda e=exc: (
                    self._stop_op(),
                    self._status.set(f"Unexpected error: {e}", "error"),
                    messagebox.showerror("Unexpected Error", str(e)),
                ))

        threading.Thread(target=_work, daemon=True).start()

    def _stop_op(self):
        self._spinner.stop()
        self._progress.stop()

    # ── Output display ────────────────────────────────────────────────────────

    def _set_out_box(self, text: str):
        self._out_box.configure(state="normal")
        self._out_box.delete("1.0", "end")
        self._out_box.insert("end", text)
        self._out_box.configure(state="disabled")

    def _show_result(self):
        if not self._result:
            return
        t = self._result["type"]
        self._status.set(f"Decryption complete ✓ — type: {t}", "ok")
        if t == "text":
            self._set_out_box(self._result["data"].decode("utf-8"))
        elif t == "file":
            meta = self._result["meta"]
            self._set_out_box(
                f"[File payload]\nFilename  :  {meta.get('filename','extracted_file')}\n"
                f"Size      :  {len(self._result['data']):,} bytes"
            )
            self._save_file_btn.configure(state="normal")
        elif t == "audio":
            self._set_out_box(f"[Audio payload]\nSize  :  {len(self._result['data']):,} bytes")
            self._play_btn.configure(state="normal")
            self._save_audio_btn.configure(state="normal")

    def _reset_output(self):
        self._out_box.configure(state="normal")
        self._out_box.delete("1.0", "end")
        self._out_box.configure(state="disabled")
        self._play_btn.configure(state="disabled")
        self._save_audio_btn.configure(state="disabled")
        self._save_file_btn.configure(state="disabled")

    # ── Save / play ───────────────────────────────────────────────────────────

    def _save_file(self):
        if not self._result or self._result["type"] != "file":
            return
        meta = self._result["meta"]
        path = filedialog.asksaveasfilename(
            title="Save extracted file",
            initialfile=meta.get("filename", "extracted_file"),
            filetypes=[(f"*.{meta.get('ext','*')}", f"*.{meta.get('ext','*')}"), ("All", "*.*")],
        )
        if path:
            with open(path, "wb") as fh:
                fh.write(self._result["data"])
            self._status.set(f"File saved — {os.path.basename(path)}", "ok")

    def _save_audio(self):
        if not self._result or self._result["type"] != "audio":
            return
        ext  = self._result["meta"].get("ext", "wav")
        path = filedialog.asksaveasfilename(
            title="Save audio", defaultextension=f".{ext}",
            filetypes=[(ext.upper(), f"*.{ext}"), ("All", "*.*")],
        )
        if path:
            with open(path, "wb") as fh:
                fh.write(self._result["data"])
            self._status.set(f"Audio saved — {os.path.basename(path)}", "ok")

    def _play_audio(self):
        if not self._result or self._result["type"] != "audio":
            return
        if not _PYAUDIO_OK:
            messagebox.showerror("PyAudio Unavailable",
                                 "Install PyAudio to play audio.\nYou can still save the file.")
            return
        audio_bytes = self._result["data"]
        def _play():
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(audio_bytes); tmp = f.name
            pa = pyaudio.PyAudio()
            with wave.open(tmp, "rb") as wf:
                stream = pa.open(format=pa.get_format_from_width(wf.getsampwidth()),
                                 channels=wf.getnchannels(), rate=wf.getframerate(), output=True)
                data = wf.readframes(1024)
                while data:
                    stream.write(data); data = wf.readframes(1024)
                stream.stop_stream(); stream.close()
            pa.terminate(); os.unlink(tmp)
        threading.Thread(target=_play, daemon=True).start()
