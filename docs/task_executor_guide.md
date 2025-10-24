# TaskExecutor Guide

## Overview

The `task_executor.py` module provides a high-level async wrapper for executing ACE tasks from `ace-task/ace-task.py` with UI integration capabilities. It enables:

- **Async task execution** with proper error handling
- **Progress callbacks** for real-time UI updates
- **Transcript capture** for session replay and analysis
- **Logging interception** to forward logs to UI components
- **Automatic playbook management** (load and save)
- **Thread-safe operations** for concurrent execution

## Architecture

### Core Components

```
TaskExecutor
├── __init__() - Initialize with ace-task/ace-skill paths
├── execute_task() - Main execution method with callbacks
├── _setup_python_path() - Configure imports for ace-task modules
├── _import_ace_task_modules() - Dynamic import of run_task, DeltaPlaybook
├── _load_playbook() - Async playbook loading
├── _save_playbook() - Async playbook saving
├── _setup_transcript_capture() - Enable JSONL recording
├── _cleanup_transcript_capture() - Close transcript writer
├── _setup_logging_interceptor() - Install log forwarding
└── _cleanup_logging_interceptor() - Remove log handler

LoggingInterceptor
└── emit() - Thread-safe log forwarding to callback

TaskExecutionResult
├── trajectory - TaskTrajectory from ace-task.py
├── playbook_version - Version after updates
├── delta_count - Number of delta updates applied
├── success - Execution status
└── error_message - Error details if failed
```

## Installation

### Requirements

```bash
# Required dependencies
pip install claude-agent-sdk
pip install python-dotenv
pip install anyio

# Or use the ace_tools environment
cd ace_tools
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Project Structure

```
ace-claude/
├── ace-task/
│   └── ace-task.py          # Task execution engine
├── ace-skill/
│   └── ace_skill_utils.py   # Skill generation utilities
└── ace_tools/
    ├── task_executor.py     # This module
    ├── transcript_capture.py # Transcript recording
    └── example_task_executor.py # Usage examples
```

## Usage

### Basic Usage with Class

```python
from pathlib import Path
from ace_tools.task_executor import TaskExecutor

async def main():
    # Initialize executor
    executor = TaskExecutor()

    # Define progress callback
    def on_progress(message: str):
        print(f"[Progress] {message}")

    # Execute task
    result = await executor.execute_task(
        task_prompt="Create a new API endpoint for user management",
        playbook_path=Path("playbook.json"),
        transcript_path=Path("docs/transcripts/session.jsonl"),
        progress_callback=on_progress,
    )

    # Check results
    if result.success:
        print(f"Task completed successfully!")
        print(f"Playbook version: {result.playbook_version}")
        print(f"Delta updates: {result.delta_count}")
        print(f"Messages: {len(result.trajectory.messages)}")
    else:
        print(f"Task failed: {result.error_message}")

# Run
import asyncio
asyncio.run(main())
```

### Convenience Function

For simple use cases without managing an executor instance:

```python
from pathlib import Path
from ace_tools.task_executor import execute_task

async def main():
    result = await execute_task(
        task_prompt="Optimize database queries",
        playbook_path=Path("playbook.json"),
        progress_callback=lambda msg: print(msg),
    )

    return result.success

import asyncio
success = asyncio.run(main())
```

### Custom Paths

If your ACE directories are in non-standard locations:

```python
from pathlib import Path
from ace_tools.task_executor import TaskExecutor

executor = TaskExecutor(
    ace_task_path=Path("/custom/path/to/ace-task"),
    ace_skill_path=Path("/custom/path/to/ace-skill"),
)
```

### Progress Callbacks

Progress callbacks receive formatted status messages:

```python
def progress_callback(message: str):
    """
    Receives messages like:
    - "Loading playbook..."
    - "Loaded playbook version 2 with 5 items"
    - "Starting task execution: Create a new API endpoint..."
    - "Task completed with 42 messages"
    - "Saving playbook updates..."
    - "Playbook saved (version 3, 2 deltas)"
    - "ERROR: Task execution failed: ..."
    """
    # Send to UI, log file, or console
    print(f"[{datetime.now()}] {message}")

