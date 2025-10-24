"""Transcript capture system for ACE Claude sessions.

This module provides structured JSONL recording of Claude Agent SDK interactions,
capturing user prompts, tool invocations, tool results, and subagent completions
for replay and analysis in the skills inspector UI.

Architecture:
- TranscriptWriter: Thread-safe JSONL file writer with session metadata
- Hook functions: Capture SDK events (UserPromptSubmit, ToolStart, ToolFinish, SubagentStop)
- Integration utilities: Context managers and hook builders for easy enablement

Usage:
    # Enable transcript capture for a session
    with enable_transcript_capture(Path("docs/transcripts/session.jsonl")) as hooks:
        options = ClaudeAgentOptions(
            agents=load_subagents(root),
            hooks=hooks,
        )
        async with ClaudeSDKClient(options=options) as client:
            await client.query("Task prompt")
            async for msg in client.receive_response():
                # Messages automatically captured
                pass

    # Or add hooks manually
    transcript_hooks = build_transcript_hooks(Path("docs/transcripts/session.jsonl"))
    options = ClaudeAgentOptions(
        agents=agents,
        hooks={**existing_hooks, **transcript_hooks},
    )
"""

from __future__ import annotations

import json
import logging
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from claude_agent_sdk import (
    AgentDefinition,
    HookContext,
    HookInput,
    HookJSONOutput,
    HookMatcher,
    Message,
)

logger = logging.getLogger(__name__)


@dataclass
class EventRecord:
    """Normalized event record for transcript storage.

    Attributes:
        event_type: Hook event name (UserPromptSubmit, ToolStart, ToolFinish, SubagentStop)
        timestamp: ISO 8601 timestamp
        payload: Serialized SDK message or hook input data
        metadata: Additional context (trajectory_id, loop_type, agent_name, etc.)
    """
    event_type: str
    timestamp: str
    payload: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        """Serialize to JSON string for JSONL storage."""
        return json.dumps({
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "payload": self.payload,
            "metadata": self.metadata,
        }, default=str)


class TranscriptWriter:
    """Thread-safe JSONL writer for session transcripts.

    Manages file I/O for capturing SDK events during Claude Agent sessions.
    Ensures proper session initialization with metadata header and thread-safe
    write operations.

    Attributes:
        output_path: Path to JSONL output file
        file_handle: Open file handle (None if not started)
        lock: Threading lock for write synchronization
        session_id: Unique session identifier
    """

    def __init__(self, output_path: Path) -> None:
        """Initialize transcript writer.

        Args:
            output_path: Path to JSONL file for transcript storage
        """
        self.output_path = output_path
        self.file_handle: Any = None
        self.lock = threading.Lock()
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.started = False

    def write_session_header(
        self,
        agents: dict[str, AgentDefinition] | None = None,
        allowed_tools: list[str] | None = None,
        permission_mode: str | None = None,
        **extra_metadata: Any,
    ) -> None:
        """Write session initialization header to transcript.

        Args:
            agents: Dictionary of agent definitions by name
            allowed_tools: List of permitted tool names
            permission_mode: Permission mode (auto, ask, deny)
            **extra_metadata: Additional session metadata
        """
        with self.lock:
            if not self.started:
                self._ensure_directory()
                self.file_handle = self.output_path.open("a", encoding="utf-8")
                self.started = True

            header_payload = {
                "session_id": self.session_id,
                "timestamp": datetime.now().isoformat(),
                "agents": {
                    name: {
                        "description": agent.description,
                        "model": getattr(agent, "model", "sonnet"),
                        "tools": getattr(agent, "tools", None),
                    }
                    for name, agent in (agents or {}).items()
                },
                "allowed_tools": allowed_tools,
                "permission_mode": permission_mode,
                **extra_metadata,
            }

            record = EventRecord(
                event_type="SessionHeader",
                timestamp=datetime.now().isoformat(),
                payload=header_payload,
                metadata={"session_id": self.session_id},
            )

            self.file_handle.write(record.to_json() + "\n")
            self.file_handle.flush()
            logger.info("Wrote session header to %s", self.output_path)

    def write_event(self, record: EventRecord) -> None:
        """Write event record to transcript file.

        Args:
            record: EventRecord to write
        """
        with self.lock:
            if not self.started:
                self.write_session_header()

            if self.file_handle:
                self.file_handle.write(record.to_json() + "\n")
                self.file_handle.flush()
                logger.debug("Wrote event: %s", record.event_type)

    def close(self) -> None:
        """Close transcript file handle."""
        with self.lock:
            if self.file_handle:
                self.file_handle.close()
                self.file_handle = None
                self.started = False
                logger.info("Closed transcript: %s", self.output_path)

    def _ensure_directory(self) -> None:
        """Create output directory if it doesn't exist."""
        self.output_path.parent.mkdir(parents=True, exist_ok=True)


