"""Utility module for ACE skill loop support.

This module contains helpers for loading Claude agent definitions, running
skill-focused sessions with isolated working directories, extracting
structured deltas from streamed messages, and configuring hook matchers for
skill reflection. The implementation mirrors the detailed specification in
``plan/ACEskills_plan_7.md``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator, Callable

from claude_agent_sdk import (
    AgentDefinition,
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    HookContext,
    HookInput,
    HookJSONOutput,
    HookMatcher,
    Message,
    ResultMessage,
    ToolResultBlock,
    ToolUseBlock,
)

logger = logging.getLogger(__name__)


def _resolve_claude_root(root: Path) -> Path:
    """Return the directory that directly contains ``agents`` and ``commands``."""

    if (root / "agents").is_dir() and (root / "commands").is_dir():
        return root

    potential = root / ".claude"
    if potential.is_dir():
        return potential

    return root


def parse_agent_markdown(md_path: Path) -> AgentDefinition:
    """Parse a Claude agent definition from markdown."""

    content = md_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    description: list[str] = []
    prompt: list[str] = []
    tools: list[str] = []
    model = "sonnet"
    current_section: str | None = None

    for raw_line in lines:
        line = raw_line.strip()
        if line.startswith("## Description"):
            current_section = "description"
            continue
        if line.startswith("## Prompt"):
            current_section = "prompt"
            continue
        if line.startswith("## Tools"):
            current_section = "tools"
            continue
        if line.startswith("## Model"):
            current_section = "model"
            continue
        if line.startswith("#"):
            current_section = None
            continue

        if not line:
            continue

        if current_section == "description":
            description.append(line)
        elif current_section == "prompt":
            prompt.append(line)
        elif current_section == "tools" and line.startswith("-"):
            tools.append(line[1:].strip())
        elif current_section == "model":
            model = line

    return AgentDefinition(
        description=" ".join(description).strip(),
        prompt=" ".join(prompt).strip(),
        tools=tools or None,
        model=model.strip() or "sonnet",
    )


def load_subagents(root: Path) -> dict[str, AgentDefinition]:
    """Load every markdown agent definition within ``root``."""

    agents: dict[str, AgentDefinition] = {}
    claude_root = _resolve_claude_root(root)
    agents_dir = claude_root / "agents"

    if not agents_dir.exists():
        logger.warning("No agents directory found at %s", agents_dir)
        return agents

    for md_file in sorted(agents_dir.glob("*.md")):
        try:
            agent_def = parse_agent_markdown(md_file)
            agents[md_file.stem] = agent_def
            logger.info("Loaded agent definition: %s", md_file.stem)
        except Exception as exc:  # pragma: no cover - defensive logging only
            logger.error("Failed to parse agent markdown %s: %s", md_file, exc)

    return agents


def load_slash_commands(root: Path) -> list[Path]:
    """Return a list of available slash-command markdown files."""

    claude_root = _resolve_claude_root(root)
    commands_dir = claude_root / "commands"
    if not commands_dir.exists():
        return []
    return sorted(commands_dir.glob("*.md"))


def validate_claude_directory(root: Path) -> dict[str, Any]:
    """Validate the expected Claude configuration structure."""

    claude_root = _resolve_claude_root(root)
    agents_dir = claude_root / "agents"
    commands_dir = claude_root / "commands"

    context = "task" if "ace-task" in str(root) else "skill"
    expected_agents = [
        f"{context}-generator.md",
        f"{context}-curator.md",
        f"{context}-reflector.md",
    ]

    found_agents = [f.name for f in agents_dir.glob("*.md")] if agents_dir.exists() else []
    missing_agents = [agent for agent in expected_agents if agent not in found_agents]
    found_commands = [f.name for f in commands_dir.glob("*.md")] if commands_dir.exists() else []

    return {
        "valid": not missing_agents,
        "agents_found": found_agents,
        "agents_missing": missing_agents,
        "commands_found": found_commands,
        "context": context,
    }


@dataclass
class ToolCallSummary:
    """Summary information about a tool invocation."""

    tool_name: str
    input_summary: str
    output_summary: str
    success: bool
    duration_ms: float


@dataclass
class SkillSessionSummary:
    """Structured digest of a skill-generation session."""

    clarifications: list[str]
    references: list[str]
    tool_calls: list[ToolCallSummary]
    runbook_snippets: list[str]
    reflection_notes: list[str]
    duration_seconds: float
    success: bool

    def brief(self) -> str:
        """Return a concise textual summary for logging and prompts."""

        status = "success" if self.success else "incomplete"
        return (
            f"Skill session: {len(self.tool_calls)} tools, "
            f"{len(self.runbook_snippets)} snippets, {status}"
        )


class SkillLoop:
    """Execute a skill-generation session within an isolated context."""

    def __init__(
        self,
        skill_project_root: Path,
        hooks: dict[HookEvent, list[HookMatcher]] | None = None,
        playbook_context: dict[str, Any] | None = None,
    ) -> None:
        self.skill_project_root = skill_project_root
        self.hooks = hooks or {}
        self.playbook_context = playbook_context or {}

    async def run_skill_session(
        self, skill_prompt: str, trajectory_id: str
    ) -> AsyncIterator[Message]:
        """Stream messages from a dedicated ``ClaudeSDKClient`` instance."""

        options = ClaudeAgentOptions(
            agents=load_subagents(self.skill_project_root / ".claude"),
            setting_sources=["project"],
            cwd=self.skill_project_root,
            hooks=self.hooks,
        )

        async with ClaudeSDKClient(options=options) as client:
            enriched_prompt = self._enrich_prompt(skill_prompt)
            await client.query(enriched_prompt)

            async for msg in client.receive_response():
                metadata = getattr(msg, "metadata", None)
                if metadata is None:
                    metadata = {}
                    setattr(msg, "metadata", metadata)
                metadata.setdefault("trajectory_id", trajectory_id)
                metadata.setdefault("loop_type", "skill")
                yield msg

    def _enrich_prompt(self, base_prompt: str) -> str:
        """Inject delta playbook context into the outbound prompt."""

        if not self.playbook_context:
            return base_prompt

        parts = [base_prompt, "", "## Context from Delta Playbook"]

        existing_skills = self.playbook_context.get("existing_skills") or []
        if existing_skills:
            parts.append("Existing skills: " + ", ".join(existing_skills))

        constraints = self.playbook_context.get("constraints") or []
        if constraints:
            parts.append(f"Constraints: {len(constraints)} active")

        references = self.playbook_context.get("references") or []
        if references:
            parts.append(f"References: {len(references)} available")

        return "\n".join(parts)


def summarize_skill_session(messages: list[Message]) -> SkillSessionSummary:
    """Aggregate streamed messages into the structured summary format."""

    clarifications: list[str] = []
    references: list[str] = []
    tool_calls: list[ToolCallSummary] = []
    runbook_snippets: list[str] = []
    reflection_notes: list[str] = []

    start_time: datetime | None = None
    end_time: datetime | None = None
    success = False

    for msg in messages:
        timestamp = getattr(msg, "timestamp", None)
        if isinstance(timestamp, datetime):
            if start_time is None:
                start_time = timestamp
            end_time = timestamp
        elif isinstance(timestamp, str):
            try:
                parsed = datetime.fromisoformat(timestamp)
            except ValueError:
                parsed = None
            if parsed:
                if start_time is None:
                    start_time = parsed
                end_time = parsed

        if isinstance(msg, AssistantMessage):
            content = msg.content if isinstance(msg.content, str) else ""
            if "?" in content:
                questions = [segment.strip() for segment in content.split("?") if segment.strip()]
                clarifications.extend(questions)

        if isinstance(msg, ToolUseBlock):
            summary = ToolCallSummary(
                tool_name=msg.name,
                input_summary=str(getattr(msg, "input", ""))[:100],
                output_summary="",
                success=False,
                duration_ms=0.0,
            )
            tool_calls.append(summary)

            if msg.name == "Write":
                input_payload = getattr(msg, "input", {})
                if isinstance(input_payload, dict) and "content" in input_payload:
                    runbook_snippets.append(str(input_payload["content"]))

        if isinstance(msg, ToolResultBlock):
            for tool_summary in reversed(tool_calls):
                if not tool_summary.output_summary:
                    tool_summary.output_summary = str(getattr(msg, "content", ""))[:100]
                    tool_summary.success = not getattr(msg, "is_error", False)
                    break

        metadata = getattr(msg, "metadata", {}) or {}
        hook_decision = metadata.get("hook_decision")
        if hook_decision:
            reflection_notes.append(str(hook_decision))

        if isinstance(msg, ResultMessage):
            success = True

    duration = 0.0
    if start_time and end_time:
        duration = (end_time - start_time).total_seconds()

    return SkillSessionSummary(
        clarifications=clarifications,
        references=references,
        tool_calls=tool_calls,
        runbook_snippets=runbook_snippets,
        reflection_notes=reflection_notes,
        duration_seconds=duration,
        success=success,
    )


def extract_tool_metrics(messages: list[Message]) -> dict[str, Any]:
    """Compute aggregate tool-usage statistics for reflection."""

    tool_stats: dict[str, dict[str, Any]] = {}

    for msg in messages:
        if isinstance(msg, ToolUseBlock):
            tool_name = msg.name
            stats = tool_stats.setdefault(
                tool_name,
                {"count": 0, "successes": 0, "durations": []},
            )
            stats["count"] += 1

        if isinstance(msg, ToolResultBlock):
            for stats in tool_stats.values():
                if stats["count"] > stats.get("processed", 0):
                    if not getattr(msg, "is_error", False):
                        stats["successes"] += 1
                    stats["processed"] = stats.get("processed", 0) + 1
                    break

    return {
        "tool_counts": {name: stats["count"] for name, stats in tool_stats.items()},
        "success_rates": {
            name: (stats["successes"] / stats["count"] if stats["count"] else 0.0)
            for name, stats in tool_stats.items()
        },
    }


def build_skill_reflector_hooks() -> dict[str, list[HookMatcher]]:
    """Construct the default hook set for the skill reflector."""

    async def validate_tool_input(
        input_data: HookInput, tool_use_id: str | None, context: HookContext
    ) -> HookJSONOutput:
        tool_name = input_data.get("tool_name")
        tool_input = input_data.get("tool_input", {})

        if tool_name == "Write":
            path = tool_input.get("path", "")
            for pattern in ["/etc/", "/sys/", "~/.ssh/"]:
                if pattern in path:
                    logger.warning("Blocked Write to forbidden path: %s", path)
                    return {
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "permissionDecision": "deny",
                            "permissionDecisionReason": f"Path matches forbidden pattern: {pattern}",
                        }
                    }

        if tool_name == "Bash":
            command = tool_input.get("command", "")
            for pattern in ["rm -rf", "dd if=", "> /dev/"]:
                if pattern in command:
                    logger.warning("Blocked destructive command: %s", command)
                    return {
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "permissionDecision": "deny",
                            "permissionDecisionReason": f"Command contains destructive pattern: {pattern}",
                        }
                    }

        return {}

    async def capture_tool_result(
        input_data: HookInput, tool_use_id: str | None, context: HookContext
    ) -> HookJSONOutput:
        tool_name = input_data.get("tool_name")
        if not hasattr(context, "tool_results"):
            context.tool_results = []  # type: ignore[attr-defined]
        context.tool_results.append(  # type: ignore[attr-defined]
            {
                "tool_name": tool_name,
                "tool_use_id": tool_use_id,
                "timestamp": datetime.now().isoformat(),
            }
        )
        logger.info("Captured result for %s", tool_name)
        return {}

    async def record_subagent_completion(
        input_data: HookInput, tool_use_id: str | None, context: HookContext
    ) -> HookJSONOutput:
        agent_name = input_data.get("agent_name", "unknown")
        if not hasattr(context, "subagent_completions"):
            context.subagent_completions = []  # type: ignore[attr-defined]
        context.subagent_completions.append(  # type: ignore[attr-defined]
            {
                "agent_name": agent_name,
                "timestamp": datetime.now().isoformat(),
            }
        )
        logger.info("Subagent completed: %s", agent_name)
        return {}

    return {
        'PreToolUse': [
            HookMatcher(matcher=None, hooks=[validate_tool_input])
        ],
        'PostToolUse': [
            HookMatcher(matcher=None, hooks=[capture_tool_result])
        ],
        'SubagentStop': [
            HookMatcher(matcher=None, hooks=[record_subagent_completion])
        ],
    }


def build_custom_skill_hooks(
    validators: list[Callable[[HookInput, str | None, HookContext], Any]],
    reflectors: list[Callable[[HookInput, str | None, HookContext], Any]],
) -> dict[str, list[HookMatcher]]:
    """Create a hook configuration that layers custom logic onto defaults."""

    matchers: dict[str, list[HookMatcher]] = {
        'PreToolUse': [],
        'PostToolUse': [],
    }

    for validator in validators:
        matchers['PreToolUse'].append(
            HookMatcher(matcher=None, hooks=[validator])
        )

    for reflector in reflectors:
        matchers['PostToolUse'].append(
            HookMatcher(matcher=None, hooks=[reflector])
        )

    return matchers


__all__ = [
    "SkillLoop",
    "SkillSessionSummary",
    "ToolCallSummary",
    "build_custom_skill_hooks",
    "build_skill_reflector_hooks",
    "extract_tool_metrics",
    "load_slash_commands",
    "load_subagents",
    "parse_agent_markdown",
    "summarize_skill_session",
    "validate_claude_directory",
]
