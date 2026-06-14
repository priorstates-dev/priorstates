#!/usr/bin/env bash
# Build a macOS installer package (flat .pkg) for the open-source PriorStates
# core. **No admin password** — it's an "install for me only" (home-domain) pkg:
# it stages the bundled wheels + install.sh under ~/Library/PriorStates and its
# postinstall (running as the user) runs install.sh — the same per-user venv
# install as the tarball, but double-clickable in Installer.app.
#
# install.sh creates the CLI launchers AND a ~/Applications/PriorStates.app
# bundle (per-user, no admin), so after install the app shows up in Launchpad /
# Spotlight / Finder. (Generic app icon for now — no bundled .icns.)
#
#   packaging/macos/build-pkg.sh        # → build/priorstates-<ver>.pkg
#
# Builds on macOS (pkgbuild/productbuild) OR on Linux with xar + mkbom
# (bomutils) on PATH or in ~/opt/pkgtools/bin — see
# https://github.com/hogliux/bomutils for the flat-package layout.
# Signs + notarizes when PRIORSTATES_PKG_SIGN_ID (and a notary profile) are set —
# CI sets them, so released pkgs are signed + notarized (double-click to install).
# Without them (e.g. a plain local build) the pkg is unsigned (right-click → Open).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
VER="$(grep -m1 '^version' "$REPO/pyproject.toml" | sed 's/.*"\(.*\)".*/\1/')"
ID="com.priorstates.priorstates"
LOC="/Library/PriorStates"
OUT="$REPO/build"
WORK="$OUT/macos"
PKG="$OUT/priorstates-$VER.pkg"

export PATH="$PATH:$HOME/opt/pkgtools/bin"

