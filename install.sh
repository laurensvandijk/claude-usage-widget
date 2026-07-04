#!/usr/bin/env bash
# Installer for the Claude usage Übersicht widget.
# Symlinks this folder into Übersicht's widgets directory and (re)starts Übersicht.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WIDGETS_DIR="$HOME/Library/Application Support/Übersicht/widgets"
LINK="$WIDGETS_DIR/claude-usage"

# 1. Übersicht present?
if [ ! -d "/Applications/Übersicht.app" ]; then
  echo "Übersicht is not installed."
  echo "Install it first:  brew install --cask ubersicht"
  exit 1
fi

# 2. Claude Code login present?
if ! security find-generic-password -s "Claude Code-credentials" -w >/dev/null 2>&1; then
  echo "No Claude Code login found in your Keychain."
  echo "Log in first by running:  claude   (and completing the sign-in)"
  exit 1
fi

# 3. Link the widget folder in.
mkdir -p "$WIDGETS_DIR"
ln -sfn "$REPO_DIR" "$LINK"
echo "Linked widget -> $LINK"

# 4. Sanity-check the data script.
echo "Testing usage fetch..."
if python3 "$REPO_DIR/claude-usage.py" | grep -q '"ok": true'; then
  echo "  OK — usage data fetched."
else
  echo "  Warning: the script did not return usage data. Make sure you're logged in with 'claude'."
fi

# 5. (Re)start Übersicht so it picks up the widget.
osascript -e 'quit app "Übersicht"' >/dev/null 2>&1 || true
sleep 1
open -a "Übersicht"
echo "Done. The widget should appear on your desktop (top-right by default)."
echo "If a firewall prompts, allow api.anthropic.com and platform.claude.com."
