#!/bin/zsh
# Reset macOS privacy grants used by FastWhisper Flow for a fresh reinstall test.
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
DOMAIN="gui/$(id -u)"

cd "$DIR"
./flow.sh stop >/dev/null 2>&1 || true
launchctl bootout "$DOMAIN/com.fastwhisper.flow" >/dev/null 2>&1 || true

rm -f "$HOME/Library/LaunchAgents/com.fastwhisper.flow.plist"

for bundle_id in \
  org.python.python \
  com.jtiapbn.fastwhisperflow.toggle \
  com.jtiapbn.fastwhisperflow.installer
do
  tccutil reset Microphone "$bundle_id" >/dev/null 2>&1 || true
  tccutil reset Accessibility "$bundle_id" >/dev/null 2>&1 || true
  tccutil reset AppleEvents "$bundle_id" >/dev/null 2>&1 || true
done

echo "Reset FastWhisper Flow permissions. Reinstall, then add Python.app back to Accessibility when prompted."