echo "==> staging payload ($VER)"
rm -rf "$WORK"; mkdir -p "$WORK/payload/wheels" "$WORK/scripts" "$WORK/flat"
if ls "$OUT"/wheels/*.whl >/dev/null 2>&1; then
  cp "$OUT"/wheels/*.whl "$WORK/payload/wheels/"
else
  python3 -m pip wheel --no-deps -w "$WORK/payload/wheels" "$REPO" >/dev/null
fi
cp "$HERE/../unix/install.sh" "$WORK/payload/install.sh"
cp "$REPO/README.md" "$WORK/payload/README.md" 2>/dev/null || true
cat > "$WORK/payload/UNINSTALL.txt" <<TXT
To remove PriorStates (no admin needed):
  sh ~/Library/PriorStates/install.sh --uninstall   # unwire agents + remove the per-user install
  rm -rf ~/Library/PriorStates                       # remove these installer files
  pkgutil --forget $ID 2>/dev/null || true
Your memory in ~/.priorstates is always left intact.
TXT
# normalize perms (the build umask leaks into cpio/bom otherwise)
find "$WORK/payload" -type d -exec chmod 0755 {} +
find "$WORK/payload" -type f -exec chmod 0644 {} +
chmod 0755 "$WORK/payload/install.sh"

# postinstall runs as the USER (install-for-me-only). $2 is the resolved install
# destination (~/Library/PriorStates). PATH is widened because the installer env
# misses brew / python.org locations. (Stays correct if some flow runs it as root.)
cat > "$WORK/scripts/postinstall" <<'POST'
#!/bin/bash
set -u
TARGET="${2:-$HOME/Library/PriorStates}"
WIDE_PATH="/usr/local/bin:/opt/homebrew/bin:/Library/Frameworks/Python.framework/Versions/Current/bin:/usr/bin:/bin:/usr/sbin:/sbin"
RUN=()
if [ "$(id -u)" = 0 ]; then
  CU="$(/usr/bin/stat -f%Su /dev/console 2>/dev/null || echo "")"
  [ -n "$CU" ] && [ "$CU" != root ] && RUN=(/usr/bin/sudo -u "$CU" -H)
fi
echo "[priorstates] per-user setup from $TARGET"
if "${RUN[@]}" /usr/bin/env PATH="$WIDE_PATH" /bin/bash "$TARGET/install.sh"; then
  echo "[priorstates] setup complete"
else
  echo "[priorstates] install.sh did not finish — files are in $TARGET"
  # install.sh provisions its own Python (via uv) when none is present, so this
  # only fires on a genuine failure — most likely no internet during setup.
  "${RUN[@]}" /usr/bin/osascript -e "display dialog \"PriorStates files were copied, but setup did not finish (no internet connection?).\n\nReconnect, then run:\n\n  sh '$TARGET/install.sh'\" buttons {\"OK\"} default button 1 with title \"PriorStates\"" >/dev/null 2>&1 || true
fi
exit 0
POST
chmod 0755 "$WORK/scripts/postinstall"

NF="$(find "$WORK/payload" | wc -l | tr -d ' ')"
KB="$(du -sk "$WORK/payload" | cut -f1)"

write_distribution() {
  cat > "$1" <<DIST
<?xml version="1.0" encoding="utf-8"?>
<installer-gui-script minSpecVersion="1">
  <title>PriorStates $VER</title>
  <!-- Install for me only: home-domain → NO admin password; lands in ~/Library. -->
  <options customize="never" require-scripts="true"/>
  <domains enable_anywhere="false" enable_currentUserHome="true" enable_localSystem="false"/>
  <volume-check><allowed-os-versions><os-version min="11.0"/></allowed-os-versions></volume-check>
  <choices-outline><line choice="default"><line choice="ps"/></line></choices-outline>
  <choice id="default"/>
  <choice id="ps" visible="false"><pkg-ref id="$ID"/></choice>
  <pkg-ref id="$ID" version="$VER" onConclusion="none" installKBytes="$KB">#priorstates-core.pkg</pkg-ref>
</installer-gui-script>
DIST
}

if command -v pkgbuild >/dev/null 2>&1 && command -v productbuild >/dev/null 2>&1; then
  # native macOS toolchain
  echo "==> pkgbuild + productbuild"
  # --ownership recommended: the installer assigns ownership to the installing
  # user (correct for a home-domain, no-admin install).
  pkgbuild --root "$WORK/payload" --scripts "$WORK/scripts" \
    --identifier "$ID" --version "$VER" --install-location "$LOC" \
    --ownership recommended \
    "$WORK/priorstates-core.pkg" >/dev/null
  write_distribution "$WORK/Distribution"
  # Sign with a Developer ID Installer identity if provided, so Gatekeeper
  # accepts it without the right-click→Open dance. Set:
  #   PRIORSTATES_PKG_SIGN_ID="Developer ID Installer: NAME (TEAMID)"
  # Find the exact string with: security find-identity -v | grep "Developer ID Installer"
  if [ -n "${PRIORSTATES_PKG_SIGN_ID:-}" ]; then
    echo "==> signing installer as: $PRIORSTATES_PKG_SIGN_ID"
    productbuild --distribution "$WORK/Distribution" --package-path "$WORK" \
      --sign "$PRIORSTATES_PKG_SIGN_ID" "$PKG" >/dev/null
  else
    echo "==> (unsigned — set PRIORSTATES_PKG_SIGN_ID to sign)"
    productbuild --distribution "$WORK/Distribution" --package-path "$WORK" "$PKG" >/dev/null
  fi
  # Notarize + staple if a stored notarytool credential profile is provided, so
  # the pkg passes Gatekeeper with no warning at all. One-time setup on the Mac:
  #   xcrun notarytool store-credentials priorstates-notary \
  #       --apple-id <id> --team-id <TEAMID> --password <app-specific-password>
  # then build with PRIORSTATES_NOTARY_PROFILE=priorstates-notary.
  if [ -n "${PRIORSTATES_PKG_SIGN_ID:-}" ] && [ -n "${PRIORSTATES_NOTARY_PROFILE:-}" ]; then
    # --timeout caps the wait so a stuck/backlogged Apple notarization can never
    # hang the build indefinitely; on timeout/failure we keep the SIGNED .pkg.
    echo "==> notarizing (notarytool --wait, up to ${PRIORSTATES_NOTARY_TIMEOUT:-30m})..."
    if xcrun notarytool submit "$PKG" --keychain-profile "$PRIORSTATES_NOTARY_PROFILE" \
         --wait --timeout "${PRIORSTATES_NOTARY_TIMEOUT:-30m}"; then
      xcrun stapler staple "$PKG" && echo "==> notarized + stapled"
    else
      echo "!! notarization did not complete (timeout or rejection) — shipping the SIGNED .pkg"
      echo "   un-stapled; check status later: xcrun notarytool history --keychain-profile $PRIORSTATES_NOTARY_PROFILE"
    fi
  fi
else
  # Linux: hand-assemble the flat package with xar + mkbom + cpio
  for t in xar mkbom cpio gzip; do
    command -v "$t" >/dev/null 2>&1 || { echo "!! $t not found — need xar + bomutils (see header)"; exit 1; }
  done
  echo "==> assembling flat package (xar + mkbom)"
  COMP="$WORK/flat/priorstates-core.pkg"
  mkdir -p "$COMP"
  cat > "$COMP/PackageInfo" <<PI
<?xml version="1.0" encoding="utf-8"?>
<pkg-info format-version="2" identifier="$ID" version="$VER" install-location="$LOC" auth="none" overwrite-permissions="true">
  <payload installKBytes="$KB" numberOfFiles="$NF"/>
  <scripts><postinstall file="./postinstall"/></scripts>
</pkg-info>
PI
  ( cd "$WORK/payload" && find . | cpio -o --format odc --owner 0:80 2>/dev/null | gzip -9c ) > "$COMP/Payload"
  ( cd "$WORK/scripts" && find . | cpio -o --format odc --owner 0:80 2>/dev/null | gzip -9c ) > "$COMP/Scripts"
  mkbom -u 0 -g 80 "$WORK/payload" "$COMP/Bom"
  write_distribution "$WORK/flat/Distribution"
  rm -f "$PKG"
  ( cd "$WORK/flat" && xar --compression none -cf "$PKG" Distribution priorstates-core.pkg )
fi

echo "built: $PKG ($(du -h "$PKG" | cut -f1 | tr -d ' '))"
