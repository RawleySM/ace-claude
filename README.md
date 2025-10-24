# ACE Claude

**Autonomous Coding Engine** - A self-improving AI development system built on Claude Code and the Claude Agent SDK.

## Overview

ACE Claude implements a dual-loop architecture that enables autonomous software development with continuous learning and skill accumulation:

- **Task Loop**: Orchestrates complex multi-step development tasks using Claude Code
- **Skill Loop**: Generates and refines reusable development patterns and workflows
- **Delta Playbook**: Tracks learned patterns and improvements for future reuse

The system leverages the [Claude Agent SDK](https://docs.claude.com/en/api/agent-sdk) to create specialized sub-agents and custom slash commands for a fully autonomous coding experience.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Task Loop                         │
│  (ace-task.py with ace-task/.claude/)              │
│                                                     │
│  ┌──────────────┐      ┌──────────────┐           │
│  │ Task Query   │─────→│ Task         │           │
│  │              │      │ Trajectory   │           │
│  └──────────────┘      └──────┬───────┘           │
│                               │                    │
│                               ↓                    │
│  ┌──────────────┐      ┌──────────────┐           │
│  │ Delta        │←─────│ Task         │           │
│  │ Playbook     │      │ Curator      │           │
│  └──────────────┘      └──────────────┘           │
│         ↕                                          │
└─────────┼──────────────────────────────────────────┘
          │ In-process function call: SkillLoop()
          ↓
┌─────────────────────────────────────────────────────┐
│                  Skill Loop                         │
│  (SkillLoop class with ace-skill/.claude/)         │
│                                                     │
│  ┌──────────────┐      ┌──────────────┐           │
│  │ Skill        │─────→│ Skill        │           │
│  │ Generator    │      │ Reflector    │           │
│  └──────────────┘      └──────────────┘           │
│                                                     │
└─────────────────────────────────────────────────────┘

Two ClaudeSDKClient instances with different cwd parameters,
running in a single Python process with direct message passing.
```

### Components

- **ace-task/**: Main task orchestration loop with Claude Agent SDK integration
- **ace-skill/**: Skill generation utilities module with `SkillLoop` class for in-process skill generation
- **ace_tools/**: Session inspection and analysis toolkit with Textual UI inspector
- **Delta Playbook**: JSON-based knowledge store of learned development patterns
- **Task Trajectory**: Unified trajectory recording both task and skill loop messages
- **Task Curator**: Analyzes trajectories to extract reusable patterns and update the playbook
- **Skill Reflector**: Hook-based validation system for skill quality and safety

## Prerequisites

- **Python 3.10+** with [uv](https://github.com/astral-sh/uv) for package management
- **Node.js & npm** for installing Claude Code CLI
- **Claude Code CLI** (installed via setup script)
- **Anthropic API Key** set as `ANTHROPIC_API_KEY` environment variable

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd ace-claude
```

2. Set your Anthropic API key:
```bash
export ANTHROPIC_API_KEY='your-api-key-here'
```

3. Run the setup script to install Claude Code CLI:
```bash
./scripts/setup_claude_code.sh
```

This will:
- Install the `@anthropic-ai/claude-code` CLI globally
- Authenticate using your API key
- Verify the installation

## Usage

### Running the Task Loop

The task loop is the main entry point for autonomous development tasks:

```bash
uv run ace-task/ace-task.py
```

This starts an interactive session where you can:
- Provide high-level development goals
- Let ACE decompose tasks into subtasks
- Watch as it generates code, runs tests, and iterates
- See the system learn patterns and update the playbook
- Automatically escalate to skill loop when reusable patterns are detected

### Using the Session Inspector

Inspect and analyze ACE session trajectories with the Textual UI inspector:

```bash
# Install inspector dependencies
cd ace_tools
uv pip install -r requirements.txt

# Launch inspector with a transcript file
python -m ace_tools.skills_inspector docs/transcripts/session.jsonl
```

The inspector provides:
- **Timeline view**: Chronological stream of assistant messages, tool uses, and results
- **Context view**: Session metadata, agents, and playbook state
- **Skill detail view**: Deep dive into specific tool invocations

See the [Session Inspection and Analysis](#session-inspection-and-analysis) section for complete documentation.

### Running Tests

Verify the complete system integration:

```bash
./test_e2e.py
```

The test suite validates:
- Module imports and dependencies
- Directory structure and configuration
- Agent definitions and loading
- Hook system configuration
- Playbook operations
- Trajectory tracking
- Curator logic

## Project Structure

```
ace-claude/
├── ace-task/              # Task loop orchestration
│   ├── ace-task.py       # Main task loop script
│   ├── playbook.json     # Delta playbook storage
│   └── .claude/          # Task-specific agents and commands
│       ├── agents/       # Custom agent definitions
│       └── commands/     # Slash commands for task loop
│
├── ace-skill/            # Skill generation system
│   ├── ace_skill_utils.py  # Shared utilities module (SkillLoop class)
│   ├── skills/           # Generated skill storage
│   └── .claude/          # Skill-specific agents and commands
│       ├── agents/       # Custom agent definitions
│       └── commands/     # Slash commands for skill loop
│
├── ace_tools/           # Session inspection and analysis tools
│   ├── __init__.py      # Package exports
│   ├── skills_inspector.py  # CLI entry point
│   ├── inspector_ui.py  # Textual TUI implementation
│   ├── models.py        # Data models for sessions and events
│   ├── transcript_capture.py  # SDK hook integration
│   ├── example_integration.py  # Integration patterns
│   ├── test_models.py   # Unit tests
│   └── requirements.txt # Tool dependencies
│
├── plan/                 # Design specifications
│   └── *.md             # Architecture and implementation docs
│
├── scripts/             # Automation scripts
│   └── setup_claude_code.sh  # Environment setup
│
└── test_e2e.py          # End-to-end test suite
```

## How It Works

### Task Execution Flow

1. **User provides a task**: High-level development goal or feature request
2. **Task Generator**: Decomposes into actionable subtasks
3. **Task Execution**: Uses Claude Code tools (Read, Write, Bash, etc.) to implement
4. **Trajectory Recording**: Captures all interactions, decisions, and code changes
5. **Task Curator**: Analyzes trajectory for reusable patterns
6. **Playbook Update**: Stores learned patterns in delta playbook
7. **Skill Generation** (optional): Escalates to in-process skill loop for complex patterns

### Skill Generation Flow (In-Process)

1. **Pattern Detection**: Curator identifies reusable patterns in trajectory
2. **Skill Loop Invocation**: Task loop instantiates `SkillLoop` with `cwd=ace-skill/`
3. **Separate ClaudeSDKClient**: Skill loop creates its own SDK client using `ace-skill/.claude/` agents
4. **Message Streaming**: Skill messages are streamed directly into unified task trajectory
5. **Delta Extraction**: `summarize_skill_session()` extracts structured deltas from skill messages
6. **Skill Reflector**: Hook-based validation runs during skill generation
7. **Playbook Integration**: Task loop validates and merges deltas into delta playbook
8. **Context Enrichment**: Task continues with enriched playbook context

### Key Architecture: In-Process Dual-Loop Design

ACE Claude uses a unique in-process architecture where both task and skill loops run in the same Python process but maintain separate contexts:

**Working Directory Isolation**:
- Task loop: `ClaudeSDKClient` with `cwd=ace-task/` loads `ace-task/.claude/` agents
- Skill loop: `ClaudeSDKClient` with `cwd=ace-skill/` loads `ace-skill/.claude/` agents
- No separate process boundaries or MCP servers needed

**Unified Trajectory**:
- Both loops append messages to a single `TaskTrajectory`
- Messages tagged with `metadata.loop_type` ("task" or "skill")
- Skill sessions extractable via `get_skill_sessions()`

**Direct Function Calls**:
- Task loop imports `ace_skill_utils` module directly
- Instantiates `SkillLoop` class when patterns detected
- Streams skill messages in real-time via `async for`
- No inter-process communication overhead

### Delta Playbook

The playbook is a JSON file that accumulates knowledge over time:

```json
{
  "items": [
    {
      "type": "skill",
      "name": "error-handler",
      "description": "Robust error handling pattern",
      "token_count": 150,
      "created_at": "2025-10-24T10:30:00Z"
    }
  ],
  "version": 1,
  "token_budget": 5000,
  "updated_at": "2025-10-24T10:30:00Z"
}
```

**Playbook Item Types**:
- `skill`: Reusable code patterns and runbooks
- `constraint`: Validation rules and limitations
- `reference`: External documentation and resources
- `clarification`: Questions and answers from skill sessions

**Token Budget Management**:
The Task Curator tracks `proposed_updates_token_count` and automatically triggers skill loop escalation when pending updates exceed the playbook's `token_budget`, enabling proactive generalization before context bloat.

## Session Inspection and Analysis

### Overview

The `ace_tools/` directory provides a comprehensive toolkit for inspecting, analyzing, and curating ACE task and skill loop trajectories. The centerpiece is the **Skills Session Inspector**, a Terminal UI (TUI) built with [Textual](https://textual.textualize.io/) that provides a structured, filterable view of Claude Agent SDK sessions.

### Why Use the Inspector?

Raw terminal logs can be noisy and difficult to analyze. The inspector provides:

- **Structured filtering**: Toggle views to show only tool failures, slash commands, or subagent activity
- **Replay fidelity**: Reconstructs the exact order of `ClaudeSDKClient` events with full metadata
- **Curator workflow**: Integrated export actions for extracting deltas and updating the playbook
- **Extensible architecture**: Built on structured JSONL transcripts that can power future dashboards

### Installation

Install the inspector dependencies:

```bash
cd ace_tools
uv pip install -r requirements.txt
```

Dependencies:
- `claude-agent-sdk>=0.1.4` - Claude Agent SDK for hook integration
- `pydantic>=2.0.0` - Data validation and serialization
- `textual>=0.40.0` - Terminal UI framework

### Capturing Transcripts

To use the inspector, you first need to capture session transcripts. There are three integration patterns:

#### 1. Context Manager Pattern (Recommended)

```python
from pathlib import Path
from ace_tools.transcript_capture import enable_transcript_capture
from claude_agent_sdk import AgentDefinition

agents = {
    "task-generator": AgentDefinition(
        description="Generates task execution plans",
        prompt="You are a task generator...",
        model="sonnet",
    ),
}

with enable_transcript_capture(
    output_path=Path("docs/transcripts/session.jsonl"),
    agents=agents,
    allowed_tools=["Read", "Write", "Bash", "Grep"],
    permission_mode="auto",
    task_id="my-task-001",
) as hooks:
    # Use hooks in ClaudeAgentOptions
    options = ClaudeAgentOptions(agents=agents, hooks=hooks)
    async with ClaudeSDKClient(options=options) as client:
        await client.query(task_prompt)
        async for msg in client.receive_response():
            # Messages automatically captured to transcript
            pass
```

#### 2. Manual Hook Merging

For advanced control, merge transcript hooks with existing task/skill hooks:

```python
from ace_tools.transcript_capture import build_transcript_hooks, merge_hooks

# Build transcript hooks
transcript_hooks = build_transcript_hooks(Path("transcript.jsonl"))

# Merge with existing hooks
task_hooks = build_task_hooks()  # Your existing hooks
merged_hooks = merge_hooks(task_hooks, transcript_hooks)

# Use merged hooks
options = ClaudeAgentOptions(agents=agents, hooks=merged_hooks)
```

#### 3. CLI Flag Integration

Add transcript capture to `ace-task.py` with a command-line flag:

```bash
python ace-task/ace-task.py \
    --enable-transcript docs/transcripts/session.jsonl \
    "Build a web application"
```

See `ace_tools/example_integration.py` for complete integration examples.

### Using the Inspector

Launch the inspector with a transcript file:

```bash
python -m ace_tools.skills_inspector docs/transcripts/session.jsonl
```

Or use it directly:

```bash
python ace_tools/skills_inspector.py docs/transcripts/session.jsonl
```

#### Inspector UI Features

The Textual UI provides three main views:

1. **Timeline Pane**: Chronological stream of events rendered as collapsible cards:
   - `AssistantMessage` blocks
   - `ToolUseBlock` invocations
   - `ToolResultBlock` outputs
   - `SubagentStop` events

2. **Context Pane**: Session overview:
   - Current playbook summary
   - Applied deltas
   - Session metadata (agents, permissions, tools)

3. **Skill Detail Pane**: Deep dive into individual tool invocations:
   - Parameters and arguments
   - stdout/stderr output
   - Curator annotations and tags

#### Keyboard Shortcuts

- `←/→` - Switch between tabs (Timeline / Context / Skill Detail)
- `s` - Toggle slash-command filter
- `e` - Export selected skill delta to `ace/playbook_deltas/{session_id}.json`
- `q` - Quit inspector

### Transcript Format

Transcripts are stored as JSONL (JSON Lines) files where each line is a structured event:

```json
{"event_type": "session_start", "timestamp": "2025-10-24T10:30:00Z", "metadata": {...}}
{"event_type": "tool_use", "timestamp": "2025-10-24T10:30:15Z", "sdk_block": {...}}
{"event_type": "tool_result", "timestamp": "2025-10-24T10:30:20Z", "sdk_block": {...}}
```

The inspector uses Pydantic models to validate and parse these events:

- **SessionModel**: Wraps complete session transcripts
- **EventRecord**: Normalized schema for each event
- **SkillOutcome**: Derived from tool use/result pairs with enriched metadata

### Integration with ACE Loops

The transcript capture system integrates seamlessly with the dual-loop architecture:

- **Task Loop**: Captures main orchestration trajectory
- **Skill Loop**: Captures skill generation sessions with `loop_type="skill"` metadata
- **Unified Trajectory**: Both loops write to the same transcript, enabling cross-loop analysis

Events are tagged with `metadata.loop_type` to distinguish task vs. skill operations.

### Advanced Features

#### Filtering Sessions

Group transcripts by session ID or task ID:

```python
from ace_tools.models import TranscriptLoader

loader = TranscriptLoader()
sessions = loader.load_file(Path("transcript.jsonl"))

# Filter by task ID
task_sessions = [s for s in sessions if s.task_id == "my-task-001"]
```

#### Extracting Skill Sessions

Pull out skill-specific sessions for focused analysis:

```python
from ace_tools.models import SessionModel

session = SessionModel.load(Path("transcript.jsonl"))
skill_sessions = session.get_skill_sessions()

for skill_session in skill_sessions:
    print(f"Skill: {skill_session.metadata.get('skill_name')}")
    print(f"Events: {len(skill_session.events)}")
```

#### Custom Event Handlers

Add custom hooks to process events in real-time:

```python
from ace_tools.transcript_capture import EventRecord

async def custom_handler(event: EventRecord):
    if event.event_type == "tool_use" and event.sdk_block.name == "Bash":
        print(f"Bash command executed: {event.sdk_block.input}")

# Register with TranscriptWriter
writer = TranscriptWriter(output_path, custom_hooks=[custom_handler])
```

### Future Enhancements

The inspector is designed for extensibility:

- **Live mode**: Tail in-progress transcript files with async updates
- **Web dashboard**: Browser-based UI using the same SessionModel
- **Metrics overlay**: Tool success rates, permission escalations, and performance stats
- **Delta suggestions**: ML-powered recommendations for playbook updates

## Configuration

### Custom Agents

Add agent definitions to `.claude/agents/` in either directory using markdown format:

```markdown
# ace-task/.claude/agents/tester.md

## Description
Creates and runs comprehensive tests

## Prompt
You are a testing expert. Write thorough tests ensuring code quality.

## Tools
- Read
- Write
- Bash

## Model
sonnet
```

### Slash Commands

Create custom commands in `.claude/commands/`:

```markdown
# ace-task/.claude/commands/build.md
Run the project build and report any errors
```

Then use with `/build` in the task loop.

## Development

### Adding New Features

1. Modify the task or skill loop scripts
2. Update `.claude/agents/` if new specialized agents are needed
3. Add tests to `test_e2e.py`
4. Run the test suite to verify integration

### Debugging

Set debug mode for detailed logging:

```bash
DEBUG_STARTUP_SCRIPT=1 ./scripts/setup_claude_code.sh
```

## References

- [Claude Agent SDK Documentation](https://docs.claude.com/en/api/agent-sdk)
- [Claude Code CLI](https://docs.claude.com/en/docs/claude-code)
- [ACE Framework](https://github.com/daveshap/ACE_Framework)

## License

See LICENSE file for details.
