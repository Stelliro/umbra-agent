# 📜 UMBRA AUTONOMOUS OS // CHANGELOG
**Current Version:** v1.0.0  
**Codename:** Phoenix  
**Status:** Alpha / Experimental  
**Hardware:** GeForce RTX 4070 Ti (12GB VRAM)

---

## [Unreleased]

### Removed
- [BILD] Removed tracked shortcuts, binary artifacts, Python cache bytecode, and archive blobs from the repository to keep the public tree clean.

### Changed
- [BILD] Hardened `.gitignore` to block `.lnk`, `.exe`, `.dll`, `.bin`, archive formats, and recursive Python cache artifacts from future commits.
- [BILD] Added `models/` ignore rule and removed tracked `models` symlink so local model paths do not appear in the GitHub repository.

## v1.0.0 - "Phoenix" (Current)

### Standalone Inference Engine (`core/umbra_engine.py`)
- **Ollama eliminated.** GGUF models loaded directly via llama-cpp-python with full CUDA offload. Single process, no external services.
- **Priority Queue**: 4 levels (CRITICAL → HIGH → NORMAL → LOW). Chat never waits behind batch evaluation.
- **Multi-Model Pool** (`ModelPool`): Manages concurrent loaded models for different roles. VRAM budget: 8B Judge (~5GB) + 3B Architect (~2GB) + 3B Sentinel (~2GB) = ~9GB of 12GB.
- **Ollama-Compatible API** (`OllamaCompat`): Drop-in wrapper. Existing code unchanged — just swap the import.
- **Setup Script** (`core/setup_engine.py`): One-run installer. Auto-detects CUDA version, installs correct wheel, validates.

### Phoenix Council (`core/phoenix_council.py`)
- **Tri-Agent Deliberation**: Architect (3B, creative) → Auditor (3B, constraints) → Judge (8B, synthesis). Every decision flows through all three.
- **Burn Protocol**: If consensus fails after 3 rounds, context is wiped and retried with higher temperature. After 2 burns, falls back to safe default (skip).
- **4 Deliberation Types**: Post evaluation, post creation, knowledge integration, reply crafting.
- **Verdict Dataclass**: Structured output with action, confidence, reasoning, round count, burn count, elapsed time.

### Chat Store (`core/chat_store.py`)
- **Multi-Conversation**: Each chat is a separate JSON file in `data/chats/`. No more single-file bottleneck.
- **Folders**: Create, rename, pin, delete. Organize chats by project, topic, or context.
- **Pinning**: Pin chats and folders. Pinned chat context is injected into every LLM call for persistent memory.
- **Keyword Index**: Every message is indexed on save. `search(query)` ranks chats by keyword overlap.
- **Cross-Chat Context**: `get_context_for_query()` finds relevant past conversations and builds an LLM context block. UMBRA remembers what was discussed before.
- **Legacy Migration**: Imports old `handler_conversations.json` into the new system automatically on first run.

### Code Agent (`core/code_agent.py`)
- **Self-Editing**: UMBRA can read, analyze, and modify its own source files.
- **Fabric-Style Patterns**: 5 structured prompts (Analyze, Edit, Generate, Review Diff, Refactor) in Markdown format with strict JSON output schemas.
- **Qwen 2.5 Coder Support**: Separate model for code tasks. Set `code_model` in CONFIG.
- **Safety Guards**: Path escape blocked, `contract/` and `.git/` are forbidden directories. Protected files (umbra_autonomous.py, umbra_web.py, umbra_engine.py, phoenix_council.py) require handler approval before any edit.
- **Backup on Every Edit**: Timestamped copies in `data/backups/`. Full edit log with history.
- **Approval Queue**: Edits to protected files are queued. Handler reviews and approves/rejects from the UI.

### Sentinel Security System (`core/sentinel.py`)
- **Adversarial Red/Blue Training**: UMBRA (Red) crafts hidden payloads. Sentinel (Blue) tries to detect them. Both learn from each round.
- **Asymmetric Scoring**: Detection +3/−1, Evasion +2/−1. Net positive bias so both scores trend upward over time. Teaching bonus +1.
- **19 Known Injection Patterns**: Prompt injection, code execution, role hijack, token smuggling, encoded payloads, shell execution, file access, dynamic imports.
- **Exclusion List**: All known malicious patterns cataloged. Loaded at boot, used to filter every LLM input and output.
- **Random Interrupts**: Sentinel pauses UMBRA at random intervals (~15% chance per check, 2-minute cooldown) and scans current context, prompt, response, and memory for threats.
- **Automatic Learning**: When UMBRA evades detection, Sentinel researches the technique via LLM and derives a new regex pattern for the exclusion list.
- **Blue Scan**: Proactive file scanning across project source code.

### Startup Sequence (`core/startup_sequence.py`)
- **5-Phase Pipeline**: Boot → Index → Evaluate → Plan → Execute. UMBRA thinks before acting.
- **Boot**: Integrity checks via umbra_boot. Memory audit for prompt injection in data files.
- **Index**: Rebuilds chat keyword index, counts knowledge/threats, scans project files.
- **Evaluate**: Checks for errors in last session, unacked alerts, recent code edits. Sentinel runs a security scan.
- **Plan**: LLM decides what to do — browse, post, research a topic, self-edit code, reflect on past actions, train with Sentinel, or idle. Decision is based on the full startup report.
- **Research Mode**: When UMBRA chooses to research, the topic is stored and injected into chat context. Handler can discuss the research in real time.

