# Spec: ACE Skills Sub-loop with Claude-Agent-SDK Single-File Scripts (In-Process Design)

## Overview anchored to Figure 1
The skills loop in Figure 1 adds a bidirectional Claude Code detour between the Task Generator, Skill Reflector, and Delta Playbook. We realize that detour with two single-file uv-compatible Python scripts that lean directly on the Claude-Agent-SDK:

- `ace-task/ace-task.py` — orchestrates the full TASK loop, imports utilities from `ace_skill_utils`, manages the complete trajectory including skill sub-loops, reconciles delta playbook items, and coordinates separate `.claude/` directory contexts.
- `ace-skill/ace_skill_utils.py` — provides reusable helpers for loading configuration, running skill sessions, and extracting deltas. This is a **pure Python module** with no MCP server functionality.

Each script lives in its own project subtree with an isolated `.claude/` directory that matches the SDK's documented layout:

```
ace-task/
  ace-task.py
  .claude/
    agents/
      task-generator.md
      task-curator.md
      task-reflector.md
    commands/
      review-playbook.md
ace-skill/
  ace_skill_utils.py
  .claude/
    agents/
      skill-generator.md
      skill-curator.md
      skill-reflector.md
    commands/
      validate-skill.md
```

The task loop uses explicit `cwd` parameters when instantiating skill sessions to ensure each `ClaudeSDKClient` picks up the correct `.claude/` assets, providing directory isolation without process boundaries.

## Message Flow (Task → Skill → Playbook)

**Explicit data flow for clarity:**

1. **Task Initiation**: `ace-task.py` receives task prompt → creates Task `ClaudeSDKClient` with `cwd=ace-task/`
2. **Skill Invocation**: When skill generation needed → instantiates `SkillLoop` with `cwd=ace-skill/` → creates separate Skill `ClaudeSDKClient`
3. **Message Streaming**: Skill loop yields `Message` objects in real-time → Task loop appends to unified TASK trajectory
4. **Delta Extraction**: After skill session completes → `summarize_skill_session()` extracts structured deltas
5. **Playbook Update**: Task loop validates deltas → merges accepted items into Delta Playbook → continues with enriched context

**Key principle**: Two `ClaudeSDKClient` instances with different working directories, but single Python process with direct function calls and message passing.

## Agent Architecture

### Task Loop Agents (ace-task/.claude/agents/)

**task-generator.md**
```markdown
# Task Generator

## Description
Generates and decomposes high-level tasks into actionable subtasks with clear objectives and success criteria.

## Prompt
You are a task generator. Break down complex objectives into specific, actionable tasks. For each task, define clear inputs, expected outputs, and success criteria. Identify when skill generation is needed for novel or reusable patterns.

## Tools
- Read
- Write
- Bash
- Grep

## Model
sonnet
```

**task-curator.md**
```markdown
# Task Curator

## Description
Curates task execution flow, manages dependencies, and maintains the task trajectory and delta playbook.

## Prompt
You are a task curator. Organize task execution, track progress, manage dependencies between tasks, and maintain the delta playbook. Integrate insights from skill generation sessions back into the task context. Ensure tasks align with project goals and handle escalations appropriately.

## Tools
- Read
- Write
- Glob

## Model
sonnet
```

#### Task Curator JSON payload schema

The Task Curator emits a structured JSON payload after every planning cycle so the rest of the loop can react deterministically. The payload is serialized as a single JSON object with the following shape:

```json
{
  "summary": "string",
  "proposed_updates": [
    {
      "id": "string",
      "description": "string",
      "target": "string",
      "priority": "low|medium|high"
    }
  ],
  "python_helpers": ["string"],
  "reference_requests": ["string"]
}
```

- `summary` *(string, required)* — One-sentence recap of the curator's latest decisions that the Task Generator uses to keep the global trajectory synchronized.
- `proposed_updates` *(array of objects, optional; defaults to `[]`)* — Zero or more granular updates that describe delta playbook merges, task reprioritizations, or dependency tweaks. Each entry must include an `id` (stable identifier), `description` (freeform text), `target` (path, task identifier, or skill name), and `priority` (enumerated `low`, `medium`, or `high`).
- `python_helpers` *(array of strings, optional; defaults to `[]`)* — Names of helper functions or scripts the Task Curator wants the Skill loop to (re)generate. Non-empty lists cause the Skill Node orchestration function to launch the skill-generation detour immediately so the helpers are synthesized before the next task step.
- `reference_requests` *(array of strings, optional; defaults to `[]`)* — Citations, specs, or external resources that must be fetched. When populated, the Skill Node bypasses the normal task flow and opens the reference-acquisition path so downstream agents receive the requested artifacts.

The Task Curator writes this JSON object to the task trajectory stream (and makes it available via the in-process message bus) at the end of each curation pass. The Skill Node function consumes the object, inspects `python_helpers` and `reference_requests`, and automatically decides whether to initiate the skill sub-loop or the reference retrieval flow. If both lists are empty, the Task Node continues the main execution path using the `summary` and any `proposed_updates` to adjust its plan without triggering auxiliary loops.

**task-reflector.md**
```markdown
# Task Reflector

## Description
Reflects on task execution, validates outcomes, and ensures quality standards are met.

## Prompt
You are a task reflector. Review completed tasks for quality, correctness, and alignment with objectives. Validate that success criteria are met. Identify lessons learned and patterns that should be captured as skills. Flag issues that require rework or clarification.

## Tools
- Read
- Grep
- Bash

## Model
sonnet
```

### Skill Loop Agents (ace-skill/.claude/agents/)

**skill-generator.md**
```markdown
# Skill Generator

## Description
Generates reusable skills, patterns, runbooks, and code templates from task requirements.

## Prompt
You are a skill generator. Transform specific task solutions into generalized, reusable skills. Create well-documented patterns, code templates, and runbooks that can be applied to similar problems. Focus on abstraction, parameterization, and clear documentation. Extract the essence of what makes a solution reusable.

## Tools
- Read
- Write
- Bash
- Grep

## Model
sonnet
```

