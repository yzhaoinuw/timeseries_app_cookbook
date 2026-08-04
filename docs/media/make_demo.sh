#!/bin/bash
# Rebuild every demo asset from a raw screen recording of the app.
#
#   ./make_demo.sh [path/to/raw_recording.mov]
#
# Produces, next to the raw recording:
#   <name>_captioned.mp4  full-res captioned master (source of truth for exports)
#   <name>_readme.mp4     downscaled export, the file uploaded to GitHub
# and, in this directory:
#   ts_app_demo.gif       the hero GIF committed to the repo
#
# Needs ffmpeg on PATH and a Python with Pillow (see README.md in this folder).

set -euo pipefail

SRC=${1:-$HOME/Desktop/ts_app_demo.mov}
PY=${PY:-python3}

HERE=$(cd "$(dirname "$0")" && pwd)
SRC_DIR=$(cd "$(dirname "$SRC")" && pwd)
STEM=$(basename "$SRC")
STEM=${STEM%.*}

MASTER="$SRC_DIR/${STEM}_captioned.mp4"
EXPORT="$SRC_DIR/${STEM}_readme.mp4"
GIF="$HERE/ts_app_demo.gif"

# Hero GIF window and encode settings. 800px / 10fps / 48 colors lands ~3MB for
# a 21s clip; GitHub's image proxy gets unhappy well before 10MB, so keep headroom.
GIF_START=14
GIF_DUR=21
GIF_W=800
GIF_FPS=10
GIF_COLORS=48

[ -f "$SRC" ] || { echo "raw recording not found: $SRC" >&2; exit 1; }

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

# 1. Caption banners. Local ffmpeg (Homebrew) is built without libass/freetype,
#    so there is no `ass`/`drawtext` filter — captions are transparent PNGs
#    composited with the core `overlay` filter instead.
echo "==> rendering caption banners"
(cd "$WORK" && "$PY" "$HERE/make_banners.py")

# 2. Composite the banners onto the raw recording at full resolution.
echo "==> compositing captions -> $MASTER"
GRAPH=$(cat "$WORK/overlay_graph.txt")
LAST=$(ls "$WORK"/cap_*.png | wc -l | tr -d ' ')
INPUTS=()
for n in $(seq 1 "$LAST"); do INPUTS+=(-i "$WORK/cap_${n}.png"); done
ffmpeg -y -loglevel error -i "$SRC" "${INPUTS[@]}" \
  -filter_complex "$GRAPH" -map "[v${LAST}]" \
  -c:v libx264 -crf 18 -preset medium -pix_fmt yuv420p -movflags +faststart -an \
  "$MASTER"

# 3. Downscaled export — this is the file to drag-drop into the GitHub web
#    editor to mint the user-attachment URL the README's Demo section uses.
echo "==> exporting README mp4 -> $EXPORT"
ffmpeg -y -loglevel error -i "$MASTER" -vf "fps=15,scale=1600:-2" \
  -c:v libx264 -crf 24 -preset slower -pix_fmt yuv420p -movflags +faststart -an \
  "$EXPORT"

# 4. Hero GIF — two-pass palette, the only way to keep a noisy signal trace
#    from blowing past the size budget.
echo "==> building hero GIF -> $GIF"
ffmpeg -y -loglevel error -ss $GIF_START -t $GIF_DUR -i "$MASTER" \
  -vf "fps=${GIF_FPS},scale=${GIF_W}:-1:flags=lanczos,palettegen=max_colors=${GIF_COLORS}:stats_mode=diff" \
  "$WORK/palette.png"
ffmpeg -y -loglevel error -ss $GIF_START -t $GIF_DUR -i "$MASTER" -i "$WORK/palette.png" \
  -lavfi "fps=${GIF_FPS},scale=${GIF_W}:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle" \
  "$GIF"

echo
echo "done:"
du -h "$MASTER" "$EXPORT" "$GIF"
