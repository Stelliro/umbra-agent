# CODEBASE INDEX - UMBRA UMBRA

> Single source of truth for project structure, conventions, and architecture.
> Last updated: 2026-04-26 (created initial index from current repository state)

---

## 1. Project Overview

UMBRA UMBRA is a local-first autonomous AI workstation that combines an agent runtime, chat memory, safety systems, and a Flask web command center.

- Type: Desktop-local AI automation and web control app
- Primary Language(s): Python
- Key Frameworks / Libraries: Flask, customtkinter, requests, ollama, llama-cpp-python, playwright
- Target Platform(s): Windows-first local runtime (cross-platform Python code in many modules)
- Current Version: 0.8.0 (core/version.py)
- Status: Alpha / Active Development

### Goals
- Run an autonomous local AI loop with operator controls and safety checks.
- Provide chat, memory, and code-agent workflows through a web UI and local tools.

### Non-Goals (explicit out-of-scope)
- Public cloud-native deployment as the default mode.
- Production-hardened multi-tenant SaaS behavior.

---

## 2. Repository Structure

```
UMBRA/
|- .github/
|  |- copilot-instructions.md
|  |- instructions/
|  |- CODEBASE_INDEX_TEMPLATE.md
|- contract/                    # ethics/transparency contract assets
|- core/                        # main runtime modules and agent systems
|- data/                        # local runtime state, logs, memory, and indexes
|- docs/                        # roadmap/changelog/reference docs
|- library/                     # auxiliary local assets
|- models/                      # local model files
|- research/                    # research/source materials
|- tests/                       # python tests
|- transparency/                # integrity artifacts
|- umbra_web.py                 # Flask command center entrypoint
|- umbra_gui.py                 # customtkinter local GUI
|- setup.bat                    # local setup helper
|- requirements.txt             # Python dependencies
|- CODEBASE_INDEX.md            # this file
```

### Key Modules

#### Web Command Center

