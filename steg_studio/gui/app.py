# steg_studio/gui/app.py
"""Steg Studio v2.1 — Forensic Steganography Workstation shell.

Layout:
  ┌──────────────────────────────────────────────────────────────┐
  │  TitleBar    · traffic lights + brand + session + version    │
  ├──────────────────────────────────────────────────────────────┤
  │  TopBar      · eyebrow + title + segmented + actions         │
  ├──┬───────────────────────────────────────────────────────────┤
  │R │  Workspace                                                │
  │a │  (encrypt | decrypt — each has 1fr workspace + inspector) │
  │i ├───────────────────────────────────────────────────────────┤
  │l │  Event log drawer (collapsible)                           │
  ├──┴───────────────────────────────────────────────────────────┤
  │  StatusBar   · READY · KDF · Cipher · LSB · mem · cpu · ver  │
  └──────────────────────────────────────────────────────────────┘
"""
from __future__ import annotations

import customtkinter as ctk

from . import prefs, theme
from .assets import icon
from .components import V2Badge, V2Segmented, ConsoleLog, Tooltip, session_id

try:
    import psutil
    _PSUTIL_OK = True
except Exception:  # noqa: BLE001
    psutil = None
    _PSUTIL_OK = False
from .encrypt_panel import EncryptPanel
from .decrypt_panel import DecryptPanel
from .inspector_panel import InspectorPanel