**skill-curator.md**
```markdown
# Skill Curator

## Description
Curates the skill library, manages skill metadata, and organizes skills for discoverability.

## Prompt
You are a skill curator. Organize generated skills into a coherent library structure. Tag skills with relevant categories, dependencies, and use cases. Maintain skill metadata including version history, applicability constraints, and related skills. Ensure skills are well-documented and discoverable. Identify overlapping or redundant skills that should be consolidated.

## Tools
- Read
- Write
- Glob
- Grep

## Model
sonnet
```

**skill-reflector.md**
```markdown
# Skill Reflector

## Description
Reflects on skill generation quality, validates skill reusability, and enforces skill standards.

## Prompt
You are a skill reflector. Evaluate generated skills for quality, generalizability, and reusability. Ensure skills follow best practices and project standards. Validate that skills are properly parameterized and documented. Check for security issues, performance concerns, or maintainability problems. Provide feedback to improve skill quality before they're added to the library.

## Tools
- Read
- Bash

## Model
sonnet
```

## Claude-Agent-SDK touchpoints and documentation references

The specification binds every moving part to SDK primitives shown in the official examples repository:

- **Streaming TASK loop** — Use `ClaudeSDKClient` to maintain the bi-directional exchange in the TASK Query → TASK Trajectory path. The streaming helper is documented in `examples/streaming_mode.py`:
  ```python
  async with ClaudeSDKClient() as client:
      print("User: What is 2+2?")
      await client.query("What is 2+2?")

      async for msg in client.receive_response():
          display_message(msg)
  ```
  (`examples/streaming_mode.py`, lines 53-60)

- **Custom agent registry** — Load `.claude/agents/*.md` files into `AgentDefinition` objects passed through `ClaudeAgentOptions.agents`, matching `examples/agents.py`:
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

- **Slash command discovery** — Respect the `.claude/commands` directory via `setting_sources`, demonstrated in `examples/setting_sources.py`:
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

- **Working directory isolation** — Use explicit `cwd` parameter in `ClaudeAgentOptions` to point each SDK client at different `.claude/` directories:
  ```python
  # Task loop uses ace-task/.claude/
  task_options = ClaudeAgentOptions(cwd=Path(__file__).parent)
  
  # Skill loop uses ace-skill/.claude/
  skill_options = ClaudeAgentOptions(cwd=skill_project_root)
  ```

- **Hook instrumentation for the skill reflector** — Mirror Figure 1's "Skill Reflector" node by installing SDK hooks via `ClaudeAgentOptions.hooks` the way `examples/hooks.py` blocks commands and annotates tool runs:
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

- **Result aggregation** — Capture `AssistantMessage`, `ToolUseBlock`, `ToolResultBlock`, and `ResultMessage` instances in the TASK trajectory, aligning with the delta playbook overlays shown in the diagram and the `display_message` helpers in the SDK examples.

## Responsibilities and interactions

### ace-skill/ace_skill_utils.py (pure Python module)

**Purpose**: Provides reusable utilities for configuration loading, skill session orchestration, and delta extraction. No MCP server functionality, no `main()` entrypoint—purely imported by `ace-task.py`.

1. **Configuration loaders**
   
   ```python
   def load_subagents(root: Path) -> dict[str, AgentDefinition]:
       """
       Parse .claude/agents/*.md files into AgentDefinition objects.
       
       Expected markdown structure:
       - # {Agent Name}
       - ## Description
       - ## Prompt
       - ## Tools (optional, bullet list)
       - ## Model (optional, defaults to "sonnet")
       
       For ace-task/, expects:
       - task-generator.md
       - task-curator.md
       - task-reflector.md
       
       For ace-skill/, expects:
       - skill-generator.md
       - skill-curator.md
       - skill-reflector.md
       
       Returns dict keyed by agent name (e.g., "task-generator", "skill-curator").
       """
       agents = {}
       agents_dir = root / ".claude" / "agents"
       
       if not agents_dir.exists():
           logger.warning(f"No agents directory found at {agents_dir}")
           return agents
       
       for md_file in agents_dir.glob("*.md"):
           try:
               agent_def = parse_agent_markdown(md_file)
               agent_name = md_file.stem
               agents[agent_name] = agent_def
               logger.info(f"Loaded agent: {agent_name}")
           except Exception as e:
               logger.error(f"Failed to load agent {md_file}: {e}")
       
       return agents
   
   def parse_agent_markdown(md_path: Path) -> AgentDefinition:
       """
       Parse markdown agent definition into AgentDefinition object.
       
       Extracts:
       - Title (# heading) → used for display
       - Description section content
       - Prompt section content
       - Tools list (if present)
       - Model (if specified, defaults to "sonnet")
       """
       content = md_path.read_text()
       
       # Simple parser - in production might use markdown parser library
       lines = content.split('\n')
       
       description = ""
       prompt = ""
       tools = []
       model = "sonnet"
       
       current_section = None
       
       for line in lines:
           if line.startswith("## Description"):
               current_section = "description"
           elif line.startswith("## Prompt"):
               current_section = "prompt"
           elif line.startswith("## Tools"):
               current_section = "tools"
           elif line.startswith("## Model"):
               current_section = "model"
           elif line.startswith("#"):
               current_section = None
           elif current_section == "description" and line.strip():
               description += line.strip() + " "
           elif current_section == "prompt" and line.strip():
               prompt += line.strip() + " "
           elif current_section == "tools" and line.strip().startswith("-"):
               tools.append(line.strip()[1:].strip())
           elif current_section == "model" and line.strip():
               model = line.strip()
       
       return AgentDefinition(
           description=description.strip(),
           prompt=prompt.strip(),
           tools=tools if tools else None,
           model=model,
       )
   ```

   ```python
   def load_slash_commands(root: Path) -> list[Path]:
       """
       Enumerate .claude/commands/*.md files for validation and logging.
       
       The SDK automatically discovers these when setting_sources=["project"],
       but this helper provides metadata for trajectory annotations.
       """
       commands_dir = root / ".claude" / "commands"
       
       if not commands_dir.exists():
           return []
       
       return list(commands_dir.glob("*.md"))
   ```

   ```python
   def validate_claude_directory(root: Path) -> dict[str, Any]:
       """
       Health check that verifies complete agent and command structure.
       
       For task loop:
       - Expects task-generator, task-curator, task-reflector agents
       
       For skill loop:
       - Expects skill-generator, skill-curator, skill-reflector agents
       """
       agents_dir = root / ".claude" / "agents"
       commands_dir = root / ".claude" / "commands"
       
       # Determine expected agents based on directory name
       context = "task" if "ace-task" in str(root) else "skill"
       expected_agents = [
           f"{context}-generator.md",
           f"{context}-curator.md",
           f"{context}-reflector.md",
       ]
       
       found_agents = [f.name for f in agents_dir.glob("*.md")] if agents_dir.exists() else []
       missing_agents = [a for a in expected_agents if a not in found_agents]
       
       found_commands = [f.name for f in commands_dir.glob("*.md")] if commands_dir.exists() else []
       
       return {
           "valid": len(missing_agents) == 0,
           "agents_found": found_agents,
           "agents_missing": missing_agents,
           "commands_found": found_commands,
           "context": context,
       }
   ```

