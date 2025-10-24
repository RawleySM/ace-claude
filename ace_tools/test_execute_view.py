"""Simple test application for ExecuteView widget.

This module provides a minimal Textual application to demonstrate and test
the ExecuteView widget in isolation.

Usage:
    python test_execute_view.py
"""

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header

from execute_view import EXECUTE_VIEW_CSS, ExecuteView


class ExecuteViewTestApp(App[None]):
    """Test application for ExecuteView widget.

    This app demonstrates the ExecuteView widget with basic event handling
    and simulated execution flow.
    """

    CSS = EXECUTE_VIEW_CSS

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("c", "clear_log", "Clear Log"),
    ]

    def compose(self) -> ComposeResult:
        """Build the test application layout."""
        yield Header()
        yield ExecuteView(
            playbook_path="playbook.json",
            trajectory_dir="trajectories",
        )
        yield Footer()

    def on_execute_view_execute_requested(
        self, event: ExecuteView.ExecuteRequested
    ) -> None:
        """Handle execute request from ExecuteView.

        Args:
            event: ExecuteRequested message with task details
        """
        execute_view = self.query_one(ExecuteView)

        # Simulate execution
        execute_view.log_output("=" * 60, style="info")
        execute_view.log_output("Task execution started", style="info")
        execute_view.log_output(f"Task: {event.task}", style="default")
        execute_view.log_output(f"Playbook: {event.playbook_path}", style="default")
        execute_view.log_output("=" * 60, style="info")

        # Simulate some processing steps
        execute_view.log_output("Step 1: Loading playbook...", style="info")
        execute_view.log_output("Step 2: Initializing ACE system...", style="info")
        execute_view.log_output("Step 3: Executing task loop...", style="info")

        # Simulate completion
        execute_view.log_output("Task completed successfully!", style="success")
        execute_view.set_status("completed")
        execute_view.set_executing(False)
        execute_view.set_trajectory_path("trajectories/test_trajectory.jsonl")

    def action_clear_log(self) -> None:
        """Clear the execution log."""
        execute_view = self.query_one(ExecuteView)
        execute_view.clear_output()
        execute_view.set_status("idle")


def main() -> None:
    """Run the test application."""
    app = ExecuteViewTestApp()
    app.title = "ExecuteView Test"
    app.sub_title = "Testing ACE task execution widget"
    app.run()


if __name__ == "__main__":
    main()
