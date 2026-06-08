---
type: source
title: "LLM Wiki — Idea File"
created: 2026-06-06
updated: 2026-06-06
tags: [meta, pattern, knowledge-management, architecture]
sources: [llm-wiki-idea]
related: [llm-wiki-pattern, rag-vs-compiled-knowledge, memex, wiki-maintenance-burden, vannevar-bush, obsidian, qmd]
---

# LLM Wiki — Idea File

**Source:** `raw/llm-wiki-idea.md`
**Type:** Pattern description / architectural blueprint
**Author:** Tobi (implied from qmd authorship and first-person narrative)

## Summary

A foundational document describing a pattern for building **personal knowledge bases using LLMs**. The core insight is that instead of using LLMs for on-the-fly RAG retrieval, you have the LLM **incrementally build and maintain a persistent wiki** — a structured, interlinked collection of markdown files. The wiki compounds over time: each new source enriches the entire structure, cross-references are pre-built, contradictions are flagged, and synthesis is always current.

## Key Claims

- **RAG is stateless.** Most LLM+document systems (NotebookLM, ChatGPT file uploads) re-derive knowledge on every query. Nothing accumulates.
- **The wiki is a persistent, compounding artifact.** Knowledge is compiled once and kept current, not re-derived each time.
- **The LLM does the maintenance.** Humans abandon wikis because bookkeeping (cross-references, updates, consistency) scales poorly. LLMs eliminate this burden.
- **Three-layer architecture:** raw sources (immutable) → wiki (LLM-owned) → schema (co-owned).
- **Four operations:** ingest, query, lint, explore.
- **The pattern is domain-agnostic.** Works for personal development, research, reading, business, and any knowledge accumulation context.
- **Related to Vannevar Bush's Memex (1945)** — the missing piece was maintenance, which LLMs now provide.

## Architecture (from source)

| Layer | Owner | Purpose |
|-------|-------|---------|
| Raw sources (`raw/`) | User | Immutable source documents |
| Wiki (`wiki/`) | LLM | Generated, maintained, cross-referenced knowledge pages |
| Schema (`AGENTS.md`) | Co-owned | Rules, conventions, workflows for the LLM agent |

## Operations (from source)

1. **Ingest** — read source → create summary → update entity/concept pages → cross-reference → update index/log
2. **Query** — read index → find pages → synthesize answer → optionally file back into wiki
3. **Lint** — scan for orphans, broken links, contradictions, gaps, thin pages
4. **Explore** — suggest next reads, unfilled gaps, unexplored connections

## Use Cases Mentioned

- Personal (goals, health, self-improvement)
- Research (papers, evolving thesis)
- Reading a book (characters, themes, plot threads — "Tolkien Gateway"-style)
- Business/team (Slack, meeting transcripts, project docs)
- Competitive analysis, due diligence, trip planning, course notes

## Tooling Mentioned

- [[obsidian]] — as the wiki viewer/IDE (graph view, Web Clipper, Marp, Dataview)
- [[qmd]] — local search engine for scaling wiki navigation
- Git — version history for free

## Notable Quotes

> "Obsidian is the IDE; the LLM is the programmer; the wiki is the codebase."

> "The human's job is to curate sources, direct the analysis, ask good questions, and think about what it all means. The LLM's job is everything else."

> "Humans abandon wikis because the maintenance burden grows faster than the value."