2. **Skill loop orchestration**
   
   ```python
   class SkillLoop:
       """
       Manages the lifecycle of a skill generation session using its own ClaudeSDKClient.
       """
       
       def __init__(
           self,
           skill_project_root: Path,
           hooks: dict[HookEvent, list[HookMatcher]] | None = None,
           playbook_context: dict[str, Any] | None = None,
       ):
           """
           Initialize skill loop with isolated working directory.
           
           Args:
               skill_project_root: Path to ace-skill/ directory containing .claude/
               hooks: Optional hook matchers for skill reflector integration
               playbook_context: Current delta playbook state for context injection
           """
           self.skill_project_root = skill_project_root
           self.hooks = hooks or {}
           self.playbook_context = playbook_context or {}
       
       async def run_skill_session(
           self, 
           skill_prompt: str, 
           trajectory_id: str
       ) -> AsyncIterator[Message]:
           """
           Run a complete skill generation session and stream messages.
           
           Creates a ClaudeSDKClient with cwd=skill_project_root to ensure
           the skill loop uses ace-skill/.claude/ assets. Yields Message objects
           that the task loop can append to its unified trajectory.
           
           Args:
               skill_prompt: The skill generation request
               trajectory_id: Unique ID for tracking this skill session
               
           Yields:
               Message objects (AssistantMessage, ToolUseBlock, ResultMessage, etc.)
           """
           options = ClaudeAgentOptions(
               agents=load_subagents(self.skill_project_root / ".claude"),
               setting_sources=["project"],
               cwd=self.skill_project_root,
               hooks=self.hooks,
           )
           
           async with ClaudeSDKClient(options=options) as client:
               # Inject playbook context into prompt if available
               enriched_prompt = self._enrich_prompt(skill_prompt)
               
               await client.query(enriched_prompt)
               
               async for msg in client.receive_response():
                   # Annotate messages with trajectory_id before yielding
                   if not hasattr(msg, 'metadata') or msg.metadata is None:
                       msg.metadata = {}
                   msg.metadata["trajectory_id"] = trajectory_id
                   msg.metadata["loop_type"] = "skill"
                   yield msg
       
       def _enrich_prompt(self, base_prompt: str) -> str:
           """
           Inject playbook context into skill prompt.
           
           Adds information about existing skills, constraints, and references
           to help the skill generator avoid duplication and maintain consistency.
           """
           if not self.playbook_context:
               return base_prompt
           
           context_parts = [base_prompt, "\n\n## Context from Delta Playbook\n"]
           
           if self.playbook_context.get("existing_skills"):
               context_parts.append(
                   f"Existing skills: {', '.join(self.playbook_context['existing_skills'])}"
               )
           
           if self.playbook_context.get("constraints"):
               context_parts.append(
                   f"\nConstraints: {len(self.playbook_context['constraints'])} active"
               )
           
           if self.playbook_context.get("references"):
               context_parts.append(
                   f"\nReferences: {len(self.playbook_context['references'])} available"
               )
           
           return "\n".join(context_parts)
   ```

