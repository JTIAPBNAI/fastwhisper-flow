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
cp "$DIR/flow.py" "$DIR/install.sh" "$DIR/cleanup.py" "$DIR/flow.sh" "$DIR/README.md" "$PAYLOAD/"
echo "✓ อัปเดต payload: flow.py install.sh cleanup.py flow.sh README.md"

codesign --force --deep -s - "$APP"
echo "✓ re-sign (ad-hoc)"

rm -f FastWhisperFlow-Installer.zip
zip -qry FastWhisperFlow-Installer.zip "$APP"
mv FastWhisperFlow-Installer.zip "$ZIP"
echo "✓ สร้างใหม่: $ZIP"
