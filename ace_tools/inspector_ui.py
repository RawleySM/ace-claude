"""Textual TUI application for inspecting ACE skill session trajectories.

This module provides an interactive terminal-based UI for exploring Claude Agent SDK
skill loops, displaying structured events (AssistantMessage, ToolUseBlock, ToolResultBlock,
SubagentStop), and enabling curators to review and export skill deltas.

The inspector follows the specification in plan/UI_plan and provides:
- TimelineView: chronological stream of events with collapsible cards
- ContextView: playbook summary, deltas, and session metadata
- SkillDetailView: tool invocation details with annotation support
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.reactive import reactive
from textual.widgets import (
    Button,
    Collapsible,
    Footer,
    Header,
    Input,
    Label,
    Static,
    TabbedContent,
    TabPane,
    Tree,
)

from .models import EventRecord, SessionModel, SkillOutcome
from .execute_view import ExecuteView, EXECUTE_VIEW_CSS


class EventCard(Static):
    """Collapsible card widget for displaying a single event."""

    def __init__(self, event: EventRecord, event_index: int) -> None:
        super().__init__()
        self.event = event
        self.event_index = event_index
        # Apply CSS class for color coding
        self.add_class(self._get_css_class())

    def compose(self) -> ComposeResult:
        """Build the card layout with collapsible content."""
        # Determine status and color
        status_text = self._get_status_text()

        # Create card title
        title = f"[{self.event_index}] {self.event.event_type.upper()} - {status_text}"

        with Collapsible(title=title, collapsed=True):
            yield Label(f"Timestamp: {self.event.timestamp.isoformat()}")

            # Event-specific content
            if self.event.event_type == "tool_use":
                tool_name = self.event.sdk_block.get("name", "unknown")
                yield Label(f"Tool: {tool_name}", classes="tool-name")

                parameters = self.event.sdk_block.get("input", {})
                if parameters:
                    yield Label("Parameters:", classes="section-header")
                    params_json = json.dumps(parameters, indent=2)
                    yield Static(params_json, classes="json-content")

            elif self.event.event_type == "tool_result":
                content = self.event.sdk_block.get("content", "")
                yield Label("Result:", classes="section-header")
                result_text = str(content)[:500]  # Truncate long output
                if len(str(content)) > 500:
                    result_text += "\n... (truncated)"
                yield Static(result_text, classes="result-content")

                is_error = self.event.sdk_block.get("is_error", False)
                if is_error:
                    yield Label("Error:", classes="error-header")
                    yield Static(str(content), classes="error-content")

            elif self.event.event_type == "assistant_message":
                content = self.event.sdk_block.get("content", "")
                if isinstance(content, str):
                    text = content[:500]
                    if len(content) > 500:
                        text += "\n... (truncated)"
                    yield Static(text, classes="assistant-content")
                elif isinstance(content, list):
                    # Handle content blocks
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text = block.get("text", "")[:500]
                            yield Static(text, classes="assistant-content")

            # Loop type and trajectory
            if self.event.loop_type or self.event.trajectory_id:
                yield Label("Context:", classes="section-header")
                if self.event.loop_type:
                    yield Label(f"Loop Type: {self.event.loop_type}")
                if self.event.trajectory_id:
                    yield Label(f"Trajectory ID: {self.event.trajectory_id}")

            # Curator tags
            if self.event.curator_tags:
                yield Label("Curator Tags:", classes="section-header")
                yield Label(", ".join(self.event.curator_tags), classes="tag-list")

    def _get_status_text(self) -> str:
        """Get human-readable status text."""
        # Check for tool result success/error
        if self.event.event_type == "tool_result":
            is_error = self.event.sdk_block.get("is_error", False)
            return "Failed" if is_error else "Success"

        # Check for subagent stop
        if self.event.event_type == "subagent_stop":
            stop_reason = self.event.sdk_block.get("stop_reason", "unknown")
            return f"Stopped: {stop_reason}"

        return "Info"

    def _get_css_class(self) -> str:
        """Get CSS class for color coding."""
        # Red for errors
        if self.event.event_type == "tool_result" and self.event.sdk_block.get("is_error", False):
            return "event-error"

        # Blue for subagents
        if self.event.loop_type == "skill" or self.event.event_type == "subagent_stop":
            return "event-subagent"

        # Green for successful tool results
        if self.event.event_type == "tool_result" and not self.event.sdk_block.get("is_error", False):
            return "event-success"

        return "event-info"


class TimelineView(VerticalScroll):
    """Timeline widget displaying chronological stream of events.

    Features:
    - Collapsible cards for each event
    - Color coding: green for success, red for errors, blue for subagents
    - Filtering: toggle slash commands, tool failures only
    """

    filter_slash_commands = reactive(False)
    filter_failures_only = reactive(False)

    def __init__(self, session: SessionModel | None = None) -> None:
        super().__init__()
        self.session = session
        self.border_title = "Timeline View"

    def compose(self) -> ComposeResult:
        """Build the timeline layout."""
        yield Label("Event Timeline", classes="pane-header")

        if not self.session:
            yield Label("No session loaded", classes="empty-state")
            return

        # Filter controls
        with Horizontal(classes="filter-controls"):
            yield Button("Toggle Slash Commands", id="toggle-slash", variant="primary")
            yield Button("Toggle Failures Only", id="toggle-failures", variant="primary")

        # Event cards
        yield from self._render_events()

    def _render_events(self) -> list[EventCard]:
        """Render event cards based on current filters."""
        if not self.session:
            return []

        cards = []
        for idx, event in enumerate(self.session.events):
            if self._should_show_event(event):
                cards.append(EventCard(event, idx))

        return cards

    def _should_show_event(self, event: EventRecord) -> bool:
        """Check if event passes current filters."""
        # Filter slash commands (looking for SlashCommand tool usage)
        if self.filter_slash_commands:
            if event.event_type == "tool_use":
                tool_name = event.sdk_block.get("name", "")
                if tool_name == "SlashCommand":
                    return False

        # Filter failures only
        if self.filter_failures_only:
            if event.event_type != "tool_result":
                return False
            if not event.sdk_block.get("is_error", False):
                return False

        return True

    def update_session(self, session: SessionModel) -> None:
        """Update the displayed session and refresh view."""
        self.session = session
        self.refresh(recompose=True)

    @on(Button.Pressed, "#toggle-slash")
    def toggle_slash_filter(self) -> None:
        """Toggle slash command filter."""
        self.filter_slash_commands = not self.filter_slash_commands
        self.refresh(recompose=True)

    @on(Button.Pressed, "#toggle-failures")
    def toggle_failure_filter(self) -> None:
        """Toggle failure-only filter."""
        self.filter_failures_only = not self.filter_failures_only
        self.refresh(recompose=True)


class ContextView(VerticalScroll):
    """Context widget showing playbook summary and session metadata.

    Displays:
    - Current playbook summary
    - Applied deltas
    - Session metadata (task_id, created_at, duration)
    """

    def __init__(self, session: SessionModel | None = None) -> None:
        super().__init__()
        self.session = session
        self.border_title = "Context View"

    def compose(self) -> ComposeResult:
        """Build the context layout."""
        yield Label("Session Context", classes="pane-header")

        if not self.session:
            yield Label("No session loaded", classes="empty-state")
            return

        # Session metadata
        with Container(classes="context-section"):
            yield Label("Session Metadata", classes="section-header")
            yield Label(f"Session ID: {self.session.session_id}")
            yield Label(f"Task ID: {self.session.task_id}")
            yield Label(f"Created At: {self.session.created_at.isoformat()}")
            duration = self.session.get_duration_seconds()
            yield Label(f"Duration: {duration:.2f}s")
            yield Label(f"Total Events: {len(self.session.events)}")

            # Event type breakdown
            tool_uses = len(self.session.get_tool_calls())
            tool_results = len(self.session.get_tool_results())
            assistant_msgs = len(self.session.get_assistant_messages())
            skill_events = len(self.session.get_skill_events())

            yield Label(f"Tool Uses: {tool_uses}")
            yield Label(f"Tool Results: {tool_results}")
            yield Label(f"Assistant Messages: {assistant_msgs}")
            yield Label(f"Skill Events: {skill_events}")

        # Playbook context
        if self.session.playbook_context:
            with Container(classes="context-section"):
                yield Label("Playbook Context", classes="section-header")

                existing_skills = self.session.playbook_context.get("existing_skills", [])
                if existing_skills:
                    yield Label(f"Existing Skills: {len(existing_skills)}")
                    for skill in existing_skills[:10]:  # Show first 10
                        yield Label(f"  - {skill}", classes="item-list")

                constraints = self.session.playbook_context.get("constraints", [])
                if constraints:
                    yield Label(f"Constraints: {len(constraints)}")

                references = self.session.playbook_context.get("references", [])
                if references:
                    yield Label(f"References: {len(references)}")

        # Additional metadata
        if self.session.metadata:
            with Container(classes="context-section"):
                yield Label("Additional Metadata", classes="section-header")
                metadata_json = json.dumps(self.session.metadata, indent=2)
                yield Static(metadata_json, classes="json-content")

    def update_session(self, session: SessionModel) -> None:
        """Update the displayed session and refresh view."""
        self.session = session
        self.refresh(recompose=True)


class SkillDetailView(VerticalScroll):
    """Skill detail widget showing tool invocation details.

    Features:
    - Tool invocation details: name, parameters, stdout/stderr
    - Success/failure status
    - Curator annotation input field
    - Export button for selected skill
    """

    current_outcome_index = reactive(0)

    def __init__(self, session: SessionModel | None = None) -> None:
        super().__init__()
        self.session = session
        self.outcomes: list[SkillOutcome] = []
        self.border_title = "Skill Detail View"

    def compose(self) -> ComposeResult:
        """Build the skill detail layout."""
        yield Label("Skill Details", classes="pane-header")

        if not self.session:
            yield Label("No session loaded", classes="empty-state")
            return

        self.outcomes = self.session.get_skill_outcomes()

        if not self.outcomes:
            yield Label("No tool outcomes available", classes="empty-state")
            return

        # Navigation controls
        with Horizontal(classes="nav-controls"):
            yield Button("< Previous", id="prev-outcome", variant="default")
            yield Label(f"Outcome 1 of {len(self.outcomes)}", id="outcome-counter")
            yield Button("Next >", id="next-outcome", variant="default")

        # Current outcome details
        yield from self._render_current_outcome()

    def _render_current_outcome(self) -> ComposeResult:
        """Render the currently selected outcome."""
        if not self.outcomes or self.current_outcome_index >= len(self.outcomes):
            return

        outcome = self.outcomes[self.current_outcome_index]

        # Tool information
        with Container(classes="outcome-section"):
            yield Label("Tool Information", classes="section-header")
            yield Label(f"Tool Name: {outcome.tool_name}", classes="tool-name")

            tool_use_id = outcome.tool_use_id or "N/A"
            yield Label(f"Tool Use ID: {tool_use_id}")

            if outcome.timestamp:
                timestamp_str = outcome.timestamp.isoformat() if hasattr(outcome.timestamp, 'isoformat') else str(outcome.timestamp)
                yield Label(f"Timestamp: {timestamp_str}")

            if outcome.duration_ms:
                yield Label(f"Duration: {outcome.duration_ms:.2f}ms")

            status_text = "Success" if outcome.success else "Failed"
            status_class = "status-success" if outcome.success else "status-error"
            yield Label(f"Status: {status_text}", classes=status_class)

        # Parameters
        if outcome.tool_input:
            with Container(classes="outcome-section"):
                yield Label("Parameters", classes="section-header")
                params_json = json.dumps(outcome.tool_input, indent=2)
                yield Static(params_json, classes="json-content")

        # Tool output
        if outcome.tool_output:
            with Container(classes="outcome-section"):
                yield Label("Tool Output", classes="section-header")
                # Truncate very long output
                output_text = outcome.tool_output
                if len(output_text) > 2000:
                    output_text = output_text[:2000] + "\n... (truncated)"
                yield Static(output_text, classes="stdout-content")

        # Permission mode
        if outcome.permission_mode:
            with Container(classes="outcome-section"):
                yield Label("Permission Mode", classes="section-header")
                yield Label(outcome.permission_mode)

        # Curator annotation
        with Container(classes="outcome-section"):
            yield Label("Curator Annotation", classes="section-header")
            yield Input(
                placeholder="Add curator notes...",
                value="",
                id="annotation-input",
            )
            yield Button("Save Annotation", id="save-annotation", variant="success")

        # Export button
        with Container(classes="outcome-section"):
            yield Button("Export Selected Skill", id="export-skill", variant="primary")

    def update_session(self, session: SessionModel) -> None:
        """Update the displayed session and refresh view."""
        self.session = session
        self.outcomes = session.get_skill_outcomes() if session else []
        self.current_outcome_index = 0
        self.refresh(recompose=True)

    @on(Button.Pressed, "#prev-outcome")
    def previous_outcome(self) -> None:
        """Navigate to previous outcome."""
        if self.current_outcome_index > 0:
            self.current_outcome_index -= 1
            self.refresh(recompose=True)

    @on(Button.Pressed, "#next-outcome")
    def next_outcome(self) -> None:
        """Navigate to next outcome."""
        if self.current_outcome_index < len(self.outcomes) - 1:
            self.current_outcome_index += 1
            self.refresh(recompose=True)

    @on(Button.Pressed, "#save-annotation")
    def save_annotation(self) -> None:
        """Save curator annotation to current outcome."""
        if not self.outcomes or self.current_outcome_index >= len(self.outcomes):
            return

        try:
            annotation_input = self.query_one("#annotation-input", Input)
            annotation_text = annotation_input.value

            # Store annotation in session metadata
            if not hasattr(self.session, '_annotations'):
                self.session.metadata['annotations'] = {}

            outcome = self.outcomes[self.current_outcome_index]
            tool_use_id = outcome.tool_use_id or f"outcome_{self.current_outcome_index}"

            if 'annotations' not in self.session.metadata:
                self.session.metadata['annotations'] = {}

            self.session.metadata['annotations'][tool_use_id] = annotation_text

            self.app.notify("Annotation saved", severity="information")
        except Exception as e:
            self.app.notify(f"Error saving annotation: {e}", severity="error")

    @on(Button.Pressed, "#export-skill")
    def export_skill(self) -> None:
        """Export current skill outcome to JSON file."""
        if not self.outcomes or self.current_outcome_index >= len(self.outcomes):
            return

        outcome = self.outcomes[self.current_outcome_index]

        # Get annotation if exists
        tool_use_id = outcome.tool_use_id or f"outcome_{self.current_outcome_index}"
        annotation = self.session.metadata.get('annotations', {}).get(tool_use_id, "")

        # Prepare export data
        timestamp_str = ""
        if outcome.timestamp:
            timestamp_str = outcome.timestamp.isoformat() if hasattr(outcome.timestamp, 'isoformat') else str(outcome.timestamp)

        export_data = {
            "tool_name": outcome.tool_name,
            "tool_use_id": outcome.tool_use_id,
            "timestamp": timestamp_str,
            "parameters": outcome.tool_input,
            "output": outcome.tool_output,
            "success": outcome.success,
            "duration_ms": outcome.duration_ms,
            "permission_mode": outcome.permission_mode,
            "curator_annotation": annotation,
            "session_id": self.session.session_id if self.session else "unknown",
            "exported_at": datetime.now().isoformat(),
        }

        # Save to file
        export_dir = Path("ace-exports")
        export_dir.mkdir(exist_ok=True)

        # Create safe filename
        safe_tool_name = "".join(c if c.isalnum() else "_" for c in outcome.tool_name)
        safe_id = (outcome.tool_use_id or "unknown")[:8]
        filename = f"skill_{safe_tool_name}_{safe_id}.json"
        export_path = export_dir / filename

        try:
            with export_path.open("w") as fh:
                json.dump(export_data, fh, indent=2)

            self.app.notify(f"Skill exported to {export_path}", severity="information")
        except Exception as e:
            self.app.notify(f"Export failed: {e}", severity="error")


class TrajectorySelector(VerticalScroll):
    """Left sidebar widget for selecting trajectories."""

    def __init__(self, sessions: list[SessionModel]) -> None:
        super().__init__()
        self.sessions = sessions
        self.border_title = "Trajectories"

    def compose(self) -> ComposeResult:
        """Build the trajectory selector layout."""
        yield Label("Available Sessions", classes="pane-header")

        if not self.sessions:
            yield Label("No sessions loaded", classes="empty-state")
            return

        # Build tree of sessions
        tree: Tree[dict[str, Any]] = Tree("Sessions")
        tree.root.expand()

        for idx, session in enumerate(self.sessions):
            label = f"[{idx}] {session.task_id[:16]}..."
            node_data = {"index": idx, "session": session}
            node = tree.root.add(label, data=node_data)

            # Add session metadata as child nodes
            node.add_leaf(f"ID: {session.session_id[:16]}...")
            node.add_leaf(f"Events: {len(session.events)}")
            node.add_leaf(f"Duration: {session.get_duration_seconds():.2f}s")

        yield tree


class SkillInspectorApp(App[None]):
    """Main Textual application for ACE skill session inspection.

    Features:
    - Three-pane layout with tabs or split view
    - Left sidebar: trajectory selector list
    - Main area: Timeline/Context/SkillDetail tabs
    - Keyboard shortcuts:
      - ←/→: switch tabs
      - s: toggle slash-command filter
      - e: export selected skill delta
      - q: quit

    Attributes:
        sessions: List of SessionModel objects to display
        current_session: Currently selected session
    """

    CSS = EXECUTE_VIEW_CSS + """
    Screen {
        layout: horizontal;
    }

    TrajectorySelector {
        width: 30;
        border: solid $primary;
    }

    #main-content {
        width: 1fr;
        border: solid $accent;
    }

    .pane-header {
        text-style: bold;
        background: $boost;
        padding: 1;
        margin-bottom: 1;
    }

    .section-header {
        text-style: bold;
        color: $accent;
        margin-top: 1;
        margin-bottom: 1;
    }

    .context-section {
        border: solid $primary;
        padding: 1;
        margin-bottom: 1;
    }

    .outcome-section {
        border: solid $primary;
        padding: 1;
        margin-bottom: 1;
    }

    .filter-controls {
        height: auto;
        margin-bottom: 1;
    }

    .nav-controls {
        height: auto;
        margin-bottom: 1;
    }

    .tool-name {
        color: $success;
        text-style: bold;
    }

    .status-success {
        color: $success;
        text-style: bold;
    }

    .status-error {
        color: $error;
        text-style: bold;
    }

    .error-header {
        color: $error;
        text-style: bold;
    }

    .json-content {
        background: $surface;
        padding: 1;
        border: solid $primary-background;
    }

    .result-content {
        background: $surface;
        padding: 1;
        border: solid $primary-background;
    }

    .stdout-content {
        background: $surface;
        padding: 1;
        border: solid $primary-background;
    }

    .stderr-content {
        background: $error-darken-1;
        padding: 1;
        border: solid $error;
        color: $text;
    }

    .assistant-content {
        background: $surface;
        padding: 1;
        border: solid $accent-darken-1;
    }

    .error-content {
        background: $error-darken-2;
        padding: 1;
        border: solid $error;
    }

    .empty-state {
        color: $text-muted;
        text-style: italic;
        padding: 2;
    }

    .item-list {
        margin-left: 2;
        color: $text-muted;
    }

    .tag-list {
        color: $accent;
        text-style: italic;
    }

    /* Event card color coding */
    .event-success Collapsible {
        border-left: thick $success;
    }

    .event-error Collapsible {
        border-left: thick $error;
    }

    .event-subagent Collapsible {
        border-left: thick $accent;
    }

    .event-info Collapsible {
        border-left: thick $primary;
    }

    Collapsible {
        margin-bottom: 1;
    }

    Input {
        margin-bottom: 1;
    }

    Button {
        margin-right: 1;
    }
    """

    BINDINGS = [
        ("left,h", "previous_tab", "Previous Tab"),
        ("right,l", "next_tab", "Next Tab"),
        ("n", "focus_execute_tab", "New Task"),
        ("s", "toggle_slash", "Toggle Slash Filter"),
        ("e", "export_skill", "Export Skill"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self, sessions: list[SessionModel]) -> None:
        super().__init__()
        self.sessions = sessions
        self.current_session: SessionModel | None = sessions[0] if sessions else None
        self.title = "ACE Skill Inspector"
        self.sub_title = f"{len(sessions)} session(s) loaded"

    def compose(self) -> ComposeResult:
        """Build the main application layout."""
        yield Header()

        # Main horizontal layout
        with Horizontal():
            # Left sidebar: trajectory selector
            yield TrajectorySelector(self.sessions)

            # Main content area: tabbed views
            with TabbedContent(id="main-content"):
                # Execute tab - first position for easy access
                with TabPane("Execute", id="execute-tab"):
                    yield ExecuteView()

                with TabPane("Timeline", id="timeline-tab"):
                    yield TimelineView(self.current_session)

                with TabPane("Context", id="context-tab"):
                    yield ContextView(self.current_session)

                with TabPane("Skill Detail", id="detail-tab"):
                    yield SkillDetailView(self.current_session)

        yield Footer()

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle trajectory selection from tree."""
        if event.node.data and isinstance(event.node.data, dict):
            session_index = event.node.data.get("index")
            if session_index is not None and 0 <= session_index < len(self.sessions):
                self.current_session = self.sessions[session_index]
                self._update_views()

    def _update_views(self) -> None:
        """Update all view widgets with current session."""
        if not self.current_session:
            return

        # Update timeline view
        timeline = self.query_one(TimelineView)
        timeline.update_session(self.current_session)

        # Update context view
        context = self.query_one(ContextView)
        context.update_session(self.current_session)

        # Update skill detail view
        detail = self.query_one(SkillDetailView)
        detail.update_session(self.current_session)

        # Update subtitle
        self.sub_title = f"Session: {self.current_session.task_id[:32]}..."

    def action_previous_tab(self) -> None:
        """Switch to previous tab."""
        tabbed = self.query_one(TabbedContent)
        tabbed.action_previous_tab()

    def action_next_tab(self) -> None:
        """Switch to next tab."""
        tabbed = self.query_one(TabbedContent)
        tabbed.action_next_tab()

    def action_toggle_slash(self) -> None:
        """Toggle slash command filter in timeline."""
        timeline = self.query_one(TimelineView)
        timeline.toggle_slash_filter()

    def action_export_skill(self) -> None:
        """Export current skill from detail view."""
        detail = self.query_one(SkillDetailView)
        detail.export_skill()

    def action_focus_execute_tab(self) -> None:
        """Switch to the Execute tab."""
        tabbed = self.query_one(TabbedContent)
        tabbed.active = "execute-tab"

    async def on_execute_view_execute_requested(self, event: ExecuteView.ExecuteRequested) -> None:
        """Handle task execution request from ExecuteView.

        Args:
            event: ExecuteRequested event containing task and playbook path
        """
        execute_view = self.query_one(ExecuteView)

        try:
            # Import task executor
            from .task_executor import TaskExecutor

            # Setup paths
            transcript_path = Path("docs/transcripts") / f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
            transcript_path.parent.mkdir(parents=True, exist_ok=True)

            # Create executor
            executor = TaskExecutor()

            # Progress callback for UI updates
            def on_progress(message: str) -> None:
                # Use call_from_thread for thread-safe UI updates
                self.call_from_thread(execute_view.log_output, message, "info")

            execute_view.log_output("Starting task execution...", "info")

            # Execute task asynchronously
            result = await executor.execute_task(
                task_prompt=event.task,
                playbook_path=Path(event.playbook_path),
                transcript_path=transcript_path,
                progress_callback=on_progress,
            )

            if result.success:
                execute_view.set_status("completed")
                execute_view.log_output(
                    f"Task completed successfully! Version: {result.playbook_version}, "
                    f"Deltas: {result.delta_count}",
                    "success"
                )
                execute_view.set_trajectory_path(transcript_path)

                # Reload session from transcript
                await self._reload_session_from_transcript(transcript_path)
            else:
                execute_view.set_status("error")
                execute_view.log_output(f"Task failed: {result.error_message}", "error")

        except Exception as e:
            execute_view.set_status("error")
            execute_view.log_output(f"Execution error: {str(e)}", "error")
            logger.exception("Task execution failed")
        finally:
            execute_view.set_executing(False)

    async def _reload_session_from_transcript(self, transcript_path: Path) -> None:
        """Reload sessions list after new transcript is created.

        Args:
            transcript_path: Path to the newly created transcript file
        """
        try:
            from .models import TranscriptLoader

            # Load the new session
            new_sessions = TranscriptLoader.load_transcript(transcript_path)

            if new_sessions:
                # Add to sessions list
                self.sessions.extend(new_sessions)
                self.current_session = new_sessions[0]

                # Update subtitle
                self.sub_title = f"{len(self.sessions)} session(s) loaded"

                # Switch to Timeline tab and update views
                tabbed = self.query_one(TabbedContent)
                tabbed.active = "timeline-tab"
                self._update_views()

                self.notify(f"Loaded new session: {self.current_session.task_id[:32]}...", severity="information")
            else:
                self.notify("No sessions found in transcript", severity="warning")

        except Exception as e:
            logger.exception("Failed to reload session from transcript")
            self.notify(f"Failed to load transcript: {e}", severity="error")


