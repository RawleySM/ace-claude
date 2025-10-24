# TaskExecutor Module

Async wrapper for ACE task execution with UI integration and progress tracking.

## Quick Start

```python
from pathlib import Path
from ace_tools.task_executor import execute_task

# Simple execution
result = await execute_task(
    task_prompt="Create a new API endpoint",
    playbook_path=Path("playbook.json"),
    progress_callback=print,
)

if result.success:
    print(f"✓ Task completed! {result.delta_count} updates")
else:
    print(f"✗ Failed: {result.error_message}")
```

## Features

- ✓ **Async execution** - Non-blocking task processing
- ✓ **Progress callbacks** - Real-time UI updates
- ✓ **Transcript capture** - Session replay and analysis
- ✓ **Logging interception** - Forward logs to UI
- ✓ **Error handling** - Comprehensive error reporting
- ✓ **Playbook management** - Automatic load/save
- ✓ **Thread-safe** - Concurrent execution support

## Installation

```bash
pip install claude-agent-sdk python-dotenv anyio
```

## Basic Usage

### Using the Class

```python
from ace_tools.task_executor import TaskExecutor

executor = TaskExecutor()

result = await executor.execute_task(
    task_prompt="Optimize database queries",
    playbook_path=Path("playbook.json"),
    transcript_path=Path("transcript.jsonl"),  # Optional
    progress_callback=lambda msg: print(f"[Progress] {msg}"),  # Optional
)

print(f"Success: {result.success}")
print(f"Playbook version: {result.playbook_version}")
print(f"Delta updates: {result.delta_count}")
```

### Using the Convenience Function

```python
from ace_tools.task_executor import execute_task

result = await execute_task(
    "Create authentication system",
    Path("playbook.json"),
    progress_callback=print,
)
```

## Result Object

```python
@dataclass
class TaskExecutionResult:
    trajectory: TaskTrajectory | None  # Full message history
    playbook_version: int              # Version after updates
    delta_count: int                   # Number of updates applied
    success: bool                      # Execution status
    error_message: str | None          # Error details if failed
```

## Progress Callbacks

Receive real-time status updates:

```python
def on_progress(message: str):
    # Messages include:
    # - "Loading playbook..."
    # - "Starting task execution: ..."
    # - "Task completed with 42 messages"
    # - "Saving playbook updates..."
    # - "ERROR: ..."
    print(message)

result = await executor.execute_task(
    task_prompt="...",
    playbook_path=Path("playbook.json"),
    progress_callback=on_progress,
)
```

## Error Handling

```python
# Check result status
result = await executor.execute_task(...)

if not result.success:
    print(f"Error: {result.error_message}")
    # Handle error appropriately

# Or catch validation errors
try:
    result = await executor.execute_task(
        task_prompt="",  # Empty prompt
        playbook_path=Path("playbook.json"),
    )
except ValueError as e:
    print(f"Validation error: {e}")
```

## UI Integration Examples

### FastAPI

```python
@app.post("/tasks/execute")
async def execute_endpoint(task_prompt: str):
    result = await execute_task(
        task_prompt=task_prompt,
        playbook_path=Path("playbook.json"),
        progress_callback=lambda msg: print(f"[API] {msg}"),
    )
    return {"success": result.success, "deltas": result.delta_count}
```

### Streamlit

```python
if st.button("Execute"):
    progress = st.empty()

    result = await execute_task(
        task_prompt=st.text_area("Task"),
        playbook_path=Path("playbook.json"),
        progress_callback=lambda msg: progress.text(msg),
    )

    if result.success:
        st.success(f"{result.delta_count} updates applied")
```

### Gradio

```python
def execute_ui(task_prompt: str):
    result = asyncio.run(execute_task(
        task_prompt=task_prompt,
        playbook_path=Path("playbook.json"),
    ))
    return f"Success: {result.success}"

gr.Interface(fn=execute_ui, inputs="text", outputs="text").launch()
```

## Advanced Features

### Transcript Capture

Enable session recording for replay in the skills inspector:

```python
result = await executor.execute_task(
    task_prompt="...",
    playbook_path=Path("playbook.json"),
    transcript_path=Path("docs/transcripts/session.jsonl"),
)

# Transcript file contains:
# - SessionHeader
# - ToolStart/ToolFinish events
# - SubagentStop events
```

### Custom Logging

Intercept and forward logs from ace-task modules:

```python
logs = []

def capture_logs(message: str):
    logs.append(message)
    print(message)

result = await executor.execute_task(
    task_prompt="...",
    playbook_path=Path("playbook.json"),
    progress_callback=capture_logs,
)

print(f"Captured {len(logs)} log messages")
```

### Analyzing Results

```python
if result.success:
    trajectory = result.trajectory

    # Get task and skill messages
    task_msgs = trajectory.get_task_messages()
    skill_sessions = trajectory.get_skill_sessions()

    print(f"Task messages: {len(task_msgs)}")
    print(f"Skill sessions: {len(skill_sessions)}")

    # Check delta updates
    for delta in trajectory.delta_updates:
        if delta.get("type") == "skill":
            print(f"New skill: {delta['name']}")
```

## Configuration

### Custom Paths

```python
executor = TaskExecutor(
    ace_task_path=Path("/custom/ace-task"),
    ace_skill_path=Path("/custom/ace-skill"),
)
```

### Auto-detection

By default, paths are auto-detected relative to the module:
```
ace-claude/
├── ace-task/
├── ace-skill/
└── ace_tools/
    └── task_executor.py  # Detects ../ace-task and ../ace-skill
```

## API Reference

### Classes

- **`TaskExecutor`** - Main execution class
  - `__init__(ace_task_path, ace_skill_path)` - Initialize
  - `async execute_task(...)` - Execute task with callbacks

- **`TaskExecutionResult`** - Result dataclass
  - `trajectory` - Full message history
  - `playbook_version` - Updated version number
  - `delta_count` - Number of applied updates
  - `success` - Execution status
  - `error_message` - Error details

- **`LoggingInterceptor`** - Thread-safe log handler
  - `__init__(callback)` - Initialize with callback
  - `emit(record)` - Forward log records

### Functions

- **`async execute_task(...)`** - Convenience function
  - Parameters: Same as `TaskExecutor.execute_task()` plus custom paths
  - Returns: `TaskExecutionResult`

## Requirements

- Python 3.10+
- claude-agent-sdk
- python-dotenv
- anyio
- ace-task/ace-task.py
- ace-skill/ace_skill_utils.py

## Documentation

- **Full guide**: `/docs/task_executor_guide.md`
- **Examples**: `/ace_tools/example_task_executor.py`
- **Tests**: `/test_task_executor.py`

## Troubleshooting

| Error | Solution |
|-------|----------|
| `ImportError: No module named 'claude_agent_sdk'` | Install: `pip install claude-agent-sdk` |
| `FileNotFoundError: ace-task directory not found` | Check paths or provide custom `ace_task_path` |
| `ValueError: task_prompt cannot be empty` | Provide non-empty task description |
| `FileNotFoundError: Playbook directory does not exist` | Create parent directory: `path.parent.mkdir(parents=True)` |

## License

Part of the ACE Claude system. See project LICENSE file.
