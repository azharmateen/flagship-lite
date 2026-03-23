"""Minimal FastAPI server for flag evaluation via HTTP."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from .flags import Flag
from .loader import FlagWatcher, load_flags, save_flags


def create_app(flags_file: str = "flags.yaml") -> FastAPI:
    """Create a FastAPI app for serving feature flags."""
    app = FastAPI(
        title="flagship-lite",
        description="Feature flag evaluation server",
        version="0.1.0",
    )

    watcher = FlagWatcher(flags_file)

    @app.get("/flags")
    def list_flags():
        """List all feature flags."""
        return {
            "flags": [f.to_dict() for f in watcher.flags],
            "count": len(watcher.flags),
        }

    @app.get("/flags/{name}")
    def get_flag(name: str):
        """Get a single flag by name."""
        flag = watcher.get(name)
        if flag is None:
            raise HTTPException(404, f"Flag '{name}' not found")
        return flag.to_dict()

    @app.get("/flags/{name}/eval")
    def evaluate_flag(
        name: str,
        user_id: Optional[str] = Query(None),
        email: Optional[str] = Query(None),
        environment: Optional[str] = Query(None),
    ):
        """Evaluate a flag for the given context."""
        flag = watcher.get(name)
        if flag is None:
            raise HTTPException(404, f"Flag '{name}' not found")

        context: dict[str, Any] = {}
        if user_id:
            context["user_id"] = user_id
        if email:
            context["email"] = email
        if environment:
            context["environment"] = environment

        enabled, reason = flag.evaluate(context)
        return {
            "flag": name,
            "enabled": enabled,
            "reason": reason,
        }

    @app.post("/flags/{name}/toggle")
    def toggle_flag(name: str):
        """Toggle a flag on/off."""
        flags = watcher.reload()
        target = None
        for f in flags:
            if f.name == name:
                target = f
                break

        if target is None:
            raise HTTPException(404, f"Flag '{name}' not found")

        from datetime import datetime
        target.enabled = not target.enabled
        target.updated_at = datetime.utcnow().isoformat()
        save_flags(flags, flags_file)
        watcher.reload()

        return {
            "flag": name,
            "enabled": target.enabled,
            "message": f"Flag '{name}' is now {'enabled' if target.enabled else 'disabled'}",
        }

    @app.get("/health")
    def health():
        return {"status": "ok", "flags_count": len(watcher.flags)}

    return app
