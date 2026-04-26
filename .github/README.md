# Universal Copilot Workspace Template

A plug-and-play set of GitHub Copilot instruction files for any project type — games, web apps, desktop apps, APIs, CLI tools, and libraries.

---

## What Is Included

```
_UNIVERSAL_TEMPLATES/
├── README.md                                          <- This file
├── CODEBASE_INDEX_TEMPLATE.md                         <- Single source of truth template
├── CHANGELOG_TEMPLATE.md                              <- Keep a Changelog format with agent IDs
└── .github/
    ├── copilot-instructions.md                        <- Master AI agent instructions
    └── instructions/
        ├── documentation.instructions.md              <- CODEBASE_INDEX + CHANGELOG rules
        ├── feature-pipeline.instructions.md           <- 9-step feature pipeline + sub-pipelines
        ├── implementation-standards.instructions.md   <- Security, quality, testing, compatibility
        └── agent-routing.instructions.md              <- Agent ID system + routing rules
```

---

## Quick Setup (New Project)

**Step 1** — Copy the `.github/` folder into your project root.

**Step 2** — Copy and rename the templates:
- `CODEBASE_INDEX_TEMPLATE.md` -> `CODEBASE_INDEX.md`
- `CHANGELOG_TEMPLATE.md` -> `CHANGELOG.md`

**Step 3** — Fill in `CODEBASE_INDEX.md`. Replace every [PLACEHOLDER] with real project details:
- Project name, type, language, stack
- Repository structure and module descriptions
- Build and run instructions
- Coding conventions

**Step 4** — Customize `copilot-instructions.md`. Edit the agent routing table to match your team and domains. Remove inapplicable agents and add project-specific ones.

**Step 5** — Customize `feature-pipeline.instructions.md`. Replace or supplement the sub-pipelines with ones that match your workflow.

**Step 6** — Add your first CHANGELOG entry under [Unreleased] -> Added:
```
- [ARCH] Initial project scaffold
- [DOCS] Created CODEBASE_INDEX.md and Copilot instruction files
```

---

## Core Concepts

### CODEBASE_INDEX.md — Single Source of Truth
The first file every AI agent reads. Contains project overview, annotated file tree, per-module API summaries, coding conventions, and build instructions. Every structural or architectural change must update it.

### CHANGELOG.md — Functional History
Every functional change gets one line, prefixed with the responsible agent ID:
```
- [BE] Added rate limiting to auth endpoints
- [FE] Fixed overflow bug on mobile checkout form
```

### Agent IDs — Traceability
Short uppercase IDs (ARCH, FE, BE, etc.) tag every changelog entry so it is always clear what kind of change was made and by which specialist.

### 9-Step Feature Pipeline — Discipline
Every code-changing AI response must include: context loaded, architecture impact, pattern match, files to change, detailed plan, implementation, doc update, self-review checklist, and validation. This prevents blind edits and architectural drift.

---

## Adapting for Different Project Types

| Project Type | Suggested Customizations |
|---|---|
| Web App (Full-Stack) | Keep FE, BE, DATA agents. Add DevOps/Infra, Testing agents. Add API Routes and DB Schema sections to index. |
| Game (Custom Engine) | Keep ARCH, GPLAY, RNDR, PHYS, AUDI, AIBT. Add Game Systems and Content Pipeline sections to index. |
| Game (Unity/Godot/UE) | Replace RNDR/PHYS with engine-specific agents. Add Scene Structure section to index. |
| Desktop App | Keep ARCH, UI, DATA, BILD. Add Platform Integration section. |
| CLI Tool / Library | Keep ARCH, BILD, DOCS. Add Public API Contract section. |
| Mobile App | Add iOS, Android, or cross-platform agents. Add Platform Guides section. |

---

## Maintenance Rules

1. Never let the index go stale. Update it alongside every code change.
2. Never skip CHANGELOG entries for functional changes.
3. Add new instruction files for new conventions — reference them from the index.
4. Review the index periodically for accuracy as the project evolves.
