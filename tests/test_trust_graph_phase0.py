"""Trust graph — Phase 0 (the claim model): id / as_of / evidence + backfill.

Additive feature: every memory becomes a claim carrying a stable id, an as_of date,
and optional evidence/edges. These tests assert the new fields are written, that the
backfill of pre-trust-graph files is idempotent and lossless, that overwrite keeps the
id stable, that the `[trust]` config overlay merges (never resets), and — crucially —
that recall and backward compatibility are unchanged.
"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from priorstates.core.config import Config, _apply  # noqa: E402
from priorstates.memory import api as mem  # noqa: E402
from priorstates.memory import writer  # noqa: E402


def _cfg(tmp_path: Path) -> Config:
    home = tmp_path / "home"
    proj = tmp_path / "proj"
    (proj / ".priorstates").mkdir(parents=True)
    (home / ".priorstates").mkdir(parents=True)
    return Config(home=home, project_root=proj, agents_enabled=[])


def test_assign_claim_id_deterministic_and_shaped():
    a = writer.assign_claim_id("foo", 123)
    assert a == writer.assign_claim_id("foo", 123)        # deterministic
    assert a != writer.assign_claim_id("foo", 124)        # varies with time
    assert a != writer.assign_claim_id("bar", 123)        # varies with name
    assert a.startswith("cl_") and len(a) == len("cl_") + 12


def test_add_assigns_id_as_of_evidence(tmp_path):
    cfg = _cfg(tmp_path)
    mem.add_memory(cfg, name="claim one", type_str="note", description="d",
                   body="b", evidence=["journal:x", "run:y"], as_of="2026-05-21")
    fm = mem.show_memory(cfg, "claim one")["frontmatter"]
    assert fm["id"].startswith("cl_")
    assert fm["as_of"] == "2026-05-21"
    assert fm["evidence"] == "[journal:x, run:y]"
    assert "source" not in fm        # absent == local; not baked, so import can stamp it


def test_add_defaults_as_of_to_today(tmp_path):
    cfg = _cfg(tmp_path)
    mem.add_memory(cfg, name="c2", type_str="note", description="", body="b")
    fm = mem.show_memory(cfg, "c2")["frontmatter"]
    assert fm["as_of"] == datetime.now().date().isoformat()
    assert fm["id"].startswith("cl_")


def test_backfill_idempotent_and_lossless(tmp_path):
    cfg = _cfg(tmp_path)
    d = Path(cfg.memory_project_dir)
    d.mkdir(parents=True, exist_ok=True)
    p = d / "legacy.md"
    p.write_text("---\nname: legacy\ndescription: x\ntype: note\ntags: [reviewed]\n---\nbody\n",
                 encoding="utf-8")
    assert writer.ensure_claim_fields(p) is True          # backfilled
    t1 = p.read_text()
    assert "id: cl_" in t1 and "as_of:" in t1 and "tags: [reviewed]" in t1 and "body" in t1
    assert writer.ensure_claim_fields(p) is False         # idempotent
    assert p.read_text() == t1                            # byte-identical


def test_backfill_preserves_metadata_block(tmp_path):
    cfg = _cfg(tmp_path)
    d = Path(cfg.memory_project_dir)
    d.mkdir(parents=True, exist_ok=True)
    p = d / "withmeta.md"
    p.write_text("---\nname: m\ndescription: d\ntype: note\nmetadata:\n  k: v\n---\nthe body\n",
                 encoding="utf-8")
    writer.ensure_claim_fields(p)
    t = p.read_text()
    assert "metadata:" in t and "  k: v" in t and "the body" in t and "id: cl_" in t


def test_overwrite_keeps_id(tmp_path):
    cfg = _cfg(tmp_path)
    mem.add_memory(cfg, name="keep", type_str="note", description="", body="v1")
    id1 = mem.show_memory(cfg, "keep")["frontmatter"]["id"]
    mem.add_memory(cfg, name="keep", type_str="note", description="", body="v2", overwrite=True)
    id2 = mem.show_memory(cfg, "keep")["frontmatter"]["id"]
    assert id1 == id2


def test_recall_unchanged(tmp_path):
    cfg = _cfg(tmp_path)
    mem.add_memory(cfg, name="fader hi-vol", type_str="note", description="", body="Sharpe -2 on hi vol")
    mem.add_memory(cfg, name="cash open", type_str="note", description="", body="09:00 NY open")
    names = [h["name"] for h in mem.search_memory(cfg, "fader volatility", k=2)]
    assert "fader hi-vol" in names


def test_legacy_file_searchable_then_backfilled(tmp_path):
    cfg = _cfg(tmp_path)
    d = Path(cfg.memory_project_dir)
    d.mkdir(parents=True, exist_ok=True)
    (d / "old.md").write_text("---\nname: old thing\ndescription: x\ntype: note\n---\nplain old body\n",
                              encoding="utf-8")
    mem.reindex(cfg, "project")        # backfills + indexes
    assert "id: cl_" in (d / "old.md").read_text()
    assert any(h["name"] == "old thing" for h in mem.search_memory(cfg, "old thing", k=3))


def test_config_trust_overlay_merges(tmp_path):
    base = _apply(Config(home=tmp_path), {"trust": {"a": 1, "halflife_days": 90}})
    assert base.trust == {"a": 1, "halflife_days": 90}
    # an overlay WITHOUT [trust] must preserve, not reset (the bug Phase 0 fixed)
    assert _apply(base, {"memory": {"types": ["note"]}}).trust == {"a": 1, "halflife_days": 90}
    # an overlay WITH [trust] merges (project over global)
    assert _apply(base, {"trust": {"b": 2, "halflife_days": 30}}).trust == \
        {"a": 1, "b": 2, "halflife_days": 30}
