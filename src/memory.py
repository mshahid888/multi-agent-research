"""Shared working memory passed between agents.

Each agent writes under its own namespace; a shared blackboard holds run-wide
facts (e.g. the company name). Everything is JSON-serializable and persisted
per run to ``memory.json`` so a run can be inspected or resumed later.
"""
from __future__ import annotations

import json
import time
from pathlib import Path


class AgentMemory:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self._namespaces: dict[str, dict] = {}
        self._shared: dict = {}
        self.events: list[dict] = []

    # -- namespaced reads/writes --------------------------------------
    def write(self, agent: str, key: str, value) -> None:
        """Agent-scoped write, e.g. memory.write("researcher", "findings", [...])."""
        self._namespaces.setdefault(agent, {})[key] = value
        self.log(agent, f"write:{key}")

    def read(self, agent: str, key: str, default=None):
        return self._namespaces.get(agent, {}).get(key, default)

    def read_all(self, agent: str) -> dict:
        return dict(self._namespaces.get(agent, {}))

    # -- shared blackboard ---------------------------------------------
    def share(self, key: str, value) -> None:
        self._shared[key] = value

    def get_shared(self, key: str, default=None):
        return self._shared.get(key, default)

    # -- audit trail ----------------------------------------------------
    def log(self, actor: str, action: str, detail: str = "") -> None:
        self.events.append({
            "t": time.strftime("%H:%M:%S"),
            "actor": actor,
            "action": action,
            "detail": detail,
        })

    # -- persistence -----------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "namespaces": self._namespaces,
            "shared": self._shared,
            "events": self.events,
        }

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    @classmethod
    def load(cls, path: str | Path) -> "AgentMemory":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        mem = cls(data["run_id"])
        mem._namespaces = data.get("namespaces", {})
        mem._shared = data.get("shared", {})
        mem.events = data.get("events", [])
        return mem
