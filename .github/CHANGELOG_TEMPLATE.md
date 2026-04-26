# Changelog

All notable changes to **[Project Name]** are documented here.

This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

### Version Number Guide
- **MAJOR** (x.0.0) — Breaking changes to public APIs or saved data formats
- **MINOR** (0.x.0) — New features, backward-compatible
- **PATCH** (0.0.x) — Bug fixes, backward-compatible

### Entry Format
```
- [AGENT_ID] Description of change — module/system name included
```

---

## [Unreleased]

> All completed but unreleased changes live here.
> When a version is tagged, move these entries into a new versioned section below.

### Added

### Changed

### Fixed

### Removed

---

## [0.1.0] — YYYY-MM-DD

> First tracked release.

### Added
- [ARCH] Initial project scaffold
- [BILD] Configured build system with dependency manager
- [DOCS] Created CODEBASE_INDEX.md, CHANGELOG.md, and .github instruction files

---

## HOW TO USE THIS FILE
##
## 1. Every functional code change gets one line under [Unreleased].
## 2. Prefix with the responsible agent ID: [ARCH], [FE], [BE], etc.
## 3. Use the correct category:
##    Added   — new feature, system, file, endpoint, screen
##    Changed — modified behavior, API, schema, config
##    Fixed   — bug fix, crash fix, logic correction
##    Removed — deletion, deprecation cleanup
## 4. Skip doc-only or formatting-only changes.
## 5. When releasing: rename [Unreleased] to [x.y.z] — YYYY-MM-DD, add a fresh [Unreleased] above it.
##
## EXAMPLES
##
## ### Added
## - [BE] Added POST /api/users endpoint with input validation and rate limiting
## - [FE] Added dark mode toggle — persists to localStorage
## - [GPLAY] Implemented stamina system with exhaustion state and recovery curve
##
## ### Fixed
## - [BE] Fixed JWT token not invalidated on password reset
## - [FE] Fixed checkout total rounding error on quantities > 100
##
## ### Changed
## - [UI] Overhauled settings modal — grouped into tabs (General, Display, Audio, Controls)
##
## ### Removed
## - [RFCT] Removed deprecated LegacyParser — replaced by DataParser since v0.3
