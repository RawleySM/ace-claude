#!/usr/bin/env python3
"""Example usage of TaskExecutor for ACE task execution with UI integration.

This script demonstrates how to use the TaskExecutor class to execute
ACE tasks with progress callbacks, transcript capture, and error handling.

Requirements:
- claude-agent-sdk must be installed
- ace-task and ace-skill directories must exist
- Playbook JSON file path must be provided

Usage:
    python example_task_executor.py "Create a new API endpoint" playbook.json

    # With transcript capture
    python example_task_executor.py "Add authentication" playbook.json --transcript transcript.jsonl

    # Using convenience function
    python example_task_executor.py "Optimize database queries" playbook.json --use-function
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add parent directory to path for ace_tools import
sys.path.insert(0, str(Path(__file__).parent.parent))


async def example_with_class(
    task_prompt: str,
    playbook_path: Path,
    transcript_path: Path | None = None,
):
    """Example using TaskExecutor class directly."""
    from ace_tools.task_executor import TaskExecutor

    print("=" * 60)
    print("TaskExecutor Example - Using Class")
    print("=" * 60)
    print()

    # Create executor instance
    print("Initializing TaskExecutor...")
    executor = TaskExecutor()
    print(f"  ACE task path: {executor.ace_task_path}")
    print(f"  ACE skill path: {executor.ace_skill_path}")
    print()

    # Define progress callback
    def progress_callback(message: str):
        print(f"[Progress] {message}")

    # Execute task
    print(f"Executing task: {task_prompt}")
    print()

    result = await executor.execute_task(
        task_prompt=task_prompt,
        playbook_path=playbook_path,
        transcript_path=transcript_path,
        progress_callback=progress_callback,
    )

    # Display results
    print()
    print("=" * 60)
    print("Execution Results")
    print("=" * 60)

    if result.success:
        print("Status: SUCCESS")
        print(f"Playbook version: {result.playbook_version}")
        print(f"Delta updates: {result.delta_count}")
        print(f"Total messages: {len(result.trajectory.messages) if result.trajectory else 0}")

        if result.trajectory:
            task_messages = result.trajectory.get_task_messages()
            skill_sessions = result.trajectory.get_skill_sessions()
            print(f"Task messages: {len(task_messages)}")
            print(f"Skill sessions: {len(skill_sessions)}")
    else:
        print("Status: FAILED")
        print(f"Error: {result.error_message}")

    print()
    return result


async def example_with_function(
    task_prompt: str,
    playbook_path: Path,
    transcript_path: Path | None = None,
):
    """Example using convenience function."""
    from ace_tools.task_executor import execute_task

    print("=" * 60)
    print("TaskExecutor Example - Using Convenience Function")
    print("=" * 60)
    print()

    # Define progress callback
    progress_messages = []

    def progress_callback(message: str):
        progress_messages.append(message)
        print(f"[Progress] {message}")

    # Execute task
    print(f"Executing task: {task_prompt}")
    print()

    result = await execute_task(
        task_prompt=task_prompt,
        playbook_path=playbook_path,
        transcript_path=transcript_path,
        progress_callback=progress_callback,
    )

    # Display results
    print()
    print("=" * 60)
    print("Execution Results")
    print("=" * 60)

    if result.success:
        print("Status: SUCCESS")
        print(f"Playbook version: {result.playbook_version}")
        print(f"Delta updates: {result.delta_count}")
        print(f"Progress messages received: {len(progress_messages)}")
    else:
        print("Status: FAILED")
        print(f"Error: {result.error_message}")

    print()
    return result


async def example_error_handling(task_prompt: str):
    """Example demonstrating error handling."""
    from ace_tools.task_executor import TaskExecutor, TaskExecutionResult

    print("=" * 60)
    print("TaskExecutor Example - Error Handling")
    print("=" * 60)
    print()

    executor = TaskExecutor()

    # Test 1: Invalid playbook path
    print("Test 1: Invalid playbook directory...")
    result = await executor.execute_task(
        task_prompt=task_prompt,
        playbook_path=Path("/nonexistent/path/playbook.json"),
    )

    if not result.success:
        print(f"  ✓ Error caught: {result.error_message}")
    print()

    # Test 2: Empty task prompt
    print("Test 2: Empty task prompt...")
    try:
        result = await executor.execute_task(
            task_prompt="",
            playbook_path=Path("playbook.json"),
        )
        print(f"  ✗ Should have raised ValueError")
    except ValueError as e:
        print(f"  ✓ ValueError caught: {e}")
    print()

    # Test 3: Custom error callback
    print("Test 3: Custom error callback...")
    errors = []

    def error_callback(message: str):
        if "ERROR" in message:
            errors.append(message)

    result = await executor.execute_task(
        task_prompt=task_prompt,
        playbook_path=Path("/nonexistent/path/playbook.json"),
        progress_callback=error_callback,
    )

    if errors:
        print(f"  ✓ Captured {len(errors)} error message(s) via callback")
    print()


async def example_with_logging():
    """Example demonstrating logging interception."""
    import logging
    from ace_tools.task_executor import LoggingInterceptor

    print("=" * 60)
    print("TaskExecutor Example - Logging Interception")
    print("=" * 60)
    print()

    # Capture log messages
    captured_logs = []

    def log_callback(message: str):
        captured_logs.append(message)

    # Create interceptor
    handler = LoggingInterceptor(log_callback)

    # Create test logger
    logger = logging.getLogger("test_ace_task")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    # Emit test messages
    logger.info("Task started")
    logger.info("Processing skill generation")
    logger.info("Task completed")

    # Clean up
    logger.removeHandler(handler)

    # Display results
    print(f"Captured {len(captured_logs)} log messages:")
    for log in captured_logs:
        print(f"  - {log}")
    print()


def main():
    """Run example based on command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Example usage of TaskExecutor for ACE task execution"
    )
    parser.add_argument(
        "task_prompt",
        nargs="?",
        help="Task prompt to execute (optional for demo modes)",
    )
    parser.add_argument(
        "playbook_path",
        nargs="?",
        help="Path to playbook JSON file (optional for demo modes)",
    )
    parser.add_argument(
        "--transcript",
        type=Path,
        help="Optional path for transcript capture",
    )
    parser.add_argument(
        "--use-function",
        action="store_true",
        help="Use convenience function instead of class",
    )
    parser.add_argument(
        "--demo-logging",
        action="store_true",
        help="Run logging interception demo",
    )
    parser.add_argument(
        "--demo-errors",
        action="store_true",
        help="Run error handling demo",
    )

    args = parser.parse_args()

    # Run demo modes
    if args.demo_logging:
        asyncio.run(example_with_logging())
        return 0

    if args.demo_errors:
        task_prompt = args.task_prompt or "Demo task"
        asyncio.run(example_error_handling(task_prompt))
        return 0

    # Validate required arguments
    if not args.task_prompt:
        parser.error("task_prompt is required (unless using --demo-* flags)")
    if not args.playbook_path:
        parser.error("playbook_path is required (unless using --demo-* flags)")

    playbook_path = Path(args.playbook_path)

    # Run execution example
    try:
        if args.use_function:
            result = asyncio.run(example_with_function(
                args.task_prompt,
                playbook_path,
                args.transcript,
            ))
        else:
            result = asyncio.run(example_with_class(
                args.task_prompt,
                playbook_path,
                args.transcript,
            ))

        return 0 if result.success else 1

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
