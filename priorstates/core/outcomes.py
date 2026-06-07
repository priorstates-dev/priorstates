"""Append-only outcome ledger feeding claim confidence (trust-graph Phase 3).

Each acted-on outcome (``confirmed`` / ``refuted`` / ``used_ok`` / ``used_bad``) is one
JSON line in ``<memory_dir>/outcomes.jsonl``. ``compute_confidence`` consumes the net
signed weight, so a claim that proved right gains confidence and one that proved wrong
loses it — closing the loop that lets the store learn which of its own facts are
reliable.

This is the OPEN/local backend; the enterprise edition swaps in a hash-chained,
tamper-evident ledger behind the same interface.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

LEDGER = "outcomes.jsonl"
RESULTS = ("confirmed", "refuted", "used_ok", "used_bad")
_WEIGHT = {"confirmed": 1.0, "used_ok": 0.5, "refuted": -1.0, "used_bad": -0.5}
_CACHE: dict = {}


def _path(memory_dir) -> Path:
    return Path(memory_dir) / LEDGER


def _signed(rec: dict) -> float:
    base = _WEIGHT.get(str(rec.get("result", "")).lower(), 0.0)
    try:
        w = float(rec.get("weight", 1.0))
    except (TypeError, ValueError):
        w = 1.0
    return base * w


def record(memory_dir, claim_id: str, result: str, *, by: str = "", note: str = "",
           weight: float = 1.0, at: str | None = None) -> dict:
    result = str(result).lower().replace("-", "_")
    if result not in _WEIGHT:
        raise ValueError(f"unknown outcome {result!r}; valid: {RESULTS}")
    rec = {"at": at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "claim": claim_id, "result": result, "weight": float(weight)}
    if by:
        rec["by"] = by
    if note:
        rec["note"] = note
    p = _path(memory_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def list_for(memory_dir, claim_id: str) -> list[dict]:
    out: list[dict] = []
    p = _path(memory_dir)
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if rec.get("claim") == claim_id:
            out.append(rec)
    return out


def net_by_claim(memory_dir) -> dict:
    """{claim_id: net signed weight}, cached per (mtime, size) so a reindex parses the
    ledger once and re-reads only after an append."""
    p = _path(memory_dir)
    try:
        stt = p.stat()
        sig = (stt.st_mtime_ns, stt.st_size)
    except OSError:
        return {}
    key = str(p)
    cached = _CACHE.get(key)
    if cached and cached[0] == sig:
        return cached[1]
    net: dict = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        cid = rec.get("claim")
        if cid:
            net[cid] = net.get(cid, 0.0) + _signed(rec)
    _CACHE[key] = (sig, net)
    return net
