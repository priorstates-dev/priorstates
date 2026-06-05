"""Relay agent — serve this machine's memory to web/mobile agents via the hub.

The desktop GUI's MCP server is **stdio** — only local clients (Claude Desktop,
the CLIs) can reach it. Web and mobile AI apps can only use a **remote** MCP
connector. Rather than expose this laptop, the agent dials **outbound** to the
hub and answers tool calls the hub forwards to it:

    web/mobile app ──MCP──▶ hub ──relay──▶ this agent ──▶ local memory

The laptop makes only outbound HTTPS calls (no inbound ports). Recall-only by
default (`--allow-write` to permit memory_add/journal_add). Auth reuses the hub
key/token (and the EE bearer when the enterprise plugin is installed).
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

from .core.config import load_config
from .mcp import tools


def _headers(url: str) -> dict:
    h = {"Content-Type": "application/json"}
    key = os.environ.get("PRIORSTATES_HUB_KEY")
    if key:
        h["X-PriorStates-Key"] = key
    try:                                   # EE SSO bearer, if the plugin is present
        from .core import plugins
        h.update(plugins.registry().hub_headers(url))
    except Exception:
        pass
    return h


def _post(hub: str, path: str, body: dict, timeout: float):
    url = hub.rstrip("/") + path
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 method="POST", headers=_headers(url))
    with urllib.request.urlopen(req, timeout=timeout) as r:   # noqa: S310
        return r.status, (json.loads(r.read() or b"null"))


def serve(hub: str | None = None, *, allow_write: bool = False,
          on_ready=None) -> None:
    """Run the relay loop until interrupted."""
    hub = (hub or os.environ.get("PRIORSTATES_HUB") or "https://priorstates.com/w").rstrip("/")
    cfg = load_config()
    allowed = set(tools.ALL_TOOLS if allow_write else tools.READ_TOOLS)
    if on_ready:
        on_ready(hub, sorted(allowed))
    backoff = 1.0
    while True:
        try:
            status, req = _post(hub, "/relay/poll", {"tools": sorted(allowed)}, timeout=40)
            backoff = 1.0
            if not req or req.get("idle") or "id" not in req:
                continue                                  # long-poll idle → re-poll
            rid, name, args = req.get("id"), req.get("tool"), req.get("args") or {}
            try:
                if name not in allowed:
                    raise PermissionError(f"tool {name!r} not exposed (relay is "
                                          f"{'read+write' if allow_write else 'read-only'})")
                result = tools.call(cfg, name, args)
                out = {"id": rid, "result": result}
            except Exception as e:
                out = {"id": rid, "error": str(e)}
            _post(hub, "/relay/respond", out, timeout=30)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                print(f"relay auth rejected ({e.code}): set PRIORSTATES_HUB_KEY or "
                      f"`ee login`. {e.read().decode('utf-8', 'replace')}", file=sys.stderr)
                return
            time.sleep(backoff); backoff = min(backoff * 2, 30)
        except KeyboardInterrupt:
            print("\nrelay stopped."); return
        except Exception:
            time.sleep(backoff); backoff = min(backoff * 2, 30)   # reconnect
