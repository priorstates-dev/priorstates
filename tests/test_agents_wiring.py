"""VSCode-family agent wiring: register/idempotence/uninstall + instructions
frontmatter. Runs in a subprocess with a sandboxed HOME because the adapter
table binds Path.home() at import time."""
import os
import subprocess
import sys

import pytest

_SCRIPT = r'''
import json, os
from priorstates.core.config import load_config
from priorstates.agents.adapters import detect_installed
from priorstates.agents.install import install, uninstall

home = os.environ["HOME"]
cfg = load_config()

detected = set(detect_installed())
assert {"claude", "vscode", "cursor", "windsurf"} <= detected, detected

r1 = {r["agent"]: r["mcp"] for r in install(cfg)}
for a in ("vscode", "cursor", "windsurf"):
    assert r1[a] == "registered", r1

# idempotent re-run
r2 = {r["agent"]: r["mcp"] for r in install(cfg)}
assert all(v == "unchanged" for v in r2.values()), r2

# vscode: "servers" key + explicit stdio type
vs = json.load(open(f"{home}/.config/Code/User/mcp.json"))
assert "priorstates" in vs["servers"]
assert vs["servers"]["priorstates"]["type"] == "stdio"

# cursor / windsurf: standard mcpServers key
assert "priorstates" in json.load(open(f"{home}/.cursor/mcp.json"))["mcpServers"]
assert "priorstates" in json.load(
    open(f"{home}/.codeium/windsurf/mcp_config.json"))["mcpServers"]

# vscode instructions file: frontmatter first, protocol block present
ins = open(f"{home}/.config/Code/User/prompts/priorstates.instructions.md").read()
assert ins.startswith('---\napplyTo: "**"\n---'), ins[:60]
assert "priorstates: protocol" in ins

# windsurf global rules got the protocol block
gr = open(f"{home}/.codeium/windsurf/memories/global_rules.md").read()
assert "priorstates: protocol" in gr

# uninstall removes registrations + blocks but keeps the frontmatter file
r3 = {r["agent"]: r["mcp"] for r in uninstall(cfg)}
for a in ("vscode", "cursor", "windsurf"):
    assert r3[a] == "removed", r3
vs = json.load(open(f"{home}/.config/Code/User/mcp.json"))
assert "priorstates" not in vs.get("servers", {})
ins = open(f"{home}/.config/Code/User/prompts/priorstates.instructions.md").read()
assert "priorstates: protocol" not in ins
assert ins.startswith("---")
print("OK")
'''


@pytest.mark.skipif(os.name == "nt", reason="sandboxed HOME is posix-only")
def test_vscode_family_wiring(tmp_path):
    for d in (".config/Code/User", ".cursor", ".codeium/windsurf", ".claude"):
        (tmp_path / d).mkdir(parents=True)
    env = dict(
        os.environ,
        HOME=str(tmp_path),
        XDG_CONFIG_HOME="",
        PRIORSTATES_HOME=str(tmp_path / ".priorstates"),
        PYTHONPATH=os.pathsep.join(p for p in sys.path if p),
    )
    r = subprocess.run([sys.executable, "-c", _SCRIPT], env=env,
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, f"stdout:\n{r.stdout}\nstderr:\n{r.stderr}"
    assert "OK" in r.stdout
