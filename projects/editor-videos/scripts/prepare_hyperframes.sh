#!/usr/bin/env bash
# Prepara a etapa 2 (Hyperframes) a partir do corte do video-use.
#
#   prepare_hyperframes.sh <edit_dir> [cut_video]
#
# Cria <edit_dir>/hyperframes/ no layout do fluxo talking-head-recut:
#   metadata.json, transcript.json (tempo de saída) e public/ com fontes,
#   GSAP e input-video.mp4 recodificado com GOP denso (keyframe a cada frame
#   de segundo), sem o qual o renderer congela o vídeo ao buscar frames.
set -euo pipefail

EDIT_DIR="$(cd "$1" && pwd)"
CUT="${2:-$EDIT_DIR/cut.mp4}"
HERE="$(cd "$(dirname "$0")" && pwd)"
HF_REPO="${HF_REPO:-$(cd "$HERE/../../.." && pwd)}"
SKILL_DIR="$HF_REPO/skills/talking-head-recut"
WORK="$EDIT_DIR/hyperframes"

[ -f "$CUT" ] || { echo "corte não encontrado: $CUT" >&2; exit 1; }
[ -d "$SKILL_DIR/assets" ] || { echo "skill talking-head-recut não encontrada em $SKILL_DIR" >&2; exit 1; }

mkdir -p "$WORK/public/fonts" "$WORK/public/vendor" "$WORK/public/cards"
cp -r --update=none "$SKILL_DIR/assets/fonts/." "$WORK/public/fonts/"
cp --update=none "$SKILL_DIR/assets/vendor/gsap.min.js" "$WORK/public/vendor/"

ffprobe -v error -select_streams v:0 \
  -show_entries stream=width,height,r_frame_rate \
  -show_entries format=duration -of json "$CUT" > "$WORK/metadata.json"

FPS_FRAC=$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of csv=p=0 "$CUT")
FPS=$(python3 -c "from fractions import Fraction as F; print(round(float(F('$FPS_FRAC'))))")

ffmpeg -v error -y -i "$CUT" -c:v libx264 -crf 18 -g "$FPS" -keyint_min "$FPS" \
  -pix_fmt yuv420p -movflags +faststart -c:a aac -b:a 192k "$WORK/public/input-video.mp4"

python3 "$HERE/remap_transcript.py" --edit-dir "$EDIT_DIR" -o "$WORK/transcript.json"

python3 - "$WORK/metadata.json" <<'PY'
import json, sys
m = json.load(open(sys.argv[1]))
s = m["streams"][0]
print(f"pronto: {s['width']}x{s['height']} @ {s['r_frame_rate']}, {float(m['format']['duration']):.2f}s")
PY
echo "trabalho: $WORK"
