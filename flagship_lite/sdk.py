"""Python SDK: simple API for checking feature flags in application code."""

from __future__ import annotations

from typing import Any, Optional

from .flags import Flag
from .loader import FlagWatcher, find_flags_file


# Module-level watcher (lazy-initialized)
_watcher: Optional[FlagWatcher] = None


def _get_watcher() -> FlagWatcher:
    """Get or create the module-level flag watcher."""
    global _watcher
    if _watcher is None:
        flags_file = find_flags_file()
        if flags_file is None:
            raise FileNotFoundError(
                "No flags.yaml found. Run 'flagship-lite init' to create one."
            )
        _watcher = FlagWatcher(str(flags_file))
    return _watcher


def configure(flags_file: str) -> None:
    """Configure the SDK with a specific flags file path.

    Call this once at application startup:
        from flagship_lite import configure
        configure("/path/to/flags.yaml")
    """
    global _watcher
    _watcher = FlagWatcher(flags_file)


def flag_enabled(
    name: str,
    user_id: Optional[str] = None,
    email: Optional[str] = None,
    environment: Optional[str] = None,
    **extra_context: Any,
) -> bool:
    """Check if a feature flag is enabled.

    This is the primary SDK function. Use it in your application code:

        from flagship_lite import flag_enabled

        if flag_enabled("new_checkout", user_id="123"):
            show_new_checkout()
        else:
            show_old_checkout()

    Args:
        name: Flag name.
        user_id: User identifier (for percentage rollout).
        email: User email (for email-based targeting).
        environment: Current environment (production, staging, etc.).
        **extra_context: Additional context attributes for targeting rules.

    Returns:
        True if the flag is enabled for this context.
    """
    context: dict[str, Any] = {**extra_context}
    if user_id is not None:
        context["user_id"] = user_id
    if email is not None:
        context["email"] = email
    if environment is not None:
        context["environment"] = environment

    watcher = _get_watcher()
    flag = watcher.get(name)
    if flag is None:
        return False

    enabled, _ = flag.evaluate(context)
    return enabled


def flag_detail(
    name: str,
    user_id: Optional[str] = None,
    email: Optional[str] = None,
    environment: Optional[str] = None,
    **extra_context: Any,
) -> dict[str, Any]:
    """Get detailed evaluation result for a flag.

    Returns:
        Dict with 'enabled', 'reason', 'flag' (metadata).
    """
    context: dict[str, Any] = {**extra_context}
    if user_id is not None:
        context["user_id"] = user_id
    if email is not None:
        context["email"] = email
    if environment is not None:
        context["environment"] = environment

    watcher = _get_watcher()
    flag = watcher.get(name)
    if flag is None:
        return {"enabled": False, "reason": "flag not found", "flag": None}

    enabled, reason = flag.evaluate(context)
    return {
        "enabled": enabled,
        "reason": reason,
        "flag": flag.to_dict(),
    }


def get_flag(name: str) -> Optional[dict[str, Any]]:
    """Get flag metadata by name."""
    watcher = _get_watcher()
    flag = watcher.get(name)
    return flag.to_dict() if flag else None


def get_all_flags() -> list[dict[str, Any]]:
    """Get all flag metadata."""
    watcher = _get_watcher()
    return [f.to_dict() for f in watcher.flags]
