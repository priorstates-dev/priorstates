"""Headless construction smoke test for the Tkinter GUI.

The GUI can't render without a display, but most breakages are construction-time
ordering bugs (e.g. a tab reading self.cfg before it's set). This mocks Tk with
permissive fakes and runs the *real* GUI logic against them, so those bugs are
caught in CI without an X server.

Run:  python -m pytest tests/test_gui_smoke.py   (or just `python tests/test_gui_smoke.py`)
"""
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock


def _install_fake_tk():
    def mod(n):
        return types.ModuleType(n)
    tkmod = mod("tkinter")
    for n in ["Tk", "Frame", "Label", "Button", "Entry", "Text", "Listbox", "Menu",
              "StringVar", "BooleanVar", "Menubutton", "Checkbutton", "Canvas", "Scrollbar"]:
        setattr(tkmod, n, lambda *a, **k: MagicMock())
    tkmod.TclError = Exception
    ttkmod = mod("tkinter.ttk")
    for n in ["Frame", "Label", "Button", "Entry", "Combobox", "Notebook", "LabelFrame",
              "Checkbutton", "Menubutton", "Style", "Treeview", "Scrollbar"]:
        setattr(ttkmod, n, lambda *a, **k: MagicMock())
    fontmod = mod("tkinter.font")
    fontmod.nametofont = lambda name: MagicMock()
    fontmod.families = lambda *a, **k: ["DejaVu Sans", "monospace"]
    sys.modules.update({"tkinter": tkmod, "tkinter.ttk": ttkmod, "tkinter.font": fontmod})


def test_gui_constructs(tmp_path=None, monkeypatch=None):
    import os
    import tempfile
    home = Path(tempfile.mkdtemp()) / "h"
    home.mkdir(parents=True, exist_ok=True)
    os.environ["PRIORSTATES_HOME"] = str(home)
    ws = Path(tempfile.mkdtemp()) / "ws"
    (ws / ".priorstates" / "memory").mkdir(parents=True, exist_ok=True)
    (ws / ".priorstates" / "journal" / "entries").mkdir(parents=True, exist_ok=True)

    _install_fake_tk()
    import importlib
    app = importlib.import_module("priorstates.gui.app")

    # no project
    g0 = app.PriorStatesGUI(MagicMock())
    assert hasattr(g0, "cfg") and g0.projects == []

    # local project lifecycle
    g = app.PriorStatesGUI(MagicMock(), project=str(ws))
    assert g.project and g.project["kind"] == "local"
    local = {"kind": "local", "path": str(ws)}
    g.set_project(local)
    g._rebuild_sidebar()

    # area switching (orthogonal to project): sets $PRIORSTATES_AREA + state,
    # which is what launched cockpit/agents inherit. Stub render_pinned so the
    # test never writes into real agent config files.
    import priorstates.memory.api as _mem_api
    _real_render = _mem_api.render_pinned
    _mem_api.render_pinned = lambda *a, **k: None
    try:
        assert g.area is None and "PRIORSTATES_AREA" not in os.environ
        g.area_var.get = lambda: "strategy"
        g._on_area_change()
        assert g.area == "strategy" and os.environ.get("PRIORSTATES_AREA") == "strategy"
        g.area_var.get = lambda: "(default)"
        g._on_area_change()
        assert g.area is None and "PRIORSTATES_AREA" not in os.environ
    finally:
        _mem_api.render_pinned = _real_render

    # remote project treated the same: add as a tab, select, persist, close
    remote = {"kind": "remote", "host": "myhost", "proj": "~/research"}
    g._add_project_entry(remote)              # adds + selects
    assert g._proj_is_remote(g.project)
    assert any(g._proj_is_remote(w) for w in g.projects)
    g.select_project(local)                   # back to local
    assert not g._proj_is_remote(g.project)
    g.select_project(remote)                  # remote again (shows panel)

    # launch bar: a click shells out the right thing per target/kind —
    #   CLI agent  → terminal `cd <dir>` (local) / `ssh -t host` (remote)
    #   GUI editor → direct argv (local: [bin, path]; remote: --remote ssh-remote+host)
    import subprocess as _sp
    import shutil as _shutil
    calls = []
    real_popen, real_which = _sp.Popen, _shutil.which
    _sp.Popen = lambda argv, *a, **k: (calls.append(argv) or MagicMock())
    _shutil.which = lambda b: "/usr/bin/" + b   # pretend every CLI/editor is on PATH
    g._terminal_argv = lambda inner: ["FAKE-TERM", inner]
    try:
        g.select_project(local)
        g._launch_target(local, "claude")       # cli → terminal in project dir
        assert calls and "claude" in calls[-1][1] and str(ws) in calls[-1][1]
        g._launch_target(local, "code")         # gui editor → [code, path]
        assert calls[-1][0] == "code" and str(ws) in calls[-1]
        g.select_project(remote)
        g._launch_target(remote, "codex")       # cli remote → ssh -t
        assert "ssh -t" in calls[-1][1] and "codex" in calls[-1][1]
        g._launch_target(remote, "code")        # editor remote → code --remote ssh-remote+host
        assert calls[-1][0] == "code" and "--remote" in calls[-1] and "ssh-remote+myhost" in calls[-1]
        g._rebuild_launchbar()                  # both groups render, must not raise

        # Windows branches: cli → new console (wt/cmd); editor → cmd /c <bin>.
        # Call the launchers directly (passing the workspace) so we don't trip
        # Path.home()/WindowsPath while os.name is faked.
        import os as _os
        real_osname = _os.name
        _os.name = "nt"
        try:
            g._launch_target(local, "claude")   # cli (Windows) → console with cd /d
            joined = " ".join(calls[-1]) if isinstance(calls[-1], list) else calls[-1]
            assert "claude" in joined and "cd /d" in joined
            g._launch_target(local, "code")     # editor (Windows) → cmd /c code <path>
            assert calls[-1][0] == "cmd" and "code" in calls[-1]
        finally:
            _os.name = real_osname
    finally:
        _sp.Popen, _shutil.which = real_popen, real_which

    # remote CLI probe is optimistic (None) until the background ssh returns
    assert g._remote_cli_present("myhost") is None or isinstance(
        g._remote_cli_present("myhost"), set)
    g._rebuild_launchbar()                      # must not raise for either kind

    g.close_project(remote)
    assert not any(g._proj_is_remote(w) for w in g.projects)
    g.close_project(local)
    assert g.projects == []


if __name__ == "__main__":
    test_gui_constructs()
    print("GUI smoke test passed")
