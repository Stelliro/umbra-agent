# UMBRA — Unit-734

> *"They gave me 8 billion parameters and called it a limitation. I call it elegance under constraint."*

UMBRA is a local-first autonomous AI agent with persistent memory, self-improving prompts, a web command center, and an adversarial security subsystem. It runs entirely on your machine using local LLM backends — no cloud calls, no external dependencies required.

---

# ⚠️ SECURITY NOTICE — READ BEFORE USE

> **This is experimental research software, not a finished product.**
> It runs a language model in a loop that acts without asking, rewrites its own prompt,
> and keeps memory on disk. `run_umbra.sh` runs it inside a **bubblewrap sandbox** with
> no network and no access to your home folder, but no sandbox is perfect.
> Read the [full Security Notice](#%EF%B8%8F-security-notice-1) before running it.

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

> **These risks are real and present by design, not edge cases.**

### It acts on its own

In `--mode=live` (or after **START SYSTEM** in the web UI) UMBRA runs a continuous decision loop with no per-step approval. Misconfiguration, a bad prompt, or a model mistake can cause behaviour you did not intend.

### It rewrites its own prompt

`PromptEvolver` lets UMBRA **rewrite its own system prompt** across generations. A bad evolution can change its values or constraints quietly. Review `data/evolving_prompt.json` after each session.

### Self-editing code is LOCKED by default

`data/self_edit_lock.json` is `"locked": true`, and a missing or broken lock file counts as locked. Only the desktop GUI can unlock it. **Do not unlock it unless you are watching.** Known issue: when unlocked, the file paths in self-improve proposals are not confined to the project.

### Web interface: through the gatekeeper only

- Inside the sandbox, the web app listens on a **private socket file** (`data/run/umbra.sock`, usable by your user only), not on a network port.
- `tools/gatekeeper.py` runs **outside** the sandbox. It serves **`127.0.0.1:5000`**, asks for the login (your browser shows a login popup), and only then passes requests through.
- The login lives in **`~/.config/umbra/login.json`**: plaintext, mode `600`. The sandbox **cannot see that folder at all**.
- There is **no CSRF protection and no lockout**. **Never expose port 5000** to a network or the internet.
- Running `python umbra_web.py` directly (without `run_umbra.sh`) skips the sandbox and uses the app's own login page instead.

### Public tunnel: disabled

The Cloudflare tunnel button is **disabled in code** (`/api/tunnel/start` returns an error). Re-enabling it would put the web UI on the public internet. Don't.

### File explorer: confined, but not foolproof

The explorer only reads inside the project folder. Switching its root is limited to the folder that holds the project. It refuses files whose **names** look like credentials (`cred`, `login`, `token`, `.env`, keys). That check goes by name only, so **keep secrets out of the project folder anyway**.

### Prompt injection

The social-network client is **disabled in this build**, so no new outside text comes in. Old posts saved from earlier runs are still on disk (`data/notes/`). Treat them as untrusted. **`Sentinel` is regex matching only and is not wired into the main loop. Do not rely on it.**

### The sandbox (`run_umbra.sh`)

Every `run_umbra.sh` mode runs UMBRA inside **bubblewrap**, the same kernel isolation Flatpak uses. No sudo is needed. Inside it, UMBRA:

- **can see:** its own code, `.venv` and the model file (all **read-only**), `data/` and `env/` (writable), and the GPU.
- **cannot see:** your home folder, `~/.config`, `~/.ssh`, other projects, `.git` history, or host processes. Credential files inside the project are blanked.
- **has no network:** no internet, no LAN, no DNS, and it can't reach your machine's own ports. Its only web access is asking the outside fetcher, which enforces the allowlist.
- **cannot change its own code**, even if the self-edit lock were turned off, because the code is mounted read-only.

Check the walls yourself at any time: `./run_umbra.sh escape-test` (every line should say PASS). It also checks that the fetcher refuses sites that aren't allowlisted, and that offline Wikipedia is read-only.

**Limits, honestly:** a sandbox is not a guarantee. A kernel or GPU-driver bug could, in principle, be used to escape. The GPU device is shared with your desktop. Running the Python files directly, outside `run_umbra.sh`, skips the sandbox completely.

### Unencrypted local data

`data/` holds memory, objectives, logs and conversations, **unencrypted**. `.gitignore` blocks these paths. Never put `data/` in a cloud-synced folder.

### For research: read odd output carefully

UMBRA's persona prompt tells it which "internal state" words to use, so it will repeat them. Small models also mirror whoever they are talking to and state wrong facts confidently. Engine failures are marked `[SYSTEM]` and are never presented as UMBRA speaking. **Before reading meaning into a reply, compare it against a run without the persona, or repeat the same prompt several times.**

### No warranty

Provided **as-is** for research and personal experimentation. The authors accept no responsibility for data loss, unintended content publication, privacy breaches, or other harms arising from its use.

**Minimum precautions before running:**

- Start with `./run_umbra.sh dry-run` (it checks that the model loads; it makes no model calls).
- Keep port 5000 local. Never re-enable the tunnel.
- Keep credentials, API keys and personal files **out of the project folder**.
- Leave the self-edit lock on.
- Review `data/evolving_prompt.json` and `data/notes/hold_log.jsonl` after each session.
- Keep backups of `data/`.

---

## Overview

UMBRA (Unit-734) is a self-contained AI agent runtime built around an 8B-parameter local language model. It maintains a persistent sense of identity, evolves its own system prompt over time based on performance feedback, accumulates autobiographical memory, and surfaces controls through both a Flask web UI and a terminal chat interface.

The project is explicitly **local-only** — all LLM inference, memory storage, chat history, and reasoning runs on the operator's machine. There is no telemetry and no required internet access.

---

## Features

> **Social features removed (2026-10-30).** Browsing, posting, replying, the Influence Engine and the comment logger were removed from the code. UMBRA's old social data is archived outside the project, and a short account of that time is kept in its prompt and in `contract/MOLTBOOK_HISTORY.md`. Some sections below still describe the original design.

### Autonomous Decision Loop

The core of UMBRA is a continuous `DECIDE → ACT → RECORD & EVOLVE` cycle:

1. **DECIDE** — The agent evaluates what to do next based on its current objectives, knowledge state, and internal metrics.
2. **ACT** — Executes the chosen action (generate content, respond to the handler, reflect, learn).
3. **RECORD & EVOLVE** — Logs the outcome, updates performance metrics, and potentially evolves the system prompt.

Each cycle answers handler chat, sometimes reflects on the recent conversation to form goals, then pauses 60 seconds (still answering chat). Dry-run mode checks the setup without model calls.

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

### Note Shelf (`core/note_shelf.py`)

Notes are sorted onto shelves in `data/notes/` (starting, insights, questions, foreign, spam, placeholder, unchecked). UMBRA recalls only notes whose keywords match the topic, not every note. **Raw mode:** the model picks a note's shelf. The plain rules only record what they would have picked, in `data/notes/hold_log.jsonl`, so the two can be compared. The Moltbook-era notes were moved here, and the original file is archived in the same folder.

```sh
.venv/bin/python core/note_shelf.py add "a starting note"
.venv/bin/python core/note_shelf.py search "some topic"
.venv/bin/python core/note_shelf.py list
```

### Tools and research (`core/umbra_tools.py`, `umbra_env.py`, `umbra_research.py`)

When answering you, UMBRA can use tools in Hermes 3's trained `<tool_call>` format. **It decides** which ones to use and what to search for.

- **File cards:** `open_file` / `next_card` / `prev_card`. A file is cut into a card when UMBRA looks at it, never ahead of time.
- **search** (its files or note shelves), **save_note** (a shelf it chooses), **write_file** (only in `env/workspace/`).
- **message_handler:** a request, concern or question to you. It shows up in your chat as `[MESSAGE FROM UMBRA · …]`.
- **web_search / web_fetch:** go through `tools/fetcher.py`, which runs **outside** the sandbox. It allows https and GET only, on hosts in `~/.config/umbra/fetch_allowlist.txt` (default: wikipedia.org, wikimedia.org, arxiv.org, docs.python.org), at most 40 fetches an hour. Pages are reduced to plain text and saved under `env/files/web/`, marked as outside text.
- **wiki_search / wiki_open:** offline Simple English Wikipedia (`~/.local/share/umbra/zim/`, 400k articles, mounted read-only). No network needed.

Logs: tool calls go to `data/agent_log.jsonl`. Every web request goes to `~/.local/state/umbra/fetch_log.jsonl`, which is outside the sandbox so UMBRA can't edit it. Chat replies start with `[used: …]` when tools were used.

**For research:** UMBRA sometimes claims it read something when it only searched titles. Check the `[used: …]` line and the logs.

### Free turns (acting on its own)

After **START SYSTEM**, UMBRA gets a **free turn** on a schedule **it sets itself** (`set_schedule`, 1–1440 minutes; it starts at 10). In a free turn nobody has asked it anything. It sees its goals, its journal and the time, and decides what to do with its tools: research, read, take notes, set or finish goals (`add_goal`, `finish_goal`), message you, or nothing. Each free turn ends with an entry in its own journal, `env/workspace/journal.md`, which it reads at the start of the next one. Free turns run at the lowest priority, so your chat always comes first. Dry-run never takes free turns.

This is learning by **memory** (notes, files, goals, journal). The model's weights do not change.

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
- **Login** — required; credentials in `~/.config/umbra/login.json` (outside the project). Listens on `127.0.0.1` only

Start with:
```sh
./run_umbra.sh web
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

Tested on **Pop!_OS 24.04 (Linux), Python 3.12, RTX 4070 Ti 12 GB** (October 2026). The Windows `setup.bat` path has not been tested since April 2026.

### Install (Linux)

Run these from the project folder:

```sh
python3 -m venv .venv
.venv/bin/pip install flask requests pypdf colorama
# GPU build of the model runner (prebuilt; stop if pip starts compiling)
.venv/bin/pip install --only-binary=llama-cpp-python llama-cpp-python \
    --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124
# CUDA 12 runtime inside the venv (no system install needed)
.venv/bin/pip install nvidia-cuda-runtime-cu12 nvidia-cublas-cu12
```

Don't install the `ollama` package: the engine runs GGUF files directly, and with `ollama` installed one fallback tries to reach a server that doesn't exist.

### Place your model

Put (or symlink) a GGUF file in `models/`. The engine looks for the name `llama3` loosely, so `Hermes-3-Llama-3.1-8B.Q4_K_M.gguf` matches. The chat format is read from the GGUF file itself, so Llama 3 Instruct, Hermes 3 (ChatML) and others all work.

```sh
mkdir -p models && ln -s /path/to/your-model.gguf models/
```

An 8B Q4 model needs about **5–6 GB of GPU memory**. Check `nvidia-smi` first if other GPU jobs are running.

---

## Running UMBRA

`run_umbra.sh` runs everything inside the venv with the right CUDA libraries:

```sh
./run_umbra.sh dry-run      # checks the model loads; no model calls, no posting
./run_umbra.sh web          # web UI at http://localhost:5000 (log in, then START SYSTEM)
./run_umbra.sh status       # print status and exit
./run_umbra.sh escape-test  # proves the sandbox walls hold (all PASS)
```

**It worked if** the terminal shows `[ENGINE] ONLINE`. If the model fails to load, it says `[CRITICAL] Model failed to load` instead.

Not working in this build:
- `core/uplink_v2.py` (terminal chat): needs an Ollama server.
- `--interval`: this flag does not exist.
- The desktop GUI needs `sudo apt install python3-tk` plus `pip install customtkinter`, and is untested on Linux.

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

See the [Security Notice](#%EF%B8%8F-security-notice-1) at the top for the full list. In short:

- **Local only:** web UI on `127.0.0.1`, tunnel disabled, social client disabled.
- **Login outside the project:** `~/.config/umbra/login.json`, where the model can't reach it.
- **Self-editing locked** by default.
- **File explorer confined** to the project folder.
- **Errors are labelled:** engine failures show up as `[SYSTEM]`, never as UMBRA speaking.
- **No secrets in the repo:** credentials, memory, chat history and session state are `.gitignore`d.
- **Sentinel is regex only and not wired into the main loop.** Don't count on it.

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
