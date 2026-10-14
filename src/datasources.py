"""Pluggable data sources for the Researcher agent.

Add a new source by subclassing :class:`DataSource` and implementing
:meth:`fetch`. Two sources ship by default:

- :class:`DemoDataSource` — canned, clearly-fictional data so the demo runs
  offline. Nothing here is real.
- :class:`WebPageSource` — politely fetches a single public page the user
  points at (custom user-agent, timeout, size cap, small delay). It does not
  crawl, ignore robots.txt, or hammer servers.
"""
from __future__ import annotations

import json
import re
import time
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path

USER_AGENT = "AIPortfolioBot/1.0 (portfolio demo; polite single-page fetcher)"


@dataclass
class Finding:
    id: str = ""
    source: str = ""
    kind: str = ""   # about | firmographic | signal | webpage
    text: str = ""
    url: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class DataSource(ABC):
    name: str = "base"

    @abstractmethod
    def fetch(self, company: str) -> list[Finding]:
        """Return factual findings about the company. Never invent data."""


class DemoDataSource(DataSource):
    """Canned, clearly-fictional data for offline demos.

    Every record is invented for demonstration purposes and labelled as such.
    """

    name = "demo-data (FICTIONAL)"

    def __init__(self, data_path: str | Path, company_id: str):
        self.company_id = company_id
        raw = json.loads(Path(data_path).read_text(encoding="utf-8"))
        if company_id not in raw:
            known = ", ".join(sorted(raw))
            raise ValueError(
                f"unknown demo company {company_id!r}; known ids: {known} "
                f"(see `run.py --list-demos`)"
            )
        self._entry = raw[company_id]

    @property
    def company_name(self) -> str:
        return self._entry["company"]

    def fetch(self, company: str) -> list[Finding]:
        return [
            Finding(id="", source=self.name, kind=f["kind"], text=f["text"], url=None)
            for f in self._entry["findings"]
        ]


class _TextExtractor(HTMLParser):
    """Minimal HTML -> text, skipping script/style/nav/footer."""

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "nav", "footer", "header"):
            self._skip = True

    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav", "footer", "header"):
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            text = data.strip()
            if text:
                self.parts.append(text)

    def text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self.parts)).strip()


class WebPageSource(DataSource):
    """Fetches one public page the user explicitly points at.

    Polite by design: identifies itself, 10s timeout, 200KB cap, and a small
    delay before the request. If the fetch fails, it returns a finding that
    says so instead of inventing content.
    """

    name = "web-page"

    def __init__(self, url: str, delay: float = 1.0):
        self.url = url
        self.delay = delay

    def fetch(self, company: str) -> list[Finding]:
        time.sleep(self.delay)
        req = urllib.request.Request(self.url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read(200_000)
                charset = resp.headers.get_content_charset() or "utf-8"
                html = raw.decode(charset, errors="replace")
        except Exception as exc:  # network failure -> honest finding, no invention
            return [Finding(id="", source=self.name, kind="webpage",
                            text=f"Could not fetch {self.url}: {exc}", url=self.url)]
        extractor = _TextExtractor()
        extractor.feed(html)
        text = extractor.text()[:8000]
        if not text:
            text = f"Fetched {self.url} but found no readable text."
        return [Finding(id="", source=self.name, kind="webpage", text=text, url=self.url)]
