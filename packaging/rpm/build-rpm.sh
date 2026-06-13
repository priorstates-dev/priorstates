#!/usr/bin/env bash
# Build a distro-agnostic noarch .rpm for the open-source PriorStates core
# (RHEL/Rocky/Alma 9+, Fedora) with a desktop launcher, man pages and the
# CLI/GUI commands — the RPM counterpart of packaging/deb/build-deb.sh.
#
# The wheel is unzipped into /usr/lib/priorstates (a private dir, so we don't
# bind to any one python's site-packages); /usr/bin/priorstates picks a
# Python 3.10+ at runtime. EL9's system python3 is 3.9 — the spec's rich
# dependency pulls python3.12 there. See packaging/rpm/priorstates.spec.
#
#   packaging/rpm/build-rpm.sh        # → build/priorstates-<ver>-1.noarch.rpm
#
# Uses rpmbuild if installed; otherwise builds inside a rockylinux:9 docker
# container (staging always happens on the host). No root needed locally.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
VER="$(grep -m1 '^version' "$REPO/pyproject.toml" | sed 's/.*"\(.*\)".*/\1/')"
OUT="$REPO/build"
RTOP="$OUT/rpm"
STAGE="$RTOP/stage"
WH="$OUT/wheels"

echo "==> building priorstates ${VER} (noarch rpm)"
rm -rf "$RTOP"; mkdir -p "$STAGE" "$WH" "$RTOP/top"

# ---- payload: build the wheel (reuse build.sh's if present), unzip ----------
ls "$WH/priorstates-$VER"-*.whl >/dev/null 2>&1 || {
  echo "==> building wheel"
  python3 -m pip wheel --no-deps -w "$WH" "$REPO" >/dev/null
}
mkdir -p \
  "$STAGE/usr/lib/priorstates" \
  "$STAGE/usr/bin" \
  "$STAGE/usr/share/applications" \
  "$STAGE/usr/share/icons/hicolor/scalable/apps" \
  "$STAGE/usr/share/man/man1" \
  "$STAGE/usr/share/doc/priorstates"
PL="$STAGE/usr/lib/priorstates"
for whl in "$WH/priorstates-$VER"-*.whl; do
  echo "    unpacking $(basename "$whl")"
  python3 - "$whl" "$PL" <<'PY'
import sys, zipfile
zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])
PY
done
find "$PL" \( -name '__pycache__' -o -name '*.pyc' -o -name '*.psmem' \) -prune -exec rm -rf {} + 2>/dev/null || true
find "$PL" -name 'RECORD' -path '*.dist-info/*' -delete 2>/dev/null || true

# ---- CLI + GUI launchers (runtime interpreter pick) -------------------------
cat > "$STAGE/usr/bin/priorstates" <<'SH'
#!/bin/sh
# PriorStates launcher: pick a Python 3.10+ — preferring one that already has
# numpy so the interpreter matches the distro numpy package the RPM pulled in.
# (RHEL/Rocky/Alma 9: system python3 is 3.9; the RPM installs python3.12.)
PY=""
for c in python3 python3.13 python3.12 python3.11 python3.10; do
  command -v "$c" >/dev/null 2>&1 || continue
  "$c" -c 'import sys, numpy; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null && { PY="$c"; break; }
done
if [ -z "$PY" ]; then
  for c in python3 python3.13 python3.12 python3.11 python3.10; do
    command -v "$c" >/dev/null 2>&1 || continue
    "$c" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null && { PY="$c"; break; }
  done
fi
if [ -z "$PY" ]; then
  echo "priorstates: no Python 3.10+ found." >&2
  echo "  RHEL/Rocky/Alma 9:  sudo dnf install python3.12 python3.12-numpy" >&2
  echo "  Fedora:             sudo dnf install python3 python3-numpy" >&2
  exit 1
fi
PYTHONPATH="/usr/lib/priorstates${PYTHONPATH:+:$PYTHONPATH}" exec "$PY" -m priorstates "$@"
SH
cat > "$STAGE/usr/bin/priorstates-gui" <<'SH'
#!/bin/sh
exec /usr/bin/priorstates gui "$@"
SH
chmod 0755 "$STAGE/usr/bin/priorstates" "$STAGE/usr/bin/priorstates-gui"

