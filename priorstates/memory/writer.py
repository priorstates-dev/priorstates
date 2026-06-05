"""Memory write path: create / delete / pin ``.md`` files.

Ported from the reference writer; the valid ``type`` set now comes from the
active config rather than a fixed enum.
"""
from __future__ import annotations

import hashlib
import os
import re
import time
from pathlib import Path

SLUG_RE = re.compile(r"[^a-z0-9]+")


class MemoryWriteError(Exception):
    pass


def make_slug(name: str, max_len: int = 80) -> str:
    s = SLUG_RE.sub("-", name.lower()).strip("-") or "memory"
    return s[:max_len].rstrip("-") if len(s) > max_len else s


def _frontmatter_name(path: Path) -> str | None:
    try:
        head = path.read_text(encoding="utf-8", errors="replace").split("---\n", 2)
    except OSError:
        return None
    if len(head) < 3:
        return None
    for line in head[1].splitlines():
        if line.startswith("name:"):
            return line.split(":", 1)[1].strip().strip('"').strip("'")
    return None


def find_existing_by_name(memory_dir: Path, name: str) -> Path | None:
    name_norm = name.strip()
    for p in memory_dir.glob("*.md"):
        if p.name in ("MEMORY.md", "INDEX.md", "README.md"):
            continue
        if _frontmatter_name(p) == name_norm:
            return p
    return None


def _norm_tags(tags) -> list[str]:
    """De-dup + order-preserve a list of tag strings (lowercased, trimmed)."""
    out: list[str] = []
    for t in tags or []:
        t = str(t).strip().lower()
        if t and t not in out:
            out.append(t)
    return out


def build_frontmatter(*, name: str, type_str: str, description: str, pinned: bool,
                      valid_types: list[str], tags: list[str] | None = None) -> str:
    if type_str not in valid_types:
        raise MemoryWriteError(f"unknown type {type_str!r}; valid: {valid_types}")
    lines = [f"name: {name}", f"description: {description}", f"type: {type_str}"]
    if pinned:
        lines.append("pinned: true")
    tags = _norm_tags(tags)
    if tags:
        lines.append(f"tags: [{', '.join(tags)}]")
    return "\n".join(lines) + "\n"


def create_memory(*, name: str, type_str: str, description: str, body: str,
                  memory_dir: Path, valid_types: list[str],
                  pinned: bool = False, overwrite: bool = False,
                  tags: list[str] | None = None) -> Path:
    memory_dir = Path(memory_dir)
    memory_dir.mkdir(parents=True, exist_ok=True)
    name = name.strip()
    if not name:
        raise MemoryWriteError("name must be non-empty")
    body = body.strip()
    if not body:
        raise MemoryWriteError("body must be non-empty")

    existing = find_existing_by_name(memory_dir, name)
    if existing is not None and not overwrite:
        raise MemoryWriteError(f"a memory named {name!r} already exists at {existing}; "
                               f"pass overwrite=True to replace it")

    fm = build_frontmatter(name=name, type_str=type_str, description=description.strip(),
                           pinned=pinned, valid_types=valid_types, tags=tags)
    content = f"---\n{fm}---\n{body}\n"
    path = memory_dir / f"{make_slug(name)}.md"
    if path.exists() and (existing is None or existing != path):
        h = hashlib.sha256(f"{name}:{time.time()}".encode()).hexdigest()[:6]
        path = memory_dir / f"{make_slug(name)}-{h}.md"
    if existing is not None and overwrite:
        path = existing
    tmp = path.with_suffix(".md.tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)
    return path


def delete_memory(name: str, *, memory_dir: Path) -> Path | None:
    existing = find_existing_by_name(Path(memory_dir), name)
    if existing is None:
        return None
    existing.unlink()
    return existing


def set_pinned(name: str, pinned: bool, *, memory_dir: Path) -> Path | None:
    existing = find_existing_by_name(Path(memory_dir), name)
    if existing is None:
        return None
    parts = existing.read_text(encoding="utf-8").split("---\n", 2)
    if len(parts) < 3:
        raise MemoryWriteError(f"{existing} has no frontmatter")
    new_lines, saw = [], False
    for line in parts[1].splitlines():
        if line.strip().startswith("pinned:"):
            saw = True
            if pinned:
                new_lines.append("pinned: true")
        else:
            new_lines.append(line)
    if pinned and not saw:
        new_lines.append("pinned: true")
    new_text = f"---\n{chr(10).join(new_lines)}\n---\n{parts[2]}"
    tmp = existing.with_suffix(".md.tmp")
    tmp.write_text(new_text, encoding="utf-8")
    os.replace(tmp, existing)
    return existing


def parse_tags(value: str | None) -> list[str]:
    """Parse a frontmatter ``tags:`` value into a list.

    Tolerant of ``[a, b]``, ``a, b`` and ``a b`` forms (the inline-list, CSV and
    whitespace conventions that show up across hand-written and generated files).
    """
    if not value:
        return []
    v = value.strip()
    if v.startswith("[") and v.endswith("]"):
        v = v[1:-1]
    parts = re.split(r"[,\s]+", v)
    return _norm_tags(p.strip().strip("\"'") for p in parts if p.strip())


def add_tags(name: str, tags: list[str], *, memory_dir: Path,
             remove: bool = False) -> tuple[Path, list[str]] | None:
    """Merge (or, with ``remove``, drop) ``tags`` on an existing memory.

    Returns ``(path, resulting_tags)`` or ``None`` if no memory matches ``name``.
    Idempotent: adding a tag already present is a no-op.
    """
    existing = find_existing_by_name(Path(memory_dir), name)
    if existing is None:
        return None
    parts = existing.read_text(encoding="utf-8").split("---\n", 2)
    if len(parts) < 3:
        raise MemoryWriteError(f"{existing} has no frontmatter")
    fm_lines, cur, saw_i = [], [], None
    for i, line in enumerate(parts[1].splitlines()):
        if line.strip().startswith("tags:"):
            cur = parse_tags(line.split(":", 1)[1])
            saw_i = len(fm_lines)
            fm_lines.append(None)  # placeholder, filled below
        else:
            fm_lines.append(line)
    want = _norm_tags(tags)
    if remove:
        result = [t for t in cur if t not in want]
    else:
        result = _norm_tags(cur + want)
    tag_line = f"tags: [{', '.join(result)}]" if result else None
    if saw_i is not None:
        if tag_line is None:
            fm_lines.pop(saw_i)
        else:
            fm_lines[saw_i] = tag_line
    elif tag_line is not None:
        fm_lines.append(tag_line)
    new_text = f"---\n{chr(10).join(fm_lines)}\n---\n{parts[2]}"
    tmp = existing.with_suffix(".md.tmp")
    tmp.write_text(new_text, encoding="utf-8")
    os.replace(tmp, existing)
    return existing, result
