---
type: entity
title: "Toolkit for Antigravity"
created: 2026-06-06
updated: 2026-06-06
tags: [tool, extension, ide, ai-workflow]
sources: [toolkit-for-antigravity]
related: [antigravity-ide, auto-accept, ai-quota-monitoring]
---

# Toolkit for Antigravity

**Toolkit for Antigravity** (formerly "Antigravity Panel") is a community-built extension for [[antigravity-ide]] that provides operational tooling for AI-heavy workflows.

- **Repository:** [github.com/n2ns/antigravity-panel](https://github.com/n2ns/antigravity-panel)
- **License:** Apache 2.0
- **Languages:** 13 (EN, ZH, JA, FR, DE, ES, PT, IT, KO, RU, PL, TR)

## Core capabilities

| Feature | Purpose |
|---------|---------|
| [[ai-quota-monitoring]] | Real-time Gemini/Claude/GPT quota with visual thresholds |
| [[auto-accept]] | Hands-free agent operation — auto-approve commands and edits |
| Cache Management | Browse/delete Brain Tasks and Code Context caches |
| Commit Generator | Claude/LLM-powered conventional commit messages |
| Service Recovery | Restart Language Server, Reset Status, Reload Window |
| Quick Config | One-click access to Rules, MCP, Allowlist settings |

## Privacy

All operations are local. No data is collected, transmitted, or stored externally. The only external call is the optional Anthropic API for commit message generation (user-initiated, requires explicit API key setup).

## Notable contributors

- @restinnotes — CDP Auto-Accept implementation
- @simbaTmotsi — Local LLM Commit Message Generator
- @AMDphreak — Quota reset alignment, model grouping
- @vincenzofabiano92 — Connection stability, Italian localization

## Mentioned in

- [[toolkit-for-antigravity|source page]] (source)
- [[antigravity-ide]] (parent tool)
