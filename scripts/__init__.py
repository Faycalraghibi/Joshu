"""
Joshu Build Scripts

This package contains automation scripts for building, testing,
and releasing the Joshu CLI project.

Scripts:
    build.py              - Main build orchestrator
    build_package.py      - Individual package builder
    build_vscode_companion.py - VSCode extension builder
    clean.py              - Artifact cleanup
    copy_assets.py        - Asset bundling
    prepare_package.py    - Common file propagation
"""

from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent

__all__ = ["SCRIPTS_DIR", "PROJECT_ROOT"]
