"""Shared MCP tool dispatch.

The same tool implementations are exposed two ways: the stdio MCP server
(`server.py`, for local clients) and the **hub relay agent** (`relay.py`, which
answers tool calls forwarded from a web/mobile app via the hub). Keeping the
dispatch here means both paths behave identically.
"""
from __future__ import annotations

from ..core import journal as J
from ..memory import api as mem

# Recall-only tools — the safe default for the relay (a web app can READ your
# memory but not modify it). Writes are opt-in (`--allow-write`).
READ_TOOLS = ("memory_search", "memory_get", "memory_list_pinned", "journal_search")
WRITE_TOOLS = ("memory_add", "journal_add")
ALL_TOOLS = READ_TOOLS + WRITE_TOOLS


def call(cfg, name: str, args: dict | None):
    """Execute a tool by name against `cfg`; returns a JSON-serializable result."""
    a = args or {}
    if name == "memory_search":
        return mem.search_memory(cfg, a["query"], k=a.get("k", 5),
                                 type_str=a.get("type"), scope=a.get("scope", "all"))
    if name == "memory_get":
        return mem.get_memory(cfg, a["name"], scope=a.get("scope", "all"))
    if name == "memory_list_pinned":
        return mem.list_pinned(cfg, scope=a.get("scope", "all"))
    if name == "journal_search":
        return J.search(cfg, topic=a.get("topic"), outcome=a.get("outcome"),
                        tag=a.get("tag"), since=a.get("since"), until=a.get("until"),
                        query=a.get("query"), k=a.get("k", 20))
    if name == "memory_add":
        return mem.add_memory(cfg, name=a["name"], type_str=a["type"],
                              description=a.get("description", ""), body=a["body"],
                              pinned=a.get("pinned", False), scope=a.get("scope", "project"),
                              tags=a.get("tags"))
    if name == "journal_add":
        e = J.add(cfg, topic=a["topic"], outcome=a["outcome"], title=a["title"],
                  body=a["body"], tags=a.get("tags"), evidence=a.get("evidence"),
                  supersedes=a.get("supersedes"))
        return {"id": e.id, "outcome": e.outcome}
    raise ValueError(f"unknown or unsupported tool: {name!r}")
