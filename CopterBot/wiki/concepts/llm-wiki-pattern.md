---
type: concept
title: "LLM Wiki Pattern"
created: 2026-06-06
updated: 2026-06-06
tags: [pattern, architecture, knowledge-management, core]
sources: [llm-wiki-idea]
related: [rag-vs-compiled-knowledge, memex, wiki-maintenance-burden, obsidian, qmd]
---

# LLM Wiki Pattern

The **LLM Wiki Pattern** is an approach to personal knowledge management where an LLM agent **incrementally builds and maintains a persistent, interlinked wiki** from raw source documents.

## How it differs from RAG

Traditional RAG retrieves raw document chunks at query time and generates answers from scratch. The LLM Wiki Pattern inverts this: knowledge is **compiled once** into structured wiki pages and **kept current** as new sources arrive. See [[rag-vs-compiled-knowledge]] for a detailed comparison.

## Three-layer architecture

1. **Raw sources** — immutable documents curated by the user
2. **The wiki** — LLM-generated markdown pages (summaries, entities, concepts, analyses)
3. **The schema** — a rules document co-evolved by user and LLM

## Four core operations

| Operation | Trigger | What happens |
|-----------|---------|-------------|
| **Ingest** | New source added | LLM reads, summarizes, updates entity/concept pages, cross-references, updates index and log |
| **Query** | User asks a question | LLM reads index → relevant pages → synthesizes answer → optionally files it back |
| **Lint** | Periodic health check | Scans for orphans, contradictions, gaps, stale content |
| **Explore** | User asks for suggestions | LLM reviews gaps and suggests next reads or questions |

## Key insight

The pattern works because LLMs eliminate the [[wiki-maintenance-burden]] — the bookkeeping that causes humans to abandon wikis. The human focuses on curation and thinking; the LLM handles summarizing, cross-referencing, filing, and consistency.

## Historical lineage

The pattern realizes a version of [[vannevar-bush|Vannevar Bush]]'s [[memex]] (1945) — a personal knowledge store with associative trails. Bush couldn't solve the maintenance problem; LLMs do.

## Mentioned in

- [[llm-wiki-idea]] (foundational source)
