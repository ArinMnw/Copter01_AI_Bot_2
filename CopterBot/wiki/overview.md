---
type: overview
title: "Wiki Overview"
created: 2026-06-06
updated: 2026-06-06
tags: [meta, synthesis]
---

# Wiki Overview

This is a **personal knowledge base** maintained by an LLM agent following the [[llm-wiki-pattern]].

## What this wiki is

A persistent, compounding knowledge artifact. Rather than re-deriving answers from raw documents on every query (the [[rag-vs-compiled-knowledge|RAG approach]]), this wiki **pre-compiles** knowledge: every source is read, synthesized, and integrated into an interlinked web of pages. The cross-references are already built. The contradictions are already flagged. Each new source makes the whole structure richer.

## How it works

The system has three layers:

1. **Raw sources** (`raw/`) — immutable source documents. The LLM reads from these but never modifies them.
2. **The wiki** (`wiki/`) — LLM-generated markdown pages. Summaries, entity pages, concept pages, analyses. All maintained and cross-referenced by the LLM.
3. **The schema** (`AGENTS.md`) — rules and conventions that govern how the LLM operates on the wiki.

## Current state

- **Sources ingested:** 2
- **Key themes:** LLM-assisted knowledge management, the [[wiki-maintenance-burden]] problem, [[memex|Bush's Memex]] vision realized through AI, AI-native tooling and workflow automation
- **Coverage:** Foundational pattern + operational tooling. Ready for domain-specific sources.

## Core concepts

- [[llm-wiki-pattern]] — the central design pattern
- [[rag-vs-compiled-knowledge]] — why pre-compiled knowledge beats on-the-fly retrieval
- [[memex]] — the historical precursor (Vannevar Bush, 1945)
- [[wiki-maintenance-burden]] — the problem LLMs uniquely solve
- [[auto-accept]] — hands-free agent mode, removing the human bottleneck
- [[ai-quota-monitoring]] — tracking LLM usage for sustainable workflows

## Key entities

- [[vannevar-bush]] — originator of the Memex concept
- [[obsidian]] — the markdown IDE for browsing the wiki
- [[antigravity-ide]] — the AI-native IDE where the wiki agent runs
- [[toolkit-for-antigravity]] — extension for quota, cache, and auto-accept
- [[qmd]] — search tooling for scaling wiki navigation

## What's next

This wiki is freshly bootstrapped. To grow it:

1. **Add sources** — clip articles, paste notes, drop documents into `raw/`
2. **Ask questions** — the LLM will synthesize answers from wiki pages
3. **Explore** — let the LLM suggest gaps, connections, and next reads
4. **Lint** — periodically health-check for orphans, contradictions, and gaps
