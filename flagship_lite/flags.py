"""Flag model: name, description, enabled, rollout_percentage, targeting rules."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class TargetingRule:
    """A single targeting rule for a feature flag."""
    attribute: str       # "user_id", "email", "environment", "country", etc.
    operator: str        # "eq", "neq", "contains", "starts_with", "ends_with", "in", "regex"
    value: Any           # The value to match against

    def matches(self, context: dict[str, Any]) -> bool:
        """Check if this rule matches the given context."""
        actual = context.get(self.attribute)
        if actual is None:
            return False

        actual_str = str(actual)
        value_str = str(self.value)

        if self.operator == "eq":
            return actual_str == value_str
        elif self.operator == "neq":
            return actual_str != value_str
        elif self.operator == "contains":
            return value_str in actual_str
        elif self.operator == "starts_with":
            return actual_str.startswith(value_str)
        elif self.operator == "ends_with":
            return actual_str.endswith(value_str)
        elif self.operator == "in":
            if isinstance(self.value, list):
                return actual_str in [str(v) for v in self.value]
            return actual_str in value_str.split(",")
        elif self.operator == "regex":
            import re
            return bool(re.search(value_str, actual_str))
        return False


@dataclass
class Flag:
    """A feature flag definition."""
    name: str
    description: str = ""
    enabled: bool = False
    rollout_percentage: float = 100.0  # 0-100
    targeting_rules: list[TargetingRule] = field(default_factory=list)
    environments: list[str] = field(default_factory=list)  # empty = all environments
    created_at: str = ""
    updated_at: str = ""
    tags: list[str] = field(default_factory=list)

    def __post_init__(self):
        now = datetime.utcnow().isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def evaluate(self, context: Optional[dict[str, Any]] = None) -> tuple[bool, str]:
        """Evaluate this flag for a given context.

        Args:
            context: Dict with user_id, email, environment, etc.

        Returns:
            Tuple of (is_enabled, reason).
        """
        if not self.enabled:
            return False, "flag is disabled"

        ctx = context or {}

        # Check environment targeting
        if self.environments:
            env = ctx.get("environment", "")
            if env and env not in self.environments:
                return False, f"environment '{env}' not in {self.environments}"

        # Check targeting rules (all must match if present)
        if self.targeting_rules:
            for rule in self.targeting_rules:
                if not rule.matches(ctx):
                    return False, f"targeting rule failed: {rule.attribute} {rule.operator} {rule.value}"

        # Check percentage rollout
        if self.rollout_percentage < 100.0:
            user_id = ctx.get("user_id", ctx.get("id", ""))
            if not user_id:
                return False, "no user_id for percentage rollout"

            # Deterministic hash-based rollout
            hash_input = f"{self.name}:{user_id}"
            hash_val = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
            bucket = hash_val % 100

            if bucket >= self.rollout_percentage:
                return False, f"user not in rollout ({bucket}% >= {self.rollout_percentage}%)"

        return True, "all checks passed"

    def to_dict(self) -> dict:
        """Serialize flag to a dictionary."""
        d: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "enabled": self.enabled,
        }
        if self.rollout_percentage != 100.0:
            d["rollout_percentage"] = self.rollout_percentage
        if self.targeting_rules:
            d["targeting_rules"] = [
                {"attribute": r.attribute, "operator": r.operator, "value": r.value}
                for r in self.targeting_rules
            ]
        if self.environments:
            d["environments"] = self.environments
        if self.tags:
            d["tags"] = self.tags
        d["created_at"] = self.created_at
        d["updated_at"] = self.updated_at
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Flag":
        """Create a Flag from a dictionary (YAML-parsed)."""
        rules = []
        for r in data.get("targeting_rules", []):
            rules.append(TargetingRule(
                attribute=r.get("attribute", ""),
                operator=r.get("operator", "eq"),
                value=r.get("value", ""),
            ))

        return cls(
            name=data["name"],
            description=data.get("description", ""),
            enabled=data.get("enabled", False),
            rollout_percentage=float(data.get("rollout_percentage", 100.0)),
            targeting_rules=rules,
            environments=data.get("environments", []),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            tags=data.get("tags", []),
        )
