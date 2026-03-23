"""flagship-lite: Feature flags that live in your repo."""

__version__ = "0.1.0"

from .sdk import flag_enabled, get_flag, get_all_flags

__all__ = ["flag_enabled", "get_flag", "get_all_flags"]
