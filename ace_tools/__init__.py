"""ACE Tools - Session Inspector and Analysis Utilities.

This package provides tools for inspecting, analyzing, and curating
ACE (Agent-Centric Engineering) task and skill loop trajectories.
"""

from .transcript_capture import (
    EventRecord,
    TranscriptWriter,
    build_transcript_hooks,
    enable_transcript_capture,
    merge_hooks,
)

try:
    from .models import SessionModel, SkillOutcome, TranscriptLoader
    _has_models = True
except ImportError:
    _has_models = False

try:
    from .task_executor import (
        TaskExecutor,
        TaskExecutionResult,
        execute_task,
    )
    _has_task_executor = True
except ImportError:
    _has_task_executor = False

__version__ = "0.1.0"

# Build __all__ list dynamically based on available imports
_base_exports = [
    "EventRecord",
    "TranscriptWriter",
    "build_transcript_hooks",
    "enable_transcript_capture",
    "merge_hooks",
]

_all_exports = _base_exports.copy()

if _has_models:
    _all_exports.extend([
        "SessionModel",
        "SkillOutcome",
        "TranscriptLoader",
    ])

if _has_task_executor:
    _all_exports.extend([
        "TaskExecutor",
        "TaskExecutionResult",
        "execute_task",
    ])

__all__ = _all_exports
