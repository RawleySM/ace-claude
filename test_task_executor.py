#!/usr/bin/env python3
"""Test script for TaskExecutor functionality.

This script verifies that the TaskExecutor can be imported, initialized,
and basic functionality works as expected.
"""

import asyncio
import sys
from pathlib import Path


async def test_import():
    """Test that TaskExecutor can be imported."""
    print("Test 1: Importing TaskExecutor...")
    try:
        from ace_tools.task_executor import (
            TaskExecutor,
            TaskExecutionResult,
            execute_task,
        )
        print("  ✓ TaskExecutor imported successfully")
        return True
    except ImportError as e:
        print(f"  ✗ Failed to import TaskExecutor: {e}")
        return False


async def test_initialization():
    """Test that TaskExecutor can be initialized."""
    print("\nTest 2: Initializing TaskExecutor...")
    try:
        from ace_tools.task_executor import TaskExecutor

        # Test with auto-detected paths
        executor = TaskExecutor()
        print(f"  ✓ TaskExecutor initialized")
        print(f"    - ACE task path: {executor.ace_task_path}")
        print(f"    - ACE skill path: {executor.ace_skill_path}")

        # Verify paths exist
        if not executor.ace_task_path.exists():
            print(f"  ⚠ Warning: ace-task path does not exist: {executor.ace_task_path}")
            return False
        if not executor.ace_skill_path.exists():
            print(f"  ⚠ Warning: ace-skill path does not exist: {executor.ace_skill_path}")
            return False

        return True
    except Exception as e:
        print(f"  ✗ Failed to initialize TaskExecutor: {e}")
        return False


async def test_logging_interceptor():
    """Test that LoggingInterceptor works correctly."""
    print("\nTest 3: Testing LoggingInterceptor...")
    try:
        from ace_tools.task_executor import LoggingInterceptor

        messages = []

        def callback(msg: str):
            messages.append(msg)

        handler = LoggingInterceptor(callback)

        # Create a test logger and emit a message
        import logging
        test_logger = logging.getLogger("test_logger")
        test_logger.addHandler(handler)
        test_logger.setLevel(logging.INFO)

        test_logger.info("Test message")

        # Clean up
        test_logger.removeHandler(handler)

        if messages:
            print(f"  ✓ LoggingInterceptor captured {len(messages)} message(s)")
            print(f"    Sample: {messages[0][:80]}...")
            return True
        else:
            print("  ✗ LoggingInterceptor failed to capture messages")
            return False

    except Exception as e:
        print(f"  ✗ Failed to test LoggingInterceptor: {e}")
        return False


async def test_result_dataclass():
    """Test that TaskExecutionResult can be created."""
    print("\nTest 4: Testing TaskExecutionResult...")
    try:
        from ace_tools.task_executor import TaskExecutionResult

        # Create a success result
        result = TaskExecutionResult(
            trajectory=None,
            playbook_version=2,
            delta_count=5,
            success=True,
        )

        print(f"  ✓ TaskExecutionResult created successfully")
        print(f"    - Success: {result.success}")
        print(f"    - Playbook version: {result.playbook_version}")
        print(f"    - Delta count: {result.delta_count}")

        # Create a failure result
        error_result = TaskExecutionResult(
            trajectory=None,
            playbook_version=0,
            delta_count=0,
            success=False,
            error_message="Test error",
        )

        print(f"  ✓ Error result created successfully")
        print(f"    - Success: {error_result.success}")
        print(f"    - Error: {error_result.error_message}")

        return True
    except Exception as e:
        print(f"  ✗ Failed to test TaskExecutionResult: {e}")
        return False


async def test_convenience_function():
    """Test that the convenience function exists and has proper signature."""
    print("\nTest 5: Testing convenience function...")
    try:
        from ace_tools.task_executor import execute_task
        import inspect

        sig = inspect.signature(execute_task)
        params = list(sig.parameters.keys())

        expected_params = [
            'task_prompt',
            'playbook_path',
            'transcript_path',
            'progress_callback',
            'ace_task_path',
            'ace_skill_path',
        ]

        if set(params) == set(expected_params):
            print(f"  ✓ execute_task function has correct signature")
            print(f"    Parameters: {', '.join(params)}")
            return True
        else:
            print(f"  ✗ execute_task has unexpected parameters")
            print(f"    Expected: {expected_params}")
            print(f"    Got: {params}")
            return False

    except Exception as e:
        print(f"  ✗ Failed to test convenience function: {e}")
        return False


async def main():
    """Run all tests."""
    print("=" * 60)
    print("TaskExecutor Test Suite")
    print("=" * 60)

    results = []

    # Run tests
    results.append(await test_import())
    results.append(await test_initialization())
    results.append(await test_logging_interceptor())
    results.append(await test_result_dataclass())
    results.append(await test_convenience_function())

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = sum(results)
    total = len(results)

    print(f"Passed: {passed}/{total}")

    if passed == total:
        print("✓ All tests passed!")
        return 0
    else:
        print(f"✗ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
