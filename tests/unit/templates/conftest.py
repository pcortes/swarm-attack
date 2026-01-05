# tests/unit/templates/conftest.py
"""
Local conftest for template tests.

This file exists to provide isolation from the global conftest.py
which has import issues with swarm_attack.config.

Template tests don't need any SwarmConfig fixtures - they just
validate markdown files exist and have proper structure.
"""
