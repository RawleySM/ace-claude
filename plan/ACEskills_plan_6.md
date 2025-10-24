# Spec: ACE Skills Sub-loop with MCP Server Architecture

## Overview anchored to Figure 1

The skills loop in Figure 1 adds a bidirectional Claude Code detour between the Task Generator, Skill Reflector, and Delta Playbook. We realize that detour with two independent single-file uv-compatible Python scripts that communicate via the MCP protocol:

- **`ace-task/ace-task.py`** – Orchestrates the full TASK loop, streams trajectory state, reconciles delta playbook items, and invokes the skill generation MCP tool when needed.
- **`ace-skill/ace-skill.py`** – Runs as a standalone stdio MCP server that exposes a `generate_skill` tool. This server operates in its own process with its own `.claude/` directory context.

## Architecture: Process Boundaries

```
┌─────────────────────────────────┐
│   ace-task.py (Main Process)    │
│   - Task loop orchestration     │
│   - Uses ace-task/.claude/      │
│   - Invokes MCP tool             │
└────────────┬────────────────────┘
             │ MCP Protocol (stdio)
             │ Tool: mcp__ace-skills__generate_skill
             ▼
┌─────────────────────────────────┐
│ ace-skill.py (MCP Server Process)│
│ - Skill generation loop          │
│ - Uses ace-skill/.claude/        │
│ - Returns skill deltas           │
└──────────────────────────────────┘
```

## Directory Structure

```
ace-task/
  ace-task.py              # Main orchestrator
  .mcp.json                # MCP server configuration
  .claude/
    agents/
      task-generator.md
      task-curator.md
      task-reflector.md
    commands/
      review-playbook.md
  playbook.json            # Delta playbook persistence

ace-skill/
  ace-skill.py             # MCP server (stdio)
  .claude/
    agents/
      skill-generator.md
      skill-curator.md
      skill-reflector.md
    commands/
      validate-skill.md
  skills/                  # Generated skills library
```

## MCP Server Configuration

`ace-task/.mcp.json` spawns the skill server in its own directory:

```json
{
  "mcpServers": {
    "ace-skills": {
      "command": "uv",
      "args": ["run", "../ace-skill/ace-skill.py"],
      "cwd": "../ace-skill"
    }
  }
}
```

This ensures:
- `ace-skill.py` runs with `cwd=ace-skill/`
- It loads agents from `ace-skill/.claude/agents/`
- It loads commands from `ace-skill/.claude/commands/`
- Process-level isolation between task and skill contexts

## Claude-Agent-SDK Touchpoints

### Task Loop (ace-task.py)

**Streaming TASK loop** – Use `ClaudeSDKClient` with MCP server configuration:

```python
# /// script
# dependencies = ["claude-agent-sdk", "anyio"]
# ///

from pathlib import Path
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

task_root = Path(__file__).parent

options = ClaudeAgentOptions(
    setting_sources=["project"],
    cwd=task_root,
    # MCP server loaded from .mcp.json automatically
)

async with ClaudeSDKClient(options=options) as client:
    await client.query("Generate authentication skill")

    async for msg in client.receive_response():
        # Process messages
        display_message(msg)
```

**Invoking the skill tool** – Call the MCP tool with allowed tools gating:

```python
options = ClaudeAgentOptions(
    setting_sources=["project"],
    cwd=task_root,
    allowedTools=["mcp__ace-skills__generate_skill"]
)

async with ClaudeSDKClient(options=options) as client:
    # Claude can now invoke the generate_skill tool from the MCP server
    await client.query(
        "Generate a reusable skill for user authentication with JWT tokens"
    )

    async for msg in client.receive_response():
        if isinstance(msg, ToolResultBlock):
            # Extract skill deltas from tool result
            skill_deltas = parse_skill_result(msg.content)
            playbook.merge(skill_deltas)
```

### Skill MCP Server (ace-skill.py)

**MCP server implementation** – Standalone stdio server with isolated `.claude/` context:

```python
# /// script
# dependencies = ["claude-agent-sdk", "anyio", "mcp"]
# ///

import asyncio
from pathlib import Path
from mcp.server import Server
from mcp.server.stdio import stdio_server
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

skill_root = Path(__file__).parent
server = Server("ace-skills")

@server.call_tool()
async def generate_skill(
    prompt: str,
    playbook_context: dict | None = None
) -> dict:
    """
    Generate a reusable skill from task requirements.

    Args:
        prompt: Description of skill to generate
        playbook_context: Existing skills to avoid duplication

    Returns:
        Structured skill deltas including code, docs, and metadata
    """
    # Initialize SDK client with ace-skill/.claude/ directory
    options = ClaudeAgentOptions(
        setting_sources=["project"],
        cwd=skill_root,
    )

    messages = []
    async with ClaudeSDKClient(options=options) as client:
        # Enrich prompt with playbook context
        enriched_prompt = enrich_with_context(prompt, playbook_context)

        await client.query(enriched_prompt)

        async for msg in client.receive_response():
            messages.append(msg)

    # Extract skill deltas from message stream
    return extract_skill_deltas(messages)


async def main():
    """Run MCP server on stdio."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
```

