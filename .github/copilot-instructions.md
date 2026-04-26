# Copilot Workspace Instructions

> **Mandatory. Execute in order. No skipping.**
> This template applies to any project type: games, web apps, desktop apps, APIs, tools, or libraries.
> Replace all `[PLACEHOLDER]` values with project-specific details.
> Domain-specific rules live in `.github/instructions/` — loaded automatically by file type.

---

## Step 1: Read Priority Context (FIRST)

1. Read `CODEBASE_INDEX.md` at workspace root **before** any other work.
2. Read any referenced instruction files relevant to the affected modules.
3. It is the **single source of truth** for structure, conventions, and architecture.
4. Never assume — verify against the index.

## Step 2: Understand the Request

1. Read the **entire** prompt. Identify affected files, modules, and dependencies.
2. Cross-reference against documented conventions.
3. If ambiguous or conflicting, **ask before proceeding**.

## Step 3: Plan Before Coding

1. Outline: files to create/modify/delete, conventions, side effects, breaking changes.
2. Must not violate documented conventions.
3. For large/risky changes, propose incremental steps and confirm.

## Step 4: After Every Change

1. Update `CODEBASE_INDEX.md` if structure, conventions, or architecture changed.
2. Update `CHANGELOG.md` — add a brief entry under `[Unreleased]` for every functional change. Skip for doc-only or formatting-only edits.
3. Update related files — consumers, tests, docs, configs.
4. New convention? Create an instruction file in `.github/instructions/`, reference it in the index.

## Step 5: Validate & Self-Review

- Mental dry-run: happy path + edge cases. Check boundaries and type alignment.
- Code follows conventions. Errors handled explicitly. No secrets. No dead code.
- Codebase left in a valid, consistent, buildable/runnable state.

---

## Core Principles

- **When in doubt, ask.** Consistency over cleverness. Security first.
- **Atomic changes** — every response leaves the codebase valid.
- **Explicit over implicit** — types, config, returns, error handling.
- **Respect boundaries** — no circular dependencies or architectural violations.
- **Never skip doc updates.** Stale docs are worse than none.

---

## Agent Routing

Specialist agents live in `.github/agents/`. Each has an **Agent ID** for changelog attribution.
When a task clearly falls into one domain, delegate to or switch to the appropriate agent.
Multi-domain tasks may chain agents.

> **Instructions:** Replace the table below with agents relevant to your project.

| Agent | ID | Use When |
|---|---|---|
| **CoreArchitect** | `ARCH` | App entry point, system wiring, initialization, main loop/lifecycle |
| **FrontendDev** | `FE` | Components, pages, layouts, styles, client-side state |
| **BackendDev** | `BE` | APIs, services, business logic, server config, middleware |
| **DataLayer** | `DATA` | Schemas, migrations, queries, ORMs, caching, seed data |
| **GameplaySystems** | `GPLAY` | Game mechanics, progression, simulation, rules engine |
| **RenderSpecialist** | `RNDR` | Shaders, render pipelines, graphics, visual effects |
| **AIBehavior** | `AIBT` | NPC AI, agents, pathfinding, behavior trees, decision logic |
| **UINavigator** | `UI` | Menus, HUD, settings screens, forms, modals, accessibility |
| **BuildEngineer** | `BILD` | Build system, package management, CI/CD, Docker, scripts |
| **AssetForge** | `ASST` | Art assets, content files, serialization pipelines, media |
| **AudioForge** | `AUDI` | Audio engine, music systems, SFX, mixing, spatial audio |
| **PhysicsForge** | `PHYS` | Physics simulation, collision, rigidbodies, constraints |
| **SecurityAudit** | `SEC` | Auth, authz, input validation, secrets, OWASP concerns |
| **DocKeeper** | `DOCS` | CODEBASE_INDEX, CHANGELOG, READMEs, design docs |
| **FastRefactor** | `RFCT` | Renaming, extracting, moving code, dead code removal |
| **ToolSmith** | `TOOL` | Dev tools, CLI scripts, diagnostic utilities, generators |
| **LowTokenMode** | `LO` | Quick fixes, minimal output, context conservation |

### Changelog Attribution

Every `CHANGELOG.md` entry under `[Unreleased]` must be prefixed with the agent ID:
```
- [ARCH] Added FooSystem to App initialization
- [FE] Fixed button overflow on mobile viewport
- [BE] Refactored UserService to use repository pattern
```

### Multi-Agent Tasks

When a task spans multiple domains, the primary agent coordinates and delegates sub-tasks. The changelog entry uses the primary agent ID.
