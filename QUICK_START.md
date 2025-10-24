# Quick Start Guide: ACE Claude UI Execute Tab

## What's New?

The ACE Claude Inspector now has an **Execute** tab that lets you submit tasks directly from the UI!

## Installation (First Time Only)

```bash
cd /home/rawleysm/dev/ace-claude

# Install dependencies
pip install -r ace_tools/requirements.txt
```

## Usage

### Launch the UI

```bash
# Start with empty session list
python -m ace_tools.inspector_ui

# Or start with existing transcripts
python -m ace_tools.inspector_ui docs/transcripts/*.jsonl
```

### Execute a Task

1. **Press `n`** to open the Execute tab (or it's the first tab by default)

2. **Enter your task** in the text area:
   ```
   Example: "Analyze the codebase and create a README"
   ```

3. **Verify playbook path** (default: `playbook.json`)

4. **Click "Execute Task"** or Tab+Enter

5. **Watch live output** in the log panel

6. **Review results** - UI automatically switches to Timeline tab when complete

### Keyboard Shortcuts

- `n` - New task (open Execute tab)
- `←` / `→` - Switch tabs
- `h` / `l` - Switch tabs (vim-style)
- `s` - Toggle slash command filter
- `e` - Export skill
- `q` - Quit

## Example Session

```
┌─────────────────────────────────────────────────────┐
│ ACE Skill Inspector                                 │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Task Description:                                  │
│  ┌─────────────────────────────────────────────┐   │
│  │ Create a new authentication module          │   │
│  │ with JWT token support                      │   │
│  │                                             │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  Playbook Path:                                     │
│  [playbook.json                            ]        │
│                                                     │
│  [Execute Task]                                     │
│                                                     │
│  Status: Running - Task in progress...              │
│                                                     │
│  Execution Output:                                  │
│  ┌─────────────────────────────────────────────┐   │
│  │ 12:34:56 - Starting task execution...       │   │
│  │ 12:34:57 - Loading playbook version 5       │   │
│  │ 12:34:58 - Executing task loop...           │   │
│  │ 12:35:02 - Tool invoked: Read               │   │
│  │ 12:35:03 - Escalating to skill loop         │   │
│  │ 12:35:10 - Skill generation complete        │   │
│  │ 12:35:11 - Task completed successfully!     │   │
│  └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

## What Happens Behind the Scenes?

1. **Transcript Capture**: Every execution saves a detailed transcript to:
   ```
   docs/transcripts/session_20241024_123456.jsonl
   ```

2. **Playbook Updates**: Your `playbook.json` is automatically updated with:
   - New skills discovered
   - Constraints learned
   - References captured

3. **Automatic Analysis**: After execution:
   - Transcript is loaded as a new session
   - Timeline view shows all tool calls
   - Context view shows playbook updates
   - Skill Detail view shows tool parameters/results

## Troubleshooting

### "Module not found" errors
```bash
# Make sure dependencies are installed
pip install -r ace_tools/requirements.txt
```

### UI doesn't start
```bash
# Check Python version (need 3.10+)
python3 --version

# Try with explicit python3
python3 -m ace_tools.inspector_ui
```

### Execution hangs
- Check if ace-task.py and ace-skill directories exist
- Verify playbook.json is valid JSON
- Check logs in execution output panel

### Can't find playbook.json
```bash
# Create a minimal playbook
echo '{"items": [], "version": 1, "token_budget": 2000}' > playbook.json
```

## Next Steps

After executing a task:

1. **Review Timeline** - See chronological flow of events
2. **Check Context** - View playbook updates and metadata
3. **Inspect Skills** - Examine tool calls in detail
4. **Export Skills** - Save useful patterns for reuse
5. **Execute Again** - Press `n` for a new task

## Tips & Tricks

- **Multiline Tasks**: The text area supports multiple lines - great for detailed instructions
- **Playbook Paths**: Can be absolute or relative paths
- **Live Monitoring**: Watch the execution log for real-time progress
- **Quick Navigation**: Use `n` to quickly start new tasks
- **Session History**: All executions are saved in `docs/transcripts/`

## Advanced Usage

### Custom Playbook Location
Edit the playbook path field before executing:
```
/path/to/my/custom_playbook.json
```

### Review Multiple Executions
```bash
# Load all your past sessions
python -m ace_tools.inspector_ui docs/transcripts/*.jsonl
```

### Extract Patterns
1. Execute task
2. Switch to Skill Detail tab
3. Navigate through outcomes
4. Add curator annotations
5. Export promising skills

## Getting Help

- View full documentation: `IMPLEMENTATION_SUMMARY.md`
- Check API reference: `ace_tools/EXECUTE_VIEW_README.md`
- Report issues: Create an issue in the repository

---

**Happy Task Executing! 🚀**
