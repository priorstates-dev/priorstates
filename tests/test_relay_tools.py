"""Shared MCP tool dispatch used by the stdio server + the relay agent."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from priorstates.core.config import Config  # noqa: E402
from priorstates.mcp import tools  # noqa: E402
from priorstates.memory import api as mem  # noqa: E402


def _cfg(tmp_path):
    home = tmp_path / "home"
    (home / ".priorstates").mkdir(parents=True)
    return Config(home=home, project_root=None, agents_enabled=[])


def test_read_tools_dispatch(tmp_path):
    cfg = _cfg(tmp_path)
    mem.add_memory(cfg, name="teal fact", type_str="note", description="d",
                   body="the sky is teal on tuesdays", scope="global", pinned=True)
    got = tools.call(cfg, "memory_get", {"name": "teal fact"})
    assert got and got["name"] == "teal fact"
    pinned = tools.call(cfg, "memory_list_pinned", {})
    assert any(p["name"] == "teal fact" for p in pinned)
    hits = tools.call(cfg, "memory_search", {"query": "sky colour", "k": 3})
    assert any("teal" in h["body"] for h in hits)


def test_unknown_tool_raises(tmp_path):
    with pytest.raises(ValueError):
        tools.call(_cfg(tmp_path), "definitely_not_a_tool", {})


def test_read_only_set_excludes_writes():
    assert "memory_add" not in tools.READ_TOOLS
    assert "memory_add" in tools.ALL_TOOLS and "journal_add" in tools.ALL_TOOLS


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
