---
type: entity
title: "qmd"
created: 2026-06-06
updated: 2026-06-06
tags: [tool, search, software]
sources: [llm-wiki-idea]
related: [llm-wiki-pattern, obsidian]
---

# qmd

**qmd** is a local search engine for markdown files, created by Tobi. It provides hybrid **BM25/vector search** with LLM re-ranking, all running on-device.

- **Repository:** [github.com/tobi/qmd](https://github.com/tobi/qmd)

## Role in the LLM Wiki

At small scale (~100 sources, hundreds of pages), the `index.md` file is sufficient for the LLM to navigate the wiki. As the wiki grows, qmd provides proper search capabilities:

- **CLI mode** — the LLM can shell out to `qmd search "query"` to find relevant pages
- **MCP server mode** — the LLM can use qmd as a native tool (Model Context Protocol)

## Features

- Hybrid BM25 + vector search
- LLM re-ranking of results
- Fully local / on-device (no cloud dependency)
- Designed for markdown file collections

> [!NOTE] Gap
> qmd is not yet set up in this vault. It should be installed when the wiki grows beyond ~100 pages and index-based navigation becomes insufficient.

## Mentioned in

- [[llm-wiki-idea]] (foundational source)
- [[rag-vs-compiled-knowledge]] (scaling note)
