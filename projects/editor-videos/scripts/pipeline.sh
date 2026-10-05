#!/usr/bin/env bash
# Orquestra as etapas mecânicas. As decisões editoriais (revisar o EDL,
# desenhar as animações) ficam com o editor entre uma etapa e outra.
#
#   pipeline.sh analisar <video> [<video> ...]   transcreve, empacota, rascunha o EDL
#   pipeline.sh cortar   <edit_dir>              renderiza o corte e prepara o Hyperframes
#   pipeline.sh animar   <edit_dir>              lint + render da composição → final.mp4
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
VIDEO_USE_DIR="${VIDEO_USE_DIR:-$HOME/video-use}"
HF="npx --yes hyperframes@${HF_VERSION:-0.8.134}"
cmd="${1:-}"; shift || true

has_scribe_key() {
  [ -n "${ELEVENLABS_API_KEY:-}" ] || grep -q '^ELEVENLABS_API_KEY=..' "$VIDEO_USE_DIR/.env" 2>/dev/null
}

case "$cmd" in
  analisar)
    [ $# -ge 1 ] || { echo "uso: pipeline.sh analisar <video> [...]" >&2; exit 2; }
    EDIT_DIR="$(cd "$(dirname "$1")" && pwd)/edit"
    mkdir -p "$EDIT_DIR"
    for v in "$@"; do
      if has_scribe_key; then
        python3 "$VIDEO_USE_DIR/helpers/transcribe.py" "$v" --edit-dir "$EDIT_DIR" --language pt
      else
        python3 "$HERE/transcribe_local.py" "$v" --edit-dir "$EDIT_DIR" --model "${WHISPER_MODEL:-medium}"
      fi
    done
    python3 "$VIDEO_USE_DIR/helpers/pack_transcripts.py" --edit-dir "$EDIT_DIR"
    python3 "$HERE/auto_cut.py" "$@" --edit-dir "$EDIT_DIR" ${AUTO_CUT_ARGS:-}
    echo "revise: $EDIT_DIR/takes_packed.md, $EDIT_DIR/cut_report.md, $EDIT_DIR/edl.json"
    ;;
  cortar)
    EDIT_DIR="$(cd "${1:?uso: pipeline.sh cortar <edit_dir>}" && pwd)"
    python3 "$VIDEO_USE_DIR/helpers/render.py" "$EDIT_DIR/edl.json" -o "$EDIT_DIR/cut.mp4" ${RENDER_ARGS:-}
    "$HERE/prepare_hyperframes.sh" "$EDIT_DIR" "$EDIT_DIR/cut.mp4"
    ;;
  animar)
    EDIT_DIR="$(cd "${1:?uso: pipeline.sh animar <edit_dir>}" && pwd)"
    WORK="$EDIT_DIR/hyperframes"
    FPS=$(python3 -c "import json;from fractions import Fraction as F;print(round(float(F(json.load(open('$WORK/metadata.json'))['streams'][0]['r_frame_rate']))))")
    (cd "$WORK" && $HF lint public)
    (cd "$WORK" && $HF render public -o "$EDIT_DIR/final.mp4" --fps "$FPS" --skill=talking-head-recut)
    ffprobe -v error -show_entries format=duration -of csv=p=0 "$EDIT_DIR/final.mp4"
    ;;
  *)
    sed -n '2,8p' "$0"; exit 2 ;;
esac
