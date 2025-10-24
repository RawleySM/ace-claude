#!/usr/bin/env python3
"""Basic tests for ACE Tools models."""

import json
import sys
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

print("Testing ACE Tools Models")
print("=" * 60)

# Test 1: Import models
print("\n1. Testing imports...")
try:
    from ace_tools.models import EventRecord, SessionModel, SkillOutcome, TranscriptLoader
    print("   ✓ All models imported successfully")
except ImportError as e:
    print(f"   ✗ Import failed: {e}")
    sys.exit(1)

# Test 2: Create EventRecord
print("\n2. Testing EventRecord creation...")
try:
    event = EventRecord(
        event_type="tool_use",
        timestamp=datetime.now(),
        sdk_block={"name": "test_tool", "input": {"arg": "value"}},
        loop_type="task",
    )
    print(f"   ✓ EventRecord created: {event.event_type}")
    print(f"     - Timestamp: {event.timestamp}")
    print(f"     - Loop type: {event.loop_type}")
except Exception as e:
    print(f"   ✗ EventRecord creation failed: {e}")
    sys.exit(1)

# Test 3: Create SkillOutcome
print("\n3. Testing SkillOutcome creation...")
try:
    outcome = SkillOutcome(
        tool_name="Bash",
        tool_input={"command": "ls -la"},
        tool_output="total 42\ndrwxr-xr-x...",
        success=True,
    )
    print(f"   ✓ SkillOutcome created: {outcome.tool_name}")
    print(f"     - Success: {outcome.success}")
    print(f"     - Output length: {len(outcome.tool_output)}")
except Exception as e:
    print(f"   ✗ SkillOutcome creation failed: {e}")
    sys.exit(1)

# Test 4: Create SessionModel
print("\n4. Testing SessionModel creation...")
try:
    session = SessionModel(
        session_id="test-session-001",
        task_id="test-task-001",
        events=[event],
        playbook_context={"version": 1, "existing_skills": []},
    )
    print(f"   ✓ SessionModel created: {session.session_id}")
    print(f"     - Task ID: {session.task_id}")
    print(f"     - Events: {len(session.events)}")
    print(f"     - Playbook version: {session.playbook_context.get('version')}")
except Exception as e:
    print(f"   ✗ SessionModel creation failed: {e}")
    sys.exit(1)

# Test 5: Filter events
print("\n5. Testing event filtering...")
try:
    # Add more events
    session.events.append(
        EventRecord(
            event_type="tool_result",
            timestamp=datetime.now(),
            sdk_block={"content": "success", "is_error": False},
            loop_type="task",
        )
    )
    session.events.append(
        EventRecord(
            event_type="assistant_message",
            timestamp=datetime.now(),
            sdk_block={"content": "Here's what I found..."},
            loop_type="skill",
        )
    )

    tool_calls = session.get_tool_calls()
    skill_events = session.get_skill_events()
    task_events = session.get_task_events()

    print(f"   ✓ Event filtering working:")
    print(f"     - Tool calls: {len(tool_calls)}")
    print(f"     - Skill events: {len(skill_events)}")
    print(f"     - Task events: {len(task_events)}")
except Exception as e:
    print(f"   ✗ Event filtering failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 6: Curator tags
print("\n6. Testing curator tags...")
try:
    session.add_curator_tag(0, "important")
    session.add_curator_tag(0, "needs-review")

    tagged = session.filter_events(curator_tags=["important"])
    print(f"   ✓ Curator tagging working:")
    print(f"     - Tags on event 0: {session.events[0].curator_tags}")
    print(f"     - Events with 'important': {len(tagged)}")
except Exception as e:
    print(f"   ✗ Curator tagging failed: {e}")
    sys.exit(1)

# Test 7: TranscriptLoader with JSONL
print("\n7. Testing TranscriptLoader...")
try:
    # Create temporary JSONL file
    with NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as tmp:
        tmp_path = Path(tmp.name)

        # Write sample transcript
        events_data = [
            {
                "type": "message",
                "role": "assistant",
                "content": "Starting task...",
                "timestamp": datetime.now().isoformat(),
                "metadata": {
                    "session_id": "sess-001",
                    "task_id": "task-001",
                    "loop_type": "task",
                },
            },
            {
                "name": "Bash",
                "input": {"command": "pwd"},
                "timestamp": datetime.now().isoformat(),
                "metadata": {
                    "session_id": "sess-001",
                    "task_id": "task-001",
                    "loop_type": "task",
                },
            },
        ]

        for event_data in events_data:
            tmp.write(json.dumps(event_data) + "\n")

    # Load transcript
    sessions = TranscriptLoader.load_transcript(tmp_path)
    tmp_path.unlink()  # Clean up

    print(f"   ✓ TranscriptLoader working:")
    print(f"     - Sessions loaded: {len(sessions)}")
    print(f"     - Events in session: {len(sessions[0].events)}")
    print(f"     - Session ID: {sessions[0].session_id}")
except Exception as e:
    print(f"   ✗ TranscriptLoader failed: {e}")
    import traceback
    traceback.print_exc()
    if tmp_path.exists():
        tmp_path.unlink()
    sys.exit(1)

# Test 8: Duration calculation
print("\n8. Testing session duration...")
try:
    duration = session.get_duration_seconds()
    print(f"   ✓ Duration calculation working:")
    print(f"     - Duration: {duration:.3f} seconds")
except Exception as e:
    print(f"   ✗ Duration calculation failed: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("✅ All model tests PASSED")
print("=" * 60)
print("\nThe ACE Tools models are working correctly.")
print("Ready for integration with the Session Inspector UI.")