result = await executor.execute_task(
    task_prompt="...",
    playbook_path=Path("playbook.json"),
    progress_callback=progress_callback,
)
```

### Transcript Capture

Enable transcript capture for session replay in the skills inspector:

```python
from pathlib import Path

result = await executor.execute_task(
    task_prompt="Add authentication middleware",
    playbook_path=Path("playbook.json"),
    transcript_path=Path("docs/transcripts/auth_session.jsonl"),
    progress_callback=print,
)

# Transcript file will contain:
# - SessionHeader with metadata
# - ToolStart events
# - ToolFinish events
# - SubagentStop events
```

### Error Handling

The executor provides comprehensive error handling:

```python
from pathlib import Path
from ace_tools.task_executor import TaskExecutor

executor = TaskExecutor()

# Invalid playbook path
result = await executor.execute_task(
    task_prompt="Some task",
    playbook_path=Path("/nonexistent/playbook.json"),
)

if not result.success:
    print(f"Error: {result.error_message}")
    # Example: "Task execution failed: FileNotFoundError: ..."

# Empty task prompt
try:
    result = await executor.execute_task(
        task_prompt="",
        playbook_path=Path("playbook.json"),
    )
except ValueError as e:
    print(f"Validation error: {e}")
    # Example: "task_prompt cannot be empty"

# Import errors
try:
    executor = TaskExecutor(
        ace_task_path=Path("/wrong/path"),
    )
except FileNotFoundError as e:
    print(f"Path error: {e}")
    # Example: "ace-task directory not found at /wrong/path"
except ImportError as e:
    print(f"Import error: {e}")
    # Example: "Failed to import from ace-task.py: ..."
```

### Logging Interception

The executor automatically intercepts logs from ace-task and ace-skill modules:

```python
import logging

# Configure logging level
logging.getLogger("ace_task").setLevel(logging.DEBUG)
logging.getLogger("ace_skill_utils").setLevel(logging.INFO)

# Logs will be forwarded to progress_callback
logs = []

def capture_logs(message: str):
    logs.append(message)
    print(message)

result = await executor.execute_task(
    task_prompt="Generate a new skill",
    playbook_path=Path("playbook.json"),
    progress_callback=capture_logs,
)

# logs now contains all intercepted log messages
print(f"Captured {len(logs)} log messages")
```

## Integration Examples

### FastAPI Integration

```python
from fastapi import FastAPI, BackgroundTasks
from pathlib import Path
from ace_tools.task_executor import TaskExecutor

app = FastAPI()
executor = TaskExecutor()

@app.post("/tasks/execute")
async def execute_task_endpoint(
    task_prompt: str,
    playbook_id: str,
    background_tasks: BackgroundTasks,
):
    """Execute a task in the background."""

    async def run_task():
        result = await executor.execute_task(
            task_prompt=task_prompt,
            playbook_path=Path(f"playbooks/{playbook_id}.json"),
            transcript_path=Path(f"transcripts/{playbook_id}.jsonl"),
            progress_callback=lambda msg: print(f"[{playbook_id}] {msg}"),
        )

        # Store result in database
        # ...

    background_tasks.add_task(run_task)

    return {"status": "started", "playbook_id": playbook_id}
```

### Streamlit Integration

```python
import streamlit as st
from pathlib import Path
from ace_tools.task_executor import execute_task

st.title("ACE Task Executor")

task_prompt = st.text_area("Task Prompt")
playbook_path = st.text_input("Playbook Path", "playbook.json")

if st.button("Execute Task"):
    progress_placeholder = st.empty()

    def update_progress(message: str):
        progress_placeholder.text(message)

    with st.spinner("Executing task..."):
        result = asyncio.run(execute_task(
            task_prompt=task_prompt,
            playbook_path=Path(playbook_path),
            progress_callback=update_progress,
        ))

    if result.success:
        st.success(f"Task completed! {result.delta_count} updates applied")
        st.json({
            "playbook_version": result.playbook_version,
            "delta_count": result.delta_count,
            "message_count": len(result.trajectory.messages),
        })
    else:
        st.error(f"Task failed: {result.error_message}")
