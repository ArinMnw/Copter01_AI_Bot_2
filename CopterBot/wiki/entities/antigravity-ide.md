---
type: entity
title: "Antigravity IDE"
created: 2026-06-06
updated: 2026-06-06
tags: [tool, ide, software, ai-coding]
sources: [toolkit-for-antigravity]
related: [obsidian, toolkit-for-antigravity, auto-accept, ai-quota-monitoring, llm-wiki-pattern]
---

# Antigravity IDE

**Antigravity IDE** is an AI-native code editor developed by Google DeepMind. It integrates LLM agents (Gemini, Claude, GPT) directly into the coding workflow, enabling AI-assisted code generation, editing, and terminal operations.

## Architecture

Built on the VS Code / Electron platform. Key internal components:

- **Agent** — the LLM backend that suggests code changes and terminal commands
- **Language Server** — background process that powers the Agent
- **Webview** — sandboxed UI panels (may affect extension capabilities like [[auto-accept]])
- **Brain** — conversation cache storage for AI sessions

## Relationship to the LLM Wiki

Antigravity IDE is the **environment where the wiki agent runs**. While [[obsidian]] is the IDE for *browsing* the wiki, Antigravity is the IDE for *building* it — the LLM agent operates here, reading files, writing wiki pages, and running commands.

| Tool | Role in LLM Wiki |
|------|-------------------|
| [[antigravity-ide]] | Where the LLM agent runs — edits files, runs commands |
| [[obsidian]] | Where the user browses — reads pages, views graph |

## Key Extension: Toolkit for Antigravity

The [[toolkit-for-antigravity]] extension adds operational tools:

- [[ai-quota-monitoring]] — track Gemini/Claude/GPT usage to avoid hitting limits
- [[auto-accept]] — hands-free mode for uninterrupted agent workflows
- Cache management — clean up conversation history
- Service recovery — restart/reset when the agent becomes unresponsive

## Configuration

Settings accessed via `Ctrl+,` → search `tfa`:

- Quota polling interval (default 90s)
- Warning/critical thresholds (30%/10%)
- Cache auto-clean (keeps N newest tasks)
- UI scale (0.8–2.0)

## Platform Support

Windows, macOS, Linux

## Mentioned in

- [[toolkit-for-antigravity]] (source)
- [[auto-accept]] (concept)
- [[ai-quota-monitoring]] (concept)