# Global writer instance for hook functions
_transcript_writer: TranscriptWriter | None = None


def set_transcript_writer(writer: TranscriptWriter | None) -> None:
    """Set global transcript writer instance.

    Args:
        writer: TranscriptWriter instance or None to disable
    """
    global _transcript_writer
    _transcript_writer = writer


def get_transcript_writer() -> TranscriptWriter | None:
    """Get current transcript writer instance.

    Returns:
        Active TranscriptWriter or None if not enabled
    """
    return _transcript_writer


async def record_user_prompt_submit(
    input_data: HookInput, tool_use_id: str | None, context: HookContext
) -> HookJSONOutput:
    """Hook function to capture UserPromptSubmit events.

    Records the user's initial prompt submission with metadata about
    the trajectory and loop type.

    Args:
        input_data: Hook input containing prompt data
        tool_use_id: Tool use ID (unused for this hook)
        context: Hook context with session state

    Returns:
        Empty hook output (no modifications)
    """
    writer = get_transcript_writer()
    if not writer:
        return {}

    prompt_text = input_data.get("prompt", "")
    trajectory_id = input_data.get("trajectory_id")
    loop_type = input_data.get("loop_type", "task")

    record = EventRecord(
        event_type="UserPromptSubmit",
        timestamp=datetime.now().isoformat(),
        payload={
            "prompt": prompt_text[:500],  # Truncate long prompts
            "prompt_length": len(prompt_text) if isinstance(prompt_text, str) else 0,
        },
        metadata={
            "trajectory_id": trajectory_id,
            "loop_type": loop_type,
            "session_id": writer.session_id,
        },
    )

    writer.write_event(record)
    logger.debug("Recorded UserPromptSubmit event")
    return {}


async def record_tool_start(
    input_data: HookInput, tool_use_id: str | None, context: HookContext
) -> HookJSONOutput:
    """Hook function to capture tool invocation start events.

    Records when a tool begins execution, capturing the tool name,
    input parameters, and timing information.

    Args:
        input_data: Hook input containing tool invocation data
        tool_use_id: Unique ID for this tool use
        context: Hook context with session state

    Returns:
        Empty hook output (no modifications)
    """
    writer = get_transcript_writer()
    if not writer:
        return {}

    tool_name = input_data.get("tool_name", "unknown")
    tool_input = input_data.get("tool_input", {})

    # Extract metadata from tool_input if present
    metadata_dict = {}
    if isinstance(tool_input, dict):
        # Check for common metadata patterns
        if "metadata" in tool_input:
            metadata_dict = tool_input["metadata"]

        # Sanitize tool_input for logging (remove large content)
        sanitized_input = {
            k: (v[:200] + "..." if isinstance(v, str) and len(v) > 200 else v)
            for k, v in tool_input.items()
            if k != "metadata"
        }
    else:
        sanitized_input = {"raw_input": str(tool_input)[:200]}

    record = EventRecord(
        event_type="ToolStart",
        timestamp=datetime.now().isoformat(),
        payload={
            "tool_name": tool_name,
            "tool_use_id": tool_use_id,
            "tool_input": sanitized_input,
        },
        metadata={
            "trajectory_id": metadata_dict.get("trajectory_id"),
            "loop_type": metadata_dict.get("loop_type"),
            "session_id": writer.session_id,
        },
    )

    writer.write_event(record)
    logger.debug("Recorded ToolStart event: %s", tool_name)
    return {}