APP_NAME = "Steg Studio — Forensic Steganography Workstation"
GEOMETRY = "1480x900"
MIN_SIZE = (900, 600)


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry(GEOMETRY)
        self.minsize(*MIN_SIZE)

        # Apply persisted theme
        saved = prefs.get("theme", "dark")
        theme.set_mode(saved)
        ctk.set_appearance_mode("dark" if saved == "dark" else "light")
        self.configure(fg_color=theme.BG_1)

        self._mode = "encrypt"
        self._console_open = True
        self._drawer_height = int(prefs.get("drawer_height", 200) or 200)
        self._drawer_height = max(80, min(400, self._drawer_height))
        self._build()
        self._bind_shortcuts()
        if _PSUTIL_OK:
            self.after(500, self._tick_metrics)

    # ── shell ────────────────────────────────────────────────────────────────
    def _build(self):
        self._build_titlebar()
        self._build_topbar()

        body = ctk.CTkFrame(self, fg_color=theme.BG_1, corner_radius=0)
        body.pack(fill="both", expand=True)

        self._build_rail(body)

        self._main_col = ctk.CTkFrame(body, fg_color=theme.BG_1, corner_radius=0)
        self._main_col.pack(side="left", fill="both", expand=True)

        self._workspace = ctk.CTkFrame(self._main_col,
                                        fg_color=theme.BG_1, corner_radius=0)
        self._workspace.pack(fill="both", expand=True)

        # Console drawer (with drag handle above it for vertical resize)
        self._drawer = ctk.CTkFrame(self._main_col, fg_color=theme.BG_2,
                                     height=self._drawer_height,
                                     corner_radius=0, border_width=0)
        self._drawer.pack(fill="x", side="bottom")
        self._drawer.pack_propagate(False)

        self._grip = ctk.CTkFrame(self._main_col, fg_color=theme.STROKE_HI,
                                   height=4, corner_radius=0, cursor="sb_v_double_arrow")
        self._grip.pack(fill="x", side="bottom", before=self._drawer)
        self._grip.bind("<Enter>",
                        lambda _e: self._grip.configure(fg_color=theme.AMBER))
        self._grip.bind("<Leave>",
                        lambda _e: self._grip.configure(fg_color=theme.STROKE_HI))
        self._grip.bind("<ButtonPress-1>", self._grip_press)
        self._grip.bind("<B1-Motion>", self._grip_drag)
        self._grip.bind("<ButtonRelease-1>", self._grip_release)
        self._grip_origin = None

        self._build_drawer()

        self._build_statusbar()
        self._build_panels()

        # Boot log
        self._log.add("steg-studio/core v2.1.0 · py · cryptography backend OpenSSL", "info")
        self._log.add("Cryptography: Fernet (AES-128-CBC + HMAC-SHA256) · PBKDF2-HMAC-SHA256 480K iters", "info")
        self._log.add(f"Session initialised · session#{session_id()}", "ok")

    def _build_titlebar(self):
        bar = ctk.CTkFrame(self, fg_color=theme.BG_0, height=40,
                            corner_radius=0)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        # Traffic lights
        tl = ctk.CTkFrame(bar, fg_color="transparent")
        tl.pack(side="left", padx=14)
        for col in ("#FF5F57", "#FEBC2E", "#28C840"):
            d = ctk.CTkLabel(tl, text="●", text_color=col,
                              font=("Segoe UI", 12), width=14)
            d.pack(side="left", padx=2)

        # Brand center
        center = ctk.CTkFrame(bar, fg_color="transparent")
        center.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(center, text="",
                      image=icon("lock", 14, theme.AMBER_INK),
                      width=20, height=20,
                      fg_color=theme.AMBER, corner_radius=4
                      ).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(center, text="Steg Studio",
                      font=("Segoe UI", 12, "bold"),
                      text_color=theme.TEXT_MID
                      ).pack(side="left")
        ctk.CTkLabel(center, text="·",
                      font=("JetBrains Mono", 11),
                      text_color=theme.TEXT_DIM
                      ).pack(side="left", padx=8)
        ctk.CTkLabel(center,
                      text=f"session {session_id()} · workspace",
                      font=("JetBrains Mono", 10),
                      text_color=theme.TEXT_LO
                      ).pack(side="left")

        ctk.CTkLabel(bar, text="v2.1.0",
                      font=("JetBrains Mono", 10),
                      text_color=theme.TEXT_DIM
                      ).pack(side="right", padx=14)

    def _build_topbar(self):
        bar = ctk.CTkFrame(self, fg_color=theme.BG_2, height=68,
                            corner_radius=0)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        # Eyebrow + big title (left)
        left = ctk.CTkFrame(bar, fg_color="transparent")
        left.pack(side="left", padx=20, pady=12)
        self._eyebrow = ctk.CTkLabel(left,
                                       text="EMBED / ENCRYPT",
                                       font=("Segoe UI", 9, "bold"),
                                       text_color=theme.AMBER, anchor="w")
        self._eyebrow.pack(anchor="w")
        self._title = ctk.CTkLabel(left,
                                     text="Hide an authenticated payload inside a lossless image",
                                     font=("Segoe UI", 16, "bold"),
                                     text_color=theme.TEXT_HI, anchor="w")
        self._title.pack(anchor="w")

        # Right cluster: segmented + history + prefs
        right = ctk.CTkFrame(bar, fg_color="transparent")
        right.pack(side="right", padx=20, pady=12)

        self._seg = V2Segmented(right, ["Encrypt", "Decrypt", "Inspect"],
                                  on_change=lambda v: self._switch(v.lower()),
                                  icons=["lock", "unlock", "chart"])
        self._seg.pack(side="left")

        # Dark / Light toggle
        self._theme_seg = V2Segmented(
            right, ["Dark", "Light"],
            on_change=lambda v: self._toggle_theme(v.lower()))
        self._theme_seg.pack(side="left", padx=(12, 0))
        self._theme_seg.set("Light" if theme.MODE == "light" else "Dark")
        Tooltip(self._theme_seg, "Dark / Light theme  (Ctrl+T)")

    def _build_rail(self, parent):
        rail = ctk.CTkFrame(parent, fg_color=theme.BG_2, width=56,
                             corner_radius=0)
        rail.pack(side="left", fill="y")
        rail.pack_propagate(False)

        items = [
            ("encrypt", "lock", "Encrypt  (Ctrl+1)"),
            ("decrypt", "unlock", "Decrypt  (Ctrl+2)"),
            ("inspect", "chart", "Inspect  (Ctrl+3)"),
        ]
        self._rail_btns: dict[str, ctk.CTkButton] = {}
        for key, ic, tip in items:
            b = ctk.CTkButton(rail, text="",
                               image=icon(ic, 16,
                                           theme.AMBER if key == self._mode
                                           else theme.TEXT_LO),
                               width=40, height=40,
                               fg_color=("#3C2A0E" if key == self._mode
                                         else "transparent"),
                               hover_color=theme.BG_3,
                               border_width=1 if key == self._mode else 0,
                               border_color="#6A4818",
                               corner_radius=6,
                               command=(lambda k=key: self._switch(k)))
            b.pack(pady=4)
            Tooltip(b, tip)
            self._rail_btns[key] = b
            self._rail_btns[key + "_icon"] = ic  # type: ignore

        # spacer
        ctk.CTkFrame(rail, fg_color="transparent", height=1).pack(
            fill="y", expand=True)

        # Console toggle at bottom
        self._console_btn = ctk.CTkButton(
            rail, text="",
            image=icon("terminal", 16, theme.AMBER),
            width=40, height=40,
            fg_color="#3C2A0E", hover_color=theme.BG_3,
            border_width=1, border_color="#6A4818",
            corner_radius=6,
            command=self._toggle_console)
        self._console_btn.pack(pady=8)
        Tooltip(self._console_btn, "Toggle event log  (Ctrl+L)")

    def _build_drawer(self):
        head = ctk.CTkFrame(self._drawer, fg_color=theme.BG_2,
                             height=32, corner_radius=0)
        head.pack(fill="x")
        head.pack_propagate(False)
        ctk.CTkLabel(head, text="",
                      image=icon("terminal", 13, theme.AMBER), width=18
                      ).pack(side="left", padx=(14, 6))
        ctk.CTkLabel(head, text="EVENT LOG",
                      font=("Segoe UI", 10, "bold"),
                      text_color=theme.TEXT_MID
                      ).pack(side="left")
        self._log_count = V2Badge(head, "0 entries", "neutral")
        self._log_count.pack(side="left", padx=10)

        ctk.CTkButton(head, text="Clear",
                       fg_color="transparent", hover_color=theme.BG_3,
                       text_color=theme.TEXT_DIM,
                       font=("Segoe UI", 10),
                       width=50, height=22, corner_radius=4,
                       command=self._clear_log
                       ).pack(side="right", padx=(0, 4))
        ctk.CTkButton(head, text="✕",
                       fg_color="transparent", hover_color=theme.BG_3,
                       text_color=theme.TEXT_DIM,
                       font=("Segoe UI", 12),
                       width=30, height=22, corner_radius=4,
                       command=self._toggle_console
                       ).pack(side="right", padx=(0, 8))

        body = ctk.CTkFrame(self._drawer, fg_color=theme.BG_2)
        body.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        self._log = ConsoleLog(body)
        self._log.pack(fill="both", expand=True)

    def _build_statusbar(self):
        bar = ctk.CTkFrame(self, fg_color=theme.BG_0, height=28,
                            corner_radius=0)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        def chunk(text: str, color: str = theme.TEXT_LO,
                  bold: bool = False, accent_dot: bool = False):
            f = ctk.CTkFrame(bar, fg_color="transparent")
            f.pack(side="left", padx=(0, 8))
            if accent_dot:
                ctk.CTkLabel(f, text="●",
                              text_color=theme.OK,
                              font=("Segoe UI", 10),
                              width=12).pack(side="left")
            ctk.CTkLabel(f, text=text,
                          font=("JetBrains Mono", 10,
                                "bold" if bold else "normal"),
                          text_color=color
                          ).pack(side="left")
            return f

        chunk(" READY", theme.TEXT_HI, bold=True, accent_dot=True)
        sep = lambda: ctk.CTkLabel(bar, text="│", text_color=theme.TEXT_DIM,
                                    font=("Segoe UI", 11)).pack(side="left",
                                                                  padx=4)
        sep()
        chunk("PBKDF2 · 480,000 iters")
        sep()
        chunk("Fernet · AES-128-CBC + HMAC-SHA256")
        sep()
        chunk("LSB · 1-bit · G-channel primary")

        # Right side: version + live metrics (if psutil)
        ctk.CTkLabel(bar, text=f"v2.1.0 · session {session_id()}",
                     font=("JetBrains Mono", 10),
                     text_color=theme.AMBER).pack(side="right", padx=8)
        if _PSUTIL_OK:
            ctk.CTkLabel(bar, text="│", text_color=theme.TEXT_DIM,
                         font=("Segoe UI", 11)).pack(side="right", padx=4)
            self._cpu_lbl = ctk.CTkLabel(
                bar, text="cpu —", font=("JetBrains Mono", 10),
                text_color=theme.TEXT_LO)
            self._cpu_lbl.pack(side="right", padx=4)
            self._mem_lbl = ctk.CTkLabel(
                bar, text="mem —", font=("JetBrains Mono", 10),
                text_color=theme.TEXT_LO)
            self._mem_lbl.pack(side="right", padx=4)

    def _build_panels(self):
        self._encrypt = EncryptPanel(
            self._workspace,
            log=self._log_event,
            on_status=lambda *_: None,
            on_inspect=self._set_inspector,
        )
        self._decrypt = DecryptPanel(
            self._workspace,
            log=self._log_event,
            on_status=lambda *_: None,
            on_inspect=self._set_inspector,
        )
        self._inspect = InspectorPanel(self._workspace)
        self._encrypt.pack(fill="both", expand=True)
        self._current = self._encrypt

    # ── view switching ───────────────────────────────────────────────────────
    def _switch(self, mode: str):
        if mode == self._mode:
            return
        for panel in (self._encrypt, self._decrypt, self._inspect):
            panel.pack_forget()
        self._mode = mode
        if mode == "encrypt":
            self._eyebrow.configure(text="EMBED / ENCRYPT")
            self._title.configure(
                text="Hide an authenticated payload inside a lossless image")
            self._encrypt.pack(fill="both", expand=True)
            self._current = self._encrypt
            self._seg.set("Encrypt")
        elif mode == "decrypt":
            self._eyebrow.configure(text="EXTRACT / DECRYPT")
            self._title.configure(
                text="Recover and verify a payload from a stego image")
            self._decrypt.pack(fill="both", expand=True)
            self._current = self._decrypt
            self._seg.set("Decrypt")
        else:  # inspect
            self._eyebrow.configure(text="FORENSIC INSPECTOR")
            self._title.configure(
                text="Trace of the most recent operation")
            self._inspect.pack(fill="both", expand=True)
            self._current = self._inspect
            self._seg.set("Inspect")
        self._sync_rail()

    def _set_inspector(self, state: dict):
        try:
            kind = state.get("kind")
            if kind == "narrate":
                self._inspect.narrate(state.get("msg", ""),
                                      state.get("tone", "info"))
                return
            if kind == "reset_narration":
                self._inspect.reset_narration()
                return
            if kind == "update_capacity":
                self._inspect.update_capacity(state)
                return
            if state.get("preview"):
                self._inspect.set_preview_state(state)
                return
            self._inspect.set_state(state)
            self._log_event(
                f"Inspector updated · {state.get('label','')}", "info")
        except Exception as exc:
            self._log_event(f"Inspector update failed · {exc}", "crit")

    def _toggle_theme(self, mode: str):
        if mode not in ("dark", "light"):
            return
        if theme.MODE == mode:
            return
        theme.set_mode(mode)
        prefs.set("theme", mode)
        try:
            ctk.set_appearance_mode("dark" if mode == "dark" else "light")
        except Exception:
            pass
        # Full UI rebuild: our widgets capture theme tokens at build time and
        # do not listen for palette changes, so the only reliable way to
        # repaint is to tear down and re-create the shell.
        self._rebuild_ui()
        self._log_event(f"Theme · {mode}", "info")

    def _rebuild_ui(self):
        for child in list(self.winfo_children()):
            try:
                child.destroy()
            except Exception:
                pass
        self.configure(fg_color=theme.BG_1)
        self._build()

    def _sync_rail(self):
        for key in ("encrypt", "decrypt", "inspect"):
            b = self._rail_btns[key]
            ic = self._rail_btns[key + "_icon"]  # type: ignore
            active = key == self._mode
            b.configure(
                fg_color="#3C2A0E" if active else "transparent",
                border_width=1 if active else 0,
                image=icon(ic, 16,
                            theme.AMBER if active else theme.TEXT_LO),
            )

    def _toggle_console(self):
        self._console_open = not self._console_open
        if self._console_open:
            self._drawer.pack(fill="x", side="bottom")
            self._grip.pack(fill="x", side="bottom", before=self._drawer)
            self._console_btn.configure(fg_color="#3C2A0E", border_width=1)
        else:
            self._drawer.pack_forget()
            self._grip.pack_forget()
            self._console_btn.configure(fg_color="transparent", border_width=0)

    def _clear_log(self):
        self._log.clear()
        self._log_count.set("0 entries", "neutral")

    def _log_event(self, msg: str, level: str = "info"):
        self._log.add(msg, level)
        self._log_count.set(f"{self._log.count} entries", "neutral")

    # ── drawer resize ────────────────────────────────────────────────────────
    def _grip_press(self, event):
        self._grip_origin = (event.y_root, self._drawer_height)

    def _grip_drag(self, event):
        if self._grip_origin is None or not self._console_open:
            return
        y0, h0 = self._grip_origin
        delta = y0 - event.y_root  # up = larger drawer
        new_h = max(80, min(400, h0 + delta))
        if new_h != self._drawer_height:
            self._drawer_height = new_h
            self._drawer.configure(height=new_h)

    def _grip_release(self, _event):
        self._grip_origin = None
        prefs.set("drawer_height", self._drawer_height)

    # ── shortcuts ────────────────────────────────────────────────────────────
    def _bind_shortcuts(self):
        # Bind on the toplevel only — bind_all + duplicate case bindings
        # caused double-fires under Caps Lock.
        self.bind("<Control-Key-1>", lambda _e: self._switch("encrypt"))
        self.bind("<Control-Key-2>", lambda _e: self._switch("decrypt"))
        self.bind("<Control-Key-3>", lambda _e: self._switch("inspect"))
        self.bind("<Control-Key-l>", lambda _e: self._toggle_console())
        self.bind("<Control-Key-t>",
                  lambda _e: self._toggle_theme(
                      "light" if theme.MODE == "dark" else "dark"))

    # ── status bar live metrics ──────────────────────────────────────────────
    def _tick_metrics(self):
        # Stop ticking once the window has been destroyed.
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        try:
            if _PSUTIL_OK and hasattr(self, "_mem_lbl"):
                mem = psutil.virtual_memory().percent
                cpu = psutil.cpu_percent(interval=None)
                self._mem_lbl.configure(text=f"mem {mem:.0f}%")
                self._cpu_lbl.configure(text=f"cpu {cpu:.0f}%")
        except Exception:
            pass
        try:
            self.after(2000, self._tick_metrics)
        except Exception:
            pass


def run():
    from .splash import SplashScreen

    app = App()
    app.withdraw()  # hide until splash finishes
    SplashScreen(app, on_done=lambda: (app.deiconify(), app.lift()))
    app.mainloop()


if __name__ == "__main__":
    run()
