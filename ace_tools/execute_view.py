"""ExecuteView widget for the ACE Claude Textual UI.

This module provides an interactive widget for executing ACE tasks through
the Textual terminal UI. Users can input task descriptions, specify playbooks,
and monitor execution progress with live output streaming.

The ExecuteView follows the UI patterns established in inspector_ui.py and
provides a clean interface for task execution with real-time feedback.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from textual import on
from textual.containers import VerticalScroll
from textual.reactive import reactive
from textual.widgets import Button, Input, Label, RichLog, Static, TextArea


class ExecuteView(VerticalScroll):
    """Widget for executing ACE tasks with live output monitoring.

    Features:
    - Multiline task input with TextArea
    - Playbook path configuration
    - Execute button with state management
    - Status indicator (idle, running, completed, error)
    - RichLog for streaming execution output
    - Trajectory path tracking

    Attributes:
        is_executing: Reactive boolean tracking execution state
        status_text: Reactive string for status display
        trajectory_path: Path to the generated trajectory file
    """

    is_executing = reactive(False)
    status_text = reactive("idle")

    def __init__(
        self,
        playbook_path: str = "playbook.json",
        trajectory_dir: str = "trajectories",
    ) -> None:
        """Initialize the ExecuteView widget.

        Args:
            playbook_path: Default path to the playbook JSON file
            trajectory_dir: Directory where trajectory files will be saved
        """
        super().__init__()
        self.border_title = "Execute Task"
        self.default_playbook = playbook_path
        self.trajectory_dir = Path(trajectory_dir)
        self.trajectory_path: Optional[Path] = None

    def compose(self):
        """Build the execute view layout."""
        yield Label("Task Execution", classes="pane-header")

        # Task input section
        yield Label("Task Description:", classes="section-header")
        yield TextArea(
            text="",
            language="markdown",
            theme="monokai",
            id="task-input",
            classes="task-input",
        )

        # Playbook path configuration
        yield Label("Playbook Path:", classes="section-header")
        yield Input(
            value=self.default_playbook,
            placeholder="Path to playbook.json",
            id="playbook-input",
            classes="playbook-input",
        )

        # Execute button
        yield Button(
            "Execute Task",
            id="execute-button",
            variant="primary",
            classes="execute-button",
        )

        # Status display
        yield Label("Status:", classes="section-header")
        yield Static(
            self._format_status(),
            id="status-display",
            classes=self._get_status_class(),
        )

        # Execution output log
        yield Label("Execution Output:", classes="section-header")
        yield RichLog(
            id="execution-log",
            highlight=True,
            markup=True,
            classes="execution-log",
        )

    def _format_status(self) -> str:
        """Format the status text for display.

        Returns:
            Formatted status string with appropriate styling
        """
        status_map = {
            "idle": "Idle - Ready to execute",
            "running": "Running - Task in progress...",
            "completed": "Completed - Task finished successfully",
            "error": "Error - Task execution failed",
        }
        return status_map.get(self.status_text, self.status_text)

    def _get_status_class(self) -> str:
        """Get CSS class for status display based on current state.

        Returns:
            CSS class name for status styling
        """
        class_map = {
            "idle": "status-idle",
            "running": "status-running",
            "completed": "status-success",
            "error": "status-error",
        }
        return class_map.get(self.status_text, "status-idle")

    def watch_status_text(self, new_status: str) -> None:
        """React to status text changes and update display.

        Args:
            new_status: New status text value
        """
        try:
            status_display = self.query_one("#status-display", Static)
            status_display.update(self._format_status())

            # Update CSS class for color coding
            status_display.remove_class("status-idle")
            status_display.remove_class("status-running")
            status_display.remove_class("status-success")
            status_display.remove_class("status-error")
            status_display.add_class(self._get_status_class())
        except Exception:
            # Widget may not be mounted yet
            pass

    def watch_is_executing(self, is_executing: bool) -> None:
        """React to execution state changes and update button state.

        Args:
            is_executing: New execution state
        """
        try:
            execute_button = self.query_one("#execute-button", Button)
            execute_button.disabled = is_executing

            if is_executing:
                execute_button.label = "Executing..."
                self.status_text = "running"
            else:
                execute_button.label = "Execute Task"
                if self.status_text == "running":
                    self.status_text = "idle"
        except Exception:
            # Widget may not be mounted yet
            pass

    @on(Button.Pressed, "#execute-button")
    def handle_execute(self) -> None:
        """Handle execute button press event.

        Validates input and initiates task execution. This method should be
        overridden or extended by the parent application to implement actual
        execution logic.
        """
        if self.is_executing:
            return

        # Get input values
        try:
            task_input = self.query_one("#task-input", TextArea)
            playbook_input = self.query_one("#playbook-input", Input)
            execution_log = self.query_one("#execution-log", RichLog)

            task_text = task_input.text.strip()
            playbook_path = playbook_input.value.strip()

            # Validate inputs
            if not task_text:
                execution_log.write("[red]Error: Task description cannot be empty[/red]")
                self.status_text = "error"
                return

            if not playbook_path:
                execution_log.write("[red]Error: Playbook path cannot be empty[/red]")
                self.status_text = "error"
                return

            # Check if playbook exists
            if not Path(playbook_path).exists():
                execution_log.write(
                    f"[yellow]Warning: Playbook file not found: {playbook_path}[/yellow]"
                )
                execution_log.write("[yellow]Execution will proceed anyway...[/yellow]")

            # Clear previous output
            execution_log.clear()

            # Update state
            self.is_executing = True
            execution_log.write("[cyan]Preparing to execute task...[/cyan]")
            execution_log.write(f"[cyan]Task: {task_text[:100]}...[/cyan]")
            execution_log.write(f"[cyan]Playbook: {playbook_path}[/cyan]")

            # Post custom event for parent app to handle
            self.post_message(
                self.ExecuteRequested(
                    task=task_text,
                    playbook_path=playbook_path,
                )
            )

        except Exception as e:
            self.status_text = "error"
            try:
                execution_log = self.query_one("#execution-log", RichLog)
                execution_log.write(f"[red]Error during execution: {e}[/red]")
            except Exception:
                pass

    def log_output(self, message: str, style: str = "default") -> None:
        """Write a message to the execution log.

        Args:
            message: Message text to log
            style: Style hint (default, success, error, warning, info)
        """
        try:
            execution_log = self.query_one("#execution-log", RichLog)

            style_map = {
                "success": "green",
                "error": "red",
                "warning": "yellow",
                "info": "cyan",
                "default": "white",
            }

            color = style_map.get(style, "white")
            execution_log.write(f"[{color}]{message}[/{color}]")
        except Exception:
            pass

    def clear_output(self) -> None:
        """Clear the execution log."""
        try:
            execution_log = self.query_one("#execution-log", RichLog)
            execution_log.clear()
        except Exception:
            pass

    def set_executing(self, executing: bool) -> None:
        """Programmatically set execution state.

        Args:
            executing: Whether task is currently executing
        """
        self.is_executing = executing

    def set_status(self, status: str) -> None:
        """Programmatically set status text.

        Args:
            status: Status string (idle, running, completed, error)
        """
        if status in ["idle", "running", "completed", "error"]:
            self.status_text = status

    def set_trajectory_path(self, path: Path | str) -> None:
        """Set the path to the generated trajectory file.

        Args:
            path: Path to trajectory file
        """
        self.trajectory_path = Path(path) if isinstance(path, str) else path
        self.log_output(f"Trajectory saved to: {self.trajectory_path}", style="info")

    def get_task_text(self) -> str:
        """Get current task input text.

        Returns:
            Task description text
        """
        try:
            task_input = self.query_one("#task-input", TextArea)
            return task_input.text.strip()
        except Exception:
            return ""

    def get_playbook_path(self) -> str:
        """Get current playbook path.

        Returns:
            Playbook path string
        """
        try:
            playbook_input = self.query_one("#playbook-input", Input)
            return playbook_input.value.strip()
        except Exception:
            return self.default_playbook

    class ExecuteRequested:
        """Message posted when task execution is requested.

        Attributes:
            task: Task description text
            playbook_path: Path to playbook file
        """

        def __init__(self, task: str, playbook_path: str) -> None:
            self.task = task
            self.playbook_path = playbook_path


# CSS styling for ExecuteView
EXECUTE_VIEW_CSS = """
ExecuteView {
    border: solid $primary;
    padding: 1;
}

.task-input {
    height: 10;
    border: solid $accent;
    margin-bottom: 1;
}

.playbook-input {
    margin-bottom: 1;
}

.execute-button {
    width: 100%;
    margin-bottom: 1;
}

.execution-log {
    height: 20;
    border: solid $primary;
    background: $surface;
    padding: 1;
}

.status-idle {
    color: $text-muted;
    background: $surface;
    padding: 1;
    margin-bottom: 1;
}

.status-running {
    color: $accent;
    text-style: bold;
    background: $surface;
    padding: 1;
    margin-bottom: 1;
}

.status-success {
    color: $success;
    text-style: bold;
    background: $surface;
    padding: 1;
    margin-bottom: 1;
}

.status-error {
    color: $error;
    text-style: bold;
    background: $surface;
    padding: 1;
    margin-bottom: 1;
}
"""


__all__ = ["ExecuteView", "EXECUTE_VIEW_CSS"]
