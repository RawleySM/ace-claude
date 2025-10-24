# Spec: ACE Skills Sub-loop with Claude-Agent-SDK Single-File Scripts

## Overview anchored to Figure 1
The skills loop in Figure 1 adds a bidirectional Claude Code detour between the Task Generator, Skill Reflector, and Delta Playbook. We will realize that detour with two single-file uv-compatible Python scripts that lean directly on the Claude-Agent-SDK:

- `ace-task/ace-task.py` – orchestrates the full TASK loop, imports `ace_skill` as a module, streams trajectory state, and reconciles delta playbook items.
- `ace-skill/ace-skill.py` – exports reusable helpers for loading Skills assets (subagents, slash commands, MCP servers) and running the SKILL loop. This module is imported by `ace-task.py` and mirrors the “Skill Generator → Skill Reflector” portion of the diagram.

Each script lives in its own project subtree with a `.claude` directory that matches the SDK’s documented layout:

```
ace-task/
  ace-task.py
  .claude/
    agents/
    commands/
ace-skill/
  ace-skill.py
  .claude/
    agents/
    commands/
```

Both programs must load subagent and slash-command assets from their local `.claude` folders at runtime so that Task runs can mount project-specific behaviors exactly as described in the [Subagents](https://docs.claude.com/en/api/agent-sdk/subagents) and [Slash Commands](https://docs.claude.com/en/api/agent-sdk/slash-commands) documentation.

## Claude-Agent-SDK touchpoints and documentation references
The specification binds every moving part to SDK primitives shown in the official examples repository:

- **Streaming TASK loop** – Use `ClaudeSDKClient` to maintain the bi-directional exchange in the TASK Query → TASK Trajectory path. The streaming helper is documented in `examples/streaming_mode.py`:
  ```python
  async with ClaudeSDKClient() as client:
      print("User: What is 2+2?")
      await client.query("What is 2+2?")

      async for msg in client.receive_response():
          display_message(msg)
  ```
  (`examples/streaming_mode.py`, lines 53-60)

- **Custom agent registry** – Load `.claude/agents/*.json|*.yaml` files into `AgentDefinition` objects passed through `ClaudeAgentOptions.agents`, matching `examples/agents.py`:
  ```python
  options = ClaudeAgentOptions(
      agents={
          "analyzer": AgentDefinition(
              description="Analyzes code structure and patterns",
              prompt="You are a code analyzer. Examine code structure, patterns, and architecture.",
              tools=["Read", "Grep", "Glob"],
          ),
          "tester": AgentDefinition(
              description="Creates and runs tests",
              prompt="You are a testing expert. Write comprehensive tests and ensure code quality.",
              tools=["Read", "Write", "Bash"],
              model="sonnet",
          ),
      },
      setting_sources=["user", "project"],
  )
  ```
  (`examples/agents.py`, lines 84-101)

- **Slash command discovery** – Respect the `.claude/commands` directory and surfacing through `setting_sources`, demonstrated in `examples/setting_sources.py`:
  ```python
  options = ClaudeAgentOptions(
      setting_sources=["user", "project"],
      cwd=sdk_dir,
  )

  async with ClaudeSDKClient(options=options) as client:
      await client.query("What is 2 + 2?")

      async for msg in client.receive_response():
          if isinstance(msg, SystemMessage) and msg.subtype == "init":
              commands = extract_slash_commands(msg)
              print(f"Available slash commands: {commands}")
              if "commit" in commands:
                  print("✓ /commit is available (expected)")
              break
  ```
  (`examples/setting_sources.py`, lines 73-99)

- **In-process MCP servers** – Wrap skill tools with the documented `@tool` decorator and `create_sdk_mcp_server`, paralleling `examples/mcp_calculator.py` so that `ace-skill.py` can expose domain-specific skills:
  ```python
  from claude_agent_sdk import (
      ClaudeAgentOptions,
      create_sdk_mcp_server,
      tool,
  )

  @tool("add", "Add two numbers", {"a": float, "b": float})
  async def add_numbers(args: dict[str, Any]) -> dict[str, Any]:
      result = args["a"] + args["b"]
      return {
          "content": [{"type": "text", "text": f"{args['a']} + {args['b']} = {result}"}]
      }
  ```
  (`examples/mcp_calculator.py`, lines 12-31)

- **Hook instrumentation for the skill reflector** – Mirror Figure 1’s “Skill Reflector” node by installing SDK hooks via `ClaudeAgentOptions.hooks` the way `examples/hooks.py` blocks commands and annotates tool runs:
  ```python
  async def check_bash_command(
      input_data: HookInput, tool_use_id: str | None, context: HookContext
  ) -> HookJSONOutput:
      """Prevent certain bash commands from being executed."""
      tool_name = input_data["tool_name"]
      tool_input = input_data["tool_input"]

      if tool_name != "Bash":
          return {}

      command = tool_input.get("command", "")
      block_patterns = ["foo.sh"]

      for pattern in block_patterns:
          if pattern in command:
              logger.warning(f"Blocked command: {command}")
              return {
                  "hookSpecificOutput": {
                      "hookEventName": "PreToolUse",
                      "permissionDecision": "deny",
                      "permissionDecisionReason": f"Command contains invalid pattern: {pattern}",
                  }
              }

      return {}
  ```
  (`examples/hooks.py`, lines 35-60)

- **Result aggregation** – Capture `AssistantMessage`, `ToolUseBlock`, `ToolResultBlock`, and `ResultMessage` instances in the TASK trajectory, aligning with the delta playbook overlays shown in the diagram and the `display_message` helpers in the SDK examples.

## Responsibilities and interactions

### ace-skill/ace-skill.py (module)
1. **Configuration loaders**
   - `load_subagents(root: Path) -> dict[str, AgentDefinition]`: parse `.claude/agents` files (JSON/YAML) into `AgentDefinition` objects.
   - `load_commands(root: Path) -> list[Path]`: enumerate `.claude/commands/*.md` for logging and validation; command bodies are executed by Claude Code via the SDK when `setting_sources` includes `"project"`.
   - `load_mcp_servers(root: Path) -> dict[str, McpSdkServerConfig]`: register optional MCP servers (exposed via `create_sdk_mcp_server`) per documentation.

2. **Skill loop primitives**
   - `class SkillLoop`: wraps `ClaudeSDKClient` lifecycle for SKILL requests. Constructor accepts `ClaudeAgentOptions`, optional hooks, and Delta Playbook context. Methods:
     - `async def run_skill_session(self, prompt: str, trajectory_id: str) -> AsyncIterator[Message]`: streams messages, yields `Message` instances for the TASK loop to record, and forwards tool hooks to the reflector step.
     - `async def invoke_tools(...)`: optional helper to call `client.query` on behalf of `ace-task` when the diagram’s Skill Generator is invoked.

3. **Delta extraction helpers**
   - `summarize_skill_session(messages: list[Message]) -> dict`: collapse `ToolUseBlock`/`ToolResultBlock` pairs into structured delta items consumed by the Task Curator.

### ace-task/ace-task.py (script)
1. **Playbook-driven orchestration**
   - Bootstraps `ClaudeAgentOptions` with:
     - `.agents` from `ace_skill.load_subagents(Path(__file__).parent)`
     - `.mcp_servers` from `ace_skill.load_mcp_servers(...)`
     - `.setting_sources=["project"]` so `.claude/commands` resolve per `examples/setting_sources.py`.
   - Registers hooks for reflection (e.g., permission gating) via `ace_skill.build_hooks()` returning `HookMatcher` maps similar to `examples/hooks.py`.

2. **TASK loop alignment**
   - `async def run_task(task_prompt: str)`: enters `SkillLoop.run_skill_session`, consumes messages, appends them to ACE’s TASK trajectory log, and feeds them into the “Skill Reflector” sub-loop from Figure 1.
   - Integrates delta output with the Playbook store: accepted deltas update the Delta Playbook Items component shown in the diagram.

3. **Slash-command echoing**
   - After each session, call `client.get_server_info()` to enumerate `commands` and annotate the trajectory with available slash commands. This is required so the “SKILL Insights” bubble in Figure 1 always reflects local `.claude/commands` state.

4. **Skill inspector hand-off**
   - Provide CLI arguments for exporting transcripts (JSONL) that include `Message.model_dump()` payloads for later inspection, matching the diagram’s “Content Playbook” and “Delta Playbook” reconciliation needs.

## Data flow derived from Figure 1
1. **Task Query** – `run_task()` receives a task stub, composes a SKILL prompt (task prompt + playbook context), and initializes `SkillLoop` with generator metadata.
2. **Skill Generator/Reflector** – `SkillLoop` streams messages and triggers hook callbacks. Hook decisions (allow/deny) become Skill Reflector output in the diagram.
3. **Skill Insights** – `summarize_skill_session` emits structured deltas: clarifications, references, and runbooks. These align with the Delta Playbook Items in Figure 1.
4. **Delta Feedback** – `ace-task.py` persists accepted deltas back into the Playbook store and optionally updates context summary before the next TASK iteration.
5. **Trajectory Logging** – Both scripts write transcripts capturing `AssistantMessage`, `ToolUseBlock`, and `ResultMessage` records that the diagram labels “TASK Trajectory” and “SKILL Trajectory.”

## Implementation considerations
- **uv single-file constraint** – Both Python scripts must run as standalone uv entry points; keep dependencies limited to Claude-Agent-SDK, anyio, and stdlib modules.
- **Configuration precedence** – When both `.claude` directories exist, `ace-task.py` should treat its local assets as the canonical set, while `ace-skill.py` acts as a module that can be reused elsewhere.
- **Extensibility** – Hooks should capture `HookEvent.SubagentStop` for subagent tracing and `HookEvent.ToolStart/ToolFinish` for tool metrics, aligning with Figure 1’s Skill Reflector loop.
- **Testing** – Provide dry-run mode that instantiates `SkillLoop` with a fake `Transport` (see `ClaudeSDKClient` constructor) so unit tests can simulate trajectories without hitting the live CLI.

This spec grounds every step of the ACE skills detour in the officially documented Claude-Agent-SDK constructs while respecting the diagram’s architecture and the requirement for directory-scoped subagents and slash commands.
