#!/usr/bin/env bash
# PriorStates — self-contained installer (Linux / macOS).
#
# Bundled in the download tarball next to wheels/. Installs the open-source
# core into a private venv and wires CLI + GUI launchers, so you never touch
# pip. Only numpy is fetched from PyPI (one-time network), unless you bundled
# it too. By default it then wires every detected AI agent (install-and-forget).
#
#   ./install.sh                # install / upgrade + wire agents + semantic recall
#   ./install.sh --lite         # skip the onnx libs + 127MB model (hashing recall)
#   ./install.sh --no-wire      # install but skip agent wiring
#   ./install.sh --uninstall    # remove
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
WHEELS="$HERE/wheels"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}/priorstates"
VENV="$DATA/venv"
BIN="$HOME/.local/bin"

WIRE=1; MODEL=1
for a in "$@"; do
  case "$a" in
    --no-wire) WIRE=0 ;;
    --lite|--no-model) MODEL=0 ;;
    --uninstall)
      # Unwire the MCP server + pinned block from the user's agents, and remove the
      # desktop/app launcher, via the CLI (best-effort) BEFORE the venv goes away.
      "$VENV/bin/priorstates" agents uninstall >/dev/null 2>&1 || true
      "$VENV/bin/priorstates" install-launcher --uninstall >/dev/null 2>&1 || true
      rm -rf "$VENV" "$DATA"
      rm -f "$BIN/priorstates" "$BIN/priorstates-gui"
      echo "PriorStates removed. (Your memory in ~/.priorstates was left intact.)"
      exit 0 ;;
    *) echo "unknown flag: $a"; exit 2 ;;
  esac
done

# ---- find a suitable python (3.10+, ideally with Tkinter for the GUI) ------
# The desktop app is Tkinter; an interpreter without it still runs the CLI +
# cockpit but the GUI won't launch ("Tkinter is not available" → on macOS the app
# just appears to do nothing). Prefer a Tk-capable Python; keep a Tk-less one as
# a fallback.
PY=""; PY_NOTK=""
for c in python3 python3.13 python3.12 python3.11 python3.10; do
  command -v "$c" >/dev/null 2>&1 || continue
  "$c" -c 'import sys;exit(0 if sys.version_info>=(3,10) else 1)' 2>/dev/null || continue
  if "$c" -c 'import tkinter' 2>/dev/null; then PY="$c"; break; fi
  [ -z "$PY_NOTK" ] && PY_NOTK="$c"
done

# macOS: Homebrew's python ships WITHOUT Tk — add it to the chosen interpreter so
# the app actually launches (the common "double-click does nothing" cause).
if [ -z "$PY" ] && [ -n "$PY_NOTK" ] && [ "$(uname -s)" = Darwin ] && command -v brew >/dev/null 2>&1; then
  v="$("$PY_NOTK" -c 'import sys;print("%d.%d"%sys.version_info[:2])' 2>/dev/null)"
  echo "==> adding Tk to Homebrew Python $v (the desktop app needs it)"
  brew install "python-tk@$v" >/dev/null 2>&1 || true
  "$PY_NOTK" -c 'import tkinter' 2>/dev/null && PY="$PY_NOTK"
fi

if [ -z "$PY" ]; then
  # No Tk-capable Python — install a private copy (uv's standalone CPython bundles
  # Tk) so the GUI works without admin. uv is a single static binary; it does not
  # touch the system Python.
  if [ -n "$PY_NOTK" ]; then
    echo "==> no Python with Tkinter found — installing a Tk-capable private copy (no admin needed)"
  else
    echo "==> no Python 3.10+ found — installing a private copy automatically (no admin needed)"
  fi
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
  if ! command -v uv >/dev/null 2>&1; then
    if command -v curl >/dev/null 2>&1; then
      curl -fsSL https://astral.sh/uv/install.sh | sh >/dev/null 2>&1 || true
    elif command -v wget >/dev/null 2>&1; then
      wget -qO- https://astral.sh/uv/install.sh | sh >/dev/null 2>&1 || true
    fi
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
  fi
  if command -v uv >/dev/null 2>&1; then
    uv python install 3.12 >/dev/null 2>&1 || true
    PY="$(uv python find 3.12 2>/dev/null || true)"
  fi
  if [ -z "$PY" ] || [ ! -x "$PY" ]; then
    if [ -n "$PY_NOTK" ]; then
      # Couldn't get a Tk Python; use the Tk-less one so the CLI/cockpit still work.
      PY="$PY_NOTK"
      echo "!! proceeding with $($PY -V) (no Tkinter) — CLI + cockpit work; for the desktop app add Tk:"
      case "$(uname -s)" in
        Darwin) echo "     brew install python-tk@$("$PY" -c 'import sys;print("%d.%d"%sys.version_info[:2])')" ;;
        *)      echo "     sudo apt install python3-tk   (or your distro's python3-tk)" ;;
      esac
    else
      echo "!! could not auto-install Python (no network?). Install Python 3.10+ and re-run:"
      echo "   macOS: brew install python python-tk   •   Linux: sudo apt install python3 python3-venv python3-tk"
      exit 1
    fi
  fi
