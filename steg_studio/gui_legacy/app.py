# steg_studio/gui/app.py
"""
Main application window — with history sidebar panel.
"""
from __future__ import annotations

import customtkinter as ctk

from steg_studio.gui.widgets     import StatusBar, HistoryPanel, ACCENT, ACCENT_DIM, BORDER
from steg_studio.gui.encrypt_tab import EncryptTab
from steg_studio.gui.decrypt_tab import DecryptTab

APP_NAME = "Secure Steganography Studio"
GEOMETRY = "1100x680"
MIN_SIZE = (920, 600)


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry(GEOMETRY)
        self.minsize(*MIN_SIZE)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self._build_ui()

    def _build_ui(self):
        # ── Top bar ───────────────────────────────────────────────────────────
        top = ctk.CTkFrame(self, height=58, fg_color=("gray88", "#13161C"), corner_radius=0)
        top.pack(fill="x")
        top.pack_propagate(False)

        ctk.CTkFrame(top, width=4, fg_color=ACCENT, corner_radius=0).pack(side="left", fill="y")

        logo = ctk.CTkFrame(top, fg_color="transparent")
        logo.pack(side="left", padx=16)
        ctk.CTkLabel(logo, text="🔐", font=("Segoe UI", 22)).pack(side="left", padx=(0, 8))
        title_stack = ctk.CTkFrame(logo, fg_color="transparent")
        title_stack.pack(side="left")
        ctk.CTkLabel(title_stack, text="SECURE STEGANOGRAPHY STUDIO",
                     font=("Segoe UI", 14, "bold"),
                     text_color=("gray15", "gray95")).pack(anchor="w")
        ctk.CTkLabel(title_stack, text="Hide data invisibly inside images",
                     font=("Segoe UI", 9),
                     text_color=("gray50", "gray55")).pack(anchor="w")

        ctrl = ctk.CTkFrame(top, fg_color="transparent")
        ctrl.pack(side="right", padx=16)

        # History toggle button
        self._hist_var = ctk.BooleanVar(value=True)
        ctk.CTkButton(
            ctrl, text="⏱ History", width=90, height=30,
            font=("Segoe UI", 11),
            fg_color=("gray78", "#2A2F3A"), hover_color=("gray70", "#343B48"),
            text_color=("gray20", "gray80"), corner_radius=6,
            command=self._toggle_history,
        ).pack(side="right", padx=(6, 0))

        self._theme_btn = ctk.CTkButton(
            ctrl, text="☀  Light", width=88, height=30, font=("Segoe UI", 11),
            command=self._toggle_theme,
            fg_color=("gray78", "#2A2F3A"), hover_color=("gray70", "#343B48"),
            text_color=("gray20", "gray80"), corner_radius=6,
        )
        self._theme_btn.pack(side="right")

        # ── Tab strip ─────────────────────────────────────────────────────────
        tab_strip = ctk.CTkFrame(self, height=44, fg_color=("gray90", "#181B22"), corner_radius=0)
        tab_strip.pack(fill="x")
        tab_strip.pack_propagate(False)
        self._enc_tab_btn = self._make_tab_btn(tab_strip, "  ⬡  Encrypt  ", lambda: self._switch_tab("enc"))
        self._dec_tab_btn = self._make_tab_btn(tab_strip, "  ◎  Decrypt  ", lambda: self._switch_tab("dec"))
        self._enc_tab_btn.pack(side="left", padx=(16, 2), pady=7)
        self._dec_tab_btn.pack(side="left", padx=2, pady=7)

        # ── Main area = content + history sidebar ─────────────────────────────
        self._main = ctk.CTkFrame(self, fg_color=("gray92", "#181B22"), corner_radius=0)
        self._main.pack(fill="both", expand=True)

        # Content area (left)
        self._content = ctk.CTkFrame(self._main, fg_color="transparent")
        self._content.pack(side="left", fill="both", expand=True)

        # History sidebar (right, collapsible)
        self._hist_sidebar = ctk.CTkFrame(
            self._main, width=230, fg_color=("gray88", "#13161C"),
            corner_radius=0,
        )
        ctk.CTkFrame(self._hist_sidebar, width=1, fg_color=BORDER, corner_radius=0).pack(side="left", fill="y")
        self._hist_panel = HistoryPanel(self._hist_sidebar)
        self._hist_panel.pack(fill="both", expand=True, padx=(8, 8), pady=10)
        self._hist_sidebar.pack(side="right", fill="y")
        self._hist_sidebar.pack_propagate(False)

        # Create tabs (status injected after)
        self._enc_frame = EncryptTab(self._content, status_bar=self._make_noop())
        self._dec_frame = DecryptTab(self._content, status_bar=self._make_noop())

        # ── Status bar ────────────────────────────────────────────────────────
        bottom = ctk.CTkFrame(self, height=30, fg_color=("gray86", "#0F1116"), corner_radius=0)
        bottom.pack(side="bottom", fill="x")
        bottom.pack_propagate(False)
        ctk.CTkFrame(bottom, height=1, fg_color=BORDER, corner_radius=0).pack(fill="x")
        self._status = StatusBar(bottom)
        self._status.pack(side="left", fill="x", expand=True, padx=14, pady=4)
        ctk.CTkLabel(bottom, text="v2.1  ●  AES-256 + LSB",
                     font=("Segoe UI", 9), text_color=("gray60", "gray45")).pack(side="right", padx=14)

        # Wire real status bar + history refresh into tabs
        self._enc_frame._status = self._status
        self._dec_frame._status = self._status
        self._wire_history_refresh()

        self._switch_tab("enc")

    # ── History wiring ────────────────────────────────────────────────────────

    def _wire_history_refresh(self):
        """Patch embed/decrypt methods to refresh the history panel after each op."""
        orig_embed   = self._enc_frame._embed_single
        orig_decrypt = self._dec_frame._decrypt

        def _patched_embed():
            orig_embed()
            self.after(800, self._hist_panel.refresh)

        def _patched_decrypt():
            orig_decrypt()
            self.after(800, self._hist_panel.refresh)

        self._enc_frame._embed_single = _patched_embed
        self._dec_frame._decrypt      = _patched_decrypt

    def _toggle_history(self):
        if self._hist_var.get():
            self._hist_sidebar.pack_forget()
            self._hist_var.set(False)
        else:
            self._hist_sidebar.pack(side="right", fill="y")
            self._hist_var.set(True)
            self._hist_panel.refresh()

    # ── Tab switching ─────────────────────────────────────────────────────────

    def _make_tab_btn(self, parent, text, cmd):
        return ctk.CTkButton(
            parent, text=text, command=cmd, height=30,
            font=("Segoe UI", 12), corner_radius=6,
            fg_color=("gray80", "#2A2F3A"), hover_color=("gray72", "#343B48"),
            text_color=("gray20", "gray75"),
        )

    def _switch_tab(self, which: str):
        self._enc_frame.pack_forget()
        self._dec_frame.pack_forget()
        ac_fg  = (ACCENT, ACCENT)
        ac_txt = ("#003D30", "#E0FFF8")
        in_fg  = ("gray80", "#2A2F3A")
        in_txt = ("gray20", "gray75")
        if which == "enc":
            self._enc_frame.pack(fill="both", expand=True, padx=10, pady=10)
            self._enc_tab_btn.configure(fg_color=ac_fg, text_color=ac_txt)
            self._dec_tab_btn.configure(fg_color=in_fg, text_color=in_txt)
            self._status.set("Encrypt mode — select a cover image", "info")
        else:
            self._dec_frame.pack(fill="both", expand=True, padx=10, pady=10)
            self._dec_tab_btn.configure(fg_color=ac_fg, text_color=ac_txt)
            self._enc_tab_btn.configure(fg_color=in_fg, text_color=in_txt)
            self._status.set("Decrypt mode — select a stego image", "info")

    # ── Theme toggle ──────────────────────────────────────────────────────────

    def _toggle_theme(self):
        if ctk.get_appearance_mode() == "Dark":
            ctk.set_appearance_mode("light")
            self._theme_btn.configure(text="🌙  Dark")
        else:
            ctk.set_appearance_mode("dark")
            self._theme_btn.configure(text="☀  Light")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _make_noop(self):
        class _N:
            def set(self, *a, **k): pass
        return _N()


def run():
    App().mainloop()

if __name__ == "__main__":
    run()
