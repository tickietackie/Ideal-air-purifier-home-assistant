#!/usr/bin/env bash
# Renders the brand SVGs in this directory into the PNG set required by
# Home Assistant (local brand images, HA 2026.3+ and HACS).
#
# Output: custom_components/idealpro/brand/
#   icon.png / icon@2x.png            256x256 / 512x512
#   logo.png / logo@2x.png            h 256 / h 512
#   dark_logo.png / dark_logo@2x.png  h 256 / h 512
#
# Requires macOS `sips` (rasterizes SVG via CoreGraphics). Run from anywhere:
#   assets/brand/render.sh
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$DIR/../.." && pwd)"
OUT="$REPO/custom_components/idealpro/brand"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$OUT"

scale_svg() {
  # scale_svg <src.svg> <factor> <dst.svg>
  local src="$1" factor="$2" dst="$3"
  local w h
  read -r w h < <(sed -n 's/.*width="\([0-9]*\)" height="\([0-9]*\)".*/\1 \2/p' "$src" | head -1)
  sed "s/width=\"$w\" height=\"$h\"/width=\"$((w * factor))\" height=\"$((h * factor))\"/" "$src" > "$dst"
}

sips -s format png "$DIR/icon.svg" --out "$OUT/icon@2x.png" >/dev/null
sips -z 256 256 "$OUT/icon@2x.png" --out "$OUT/icon.png" >/dev/null

for name in logo dark_logo; do
  sips -s format png "$DIR/$name.svg" --out "$OUT/$name.png" >/dev/null
  scale_svg "$DIR/$name.svg" 2 "$TMP/$name@2x.svg"
  sips -s format png "$TMP/$name@2x.svg" --out "$OUT/$name@2x.png" >/dev/null
done

echo "Wrote:"
for f in "$OUT"/*.png; do
  printf '  %-28s %s\n' "$(basename "$f")" "$(sips -g pixelWidth -g pixelHeight "$f" | tail -2 | tr -d ' ' | tr '\n' ' ')"
done
