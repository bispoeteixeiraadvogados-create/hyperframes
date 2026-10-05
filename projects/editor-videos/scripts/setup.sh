#!/usr/bin/env bash
# Instala o ambiente do editor (idempotente). Rodar no início de cada sessão
# nova, porque o container da nuvem é efêmero.
#
#   bash projects/editor-videos/scripts/setup.sh
#
# - clona o video-use (browser-use/video-use) em ~/video-use, no commit fixado
# - instala as dependências Python (video-use + faster-whisper)
# - confere ffmpeg, Node 22+ e o CLI do Hyperframes
set -euo pipefail

VIDEO_USE_DIR="${VIDEO_USE_DIR:-$HOME/video-use}"
VIDEO_USE_REF="${VIDEO_USE_REF:-b877063835e6ea6e457124da7e28a0ae26691dc3}"
HF_VERSION="${HF_VERSION:-0.8.134}"

if [ ! -d "$VIDEO_USE_DIR/.git" ]; then
  git clone https://github.com/browser-use/video-use.git "$VIDEO_USE_DIR"
fi
git -C "$VIDEO_USE_DIR" fetch -q origin "$VIDEO_USE_REF" 2>/dev/null || git -C "$VIDEO_USE_DIR" fetch -q origin
git -C "$VIDEO_USE_DIR" checkout -q "$VIDEO_USE_REF"

pip install -q requests librosa matplotlib pillow numpy faster-whisper gdown 2>&1 | grep -v "Running pip as the 'root'" || true

command -v ffmpeg >/dev/null || { echo "ffmpeg ausente: apt-get install -y ffmpeg" >&2; exit 1; }
node -e 'process.exit(Number(process.versions.node.split(".")[0]) < 22 ? 1 : 0)' || { echo "Hyperframes exige Node 22+" >&2; exit 1; }
npx --yes "hyperframes@$HF_VERSION" --version >/dev/null

if [ -n "${ELEVENLABS_API_KEY:-}" ] || grep -q '^ELEVENLABS_API_KEY=..' "$VIDEO_USE_DIR/.env" 2>/dev/null; then
  echo "transcrição: ElevenLabs Scribe (chave encontrada)"
else
  echo "transcrição: faster-whisper local (sem ELEVENLABS_API_KEY)"
fi
echo "video-use: $VIDEO_USE_DIR @ $(git -C "$VIDEO_USE_DIR" rev-parse --short HEAD)"
echo "hyperframes: $(npx --yes "hyperframes@$HF_VERSION" --version)"
