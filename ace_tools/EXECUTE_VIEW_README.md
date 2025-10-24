# ExecuteView Widget

## Overview

The `ExecuteView` widget provides an interactive Textual UI component for executing ACE tasks with real-time feedback and monitoring.

## Features

- **Multiline Task Input**: Uses `TextArea` for comfortable task description entry
- **Playbook Configuration**: Input field for specifying playbook path
- **State Management**: Reactive properties for execution state and status
- **Live Output**: `RichLog` widget for streaming execution output with color coding
- **Status Indicators**: Clear visual feedback (idle, running, completed, error)
- **Trajectory Tracking**: Stores path to generated trajectory files

## Usage

### Basic Integration

```python
from textual.app import App, ComposeResult
from execute_view import ExecuteView, EXECUTE_VIEW_CSS

class MyApp(App):
    CSS = EXECUTE_VIEW_CSS

    def compose(self) -> ComposeResult:
        yield ExecuteView(
            playbook_path="playbook.json",
            trajectory_dir="trajectories"
        )

    def on_execute_view_execute_requested(self, event: ExecuteView.ExecuteRequested) -> None:
        """Handle task execution."""
        execute_view = self.query_one(ExecuteView)

        # Your execution logic here
        task = event.task
        playbook = event.playbook_path

        # Log output
        execute_view.log_output("Starting execution...", style="info")

        # Update status when done
        execute_view.set_status("completed")
        execute_view.set_executing(False)
```

### Running the Test Application

```bash
cd ace_tools
source .venv/bin/activate
python test_execute_view.py
```

## API Reference

### Constructor

```python
ExecuteView(
    playbook_path: str = "playbook.json",
    trajectory_dir: str = "trajectories"
)
```

### Reactive Properties

- `is_executing: bool` - Whether task is currently executing
- `status_text: str` - Current status (idle, running, completed, error)

### Methods

#### `log_output(message: str, style: str = "default") -> None`
Write a message to the execution log with optional styling.

**Styles**: `default`, `success`, `error`, `warning`, `info`

#### `clear_output() -> None`
Clear all content from the execution log.

#### `set_executing(executing: bool) -> None`
Programmatically set execution state and update UI.

#### `set_status(status: str) -> None`
Set status text (idle, running, completed, error).

#### `set_trajectory_path(path: Path | str) -> None`
Set the path to the generated trajectory file.

#### `get_task_text() -> str`
Get current task input text.

#### `get_playbook_path() -> str`
Get current playbook path.

### Events

#### `ExecuteView.ExecuteRequested`
Posted when user clicks the execute button.

**Attributes**:
- `task: str` - Task description text
- `playbook_path: str` - Path to playbook file

## Styling

The widget includes comprehensive CSS styling that follows the patterns from `inspector_ui.py`:

```python
from execute_view import EXECUTE_VIEW_CSS

class MyApp(App):
    CSS = EXECUTE_VIEW_CSS
```

### Custom Styling

You can override or extend the default styles:

```python
class MyApp(App):
    CSS = f"""
    {EXECUTE_VIEW_CSS}

    .task-input {{
        height: 15;  /* Increase input height */
    }}

    .execution-log {{
        height: 30;  /* Increase log height */
    }}
    """
```

## Integration with ACE System

To integrate with the actual ACE task execution system:

```python
import asyncio
from pathlib import Path
from execute_view import ExecuteView

class ACEApp(App):
    def on_execute_view_execute_requested(self, event: ExecuteView.ExecuteRequested) -> None:
        """Execute ACE task."""
        execute_view = self.query_one(ExecuteView)

        # Run async execution
        asyncio.create_task(self._execute_task(
            event.task,
            event.playbook_path
        ))

    async def _execute_task(self, task: str, playbook_path: str) -> None:
        """Async task execution handler."""
        execute_view = self.query_one(ExecuteView)

        try:
            # Import ACE components
            from ace_task import ACETaskLoop

            # Initialize task loop
            execute_view.log_output("Initializing ACE task loop...", style="info")

            # Execute task (pseudo-code)
            # result = await ace_task_loop.execute(task, playbook_path)

            # Log progress
            execute_view.log_output("Task completed successfully!", style="success")
            execute_view.set_status("completed")

            # Save trajectory
            trajectory_path = Path("trajectories") / "latest.jsonl"
            execute_view.set_trajectory_path(trajectory_path)

        except Exception as e:
            execute_view.log_output(f"Error: {e}", style="error")
            execute_view.set_status("error")
        finally:
            execute_view.set_executing(False)
```

## Widget Layout

```
┌─────────────────────────────────────┐
│ Task Execution                      │
├─────────────────────────────────────┤
│ Task Description:                   │
│ ┌─────────────────────────────────┐ │
│ │ [TextArea - multiline input]    │ │
│ │                                 │ │
│ └─────────────────────────────────┘ │
│                                     │
│ Playbook Path:                      │
│ [playbook.json                   ]  │
│                                     │
│ [ Execute Task                   ]  │
│                                     │
│ Status:                             │
│ Idle - Ready to execute             │
│                                     │
│ Execution Output:                   │
│ ┌─────────────────────────────────┐ │
│ │ [RichLog - colored output]      │ │
│ │                                 │ │
│ └─────────────────────────────────┘ │
└─────────────────────────────────────┘
```

## Example: Status Flow

```
idle → running → completed
   ↘          ↘ error
```

1. **Idle**: Ready for new task (button enabled)
2. **Running**: Task executing (button disabled)
3. **Completed**: Task finished successfully (button re-enabled)
4. **Error**: Task failed (button re-enabled)

## Color Coding

- **Info** (cyan): System messages and progress updates
- **Success** (green): Successful operations and completion
- **Error** (red): Error messages and failures
- **Warning** (yellow): Warnings and non-critical issues
- **Default** (white): General output

## Testing

Run the included test application to see the widget in action:

```bash
python test_execute_view.py
```

**Test keybindings**:
- `q` - Quit application
- `c` - Clear log

## Dependencies

- `textual` - Modern TUI framework
- Standard library: `pathlib`, `typing`

## File Structure

```
ace_tools/
├── execute_view.py           # Main widget implementation
├── test_execute_view.py      # Test application
├── EXECUTE_VIEW_README.md    # This documentation
└── inspector_ui.py           # Reference for styling patterns
```
