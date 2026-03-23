"""Find stale flags: old, always on/off, no code references."""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .flags import Flag


@dataclass
class StaleReport:
    """Report of a potentially stale flag."""
    flag_name: str
    reason: str
    severity: str  # "high", "medium", "low"
    details: str = ""

    def __str__(self) -> str:
        return f"[{self.severity.upper()}] {self.flag_name}: {self.reason}"


def _parse_date(date_str: str) -> Optional[datetime]:
    """Try to parse ISO date string."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def find_old_flags(flags: list[Flag], max_age_days: int = 90) -> list[StaleReport]:
    """Find flags that haven't been updated in a long time."""
    reports: list[StaleReport] = []
    cutoff = datetime.utcnow() - timedelta(days=max_age_days)

    for flag in flags:
        updated = _parse_date(flag.updated_at)
        if updated and updated < cutoff:
            age_days = (datetime.utcnow() - updated).days
            reports.append(StaleReport(
                flag_name=flag.name,
                reason=f"Not updated in {age_days} days",
                severity="medium",
                details=f"Last updated: {flag.updated_at}",
            ))

    return reports


def find_always_on_off(flags: list[Flag]) -> list[StaleReport]:
    """Find flags that are always enabled with 100% rollout or always disabled."""
    reports: list[StaleReport] = []

    for flag in flags:
        if flag.enabled and flag.rollout_percentage == 100.0 and not flag.targeting_rules:
            reports.append(StaleReport(
                flag_name=flag.name,
                reason="Always ON (100%, no targeting) -- can be removed and code hardcoded",
                severity="high",
                details="enabled=true, rollout=100%, no rules",
            ))
        elif not flag.enabled:
            created = _parse_date(flag.created_at)
            if created and (datetime.utcnow() - created).days > 30:
                reports.append(StaleReport(
                    flag_name=flag.name,
                    reason="Disabled for 30+ days -- dead code candidate",
                    severity="high",
                    details=f"Created: {flag.created_at}, never enabled",
                ))

    return reports


def find_unreferenced_flags(
    flags: list[Flag],
    search_dir: str = ".",
    extensions: Optional[list[str]] = None,
) -> list[StaleReport]:
    """Find flags with no code references via grep.

    Searches source files for the flag name as a string literal.
    """
    if extensions is None:
        extensions = [
            ".py", ".js", ".ts", ".jsx", ".tsx", ".rb", ".go",
            ".java", ".rs", ".swift", ".kt", ".vue", ".svelte",
        ]

    reports: list[StaleReport] = []
    search_path = Path(search_dir).resolve()

    for flag in flags:
        found = False
        # Search for flag name in source files (skip flags.yaml itself)
        for ext in extensions:
            try:
                result = subprocess.run(
                    ["grep", "-rl", flag.name, str(search_path),
                     "--include", f"*{ext}"],
                    capture_output=True, text=True, timeout=10,
                )
                if result.stdout.strip():
                    found = True
                    break
            except (subprocess.TimeoutExpired, FileNotFoundError):
                # grep not available or timeout, skip this check
                return reports

        if not found:
            reports.append(StaleReport(
                flag_name=flag.name,
                reason="No code references found -- flag may be unused",
                severity="medium",
                details=f"Searched {search_path} for '{flag.name}' in {', '.join(extensions)}",
            ))

    return reports


def detect_stale(
    flags: list[Flag],
    max_age_days: int = 90,
    search_dir: str = ".",
) -> list[StaleReport]:
    """Run all stale detection checks.

    Returns:
        Combined list of stale reports, sorted by severity.
    """
    reports: list[StaleReport] = []
    reports.extend(find_old_flags(flags, max_age_days))
    reports.extend(find_always_on_off(flags))
    reports.extend(find_unreferenced_flags(flags, search_dir))

    severity_order = {"high": 0, "medium": 1, "low": 2}
    reports.sort(key=lambda r: severity_order.get(r.severity, 3))
    return reports
