#!/usr/bin/env python3
"""Multi-Agent Research System — CLI.

Demo (offline, fictional data):

    python3 run.py --list-demos
    python3 run.py --demo nordwind            # interactive approval at the end
    python3 run.py --demo bluefin --yes       # scripted demo, auto-approves

Real page (polite single-page fetch of a URL you point at):

    python3 run.py "Acme Inc" --url https://acme.example.com/about
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.datasources import DemoDataSource, WebPageSource
from src.llm import TemplateBackend
from src.memory import AgentMemory
from src.supervisor import Approval, Supervisor
from src.trace import Tracer

DATA_PATH = Path(__file__).resolve().parent / "data" / "demo_companies.json"


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Company -> researcher -> analyst -> writer -> "
                    "human approval -> simulated send.")
    ap.add_argument("company", nargs="?",
                    help="Company name (not needed with --demo).")
    ap.add_argument("--demo", metavar="ID",
                    help="Use built-in FICTIONAL demo data (see --list-demos).")
    ap.add_argument("--url", metavar="URL",
                    help="Fetch one public page you point at (polite fetcher).")
    ap.add_argument("--list-demos", action="store_true",
                    help="List the built-in fictional demo companies.")
    ap.add_argument("--yes", action="store_true",
                    help="Auto-approve the simulated send (scripted demos/recordings).")
    ap.add_argument("--sender", default="[Your Name]",
                    help="Sender name used in the draft.")
    return ap


def main() -> None:
    args = build_parser().parse_args()

    if args.list_demos:
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        print("Built-in demo companies (ALL DATA FICTIONAL):")
        for cid, entry in data.items():
            print(f"  {cid:12} {entry['company']}")
        return

    sources = []
    company = args.company
    if args.demo:
        src = DemoDataSource(DATA_PATH, args.demo)
        sources.append(src)
        company = src.company_name
    if args.url:
        sources.append(WebPageSource(args.url))
    if not sources:
        sys.exit("error: choose a source — --demo ID or --url URL (see --list-demos).")
    if not company:
        sys.exit("error: a company name is required with --url.")

    slug = re.sub(r"\W+", "-", company.lower()).strip("-") or "company"
    run_id = f"{time.strftime('%Y%m%d-%H%M%S')}-{slug}"
    run_dir = Path(__file__).resolve().parent / "runs" / run_id

    memory = AgentMemory(run_id)
    tracer = Tracer(run_dir / "trace.log")

    approver = None
    if args.yes:
        approver = lambda draft: Approval(  # noqa: E731
            approved=True,
            by="demo --yes",
            at=time.strftime("%Y-%m-%d %H:%M:%S"),
            note="auto-approved for scripted demo (simulated send only)")

    supervisor = Supervisor(llm=TemplateBackend(), memory=memory, tracer=tracer,
                            run_dir=run_dir, approver=approver,
                            sender_name=args.sender)
    result = supervisor.run(company, sources)
    print(f"\nResult: {result['status']}")
    print(f"Artifacts: {result['run_dir']}/")
    print("  memory.json, findings.json, brief.json, outreach_draft.md, "
          "send_log.json, trace.log")


if __name__ == "__main__":
    main()
