#!/usr/bin/env python3
"""Test script for Execute tab integration in inspector UI.

This script validates the integration without requiring full runtime dependencies.
"""

import ast
import sys
from pathlib import Path


def validate_syntax(file_path: Path) -> tuple[bool, str]:
    """Validate Python file syntax.

    Args:
        file_path: Path to Python file

    Returns:
        Tuple of (success, message)
    """
    try:
        with open(file_path) as f:
            content = f.read()
        ast.parse(content)
        return True, f"✓ {file_path.name}: Syntax valid"
    except SyntaxError as e:
        return False, f"✗ {file_path.name}: Syntax error at line {e.lineno}: {e.msg}"
    except Exception as e:
        return False, f"✗ {file_path.name}: Error: {e}"


def check_imports(file_path: Path) -> tuple[bool, str]:
    """Check if required imports are present.

    Args:
        file_path: Path to Python file

    Returns:
        Tuple of (success, message)
    """
    try:
        with open(file_path) as f:
            content = f.read()

        required_imports = {
            "inspector_ui.py": [
                "from .execute_view import ExecuteView, EXECUTE_VIEW_CSS",
                "ExecuteView()",
                "action_focus_execute_tab",
                "on_execute_view_execute_requested",
            ],
            "execute_view.py": [
                "class ExecuteView",
                "class ExecuteRequested",
                "EXECUTE_VIEW_CSS",
                "TextArea",
                "RichLog",
            ],
            "task_executor.py": [
                "class TaskExecutor",
                "class TaskExecutionResult",
                "execute_task",
                "progress_callback",
            ],
        }

        file_name = file_path.name
        if file_name not in required_imports:
            return True, f"  {file_name}: Skipped (not in checklist)"

        missing = []
        for pattern in required_imports[file_name]:
            if pattern not in content:
                missing.append(pattern)

        if missing:
            return False, f"✗ {file_name}: Missing: {', '.join(missing)}"
        return True, f"✓ {file_name}: All required components present"

    except Exception as e:
        return False, f"✗ {file_name}: Error: {e}"


def main():
    """Run validation checks."""
    root = Path(__file__).parent
    ace_tools = root / "ace_tools"

    files_to_check = [
        ace_tools / "inspector_ui.py",
        ace_tools / "execute_view.py",
        ace_tools / "task_executor.py",
    ]

    print("=" * 60)
    print("Integration Validation Report")
    print("=" * 60)
    print()

    # Syntax validation
    print("1. Syntax Validation")
    print("-" * 60)
    all_valid = True
    for file_path in files_to_check:
        if not file_path.exists():
            print(f"✗ {file_path.name}: File not found!")
            all_valid = False
            continue

        success, message = validate_syntax(file_path)
        print(f"  {message}")
        if not success:
            all_valid = False
    print()

    # Import/component checks
    print("2. Component Validation")
    print("-" * 60)
    for file_path in files_to_check:
        if not file_path.exists():
            continue
        success, message = check_imports(file_path)
        print(f"  {message}")
        if not success:
            all_valid = False
    print()

    # Integration checklist
    print("3. Integration Checklist")
    print("-" * 60)
    checklist = [
        ("ExecuteView widget created", (ace_tools / "execute_view.py").exists()),
        ("TaskExecutor wrapper created", (ace_tools / "task_executor.py").exists()),
        ("inspector_ui.py imports ExecuteView", check_file_contains(
            ace_tools / "inspector_ui.py",
            "from .execute_view import ExecuteView, EXECUTE_VIEW_CSS"
        )),
        ("Execute tab added to TabbedContent", check_file_contains(
            ace_tools / "inspector_ui.py",
            'TabPane("Execute"'
        )),
        ("ExecuteView instantiated", check_file_contains(
            ace_tools / "inspector_ui.py",
            "yield ExecuteView()"
        )),
        ("Keyboard binding added", check_file_contains(
            ace_tools / "inspector_ui.py",
            "focus_execute_tab"
        )),
        ("Event handler implemented", check_file_contains(
            ace_tools / "inspector_ui.py",
            "on_execute_view_execute_requested"
        )),
        ("CSS styling merged", check_file_contains(
            ace_tools / "inspector_ui.py",
            "EXECUTE_VIEW_CSS +"
        )),
    ]

    for description, passed in checklist:
        status = "✓" if passed else "✗"
        print(f"  {status} {description}")
        if not passed:
            all_valid = False
    print()

    # Summary
    print("=" * 60)
    if all_valid:
        print("✓ All validation checks passed!")
        print()
        print("Next steps:")
        print("  1. Install dependencies: pip install -r ace_tools/requirements.txt")
        print("  2. Run the inspector: python -m ace_tools.inspector_ui transcript.jsonl")
        print("  3. Press 'n' to open the Execute tab")
        print("  4. Enter a task and click 'Execute Task'")
        return 0
    else:
        print("✗ Some validation checks failed. Review errors above.")
        return 1


def check_file_contains(file_path: Path, pattern: str) -> bool:
    """Check if file contains a pattern.

    Args:
        file_path: Path to file
        pattern: Pattern to search for

    Returns:
        True if pattern found
    """
    if not file_path.exists():
        return False
    try:
        with open(file_path) as f:
            return pattern in f.read()
    except Exception:
        return False


if __name__ == "__main__":
    sys.exit(main())
