---
type: concept
title: "Memex"
created: 2026-06-06
updated: 2026-06-06
tags: [history, vision, knowledge-management]
sources: [llm-wiki-idea]
related: [vannevar-bush, llm-wiki-pattern, wiki-maintenance-burden]
---

# Memex

The **Memex** (a portmanteau of "memory" and "index") was a hypothetical device described by [[vannevar-bush]] in his 1945 essay *"As We May Think"* (published in The Atlantic).

## The vision

Bush envisioned a personal, desk-sized device that would store all of a person's books, records, and communications on microfilm. The key innovation was **associative trails** — the user could create named links between any two items, building personal pathways through their knowledge. These trails could be shared with others.

## Relationship to the LLM Wiki

The [[llm-wiki-pattern]] realizes a version of Bush's vision:

| Memex feature | LLM Wiki equivalent |
|---------------|---------------------|
| Personal knowledge store | Obsidian vault with markdown files |
| Associative trails | `[[wikilinks]]` cross-references |
| Microfilm storage | Raw source documents in `raw/` |
| User-created links | LLM-generated bidirectional links |

The critical difference: Bush assumed the **user** would create and maintain the associative trails. In practice, this maintenance burden is why personal knowledge bases fail (see [[wiki-maintenance-burden]]). The LLM Wiki Pattern solves this by delegating maintenance to the LLM.

> "Bush's vision was closer to this than to what the web became: private, actively curated, with the connections between documents as valuable as the documents themselves. The part he couldn't solve was who does the maintenance."
> — [[llm-wiki-idea]]

## Mentioned in

- [[llm-wiki-idea]] (foundational source)