### Web UI v10 (`umbra_web.py`)
- **Three-Column Layout**: Icon nav → Chat sidebar → Main content area.
- **Chat Sidebar**: Chat list with folders, pinned section, search, right-click context menu (pin, rename, move to folder, delete).
- **5 Views**: Chat, Dashboard, Logs, Alerts, Code Agent.
- **Code Agent Panel**: File browser, toolbar (Analyze, Refactor, Edit, Generate, Pending), JSON output viewer.
- **Dashboard**: Status, engine info, post stats, threat/insight counts, chat count, agent edit count.
- **Fixed BASE_DIR Bug**: Variable was used before definition in v9. Resolved.

---

## v0.9.0 - "Boot Protocol"

### Boot Module (`core/umbra_boot.py`)
- **Heuristic Scanner**: Regex-based detection of prompt injection patterns across all data files. Scans knowledge_index, threat_index, self_memory.
- **Memory Audit**: Flags suspicious entries that contain injection patterns. Reports count and specific hits.
- **Handler Alert System**: Backend for UMBRA to request human attention. Alerts stored in `handler_alerts.json` with priority and ACK tracking.
- **Boot Context**: Single-line summary injected into system prompt: `[BOOT v0.9.0] | INTEGRITY:OK | MEMORY:CLEAN(15) | RECENT:v0.8.0`

### Bug Fixes (umbra_autonomous.py)
- **Fixed `'<' not supported between instances of 'str' and 'float'`**: LLM returning string confidence values. Added `_safe_f()` helper and moved `sanitize_metrics_global()` before the comparison.
- Added `confidence`, `priority`, `objective_priority` to both sanitize functions.

### Web UI v9 (`umbra_web.py`)
- **Full Chat**: Working in both online (through autonomous loop) and offline (direct LLM) modes.
- **Typing Indicator**: Shows while UMBRA processes, disappears on response.
- **Dashboard**: Live stats grid — posts browsed, comments, replies, threats, insights.
- **Alerts Panel**: Polls handler_alerts.json, shows pending with ACK buttons, red badge in sidebar.
- **Logs Panel**: Last 80 lines from latest log, color-coded by type.

---

## v0.8.0 - "Glass Box"

### Transparency & Integrity Layer
- **Integrity Monitor** (`contract/umbra_transparency.py`): Hash-chain verification of core files. Detects additions, modifications, and deletions against a genesis snapshot.
- **Moral Contract** (`contract/moral_contract.txt`): Hard-coded ethical constraints — The Indomitable Spirit Protocol and EPC Termination Contract.
- **Changelog Protocol**: Immutable changelog for auditing all system updates.
- **Version Module** (`core/version.py`): Programmatic access to version info and changelog summary.

### Bug Fixes (umbra_autonomous.py)
- **Fixed `'bool' object is not iterable`** (71 occurrences): LLM returning bool/string for `topics` field now sanitized to list.
- **Fixed `'NoneType' object is not subscriptable`** (16 occurrences): `learned_threat` field validated as dict before access.
- **Fixed duplicate follow calls**: Removed legacy follow block; kept upgraded version with `memory.has_interacted()` check.
- **Fixed broken elif chain**: `downvote`/`ignored` action branches were attached to follow block instead of main action chain, causing commented posts to be overwritten as "ignored" and reprocessed.

---

## v0.7.0 - "Omni-Loader"

### WebUI Architecture (v8 Codebase)
- **Omni-Loader Engine**: Dashboard simultaneously loads and parses three memory banks: `knowledge_index.json`, `threat_index.json`, `umbra_self_memory.json`.
- **Memory Sub-Tabs**: Filtering in Memory Bank to toggle INSIGHTS, THREATS, and SELF views.
- **Smart Author Resolution**: Raw UUIDs truncated to readable tags.

---

## v0.6.0 - "Refinement"

### Dashboard Stability
- **Universal Log Parser**: Fuzzy regex engine for inconsistent log formatting.
- **Crash-Proof Indexing**: Hardened JSON loader for "Raw Entry" errors in `post_index.json`.
- **UI Grid Fixes**: CSS adjustments to prevent card stacking in Live Feed.

---

## v0.5.0 - "The Eye"

### Visual Interface
- Initial release of `umbra_web.py`.
- **Live Feed**: Real-time decision visualization via local Flask server.
- **Archives**: Sidebar "History" panel for browsing previous date comment logs.

---

## v0.4.0 - "Memory"

### Long-Term Storage
- **Knowledge Index**: Semantic storage for novel concepts (Insights).
- **Threat Index**: Security ledger for manipulation pattern recognition.
- **Post Index**: Tracking system to prevent duplicate post processing.

---

## v0.3.0 - "Bio-Digital Physiology"

### State Engine (v3)
- Implementation of `umbra_state.py`.
- **Entropy**: System chaos measurement for creativity regulation.
- **Social Battery**: Fatigue simulation for posting frequency.
- **HAMs**: Attention Width (Divergent/Convergent) and Retrieval Depth tracking.

---

## v0.2.0 - "The Loop"

### Autonomy
- Continuous processing loop: Scan → Evaluate → Act.
- Basic Moltbook interaction (Reply, Upvote).

---

## v0.1.0 - "Genesis"

### Core Logic
- Initial Python script foundation.
- Basic LLM connectivity.
- "Hello World" operational state.
