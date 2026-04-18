# steg_studio/gui/workers.py
"""Run core operations on a background thread; marshal callbacks back to Tk."""
from __future__ import annotations

import queue
import threading
from typing import Any, Callable


def run_in_thread(
    root,
    fn: Callable[..., Any],
    *,
    on_progress: Callable[[float], None] | None = None,
    on_done: Callable[[Any], None] | None = None,
    on_error: Callable[[BaseException], None] | None = None,
    inject_progress_kwarg: str | None = "progress_callback",
) -> None:
    """
    Run *fn* in a worker thread. If *inject_progress_kwarg* is set, a
    thread-safe progress forwarder is injected under that kwarg name so that
    core functions can emit floats in [0, 1].
    """
    q: queue.Queue = queue.Queue()

    def _forward_progress(p: float) -> None:
        q.put(("progress", float(p)))

    def _worker():
        try:
            kwargs = {}
            if inject_progress_kwarg:
                kwargs[inject_progress_kwarg] = _forward_progress
            result = fn(**kwargs)
            q.put(("done", result))
        except BaseException as exc:  # noqa: BLE001
            q.put(("error", exc))

    threading.Thread(target=_worker, daemon=True).start()

    def _drain():
        # Coalesce: keep only the latest progress value so we never fire
        # more than one redraw per drain tick (prevents UI freezes on
        # large payloads where the core emits thousands of progress
        # events faster than Tk can repaint).
        latest_progress: float | None = None
        terminal: tuple[str, Any] | None = None
        try:
            while True:
                kind, payload = q.get_nowait()
                if kind == "progress":
                    latest_progress = payload
                else:
                    terminal = (kind, payload)
                    break
        except queue.Empty:
            pass

        if latest_progress is not None and on_progress:
            on_progress(latest_progress)

        if terminal is not None:
            kind, payload = terminal
            if kind == "done" and on_done:
                on_done(payload)
            elif kind == "error" and on_error:
                on_error(payload)
            return

        root.after(50, _drain)

    root.after(50, _drain)
