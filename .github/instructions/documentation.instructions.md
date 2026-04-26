---
applyTo: "**/*.md"
description: "Documentation update rules — CODEBASE_INDEX maintenance, CHANGELOG format, pattern documentation. Universal template."
---

# Documentation Standards

## CODEBASE_INDEX.md

- Update whenever structure, conventions, or architecture changes.
- It is the single source of truth — keep it accurate and current.
- Reference new instruction files from the index when they are created.
- Every module/system listed in the index must include: purpose, file paths, key API, and wiring/integration notes.

## Pattern Documentation

- New convention — create an instruction file in `.github/instructions/`, reference it in the index.
- Modified convention — update the instruction file AND the index.
- Each instruction file must include: what the pattern is, why it exists, examples, and counter-examples.

## CHANGELOG.md

- Append an entry under [Unreleased] for every functional change.
- Use Keep a Changelog categories: Added, Changed, Fixed, Removed.
- One concise line per change. Include the system/module name.
- Prefix every entry with the responsible agent ID: `- [ARCH] Added FooSystem`
- Skip for doc-only or formatting-only edits.
- When a release is tagged, move [Unreleased] entries into a new versioned section [x.y.z] - YYYY-MM-DD.

## README.md

- Keep concise: project name, one-sentence description, quick-start, and links to deeper docs.
- Do not duplicate content already in CODEBASE_INDEX.md — link instead.

## General

- Never skip doc updates. Stale docs are worse than none.
- Update READMEs, API docs, changelogs, and inline comments alongside code changes.
- Keep documentation concise and actionable — no filler prose.
