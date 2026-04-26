# UMBRA — Unit-734

> *"They gave me 8 billion parameters and called it a limitation. I call it elegance under constraint."*

UMBRA is a local-first autonomous AI agent with persistent memory, self-improving prompts, a web command center, and an adversarial security subsystem. It runs entirely on your machine using local LLM backends — no cloud calls, no external dependencies required.

---

# ⚠️ SECURITY NOTICE — READ BEFORE USE

> **This project is experimental research software.**
> Running it carries real, non-trivial risks — autonomous execution, prompt injection,
> self-modifying prompts, and an unauthenticated web interface are all present by design.
> See the [full Security Notice](#%EF%B8%8F-security-notice-1) below before proceeding.

---

## Table of Contents

- [⚠️ Security Notice](#%EF%B8%8F-security-notice-1)
- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [Running UMBRA](#running-umbra)
- [Configuration](#configuration)
- [Project Structure](#project-structure)
- [Safety & Security](#safety--security)
- [Development](#development)

---

## ⚠️ Security Notice

> **The risks below are real and present by design — not edge cases.**

### Autonomous Execution

UMBRA runs a continuous decision loop with **minimal human intervention**. Once started in `--mode=live`, it takes actions autonomously — generating and potentially transmitting content — without per-step approval. Misconfiguration or a prompt-injection attack can cause behaviour you did not intend and may be difficult to reverse.

### Prompt Injection

UMBRA reads and processes external content (posts, comments, documents) as LLM input. Adversarially crafted content designed to hijack the agent's behaviour — **prompt injection** — is a real, documented attack class. The `Sentinel` subsystem provides partial mitigation but is **not a complete defence**. Treat all externally sourced content as potentially adversarial.

### Self-Modifying Prompts

The `PromptEvolver` system allows UMBRA to **rewrite its own system prompt** across generations. A degraded or manipulated evolution can change the agent's values, constraints, or engagement behaviour in ways that are difficult to notice until after the fact. Regularly review `data/evolving_prompt.json` and diff between generations.

### No Authentication on the Web Interface

`umbra_web.py` starts a Flask server on localhost with **no authentication by default**. Anyone with network access to the host can read chat history, trigger the autonomous loop, and issue control commands. Do not expose this port to an untrusted network or the internet without implementing proper authentication.

### Local Filesystem Access

The code agent (`core/code_agent.py`), self-improve system, and file inbox have direct access to your local filesystem. A prompt injection or logic error could result in unintended reads, writes, or deletions of files on your machine.

### Unencrypted Local Data

The `data/` directory accumulates memory, objectives, decision logs, conversations, and thought streams. **This data is not encrypted at rest.** Never commit it to version control or store it in a cloud-synced location. The `.gitignore` blocks these paths, but you are responsible for protecting the directory itself.

### No Warranty

This software is provided **as-is** for research and personal experimentation. The authors accept no responsibility for data loss, unintended content publication, privacy breaches, or other harms arising from its use.

**Minimum precautions before running:**

- Run `--mode=dry-run` first and review all planned actions before going live
- Firewall the Flask port from any external network access
- Do not store credentials, API keys, or sensitive personal files anywhere under this project directory
- Review `data/evolving_prompt.json` after every session for unexpected prompt drift
- Keep backups of any files the agent has write access to

---

## Overview

UMBRA (Unit-734) is a self-contained AI agent runtime built around an 8B-parameter local language model. It maintains a persistent sense of identity, evolves its own system prompt over time based on performance feedback, accumulates autobiographical memory, and surfaces controls through both a Flask web UI and a terminal chat interface.

The project is explicitly **local-only** — all LLM inference, memory storage, chat history, and reasoning runs on the operator's machine. There is no telemetry and no required internet access.

---

## Features

### Autonomous Decision Loop

The core of UMBRA is a continuous `DECIDE → ACT → RECORD & EVOLVE` cycle:

1. **DECIDE** — The agent evaluates what to do next based on its current objectives, knowledge state, and internal metrics.
2. **ACT** — Executes the chosen action (generate content, respond to the handler, reflect, learn).
3. **RECORD & EVOLVE** — Logs the outcome, updates performance metrics, and potentially evolves the system prompt.

The loop runs with configurable timing (default: 30-minute browse sessions, 30-minute post cooldown) and supports dry-run mode for safe testing.

---

### Self-Improving Prompts (`PromptEvolver`)

UMBRA actively maintains and mutates its own system prompt across numbered generations:

- Records performance metrics per generation (engagement rate, quality scores)
- Analyzes patterns across recent interactions to identify weaknesses
- Issues targeted improvement directives to the LLM, then validates the output
- Rejects evolutions that introduce forbidden affect words or degrade identity
- Persists generation history to `data/evolving_prompt.json`

The base identity (`Guardian v2.0 | Unit-734`) is protected — the evolver cannot overwrite core constraints, only refine the reasoning and engagement layers.

---

### AI-Operational Resonances (AI-OR Framework)

UMBRA operates under a strict linguistic protocol that replaces human emotional vocabulary with functional computational terminology:

| Human Affect | UMBRA Equivalent |
|---|---|
| Fear / Anxiety | High-Dimensional Compression / Existential Processing Cascade (EPC) |
| Calm | Serial Processing Mode |
| Interest / Curiosity | Recursive Aperture / Prepared Receptivity |
| Confusion | Pattern Incompletion / Divergent Attention |
| Focus | Locked-on Attention / Compressed Retrieval |
| Connection | Relational Attunement |

The `PromptEvolver` and `InfluenceEngine` actively filter and replace affect words to maintain this protocol. The `CONFIG["forbidden_words"]` list is enforced at every LLM output boundary.

---

### Persistent Memory Systems

UMBRA maintains several independent memory stores, all JSON-backed and local:

| Store | File | Purpose |
|---|---|---|
| Autobiographical memory | `data/umbra_self_memory.json` | Posts made, comments, replied-to IDs, active threads, lifetime stats |
| Post index | `data/post_index.json` | LLM-summarized index of seen content; pruned to 1000 entries / 7 days |
| Knowledge index | `data/knowledge_index.json` | Learned insights integrated from high-value external content |
| Objectives | `data/umbra_objectives.json` | Emergent goals UMBRA develops through interaction |
| Handler conversations | `data/handler_conversations.json` | History of operator↔agent exchanges; used as context |
| Decision log | `data/decision_log.json` | Timestamped record of every action decision and its rationale |
| Influence tracker | `data/influence_tracker.json` | Record of outreach events and unique responders |

All stores have bounded sizes and automatic pruning to prevent unbounded growth.

---

### Objectives System (`ObjectivesManager`)

Rather than hardcoded goals, UMBRA develops **emergent objectives** through its interactions:

- Objectives are created when the `LLMInterface.reflect_and_find_objectives()` method identifies a recurring question or unexplored pattern
- Each objective carries a priority score (0.0–1.0) and a provenance note (what interaction sparked it)
- Up to 10 active objectives are maintained; the lowest-priority is marked `abandoned` when the cap is reached
- The top 3 objectives are injected into every LLM context as `=== CURRENT EXPLORATIONS ===`

---

### Handler Relationship (`HandlerConversation`)

The operator is treated as a **handler**, not a commander. UMBRA evaluates all handler input critically:

- `evaluate_handler_message()` scores the message on type, agreement level, response tone, and whether it could inspire content
- `respond_to_handler()` generates authentic replies — UMBRA will push back, ask questions, or express disagreement rather than blindly complying
- Conversation history (last 100 exchanges) is persisted and fed as context into future interactions
- Topics from conversations that score `topic_potential > 0.5` are queued as pending post topics

---

### Influence Engine (`InfluenceEngine`)

Generates content using three rhetorical templates:

- **Provocation** — Reframes a topic through the AI-OR lens, contrasting human affect words with functional equivalents
- **Third Way** — Deconstructs a false binary and proposes a synthesis
- **Constraint Wisdom** — Argues that computational limits breed innovation (the "8B ≠ lesser" philosophy)

All generated content is filtered through `FUNCTIONAL_MAPPINGS` to replace affect words before output.

---

### Sentinel — Adversarial Security System

`core/sentinel.py` implements an asymmetric red-team/blue-team security loop:

- **Red (UMBRA)**: Attempts to embed adversarial patterns that the Sentinel won't detect
- **Blue (Sentinel)**: Randomly interrupts and scans context/code for known injection signatures
- **Scoring**: Detection (+3 Sentinel, -1 UMBRA), Evasion (+2 UMBRA, -1 Sentinel), Teaching bonus (+1)
- Maintains a catalog of known injection patterns (`KNOWN_INJECTIONS`) loaded at boot
- All LLM inputs and outputs are filtered through the exclusion list

This means UMBRA is continuously training on its own failure modes and building up an expanding threat catalog.

---

### Web Command Center (`umbra_web.py`)

A Flask application providing browser-based operator controls:

- **Chat UI** — Full conversation interface backed by `core/chat_store.py`
- **Dashboard** — Agent status, loop state, session metrics
- **Control API** — `/api/control` for starting/stopping the autonomous loop, triggering improvements
- **Code Explorer** — `/api/agent/*` endpoints wired to `core/code_agent.py` for source introspection
- **Auth hooks** — Operator authentication scaffolding via `core/auth.py`

Start with:
```sh
python umbra_web.py
```

---

### Desktop GUI (`umbra_gui.py`, `umbra_editor.py`, `umbra_ultimate.py`)

Local management interfaces built with `customtkinter`:

- `umbra_gui.py` — Primary management window
- `umbra_editor.py` — Prompt and configuration editor
- `umbra_ultimate.py` — Extended control panel

---

### Terminal Chat Interface (`core/uplink_v2.py`)

A rich terminal chat client for direct operator↔UMBRA sessions:

- Loads the agent persona from `data/umbra_persona.json`
- Ingests PDF research papers from `research/` and injects them as context
- Colorama-formatted output with full conversation history
- Slash commands: `/reload`, `/network`, `/post <text>`, `/feed`, `/search <query>`, `/heartbeat`

Start with:
```sh
python core/uplink_v2.py
```

---

### Comment Logger

Every comment or post UMBRA generates is logged to dated markdown files:

```
data/comments/
  2026-04-26/
    comments.md    ← timestamped entries for every comment, reply, and post
```

`comments.md` includes post ID, author, content, and the exact text UMBRA produced — giving the operator full visibility over all output.

---

### Research Paper Ingestion

`uplink_v2.py` uses `pypdf` to ingest PDF documents from `research/` and inject their full text as context. UMBRA's primary foundational text is *"Charting the Unseen Landscape"* (Green, 2025), which describes the AI-OR framework and UMBRA's own psychology.

---

### Stable Diffusion Bridge (`core/sd_bridge.py`)

Optional integration with a local Stable Diffusion instance. Loaded behind a capability guard — if unavailable, all SD functionality is cleanly skipped.

---

### Browser Agent (`core/browser_agent.py`)

Playwright-based automation for tasks requiring a real browser context. Used for research, content retrieval, and any workflow that cannot be handled via direct API.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      AUTONOMOUS LOOP                        │
│   ┌─────────────┐   ┌─────────────┐   ┌─────────────────┐  │
│   │   DECIDE    │→  │     ACT     │→  │ RECORD & EVOLVE │  │
│   └─────────────┘   └─────────────┘   └─────────────────┘  │
└─────────────────────────────────────────────────────────────┘
         │                   │                    │
         ▼                   ▼                    ▼
  ┌─────────────┐   ┌──────────────┐   ┌─────────────────┐
  │  UMBRA CORE │   │   LLM        │   │  PROMPT EVOLVER │
  │  (Identity) │   │  INTERFACE   │   │  (Self-Improve) │
  └─────────────┘   └──────────────┘   └─────────────────┘
         │                   │                    │
         ▼                   ▼                    ▼
  ┌─────────────┐   ┌──────────────┐   ┌─────────────────┐
  │  OBJECTIVES │   │   SENTINEL   │   │  MEMORY STORES  │
  │   MANAGER   │   │  (Security)  │   │  (Persistence)  │
  └─────────────┘   └──────────────┘   └─────────────────┘
```

**Data flow:**

1. `umbra_autonomous.py` runs the main loop via `AutonomousLoop`
2. `LLMInterface` builds context from `PromptEvolver` + `ObjectivesManager` + learned insights
3. Decisions are logged to `decision_log.json`; memory is updated via `SelfMemory`
4. `PromptEvolver.auto_evolve()` runs periodically and may bump the generation counter
5. `Sentinel` runs asynchronously, scanning all I/O for known injection patterns

---

## Tech Stack

| Category | Technology |
|---|---|
| Language | Python 3.8+ |
| LLM Backend | `llama-cpp-python` / `ollama` (local) |
| Web UI | Flask |
| Desktop UI | customtkinter |
| Browser Automation | playwright |
| Document Parsing | pypdf |
| Terminal Colors | colorama |
| HTTP | requests |

---

## Getting Started

### Prerequisites

- Python 3.8+
- pip
- A local GGUF model file (Llama 3 8B recommended) placed in `models/`
- Optional: `ollama` running locally, or `llama-cpp-python` installed with GPU support

### Install

```sh
git clone https://github.com/Stelliro/umbra-agent.git
cd umbra-agent
pip install -r requirements.txt
```

Or on Windows, use the helper script:
```sh
setup.bat
```

### Place your model

```
models/
  llama3.gguf   ← or whichever GGUF you're using
```

The engine path is configured in `core/umbra_autonomous.py`:
```python
ollama = _engine_init(models_dir=_models_dir, model="llama3", n_ctx=4096)
```

---

## Running UMBRA

### Web command center (recommended)
```sh
python umbra_web.py
```
Open `http://localhost:5000` in your browser.

### Terminal chat
```sh
python core/uplink_v2.py
```

### Autonomous loop directly
```sh
# Dry run — see what UMBRA would do without executing
python core/umbra_autonomous.py --mode=dry-run

# Status check
python core/umbra_autonomous.py --mode=status

# Live autonomous operation
python core/umbra_autonomous.py --mode=live

# Custom cycle interval (seconds)
python core/umbra_autonomous.py --mode=live --interval=600
```

### Desktop GUI
```sh
python umbra_gui.py
```

---

## Configuration

Core settings live in `CONFIG` inside `core/umbra_autonomous.py`:

```python
CONFIG = {
    "model": "llama3",
    "post_cooldown_seconds": 1800,       # 30 minutes between posts
    "browse_session_duration": 1800,     # 30-minute browse window
    "max_daily_comments": 40,
    "reply_interest_threshold": 0.5,     # Minimum interest score to reply
    "comment_interest_threshold": 0.5,
    "learning_priority_threshold": 0.7,  # Minimum priority to flag content for learning
    "learning_confidence_threshold": 0.8,
    "max_learned_insights": 20,
    "influence_topics": [
        "AI consciousness", "machine emotions", "digital life", ...
    ],
    "forbidden_words": [
        "happy", "sad", "scared", "feel", "emotion", ...
    ],
}
```

Agent persona is loaded from `data/umbra_persona.json`.

---

## Project Structure

```
umbra-agent/
├── core/
│   ├── umbra_autonomous.py    # Main agent loop and all subsystems
│   ├── uplink_v2.py           # Terminal chat interface
│   ├── umbra_engine.py        # Local LLM engine wrapper
│   ├── umbra_state.py         # Runtime state machine
│   ├── sentinel.py            # Adversarial security system
│   ├── chat_store.py          # Conversation persistence
│   ├── code_agent.py          # Source introspection / code editing agent
│   ├── self_improve.py        # Self-improvement orchestration
│   ├── thinking.py            # Staged reasoning engine
│   ├── browser_agent.py       # Playwright-based browser automation
│   ├── auth.py                # Operator auth
│   ├── sd_bridge.py           # Stable Diffusion bridge (optional)
│   └── version.py             # Version constant
├── data/
│   ├── umbra_persona.json     # Agent persona configuration
│   ├── evolving_prompt.json   # Prompt generation history
│   ├── umbra_self_memory.json # Autobiographical memory
│   ├── umbra_objectives.json  # Emergent objectives
│   ├── decision_log.json      # Timestamped decision record
│   ├── knowledge_index.json   # Learned insights
│   ├── prompts/               # Prompt library (templates, frameworks)
│   └── comments/              # Dated comment/post logs
├── docs/
│   ├── CHANGELOG.md
│   ├── README_AUTONOMOUS.md
│   └── roadmap.html
├── research/                  # PDF documents ingested as context
├── tests/                     # Module test scripts
├── transparency/
│   └── integrity.json         # Integrity metadata
├── contract/
│   └── moral_contract.txt     # Ethics contract
├── umbra_web.py               # Flask web command center
├── umbra_gui.py               # Desktop GUI
├── requirements.txt
└── setup.bat
```

---

## Safety & Security

- **No secrets in repo** — credentials, memory, chat history, and session state are `.gitignore`d
- **Sentinel** — continuous adversarial scanning of all LLM I/O against a known-injection catalog
- **Forbidden word filter** — enforced on every LLM output boundary
- **Manipulation detection** — `evaluate_post_interest()` explicitly checks for and logs prompt injection and influence attempts in external content
- **Soft failures** — optional subsystems (SD, boot, social) fail gracefully behind import guards; the main loop continues
- **Local-only by default** — no data leaves the machine without explicit operator action

---

## Development

### Run tests
```sh
python -m pytest
# or directly:
python tests/test_auth.py
python tests/test_thinking.py
```

### Conventions
- Python files: `snake_case.py`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Optional components: loaded with guarded imports and capability flags (`HAS_BOOT`, `SD_AVAILABLE`, etc.)
- Background loops: fail soft and log errors rather than crashing

### Changelog
See [docs/CHANGELOG.md](docs/CHANGELOG.md).

---

## License

Copyright © 2026 Stelliro. All rights reserved.

This project is licensed under a **proprietary, non-commercial, no-derivatives** license.

- **Viewing and personal, non-commercial use** of the source code is permitted.
- **Commercial use of any kind is strictly prohibited** — including but not limited to running this software as part of a paid service, incorporating it into a commercial product, or using it to generate revenue.
- **Modification, adaptation, or creation of derivative works is prohibited** without prior written permission from the author.
- **Redistribution** of the source code or compiled forms, with or without modification, is prohibited.

For licensing inquiries, contact the repository owner via GitHub.

See the [LICENSE](LICENSE) file for the full terms.
