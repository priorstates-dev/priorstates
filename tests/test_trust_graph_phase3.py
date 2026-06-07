"""Trust graph — Phase 3 (the "why" view + the outcomes feedback loop).

An append-only outcome ledger feeds confidence: a claim that proved right gains
confidence, one that proved wrong loses it. `explain` exposes the full breakdown
(confidence parts, evidence with resolve-check, edges, outcomes); `list_stale` is the
re-verify queue. Exposed over MCP as memory_explain / memory_record_outcome.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from priorstates.core import outcomes  # noqa: E402
from priorstates.core.config import Config  # noqa: E402
from priorstates.core.indexer import confidence_components as cc  # noqa: E402
from priorstates.memory import api as mem  # noqa: E402
from priorstates.mcp import tools  # noqa: E402


def _cfg(tmp_path: Path) -> Config:
    home = tmp_path / "home"
    proj = tmp_path / "proj"
    (proj / ".priorstates").mkdir(parents=True)
    (home / ".priorstates").mkdir(parents=True)
    return Config(home=home, project_root=proj, agents_enabled=[])


# ---- ledger ---------------------------------------------------------------- #

def test_outcomes_ledger(tmp_path):
    outcomes.record(tmp_path, "cl_1", "confirmed", by="me", note="held")
    outcomes.record(tmp_path, "cl_1", "refuted")
    outcomes.record(tmp_path, "cl_2", "used_ok")
    assert len(outcomes.list_for(tmp_path, "cl_1")) == 2
    net = outcomes.net_by_claim(tmp_path)
    assert abs(net["cl_1"] - 0.0) < 1e-9        # +1 - 1
    assert abs(net["cl_2"] - 0.5) < 1e-9
    import pytest
    with pytest.raises(ValueError):
        outcomes.record(tmp_path, "cl_1", "bogus")


def test_outcome_factor():
    assert abs(cc(source=None, signer=None, scan=None, evidence=[], outcomes_net=0)["outcome_factor"] - 1.0) < 1e-9
    assert cc(source=None, signer=None, scan=None, evidence=[], outcomes_net=2)["outcome_factor"] > 1.0
    assert cc(source=None, signer=None, scan=None, evidence=[], outcomes_net=-2)["outcome_factor"] < 1.0


# ---- the feedback loop moves confidence ------------------------------------ #

def test_confirm_raises_refute_lowers(tmp_path):
    cfg = _cfg(tmp_path)
    mem.add_memory(cfg, name="c", type_str="note", description="topic", body="topic body here")
    base = mem.search_memory(cfg, "topic body here", k=1)[0]["trust"]
    mem.record_outcome(cfg, "c", "confirmed")
    up = mem.search_memory(cfg, "topic body here", k=1)[0]["trust"]
    for _ in range(3):
        mem.record_outcome(cfg, "c", "refuted")
    down = mem.search_memory(cfg, "topic body here", k=1)[0]["trust"]
    assert up > base > down


# ---- explain --------------------------------------------------------------- #

def test_explain_breakdown_and_evidence_resolution(tmp_path):
    cfg = _cfg(tmp_path)
    here = "file:" + str(tmp_path)          # exists
    mem.add_memory(cfg, name="x", type_str="note", description="d", body="b",
                   evidence=[here, "url:http://example"])
    info = mem.explain(cfg, "x")
    assert info["id"].startswith("cl_")
    assert "value" in info["confidence"] and not info["confidence"]["explicit"]
    refs = {e["ref"]: e["resolves"] for e in info["evidence"]}
    assert refs[here] is True               # file path resolves
    assert refs["url:http://example"] is None   # not locally verifiable


def test_explain_shows_edges_and_outcomes(tmp_path):
    cfg = _cfg(tmp_path)
    mem.add_memory(cfg, name="a", type_str="note", description="t", body="t one")
    mem.add_memory(cfg, name="b", type_str="note", description="t", body="t two")
    mem.link_memory(cfg, "a", "contradicts", "b")
    mem.record_outcome(cfg, "a", "confirmed", note="ok")
    info = mem.explain(cfg, "a")
    assert "contradicts" in info["edges"]
    assert info["outcomes"] and info["outcomes"][0]["result"] == "confirmed"


# ---- stale ----------------------------------------------------------------- #

def test_list_stale(tmp_path):
    cfg = _cfg(tmp_path)
    mem.add_memory(cfg, name="old", type_str="note", description="", body="b1", valid_until="2000-01-01")
    mem.add_memory(cfg, name="fresh", type_str="note", description="", body="b2", valid_until="2099-01-01")
    names = [r["name"] for r in mem.list_stale(cfg)]
    assert "old" in names and "fresh" not in names


# ---- MCP surface ----------------------------------------------------------- #

def test_mcp_explain_and_record_outcome(tmp_path):
    cfg = _cfg(tmp_path)
    tools.call(cfg, "memory_add", {"name": "m", "type": "note", "body": "mcp body", "scope": "global"})
    info = tools.call(cfg, "memory_explain", {"name": "m", "scope": "global"})
    assert info["id"].startswith("cl_")
    tools.call(cfg, "memory_record_outcome", {"name": "m", "result": "confirmed", "scope": "global"})
    info2 = tools.call(cfg, "memory_explain", {"name": "m", "scope": "global"})
    assert info2["outcomes"] and info2["confidence"]["value"] > info["confidence"]["value"]
    assert "memory_explain" in tools.READ_TOOLS and "memory_record_outcome" in tools.WRITE_TOOLS