fi
echo "==> using $($PY -V) at $PY"

# ---- create the venv (fall back to pip --user if venv is unavailable) -----
mkdir -p "$DATA" "$BIN"
if "$PY" -m venv "$VENV" 2>/dev/null; then
  PIP="$VENV/bin/pip"; TARGET_BIN="$VENV/bin"
  "$VENV/bin/python" -m pip install -q --upgrade pip >/dev/null 2>&1 || true
else
  echo "!! python venv unavailable (install python3-venv); falling back to pip --user"
  PIP="$PY -m pip"; TARGET_BIN="$HOME/.local/bin"
fi

# ---- install the bundled wheel (numpy + mcp + onnx from PyPI) --------------
# [mcp] lets agents reach the tools; [onnx] powers semantic recall — without
# them the install is not "install-and-forget", so both ship by default.
# onnxruntime lacks wheels on some platforms → fall back to lite (hashing).
echo "==> installing PriorStates (from bundled wheels)"
if [ "$MODEL" = 1 ]; then
  # shellcheck disable=SC2086
  $PIP install -q --upgrade --find-links "$WHEELS" "priorstates[mcp,onnx]" || {
    echo "!! inference extras failed — retrying lite (hashing recall)"
    MODEL=0
    # shellcheck disable=SC2086
    $PIP install -q --upgrade --find-links "$WHEELS" "priorstates[mcp]"
  }
else
  # shellcheck disable=SC2086
  $PIP install -q --upgrade --find-links "$WHEELS" "priorstates[mcp]"
fi

# ---- launchers in ~/.local/bin --------------------------------------------
cat > "$BIN/priorstates" <<SH
#!/bin/sh
exec "$TARGET_BIN/priorstates" "\$@"
SH
cat > "$BIN/priorstates-gui" <<SH
#!/bin/sh
exec "$TARGET_BIN/priorstates" gui "\$@"
SH
chmod 0755 "$BIN/priorstates" "$BIN/priorstates-gui"

# ---- desktop / app launcher ------------------------------------------------
# One implementation lives in the CLI (`priorstates install-launcher`): a Linux
# .desktop entry + themed icon, or a macOS ~/Applications/PriorStates.app — both
# using the bundled "memory stack" icon. Shared with the curl|sh web installer.
"$TARGET_BIN/priorstates" install-launcher --desktop || true

case ":$PATH:" in *":$BIN:"*) ;; *)
  echo "note: add $BIN to your PATH (e.g. echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc)";;
esac

# ---- init + wire detected agents (install-and-forget) ----------------------
# --global-only: set up the GLOBAL store only. Without it, `init` creates a
# .priorstates PROJECT in the installer's working dir, which the GUI then auto-
# opens as a "project" instead of the default global root.
if [ "$WIRE" = 1 ]; then
  echo "==> initializing + wiring detected AI agents"
  "$TARGET_BIN/priorstates" init --global-only || true
else
  echo "==> initializing (agent wiring skipped: --no-wire)"
  "$TARGET_BIN/priorstates" init --global-only --no-wire || true
fi

# ---- semantic-recall model (default; skip with --lite) ----------------------
if [ "$MODEL" = 1 ]; then
  echo "==> downloading the semantic-recall model (~127 MB; skip with --lite)"
  # Non-fatal: hashing recall keeps working; re-run `priorstates init
  # --download-model` any time.
  "$TARGET_BIN/priorstates" init --download-model --global-only --no-wire || true
fi

cat <<MSG

PriorStates installed.  Next:
  priorstates doctor              # status — which agents are wired
  priorstates cockpit             # local web cockpit → http://127.0.0.1:7700
  priorstates-gui                 # desktop control panel

Restart your agents (Claude Code, Copilot, Cursor, Codex, Gemini, …) to load
the memory + journal tools.
MSG
