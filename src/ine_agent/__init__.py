"""ine-agent: a small autonomous supervisor for the Ine repository.

Developer tooling for this repository. Not part of the Ine language.
It reads the persistent .agent/ control-plane files, decides whether
executable work exists per the PLAN selection rule, and drives a worker
CLI (OpenCode by default) through the project's own workflow.
"""

__version__ = "0.1.0"