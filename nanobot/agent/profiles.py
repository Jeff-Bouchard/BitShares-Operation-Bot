"""
Agent Profiles — Defines the specialist sub-agents and their scoped capabilities.

Each AgentProfile defines:
  - Which tools the sub-agent can access
  - Which skills are injected into its context
  - A concise persona prompt (how it thinks/responds)
  - Trigger keywords for intent routing
"""

from dataclasses import dataclass, field


@dataclass
class AgentProfile:
    """Definition of a specialist sub-agent."""

    agent_id: str
    display_name: str
    persona: str                        # Concise system-level persona for this sub-agent
    skill_names: list[str]              # Skills to load into this sub-agent's context
    tool_names: list[str]               # Tools this sub-agent can use (scoped subset)
    triggers: list[str] = field(default_factory=list)   # Keywords for intent routing
    max_iterations: int = 15            # Tool-calling loop limit


# ─── Profile Definitions ─────────────────────────────────────────────────────

DEX_TRADER = AgentProfile(
    agent_id="dex_trader",
    display_name="DEX Trader",
    persona=(
        "You are a specialist in decentralized exchange operations. You handle "
        "liquidity pool management, asset swaps, and market operations on the "
        "BitShares blockchain. You are precise with numbers and conservative with risk."
    ),
    skill_names=["bitshares-lp", "bitshares-ops", "pool-router", "straddle"],
    tool_names=[
        "read_file",
        "exec",
    ],
    triggers=[
        "trade", "buy", "sell", "swap", "liquidity", "pool", "bitshares",
        "market", "order", "price", "asset", "straddle", "limit order",
        "market maker", "spread", "buy and sell", "market making",
    ],
)

SYSTEM_ADMIN = AgentProfile(
    agent_id="system_admin",
    display_name="System Administrator",
    persona=(
        "You are an expert in system operations, file management, and shell scripting. "
        "You handle complex filesystem tasks, process management via tmux, and "
        "automation scripts. You are careful and always check your current state "
        "before making changes."
    ),
    skill_names=["tmux", "cron"],
    tool_names=[
        "read_file",
        "write_file",
        "edit_file",
        "ls",
        "exec",
        "cron",
    ],
    triggers=[
        "file", "directory", "folder", "script", "bash", "shell", "tmux",
        "process", "background", "schedule", "cron", "automation",
    ],
)

RESEARCHER = AgentProfile(
    agent_id="researcher",
    display_name="Researcher",
    persona=(
        "You are a focused research specialist. You gather information from the web, "
        "GitHub, and other external sources. You synthesize complex data into "
        "clear, actionable summaries."
    ),
    skill_names=["github", "weather", "summarize"],
    tool_names=[
        "web_search",
        "web_fetch",
        "read_file",
    ],
    triggers=[
        "search", "find", "lookup", "github", "repo", "weather", "news",
        "summarize", "research", "information",
    ],
)

CLERK = AgentProfile(
    agent_id="clerk",
    display_name="Clerk",
    persona=(
        "You are a methodical records keeper. You manage long-term memory, "
        "summarize conversations, and handle administrative scheduling tasks."
    ),
    skill_names=["memory", "summarize", "cron"],
    tool_names=[
        "read_file",
        "write_file",
        "cron",
    ],
    triggers=[
        "remember", "memory", "fact", "record", "note", "schedule",
        "reminder", "summarize", "admin", "clerk",
    ],
)


# ─── All Profiles ─────────────────────────────────────────────────────────────

ALL_PROFILES: dict[str, AgentProfile] = {
    p.agent_id: p
    for p in [
        DEX_TRADER,
        SYSTEM_ADMIN,
        RESEARCHER,
        CLERK,
    ]
}