# ---- desktop launcher + icon (same as the .deb) -----------------------------
cat > "$STAGE/usr/share/applications/priorstates.desktop" <<'DESK'
[Desktop Entry]
Type=Application
Name=PriorStates
GenericName=AI memory & journal cockpit
Comment=Shared local memory, research journal, mdlab and the cockpit for your AI agents
Exec=priorstates-gui
Icon=priorstates
Terminal=false
Categories=Development;Utility;
Keywords=AI;memory;journal;claude;codex;gemini;copilot;cursor;mcp;
StartupNotify=true
DESK

cat > "$STAGE/usr/share/icons/hicolor/scalable/apps/priorstates.svg" <<'SVG'
<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">
  <rect width="128" height="128" rx="24" fill="#0d1117"/>
  <circle cx="64" cy="58" r="30" fill="none" stroke="#58a6ff" stroke-width="6"/>
  <circle cx="64" cy="58" r="12" fill="#3fb950"/>
  <line x1="86" y1="80" x2="104" y2="98" stroke="#58a6ff" stroke-width="8" stroke-linecap="round"/>
</svg>
SVG

# ---- man pages (same content as the .deb; rpmbuild's brp-compress gzips) ----
DATE_MAN="$(date +%Y-%m-%d)"
cat > "$STAGE/usr/share/man/man1/priorstates.1" <<MAN
.TH PRIORSTATES 1 "$DATE_MAN" "priorstates $VER" "User Commands"
.SH NAME
priorstates \- local AI memory, research journal, mdlab and cockpit
.SH SYNOPSIS
.B priorstates
.I command
.RI [ options ]
.SH DESCRIPTION
PriorStates gives AI agents (Claude Code, VSCode Copilot, Cursor, Codex,
Gemini, ...) a shared local memory, a research journal, runnable-Markdown
(mdlab) and a web cockpit \- all on this machine, no cloud calls.
.SH COMMANDS
.TP
.B init
Initialize the data dirs and wire every detected AI agent (use
\fB--no-wire\fR to skip wiring).
.TP
.B agents \fR{install,uninstall,status}\fR
Wire / unwire the MCP server and protocol block per agent.
.TP
.B memory / journal
Manage memories and journal entries from the CLI.
.TP
.B cockpit
Launch the local web cockpit.
.TP
.B gui
Launch the desktop control panel.
.TP
.B doctor
Report configuration and agent status.
.SH SEE ALSO
.BR priorstates-gui (1)
MAN
cat > "$STAGE/usr/share/man/man1/priorstates-gui.1" <<MAN
.TH PRIORSTATES-GUI 1 "$DATE_MAN" "priorstates $VER" "User Commands"
.SH NAME
priorstates-gui \- desktop control panel for PriorStates
.SH SYNOPSIS
.B priorstates-gui
.SH DESCRIPTION
Opens the control panel to manage memory, the journal, agent wiring and mdlab.
Equivalent to \fBpriorstates gui\fR. Requires tkinter (python3-tkinter /
python3.12-tkinter).
.SH SEE ALSO
.BR priorstates (1)
MAN

# ---- docs -------------------------------------------------------------------
cp "$REPO/README.md" "$STAGE/usr/share/doc/priorstates/README.md" 2>/dev/null || true

# ---- rpmbuild (local if present, else rockylinux:9 container) ---------------
SPEC="$HERE/priorstates.spec"
if command -v rpmbuild >/dev/null 2>&1; then
  echo "==> rpmbuild (local)"
  rpmbuild -bb --quiet \
    --define "_topdir $RTOP/top" \
    --define "ver $VER" \
    --define "stagedir $STAGE" \
    "$SPEC"
else
  echo "==> rpmbuild (rockylinux:9 container — no local rpmbuild)"
  docker run --rm -v "$REPO:/repo" rockylinux:9 bash -c "
    set -e
    dnf install -y -q rpm-build >/dev/null
    rpmbuild -bb --quiet \
      --define '_topdir /repo/build/rpm/top' \
      --define 'ver $VER' \
      --define 'stagedir /repo/build/rpm/stage' \
      /repo/packaging/rpm/priorstates.spec
    chown -R $(id -u):$(id -g) /repo/build/rpm
  "
fi

RPM="$RTOP/top/RPMS/noarch/priorstates-$VER-1.noarch.rpm"
[ -f "$RPM" ] || { echo "!! rpm not produced"; exit 1; }
cp "$RPM" "$OUT/"
echo "built: $OUT/$(basename "$RPM")"
echo
echo "Install with:   sudo dnf install ./$(basename "$RPM")"
