"""Async task executor for ACE task loop with UI integration.

This module provides a high-level async wrapper around ace-task.py's run_task
function, enabling UI components to execute tasks with progress callbacks,
transcript capture, and proper error handling.

Features:
- Async task execution with progress streaming
- Transcript capture integration for UI replay
- Logging interception and forwarding to UI
- Automatic playbook loading and saving
- Comprehensive error handling with clear messages
- Thread-safe logging capture for concurrent operations

Usage:
    from ace_tools.task_executor import TaskExecutor
    from pathlib import Path

    executor = TaskExecutor(
        ace_task_path=Path("/path/to/ace-task"),
        ace_skill_path=Path("/path/to/ace-skill"),
    )

    async def on_progress(message: str):
        print(f"Progress: {message}")

    result = await executor.execute_task(
        task_prompt="Create a new feature",
        playbook_path=Path("playbook.json"),
        transcript_path=Path("transcript.jsonl"),
        progress_callback=on_progress,
    )

    print(f"Task completed with {len(result.messages)} messages")
"""

from __future__ import annotations

import asyncio
import logging
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class TaskExecutionResult:
    """Result of a task execution.

    Attributes:
        trajectory: TaskTrajectory from ace-task.py containing all messages
        playbook_version: Version number after updates were merged
        delta_count: Number of delta updates applied
        success: Whether execution completed without errors
        error_message: Error description if execution failed
    """
    trajectory: Any  # TaskTrajectory from ace-task.py
    playbook_version: int
    delta_count: int
    success: bool
    error_message: str | None = None


