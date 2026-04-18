"""Subagent manager for background task execution and orchestrator-style dispatch."""

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any, Dict, Set, TYPE_CHECKING

from loguru import logger

from nanobot.agent.profiles import AgentProfile, ALL_PROFILES
from nanobot.agent.registry import AgentRegistry
from nanobot.agent.tools.filesystem import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.agent.tools.shell import ExecTool
from nanobot.agent.tools.web import WebFetchTool, WebSearchTool
from nanobot.bus.events import InboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.providers.base import LLMProvider

if TYPE_CHECKING:
    from nanobot.config.schema import ExecToolConfig
    from nanobot.agent.loop import AgentLoop


class SubagentManager:
    """Manages specialist sub-agent execution with scoped tools and context."""

    def __init__(
        self,
        provider: LLMProvider,
        workspace: Path,
        bus: MessageBus,
        runner: "AgentLoop | None" = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        reasoning_effort: str | None = None,
        brave_api_key: str | None = None,
        web_proxy: str | None = None,
        exec_config: "ExecToolConfig | None" = None,
        restrict_to_workspace: bool = False,
        registry: AgentRegistry | None = None,
    ):
        from nanobot.config.schema import ExecToolConfig
        self.provider = provider
        self.workspace = workspace
        self.bus = bus
        self.runner = runner  # AgentLoop instance
        self.model = model or provider.get_default_model()
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.reasoning_effort = reasoning_effort
        self.brave_api_key = brave_api_key
        self.web_proxy = web_proxy
        self.exec_config = exec_config or ExecToolConfig()
        self.restrict_to_workspace = restrict_to_workspace
        self.registry = registry or AgentRegistry()
        
        self._running_tasks: dict[str, asyncio.Task[None]] = {}
        self._session_tasks: dict[str, set[str]] = {}  # session_key -> {task_id, ...}

    def set_runner(self, runner: "AgentLoop") -> None:
        """Set the agent runner (AgentLoop instance) for sub-agent execution."""
        self.runner = runner

    # ─── Scoped Dispatch (Synchronous — Orchestrator waits) ───────────────────

    async def dispatch(
        self,
        agent_id: str,
        task: str,
        origin_channel: str = "cli",
        origin_chat_id: str = "direct",
        session_key: str | None = None,
    ) -> str:
        """Dispatch a task to a named sub-agent and wait for the result.

        This is the primary method called by DispatchTool. It runs the sub-agent
        inline (not in the background) so the orchestrator can incorporate the
        result into its response.
        """
        if not self.runner:
            return "Error: SubagentManager has no runner assigned."

        profile = self.registry.get(agent_id)
        if not profile:
            return f"Error: Unknown sub-agent '{agent_id}'. Available: {', '.join(self.registry.all_ids())}"

        logger.info("Dispatching to [{}]: {}...", profile.display_name, task[:80])

        try:
            # Build scoped tools for this sub-agent
            scoped_tools = self._build_scoped_tools(profile)

            # Build scoped system prompt
            system_prompt = self._build_scoped_prompt(profile, task)

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": task},
            ]

            # Use the runner's agent loop logic
            final_content, _, _ = await self.runner._run_agent_loop(
                initial_messages=messages,
                tools_override=scoped_tools,
                max_iterations_override=profile.max_iterations,
            )

            if final_content is None:
                return f"Sub-agent [{profile.display_name}] completed with no output."

            logger.info("Sub-agent [{}] completed successfully.", agent_id)
            return final_content

        except Exception as e:
            logger.exception("Sub-agent [{}] failed", agent_id)
            return f"Sub-agent [{profile.display_name}] failed: {str(e)}"

    # ─── Background Spawn (Fire-and-forget) ───────────────────────────────────

    async def spawn(
        self,
        task: str,
        agent_id: str | None = None,
        label: str | None = None,
        origin_channel: str = "cli",
        origin_chat_id: str = "direct",
        session_key: str | None = None,
    ) -> str:
        """Spawn a subagent to execute a task in the background. Announces result when done."""
        task_id = str(uuid.uuid4())[:8]
        display_label = label or task[:30] + ("..." if len(task) > 30 else "")
        origin = {"channel": origin_channel, "chat_id": origin_chat_id}

        bg_task = asyncio.create_task(
            self._run_background(task_id, agent_id, task, display_label, origin)
        )
        self._running_tasks[task_id] = bg_task
        if session_key:
            self._session_tasks.setdefault(session_key, set()).add(task_id)

        def _cleanup(_: asyncio.Task) -> None:
            self._running_tasks.pop(task_id, None)
            if session_key and (ids := self._session_tasks.get(session_key)):
                ids.discard(task_id)
                if not ids:
                    del self._session_tasks[session_key]

        bg_task.add_done_callback(_cleanup)

        logger.info("Spawned background [{}]: {}", task_id, display_label)
        return f"Background task [{display_label}] started (id: {task_id}). I'll notify you when it completes."

    async def _run_background(
        self,
        task_id: str,
        agent_id: str | None,
        task: str,
        label: str,
        origin: dict[str, str],
    ) -> None:
        """Execute the subagent task and announce the result."""
        try:
            if agent_id:
                result_text = await self.dispatch(
                    agent_id=agent_id,
                    task=task,
                    origin_channel=origin["channel"],
                    origin_chat_id=origin["chat_id"],
                )
            else:
                # Fallback: unscoped execution
                result_text = await self._run_unscoped(task)

            await self._announce_result(task_id, label, task, result_text, origin, "ok")

        except Exception as e:
            logger.exception("Background task [{}] failed", task_id)
            await self._announce_result(task_id, label, task, f"Error: {str(e)}", origin, "error")

    async def _run_unscoped(self, task: str) -> str:
        """Run a task with all tools (minus spawn/dispatch) — legacy fallback."""
        if not self.runner:
            return "Error: SubagentManager has no runner assigned."

        sub_tools = ToolRegistry()
        for name in self.runner.tools.tool_names:
            if name not in ("spawn", "dispatch"):
                tool = self.runner.tools.get(name)
                if tool:
                    sub_tools.register(tool)

        system_prompt = self._build_subagent_prompt()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task},
        ]

        final_content, _, _ = await self.runner._run_agent_loop(
            initial_messages=messages,
            tools_override=sub_tools,
            max_iterations_override=15,
        )
        return final_content or "Task completed with no output."

    # ─── Scoping Helpers ──────────────────────────────────────────────────────

    def _build_scoped_tools(self, profile: AgentProfile) -> ToolRegistry:
        """Build a ToolRegistry containing only the tools in the profile."""
        scoped = ToolRegistry()
        if not self.runner:
            return scoped

        for tool_name in profile.tool_names:
            # Map simplified names in profile to actual tool names in BOB's master registry
            actual_name = {
                "read_file": "read_file",
                "write_file": "write_file",
                "edit_file": "edit_file",
                "ls": "ls",
                "exec": "exec",
                "web_search": "web_search",
                "web_fetch": "web_fetch",
                "cron": "cron",
            }.get(tool_name, tool_name)
            
            tool = self.runner.tools.get(actual_name)
            if tool:
                scoped.register(tool)
            else:
                logger.warning("Profile [{}] requests tool '{}' but it's not in the master registry.", profile.agent_id, tool_name)
        return scoped

    def _build_scoped_prompt(self, profile: AgentProfile, task: str) -> str:
        """Build a system prompt with only the profile's skills and persona."""
        from nanobot.agent.context import ContextBuilder
        from nanobot.agent.skills import SkillsLoader

        parts = []

        # 1. Sub-agent persona
        parts.append(f"# Role\n\n{profile.persona}")

        # 2. Load scoped skills
        if profile.skill_names:
            skills_loader = SkillsLoader(self.workspace)
            skills_content = skills_loader.load_skills_for_context(profile.skill_names)
            if skills_content:
                parts.append(f"# Skills\n\n{skills_content}")

        # 3. Runtime context
        runtime = ContextBuilder._build_runtime_context(None, None)
        parts.append(runtime)

        # 4. Tool usage reminder
        tool_names = ", ".join(profile.tool_names)
        parts.append(f"# Available Tools\n\nYou have access to: {tool_names}\nUse only the tools listed above. Do not reference tools you don't have.")

        return "\n\n---\n\n".join(parts)

    def _build_subagent_prompt(self) -> str:
        """Build a focused system prompt for the subagent (unscoped fallback)."""
        from nanobot.agent.context import ContextBuilder
        from nanobot.agent.skills import SkillsLoader

        time_ctx = ContextBuilder._build_runtime_context(None, None)
        parts = [f"# Subagent\n\n{time_ctx}\n\nYou are a subagent spawned to complete a specific task.\n\n## Workspace\n{self.workspace}"]

        skills_summary = SkillsLoader(self.workspace).build_skills_summary()
        if skills_summary:
            parts.append(f"## Skills\n\n{skills_summary}")

        return "\n\n".join(parts)

    async def _announce_result(
        self,
        task_id: str,
        label: str,
        task: str,
        result: str,
        origin: dict[str, str],
        status: str,
    ) -> None:
        """Announce the subagent result to the main agent via the message bus."""
        status_text = "completed successfully" if status == "ok" else "failed"

        announce_content = f"""[Subagent '{label}' {status_text}]

Task: {task}

Result:
{result}

Summarize this naturally for the user. Keep it brief (1-2 sentences). Do not mention technical details like "subagent" or task IDs."""

        msg = InboundMessage(
            channel="system",
            sender_id="subagent",
            chat_id=f"{origin['channel']}:{origin['chat_id']}",
            content=announce_content,
        )

        await self.bus.publish_inbound(msg)
    
    async def cancel_by_session(self, session_key: str) -> int:
        """Cancel all subagents for the given session. Returns count cancelled."""
        tasks = [self._running_tasks[tid] for tid in self._session_tasks.get(session_key, [])
                 if tid in self._running_tasks and not self._running_tasks[tid].done()]
        for t in tasks:
            t.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        return len(tasks)

    def get_running_count(self) -> int:
        """Return the number of currently running subagents."""
        return len(self._running_tasks)
