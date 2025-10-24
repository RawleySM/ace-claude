#!/usr/bin/env python3
"""
End-to-End Test Suite for ACE Claude System

This test suite verifies that all components of the ACE Claude system
are properly configured and can work together.
"""

import asyncio
import sys
from pathlib import Path

# Set up paths
repo_root = Path(__file__).parent
sys.path.insert(0, str(repo_root / "ace-skill"))
sys.path.insert(0, str(repo_root / "ace-task"))

print("=" * 60)
print("ACE Claude E2E Test Suite")
print("=" * 60)
print()

# Test 1: Module imports
print("Test 1: Module Imports")
print("-" * 40)
try:
    from ace_skill_utils import (
        SkillLoop,
        validate_claude_directory,
        load_subagents,
        build_skill_reflector_hooks
    )
    print("✓ ace_skill_utils imported")

    # Import ace-task module
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'ace_task',
        repo_root / 'ace-task' / 'ace-task.py'
    )
    ace_task = importlib.util.module_from_spec(spec)
    sys.modules['ace_task'] = ace_task
    spec.loader.exec_module(ace_task)

    TaskTrajectory = ace_task.TaskTrajectory
    DeltaPlaybook = ace_task.DeltaPlaybook
    TaskCurator = ace_task.TaskCurator
    build_task_client = ace_task.build_task_client
    build_task_hooks = ace_task.build_task_hooks

    print("✓ ace_task imported")
    print("✓ All core classes available")
    print()
except Exception as e:
    print(f"✗ Import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 2: Directory validation
print("Test 2: Directory Structure Validation")
print("-" * 40)
try:
    task_root = repo_root / "ace-task"
    task_validation = validate_claude_directory(task_root)
    print(f"Task context: {task_validation['context']}")
    print(f"  Agents found: {', '.join(task_validation['agents_found'])}")
    print(f"  Commands found: {', '.join(task_validation['commands_found'])}")
    print(f"  Valid: {task_validation['valid']}")

    if not task_validation['valid']:
        print(f"  ✗ Missing agents: {task_validation['agents_missing']}")
        sys.exit(1)
    print("  ✓ Task context valid")

    skill_root = repo_root / "ace-skill"
    skill_validation = validate_claude_directory(skill_root)
    print(f"Skill context: {skill_validation['context']}")
    print(f"  Agents found: {', '.join(skill_validation['agents_found'])}")
    print(f"  Commands found: {', '.join(skill_validation['commands_found'])}")
    print(f"  Valid: {skill_validation['valid']}")

    if not skill_validation['valid']:
        print(f"  ✗ Missing agents: {skill_validation['agents_missing']}")
        sys.exit(1)
    print("  ✓ Skill context valid")
    print()
except Exception as e:
    print(f"✗ Validation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: Agent loading
print("Test 3: Agent Definition Loading")
print("-" * 40)
try:
    task_agents = load_subagents(task_root / ".claude")
    print(f"Task agents loaded: {list(task_agents.keys())}")
    for name, agent in task_agents.items():
        print(f"  - {name}: {agent.description[:50]}...")
    print("  ✓ Task agents loaded successfully")

    skill_agents = load_subagents(skill_root / ".claude")
    print(f"Skill agents loaded: {list(skill_agents.keys())}")
    for name, agent in skill_agents.items():
        print(f"  - {name}: {agent.description[:50]}...")
    print("  ✓ Skill agents loaded successfully")
    print()
except Exception as e:
    print(f"✗ Agent loading failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Hook configuration
print("Test 4: Hook System Configuration")
print("-" * 40)
try:
    task_hooks = build_task_hooks()
    print(f"Task hooks configured: {list(task_hooks.keys())}")
    for event, matchers in task_hooks.items():
        print(f"  - {event}: {len(matchers)} matcher(s)")
    print("  ✓ Task hooks built successfully")

    skill_hooks = build_skill_reflector_hooks()
    print(f"Skill hooks configured: {list(skill_hooks.keys())}")
    for event, matchers in skill_hooks.items():
        print(f"  - {event}: {len(matchers)} matcher(s)")
    print("  ✓ Skill hooks built successfully")
    print()
except Exception as e:
    print(f"✗ Hook configuration failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 5: Playbook operations
print("Test 5: Delta Playbook Operations")
print("-" * 40)
try:
    playbook = DeltaPlaybook.load(task_root / "playbook.json")
    print(f"Playbook loaded:")
    print(f"  - Version: {playbook.version}")
    print(f"  - Items: {len(playbook.items)}")
    print(f"  - Token budget: {playbook.token_budget}")
    print(f"  - Updated: {playbook.updated_at}")

    context = playbook.to_context_dict()
    print(f"Context generated:")
    print(f"  - Skills: {len(context['existing_skills'])}")
    print(f"  - Constraints: {len(context['constraints'])}")
    print(f"  - References: {len(context['references'])}")
    print("  ✓ Playbook operations successful")
    print()
except Exception as e:
    print(f"✗ Playbook operations failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 6: Trajectory operations
print("Test 6: Task Trajectory Operations")
print("-" * 40)
try:
    import uuid
    from claude_agent_sdk import AssistantMessage

    trajectory = TaskTrajectory(task_id=str(uuid.uuid4()))
    print(f"Trajectory created: {trajectory.task_id[:8]}...")

    # Add a test message
    test_msg = AssistantMessage(content="Test message", model="test-model")
    setattr(test_msg, 'metadata', {'loop_type': 'task'})
    trajectory.append(test_msg)
    print(f"  - Messages: {len(trajectory.messages)}")

    # Test delta updates
    trajectory.add_delta_update([{"type": "test", "content": "test delta"}])
    print(f"  - Delta updates: {len(trajectory.delta_updates)}")

    # Test session extraction
    task_messages = trajectory.get_task_messages()
    print(f"  - Task messages: {len(task_messages)}")

    skill_sessions = trajectory.get_skill_sessions()
    print(f"  - Skill sessions: {len(skill_sessions)}")
    print("  ✓ Trajectory operations successful")
    print()
except Exception as e:
    print(f"✗ Trajectory operations failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 7: Curator operations
print("Test 7: Task Curator Operations")
print("-" * 40)
try:
    curator = TaskCurator()
    test_trajectory = TaskTrajectory(task_id="test")
    test_msg = AssistantMessage(content="This is a test with reusable patterns", model="test-model")

    summary = curator.summarize_for_outer_loop(test_trajectory, test_msg)
    print(f"Curator summary generated:")
    print(f"  - Summary: {summary.summary[:50]}...")
    print(f"  - Proposed token count: {summary.proposed_updates_token_count}")
    print(f"  - Pending requests: {len(summary.pending_requests)}")
    print(f"  - Duplicate patterns: {len(summary.duplicate_patterns)}")
    print("  ✓ Curator operations successful")
    print()
except Exception as e:
    print(f"✗ Curator operations failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Summary
print("=" * 60)
print("✅ All E2E Tests PASSED")
print("=" * 60)
print()
print("System Status:")
print("  ✓ Module imports working")
print("  ✓ Directory structure valid")
print("  ✓ Agent definitions loaded")
print("  ✓ Hook system configured")
print("  ✓ Playbook operations functional")
print("  ✓ Trajectory tracking working")
print("  ✓ Curator logic operational")
print()
print("The ACE Claude system is ready for task execution.")
print("Note: Full task execution requires Claude Code CLI authentication.")