class LoggingInterceptor(logging.Handler):
    """Thread-safe logging handler that forwards logs to a callback.

    Captures log records from ace-task.py and ace-skill modules and
    forwards formatted messages to the UI via a progress callback.

    Attributes:
        callback: Function to call with formatted log messages
        lock: Thread lock for safe concurrent access
    """

    def __init__(self, callback: Callable[[str], None]) -> None:
        """Initialize logging interceptor.

        Args:
            callback: Function to call with log messages (signature: str -> None)
        """
        super().__init__()
        self.callback = callback
        self.lock = threading.Lock()
        self.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        ))

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record to the callback.

        Args:
            record: Log record to emit
        """
        try:
            with self.lock:
                msg = self.format(record)
                self.callback(msg)
        except Exception:
            # Prevent logging errors from breaking execution
            self.handleError(record)


class TaskExecutor:
    """Async executor for ACE tasks with UI integration.

    Provides a high-level interface for executing tasks from ace-task.py
    with transcript capture, progress callbacks, and proper error handling.

    Attributes:
        ace_task_path: Path to ace-task directory
        ace_skill_path: Path to ace-skill directory
        _run_task: Imported run_task function from ace-task.py
        _DeltaPlaybook: Imported DeltaPlaybook class from ace-task.py
        _TaskTrajectory: Imported TaskTrajectory class from ace-task.py
    """

    def __init__(
        self,
        ace_task_path: Path | None = None,
        ace_skill_path: Path | None = None,
    ) -> None:
        """Initialize task executor.

        Args:
            ace_task_path: Path to ace-task directory (auto-detected if None)
            ace_skill_path: Path to ace-skill directory (auto-detected if None)

        Raises:
            ImportError: If ace-task.py or dependencies cannot be imported
        """
        # Auto-detect paths relative to this file if not provided
        if ace_task_path is None:
            ace_task_path = Path(__file__).parent.parent / "ace-task"
        if ace_skill_path is None:
            ace_skill_path = Path(__file__).parent.parent / "ace-skill"

        self.ace_task_path = ace_task_path.resolve()
        self.ace_skill_path = ace_skill_path.resolve()

        # Validate paths
        if not self.ace_task_path.exists():
            raise FileNotFoundError(
                f"ace-task directory not found at {self.ace_task_path}"
            )
        if not self.ace_skill_path.exists():
            raise FileNotFoundError(
                f"ace-skill directory not found at {self.ace_skill_path}"
            )

        # Import required modules from ace-task
        self._setup_python_path()
        self._import_ace_task_modules()

    def _setup_python_path(self) -> None:
        """Add ace-task and ace-skill to Python path for imports."""
        task_path_str = str(self.ace_task_path)
        skill_path_str = str(self.ace_skill_path)

        if task_path_str not in sys.path:
            sys.path.insert(0, task_path_str)
        if skill_path_str not in sys.path:
            sys.path.insert(0, skill_path_str)

    def _import_ace_task_modules(self) -> None:
        """Import required classes and functions from ace-task.py.

        Raises:
            ImportError: If imports fail
        """
        try:
            # Import from ace-task module
            # Note: The module is named 'ace-task' with a hyphen
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "ace_task",
                self.ace_task_path / "ace-task.py"
            )
            if spec is None or spec.loader is None:
                raise ImportError("Failed to load ace-task.py module spec")

            ace_task_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(ace_task_module)

            # Extract required components
            self._run_task = ace_task_module.run_task
            self._DeltaPlaybook = ace_task_module.DeltaPlaybook
            self._TaskTrajectory = ace_task_module.TaskTrajectory

            logger.info("Successfully imported ace-task modules")

        except Exception as e:
            raise ImportError(
                f"Failed to import from ace-task.py: {e}\n"
                f"Task path: {self.ace_task_path}\n"
                f"Skill path: {self.ace_skill_path}"
            ) from e

    async def execute_task(
        self,
        task_prompt: str,
        playbook_path: Path,
        transcript_path: Path | None = None,
        progress_callback: Callable[[str], None] | None = None,
    ) -> TaskExecutionResult:
        """Execute a task with optional transcript capture and progress updates.

        This is the main entry point for task execution. It handles:
        1. Loading the playbook from disk
        2. Setting up transcript capture (if path provided)
        3. Installing logging interceptor (if callback provided)
        4. Running the task via ace-task.py's run_task function
        5. Saving the updated playbook
        6. Returning results with error handling

        Args:
            task_prompt: User's task description to execute
            playbook_path: Path to playbook JSON file (loaded and saved)
            transcript_path: Optional path for transcript JSONL capture
            progress_callback: Optional callback for progress updates (signature: str -> None)

        Returns:
            TaskExecutionResult containing trajectory, playbook info, and status

        Raises:
            FileNotFoundError: If playbook_path parent directory doesn't exist
            ValueError: If task_prompt is empty
            Exception: Any execution errors (captured in result.error_message)
        """
        # Validate inputs
        if not task_prompt or not task_prompt.strip():
            raise ValueError("task_prompt cannot be empty")

        if not playbook_path.parent.exists():
            raise FileNotFoundError(
                f"Playbook directory does not exist: {playbook_path.parent}"
            )

        # Set up progress callback (no-op if None)
        callback = progress_callback or (lambda msg: None)

        try:
            # Step 1: Load playbook
            callback("Loading playbook...")
            playbook = await self._load_playbook(playbook_path)
            callback(f"Loaded playbook version {playbook.version} with {len(playbook.items)} items")

            # Step 2: Set up transcript capture if requested
            transcript_context = None
            if transcript_path:
                callback(f"Enabling transcript capture to {transcript_path}")
                transcript_context = await self._setup_transcript_capture(
                    transcript_path,
                    callback,
                )

            # Step 3: Set up logging interception
            log_handler = None
            if progress_callback:
                log_handler = self._setup_logging_interceptor(progress_callback)

            try:
                # Step 4: Execute the task
                callback(f"Starting task execution: {task_prompt[:100]}...")
                trajectory = await self._run_task(task_prompt, playbook)
                callback(f"Task completed with {len(trajectory.messages)} messages")

                # Step 5: Save updated playbook
                callback("Saving playbook updates...")
                await self._save_playbook(playbook, playbook_path)
                callback(f"Playbook saved (version {playbook.version}, {len(trajectory.delta_updates)} deltas)")

                # Step 6: Return success result
                return TaskExecutionResult(
                    trajectory=trajectory,
                    playbook_version=playbook.version,
                    delta_count=len(trajectory.delta_updates),
                    success=True,
                )

            finally:
                # Clean up logging interceptor
                if log_handler:
                    self._cleanup_logging_interceptor(log_handler)

                # Clean up transcript capture
                if transcript_context:
                    await self._cleanup_transcript_capture(transcript_context)

        except Exception as e:
            error_msg = f"Task execution failed: {type(e).__name__}: {str(e)}"
            logger.exception("Task execution error")
            callback(f"ERROR: {error_msg}")

            # Return error result
            return TaskExecutionResult(
                trajectory=None,
                playbook_version=0,
                delta_count=0,
                success=False,
                error_message=error_msg,
            )

    async def _load_playbook(self, path: Path) -> Any:
        """Load playbook from disk.

        Args:
            path: Path to playbook JSON file

        Returns:
            DeltaPlaybook instance

        Raises:
            Exception: If loading fails
        """
        try:
            # DeltaPlaybook.load is synchronous, wrap in executor
            loop = asyncio.get_event_loop()
            playbook = await loop.run_in_executor(
                None,
                self._DeltaPlaybook.load,
                path,
            )
            return playbook
        except Exception as e:
            raise Exception(f"Failed to load playbook from {path}: {e}") from e

    async def _save_playbook(self, playbook: Any, path: Path) -> None:
        """Save playbook to disk.

        Args:
            playbook: DeltaPlaybook instance
            path: Path to playbook JSON file

        Raises:
            Exception: If saving fails
        """
        try:
            # Ensure parent directory exists
            path.parent.mkdir(parents=True, exist_ok=True)

            # DeltaPlaybook.save is synchronous, wrap in executor
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                playbook.save,
                path,
            )
        except Exception as e:
            raise Exception(f"Failed to save playbook to {path}: {e}") from e

    async def _setup_transcript_capture(
        self,
        transcript_path: Path,
        callback: Callable[[str], None],
    ) -> dict[str, Any]:
        """Set up transcript capture for the task execution.

        Args:
            transcript_path: Path to JSONL transcript file
            callback: Progress callback

        Returns:
            Context dict for cleanup
        """
        try:
            from ace_tools.transcript_capture import (
                TranscriptWriter,
                set_transcript_writer,
            )

            # Ensure transcript directory exists
            transcript_path.parent.mkdir(parents=True, exist_ok=True)

            # Create and activate transcript writer
            writer = TranscriptWriter(transcript_path)
            writer.write_session_header(
                agents=None,  # Will be populated by ace-task client
                extra_metadata={"executor": "TaskExecutor"},
            )
            set_transcript_writer(writer)

            callback(f"Transcript capture enabled: {transcript_path}")

            return {
                "writer": writer,
                "path": transcript_path,
            }

        except ImportError:
            callback("Warning: transcript_capture module not available")
            return {}
        except Exception as e:
            callback(f"Warning: Failed to enable transcript capture: {e}")
            return {}

    async def _cleanup_transcript_capture(self, context: dict[str, Any]) -> None:
        """Clean up transcript capture resources.

        Args:
            context: Context dict from setup
        """
        if not context:
            return

        try:
            from ace_tools.transcript_capture import set_transcript_writer

            writer = context.get("writer")
            if writer:
                writer.close()

            set_transcript_writer(None)

        except Exception as e:
            logger.warning("Failed to cleanup transcript capture: %s", e)

    def _setup_logging_interceptor(
        self,
        callback: Callable[[str], None],
    ) -> LoggingInterceptor:
        """Install logging handler to intercept ace-task logs.

        Args:
            callback: Progress callback to forward logs to

        Returns:
            LoggingInterceptor handler (for cleanup)
        """
        handler = LoggingInterceptor(callback)
        handler.setLevel(logging.INFO)

        # Add to relevant loggers
        loggers_to_intercept = [
            logging.getLogger("ace_task"),
            logging.getLogger("ace_skill_utils"),
            logging.getLogger("claude_agent_sdk"),
        ]

        for log in loggers_to_intercept:
            log.addHandler(handler)

        return handler

    def _cleanup_logging_interceptor(self, handler: LoggingInterceptor) -> None:
        """Remove logging handler.

        Args:
            handler: Handler to remove
        """
        loggers_to_cleanup = [
            logging.getLogger("ace_task"),
            logging.getLogger("ace_skill_utils"),
            logging.getLogger("claude_agent_sdk"),
        ]

        for log in loggers_to_cleanup:
            log.removeHandler(handler)


# Convenience function for simple usage
async def execute_task(
    task_prompt: str,
    playbook_path: Path,
    transcript_path: Path | None = None,
    progress_callback: Callable[[str], None] | None = None,
    ace_task_path: Path | None = None,
    ace_skill_path: Path | None = None,
) -> TaskExecutionResult:
    """Convenience function to execute a task without managing an executor instance.

    Args:
        task_prompt: User's task description
        playbook_path: Path to playbook JSON file
        transcript_path: Optional path for transcript capture
        progress_callback: Optional callback for progress updates
        ace_task_path: Optional custom path to ace-task directory
        ace_skill_path: Optional custom path to ace-skill directory

    Returns:
        TaskExecutionResult with execution results and status

    Example:
        result = await execute_task(
            "Create a new API endpoint",
            Path("playbook.json"),
            progress_callback=print,
        )

        if result.success:
            print(f"Task completed with {result.delta_count} updates")
        else:
            print(f"Task failed: {result.error_message}")
    """
    executor = TaskExecutor(
        ace_task_path=ace_task_path,
        ace_skill_path=ace_skill_path,
    )

    return await executor.execute_task(
        task_prompt=task_prompt,
        playbook_path=playbook_path,
        transcript_path=transcript_path,
        progress_callback=progress_callback,
    )


__all__ = [
    "TaskExecutor",
    "TaskExecutionResult",
    "LoggingInterceptor",
    "execute_task",
]
