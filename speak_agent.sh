#!/bin/bash
# Optional, macOS only: read each new agent message aloud with `say`, so a
# participant in human mode can listen instead of reading the screen.
#   ./speak_agent.sh runs/run-<id>
set -u
RUN="${1:?Usage: ./speak_agent.sh runs/run-<id>}"
FILE="$RUN/agent_messages.txt"
command -v say >/dev/null || { echo "This script needs macOS 'say'."; exit 1; }
echo "Speaking new lines of $FILE. Press Ctrl+C to stop."
touch "$FILE"
tail -n 0 -F "$FILE" | while IFS= read -r line; do
  [ -n "$line" ] && say "$line"
done
