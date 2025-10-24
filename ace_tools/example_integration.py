#!/usr/bin/env python3
"""Example integration of transcript capture with ACE task loop.

This demonstrates how to enable transcript capture for an ACE task session,
showing three integration patterns:

1. Context manager pattern (recommended)
2. Manual hook merging
3. CLI flag integration

Run with:
    python ace-tools/example_integration.py --enable-transcript docs/transcripts/session.jsonl "Build a web app"
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ace_tools.transcript_capture import (
    build_transcript_hooks,
    enable_transcript_capture,
    merge_hooks,
)


def example_1_context_manager(transcript_path: Path) -> None:
    """Example 1: Using context manager (simplest approach).

    The context manager handles setup and cleanup automatically.
    """
    print(f"\n=== Example 1: Context Manager Pattern ===")
    print(f"Transcript: {transcript_path}")

    # Simulate agent definitions (normally from load_subagents)
    from claude_agent_sdk import AgentDefinition

    agents = {
        "task-generator": AgentDefinition(
            description="Generates task execution plans",
            prompt="You are a task generator...",
            model="sonnet",
        ),
    }

    with enable_transcript_capture(
        output_path=transcript_path,
        agents=agents,
        allowed_tools=["Read", "Write", "Bash", "Grep"],
        permission_mode="auto",
        task_id="example-task-001",
    ) as hooks:
        print(f"Hooks enabled: {list(hooks.keys())}")
        print(f"Session header written to {transcript_path}")

        # Use hooks in ClaudeAgentOptions
        # options = ClaudeAgentOptions(agents=agents, hooks=hooks)
        # async with ClaudeSDKClient(options=options) as client:
        #     await client.query(task_prompt)
        #     async for msg in client.receive_response():
        #         # Messages automatically captured
        #         pass

    print("Context exited, transcript closed")


def example_2_manual_merge(transcript_path: Path) -> None:
    """Example 2: Manual hook merging for advanced control.

    Merge transcript hooks with existing task/skill hooks.
    """
    print(f"\n=== Example 2: Manual Hook Merging ===")
    print(f"Transcript: {transcript_path}")

    # Build transcript hooks
    transcript_hooks = build_transcript_hooks(transcript_path)

    # Simulate existing task hooks
    from claude_agent_sdk import HookMatcher

    async def detect_skill_need(input_data, tool_use_id, context):
        print("Detecting skill need...")
        return {}

    task_hooks = {
        'PreToolUse': [
            HookMatcher(matcher=None, hooks=[detect_skill_need]),
        ]
    }

    # Merge hooks
    merged_hooks = merge_hooks(task_hooks, transcript_hooks)

    print(f"Merged hooks: {list(merged_hooks.keys())}")
    print(f"PreToolUse hooks count: {len(merged_hooks.get('PreToolUse', []))}")
    print(f"PostToolUse hooks count: {len(merged_hooks.get('PostToolUse', []))}")
    print(f"SubagentStop hooks count: {len(merged_hooks.get('SubagentStop', []))}")

    # Use merged hooks
    # options = ClaudeAgentOptions(agents=agents, hooks=merged_hooks)


def example_3_cli_integration() -> None:
    """Example 3: CLI flag integration pattern.

    Shows how to add --enable-transcript flag to ace-task.py
    """
    print(f"\n=== Example 3: CLI Flag Integration ===")
    print("""
To integrate with ace-task.py, add these changes:

1. Import transcript capture:
   ```python
   from pathlib import Path
   from ace_tools.transcript_capture import enable_transcript_capture, merge_hooks
   ```

2. Add CLI argument:
   ```python
   parser.add_argument(
       "--enable-transcript",
       type=Path,
       help="Enable transcript capture to JSONL file",
   )
   ```

3. Modify build_task_client():
   ```python
   async def build_task_client(transcript_path: Path | None = None):
       task_root = Path(__file__).parent
       validation = validate_claude_directory(task_root)

       # Build base hooks
       base_hooks = build_task_hooks()

       # Merge with transcript hooks if enabled
       if transcript_path:
           agents = load_subagents(task_root / ".claude")
           with enable_transcript_capture(
               output_path=transcript_path,
               agents=agents,
           ) as transcript_hooks:
               hooks = merge_hooks(base_hooks, transcript_hooks)
       else:
           hooks = base_hooks

       options = ClaudeAgentOptions(
           agents=load_subagents(task_root / ".claude"),
           setting_sources=["project"],
           cwd=task_root,
           hooks=hooks,
       )

       client = ClaudeSDKClient(options=options)
       return client, options
   ```

4. Pass transcript path to run_task():
   ```python
   if args.enable_transcript:
       logger.info("Transcript capture enabled: %s", args.enable_transcript)
       trajectory = await run_task(
           args.task_prompt,
           playbook,
           transcript_path=args.enable_transcript
       )
   ```

5. Run with transcript enabled:
   ```bash
   python ace-task/ace-task.py \\
       --enable-transcript docs/transcripts/session.jsonl \\
       "Build a web application"
   ```
    """)


def main() -> None:
    """Run integration examples."""
    parser = argparse.ArgumentParser(
        description="Demonstrate transcript capture integration patterns"
    )
    parser.add_argument(
        "--example",
        type=int,
        choices=[1, 2, 3],
        default=1,
        help="Example to run (1=context manager, 2=manual merge, 3=CLI integration)",
    )
    parser.add_argument(
        "--transcript",
        type=Path,
        default=Path("docs/transcripts/example_session.jsonl"),
        help="Path to transcript output file",
    )

    args = parser.parse_args()

    # Ensure output directory exists
    args.transcript.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("ACE Transcript Capture Integration Examples")
    print("=" * 60)

    if args.example == 1:
        example_1_context_manager(args.transcript)
    elif args.example == 2:
        example_2_manual_merge(args.transcript)
    elif args.example == 3:
        example_3_cli_integration()

    print("\n" + "=" * 60)
    print("Examples complete!")
    print(f"Transcript file: {args.transcript}")
    if args.transcript.exists():
        print(f"File size: {args.transcript.stat().st_size} bytes")
    print("=" * 60)


if __name__ == "__main__":
    main()
