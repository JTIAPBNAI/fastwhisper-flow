#!/bin/zsh
# Rebuild the double-click installer zip with the current source files.
# Uses the existing app bundle in "Installer File/FastWhisperFlow-Installer.zip"
# as the template, refreshes its payload, re-signs (ad-hoc), and re-zips.
#
#   ./build-installer.sh
#
# Then attach the zip to a GitHub release:
#   gh release create vX.Y.Z "Installer File/FastWhisperFlow-Installer.zip" ...
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
ZIP="$DIR/Installer File/FastWhisperFlow-Installer.zip"
APP="Install FastWhisper Flow.app"

[[ -f "$ZIP" ]] || { echo "ERROR: ไม่พบ $ZIP (ต้องมีตัว installer เดิมเป็นแม่แบบ)"; exit 1; }

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

unzip -q "$ZIP"
[[ -d "$APP" ]] || { echo "ERROR: ไม่พบ $APP ใน zip"; exit 1; }

PAYLOAD="$APP/Contents/Resources/payload"
cp "$DIR/flow.py" "$DIR/install.sh" "$DIR/cleanup.py" "$DIR/flow.sh" "$DIR/README.md" "$DIR/VERSION" "$DIR/reset-permissions.sh" "$DIR/requirements.txt" "$PAYLOAD/"
echo "✓ อัปเดต payload: flow.py install.sh cleanup.py flow.sh README.md VERSION reset-permissions.sh requirements.txt"

if [[ -f "$DIR/installer.applescript" ]]; then
  VERSION="$(<"$DIR/VERSION")"
  SCRIPT="$WORK/installer.applescript"
  sed "s/__APP_VERSION__/$VERSION/g" "$DIR/installer.applescript" > "$SCRIPT"
  osacompile -o "$APP/Contents/Resources/Scripts/main.scpt" "$SCRIPT"
  echo "✓ อัปเดต installer UI script"
fi

VERSION="$(<"$DIR/VERSION")"
plutil -replace CFBundleIdentifier -string "com.jtiapbn.fastwhisperflow.installer" "$APP/Contents/Info.plist"
plutil -replace CFBundleShortVersionString -string "$VERSION" "$APP/Contents/Info.plist"
plutil -replace CFBundleVersion -string "$VERSION" "$APP/Contents/Info.plist"
plutil -replace NSMicrophoneUsageDescription -string "FastWhisper Flow needs microphone access for local dictation." "$APP/Contents/Info.plist"
plutil -replace NSAppleEventsUsageDescription -string "FastWhisper Flow uses Apple Events to run the installer and open System Settings." "$APP/Contents/Info.plist"

codesign --force --deep -s - "$APP"
echo "✓ re-sign (ad-hoc)"

rm -f FastWhisperFlow-Installer.zip
zip -qry FastWhisperFlow-Installer.zip "$APP"
mv FastWhisperFlow-Installer.zip "$ZIP"
echo "✓ สร้างใหม่: $ZIP"
