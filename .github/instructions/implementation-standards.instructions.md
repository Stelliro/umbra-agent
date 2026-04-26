---
description: "Universal implementation standards — security, backward compatibility, code quality, validation. Applies to all project types."
---

# Implementation Standards

## Security (OWASP Top 10 — Always)

- No hard-coded secrets — use environment variables or a secret manager. Never commit secrets to source control.
- Validate and sanitize all external input at the system boundary — user input, API parameters, file paths, query strings.
- Prevent injection — use parameterized queries for databases; escape output for HTML/template contexts; avoid eval() or equivalent.
- Least privilege — services, database users, and API tokens should have only the permissions they need.
- Prevent path traversal — normalize and constrain all file paths before use.
- Respect existing auth/authz patterns — never bypass authentication or authorization checks.
- For web projects: configure security headers and restrict CORS origins explicitly.

## Backward Compatibility

- Identify whether a change is breaking or non-breaking for public APIs, schemas, wire formats, or config files.
- For breaking changes: provide a migration path, deprecation notice, or versioned alternative before removal.
- Never silently change the meaning of an existing public interface — add a new one instead.

## Code Quality

- Single responsibility — every function, class, module, and file does one thing well.
- DRY within reason — eliminate true duplication; don't over-abstract for one-off cases.
- No dead code — remove it, or track it with a documented issue.
- Least surprise — no hidden side effects, global state mutations, or magical behavior.
- Explicit error handling — every error path must be handled. No silent failures.
- Consistent naming — follow the codebase established naming conventions (see CODEBASE_INDEX conventions section).
- No magic numbers or strings — use named constants, enums, or config values.

## Dependency Management

- Prefer dependencies already in the project over adding new ones.
- Justify any new external dependency: actively maintained? Permissive license? Worth the surface area?
- Pin versions for reproducible builds. Use lockfiles.
- Audit new dependencies for known vulnerabilities before adding.

## Validation

- Mental dry-run — trace the happy path and at least two edge cases before declaring done.
- Boundary checks — empty inputs, null/undefined/None, zero, maximum values, concurrent access.
- Type alignment — verify types match across all call sites, interfaces, and serialization boundaries.
- Idempotency — retryable operations must be safe to run multiple times.
- The codebase must be fully valid and buildable/runnable after every change.

## Testing

- Every new feature: at least one test covering the happy path.
- Every bug fix: a regression test that would have caught the bug.
- Test behavior, not implementation — tests should survive refactoring.
- Do not mock what you own; mock what you don't own (external APIs, third-party services).

## Performance

- Do not introduce obviously expensive operations without justification.
- Profile before optimizing. Premature optimization is a source of complexity.
- Document known performance-sensitive paths in CODEBASE_INDEX.
