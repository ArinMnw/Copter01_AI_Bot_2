---
type: source
title: "Toolkit for Antigravity — README"
created: 2026-06-06
updated: 2026-06-06
tags: [tooling, ide, ai-workflow, extension, quota, cache]
sources: [toolkit-for-antigravity]
related: [antigravity-ide, auto-accept, ai-quota-monitoring, obsidian]
---

# Toolkit for Antigravity — README

**Source:** `raw/toolkit-for-antigravity.md`
**Type:** Extension documentation / README
**Author:** n2ns (community project, Apache 2.0)

## Summary

A community-built extension for [[antigravity-ide]] that provides **real-time AI quota monitoring**, **usage analytics**, **cache management**, and **auto-accept** (hands-free mode) for agent workflows. It fills operational gaps in the IDE by giving users visibility into their Gemini/Claude/GPT consumption and tools to manage workspace hygiene.

## Key Claims

- **Quota monitoring is essential** for heavy AI workflows — without it, users hit limits unexpectedly and lose momentum.
- **Auto-accept** ([[auto-accept]]) enables hands-free agent operation by automatically approving terminal commands and file edits, removing the human bottleneck from LLM-driven coding workflows.
- **Cache management** prevents workspace bloat — AI conversations accumulate hundreds of MB over time.
- **All data stays local** — the extension communicates only with local components, no external telemetry.
- **Dual-strategy auto-accept**: command API (primary) + CDP injection (fallback for sandboxed webviews).

## Features Catalog

| Feature | Description |
|---------|-------------|
| Smart Quota Monitoring | Visual display grouped by model family (Gemini, Claude, GPT) with 🟢🟡🔴 thresholds |
| Usage Trends | Interactive bar charts, 24h history, consumption rate (%/hr), runway prediction |
| Token Credits | Prompt Credits (reasoning) + Flow Credits (operations) tracking |
| Cache Management | Browse/delete Brain Tasks and Code Context caches, smart tab cleanup |
| Auto-Accept | Hands-free mode — auto-approve agent commands and edits |
| Commit Generator | Claude/LLM-powered conventional commit messages |
| Service Recovery | Restart Language Server, Reset Status, Reload Window |
| Quick Config | One-click access to Rules, MCP, Allowlist |
| Localization | 13 languages |

## Setup Notes

- **Auto-Accept CDP fallback** requires launching with `--remote-debugging-port=9222` (see [[auto-accept]])
- **Commit Generator** requires Anthropic API key (stored securely, never plaintext)
- **Cache Auto-Clean** keeps N newest tasks (default 5), deletes the rest

## Notable Quotes

> "Toolkit for Antigravity does not collect, transmit, or store any user data. All operations are performed locally on your machine."

## Mentioned in

- [[antigravity-ide]] (parent tool)
- [[auto-accept]] (key concept)
- [[ai-quota-monitoring]] (key concept)
