---
type: concept
title: "AI Quota Monitoring"
created: 2026-06-06
updated: 2026-06-06
tags: [workflow, ai-coding, operations, concept]
sources: [toolkit-for-antigravity]
related: [antigravity-ide, toolkit-for-antigravity]
---

# AI Quota Monitoring

**AI Quota Monitoring** is the practice of tracking LLM API usage in real time to prevent unexpected rate-limiting and optimize consumption.

## Why it matters

AI-native IDEs like [[antigravity-ide]] offer multiple model families (Gemini, Claude, GPT), each with separate quotas and reset cycles. Heavy workflows — especially with [[auto-accept]] enabled — can burn through quota quickly. Without monitoring:

- Users hit limits mid-task and lose momentum
- It's unclear which model family is being consumed fastest
- There's no warning before quota exhaustion

## Implementation in Toolkit for Antigravity

The [[toolkit-for-antigravity]] provides:

| Feature | Description |
|---------|-------------|
| **Visual dashboard** | Pie/arc charts grouped by model family (Gemini, Claude, GPT) |
| **Status bar** | Remaining quota with 🟢🟡🔴 emoji indicators |
| **Thresholds** | Warning at ≤30%, critical at ≤10% (configurable) |
| **Usage trends** | Bar charts showing consumption over 10-120 minutes |
| **Consumption rate** | Real-time speed in %/hour |
| **Runway prediction** | Estimated time until quota exhaustion |
| **Token credits** | Prompt Credits (reasoning) + Flow Credits (operations) |

## Two types of credits

| Credit type | Used for | Examples |
|-------------|----------|---------|
| **Prompt Credits** | Conversation input and result generation | Questions, code generation, reasoning |
| **Flow Credits** | Search, modification, and command execution | File edits, terminal commands, semantic search |

## Configuration

| Setting | Default |
|---------|---------|
| Polling interval | 90 seconds |
| Warning threshold | 30% |
| Critical threshold | 10% |
| History range | 90 minutes |

## Mentioned in

- [[toolkit-for-antigravity]] (source)
- [[antigravity-ide]] (parent tool)
