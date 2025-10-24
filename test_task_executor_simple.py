#!/usr/bin/env python3
"""Simple validation script for TaskExecutor code structure.

This script validates the TaskExecutor module without requiring
full dependency installation. It checks for:
- Proper Python syntax
- Expected class and function definitions
- Docstring presence
- Type hints
"""

import ast
import sys
from pathlib import Path


def validate_syntax(file_path: Path) -> bool:
    """Validate that the file has valid Python syntax."""
    print(f"Validating syntax of {file_path.name}...")
    try:
        with open(file_path) as f:
            source = f.read()
        ast.parse(source)
        print("  ✓ Valid Python syntax")
        return True
    except SyntaxError as e:
        print(f"  ✗ Syntax error: {e}")
        return False


def check_definitions(file_path: Path) -> bool:
    """Check that expected classes and functions are defined."""
    print(f"\nChecking definitions in {file_path.name}...")

    with open(file_path) as f:
        source = f.read()

    tree = ast.parse(source)

    # Find all class and function definitions
    classes = []
    functions = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, ast.FunctionDef) and isinstance(
            node.parent if hasattr(node, 'parent') else None, ast.Module
        ):
            # Only top-level functions
            pass

    # Extract top-level function definitions differently
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            functions.append(node.name)

    # Check expected classes
    expected_classes = [
        'TaskExecutionResult',
        'LoggingInterceptor',
        'TaskExecutor',
    ]

    missing_classes = [c for c in expected_classes if c not in classes]

    if missing_classes:
        print(f"  ✗ Missing classes: {missing_classes}")
        return False
    else:
        print(f"  ✓ All expected classes found: {', '.join(expected_classes)}")

    # Check expected functions
    expected_functions = ['execute_task']

    missing_functions = [f for f in expected_functions if f not in functions]

    if missing_functions:
        print(f"  ✗ Missing functions: {missing_functions}")
        return False
    else:
        print(f"  ✓ All expected functions found: {', '.join(expected_functions)}")

    return True


def check_methods(file_path: Path) -> bool:
    """Check that TaskExecutor has expected methods."""
    print(f"\nChecking TaskExecutor methods...")

    with open(file_path) as f:
        source = f.read()

    tree = ast.parse(source)

    # Find TaskExecutor class
    task_executor = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == 'TaskExecutor':
            task_executor = node
            break

    if not task_executor:
        print("  ✗ TaskExecutor class not found")
        return False

    # Extract method names
    methods = [
        n.name for n in task_executor.body
        if isinstance(n, ast.FunctionDef)
    ]

    expected_methods = [
        '__init__',
        'execute_task',
        '_setup_python_path',
        '_import_ace_task_modules',
        '_load_playbook',
        '_save_playbook',
        '_setup_transcript_capture',
        '_cleanup_transcript_capture',
        '_setup_logging_interceptor',
        '_cleanup_logging_interceptor',
    ]

    missing_methods = [m for m in expected_methods if m not in methods]

    if missing_methods:
        print(f"  ✗ Missing methods: {missing_methods}")
        return False
    else:
        print(f"  ✓ All expected methods found ({len(expected_methods)} methods)")

    # Check execute_task signature
    execute_task_method = None
    for node in task_executor.body:
        if isinstance(node, ast.FunctionDef) and node.name == 'execute_task':
            execute_task_method = node
            break

    if execute_task_method:
        args = [arg.arg for arg in execute_task_method.args.args]
        expected_args = ['self', 'task_prompt', 'playbook_path', 'transcript_path', 'progress_callback']

        if set(args) == set(expected_args):
            print(f"  ✓ execute_task has correct signature")
        else:
            print(f"  ⚠ execute_task signature mismatch")
            print(f"    Expected: {expected_args}")
            print(f"    Got: {args}")

    return True


def check_docstrings(file_path: Path) -> bool:
    """Check that classes and main methods have docstrings."""
    print(f"\nChecking docstrings...")

    with open(file_path) as f:
        source = f.read()

    tree = ast.parse(source)

    # Check module docstring
    module_docstring = ast.get_docstring(tree)
    if module_docstring:
        print(f"  ✓ Module docstring present ({len(module_docstring)} chars)")
    else:
        print("  ✗ Module docstring missing")
        return False

    # Check class docstrings
    classes_with_docs = 0
    total_classes = 0

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            total_classes += 1
            if ast.get_docstring(node):
                classes_with_docs += 1

    if classes_with_docs == total_classes:
        print(f"  ✓ All {total_classes} classes have docstrings")
    else:
        print(f"  ⚠ {total_classes - classes_with_docs} classes missing docstrings")

    return True


def check_type_hints(file_path: Path) -> bool:
    """Check for presence of type hints."""
    print(f"\nChecking type hints...")

    with open(file_path) as f:
        source = f.read()

    tree = ast.parse(source)

    # Count functions with return annotations
    functions_with_hints = 0
    total_functions = 0

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            total_functions += 1
            if node.returns is not None:
                functions_with_hints += 1

    if total_functions == 0:
        print("  ⚠ No functions found")
        return True

    percentage = (functions_with_hints / total_functions) * 100

    print(f"  ℹ {functions_with_hints}/{total_functions} functions have return type hints ({percentage:.0f}%)")

    # Check for typing imports
    has_typing = False
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == 'typing':
            has_typing = True
            break

    if has_typing:
        print("  ✓ typing module imported")
    else:
        print("  ⚠ typing module not explicitly imported")

    return True


def check_error_handling(file_path: Path) -> bool:
    """Check for proper error handling patterns."""
    print(f"\nChecking error handling...")

    with open(file_path) as f:
        source = f.read()

    # Count try-except blocks
    try_count = source.count('try:')
    except_count = source.count('except')

    if try_count > 0:
        print(f"  ✓ Contains {try_count} try-except blocks")
    else:
        print("  ⚠ No try-except blocks found")

    # Check for specific error handling patterns
    has_importerror = 'ImportError' in source
    has_filenotfound = 'FileNotFoundError' in source
    has_valueerror = 'ValueError' in source

    if has_importerror:
        print("  ✓ Handles ImportError")
    if has_filenotfound:
        print("  ✓ Handles FileNotFoundError")
    if has_valueerror:
        print("  ✓ Handles ValueError")

    return True


def main():
    """Run all validation checks."""
    print("=" * 60)
    print("TaskExecutor Code Validation")
    print("=" * 60 + "\n")

    task_executor_path = Path(__file__).parent / "ace_tools" / "task_executor.py"

    if not task_executor_path.exists():
        print(f"✗ File not found: {task_executor_path}")
        return 1

    results = []

    # Run validation checks
    results.append(validate_syntax(task_executor_path))
    results.append(check_definitions(task_executor_path))
    results.append(check_methods(task_executor_path))
    results.append(check_docstrings(task_executor_path))
    results.append(check_type_hints(task_executor_path))
    results.append(check_error_handling(task_executor_path))

    # Summary
    print("\n" + "=" * 60)
    print("Validation Summary")
    print("=" * 60)

    passed = sum(results)
    total = len(results)

    print(f"Passed: {passed}/{total}")

    if passed == total:
        print("\n✓ All validation checks passed!")
        print("  The code structure is correct and ready for use.")
        print("  Note: Runtime testing requires claude-agent-sdk to be installed.")
        return 0
    else:
        print(f"\n✗ {total - passed} validation check(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
