---
description: "Agent routing rules — how to assign work to specialist agents, define Agent IDs, and attribute CHANGELOG entries. Universal template."
---

# Agent Routing

## Purpose

Specialist agents are domain experts. Routing work to the right agent ensures consistent quality, focused context loading, and accurate changelog attribution.

## How To Route

1. Identify the primary domain of the requested change.
2. Consult the agent table in copilot-instructions.md.
3. If the task clearly belongs to one domain, delegate to or switch to that agent.
4. If the task spans domains, the primary agent (the one handling the most critical change) coordinates and delegates sub-tasks.
5. Always record the responsible agent ID in the CHANGELOG.md entry.

## Agent ID Rules

- IDs must be 2-5 uppercase letters.
- IDs must be unique — no two agents share an ID.
- IDs are permanent once used in a CHANGELOG entry.
- Add project-specific agents by appending rows to the table in copilot-instructions.md.

## Universal Agent Table (Starting Point)

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

## Changelog Attribution Format

```
## [Unreleased]

### Added
- [ARCH] Wired PaymentService into App initialization
- [BE] Added POST /api/orders endpoint with idempotency key support
- [FE] Added OrderConfirmation page

### Fixed
- [DATA] Fixed migration 0014 failing on existing NULL rows
- [SEC] Sanitized user-supplied filename before disk write

### Changed
- [UI] Redesigned checkout flow — 3 steps collapsed to 1

### Removed
- [RFCT] Deleted deprecated LegacyAuthHelper
```

## Multi-Agent Changelog

When a task spans domains, use the primary agent ID and list all affected areas:
```
- [ARCH] Integrated NotificationSystem — wired BE service + FE toast component + DATA schema migration
```