async def record_tool_finish(
    input_data: HookInput, tool_use_id: str | None, context: HookContext
) -> HookJSONOutput:
    """Hook function to capture tool completion events.

    Records when a tool finishes execution, capturing the result,
    success status, and error information if applicable.

    Args:
        input_data: Hook input containing tool result data
        tool_use_id: Unique ID for this tool use
        context: Hook context with session state

    Returns:
        Empty hook output (no modifications)
    """
    writer = get_transcript_writer()
    if not writer:
        return {}

    tool_name = input_data.get("tool_name", "unknown")
    tool_result = input_data.get("tool_result", {})
    is_error = input_data.get("is_error", False)

    # Sanitize result for logging
    if isinstance(tool_result, dict):
        sanitized_result = {
            k: (v[:200] + "..." if isinstance(v, str) and len(v) > 200 else v)
            for k, v in tool_result.items()
        }
    elif isinstance(tool_result, str):
        sanitized_result = {"output": tool_result[:200] + ("..." if len(tool_result) > 200 else "")}
    else:
        sanitized_result = {"output": str(tool_result)[:200]}

    record = EventRecord(
        event_type="ToolFinish",
        timestamp=datetime.now().isoformat(),
        payload={
            "tool_name": tool_name,
            "tool_use_id": tool_use_id,
            "tool_result": sanitized_result,
            "is_error": is_error,
        },
        metadata={
            "session_id": writer.session_id,
        },
    )

    writer.write_event(record)
    logger.debug("Recorded ToolFinish event: %s (error=%s)", tool_name, is_error)
    return {}


async def record_subagent_stop(
    input_data: HookInput, tool_use_id: str | None, context: HookContext
) -> HookJSONOutput:
    """Hook function to capture subagent completion events.

    Records when a subagent finishes its execution, capturing the
    agent name, final message, and any summary information.

    Args:
        input_data: Hook input containing subagent completion data
        tool_use_id: Tool use ID (unused for this hook)
        context: Hook context with session state

    Returns:
        Empty hook output (no modifications)
    """
    writer = get_transcript_writer()
    if not writer:
        return {}

    agent_name = input_data.get("agent_name", "unknown")
    final_message = input_data.get("final_message")
    trajectory_id = input_data.get("trajectory_id")

    # Serialize final message if it's a Message object
    message_payload = None
    if final_message:
        if hasattr(final_message, "model_dump"):
            message_payload = final_message.model_dump()
        elif isinstance(final_message, dict):
            message_payload = final_message
        else:
            message_payload = {"content": str(final_message)}

    record = EventRecord(
        event_type="SubagentStop",
        timestamp=datetime.now().isoformat(),
        payload={
            "agent_name": agent_name,
            "final_message": message_payload,
        },
        metadata={
            "trajectory_id": trajectory_id,
            "session_id": writer.session_id,
        },
    )

    writer.write_event(record)
    logger.info("Recorded SubagentStop event: %s", agent_name)
    return {}