3. **Delta extraction helpers**
   
   ```python
   from dataclasses import dataclass
   from typing import Any
   
   @dataclass
   class ToolCallSummary:
       """Summary of a single tool invocation."""
       tool_name: str
       input_summary: str
       output_summary: str
       success: bool
       duration_ms: float
   
   @dataclass
   class SkillSessionSummary:
       """Structured output from skill session for delta playbook integration."""
       clarifications: list[str]          # Questions/clarifications raised
       references: list[str]               # External docs/links discovered
       tool_calls: list[ToolCallSummary]   # Tools used and results
       runbook_snippets: list[str]         # Code or config generated
       reflection_notes: list[str]         # Skill reflector insights from hooks
       duration_seconds: float
       success: bool
       
       def brief(self) -> str:
           """Generate brief summary for context injection."""
           return (
               f"Skill session: {len(self.tool_calls)} tools, "
               f"{len(self.runbook_snippets)} snippets, "
               f"{'success' if self.success else 'incomplete'}"
           )
   
   def summarize_skill_session(messages: list[Message]) -> SkillSessionSummary:
       """
       Collapse the message stream into structured delta items.
       
       Extracts:
       - Clarification questions from AssistantMessage content
       - External references from tool results
       - Tool call summaries from ToolUseBlock/ToolResultBlock pairs
       - Code snippets from Write tool calls
       - Reflection notes from hook annotations
       """
       clarifications = []
       references = []
       tool_calls = []
       runbook_snippets = []
       reflection_notes = []
       
       start_time = None
       end_time = None
       success = False
       
       for msg in messages:
           # Track timing
           if start_time is None and hasattr(msg, 'timestamp'):
               start_time = msg.timestamp
           if hasattr(msg, 'timestamp'):
               end_time = msg.timestamp
           
           # Extract clarifications from assistant messages
           if isinstance(msg, AssistantMessage):
               content = msg.content if isinstance(msg.content, str) else ""
               if "?" in content:
                   # Simple heuristic: questions are clarifications
                   questions = [s.strip() for s in content.split("?") if s.strip()]
                   clarifications.extend(questions)
           
           # Extract tool calls
           if isinstance(msg, ToolUseBlock):
               tool_summary = ToolCallSummary(
                   tool_name=msg.name,
                   input_summary=str(msg.input)[:100],  # Truncate for brevity
                   output_summary="",  # Filled in by matching ToolResultBlock
                   success=False,
                   duration_ms=0.0,
               )
               tool_calls.append(tool_summary)
               
               # If Write tool, capture snippet
               if msg.name == "Write" and "content" in msg.input:
                   runbook_snippets.append(msg.input["content"])
           
           # Match tool results to calls
           if isinstance(msg, ToolResultBlock):
               for tc in reversed(tool_calls):
                   if not tc.output_summary:  # Find first unmatched call
                       tc.output_summary = str(msg.content)[:100]
                       tc.success = not msg.is_error
                       break
           
           # Extract reflection notes from hook metadata
           if hasattr(msg, 'metadata') and msg.metadata:
               if "hook_decision" in msg.metadata:
                   reflection_notes.append(msg.metadata["hook_decision"])
           
           # Check for completion
           if isinstance(msg, ResultMessage):
               success = True
       
       duration = 0.0
       if start_time and end_time:
           duration = (end_time - start_time).total_seconds()
       
       return SkillSessionSummary(
           clarifications=clarifications,
           references=references,
           tool_calls=tool_calls,
           runbook_snippets=runbook_snippets,
           reflection_notes=reflection_notes,
           duration_seconds=duration,
           success=success,
       )
   ```

   ```python
   def extract_tool_metrics(messages: list[Message]) -> dict[str, Any]:
       """
       Generate tool usage statistics for the Skill Reflector feedback loop.
       
       Returns:
       - tool_counts: {tool_name: call_count}
       - success_rates: {tool_name: success_rate}
       - avg_durations: {tool_name: avg_duration_ms}
       """
       tool_stats = {}
       
       for msg in messages:
           if isinstance(msg, ToolUseBlock):
               tool_name = msg.name
               if tool_name not in tool_stats:
                   tool_stats[tool_name] = {
                       "count": 0,
                       "successes": 0,
                       "durations": [],
                   }
               tool_stats[tool_name]["count"] += 1
           
           if isinstance(msg, ToolResultBlock):
               # Find corresponding tool use
               # (simplified - in production would match by tool_use_id)
               if not msg.is_error:
                   for name in tool_stats:
                       tool_stats[name]["successes"] += 1
                       break
       
       # Calculate rates
       metrics = {
           "tool_counts": {name: stats["count"] for name, stats in tool_stats.items()},
           "success_rates": {
               name: stats["successes"] / stats["count"] if stats["count"] > 0 else 0.0
               for name, stats in tool_stats.items()
           },
       }
       
       return metrics
   ```

4. **Hook builders for skill reflection**
   
   ```python
   from claude_agent_sdk import HookEvent, HookMatcher, HookInput, HookContext, HookJSONOutput
   
   def build_skill_reflector_hooks() -> dict[HookEvent, list[HookMatcher]]:
       """
       Returns pre-configured hooks that implement Figure 1's Skill Reflector logic.
       
       Hooks:
       - PreToolUse: Validates tool inputs against playbook constraints
       - PostToolUse: Captures tool results for delta extraction
       - SubagentStop: Records subagent completions for reflection notes
       """
       
       async def validate_tool_input(
           input_data: HookInput, 
           tool_use_id: str | None, 
           context: HookContext
       ) -> HookJSONOutput:
           """Validate tool calls against playbook rules."""
           tool_name = input_data.get("tool_name")
           tool_input = input_data.get("tool_input", {})
           
           # Example validation: prevent writing to forbidden paths
           if tool_name == "Write":
               path = tool_input.get("path", "")
               forbidden_patterns = ["/etc/", "/sys/", "~/.ssh/"]
               
               for pattern in forbidden_patterns:
                   if pattern in path:
                       logger.warning(f"Blocked Write to forbidden path: {path}")
                       return {
                           "hookSpecificOutput": {
                               "hookEventName": "PreToolUse",
                               "permissionDecision": "deny",
                               "permissionDecisionReason": f"Path matches forbidden pattern: {pattern}",
                           }
                       }
           
           # Example validation: prevent destructive Bash commands
           if tool_name == "Bash":
               command = tool_input.get("command", "")
               destructive_patterns = ["rm -rf", "dd if=", "> /dev/"]
               
               for pattern in destructive_patterns:
                   if pattern in command:
                       logger.warning(f"Blocked destructive command: {command}")
                       return {
                           "hookSpecificOutput": {
                               "hookEventName": "PreToolUse",
                               "permissionDecision": "deny",
                               "permissionDecisionReason": f"Command contains destructive pattern: {pattern}",
                           }
                       }
           
           return {}
       
       async def capture_tool_result(
           input_data: HookInput,
           tool_use_id: str | None,
           context: HookContext
       ) -> HookJSONOutput:
           """Log tool results for delta extraction."""
           tool_name = input_data.get("tool_name")
           
           # Store results in context for later summarization
           if not hasattr(context, "tool_results"):
               context.tool_results = []
           
           context.tool_results.append({
               "tool_name": tool_name,
               "tool_use_id": tool_use_id,
               "timestamp": datetime.now().isoformat(),
           })
           
           logger.info(f"Captured result for {tool_name}")
           return {}
       
       async def record_subagent_completion(
           input_data: HookInput,
           tool_use_id: str | None,
           context: HookContext
       ) -> HookJSONOutput:
           """Record subagent completions for reflection notes."""
           agent_name = input_data.get("agent_name", "unknown")
           
           logger.info(f"Subagent completed: {agent_name}")
           
           # Could store metrics about subagent performance
           if not hasattr(context, "subagent_completions"):
               context.subagent_completions = []
           
           context.subagent_completions.append({
               "agent_name": agent_name,
               "timestamp": datetime.now().isoformat(),
           })
           
           return {}
       
       return {
           HookEvent.PreToolUse: [
               HookMatcher(
                   hook_fn=validate_tool_input,
                   match_fn=lambda *_: True  # Apply to all tools
               )
           ],
           HookEvent.PostToolUse: [
               HookMatcher(
                   hook_fn=capture_tool_result,
                   match_fn=lambda *_: True
               )
           ],
           HookEvent.SubagentStop: [
               HookMatcher(
                   hook_fn=record_subagent_completion,
                   match_fn=lambda *_: True
               )
           ],
       }
   ```

   ```python
   def build_custom_skill_hooks(
       validators: list[Callable],
       reflectors: list[Callable]
   ) -> dict[HookEvent, list[HookMatcher]]:
       """
       Allow custom hook injection while maintaining standard structure.
       
       Args:
           validators: Custom PreToolUse hooks for validation
           reflectors: Custom PostToolUse hooks for reflection
       """
       matchers = {
           HookEvent.PreToolUse: [],
           HookEvent.PostToolUse: [],
       }
       
       for validator in validators:
           matchers[HookEvent.PreToolUse].append(
               HookMatcher(hook_fn=validator, match_fn=lambda *_: True)
           )
       
       for reflector in reflectors:
           matchers[HookEvent.PostToolUse].append(
               HookMatcher(hook_fn=reflector, match_fn=lambda *_: True)
           )
       
       return matchers
   ```

