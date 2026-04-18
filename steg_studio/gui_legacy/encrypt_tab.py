# steg_studio/gui/encrypt_tab.py
"""
Encrypt tab — Text / File / Audio sub-tabs.
New: progress bar, spinner, capacity warning, batch mode, before/after preview,
     animated waveform, SVG icons.
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

from steg_studio.core    import encode_text, encode_file, encode_audio
from steg_studio.core    import get_image_info, estimate_encrypted_size
from steg_studio.gui.widgets import (
    ImageInfoPanel, BeforeAfterPreview, SectionHeader, Card,
    ProgressBar, Spinner, CapacityWarning, WaveformCanvas,
    get_icon, add_history,
    ACCENT, ACCENT_DIM, BORDER,
    FONT_MONO, FONT_MONO_S, FONT_SMALL,
)


# ── Audio recorder ────────────────────────────────────────────────────────────

class _AudioRecorder:
    RATE, CHANNELS, CHUNK, FORMAT = 44100, 1, 1024, (pyaudio.paInt16 if _PYAUDIO_OK else 8)

    def __init__(self):
        self._frames: list[bytes] = []
        self._recording = False
        self._pa = self._stream = self._thread = None
        self.duration = 0.0

    def start(self):
        self._frames     = []
        self._recording  = True
        self.duration    = 0.0
        import time; self._t0 = time.time()
        self._pa     = pyaudio.PyAudio()
        self._stream = self._pa.open(format=self.FORMAT, channels=self.CHANNELS,
                                     rate=self.RATE, input=True,
                                     frames_per_buffer=self.CHUNK)
        self._thread = threading.Thread(target=self._record, daemon=True)
        self._thread.start()

    def stop(self):
        self._recording = False
        if self._thread: self._thread.join(timeout=2)
        if self._stream: self._stream.stop_stream(); self._stream.close()
        if self._pa:     self._pa.terminate()

    def get_wav_bytes(self) -> bytes:
        import io
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(self.CHANNELS)
            wf.setsampwidth(pyaudio.PyAudio().get_sample_size(self.FORMAT))
            wf.setframerate(self.RATE)
            wf.writeframes(b"".join(self._frames))
        return buf.getvalue()

    def _record(self):
        import time
        while self._recording:
            self._frames.append(self._stream.read(self.CHUNK, exception_on_overflow=False))
            self.duration = time.time() - self._t0


# ── Button factory ────────────────────────────────────────────────────────────

def _btn(parent, text: str, cmd, *, primary=False, danger=False,
         icon: str = None, width: int = 100, state="normal") -> ctk.CTkButton:
    if primary:
        fg, hover, txt = (ACCENT_DIM, ACCENT), ("#005C4B", ACCENT_DIM), ("white", "#001A14")
    elif danger:
        fg, hover, txt = ("#C62828", "#EF5350"), ("#B71C1C", "#C62828"), ("white", "white")
    else:
        fg, hover, txt = ("gray78", "#2A2F3A"), ("gray70", "#343B48"), ("gray15", "gray80")

    kw = {}
    if icon:
        img = get_icon(icon, size=14, color="#001A14" if primary else (ACCENT if not danger else "white"))
        if img:
            kw["image"] = img
            kw["compound"] = "left"

    return ctk.CTkButton(parent, text=text, command=cmd, width=width, height=30,
                          font=("Segoe UI", 11), fg_color=fg, hover_color=hover,
                          text_color=txt, corner_radius=6, state=state, **kw)


# ── Encrypt Tab ───────────────────────────────────────────────────────────────

class EncryptTab(ctk.CTkFrame):
    def __init__(self, master, status_bar, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)
        self._status      = status_bar
        self._image_path: str | None  = None
        self._image_info: dict | None = None
        self._recorder    = _AudioRecorder()
        self._audio_bytes: bytes | None = None
        self._file_path: str | None   = None
        # Batch mode
        self._batch_paths: list[str]  = []
        self._batch_mode  = False
        self._last_out_path: str | None = None   # for before/after
        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        # Left column
        left = ctk.CTkFrame(self, width=264, fg_color="transparent")
        left.pack(side="left", fill="y", padx=(0, 8))
        left.pack_propagate(False)

        SectionHeader(left, "Cover Image").pack(anchor="w", pady=(0, 6))
        self._img_panel = ImageInfoPanel(left)
        self._img_panel.pack(fill="x")

        btn_row = ctk.CTkFrame(left, fg_color="transparent")
        btn_row.pack(fill="x", pady=(8, 0))
        _btn(btn_row, " Select Image", self._select_image, primary=True, icon="image").pack(side="left", padx=(0, 4))
        _btn(btn_row, "Clear", self._clear_image, icon="clear", width=70).pack(side="left")

        # Batch toggle
        batch_row = ctk.CTkFrame(left, fg_color="transparent")
        batch_row.pack(fill="x", pady=(6, 0))
        self._batch_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            batch_row, text="Batch mode", variable=self._batch_var,
            font=("Segoe UI", 11),
            text_color=("gray30", "gray70"),
            checkmark_color=ACCENT,
            fg_color=(ACCENT_DIM, ACCENT),
            command=self._toggle_batch,
        ).pack(side="left")

        # Batch list (hidden by default)
        self._batch_card = Card(left, fg_color=("gray88", "#22262F"))
        self._batch_lbl = ctk.CTkLabel(self._batch_card,
                                        text="No images selected",
                                        font=FONT_SMALL,
                                        text_color=("gray50", "gray55"))
        self._batch_lbl.pack(padx=10, pady=6)
        _btn(self._batch_card, " Add Images", self._batch_add, primary=True,
             icon="batch", width=130).pack(padx=10, pady=(0, 8))

        # Capacity warning (lives in left column, below image panel)
        self._cap_warn = CapacityWarning(left)
        self._cap_warn.pack(fill="x", pady=(8, 0))

        # Right column
        right = ctk.CTkFrame(self, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True)

        SectionHeader(right, "Payload").pack(anchor="w", pady=(0, 6))
        payload_card = Card(right)
        payload_card.pack(fill="both", expand=True)

        self._tabs = ctk.CTkTabview(
            payload_card, fg_color="transparent",
            segmented_button_fg_color=("gray82", "#22262F"),
            segmented_button_selected_color=(ACCENT, ACCENT),
            segmented_button_selected_hover_color=(ACCENT_DIM, ACCENT_DIM),
            segmented_button_unselected_color=("gray82", "#22262F"),
            segmented_button_unselected_hover_color=("gray75", "#2A2F3A"),
            text_color=("gray20", "gray80"),
        )
        self._tabs.pack(fill="both", expand=True, padx=10, pady=(6, 4))
        self._tabs.add("  Text  ")
        self._tabs.add("  File  ")
        self._tabs.add("  Audio  ")
        self._build_text_tab()
        self._build_file_tab()
        self._build_audio_tab()

        # Security card
        sec_row = ctk.CTkFrame(right, fg_color="transparent")
        sec_row.pack(fill="x", pady=(10, 0))
        SectionHeader(sec_row, "Security").pack(anchor="w", pady=(0, 6))
        sec_card = Card(sec_row)
        sec_card.pack(fill="x")
        pw_inner = ctk.CTkFrame(sec_card, fg_color="transparent")
        pw_inner.pack(fill="x", padx=14, pady=12)
        ctk.CTkLabel(pw_inner, text="PASSWORD", width=90, anchor="w",
                     font=("Segoe UI", 9, "bold"),
                     text_color=("gray45", "gray55")).pack(side="left")
        self._pw_var = ctk.StringVar()
        self._pw_entry = ctk.CTkEntry(pw_inner, textvariable=self._pw_var,
                                      show="●", placeholder_text="Enter encryption password…",
                                      border_color=BORDER, fg_color=("gray88", "#2A2F3A"),
                                      text_color=("gray10", "gray90"))
        self._pw_entry.pack(side="left", fill="x", expand=True, padx=(6, 0))

        # Progress bar + spinner row (hidden until operation starts)
        prog_row = ctk.CTkFrame(right, fg_color="transparent")
        prog_row.pack(fill="x", pady=(8, 0))
        self._spinner  = Spinner(prog_row)
        self._spinner.pack(side="left")
        self._progress = ProgressBar(prog_row)
        self._progress.pack(side="left", fill="x", expand=True, padx=(6, 0))
        self._op_lbl = ctk.CTkLabel(prog_row, text="", font=("Segoe UI", 10),
                                     text_color=("gray45", "gray55"))
        self._op_lbl.pack(side="right", padx=(6, 0))

        # Bottom action row
        act_row = ctk.CTkFrame(right, fg_color="transparent")
        act_row.pack(fill="x", pady=(6, 0))

        self._embed_btn = ctk.CTkButton(
            act_row, text=" Embed & Save Image",
            command=self._embed, height=40,
            font=("Segoe UI", 13, "bold"),
            fg_color=(ACCENT_DIM, ACCENT), hover_color=("#005C4B", ACCENT_DIM),
            text_color=("white", "#001A14"), corner_radius=8,
        )
        embed_icon = get_icon("embed", size=16, color="#001A14")
        if embed_icon:
            self._embed_btn.configure(image=embed_icon, compound="left")
        self._embed_btn.pack(side="left", fill="x", expand=True)

        self._preview_btn = ctk.CTkButton(
            act_row, text=" Before/After",
            command=self._show_preview, width=120, height=40,
            font=("Segoe UI", 11),
            fg_color=("gray78", "#2A2F3A"), hover_color=("gray70", "#343B48"),
            text_color=("gray15", "gray80"), corner_radius=8,
            state="disabled",
        )
        img_icon = get_icon("image", size=14, color=ACCENT)
        if img_icon:
            self._preview_btn.configure(image=img_icon, compound="left")
        self._preview_btn.pack(side="left", padx=(6, 0))

    def _build_text_tab(self):
        tab = self._tabs.tab("  Text  ")
        ctk.CTkLabel(tab, text="MESSAGE", anchor="w",
                     font=("Segoe UI", 9, "bold"),
                     text_color=("gray45", "gray55")).pack(anchor="w", padx=4, pady=(4, 3))
        self._text_box = ctk.CTkTextbox(
            tab, font=FONT_MONO, fg_color=("gray88", "#1E222A"),
            border_color=BORDER, border_width=1, corner_radius=6,
            text_color=("gray10", "gray88"))
        self._text_box.pack(fill="both", expand=True, padx=4, pady=(0, 6))
        self._text_box.bind("<KeyRelease>", self._on_text_change)

    def _build_file_tab(self):
        tab = self._tabs.tab("  File  ")
        drop = Card(tab, fg_color=("gray85", "#1E222A"))
        drop.pack(fill="x", padx=4, pady=(4, 8))
        inner = ctk.CTkFrame(drop, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=12)
        _btn(inner, " Browse File…", self._select_file, primary=True, icon="file", width=130).pack(side="left", padx=(0, 8))
        _btn(inner, "Clear", self._clear_file, icon="clear", width=70).pack(side="left")
        self._file_info_var = ctk.StringVar(value="No file selected")
        ctk.CTkLabel(tab, textvariable=self._file_info_var, anchor="w",
                     font=FONT_MONO_S, text_color=("gray40", "gray60"),
                     justify="left").pack(anchor="w", padx=4)

    def _build_audio_tab(self):
        tab = self._tabs.tab("  Audio  ")

        if not _PYAUDIO_OK:
            ctk.CTkLabel(
                tab,
                text="Audio recording is unavailable.\n\nInstall PyAudio to enable this feature:\n  pip install pyaudio",
                font=("Segoe UI", 11), justify="center",
                text_color=("gray50", "gray55"),
            ).pack(expand=True, pady=40)
            # Create stub attributes so the rest of the code doesn't crash
            self._waveform  = type("_Stub", (), {"start_recording": lambda *a: None,
                                                   "stop_recording": lambda *a: None,
                                                   "clear": lambda *a: None})()
            self._rec_btn   = _btn(tab, " Record", lambda: None, primary=True, state="disabled", width=90)
            self._stop_btn  = _btn(tab, " Stop",   lambda: None, danger=True,  state="disabled", width=80)
            self._play_btn  = _btn(tab, " Play",   lambda: None, state="disabled", width=80)
            self._clr_btn   = _btn(tab, "Clear",   lambda: None, state="disabled", width=70)
            self._dur_var   = ctk.StringVar(value="Duration  :  —")
            return

        # Waveform display
        wave_frame = ctk.CTkFrame(tab, fg_color=("gray85", "#1E222A"), corner_radius=8)
        wave_frame.pack(fill="x", padx=4, pady=(4, 6))
        self._waveform = WaveformCanvas(wave_frame)
        self._waveform.pack(padx=10, pady=8)

        ctrl = Card(tab, fg_color=("gray85", "#1E222A"))
        ctrl.pack(fill="x", padx=4, pady=(0, 6))
        btn_row = ctk.CTkFrame(ctrl, fg_color="transparent")
        btn_row.pack(fill="x", padx=14, pady=10)

        self._rec_btn  = _btn(btn_row, " Record",  self._start_rec,  primary=True, icon="record",  width=90)
        self._stop_btn = _btn(btn_row, " Stop",    self._stop_rec,   danger=True,  icon="stop",    width=80, state="disabled")
        self._play_btn = _btn(btn_row, " Play",    self._play_audio, icon="play",  width=80, state="disabled")
        self._clr_btn  = _btn(btn_row, "Clear",    self._clear_audio, icon="clear", width=70, state="disabled")

        for b in (self._rec_btn, self._stop_btn, self._play_btn, self._clr_btn):
            b.pack(side="left", padx=(0, 4))

        self._dur_var = ctk.StringVar(value="Duration  :  —")
        ctk.CTkLabel(tab, textvariable=self._dur_var, font=FONT_MONO_S,
                     text_color=("gray40", "gray60")).pack(anchor="w", padx=4)

    # ── Batch mode ────────────────────────────────────────────────────────────

    def _toggle_batch(self):
        self._batch_mode = self._batch_var.get()
        if self._batch_mode:
            self._batch_card.pack(fill="x", pady=(8, 0))
        else:
            self._batch_card.pack_forget()
            self._batch_paths.clear()
            self._batch_lbl.configure(text="No images selected")

    def _batch_add(self):
        paths = filedialog.askopenfilenames(
            title="Select cover images for batch embed",
            filetypes=[("Images", "*.png *.bmp *.tiff *.tif"), ("All", "*.*")],
        )
        if paths:
            self._batch_paths = list(paths)
            self._batch_lbl.configure(text=f"{len(paths)} image(s) selected")
            self._status.set(f"Batch: {len(paths)} images loaded", "info")

    # ── Image selection ───────────────────────────────────────────────────────

    def _select_image(self):
        path = filedialog.askopenfilename(
            title="Select cover image",
            filetypes=[("Images", "*.png *.bmp *.tiff *.tif"), ("All", "*.*")],
        )
        if not path:
            return
        self._image_path = path
        info = get_image_info(path)
        self._image_info = info
        self._img_panel.set_image(path, info["capacity_bytes"])
        self._status.set(f"Image loaded — {info['capacity_bytes']:,} B capacity", "info")
        self._refresh_capacity()

    def _clear_image(self):
        self._image_path = None
        self._image_info = None
        self._img_panel.clear()
        self._cap_warn.check(0, 0)
        self._status.set("Ready", "ready")

    # ── Capacity ──────────────────────────────────────────────────────────────

    def _on_text_change(self, _=None):
        self._refresh_capacity()

    def _refresh_capacity(self):
        if not self._image_info:
            return
        cap      = self._image_info["capacity_bytes"]
        tab      = self._tabs.get().strip()
        raw_size = self._current_data_size(tab)
        enc_size = estimate_encrypted_size(raw_size) if raw_size > 0 else 0
        self._img_panel.update_data_size(raw_size, enc_size, cap)
        self._cap_warn.check(enc_size, cap)

    def _current_data_size(self, tab: str) -> int:
        if tab == "Text":
            return len(self._text_box.get("1.0", "end-1c").encode("utf-8"))
        if tab == "File" and self._file_path:
            return os.path.getsize(self._file_path)
        if tab == "Audio" and self._audio_bytes:
            return len(self._audio_bytes)
        return 0

    # ── File sub-tab ──────────────────────────────────────────────────────────

    def _select_file(self):
        path = filedialog.askopenfilename(title="Select file to embed")
        if not path:
            return
        self._file_path = path
        size = os.path.getsize(path)
        self._file_info_var.set(f"File  :  {os.path.basename(path)}\nSize  :  {size:,} bytes")
        self._refresh_capacity()
        self._status.set(f"File selected — {os.path.basename(path)}", "info")

    def _clear_file(self):
        self._file_path = None
        self._file_info_var.set("No file selected")
        self._refresh_capacity()

    # ── Audio sub-tab ─────────────────────────────────────────────────────────

    def _start_rec(self):
        if not _PYAUDIO_OK:
            messagebox.showerror("PyAudio Unavailable", "Install PyAudio to use audio recording.")
            return
        self._rec_btn.configure(state="disabled")
        self._stop_btn.configure(state="normal")
        self._waveform.start_recording()
        self._recorder.start()
        self._status.set("Recording…", "warn")
        self._update_dur()

    def _update_dur(self):
        if self._recorder._recording:
            self._dur_var.set(f"Duration  :  {self._recorder.duration:.1f} s")
            self.after(100, self._update_dur)

    def _stop_rec(self):
        self._recorder.stop()
        self._audio_bytes = self._recorder.get_wav_bytes()
        self._waveform.stop_recording(self._audio_bytes)
        self._dur_var.set(f"Duration  :  {self._recorder.duration:.1f} s")
        self._stop_btn.configure(state="disabled")
        self._play_btn.configure(state="normal")
        self._clr_btn.configure(state="normal")
        self._rec_btn.configure(state="normal")
        self._status.set(f"Recording captured — {len(self._audio_bytes):,} bytes", "ok")
        self._refresh_capacity()

    def _play_audio(self):
        if not self._audio_bytes or not _PYAUDIO_OK:
            return
        def _play():
            pa = pyaudio.PyAudio()
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(self._audio_bytes); tmp = f.name
            with wave.open(tmp, "rb") as wf:
                stream = pa.open(format=pa.get_format_from_width(wf.getsampwidth()),
                                 channels=wf.getnchannels(), rate=wf.getframerate(), output=True)
                data = wf.readframes(1024)
                while data:
                    stream.write(data); data = wf.readframes(1024)
                stream.stop_stream(); stream.close()
            pa.terminate(); os.unlink(tmp)
        threading.Thread(target=_play, daemon=True).start()

    def _clear_audio(self):
        self._audio_bytes = None
        self._dur_var.set("Duration  :  —")
        self._waveform.clear()
        self._play_btn.configure(state="disabled")
        self._clr_btn.configure(state="disabled")
        self._refresh_capacity()

    # ── Embed (single + batch) ────────────────────────────────────────────────

    def _embed(self):
        if self._batch_mode and self._batch_paths:
            self._embed_batch()
            return
        self._embed_single()

    def _embed_single(self):
        if not self._image_path:
            messagebox.showwarning("No Image", "Please select a cover image first.")
            return
        password = self._pw_var.get()
        if not password:
            messagebox.showwarning("No Password", "Please enter a password.")
            return
        tab = self._tabs.get().strip()
        if tab == "Text":
            text = self._text_box.get("1.0", "end-1c")
            if not text.strip():
                messagebox.showwarning("No Text", "Please type a message before embedding.")
                return
        elif tab == "File" and not self._file_path:
            messagebox.showwarning("No File", "Please choose a file before embedding.")
            return
        elif tab == "Audio" and not self._audio_bytes:
            messagebox.showwarning("No Audio", "Please record audio before embedding.")
            return

        cap = self._image_info["capacity_bytes"]
        est = estimate_encrypted_size(self._current_data_size(tab))
        if est > cap:
            messagebox.showerror("Image Too Small", "Image too small. Please select a larger cover image.")
            return

        out_path = filedialog.asksaveasfilename(
            title="Save stego image", defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("BMP", "*.bmp")],
        )
        if not out_path:
            return

        self._start_operation("Encrypting & embedding…")

        def _progress_cb(frac: float):
            self.after(0, lambda f=frac: self._progress.set_fraction(f))

        def _work():
            try:
                if tab == "Text":
                    img = encode_text(self._image_path, text, password,
                                      progress_callback=_progress_cb)
                elif tab == "File":
                    img = encode_file(self._image_path, self._file_path, password,
                                      progress_callback=_progress_cb)
                else:
                    img = encode_audio(self._image_path, self._audio_bytes, password,
                                       progress_callback=_progress_cb)
                img.save(out_path)
                self._last_out_path = out_path
                add_history("Encrypt", os.path.basename(out_path), ok=True)
                self.after(0, lambda: (
                    self._stop_operation(),
                    self._status.set(f"Embedding complete ✓ — {os.path.basename(out_path)}", "ok"),
                    self._preview_btn.configure(state="normal"),
                ))
            except Exception as exc:
                add_history("Encrypt", str(exc)[:50], ok=False)
                self.after(0, lambda e=exc: (
                    self._stop_operation(),
                    self._status.set(f"Error: {e}", "error"),
                    messagebox.showerror("Error", str(e)),
                ))

        threading.Thread(target=_work, daemon=True).start()

    def _embed_batch(self):
        password = self._pw_var.get()
        if not password:
            messagebox.showwarning("No Password", "Please enter a password.")
            return
        tab = self._tabs.get().strip()

        out_dir = filedialog.askdirectory(title="Select output folder for batch results")
        if not out_dir:
            return

        total = len(self._batch_paths)
        self._start_operation(f"Batch embedding 0/{total}…")

        def _work():
            for i, img_path in enumerate(self._batch_paths):
                try:
                    basename = os.path.splitext(os.path.basename(img_path))[0]
                    out_path = os.path.join(out_dir, f"{basename}_stego.png")
                    if tab == "Text":
                        text = self._text_box.get("1.0", "end-1c")
                        img  = encode_text(img_path, text, password)
                    elif tab == "File":
                        img  = encode_file(img_path, self._file_path, password)
                    else:
                        img  = encode_audio(img_path, self._audio_bytes, password)
                    img.save(out_path)
                    add_history("Batch", f"{basename}_stego.png", ok=True)
                    frac = (i + 1) / total
                    self.after(0, lambda f=frac, n=i+1: (
                        self._progress.set_fraction(f),
                        self._op_lbl.configure(text=f"Batch {n}/{total}"),
                    ))
                except Exception as exc:
                    add_history("Batch", f"FAIL {os.path.basename(img_path)}: {exc}", ok=False)

            self.after(0, lambda: (
                self._stop_operation(),
                self._status.set(f"Batch complete ✓ — {total} images saved to {os.path.basename(out_dir)}", "ok"),
            ))

        threading.Thread(target=_work, daemon=True).start()

    # ── Before / After ────────────────────────────────────────────────────────

    def _show_preview(self):
        if self._image_path and self._last_out_path:
            BeforeAfterPreview(self, self._image_path, self._last_out_path)

    # ── Operation state helpers ───────────────────────────────────────────────

    def _start_operation(self, label: str):
        self._status.set(label, "warn")
        self._spinner.start()
        # Do NOT call self._progress.start() — set_fraction() drives the bar now
        self._op_lbl.configure(text=label)
        self._embed_btn.configure(state="disabled")
        self.update()

    def _stop_operation(self):
        self._spinner.stop()
        self._progress.stop()
        self._op_lbl.configure(text="")
        self._embed_btn.configure(state="normal")
