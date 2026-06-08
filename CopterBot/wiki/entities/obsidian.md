---
type: entity
title: "Obsidian"
created: 2026-06-06
updated: 2026-06-06
tags: [tool, software, knowledge-management]
sources: [llm-wiki-idea]
related: [llm-wiki-pattern, qmd, antigravity-ide]
---

# Obsidian

**Obsidian** is a markdown-based knowledge management application. In the context of the [[llm-wiki-pattern]], it serves as the **IDE** — the interface through which the user browses, reads, and visualizes the wiki while the LLM maintains it.

## Role in the LLM Wiki

> "Obsidian is the IDE; the LLM is the programmer; the wiki is the codebase."
> — [[llm-wiki-idea]]

The LLM agent edits files in the vault; the user views the results in Obsidian in real time.

## Key features used

| Feature | Usage |
|---------|-------|
| **Graph View** | Visualize wiki structure — hubs, orphans, clusters |
| **Wikilinks** (`[[...]]`) | Cross-references between pages |
| **Web Clipper** | Browser extension to convert articles → markdown for `raw/` |
| **Marp plugin** | Generate slide decks from wiki content |
| **Dataview plugin** | Query YAML frontmatter to generate dynamic tables/lists |
| **Local image downloads** | Store images in `raw/assets/` for LLM access |

## Tips from the source

- Set "Attachment folder path" to `raw/assets/` in Settings → Files and links
- Bind "Download attachments for current file" to a hotkey (e.g. Ctrl+Shift+D)
- Use graph view to spot orphan pages and heavily-linked hubs

## Mentioned in

- [[llm-wiki-idea]] (foundational source)
