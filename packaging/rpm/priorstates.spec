# Distro-agnostic noarch RPM for the open-source PriorStates core
# (RHEL/Rocky/Alma 9+, Fedora). Built by packaging/rpm/build-rpm.sh, which
# stages the payload and passes  --define "ver ..." --define "stagedir ...".
#
# Design: the payload lives in /usr/lib/priorstates (a private dir, including
# the wheel's .dist-info so the priorstates.plugins entry-point seam stays
# discoverable) and /usr/bin/priorstates picks a Python 3.10+ at runtime —
# EL9's system python3 is 3.9, so there the rich dependency below pulls in
# python3.12 instead. One RPM therefore serves EL9 / EL10 / Fedora, whose
# system pythons all differ.

%global __brp_python_bytecompile %{nil}
%global debug_package %{nil}

Name:           priorstates
Version:        %{ver}
Release:        1
Summary:        Shared AI memory, research journal & cockpit for AI agents
License:        Apache-2.0
URL:            https://github.com/zqin2012/priorstates
BuildArch:      noarch
# Manual deps only: the automatic python dependency generator would emit
# python3dist(...) requires bound to the BUILD python, which is wrong here.
AutoReqProv:    no
Requires:       (python3.12 or python3 >= 3.10)
Requires:       (python3.12-numpy if python3.12 else python3-numpy)
Recommends:     (python3.12-pip if python3.12 else python3-pip)
Recommends:     (python3.12-tkinter if python3.12 else python3-tkinter)
Conflicts:      priorstates-hub

%description
PriorStates gives AI agents (Claude Code, VSCode Copilot, Cursor, Codex,
Gemini, ...) a shared local memory, a research journal, runnable-Markdown
(mdlab) and a web cockpit, with a desktop control panel and a CLI. Install
once: every detected agent is wired over MCP and uses the memory
automatically. 100%% local, Apache-2.0.

Installs a desktop launcher in your application menu. Agent (MCP)
integration and semantic recall use extra pip packages (mcp, onnxruntime,
tokenizers).

%install
mkdir -p %{buildroot}
cp -a %{stagedir}/. %{buildroot}/

%files
/usr/lib/priorstates
%{_bindir}/priorstates
%{_bindir}/priorstates-gui
%{_datadir}/applications/priorstates.desktop
%{_datadir}/icons/hicolor/scalable/apps/priorstates.svg
%{_mandir}/man1/priorstates.1*
%{_mandir}/man1/priorstates-gui.1*
%{_datadir}/doc/priorstates

%post
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q /usr/share/applications >/dev/null 2>&1 || :
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -f -t -q /usr/share/icons/hicolor >/dev/null 2>&1 || :
# Pick the same interpreter the launcher will use, so the printed pip line
# targets the right user site (EL9: python3.12; Fedora/EL10: python3).
PSPY=python3
python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1 || PSPY=python3.12
cat <<MSG

PriorStates installed.  Quick start (as your normal user, not root):
  PIP_BREAK_SYSTEM_PACKAGES=1 $PSPY -m pip install --user mcp onnxruntime tokenizers
                                 # agent (MCP) tools + semantic recall libs
                                 # (the env var satisfies PEP 668 on Fedora;
                                 #  harmless elsewhere. --user stays in ~/.local)
  priorstates init               # wire every detected AI agent (once)
  priorstates init --download-model   # semantic recall (~127 MB, local)
  priorstates doctor             # status — which agents are wired
  priorstates cockpit            # local web cockpit
  priorstates-gui                # desktop control panel

Find "PriorStates" in your application menu, too.
MSG
exit 0

%postun
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q /usr/share/applications >/dev/null 2>&1 || :
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -f -t -q /usr/share/icons/hicolor >/dev/null 2>&1 || :
exit 0
