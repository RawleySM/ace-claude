#!/usr/bin/env python3
"""CLI entry point for ACE Skills Session Inspector.

Usage:
    python ace_tools/skills_inspector.py <transcript.jsonl>
    python -m ace_tools.skills_inspector <transcript.jsonl>

    # Or if installed as a package:
    skills-inspector <transcript.jsonl>
"""

from __future__ import annotations

import sys
from pathlib import Path

def main() -> None:
    """Main CLI entry point."""
    from .inspector_ui import main as ui_main

    # Pass through to inspector_ui main
    ui_main()

if __name__ == "__main__":
    main()
