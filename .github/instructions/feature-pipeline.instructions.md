---
description: "Universal 9-step feature pipeline for any project type. Use when implementing new features, systems, or significant changes."
---

# Feature Pipeline (9 Steps)

Every code-changing response must contain these 9 numbered sections in order. No step may be skipped.

1. **Context Loaded** — State which files and sections of CODEBASE_INDEX.md were read.
2. **Architecture Impact** — List every system, module, or layer affected and explain why.
3. **Pattern Match** — Identify the closest existing pattern or system this change resembles.
4. **Files To Change** — Exact list of files to create, modify, or delete with full paths.
5. **Detailed Plan** — Bullet-point step-by-step plan using exact variable names and function signatures from the codebase index.
6. **Implementation** — Full code changes. Never partial files or unexplained snippets.
7. **Mandatory Documentation Update** — Exact changes needed to CODEBASE_INDEX.md and CHANGELOG.md.
8. **Self-Review Checklist:**
   - [ ] Follows documented architectural patterns (no circular deps, no layer violations)
   - [ ] Security: no hard-coded secrets, input validated, auth/authz respected
   - [ ] Error handling: all failure paths handled explicitly
   - [ ] No dead code introduced
   - [ ] Tests updated or added
   - [ ] CODEBASE_INDEX.md updated
   - [ ] CHANGELOG.md updated
   - [ ] No obvious performance regressions
   - [ ] Backward compatibility: breaking changes documented
9. **Validation** — Describe the happy path and at least two edge cases.

---

## Project-Type Sub-Pipelines

### New Backend API Endpoint
- Define route following existing naming patterns
- Create/update service method with business logic
- Add input validation at the controller/handler boundary
- Return consistent response shape
- Add integration test (happy path + failure modes)
- Update API docs or OpenAPI spec

### New Frontend Feature / Page
- Create component following existing structure
- Wire to state management or data-fetching layer
- Add routing entry if new page
- Handle loading, error, and empty states
- Validate accessibility (keyboard nav, ARIA roles, contrast)
- Update navigation or sitemap if needed

### New Game System
- Add system class; initialize in main game loop entry point
- Wire all relevant callbacks (input, events, ECS updates, etc.)
- Integrate with save/load if system has persistent state
- Integrate with UI/HUD if system has player-visible state
- Update design doc

### New CLI Tool or Script
- Follow existing tool conventions (argument parsing, exit codes, output format)
- Add help text and usage examples
- Handle all error paths with meaningful exit codes and messages
- Register in project tooling documentation

### Schema / Database Migration
- Create migration file using project convention
- Include both up and down (rollback) operations
- Update ORM models and type definitions
- Update CODEBASE_INDEX with new schema notes

### New Rendering / Shader Feature
- Follow existing shader naming and file structure
- Document all uniform/push-constant bindings
- Test in all relevant render modes
- Validate against performance budget
