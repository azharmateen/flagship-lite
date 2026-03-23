"""Evaluate flags for a given context: enabled, percentage, targeting, environment."""

from __future__ import annotations

from typing import Any, Optional

from .flags import Flag
from .loader import load_flags


def evaluate_flag(
    flag_name: str,
    context: Optional[dict[str, Any]] = None,
    flags: Optional[list[Flag]] = None,
    flags_file: Optional[str] = None,
) -> tuple[bool, str]:
    """Evaluate a single flag for the given context.

    Args:
        flag_name: Name of the flag to evaluate.
        context: Evaluation context (user_id, email, environment, etc.).
        flags: Pre-loaded flags list. If None, loads from file.
        flags_file: Path to flags YAML file.

    Returns:
        Tuple of (is_enabled, reason_string).
    """
    if flags is None:
        flags = load_flags(flags_file)

    for flag in flags:
        if flag.name == flag_name:
            return flag.evaluate(context)

    return False, f"flag '{flag_name}' not found"


def evaluate_all(
    context: Optional[dict[str, Any]] = None,
    flags: Optional[list[Flag]] = None,
    flags_file: Optional[str] = None,
) -> dict[str, tuple[bool, str]]:
    """Evaluate all flags for the given context.

    Returns:
        Dict mapping flag name to (is_enabled, reason).
    """
    if flags is None:
        flags = load_flags(flags_file)

    return {flag.name: flag.evaluate(context) for flag in flags}


def get_enabled_flags(
    context: Optional[dict[str, Any]] = None,
    flags: Optional[list[Flag]] = None,
    flags_file: Optional[str] = None,
) -> list[str]:
    """Get list of flag names that are enabled for the given context."""
    results = evaluate_all(context, flags, flags_file)
    return [name for name, (enabled, _) in results.items() if enabled]