```

### Gradio Integration

```python
import gradio as gr
from pathlib import Path
from ace_tools.task_executor import execute_task
import asyncio

async def run_task(task_prompt: str, playbook_path: str):
    """Execute task and yield progress updates."""

    messages = []

    def capture_progress(msg: str):
        messages.append(msg)

    result = await execute_task(
        task_prompt=task_prompt,
        playbook_path=Path(playbook_path),
        progress_callback=capture_progress,
    )

    # Return formatted result
    if result.success:
        return (
            "✓ Success",
            f"Version: {result.playbook_version}\n"
            f"Deltas: {result.delta_count}\n"
            f"Messages: {len(result.trajectory.messages)}",
            "\n".join(messages),
        )
    else:
        return (
            "✗ Failed",
            result.error_message,
            "\n".join(messages),
        )

def gradio_wrapper(task_prompt: str, playbook_path: str):
    return asyncio.run(run_task(task_prompt, playbook_path))

interface = gr.Interface(
    fn=gradio_wrapper,
    inputs=[
        gr.Textbox(label="Task Prompt", lines=3),
        gr.Textbox(label="Playbook Path", value="playbook.json"),
    ],
    outputs=[
        gr.Textbox(label="Status"),
        gr.Textbox(label="Results", lines=5),
        gr.Textbox(label="Progress Log", lines=10),
    ],
    title="ACE Task Executor",
)

interface.launch()
```

## Advanced Usage

### Custom Logging Handler

For more control over logging:

```python
from ace_tools.task_executor import LoggingInterceptor
import logging

class DatabaseLogHandler(LoggingInterceptor):
    """Custom handler that stores logs in database."""

    def __init__(self, session_id: str, db_connection):
        self.session_id = session_id
        self.db = db_connection
        super().__init__(self._store_log)

    def _store_log(self, message: str):
        self.db.execute(
            "INSERT INTO task_logs (session_id, message) VALUES (?, ?)",
            (self.session_id, message)
        )

# Use custom handler
handler = DatabaseLogHandler("session-123", db_connection)
logging.getLogger("ace_task").addHandler(handler)

result = await executor.execute_task(...)

logging.getLogger("ace_task").removeHandler(handler)
```

### Analyzing Trajectory Results

```python
result = await executor.execute_task(
    task_prompt="Generate authentication skill",
    playbook_path=Path("playbook.json"),
)

if result.success:
    trajectory = result.trajectory

    # Get task-level messages only
    task_messages = trajectory.get_task_messages()
    print(f"Task messages: {len(task_messages)}")

    # Get skill loop sessions
    skill_sessions = trajectory.get_skill_sessions()
    print(f"Skill sessions: {len(skill_sessions)}")

    # Analyze delta updates
    for delta in trajectory.delta_updates:
        if delta.get("type") == "skill":
            print(f"New skill: {delta.get('name')}")
        elif delta.get("type") == "constraint":
            print(f"New constraint: {delta.get('description')}")

    # Export trajectory
    import json
    trajectory_data = {
        "task_id": trajectory.task_id,
        "created_at": trajectory.created_at,
        "message_count": len(trajectory.messages),
        "delta_count": len(trajectory.delta_updates),
    }

    with open("trajectory.json", "w") as f:
        json.dump(trajectory_data, f, indent=2)
```

### Batch Processing

```python
from pathlib import Path
from ace_tools.task_executor import TaskExecutor
import asyncio

async def batch_execute_tasks(tasks: list[tuple[str, Path]]):
    """Execute multiple tasks in sequence."""

    executor = TaskExecutor()
    results = []

    for task_prompt, playbook_path in tasks:
        print(f"\n=== Executing: {task_prompt} ===")

        result = await executor.execute_task(
            task_prompt=task_prompt,
            playbook_path=playbook_path,
            progress_callback=lambda msg: print(f"  {msg}"),
        )

        results.append({
            "prompt": task_prompt,
            "success": result.success,
            "delta_count": result.delta_count,
            "error": result.error_message,
        })

    return results

