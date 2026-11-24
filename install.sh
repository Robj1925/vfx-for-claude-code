#!/bin/sh
# Link this folder's Claude Code skill into ~/.claude/skills so Claude Code can find and run the effects.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/.claude/skills/vfx-for-claude-code"
mkdir -p "$HOME/.claude/skills"
if [ -e "$DEST" ] && [ ! -L "$DEST" ]; then
  echo "$DEST exists and is not a link. Remove it first."; exit 1
fi
ln -sfn "$HERE/skills/vfx-for-claude-code" "$DEST"
# the skill finds the library through this file
printf '%s\n' "$HERE" > "$HERE/skills/vfx-for-claude-code/LIBRARY_PATH"
command -v ffmpeg >/dev/null || echo "Note: ffmpeg not found. Install it: brew install ffmpeg"
python3 -c "import numpy, PIL" 2>/dev/null || echo "Note: run pip3 install -r requirements.txt"
echo "Installed. Restart Claude Code, then ask: which effects do you have for a hook?"
