# /// script
# dependencies = [
#     "claude-agent-sdk",
#     "anyio",
# ]
# ///
"""ACE task loop orchestrator with in-process skill generation."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

# Import skill utilities from sibling project
sys.path.append(str(Path(__file__).parent.parent / "ace-skill"))
from ace_skill_utils import (  # type: ignore  # noqa: E402
    SkillLoop,
    SkillSessionSummary,
    build_skill_reflector_hooks,
    load_subagents,
    load_slash_commands,
    summarize_skill_session,
    validate_claude_directory,
)

from claude_agent_sdk import (  # noqa: E402
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    HookContext,
    HookInput,
    HookJSONOutput,
    HookMatcher,
    Message,
    ResultMessage,
    SystemMessage,
    ToolResultBlock,
    ToolUseBlock,
)

logger = logging.getLogger(__name__)


@dataclass
class TaskCuratorSummary:
    """Structured payload emitted by the task curator."""

    summary: str = ""
    proposed_updates_token_count: int = 0
    pending_requests: list[str] = field(default_factory=list)
    duplicate_patterns: list[str] = field(default_factory=list)
    escalation_notes: dict[str, Any] = field(default_factory=dict)


class TaskCurator:
    """Lightweight curator heuristic used by the outer loop."""

    def __init__(self) -> None:
        self.tool_history: list[str] = []

    def summarize_for_outer_loop(
        self, trajectory: "TaskTrajectory", latest_message: Message
    ) -> TaskCuratorSummary:
        summary_text = self._extract_summary(latest_message)
        proposed_tokens = len(trajectory.delta_updates) * 200
        pending_requests = self._detect_pending_requests(latest_message)
        duplicate_patterns = self._detect_duplicate_patterns(latest_message)

        escalation_notes: dict[str, Any] = {}
        if duplicate_patterns:
            escalation_notes["duplicate_pattern_detected"] = True

        return TaskCuratorSummary(
            summary=summary_text,
            proposed_updates_token_count=proposed_tokens,
            pending_requests=pending_requests,
            duplicate_patterns=duplicate_patterns,
            escalation_notes=escalation_notes,
        )

    def _extract_summary(self, message: Message) -> str:
        if isinstance(message, AssistantMessage):
            content = message.content if isinstance(message.content, str) else ""
            return content[:200]
        if isinstance(message, ResultMessage):
            return "Task session completed"
        if isinstance(message, ToolUseBlock):
            return f"Tool invoked: {message.name}"
        if isinstance(message, ToolResultBlock):
            return f"Tool result received ({message.name})"
        return message.__class__.__name__

    def _detect_pending_requests(self, message: Message) -> list[str]:
        requests: list[str] = []
        if isinstance(message, AssistantMessage):
            content = message.content if isinstance(message.content, str) else ""
            lowered = content.lower()
            if "start skill loop" in lowered:
                requests.append("start_skill_loop")
            if "needs reference" in lowered:
                requests.append("fetch_reference")
        return requests

    def _detect_duplicate_patterns(self, message: Message) -> list[str]:
        duplicates: list[str] = []
        if isinstance(message, ToolUseBlock):
            self.tool_history.append(message.name)
            if len(self.tool_history) >= 3:
                tail = self.tool_history[-3:]
                if len(set(tail)) == 1:
                    duplicates.append(f"repeat:{tail[0]}")
        return duplicates


@dataclass
class TaskTrajectory:
    """Unified trajectory containing task and skill messages."""

    task_id: str
    messages: list[Message] = field(default_factory=list)
    delta_updates: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def append(self, msg: Message) -> None:
        self.messages.append(msg)

    def add_delta_update(self, deltas: Iterable[dict[str, Any]]) -> None:
        self.delta_updates.extend(deltas)

    def get_skill_sessions(self) -> list[list[Message]]:
        sessions: list[list[Message]] = []
        current: list[Message] = []

        for msg in self.messages:
            metadata = getattr(msg, "metadata", {}) or {}
            if metadata.get("loop_type") == "skill":
                current.append(msg)
            elif current:
                sessions.append(current)
                current = []

        if current:
            sessions.append(current)

        return sessions

    def get_task_messages(self) -> list[Message]:
        return [
            msg
            for msg in self.messages
            if (getattr(msg, "metadata", {}) or {}).get("loop_type") == "task"
        ]


@dataclass
class DeltaPlaybook:
    """Persistent store of skills, references, and constraints."""

    items: list[dict[str, Any]] = field(default_factory=list)
    version: int = 1
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    token_budget: int = 2000

    @classmethod
    def load(cls, path: Path) -> "DeltaPlaybook":
        if not path.exists():
            logger.info("No existing playbook at %s, creating new one", path)
            return cls()

        with path.open() as fh:
            data = json.load(fh)

        return cls(
            items=data.get("items", []),
            version=data.get("version", 1),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            token_budget=data.get("token_budget", 2000),
        )

    def save(self, path: Path) -> None:
        self.updated_at = datetime.now().isoformat()
        payload = {
            "items": self.items,
            "version": self.version,
            "updated_at": self.updated_at,
            "token_budget": self.token_budget,
        }
        with path.open("w") as fh:
            json.dump(payload, fh, indent=2)

    def to_context_dict(self) -> dict[str, Any]:
        return {
            "existing_skills": [
                item["name"]
                for item in self.items
                if item.get("type") == "skill" and "name" in item
            ],
            "constraints": [
                item
                for item in self.items
                if item.get("type") == "constraint"
            ],
            "references": [
                item
                for item in self.items
                if item.get("type") == "reference"
            ],
            "version": self.version,
        }

    def validate_and_merge(self, summary: SkillSessionSummary) -> list[dict[str, Any]]:
        accepted: list[dict[str, Any]] = []
        timestamp = datetime.now().isoformat()
        existing_skill_names = {
            item.get("name") for item in self.items if item.get("type") == "skill"
        }

        for clarification in summary.clarifications:
            delta = {
                "type": "clarification",
                "content": clarification,
                "accepted": True,
                "timestamp": timestamp,
            }
            self.items.append(delta)
            accepted.append(delta)

        for reference in summary.references:
            if isinstance(reference, str) and reference.startswith(("http://", "https://")):
                delta = {
                    "type": "reference",
                    "url": reference,
                    "accepted": True,
                    "timestamp": timestamp,
                }
                self.items.append(delta)
                accepted.append(delta)

        for index, runbook in enumerate(summary.runbook_snippets):
            skill_name = f"skill_{self.version}_{index}"
            if skill_name in existing_skill_names:
                continue
            delta = {
                "type": "skill",
                "name": skill_name,
                "code": runbook,
                "accepted": True,
                "timestamp": timestamp,
                "metadata": {
                    "tool_calls": len(summary.tool_calls),
                    "duration": summary.duration_seconds,
                },
            }
            self.items.append(delta)
            accepted.append(delta)
            existing_skill_names.add(skill_name)

        for note in summary.reflection_notes:
            lowered = note.lower()
            if any(keyword in lowered for keyword in ("limit", "avoid", "prevent")):
                delta = {
                    "type": "constraint",
                    "description": note,
                    "accepted": True,
                    "timestamp": timestamp,
                }
                self.items.append(delta)
                accepted.append(delta)

        self.version += 1
        return accepted


task_curator = TaskCurator()


async def build_task_client() -> tuple[ClaudeSDKClient, ClaudeAgentOptions]:
    task_root = Path(__file__).parent
    validation = validate_claude_directory(task_root)
    if not validation["valid"]:
        logger.warning("Task context missing agents: %s", validation["agents_missing"])

    options = ClaudeAgentOptions(
        agents=load_subagents(task_root / ".claude"),
        setting_sources=["project"],
        cwd=task_root,
        hooks=build_task_hooks(),
    )

    client = ClaudeSDKClient(options=options)
    return client, options


def build_task_hooks() -> dict[str, list[HookMatcher]]:
    async def detect_skill_need(
        input_data: HookInput, tool_use_id: str | None, context: HookContext
    ) -> HookJSONOutput:
        tool_name = input_data.get("tool_name")
        if tool_name:
            history = getattr(context, "tool_history", [])
            history.append(tool_name)
            setattr(context, "tool_history", history)
            if len(history) >= 3 and len(set(history[-3:])) == 1:
                logger.info("Repeated tool usage detected: %s", tool_name)
        return {}

    async def log_task_progress(
        input_data: HookInput, tool_use_id: str | None, context: HookContext
    ) -> HookJSONOutput:
        tool_name = input_data.get("tool_name")
        logger.info("Task loop invoked tool: %s", tool_name)
        return {}

    return {
        'PreToolUse': [
            HookMatcher(matcher=None, hooks=[detect_skill_need, log_task_progress]),
        ]
    }


async def run_task(task_prompt: str, playbook: DeltaPlaybook) -> TaskTrajectory:
    trajectory = TaskTrajectory(task_id=str(uuid.uuid4()))
    client, _ = await build_task_client()

    async with client:
        await client.query(task_prompt)

        async for msg in client.receive_response():
            metadata = getattr(msg, "metadata", None)
            if metadata is None:
                metadata = {}
                setattr(msg, "metadata", metadata)
            metadata.setdefault("loop_type", "task")
            metadata.setdefault("trajectory_id", trajectory.task_id)

            trajectory.append(msg)
            curator_summary = task_curator.summarize_for_outer_loop(trajectory, msg)

            if should_invoke_skill_loop(msg, playbook, curator_summary):
                logger.info("Escalating to skill loop")
                skill_summary = await run_skill_sub_loop(msg, playbook, trajectory)
                accepted = playbook.validate_and_merge(skill_summary)
                trajectory.add_delta_update(accepted)

                context_update = (
                    f"Skill generation complete: {skill_summary.brief()}\n"
                    f"Generated {len(skill_summary.runbook_snippets)} runbook snippets."
                )
                await client.query(context_update)

    return trajectory


def should_invoke_skill_loop(
    msg: Message, playbook: DeltaPlaybook, curator_summary: TaskCuratorSummary
) -> bool:
    if should_start_skill_inner_loop(curator_summary, playbook.token_budget):
        logger.info("Curator requested inner skill loop based on token budget")
        return True

    if isinstance(msg, AssistantMessage):
        content = msg.content if isinstance(msg.content, str) else ""
        keywords = ["reusable", "pattern", "skill", "generalize", "template"]
        if any(keyword in content.lower() for keyword in keywords):
            logger.info("Detected skill keyword in assistant message")
            return True

    if curator_summary.duplicate_patterns:
        logger.info("Duplicate tool patterns detected; triggering skill loop")
        return True

    if "start_skill_loop" in curator_summary.pending_requests:
        logger.info("Curator explicitly requested skill loop start")
        return True

    return False


def should_start_skill_inner_loop(
    curator_summary: TaskCuratorSummary, token_threshold: int
) -> bool:
    if "start_skill_loop" in curator_summary.pending_requests:
        return True
    return (
        curator_summary.proposed_updates_token_count >= token_threshold
        and curator_summary.proposed_updates_token_count > 0
    )


async def run_skill_sub_loop(
    msg: Message, playbook: DeltaPlaybook, trajectory: TaskTrajectory
) -> SkillSessionSummary:
    skill_project_root = Path(__file__).parent.parent / "ace-skill"
    validation = validate_claude_directory(skill_project_root)
    if not validation["valid"]:
        raise RuntimeError(
            f"Skill context invalid; missing agents {validation['agents_missing']}"
        )

    skill_loop = SkillLoop(
        skill_project_root=skill_project_root,
        hooks=build_skill_reflector_hooks(),
        playbook_context=playbook.to_context_dict(),
    )

    skill_prompt = extract_skill_prompt(msg)
    trajectory_id = f"{trajectory.task_id}:skill:{uuid.uuid4()}"
    logger.info("Starting skill session %s", trajectory_id)

    skill_messages: list[Message] = []
    async for skill_msg in skill_loop.run_skill_session(skill_prompt, trajectory_id):
        skill_messages.append(skill_msg)
        trajectory.append(skill_msg)

    logger.info("Skill session produced %d messages", len(skill_messages))
    return summarize_skill_session(skill_messages)


def extract_skill_prompt(msg: Message) -> str:
    if isinstance(msg, AssistantMessage):
        content = msg.content if isinstance(msg.content, str) else ""
        return (
            "Generate a reusable skill based on the following requirement:\n\n"
            f"{content}\n\n"
            "Create documented patterns, code templates, and procedures that can be applied to similar problems."
        )
    return "Generate a skill for the current task context."


async def enumerate_available_commands(client: ClaudeSDKClient) -> list[str]:
    commands: list[str] = []
    async for msg in client.receive_response():
        if isinstance(msg, SystemMessage) and getattr(msg, "subtype", "") == "init":
            command_defs = getattr(msg, "commands", [])
            commands = [getattr(cmd, "name", "") for cmd in command_defs]
            break
    return commands


def export_trajectory(trajectory: TaskTrajectory, output_path: Path) -> None:
    with output_path.open("w") as fh:
        for msg in trajectory.messages:
            if hasattr(msg, "model_dump"):
                payload = msg.model_dump()
            else:
                payload = msg.__dict__.copy()
            fh.write(json.dumps(payload, default=str) + "\n")
    logger.info("Trajectory exported to %s", output_path)


async def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="ACE Task Loop with Skill Generation")
    parser.add_argument("task_prompt", nargs="?", help="Task to execute")
    parser.add_argument(
        "--playbook",
        type=Path,
        default=Path("playbook.json"),
        help="Path to delta playbook JSON file",
    )
    parser.add_argument(
        "--export-trajectory",
        type=Path,
        help="Export trajectory to JSONL file",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate .claude directory structure and exit",
    )

    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    if args.validate:
        task_root = Path(__file__).parent
        task_validation = validate_claude_directory(task_root)
        print(f"Task context validation: {task_validation}")

        skill_root = Path(__file__).parent.parent / "ace-skill"
        skill_validation = validate_claude_directory(skill_root)
        print(f"Skill context validation: {skill_validation}")
        commands = load_slash_commands(skill_root)
        print("Skill slash commands:", [path.name for path in commands])
        return

    if not args.task_prompt:
        parser.error("task_prompt is required unless --validate is provided")

    playbook = DeltaPlaybook.load(args.playbook)
    logger.info("Loaded playbook with %d items", len(playbook.items))

    trajectory = await run_task(args.task_prompt, playbook)

    if args.export_trajectory:
        export_trajectory(trajectory, args.export_trajectory)

    playbook.save(args.playbook)
    logger.info("Playbook saved with %d items", len(playbook.items))

    print("\n=== Task Execution Summary ===")
    print(f"Task ID: {trajectory.task_id}")
    print(f"Total messages: {len(trajectory.messages)}")
    task_count = len([m for m in trajectory.messages if (getattr(m, 'metadata', {}) or {}).get('loop_type') == 'task'])
    skill_count = len([m for m in trajectory.messages if (getattr(m, 'metadata', {}) or {}).get('loop_type') == 'skill'])
    print(f"Task messages: {task_count}")
    print(f"Skill messages: {skill_count}")
    print(f"Delta updates: {len(trajectory.delta_updates)}")
    print(f"Skill sessions: {len(trajectory.get_skill_sessions())}")


if __name__ == "__main__":
    asyncio.run(main())
