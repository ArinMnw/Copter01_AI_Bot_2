---
type: concept
title: "RAG vs. Compiled Knowledge"
created: 2026-06-06
updated: 2026-06-06
tags: [pattern, rag, comparison, knowledge-management]
sources: [llm-wiki-idea]
related: [llm-wiki-pattern]
---

# RAG vs. Compiled Knowledge

A comparison between two approaches to LLM-assisted knowledge management.

## RAG (Retrieval-Augmented Generation)

The dominant paradigm. Documents are chunked, embedded, and stored in a vector database. At query time, relevant chunks are retrieved and the LLM generates an answer.

**Strengths:**
- Simple to set up
- Works with any document format
- No pre-processing beyond chunking/embedding
- Scales to large document collections

**Weaknesses:**
- **Stateless** — knowledge is re-derived from scratch on every query
- **No accumulation** — subtle multi-document synthesis must be rediscovered each time
- **No cross-referencing** — connections between documents are not pre-built
- **No contradiction detection** — conflicting claims across documents are not flagged
- **Quality depends on retrieval** — miss the right chunks, miss the answer

**Examples:** NotebookLM, ChatGPT file uploads, most enterprise RAG systems.

## Compiled Knowledge (LLM Wiki Pattern)

The approach described in [[llm-wiki-pattern]]. Sources are read and integrated into a persistent wiki at ingest time. The wiki is the queryable artifact.

**Strengths:**
- **Stateful** — knowledge compounds over time
- **Pre-synthesized** — cross-references, contradictions, and connections are already built
- **Human-readable** — the wiki is browsable markdown, not an opaque vector store
- **Query quality improves with scale** — more sources = richer wiki = better answers
- **Exploratory** — the wiki structure itself reveals gaps and connections

**Weaknesses:**
- Higher upfront cost per source (ingest takes more LLM work)
- Requires a schema and conventions (some setup effort)
- May not scale to thousands of sources without search tooling (see [[qmd]])
- LLM must maintain consistency as wiki grows

## The tradeoff

RAG optimizes for **breadth with low effort**. The wiki pattern optimizes for **depth with compounding returns**. They're complementary — a wiki can use RAG-style search internally (via [[qmd]]) while maintaining pre-compiled knowledge pages.

## Mentioned in

- [[llm-wiki-idea]] (foundational source)