# Execute batch
tasks = [
    ("Create user authentication", Path("auth_playbook.json")),
    ("Add rate limiting", Path("api_playbook.json")),
    ("Implement caching", Path("cache_playbook.json")),
]

results = asyncio.run(batch_execute_tasks(tasks))

# Summary
successful = sum(1 for r in results if r["success"])
print(f"\nCompleted: {successful}/{len(results)} tasks successful")
```

## API Reference

### `TaskExecutor`

#### `__init__(ace_task_path: Path | None = None, ace_skill_path: Path | None = None)`

Initialize the task executor.

**Parameters:**
- `ace_task_path`: Path to ace-task directory (auto-detected if None)
- `ace_skill_path`: Path to ace-skill directory (auto-detected if None)

**Raises:**
- `FileNotFoundError`: If directories don't exist
- `ImportError`: If ace-task.py cannot be imported

#### `async execute_task(task_prompt: str, playbook_path: Path, transcript_path: Path | None = None, progress_callback: Callable[[str], None] | None = None) -> TaskExecutionResult`

Execute a task with optional callbacks and transcript capture.

**Parameters:**
- `task_prompt`: User's task description (non-empty string)
- `playbook_path`: Path to playbook JSON file
- `transcript_path`: Optional path for transcript JSONL capture
- `progress_callback`: Optional callback for progress updates

**Returns:**
- `TaskExecutionResult` with execution status and data

**Raises:**
- `ValueError`: If task_prompt is empty
- `FileNotFoundError`: If playbook directory doesn't exist

### `TaskExecutionResult`

Dataclass representing execution results.

**Attributes:**
- `trajectory`: TaskTrajectory from ace-task.py (None if failed)
- `playbook_version`: Playbook version after updates
- `delta_count`: Number of delta updates applied
- `success`: Whether execution completed successfully
- `error_message`: Error description if execution failed (None if successful)

### `LoggingInterceptor`

Thread-safe logging handler that forwards to a callback.

**Parameters:**
- `callback`: Function to call with formatted log messages

### `async execute_task(...) -> TaskExecutionResult`

Convenience function for one-off task execution.

**Parameters:** Same as `TaskExecutor.execute_task()` plus:
- `ace_task_path`: Optional custom path to ace-task directory
- `ace_skill_path`: Optional custom path to ace-skill directory

**Returns:** `TaskExecutionResult`

## Troubleshooting

### Import Errors

```
ImportError: Failed to import from ace-task.py
```

**Solution:** Ensure ace-task and ace-skill directories exist and contain the required files:
- `ace-task/ace-task.py`
- `ace-skill/ace_skill_utils.py`

### Module Not Found

```
ModuleNotFoundError: No module named 'claude_agent_sdk'
```

**Solution:** Install required dependencies:
```bash
pip install claude-agent-sdk python-dotenv anyio
```

### Playbook Errors

```
FileNotFoundError: Playbook directory does not exist
```

**Solution:** Create the parent directory:
```python
playbook_path = Path("data/playbooks/my_playbook.json")
playbook_path.parent.mkdir(parents=True, exist_ok=True)
```

### Empty Task Prompt

```
ValueError: task_prompt cannot be empty
```

**Solution:** Provide a non-empty task description:
```python
result = await executor.execute_task(
    task_prompt="Create a new authentication system",  # Not empty
    playbook_path=Path("playbook.json"),
)
```

## Best Practices

1. **Reuse executor instances** for multiple tasks to avoid repeated imports
2. **Use transcript capture** for debugging and session replay
3. **Implement progress callbacks** for better UX
4. **Handle errors gracefully** by checking `result.success`
5. **Use async/await consistently** throughout your application
6. **Clean up resources** in finally blocks
7. **Monitor playbook versions** to track changes over time
8. **Batch similar tasks** to improve efficiency
9. **Log to files** in production for debugging
10. **Test with small tasks** before running complex operations

## See Also

- `ace-task/ace-task.py` - Core task execution engine
- `ace_tools/transcript_capture.py` - Transcript recording system
- `ace_tools/example_task_executor.py` - Complete usage examples
- `ace_tools/inspector_ui.py` - Skills inspector UI
