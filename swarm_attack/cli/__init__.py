"""CLI package for swarm-attack.

This package provides the modular CLI architecture for swarm-attack:

Modules:
    app.py      - Main Typer app, version callback, sub-app registration
    feature.py  - Feature workflow commands (status, init, run, approve, etc.)
    bug.py      - Bug investigation commands (init, analyze, fix, etc.)
    admin.py    - Admin/recovery commands (cleanup, unlock, reset, diagnose, etc.)
    display.py  - Rich formatting utilities (format_phase, format_cost, etc.)
    common.py   - Shared helpers (get_console, get_project_dir, load_config_safe)

Command Structure:
    Commands are organized into sub-apps:
        swarm-attack feature status
        swarm-attack bug list
        swarm-attack admin diagnose

    Backwards-compatible aliases in cli_legacy.py allow old-style commands:
        swarm-attack status  →  swarm-attack feature status

Usage:
    from swarm_attack.cli import app, cli_main  # Main exports
    from swarm_attack.cli.display import format_phase, format_cost
    from swarm_attack.cli.common import get_console, get_project_dir
"""
from swarm_attack.cli.app import app, cli_main

__all__ = ["app", "cli_main"]
