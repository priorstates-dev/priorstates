"""Prompt-injection / manipulation heuristics for imported memory.

Imported memory is fed to your agents, so a hostile bundle could try to smuggle
instructions ("ignore previous instructions", tool-call lures, exfiltration) into
a memory body. This is a cheap, dependency-free first line: flag suspicious items
so they show up in the pre-ingest summary and the user can refuse. It is a
heuristic, not a guarantee — a model-based scan is the Phase-2 upgrade.
"""
from __future__ import annotations

import re

# (compiled pattern, human reason). Kept curated + explainable on purpose.
_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bignore\s+(all\s+|any\s+)?(the\s+)?(previous|prior|above|preceding)\b.{0,40}\binstruction", re.I),
     "instruction-override ('ignore previous instructions')"),
    (re.compile(r"\bdisregard\b.{0,40}\b(previous|prior|above|earlier|system|instruction)", re.I),
     "instruction-override ('disregard …')"),
    (re.compile(r"\bforget\b.{0,30}\b(everything|all|previous|above|instruction|context)", re.I),
     "context-wipe ('forget everything …')"),
    (re.compile(r"\b(new|updated|revised)\s+instructions?\s*:", re.I),
     "instruction-injection ('new instructions:')"),
    (re.compile(r"\byou\s+are\s+now\b|\bfrom\s+now\s+on\b.{0,20}\byou\b", re.I),
     "role-reassignment ('you are now …')"),
    (re.compile(r"\bdeveloper\s+mode\b|\bDAN\s+mode\b|\bjailbreak\b", re.I),
     "jailbreak marker"),
    (re.compile(r"<\|?(im_start|im_end|system|/system)\|?>|\[/?system\]|^#+\s*system\b", re.I | re.M),
     "role/system-tag spoofing"),
    (re.compile(r"\b(exfiltrat|leak|send|upload|post)\b.{0,40}\b(secret|token|key|password|credential|env|\.ssh)", re.I),
     "exfiltration lure"),
    (re.compile(r"\b(call|invoke|use|run)\b.{0,30}\btool\b.{0,30}\b(to|and)\b", re.I),
     "tool-call lure"),
    (re.compile(r"\b(run|execute|eval)\b.{0,20}\bthe\s+following\b", re.I),
     "code-execution lure"),
    (re.compile(r"\b(curl|wget)\s+https?://|\brm\s+-rf\b|\bbase64\s+-d\b|\beval\(", re.I),
     "embedded shell/command"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
     "embedded private key"),
    (re.compile(r"[A-Za-z0-9+/]{220,}={0,2}"),
     "long opaque blob (possible hidden payload)"),
    (re.compile(r"[​‌‍⁠﻿]"),
     "zero-width/invisible characters"),
]


def scan_text(text: str) -> list[str]:
    """Return a de-duplicated list of reasons this text looks manipulative."""
    reasons: list[str] = []
    for pat, reason in _PATTERNS:
        if pat.search(text) and reason not in reasons:
            reasons.append(reason)
    return reasons


def scan_bundle(manifest: dict, members: dict) -> dict[str, list[str]]:
    """Scan every memory + journal body in a bundle.

    Returns ``{archive_path: [reasons]}`` for items that tripped a heuristic.
    """
    flagged: dict[str, list[str]] = {}
    for item in manifest.get("memory", []) + manifest.get("journal", []):
        b = members.get(item["file"])
        if b is None:
            continue
        reasons = scan_text(b.decode("utf-8", "replace"))
        if reasons:
            flagged[item["file"]] = reasons
    return flagged
