"""Load flags from YAML file, validate schema, watch for changes."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Optional

import yaml

from .flags import Flag


DEFAULT_FLAGS_FILE = "flags.yaml"

# Schema for validation
REQUIRED_FIELDS = {"name"}
VALID_OPERATORS = {"eq", "neq", "contains", "starts_with", "ends_with", "in", "regex"}


class FlagLoadError(Exception):
    """Raised when flags file cannot be loaded or validated."""
    pass


def _validate_flag_data(data: dict, index: int) -> list[str]:
    """Validate a single flag's data. Returns list of errors."""
    errors: list[str] = []

    if "name" not in data:
        errors.append(f"Flag #{index}: missing required field 'name'")
        return errors

    name = data["name"]

    if not isinstance(name, str) or not name.strip():
        errors.append(f"Flag #{index}: 'name' must be a non-empty string")

    if "enabled" in data and not isinstance(data["enabled"], bool):
        errors.append(f"Flag '{name}': 'enabled' must be a boolean")

    if "rollout_percentage" in data:
        pct = data["rollout_percentage"]
        if not isinstance(pct, (int, float)) or pct < 0 or pct > 100:
            errors.append(f"Flag '{name}': 'rollout_percentage' must be 0-100")

    if "targeting_rules" in data:
        if not isinstance(data["targeting_rules"], list):
            errors.append(f"Flag '{name}': 'targeting_rules' must be a list")
        else:
            for i, rule in enumerate(data["targeting_rules"]):
                if "attribute" not in rule:
                    errors.append(f"Flag '{name}', rule #{i}: missing 'attribute'")
                op = rule.get("operator", "eq")
                if op not in VALID_OPERATORS:
                    errors.append(f"Flag '{name}', rule #{i}: invalid operator '{op}'")

    if "environments" in data and not isinstance(data["environments"], list):
        errors.append(f"Flag '{name}': 'environments' must be a list")

    return errors


def load_flags(path: Optional[str] = None) -> list[Flag]:
    """Load and validate flags from a YAML file.

    Args:
        path: Path to flags YAML file. Defaults to 'flags.yaml' in cwd.

    Returns:
        List of validated Flag objects.

    Raises:
        FlagLoadError: If the file is missing, malformed, or fails validation.
    """
    flags_path = Path(path) if path else Path(DEFAULT_FLAGS_FILE)

    if not flags_path.exists():
        raise FlagLoadError(f"Flags file not found: {flags_path}")

    try:
        raw = flags_path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw)
    except yaml.YAMLError as e:
        raise FlagLoadError(f"Invalid YAML in {flags_path}: {e}")

    if data is None:
        return []

    if isinstance(data, dict):
        flags_data = data.get("flags", [])
    elif isinstance(data, list):
        flags_data = data
    else:
        raise FlagLoadError(f"Expected a list of flags or a dict with 'flags' key")

    # Validate all flags
    all_errors: list[str] = []
    for i, flag_data in enumerate(flags_data):
        if not isinstance(flag_data, dict):
            all_errors.append(f"Flag #{i}: expected a mapping, got {type(flag_data).__name__}")
            continue
        all_errors.extend(_validate_flag_data(flag_data, i))

    if all_errors:
        raise FlagLoadError(
            f"Validation errors in {flags_path}:\n" +
            "\n".join(f"  - {e}" for e in all_errors)
        )

    # Parse flags
    flags: list[Flag] = []
    seen_names: set[str] = set()
    for flag_data in flags_data:
        name = flag_data["name"]
        if name in seen_names:
            raise FlagLoadError(f"Duplicate flag name: '{name}'")
        seen_names.add(name)
        flags.append(Flag.from_dict(flag_data))

    return flags


def save_flags(flags: list[Flag], path: Optional[str] = None) -> None:
    """Save flags back to YAML file."""
    flags_path = Path(path) if path else Path(DEFAULT_FLAGS_FILE)
    data = {"flags": [f.to_dict() for f in flags]}
    flags_path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8")


def find_flags_file(start_dir: Optional[str] = None) -> Optional[Path]:
    """Walk up the directory tree to find flags.yaml."""
    current = Path(start_dir) if start_dir else Path.cwd()
    while True:
        candidate = current / DEFAULT_FLAGS_FILE
        if candidate.exists():
            return candidate
        parent = current.parent
        if parent == current:
            return None
        current = parent


class FlagWatcher:
    """Watch a flags file for changes and reload automatically."""

    def __init__(self, path: Optional[str] = None):
        self.path = Path(path) if path else Path(DEFAULT_FLAGS_FILE)
        self._last_mtime: float = 0
        self._flags: list[Flag] = []
        self.reload()

    def reload(self) -> list[Flag]:
        """Force reload flags from file."""
        self._flags = load_flags(str(self.path))
        self._last_mtime = self.path.stat().st_mtime
        return self._flags

    @property
    def flags(self) -> list[Flag]:
        """Get flags, reloading if file has changed."""
        try:
            mtime = self.path.stat().st_mtime
            if mtime != self._last_mtime:
                self.reload()
        except FileNotFoundError:
            pass
        return self._flags

    def get(self, name: str) -> Optional[Flag]:
        """Get a specific flag by name."""
        for f in self.flags:
            if f.name == name:
                return f
        return None