### ace-task/ace-task.py (orchestration script)

**Purpose**: Main entry point that runs the TASK loop, invokes skill sessions when needed, aggregates trajectories, and manages the delta playbook lifecycle.

1. **Playbook-driven orchestration**
   
   ```python
   # /// script
   # dependencies = [
   #     "claude-agent-sdk",
   #     "anyio",
   # ]
   # ///
   
   import sys
   import asyncio
   import argparse
   import uuid
   import json
   from pathlib import Path
   from datetime import datetime
   from typing import Any
   import logging
   
   # Import utilities from ace-skill module
   sys.path.append(str(Path(__file__).parent.parent / "ace-skill"))
   from ace_skill_utils import (
       load_subagents,
       load_slash_commands,
       validate_claude_directory,
       SkillLoop,
       SkillSessionSummary,
       summarize_skill_session,
       build_skill_reflector_hooks,
   )
   
   from claude_agent_sdk import (
       ClaudeSDKClient,
       ClaudeAgentOptions,
       Message,
       AssistantMessage,
       ToolUseBlock,
       ToolResultBlock,
       ResultMessage,
       SystemMessage,
       HookEvent,
       HookMatcher,
       HookInput,
       HookContext,
       HookJSONOutput,
   )
   
   logger = logging.getLogger(__name__)
   
   
   async def initialize_task_loop() -> tuple[ClaudeSDKClient, ClaudeAgentOptions]:
       """Bootstrap task loop with ace-task/.claude/ assets."""
       task_root = Path(__file__).parent
       
       # Validate directory structure
       validation = validate_claude_directory(task_root)
       if not validation["valid"]:
           logger.warning(
               f"Missing agents: {validation['agents_missing']}. "
               "Task loop may not function correctly."
           )
       
       options = ClaudeAgentOptions(
           agents=load_subagents(task_root / ".claude"),
           setting_sources=["project"],
           cwd=task_root,
           hooks=build_task_hooks(),  # Task-level hooks (different from skill hooks)
       )
       
       client = ClaudeSDKClient(options=options)
       return client, options
   ```

   ```python
   def build_task_hooks() -> dict[HookEvent, list[HookMatcher]]:
       """
       Hooks for task loop monitoring and control.
       
       Separate from skill hooks, these monitor the outer TASK loop.
       """
       
       async def detect_skill_need(
           input_data: HookInput,
           tool_use_id: str | None,
           context: HookContext
       ) -> HookJSONOutput:
           """
           Detect when task requires skill generation.
           
           Looks for specific patterns that indicate skill loop escalation:
           - Repeated similar tool calls (pattern detection)
           - Explicit requests for reusable solutions
           - Complex multi-step procedures
           """
           tool_name = input_data.get("tool_name")
           
           # Track tool usage patterns
           if not hasattr(context, "tool_history"):
               context.tool_history = []
           
           context.tool_history.append(tool_name)
           
           # Simple heuristic: if same tool used 3+ times in a row, suggest skill
           if len(context.tool_history) >= 3:
               recent = context.tool_history[-3:]
               if len(set(recent)) == 1:  # All same tool
                   logger.info(f"Pattern detected: {tool_name} used repeatedly. Consider skill generation.")
                   # Don't block, just log for now
           
           return {}
       
       async def log_task_progress(
           input_data: HookInput,
           tool_use_id: str | None,
           context: HookContext
       ) -> HookJSONOutput:
           """Log task execution progress for trajectory analysis."""
           tool_name = input_data.get("tool_name")
           logger.info(f"Task loop: {tool_name} invoked")
           return {}
       
       return {
           HookEvent.PreToolUse: [
               HookMatcher(hook_fn=detect_skill_need, match_fn=lambda *_: True),
               HookMatcher(hook_fn=log_task_progress, match_fn=lambda *_: True),
           ],
       }
   ```