def run_inspector(sessions: list[SessionModel]) -> None:
    """Launch the inspector TUI application.

    Args:
        sessions: List of SessionModel objects to inspect
    """
    app = SkillInspectorApp(sessions)
    app.run()


def main() -> None:
    """CLI entry point for the inspector.

    Usage:
        python -m ace.tools.inspector_ui <transcript.jsonl>
    """
    import sys
    from .models import TranscriptLoader

    if len(sys.argv) < 2:
        print("Usage: python -m ace.tools.inspector_ui <transcript.jsonl>")
        sys.exit(1)

    transcript_path = Path(sys.argv[1])

    if not transcript_path.exists():
        print(f"Error: Transcript file not found: {transcript_path}")
        sys.exit(1)

    print(f"Loading sessions from {transcript_path}...")

    try:
        sessions = TranscriptLoader.load_transcript(transcript_path)
    except Exception as e:
        print(f"Error loading transcript: {e}")
        sys.exit(1)

    if not sessions:
        print("Warning: No sessions found in transcript file")
        # Create a dummy session for demonstration
        sessions = [
            SessionModel(
                session_id="demo",
                task_id="demo-task",
                created_at=datetime.now(),
            )
        ]

    print(f"Loaded {len(sessions)} session(s)")
    run_inspector(sessions)


if __name__ == "__main__":
    main()
