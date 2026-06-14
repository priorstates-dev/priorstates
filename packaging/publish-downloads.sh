#!/usr/bin/env bash
# Upload the built open-source PriorStates installers to the website download
# area (https://priorstates.com/download/). Served from /var/www/priorstates-dl/
# — a separate dir from the static site, so the site's `rsync --delete` deploy
# never wipes these binaries. SHA256SUMS is regenerated on the box over the
# FINAL hosted set (OSS + Hub artifacts share the dir; names are distinct).
#
#   SSH_OPTS='-i ~/.ssh/ydev-ec2.pem' packaging/publish-downloads.sh ubuntu@3.208.145.97
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
HOST="${1:?usage: publish-downloads.sh ubuntu@HOST   (SSH_OPTS for the key)}"
RSH="ssh ${SSH_OPTS:-}"
VER="$(grep -m1 '^version' "$REPO/pyproject.toml" | sed 's/.*"\(.*\)".*/\1/')"

STAGE="$(mktemp -d)"
shopt -s nullglob
# Windows .exe is built on a separate box; the runbook stages it into
# build/windows/ on this host BEFORE publishing (so it ships to /download/ too).
for f in "$REPO"/build/*.tar.gz "$REPO"/build/*.deb "$REPO"/build/*.pkg \
         "$REPO"/build/*.rpm "$REPO"/build/windows/*.exe; do
  cp "$f" "$STAGE/"
done
shopt -u nullglob
[ -n "$(ls -A "$STAGE")" ] || { echo "!! nothing to publish — run packaging/build.sh first"; exit 1; }

# Stable "latest" aliases so download.html links are version-free and never go
# stale. Derived from the current pyproject version, so they always point at this
# build's artifacts. Each missing artifact (e.g. no .exe this run) is skipped.
mk_alias() { [ -f "$STAGE/$1" ] && cp "$STAGE/$1" "$STAGE/$2" && echo "    alias $2 → $1"; }
echo "==> stable aliases (v$VER):"
mk_alias "priorstates_${VER}_all.deb"      "priorstates-latest.deb"          || true
mk_alias "priorstates-${VER}-1.noarch.rpm" "priorstates-latest.noarch.rpm"   || true
mk_alias "priorstates-${VER}.tar.gz"       "priorstates-latest.tar.gz"       || true
mk_alias "priorstates-${VER}.pkg"          "priorstates-latest.pkg"          || true
mk_alias "PriorStates-${VER}-Setup.exe"    "PriorStates-Setup.exe"           || true

echo "==> uploading:"; ls -1 "$STAGE" | sed 's/^/    /'
ssh ${SSH_OPTS:-} "$HOST" "rm -rf /tmp/ps-dl-oss && mkdir -p /tmp/ps-dl-oss"
rsync -az -e "$RSH" "$STAGE"/ "$HOST:/tmp/ps-dl-oss/"
ssh ${SSH_OPTS:-} "$HOST" "sudo bash -s" <<'REMOTE'
set -euo pipefail
sudo mkdir -p /var/www/priorstates-dl
sudo rsync -a /tmp/ps-dl-oss/ /var/www/priorstates-dl/
# regenerate checksums over everything currently hosted
( cd /var/www/priorstates-dl && sudo sh -c 'sha256sum *.tar.gz *.deb *.exe *.pkg *.rpm 2>/dev/null > SHA256SUMS' )
sudo chown -R www-data:www-data /var/www/priorstates-dl
echo "published. hosted artifacts:"; ls -1 /var/www/priorstates-dl
REMOTE
rm -rf "$STAGE"