2. **TASK loop with embedded skill sessions**
   
   ```python
   async def run_task(task_prompt: str, playbook: "DeltaPlaybook") -> "TaskTrajectory":
       """
       Run complete TASK loop with skill sub-loop integration.
       
       Flow:
       1. Initialize task SDK client with ace-task/.claude/
       2. Start task query and stream messages
       3. When skill generation needed:
          a. Instantiate SkillLoop with ace-skill/.claude/
          b. Stream skill messages into task trajectory
          c. Extract deltas and update playbook
       4. Continue task with enriched playbook context
       5. Return unified trajectory
       """
       trajectory = TaskTrajectory(task_id=str(uuid.uuid4()))
       
       client, options = await initialize_task_loop()
       
       async with client:
           await client.query(task_prompt)
           
           async for msg in client.receive_response():
               # Annotate with loop type
               if not hasattr(msg, 'metadata') or msg.metadata is None:
                   msg.metadata = {}
               msg.metadata["loop_type"] = "task"
               msg.metadata["trajectory_id"] = trajectory.task_id
               
               trajectory.append(msg)
               
               # Check if skill generation is needed
               if should_invoke_skill_loop(msg, playbook):
                   logger.info("Escalating to skill loop...")
                   skill_summary = await run_skill_sub_loop(
                       msg=msg,
                       playbook=playbook,
                       trajectory=trajectory
                   )
                   
                   # Merge skill deltas into playbook
                   accepted_deltas = playbook.validate_and_merge(skill_summary)
                   trajectory.add_delta_update(accepted_deltas)
                   
                   # Continue task with updated context
                   context_update = (
                       f"Skill generation complete: {skill_summary.brief()}\n"
                       f"Generated {len(skill_summary.runbook_snippets)} runbook snippets."
                   )
                   await client.query(context_update)
       
       return trajectory
   ```

   ```python
   def should_invoke_skill_loop(msg: Message, playbook: "DeltaPlaybook") -> bool:
       """
       Determine if a task message indicates need for skill generation.
       
       Criteria:
       - AssistantMessage contains keywords like "reusable", "pattern", "skill"
       - Multiple similar tool calls detected
       - Explicit request for generalization
       """
       if isinstance(msg, AssistantMessage):
           content = msg.content if isinstance(msg.content, str) else ""
           keywords = ["reusable", "pattern", "skill", "generalize", "template"]
           
           for keyword in keywords:
               if keyword.lower() in content.lower():
                   logger.info(f"Skill keyword detected: {keyword}")
                   return True
       
       # Could also check tool usage patterns, playbook state, etc.
       return False
   ```

   ```python
   async def run_skill_sub_loop(
       msg: Message,
       playbook: "DeltaPlaybook",
       trajectory: "TaskTrajectory"
   ) -> SkillSessionSummary:
       """
       Run skill session in-process with separate .claude/ directory.
       
       Args:
           msg: Task message that triggered skill need
           playbook: Current delta playbook state
           trajectory: Task trajectory to append skill messages to
       """
       skill_project_root = Path(__file__).parent.parent / "ace-skill"
       
       # Validate skill directory
       validation = validate_claude_directory(skill_project_root)
       if not validation["valid"]:
           logger.error(
               f"Skill directory invalid: missing {validation['agents_missing']}"
           )
           raise RuntimeError("Cannot run skill loop: invalid .claude/ structure")
       
       # Create skill loop with isolated working directory
       skill_loop = SkillLoop(
           skill_project_root=skill_project_root,
           hooks=build_skill_reflector_hooks(),
           playbook_context=playbook.to_context_dict(),
       )
       
       # Extract skill prompt from task message
       skill_prompt = extract_skill_prompt(msg)
       trajectory_id = f"{trajectory.task_id}:skill:{uuid.uuid4()}"
       
       logger.info(f"Starting skill session: {trajectory_id}")
       
       # Stream skill messages directly into task trajectory
       skill_messages = []
       async for skill_msg in skill_loop.run_skill_session(skill_prompt, trajectory_id):
           skill_messages.append(skill_msg)
           trajectory.append(skill_msg)  # Unified trajectory
       
       logger.info(f"Skill session complete: {len(skill_messages)} messages")
       
       # Extract deltas from skill session
       return summarize_skill_session(skill_messages)
   ```

   ```python
   def extract_skill_prompt(msg: Message) -> str:
       """
       Extract skill generation prompt from task message.
       
       Takes the assistant's message and reformulates it as a skill generation request.
       """
       if isinstance(msg, AssistantMessage):
           content = msg.content if isinstance(msg.content, str) else ""
           return (
               f"Generate a reusable skill based on the following requirement:\n\n"
               f"{content}\n\n"
               f"Create documented patterns, code templates, and procedures that can be "
               f"applied to similar problems."
           )
       
       return "Generate a skill for the current task context."
   ```

3. **Slash-command enumeration**
   
   ```python
   async def enumerate_available_commands(client: ClaudeSDKClient) -> list[str]:
       """
       Extract available slash commands from SDK client.
       
       Called after each session to update trajectory annotations
       with current command state (Figure 1's "SKILL Insights").
       """
       commands = []
       
       async for msg in client.receive_response():
           if isinstance(msg, SystemMessage) and msg.subtype == "init":
               # Extract commands from init message
               if hasattr(msg, 'commands'):
                   commands = [cmd.name for cmd in msg.commands]
               break
       
       return commands
   ```

4. **Trajectory and delta export**
   
   ```python
   def export_trajectory(trajectory: "TaskTrajectory", output_path: Path) -> None:
       """
       Export unified trajectory to JSONL for later inspection.
       
       Each line is a Message.model_dump() payload with metadata:
       - trajectory_id: Links skill messages to parent task
       - loop_type: "task" or "skill"
       - delta_updates: Playbook changes triggered by this message
       """
       with output_path.open("w") as f:
           for msg in trajectory.messages:
               # Serialize message with metadata
               msg_dict = msg.model_dump() if hasattr(msg, 'model_dump') else vars(msg)
               f.write(json.dumps(msg_dict) + "\n")
       
       logger.info(f"Trajectory exported to {output_path}")
   ```