def build_transcript_hooks(output_path: Path | None = None) -> dict[str, list[HookMatcher]]:
    """Build hook matchers for transcript capture.

    Creates a dictionary of hook matchers that can be merged into
    ClaudeAgentOptions.hooks to enable transcript recording.

    Args:
        output_path: Path to JSONL transcript file. If None, uses existing writer.

    Returns:
        Dictionary mapping hook event names to HookMatcher lists

    Example:
        >>> hooks = build_transcript_hooks(Path("transcripts/session.jsonl"))
        >>> options = ClaudeAgentOptions(
        ...     agents=agents,
        ...     hooks={**existing_hooks, **hooks},
        ... )
    """
    if output_path:
        writer = TranscriptWriter(output_path)
        set_transcript_writer(writer)

    # Note: Hook event names are strings in the current SDK API
    # Based on ace_skill_utils.py and ace-task.py patterns
    return {
        # Capture user prompt submissions (if SDK supports this event)
        # Currently not in the codebase, but mentioned in UI plan
        # 'UserPromptSubmit': [
        #     HookMatcher(matcher=None, hooks=[record_user_prompt_submit]),
        # ],

        # Capture tool invocations at start
        'PreToolUse': [
            HookMatcher(matcher=None, hooks=[record_tool_start]),
        ],

        # Capture tool results at completion
        'PostToolUse': [
            HookMatcher(matcher=None, hooks=[record_tool_finish]),
        ],

        # Capture subagent completions
        'SubagentStop': [
            HookMatcher(matcher=None, hooks=[record_subagent_stop]),
        ],
    }


@contextmanager
def enable_transcript_capture(
    output_path: Path,
    agents: dict[str, AgentDefinition] | None = None,
    allowed_tools: list[str] | None = None,
    permission_mode: str | None = None,
    **extra_metadata: Any,
) -> Iterator[dict[str, list[HookMatcher]]]:
    """Context manager for transcript capture with automatic cleanup.

    Enables transcript recording for the duration of the context, automatically
    writing session header and closing the file on exit.

    Args:
        output_path: Path to JSONL transcript file
        agents: Agent definitions to record in session header
        allowed_tools: Tool names to record in session header
        permission_mode: Permission mode to record in session header
        **extra_metadata: Additional metadata for session header

    Yields:
        Dictionary of hook matchers to add to ClaudeAgentOptions

    Example:
        >>> with enable_transcript_capture(Path("transcripts/session.jsonl")) as hooks:
        ...     options = ClaudeAgentOptions(agents=agents, hooks=hooks)
        ...     async with ClaudeSDKClient(options=options) as client:
        ...         await client.query("Task prompt")
        ...         async for msg in client.receive_response():
        ...             pass
    """
    writer = TranscriptWriter(output_path)
    set_transcript_writer(writer)

    try:
        # Write session header
        writer.write_session_header(
            agents=agents,
            allowed_tools=allowed_tools,
            permission_mode=permission_mode,
            **extra_metadata,
        )

        # Yield hooks for use in ClaudeAgentOptions
        yield build_transcript_hooks(output_path=None)

    finally:
        # Cleanup
        writer.close()
        set_transcript_writer(None)


def merge_hooks(
    *hook_dicts: dict[str, list[HookMatcher]]
) -> dict[str, list[HookMatcher]]:
    """Merge multiple hook dictionaries into a single hooks configuration.

    Combines hook matchers from multiple sources, preserving all hooks
    for each event type.

    Args:
        *hook_dicts: Variable number of hook dictionaries to merge

    Returns:
        Merged dictionary with combined hook matchers

    Example:
        >>> task_hooks = build_task_hooks()
        >>> transcript_hooks = build_transcript_hooks(Path("session.jsonl"))
        >>> merged = merge_hooks(task_hooks, transcript_hooks)
        >>> options = ClaudeAgentOptions(agents=agents, hooks=merged)
    """
    merged: dict[str, list[HookMatcher]] = {}

    for hook_dict in hook_dicts:
        for event_name, matchers in hook_dict.items():
            if event_name not in merged:
                merged[event_name] = []
            merged[event_name].extend(matchers)

    return merged


__all__ = [
    "EventRecord",
    "TranscriptWriter",
    "build_transcript_hooks",
    "enable_transcript_capture",
    "get_transcript_writer",
    "merge_hooks",
    "record_subagent_stop",
    "record_tool_finish",
    "record_tool_start",
    "record_user_prompt_submit",
    "set_transcript_writer",
]