- Files: umbra_web.py
- Purpose: Main Flask app with chat endpoints, dashboard, auth hooks, tunnel/improve orchestration hooks, and code explorer integration.
- Key API: /api/chats, /api/control, /api/dashboard, /api/agent/*
- Consumers: Browser clients, local operators
- Dependencies: core/chat_store.py, core/code_agent.py, core/auth.py, core/umbra_autonomous.py
- Design Notes: Local-first architecture; many optional features loaded behind import guards.

#### Autonomous Runtime

- Files: core/umbra_autonomous.py, core/startup_sequence.py, core/umbra_engine.py, core/umbra_integration.py
- Purpose: Core loop planning/execution, model orchestration, startup checks, runtime behavior.
- Key API: AutonomousLoop, startup sequencing utilities
- Consumers: umbra_web.py, umbra_gui.py, automation scripts
- Dependencies: state/memory/safety modules in core and data stores in data/
- Design Notes: Loop is expected to run continuously and expose chat/system controls.

#### Chat and Memory Store

- Files: core/chat_store.py, data/chats/*, data/*index*.json
- Purpose: Conversation persistence, indexing, retrieval, context assembly.
- Key API: create_chat(), add_message(), get_messages(), search(), context retrieval helpers
- Consumers: umbra_web.py and runtime layers
- Dependencies: local filesystem JSON data
- Design Notes: Data is file-backed and intended for local persistence.

#### Safety and Integrity

- Files: core/sentinel.py, core/umbra_boot.py, transparency/integrity.json, contract/*
- Purpose: Injection/threat monitoring, startup integrity checks, transparency contract scaffolding.
- Key API: sentinel scans, boot checks, integrity metadata usage
- Consumers: startup and runtime orchestration
- Dependencies: data memory/index files, contract/transparency artifacts
- Design Notes: Safety checks are integrated into startup/evaluation phases.

#### Code Agent and Self-Improvement

- Files: core/code_agent.py, core/self_improve.py, core/thinking.py, core/browser_agent.py
- Purpose: Source exploration/edit support, staged reasoning, test/improvement orchestration.
- Key API: CodeAgent methods, ThinkingEngine chain methods, SelfImproveOrchestrator
- Consumers: umbra_web.py and operator workflows
- Dependencies: LLM backend adapters and local repo files
- Design Notes: Feature availability is often conditional on optional dependencies.

---

## 3. Technology Stack

| Category | Technology | Version | Notes |
|---|---|---|---|
| Language | Python | 3.8+ expected | setup.bat checks Python presence |
| Runtime | Local Python process | N/A | Windows-focused ops scripts |
| Web Framework | Flask | from requirements | command center UI/API |
| Desktop UI | customtkinter | from requirements | local management UI |
| LLM Interface | ollama, llama-cpp-python | from requirements | model execution/integration |
| Browser Automation | playwright | from requirements | browser agent tasks |
| Networking | requests | from requirements | service/API calls |
| Document Parsing | pypdf | from requirements | research/document ingestion |
| Testing | Python test scripts | repo local | tests/ contains module tests |

---

## 4. Coding Conventions

### Naming
- Python files/modules: snake_case.py
- Classes: PascalCase
- Functions/variables: snake_case
- Constants: UPPER_SNAKE_CASE

### File and Module Organization
- Runtime logic is concentrated in core/.
- Persistent state and local operational data live in data/.
- Web entrypoint remains top-level in umbra_web.py.
- Tests are grouped in tests/ and target core behavior.

### Error Handling
- Optional components are loaded with guarded imports and capability flags.
- Runtime and background-loop code should fail soft and preserve operator visibility in logs/UI.

### Testing
- Tests exist as standalone Python test modules in tests/.
- Prioritize regression tests around runtime loop, auth, browser agent, self-improve, and thinking subsystems.

### Commit Style
- Keep commits scoped and descriptive.
- For operational cleanups, include explicit artifact categories removed/changed.

---

## 5. Key Design Documents

| Document | Location | Description |
|---|---|---|
| Autonomous System README | docs/README_AUTONOMOUS.md | overview of autonomous architecture and operations |
| Project Changelog | docs/CHANGELOG.md | version and feature history |
| Roadmap | docs/roadmap.html | roadmap visualization and phase planning |
| Moral Contract | docs/moral_contract.txt | ethics/contract text |
| Transparency Integrity | transparency/integrity.json | integrity metadata history |

---

## 6. Build and Run Instructions

### Prerequisites
- Python 3.8+
- pip
- Optional local model/runtime dependencies for full features (ollama/llama backends)

### Setup
```sh
git clone <repo-url>
cd UMBRA
python -m pip install -r requirements.txt
```

Optional helper script (Windows):
```sh
setup.bat
```

### Development
```sh
python umbra_web.py
```

Optional local GUI:
```sh
python umbra_gui.py
```

### Tests
```sh
python -m pytest
```

If pytest is not configured in environment, run direct module tests from tests/ as needed.

### Production Build
- No dedicated packaged production build pipeline currently documented.
- Standard operation is local process execution.

---

## 7. Domain-Specific: Runtime Data Model (Local Files)

- data/chats/: per-chat JSON conversations
- data/logs/: runtime log outputs
- data/*index*.json: knowledge/threat/post/chat indexes
- data/session_state.json and related files: runtime local state snapshots

Operational rule: treat data/ as runtime-local unless a specific file is intentionally versioned for schema/reference purposes.

---

## 8. Migration Notes

| Date | Change | Migration |
|---|---|---|
| 2026-04-26 | Initial CODEBASE_INDEX created | No runtime migration required |

---

## 9. Known Issues and Limitations

| Issue | Severity | Notes |
|---|---|---|
| CODEBASE_INDEX did not previously exist | Low | Now added at repository root |
| Some optional features depend on local runtime/model availability | Medium | Features degrade when imports/dependencies are missing |
| Documentation and runtime have mixed legacy/current references | Medium | Prefer current entrypoints and validate paths before automation |
