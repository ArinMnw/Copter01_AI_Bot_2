---
type: concept
title: "Auto-Accept (Hands-free Mode)"
created: 2026-06-06
updated: 2026-06-06
tags: [workflow, automation, ai-coding, concept]
sources: [toolkit-for-antigravity]
related: [antigravity-ide, toolkit-for-antigravity, llm-wiki-pattern, wiki-maintenance-burden]
---

# Auto-Accept (Hands-free Mode)

**Auto-Accept** is a workflow pattern where the LLM agent's suggested actions (terminal commands, file edits) are **automatically approved** without requiring manual user confirmation each time.

## Why it matters

In the [[llm-wiki-pattern]] and other LLM-driven workflows, the agent frequently needs to:
- Create and edit multiple files in a single operation
- Run terminal commands to verify work
- Chain multiple operations together

Without auto-accept, the user must manually approve **every** action — creating a significant bottleneck. For operations like a wiki ingest that might touch 10-15 files, this means 10-15 manual approvals. Auto-accept removes this friction.

## Connection to the maintenance burden

Auto-accept is a practical enabler of the [[wiki-maintenance-burden]] solution. The LLM can only solve the maintenance problem if it can act efficiently. Manual approval gates reintroduce human bottleneck — exactly the kind of friction that makes knowledge base maintenance unsustainable.

## Implementation in Antigravity IDE

The [[toolkit-for-antigravity]] extension implements auto-accept with a **dual strategy**:

| Strategy | Mechanism | When used |
|----------|-----------|-----------|
| **Command API** (primary) | Uses the IDE's built-in command interface | Default — works in most configurations |
| **CDP Injection** (fallback) | Chrome DevTools Protocol injection into webview | When Command API is blocked by webview sandboxing |

### Activation

- **Toggle:** Sidebar 🚀 Rocket switch in the Toolkit panel
- **Command:** `Antigravity Toolkit: Toggle Auto-Accept`

### CDP Fallback Setup (Windows)

```bat
@echo off
taskkill /F /IM Antigravity.exe /T 2>nul
start "" "D:\Develop\Antigravity\Antigravity.exe" --remote-debugging-port=9222
```

Requires launching Antigravity IDE with `--remote-debugging-port=9222`.

## Risks and considerations

- **Trust boundary:** Auto-accept means the LLM can execute arbitrary commands without review. Suitable for trusted workflows; risky for untrusted code.
- **Destructive actions:** File deletions, system commands, and network operations are auto-approved. Users should understand the scope.
- **Sandboxed webviews:** The primary command API may not work in all configurations, requiring the CDP fallback setup.

## Mentioned in

- [[toolkit-for-antigravity]] (source)
- [[antigravity-ide]] (parent tool)
