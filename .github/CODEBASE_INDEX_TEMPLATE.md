# CODEBASE INDEX — [PROJECT NAME]

> **Single source of truth** for project structure, conventions, and architecture.
> Last updated: [YYYY-MM-DD] ([brief description of what changed])
>
> Replace all [PLACEHOLDER] values with project-specific details.
> Remove sections that do not apply. Add new numbered sections as the project grows.

---

## 1. Project Overview

**[Project Name]** — [One sentence: what it is and what it does.]

- **Type:** [Game / Web App / Desktop App / API / Library / CLI Tool / Other]
- **Primary Language(s):** [e.g., TypeScript, C++, Python, Rust, Go]
- **Key Frameworks / Libraries:** [e.g., React, Next.js, Vulkan, Django, Express]
- **Target Platform(s):** [e.g., Web, Windows/Linux/macOS, iOS/Android, Steam]
- **Current Version:** [e.g., 0.1.0]
- **Status:** [Active Development / Alpha / Beta / Released]

### Goals
- [Primary goal 1]
- [Primary goal 2]

### Non-Goals (explicit out-of-scope)
- [Thing this project intentionally does NOT do]

---

## 2. Repository Structure

```
[project-root]/
├── .github/
│   ├── copilot-instructions.md       # AI agent master instructions
│   └── instructions/                 # Domain-specific instruction files
├── src/                              # [Primary source code]
│   ├── [module-a]/                   # [Description]
│   └── [module-b]/                   # [Description]
├── tests/                            # [Test files]
├── docs/                             # [Design documentation]
├── [build-config-file]               # [e.g., CMakeLists.txt, package.json]
├── CODEBASE_INDEX.md                 # This file
└── CHANGELOG.md                      # Project changelog
```

### Key Modules

#### [ModuleName]

- **Files:** `src/[path]/[Module].[ext]`
- **Purpose:** [What this module does and why it exists]
- **Key API:** `[MethodA()]`, `[MethodB(param)]`
- **Consumers:** [Which other modules depend on this one]
- **Dependencies:** [Which modules this one depends on]
- **Design Notes:** [Any non-obvious decisions or constraints]

---

## 3. Technology Stack

| Category | Technology | Version | Notes |
|---|---|---|---|
| Language | [e.g., TypeScript] | [e.g., 5.4] | [e.g., strict mode] |
| Runtime | [e.g., Node.js] | [e.g., 20 LTS] | |
| Framework | [e.g., React] | [e.g., 18.3] | |
| Database | [e.g., PostgreSQL] | [e.g., 16] | |
| Build Tool | [e.g., Vite] | [e.g., 5.2] | |
| Test Runner | [e.g., Vitest] | [e.g., 1.6] | |
| CI/CD | [e.g., GitHub Actions] | | |
| Deployment | [e.g., Vercel / Docker / Steam] | | |

---

## 4. Coding Conventions

### Naming
- [e.g., Files: kebab-case.ts | Classes: PascalCase | Functions/vars: camelCase | Constants: UPPER_SNAKE_CASE]
- [e.g., Database columns: snake_case | API routes: /kebab-case]

### File & Module Organization
- [e.g., One class/component per file. File name must match exported name.]
- [e.g., Feature folders: src/features/[feature-name]/ containing component, hook, service, and test.]

### Error Handling
- [e.g., All async functions must have explicit try/catch or use a Result type.]
- [e.g., API errors must return structured { code, message, details? } JSON.]

### Testing
- [e.g., Co-locate unit tests: MyComponent.test.tsx next to MyComponent.tsx]
- [e.g., E2E tests in tests/e2e/. Use Playwright.]

### Commit Style
- [e.g., Conventional Commits: feat:, fix:, chore:, docs:, refactor:]

---

## 5. Key Design Documents

| Document | Location | Description |
|---|---|---|
| [Architecture Overview] | `docs/architecture.md` | [High-level system design] |
| [API Design] | `docs/api-design.md` | [REST/GraphQL conventions] |
| [Data Model] | `docs/data-model.md` | [Core entity relationships] |

---

## 6. Build & Run Instructions

### Prerequisites
- [e.g., Node.js 20+, pnpm 9+]
- [e.g., .env file populated from .env.example]

### Setup
```sh
git clone [repo-url]
cd [project-name]
[install command]
cp .env.example .env
[migration command if applicable]
```

### Development
```sh
[dev server command]
# App available at http://localhost:3000
```

### Tests
```sh
[test command]
```

### Production Build
```sh
[build command]
[start command]
```

---

## 7. [Domain-Specific Section]

> Add project-specific sections here as needed. Examples:
> - Database Schema — tables, relationships, migration conventions
> - API Routes — complete route manifest
> - Game Systems — system registry with wiring notes
> - Render Pipeline — shader passes, descriptor sets, render order
> - Content Pipeline — asset formats, cooking steps

---

## 8. Migration Notes

| Date | Change | Migration |
|---|---|---|
| [YYYY-MM-DD] | [What changed] | [How to update existing code/data] |

---

## 9. Known Issues & Limitations

| Issue | Severity | Notes |
|---|---|---|
| [Description] | [High/Medium/Low] | [Workaround or planned fix] |
