"""Ine — a language for describing what, not how.

The package's own surface is the canonical formatter: `format_program`
takes .ine source and returns it in the one layout the language has.
Everything else — lexer, parser, semantics, backends — is reached through
its own module, because reaching it needs to be a deliberate act and
formatting does not.
"""

from .formatter import format_program

_version_ = "0.1.0"

__all__ = ["format_program"]