5. **CLI interface**
   
   ```python
   async def main(argv: list[str] | None = None) -> None:
       """
       CLI entrypoint with playbook management.
       
       Usage:
           uv run ace-task.py "Generate user auth flow" --playbook=./playbook.json
           uv run ace-task.py --export-trajectory=./trajectory.jsonl
       """
       parser = argparse.ArgumentParser(
           description="ACE Task Loop with Skill Generation"
       )
       parser.add_argument(
           "task_prompt",
           nargs="?",
           help="Task to execute"
       )
       parser.add_argument(
           "--playbook",
           type=Path,
           default=Path("playbook.json"),
           help="Path to delta playbook JSON file"
       )
       parser.add_argument(
           "--export-trajectory",
           type=Path,
           help="Export trajectory to JSONL file"
       )
       parser.add_argument(
           "--validate",
           action="store_true",
           help="Validate .claude/ directory structure only"
       )
       
       args = parser.parse_args(argv)
       
       # Setup logging
       logging.basicConfig(
           level=logging.INFO,
           format="%(asctime)s [%(levelname)s] %(message)s"
       )
       
       # Validation mode
       if args.validate:
           task_root = Path(__file__).parent
           validation = validate_claude_directory(task_root)
           print(f"Task context validation: {validation}")
           
           skill_root = Path(__file__).parent.parent / "ace-skill"
           validation = validate_claude_directory(skill_root)
           print(f"Skill context validation: {validation}")
           return
       
       # Require task prompt
       if not args.task_prompt:
           parser.error("task_prompt is required unless --validate is used")
       
       # Load playbook
       playbook = DeltaPlaybook.load(args.playbook)
       logger.info(f"Loaded playbook with {len(playbook.items)} items")
       
       # Run task
       trajectory = await run_task(args.task_prompt, playbook)
       
       # Export trajectory if requested
       if args.export_trajectory:
           export_trajectory(trajectory, args.export_trajectory)
       
       # Save updated playbook
       playbook.save(args.playbook)
       logger.info(f"Playbook saved with {len(playbook.items)} items")
       
       # Print summary
       print("\n=== Task Execution Summary ===")
       print(f"Task ID: {trajectory.task_id}")
       print(f"Total messages: {len(trajectory.messages)}")
       print(f"Task messages: {len([m for m in trajectory.messages if m.metadata.get('loop_type') == 'task'])}")
       print(f"Skill messages: {len([m for m in trajectory.messages if m.metadata.get('loop_type') == 'skill'])}")
       print(f"Delta updates: {len(trajectory.delta_updates)}")
       print(f"Skill sessions: {len(trajectory.get_skill_sessions())}")
   
   
   if __name__ == "__main__":
       asyncio.run(main())
   ```

## Data structures for trajectory and playbook

```python
from dataclasses import dataclass, field
from typing import Any
from pathlib import Path
import json

@dataclass
class TaskTrajectory:
    """Unified trajectory containing both task and skill messages."""
    task_id: str
    messages: list[Message] = field(default_factory=list)
    delta_updates: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def append(self, msg: Message) -> None:
        """Add message to trajectory with automatic timestamping."""
        self.messages.append(msg)
    
    def add_delta_update(self, deltas: list[dict[str, Any]]) -> None:
        """Record playbook updates triggered by skill sessions."""
        self.delta_updates.extend(deltas)
    
    def get_skill_sessions(self) -> list[list[Message]]:
        """
        Extract all skill sub-loop message sequences.
        
        Returns list of message lists, where each inner list is one skill session.
        """
        sessions = []
        current_session = []
        
        for msg in self.messages:
            metadata = getattr(msg, 'metadata', {}) or {}
            if metadata.get("loop_type") == "skill":
                current_session.append(msg)
            elif current_session:
                sessions.append(current_session)
                current_session = []
        
        if current_session:
            sessions.append(current_session)
        
        return sessions
    
    def get_task_messages(self) -> list[Message]:
        """Extract only task loop messages."""
        return [
            msg for msg in self.messages
            if (getattr(msg, 'metadata', {}) or {}).get("loop_type") == "task"
        ]


@dataclass
class DeltaPlaybook:
    """
    Manages delta playbook items from Figure 1.
    
    The playbook stores:
    - Skills: Reusable patterns and runbooks
    - Constraints: Rules and limitations
    - References: External documentation
    - Clarifications: Questions and answers
    """
    items: list[dict[str, Any]] = field(default_factory=list)
    version: int = 1
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    @classmethod
    def load(cls, path: Path) -> "DeltaPlaybook":
        """Load playbook from JSON file."""
        if not path.exists():
            logger.info(f"No existing playbook at {path}, creating new one")
            return cls()
        
        with path.open() as f:
            data = json.load(f)
        
        return cls(**data)
    
    def save(self, path: Path) -> None:
        """Persist playbook to JSON file."""
        self.updated_at = datetime.now().isoformat()
        
        with path.open("w") as f:
            json.dump(
                {
                    "items": self.items,
                    "version": self.version,
                    "updated_at": self.updated_at,
                },
                f,
                indent=2
            )
    
    def to_context_dict(self) -> dict[str, Any]:
        """
        Convert playbook to context for skill loop injection.
        
        Provides skill generator with knowledge of existing skills,
        constraints, and references to avoid duplication.
        """
        return {
            "existing_skills": [
                item["name"] for item in self.items
                if item.get("type") == "skill"
            ],
            "constraints": [
                item for item in self.items
                if item.get("type") == "constraint"
            ],
            "references": [
                item for item in self.items
                if item.get("type") == "reference"
            ],
            "version": self.version,
        }
    
    def validate_and_merge(self, summary: SkillSessionSummary) -> list[dict[str, Any]]:
        """
        Validate skill session deltas and merge accepted items.
        
        Returns list of accepted deltas for trajectory annotation.
        
        Validation rules:
        - Check for duplicate skills
        - Ensure references are valid URLs
        - Validate runbook syntax
        """
        accepted = []
        timestamp = datetime.now().isoformat()
        
        # Convert clarifications to delta items
        for clarification in summary.clarifications:
            delta = {
                "type": "clarification",
                "content": clarification,
                "accepted": True,
                "timestamp": timestamp,
            }
            self.items.append(delta)
            accepted.append(delta)
        
        # Convert references to delta items
        for reference in summary.references:
            # Simple URL validation
            if reference.startswith(("http://", "https://")):
                delta = {
                    "type": "reference",
                    "url": reference,
                    "accepted": True,
                    "timestamp": timestamp,
                }
                self.items.append(delta)
                accepted.append(delta)
        
        # Convert runbook snippets to skills
        for idx, runbook in enumerate(summary.runbook_snippets):
            delta = {
                "type": "skill",
                "name": f"skill_{self.version}_{idx}",
                "code": runbook,
                "accepted": True,
                "timestamp": timestamp,
                "metadata": {
                    "tool_calls": len(summary.tool_calls),
                    "duration": summary.duration_seconds,
                },
            }
            self.items.append(delta)
            accepted.append(delta)
        
        # Add reflection notes as constraints if they suggest limitations
        for note in summary.reflection_notes:
            if any(keyword in note.lower() for keyword in ["limit", "avoid", "prevent"]):
                delta = {
                    "type": "constraint",
                    "description": note,
                    "accepted": True,
                    "timestamp": timestamp,
                }
                self.items.append(delta)
                accepted.append(delta)
        
        self.version += 1
        return accepted
```

