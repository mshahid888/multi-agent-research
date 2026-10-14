# Multi-Agent Research System

Give it a company name → a **Researcher** agent gathers data → an **Analyst**
agent writes a structured, fully-grounded brief → a **Writer** agent drafts a
personalized outreach email → a **human approves** → the "send" is
**simulated** (logged, never transmitted).

Portfolio project #4 of 5 — demonstrates the **supervisor/router multi-agent
pattern**, agent working memory, human-in-the-loop control, and a hard
no-invention grounding guarantee.

> **Honesty notes:** the two built-in demo companies are **fictional** — every
> fact about them is invented for the demo and labelled as such. Outreach is
> **drafted and simulated only**: this project contains no sending code (no
> SMTP, no API calls); `send_log.json` always records `sent: false`.

## Architecture

```
                        ┌─────────────┐
                        │ Supervisor  │  router: decide_next(state)
                        │  (router)   │  approval gate + simulated send
                        └──────┬──────┘
               ┌───────────────┼────────────────┐
               ▼               ▼                ▼
      ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
      │ Researcher   │ │ Analyst      │ │ Writer       │
      │ - queries    │ │ - structured │ │ - outreach   │
      │   DataSources│ │   brief      │ │   email      │
      │ - findings → │ │ - grounding  │ │ - DRAFT only │
      │   memory     │ │   verified   │ │ - never sends│
      └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
             └───────────────┼────────────────┘
                             ▼
                    ┌─────────────────┐
                    │  AgentMemory    │  namespaces per agent + shared
                    │  (blackboard)   │  blackboard, saved as memory.json
                    └─────────────────┘
                             ▼
                    ┌─────────────────┐
                    │ Human approval  │── decline → stop, nothing sent
                    │      gate       │── approve → SIMULATED send (sent=false)
                    └─────────────────┘
```

**Pipeline stages:** `research → analyze → draft → approve → send(simulated)`.
The supervisor routes each step via `decide_next()`; every agent reads/writes
the shared `AgentMemory`; the terminal trace shows each handoff live.

**Grounding guarantee:** the default `TemplateBackend` is extractive — claims
are sentence spans copied from researcher findings. The Analyst additionally
runs `verify_grounding()` (token-level check against finding vocabulary) and
raises `GroundingError` on any invented claim, which aborts the run instead
of letting fiction into the draft.

## Setup

```bash
cd multi-agent-research
python3 -m pytest tests/ -q        # 25 tests, stdlib only (+ pytest)
```

No API keys, no paid services, no network needed for the demo.

## 3-step demo

```bash
# 1. See the fictional demo companies
python3 run.py --list-demos

# 2. Run the full pipeline (interactive approval at the end — say y)
python3 run.py --demo nordwind --sender "Your Name"

# 3. Inspect the artifacts of the latest run
ls runs/*/   # memory.json findings.json brief.json outreach_draft.md send_log.json trace.log
```

Scripted/non-interactive (for recordings): add `--yes` to auto-approve the
simulated send. Try the second company: `python3 run.py --demo bluefin`.

Research a real page (polite single-page fetch of a URL **you** point at):

```bash
python3 run.py "Acme Inc" --url https://acme.example.com/about
```

## Recording guide

The terminal trace *is* the demo visual — record it end to end:

1. **Intro (terminal):** `python3 run.py --list-demos` — show the two fictional
   companies; mention all demo data is fake.
2. **Run:** `python3 run.py --demo nordwind` (no `--yes`!) — narrate each
   routing step as it appears: supervisor → researcher (5 findings) →
   analyst (grounded brief) → writer (draft).
3. **Approval gate:** the draft prints; type `y` at the prompt — emphasize a
   human approved it.
4. **Simulated send:** show `send step (SIMULATED ...)` and then open
   `runs/<latest>/send_log.json` — point at `"sent": false`.
5. **Artifacts:** quickly show `brief.json` (strengths/gaps/hooks with
   evidence) and `outreach_draft.md` ("NOT SENT").

Suggested narration line: *"Three agents, one supervisor, zero invented
facts — and a human signs off before anything goes anywhere."*

## Swapping in a real LLM

`src/llm.py` defines the `LLMBackend` interface; `TemplateBackend` is the
deterministic default. To use a real model (e.g. local Ollama):

1. Subclass `LLMBackend` (see `RealLLMBackend` stub) and implement
   `build_brief(company, findings)` returning the same claim-dict shape, with
   `evidence` = finding ids per claim.
2. Pass your backend to `Supervisor(llm=YourBackend(), ...)` in `run.py`.
3. The grounding check stays enforced — a sloppy model fails loudly instead
   of inventing facts.

## Project structure

```
multi-agent-research/
├── run.py                 # CLI entry point
├── requirements.txt       # pytest only; runtime is stdlib
├── data/
│   └── demo_companies.json# 2 fictional companies (clearly labelled fake)
├── src/
│   ├── supervisor.py      # router (decide_next), approval gate, simulated send
│   ├── agents.py          # ResearcherAgent, AnalystAgent, WriterAgent + role prompts
│   ├── memory.py          # AgentMemory: namespaced memory + blackboard, JSON per run
│   ├── datasources.py     # DataSource interface; DemoDataSource; polite WebPageSource
│   ├── llm.py             # LLMBackend interface; TemplateBackend (extractive); RealLLMBackend stub
│   ├── grounding.py       # verify_grounding() + GroundingError
│   └── trace.py           # step-by-step terminal trace (+ trace.log)
└── tests/
    ├── test_router.py     # supervisor routing decisions
    ├── test_memory.py     # memory passing, isolation, save/load
    ├── test_grounding.py  # no invented claims; tampered briefs rejected
    ├── test_approval.py   # gate blocks unapproved sends; send always simulated
    └── test_datasources.py# demo source behavior
```

## What was deliberately left out

- **No real LLM calls** — the template backend keeps the project free, offline,
  and deterministic. The interface is ready for one.
- **No web crawling** — `WebPageSource` fetches exactly one user-supplied URL,
  politely. Multi-page crawling / search APIs are out of scope.
- **No sending** — by design, permanently. The approval gate and simulated
  send are the portfolio point.
