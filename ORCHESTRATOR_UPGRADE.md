# BOB Orchestrator Upgrade Guide

This document highlights the major architectural improvements implemented to transition BOB from a monolithic agent into a **Multi-Agent Orchestrator**.

## 1. Architectural Shift: Orchestrator vs. Specialist

BOB now operates on a "Lead Orchestrator" model. Instead of a single agent attempting to handle every tool and skill, the system is now divided into:

- **Lead Orchestrator (Orchestrator style)**: The primary point of contact for the user. It focuses on intent analysis, routing, and synthesizing results from specialists.
- **Specialist Fleet**: Discrete sub-agents with scoped capabilities, restricted toolsets, and tailored personas.

## 2. The Specialist Fleet

Four specialized sub-agent profiles have been added to `nanobot/agent/profiles.py`:

| Agent | Role | Key Capabilities |
| :--- | :--- | :--- |
| **DEX Trader** | Financial Operations | Liquidity pools, swaps, market orders, BitShares ops. |
| **System Admin** | System & Files | Filesystem management, shell execution, tmux, cron. |
| **Researcher** | Information Gathering | Web search, web fetch, GitHub analysis, summaries. |
| **Clerk** | Administration | Long-term memory, scheduling, clerical records. |

## 3. Synchronous Delegation (`dispatch`)

A new `DispatchTool` has been implemented to replace the generic `SpawnTool` for primary workflows:

- **Synchronous Execution**: The lead agent "waits" for the sub-agent to finish. This allows the result to be incorporated directly into the conversation.
- **Improved Context**: The orchestrator provides a clear, detailed task description to the specialist.
- **Voice Synthesis**: The lead agent reviews the specialist's technical output and presents it to the user in a consistent, professional "voice."

## 4. Scoped Execution & Precision

To reduce "model hallucination" and increase financial safety:

- **Scoped Tools**: Sub-agents only have access to the tools defined in their profile. A `DEX Trader` cannot accidentally delete files, and a `Researcher` cannot draft transactions.
- **Scoped Personas**: Each sub-agent receives a unique system prompt and relevant skills, ensuring it stays focused on its domain.
- **Override Logic**: The `AgentLoop` now supports `tools_override` and `max_iterations_override` for precise control over specialist turns.

## 5. CLI & Configuration Improvements

- **Orchestrator Toggle**: Added an `--orchestrator` flag to the `nanobot agent` and `nanobot gateway` commands.
- **Config Schema**: Added `is_orchestrator` to `AgentDefaults` in `schema.py` for persistent configuration.
- **Registry Summary**: A new `AgentRegistry` dynamically builds a "Fleet Summary" for the orchestrator's system prompt, enabling intelligent routing without exposing raw tool schemas.

## 6. Template Enhancements

The core workspace templates have been rewritten for orchestrator mode:

- **SOUL.md**: Personifies BOB as a high-stakes technical lead focused on orchestration and delegation.
- **AGENTS.md**: Provides a comprehensive routing decision tree and "Dispatch Protocol" to guide the LLM's reasoning.

---

### Usage

To run BOB in the new Orchestrator mode:

```bash
# Interactive CLI
nanobot agent --orchestrator

# Start the Gateway (Telegram/WhatsApp/etc)
nanobot gateway --orchestrator
```

You can also enable it permanently in `~/.nanobot/config.json`:
```json
"agents": {
  "defaults": {
    "isOrchestrator": true
  }
}
```
