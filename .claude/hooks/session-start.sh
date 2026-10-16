#!/bin/bash
set -euo pipefail

# Only run in Claude Code cloud sessions
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

# video-use (browser-use) as a Claude skill
[ -d "$HOME/video-use" ] || git clone https://github.com/browser-use/video-use.git "$HOME/video-use"
pip install -q requests librosa matplotlib pillow numpy faster-whisper gdown
mkdir -p "$HOME/.claude/skills"
ln -sfn "$HOME/video-use" "$HOME/.claude/skills/video-use"

# HyperFrames talking-head-recut skill (installed from current main)
npx --yes hyperframes skills update talking-head-recut
