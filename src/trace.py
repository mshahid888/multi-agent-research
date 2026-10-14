"""Pretty terminal trace so the agents' work is visible step by step.

This is the preferred "run viewer": it shows the supervisor routing between
agents live in the terminal, which is ideal for demo recordings. Every line is
also appended to ``trace.log`` in the run directory.
"""
from __future__ import annotations

import time
from pathlib import Path


class Tracer:
    def __init__(self, log_path: str | Path | None = None):
        self.log_path = Path(log_path) if log_path else None
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def _emit(self, line: str) -> None:
        print(line, flush=True)
        if self.log_path:
            with open(self.log_path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")

    def _ts(self) -> str:
        return time.strftime("%H:%M:%S")

    def header(self, text: str) -> None:
        self._emit(f"\n{'=' * 62}\n{text}\n{'=' * 62}")

    def route(self, frm: str, to: str) -> None:
        self._emit(f"[{self._ts()}] [supervisor] route: {frm} -> {to}")

    def agent(self, name: str, msg: str) -> None:
        self._emit(f"[{self._ts()}] [{name}] {msg}")

    def ok(self, msg: str) -> None:
        self._emit(f"  [ok] {msg}")

    def warn(self, msg: str) -> None:
        self._emit(f"  [warn] {msg}")

    def error(self, msg: str) -> None:
        self._emit(f"  [error] {msg}")
