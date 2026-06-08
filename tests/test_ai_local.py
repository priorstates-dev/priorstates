"""Local-first AI resolution: auto-use a running ollama server when nothing else is
configured; explicit ai.json always wins. (Probes are monkeypatched — no network.)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from priorstates.core import ai  # noqa: E402
from priorstates.core.config import Config  # noqa: E402


def _cfg(tmp_path):
    (tmp_path / ".priorstates").mkdir(parents=True, exist_ok=True)
    return Config(home=tmp_path)


def test_pick_prefers_known_families():
    assert ai._pick_ollama_model(["mistral:7b", "qwen2.5:7b"]) == "qwen2.5:7b"
    assert ai._pick_ollama_model(["foo:1b", "llama3.1:8b"]) == "llama3.1:8b"
    assert ai._pick_ollama_model(["weirdmodel:9b"]) == "weirdmodel:9b"   # falls back to first


def test_auto_uses_ollama_when_running(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)                                   # no ai.json
    monkeypatch.setattr(ai, "_ollama_models", lambda base, timeout=0.6: ["qwen2.5:7b"])
    r = ai.resolve_ai(cfg)
    assert r["provider"] == "ollama" and r["model"] == "qwen2.5:7b" and r.get("_auto")
    assert ai.configured(cfg) is True


def test_no_ai_when_nothing_available(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    monkeypatch.setattr(ai, "_ollama_models", lambda base, timeout=0.6: [])
    assert ai.resolve_ai(cfg) == {}
    assert ai.configured(cfg) is False


def test_explicit_config_wins_over_autodetect(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    ai.save_ai(cfg, {"provider": "claude_cli", "command": "claude"})
    # even with ollama running, the explicit choice is honored
    monkeypatch.setattr(ai, "_ollama_models", lambda base, timeout=0.6: ["qwen2.5:7b"])
    r = ai.resolve_ai(cfg)
    assert r["provider"] == "claude_cli"
    assert ai.configured(cfg) is True


def test_anthropic_needs_key(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    monkeypatch.setattr(ai, "_ollama_models", lambda base, timeout=0.6: [])
    ai.save_ai(cfg, {"provider": "anthropic", "model": "x"})          # no api_key
    assert ai.configured(cfg) is False
    ai.save_ai(cfg, {"provider": "anthropic", "model": "x", "api_key": "sk-1"})
    assert ai.configured(cfg) is True