## Data Flow: Task → MCP Tool → Skill Deltas

1. **Task Query** – User provides task to `ace-task.py`
2. **Skill Need Detection** – Task loop determines skill generation is needed
3. **MCP Tool Invocation** – Claude (via SDK) calls `mcp__ace-skills__generate_skill`
4. **Server Execution** – `ace-skill.py` receives tool call, runs skill session with `ace-skill/.claude/` agents
5. **Delta Extraction** – Server extracts structured deltas (code, docs, references)
6. **Tool Result** – Server returns deltas as tool result
7. **Playbook Merge** – Task loop validates and merges deltas into playbook
8. **Continue Task** – Task loop continues with enriched context

## Tool Interface: generate_skill

**Input Schema:**
```typescript
{
  prompt: string,              // Skill generation request
  playbook_context?: {         // Optional context to avoid duplication
    existing_skills: string[],
    constraints: object[],
    references: object[]
  }
}
```

**Output Schema:**
```typescript
{
  success: boolean,
  skill_deltas: {
    clarifications: string[],     // Questions raised during generation
    references: string[],         // External docs discovered
    runbook_snippets: {           // Generated code/config
      code: string,
      language: string,
      description: string
    }[],
    reflection_notes: string[],   // Skill reflector insights
    metadata: {
      duration_seconds: number,
      tool_calls: number,
      agents_invoked: string[]
    }
  },
  trajectory_id: string           // For debugging/inspection
}
```

## Responsibilities

### ace-task/ace-task.py (Task Orchestrator)

1. **Task loop management**
   - Load task agents from `ace-task/.claude/agents/`
   - Stream task messages and build trajectory
   - Detect when skill generation is needed

2. **MCP tool invocation**
   - Call `mcp__ace-skills__generate_skill` with skill prompt
   - Pass playbook context to avoid duplication
   - Parse tool result for skill deltas

3. **Playbook management**
   - Validate skill deltas before merging
   - Persist playbook to `playbook.json`
   - Inject playbook context into subsequent tasks

4. **Trajectory export**
   - Capture all messages (task + tool results)
   - Export to JSONL for inspection
   - Annotate with skill session metadata

### ace-skill/ace-skill.py (Skill MCP Server)

1. **MCP server lifecycle**
   - Run as stdio server process
   - Register `generate_skill` tool
   - Handle tool invocations independently

2. **Skill generation session**
   - Create `ClaudeSDKClient` with `ace-skill/.claude/` context
   - Run skill generation with skill agents
   - Stream messages and extract deltas

3. **Delta extraction**
   - Parse messages for clarifications, references, code
   - Apply skill reflector validation
   - Structure output for playbook consumption

4. **Isolation**
   - No imports from `ace-task`
   - No shared state
   - Pure stdio communication

## Agent Definitions

### Task Agents (ace-task/.claude/agents/)

**task-generator.md** – Decomposes tasks, identifies skill generation needs
**task-curator.md** – Manages execution flow and playbook
**task-reflector.md** – Validates outcomes and quality

### Skill Agents (ace-skill/.claude/agents/)

**skill-generator.md** – Creates reusable patterns from requirements
**skill-curator.md** – Organizes skills into coherent library
**skill-reflector.md** – Validates skill quality and reusability

## Implementation Considerations

**Process isolation benefits:**
- Hard separation between task and skill contexts
- Independent `.claude/` directory resolution
- No risk of agent/command conflicts
- Server can be restarted without affecting task loop

**Process isolation costs:**
- More complex deployment (two processes)
- Stdio communication overhead
- Harder to debug across process boundary
- Cannot share Python objects directly

**Testing:**
- Mock MCP tool results for unit tests
- Use test fixtures for skill deltas
- Validate tool schema compliance
- Test server startup/shutdown

**Error handling:**
- Task loop must handle MCP server failures
- Server should return structured errors in tool results
- Implement timeout for long-running skill sessions
- Log stdio communication for debugging

## Alignment with Figure 1

- **Task Generator** → `ace-task.py` with task-generator agent
- **Skill Generator** → `ace-skill.py` generate_skill tool with skill-generator agent
- **Task Curator** → Task loop playbook management with task-curator agent
- **Skill Curator** → Skill server delta extraction with skill-curator agent
- **Task Reflector** → Task validation with task-reflector agent
- **Skill Reflector** → Skill validation inside server with skill-reflector agent
- **Skill Insights** → Tool result deltas
- **Delta Playbook Items** → Playbook merge in task loop
- **TASK Trajectory** → Task loop message stream
- **SKILL Trajectory** → Skill server message stream (returned in tool result metadata)
- **Bidirectional flow** → MCP tool call (task→skill) + tool result (skill→task)

This pure MCP server architecture provides maximum isolation and clean separation of concerns at the cost of process management complexity.
