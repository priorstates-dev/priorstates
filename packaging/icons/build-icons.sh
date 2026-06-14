#!/usr/bin/env bash
# Regenerate every raster icon from the canonical SVG.
#
# Source of truth: priorstates/assets/icon.svg  (the "memory stack" mark).
# Outputs (committed, so installs need no rasterizer at build/runtime):
#   priorstates/assets/icon.png         256px  — Tk GUI window iconphoto
#   priorstates/assets/PriorStates.ico  multi  — Windows installer + shortcuts
#   priorstates/assets/PriorStates.icns multi  — macOS .app bundle
#
# Requires ImageMagick (`convert`) + python3. Run from anywhere.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ASSETS="$(cd "$HERE/../../priorstates/assets" && pwd)"
SVG="$ASSETS/icon.svg"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

command -v convert >/dev/null || { echo "need ImageMagick (convert)"; exit 1; }

# High-density base render, then crisp downscales.
convert -background none -density 384 "$SVG" -resize 1024x1024 "$TMP/icon_1024.png"
for s in 512 256 128 64 48 32 16; do
  convert "$TMP/icon_1024.png" -resize ${s}x${s} "$TMP/icon_$s.png"
done

cp "$TMP/icon_256.png" "$ASSETS/icon.png"
convert "$TMP/icon_16.png" "$TMP/icon_32.png" "$TMP/icon_48.png" \
        "$TMP/icon_64.png" "$TMP/icon_128.png" "$TMP/icon_256.png" "$ASSETS/PriorStates.ico"

# ImageMagick's ICNS writer is unreliable; pack the container ourselves so macOS
# gets a real multi-resolution icon (PNG-encoded entries, modern OSTypes).
python3 - "$TMP" "$ASSETS/PriorStates.icns" <<'PY'
import struct, sys, pathlib
tmp, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
mapping = [("ic07",128),("ic08",256),("ic09",512),("ic10",1024),
           ("ic11",32),("ic12",64),("ic13",256),("ic14",512)]
chunks = b""
for ostype, size in mapping:
    data = (tmp / f"icon_{size}.png").read_bytes()
    chunks += ostype.encode("ascii") + struct.pack(">I", len(data)+8) + data
out.write_bytes(b"icns" + struct.pack(">I", len(chunks)+8) + chunks)
print("icns:", out, len(mapping), "entries")
PY
# Inno Setup reads the .ico from beside each .iss (SourceDir = script dir), so
# keep those copies in sync with the canonical asset.
for d in "$HERE/../windows" "$HERE/../../../priorstates-hub/packaging/windows"; do
  [ -d "$d" ] && cp "$ASSETS/PriorStates.ico" "$d/PriorStates.ico" && echo "synced ico → $d"
done

echo "icons regenerated in $ASSETS"