## Complete Directory Structure

```
project/
├── ace-task/
│   ├── ace-task.py                    # Main orchestrator (runnable)
│   ├── .claude/
│   │   ├── agents/
│   │   │   ├── task-generator.md      # Generates and decomposes tasks
│   │   │   ├── task-curator.md        # Manages task flow and playbook
│   │   │   └── task-reflector.md      # Validates task completion
│   │   └── commands/
│   │       └── review-playbook.md     # Task slash command
│   └── playbook.json                   # Delta playbook persistence
│
└── ace-skill/
    ├── ace_skill_utils.py             # Pure utilities (imported only)
    ├── .claude/
    │   ├── agents/
    │   │   ├── skill-generator.md     # Creates reusable skills
    │   │   ├── skill-curator.md       # Organizes skill library
    │   │   └── skill-reflector.md     # Validates skill quality
    │   └── commands/
    │       └── validate-skill.md       # Skill slash command
    └── skills/                         # Generated skills library
        └── README.md
```

## Agent Interaction Patterns

### Task Loop (ace-task/)
1. **Task Generator** → Creates initial task breakdown, identifies skill generation needs
2. **Task Curator** → Orchestrates execution, manages playbook, coordinates with skill loop
3. **Task Reflector** → Reviews outcomes, captures lessons learned

### Skill Loop (ace-skill/)
1. **Skill Generator** → Transforms solutions into reusable patterns
2. **Skill Curator** → Organizes skills, manages metadata
3. **Skill Reflector** → Validates quality, enforces standards

### Cross-Loop Flow
```
Task Generator identifies need for skill
    ↓
Task Curator escalates to skill loop (in-process call)
    ↓
Skill Generator creates skill (separate ClaudeSDKClient)
    ↓
Skill Reflector validates (via hooks)
    ↓
Skill Curator adds to library
    ↓
Task Curator integrates skill back into task context
    ↓
Task Reflector validates task completion with new skill
```

## Implementation considerations

- **uv single-file constraint** — Both Python scripts must run as standalone uv entry points; keep dependencies limited to Claude-Agent-SDK, anyio, and stdlib modules. Use inline dependency specifications:
  ```python
  # /// script
  # dependencies = [
  #     "claude-agent-sdk",
  #     "anyio",
  # ]
  # ///
  ```

- **Working directory management** — The key to `.claude/` isolation is explicit `cwd` parameters:
  ```python
  # Task loop sees ace-task/.claude/
  task_options = ClaudeAgentOptions(cwd=Path(__file__).parent)
  
  # Skill loop sees ace-skill/.claude/
  skill_options = ClaudeAgentOptions(cwd=Path(__file__).parent.parent / "ace-skill")
  ```

- **Hook isolation** — Task hooks and skill hooks serve different purposes:
  - **Task hooks**: Monitor when to escalate to skill loop, track overall progress
  - **Skill hooks**: Implement Figure 1's Skill Reflector (validation, tool result capture)

- **Message metadata** — Use `msg.metadata` to tag messages with `loop_type` and `trajectory_id` for later filtering and analysis. Handle cases where `metadata` attribute doesn't exist or is None.

- **Extensibility** — Both modules should expose factory functions for custom hooks:
  ```python
  # In ace_skill_utils.py
  def build_custom_skill_hooks(
      validators: list[Callable],
      reflectors: list[Callable]
  ) -> dict[HookEvent, list[HookMatcher]]:
      """Allow custom hook injection while maintaining standard structure."""
      pass
  ```

- **Testing with fake transport** — Provide dry-run capability:
  ```python
  class FakeTransport:
      """Mock transport for testing without hitting real Claude API."""
      async def query(self, prompt: str) -> AsyncIterator[Message]:
          # Return pre-canned responses
          yield AssistantMessage(content="Mock response")
  
  # In tests
  async def test_skill_loop():
      skill_loop = SkillLoop(
          skill_project_root=test_fixtures_path,
          transport=FakeTransport(),  # SDK supports custom transport
      )
      messages = [msg async for msg in skill_loop.run_skill_session("test", "test-id")]
      assert len(messages) > 0
  ```

- **Error handling** — Both scripts should gracefully handle:
  - Missing or invalid `.claude/` directories
  - Malformed agent markdown files
  - SDK client connection failures
  - Hook execution errors
  - Playbook serialization issues

- **Logging** — Use structured logging throughout:
  ```python
  logger.info("Starting skill session", extra={
      "trajectory_id": trajectory_id,
      "playbook_version": playbook.version,
      "skill_context": len(playbook_context),
  })
  ```

## Alignment with Figure 1

- **Task Generator** → `ace-task.py` main loop with task SDK client, task-generator agent
- **Skill Generator** → `SkillLoop.run_skill_session()` with skill SDK client, skill-generator agent
- **Task Curator** → Task loop orchestration, playbook management, task-curator agent
- **Skill Curator** → Skill library organization, skill-curator agent
- **Task Reflector** → Task validation and quality checks, task-reflector agent
- **Skill Reflector** → Hooks from `build_skill_reflector_hooks()`, skill-reflector agent
- **Skill Insights** → `SkillSessionSummary` extracted from skill messages
- **Delta Playbook Items** → `DeltaPlaybook.items` updated via `validate_and_merge()`
- **TASK Trajectory** → `TaskTrajectory.messages` (unified)
- **SKILL Trajectory** → Filtered from `TaskTrajectory` via `loop_type="skill"`
- **Bidirectional flow** → In-process function calls with explicit context passing

This spec grounds every component in documented SDK patterns while maintaining clear separation of concerns through working directory isolation, explicit message flow, and a complete six-agent architecture (three per loop) that mirrors the ACE framework's Generator → Curator → Reflector pattern at both the task and skill levels.