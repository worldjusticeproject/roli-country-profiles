"""Background build of the combined all-countries PDF.

Building all 143 profiles takes about 80 seconds, which is far too long to hold
an HTTP request open -- browsers and proxies time out on a response that sends
no bytes for that long. So the build runs on a worker thread, writes the result
into output/, and the browser polls for progress and then downloads a finished
file off disk.
"""

from __future__ import annotations

import threading
from pathlib import Path

_lock = threading.Lock()
_state: dict = {"state": "idle", "done": 0, "total": 0, "error": None}


def status(target: Path) -> dict:
    """Current build state, plus the finished file if there is one."""
    with _lock:
        snapshot = dict(_state)
    if snapshot["state"] != "running" and target.exists():
        snapshot["state"] = "ready"
        snapshot["bytes"] = target.stat().st_size
    return snapshot


def start(target: Path, countries: list[str]) -> dict:
    """Kick off a build unless one is already running."""
    with _lock:
        if _state["state"] == "running":
            return dict(_state)
        _state.update(state="running", done=0, total=len(countries), error=None)

    thread = threading.Thread(
        target=_build, args=(target, countries), name="build-all", daemon=True
    )
    thread.start()
    return status(target)


def _build(target: Path, countries: list[str]) -> None:
    from .render import render_all_pdf

    def progress(done: int, total: int) -> None:
        with _lock:
            _state.update(done=done, total=total)

    try:
        pdf = render_all_pdf(countries, on_progress=progress)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Write beside the target and rename, so a half-written file is never
        # served if the process dies mid-build.
        partial = target.with_name(target.name + ".part")
        partial.write_bytes(pdf)
        partial.replace(target)
    except Exception as error:  # noqa: BLE001 - surfaced to the browser as-is
        with _lock:
            _state.update(state="failed", error=str(error))
        return

    with _lock:
        _state.update(state="ready", error=None)
