#!/bin/zsh
# FastWhisper Flow installer — run once on a new Mac:  ./install.sh
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

STAGE="${1:-all}"   # all | deps | model | apps  (stages let the GUI installer show progress)
if [[ -f VERSION ]]; then
  APP_VERSION="$(<VERSION)"
else
  APP_VERSION="dev"
fi

echo "== FastWhisper Flow v$APP_VERSION installer ($STAGE) =="

# 1. checks
[[ "$(uname -m)" == "arm64" ]] || { echo "ERROR: ต้องเป็น Mac ชิป Apple Silicon (M1 ขึ้นไป)"; exit 1; }
PYTHON_VERSION="3.13.14"
PYTHON_PKG_URL="https://www.python.org/ftp/python/$PYTHON_VERSION/python-$PYTHON_VERSION-macos11.pkg"
PYTHON_PKG_SHA256="8e58affb218c155a1dfdc27b291f817129669f8760e7a297adb2e4439ba5d2e8"

is_python313() {
  [[ -x "$1" ]] && "$1" -c '
import os, sys
python_app = os.path.join(sys.base_prefix, "Resources", "Python.app")
raise SystemExit(sys.version_info[:2] != (3, 13) or not os.path.isdir(python_app))
' 2>/dev/null
}

find_python313() {
  local cand name
  # Prefer framework builds because their Python.app can be granted Accessibility.
  for cand in \
    /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 \
    /opt/homebrew/opt/python@3.13/bin/python3.13 \
    /opt/homebrew/bin/python3.13; do
    if is_python313 "$cand"; then
      print -r -- "$cand"
      return 0
    fi
  done
  for name in python3.13 python3; do
    cand=$(command -v "$name" 2>/dev/null || true)
    if [[ -n "$cand" ]] && is_python313 "$cand"; then
      print -r -- "$cand"
      return 0
    fi
  done
  return 1
}

install_python313() {
  local pkg actual_sha
  pkg=$(mktemp -t fastwhisper-python)
  echo "-- ไม่พบ Python 3.13 — กำลังดาวน์โหลด Python $PYTHON_VERSION จาก python.org (~68 MB)..."
  curl --fail --location --proto '=https' --tlsv1.2 --progress-bar "$PYTHON_PKG_URL" -o "$pkg"
  actual_sha=$(shasum -a 256 "$pkg" | awk '{print $1}')
  if [[ "$actual_sha" != "$PYTHON_PKG_SHA256" ]]; then
    rm -f -- "$pkg"
    echo "ERROR: checksum ของ Python installer ไม่ถูกต้อง — ยกเลิกเพื่อความปลอดภัย"
    return 1
  fi

  echo "-- ติดตั้ง Python $PYTHON_VERSION (macOS จะถามรหัสผ่านผู้ดูแลระบบ)..."
  if [[ $EUID -eq 0 ]]; then
    /usr/sbin/installer -pkg "$pkg" -target /
  else
    /usr/bin/osascript - "$pkg" <<'APPLESCRIPT'
on run argv
  set pkgPath to item 1 of argv
  do shell script "/usr/sbin/installer -pkg " & quoted form of pkgPath & " -target /" with administrator privileges
end run
APPLESCRIPT
  fi
  rm -f -- "$pkg"
}

PYBIN=$(find_python313 || true)
if [[ -z "$PYBIN" ]]; then
  install_python313
  PYBIN=$(find_python313 || true)
fi
[[ -n "$PYBIN" ]] || { echo "ERROR: ติดตั้ง Python 3.13 ไม่สำเร็จ"; exit 1; }
echo "✓ Apple Silicon + $($PYBIN --version) ($PYBIN)"

# 2. virtualenv + dependencies
if [[ "$STAGE" == "all" || "$STAGE" == "deps" ]]; then
  if [[ ! -x .venv/bin/python ]] || ! is_python313 .venv/bin/python; then
    [[ ! -e .venv ]] || rm -rf -- "$DIR/.venv"
    echo "-- สร้าง Python 3.13 virtualenv..."
    "$PYBIN" -m venv .venv
  fi
  echo "-- ติดตั้งไลบรารี Python ที่จำเป็น..."
  .venv/bin/pip install -q --upgrade pip
  if [[ -f requirements.txt ]]; then
    .venv/bin/pip install -q -r requirements.txt
  else
    .venv/bin/pip install -q mlx-whisper==0.4.3 sounddevice==0.5.5 pynput==1.8.2 rumps==0.4.0 pyobjc-framework-AVFoundation==12.2.1 pyobjc-framework-ApplicationServices==12.2.1 pyobjc-framework-Quartz==12.2.1
  fi
fi
echo "✓ dependencies พร้อม"

[[ "$STAGE" == "deps" ]] && exit 0

# 3. pre-download the Thai model (~1.5GB) so first use is instant
if [[ "$STAGE" == "all" || "$STAGE" == "model" ]]; then
echo "-- ดาวน์โหลดโมเดลภาษาไทย (~1.5GB ครั้งเดียว อาจใช้เวลาสักครู่)..."
.venv/bin/python - <<'EOF'
import numpy as np, mlx_whisper
mlx_whisper.transcribe(np.zeros(16000, dtype=np.float32),
    path_or_hf_repo="tawankri/distill-thonburian-whisper-large-v3-mlx", language="th")
print("✓ โมเดลพร้อมใช้งาน")
EOF
fi
[[ "$STAGE" == "model" ]] && exit 0

# 3.5 optional: BlackHole driver for system-audio capture (Right ⌘ + Shift)
if ! system_profiler SPAudioDataType 2>/dev/null | grep -q "BlackHole 2ch"; then
  if command -v brew >/dev/null; then
    echo ""
    read "ans?ติดตั้ง BlackHole สำหรับถอดเสียงจากระบบ (Right ⌘ + Shift) ด้วยไหม? [y/N] "
    if [[ "$ans" == [yY]* ]]; then
      brew install blackhole-2ch || echo "⚠️  ติดตั้ง BlackHole ไม่สำเร็จ — ลงทีหลังได้: brew install blackhole-2ch"
      echo "   หลังติดตั้ง: เปิด Audio MIDI Setup → + → Create Multi-Output Device"
      echo "   → ติ๊กลำโพง + BlackHole 2ch → ตั้งเป็น Sound Output (ดู README หัวข้อ 🔊)"
    else
      echo "   ข้าม — โหมดไมค์ใช้ได้ปกติ ลง BlackHole ทีหลังได้เสมอ"
    fi
  else
    echo "ℹ️  โหมดเสียงระบบ (Right ⌘ + Shift) ต้องลง BlackHole เอง — ดู README หัวข้อ 🔊"
  fi
fi

# 3.7 ensure Python.app can request the microphone — without a usage
# description macOS denies mic access SILENTLY (recordings are all zeros,
# no permission dialog ever appears)
PYAPP=$(.venv/bin/python -c "import sys,os;p=os.path.join(sys.base_prefix,'Resources','Python.app');print(p if os.path.exists(p) else '')")
if [[ -n "$PYAPP" ]] && ! plutil -p "$PYAPP/Contents/Info.plist" 2>/dev/null | grep -q NSMicrophoneUsageDescription; then
  echo "-- เพิ่มสิทธิ์ขอไมโครโฟนให้ Python.app (ครั้งเดียว อาจถามรหัสผ่าน)..."
  if ! plutil -insert NSMicrophoneUsageDescription -string "FastWhisper Flow needs the microphone for dictation" "$PYAPP/Contents/Info.plist" 2>/dev/null; then
    sudo plutil -insert NSMicrophoneUsageDescription -string "FastWhisper Flow needs the microphone for dictation" "$PYAPP/Contents/Info.plist"
  fi
  codesign --force --deep -s - "$PYAPP" 2>/dev/null || sudo codesign --force --deep -s - "$PYAPP"
  echo "✓ Python.app ขอสิทธิ์ไมโครโฟนได้แล้ว"
fi

# 4. remove the legacy launch agent if an older installer created one.
# The app is now started only by FastWhisper Toggle.app so permissions are
# requested during an explicit app launch, not silently at login.
launchctl bootout "gui/$(id -u)/com.fastwhisper.flow" 2>/dev/null || true
rm -f ~/Library/LaunchAgents/com.fastwhisper.flow.plist com.fastwhisper.flow.plist
echo "✓ ตั้งค่าให้เริ่มจาก FastWhisper Toggle.app เท่านั้น"

# 5. build the double-click toggle app for this machine
rm -rf "FastWhisper Toggle.app"
osacompile -o "FastWhisper Toggle.app" -e "
set dir to \"$DIR\"
set appVersion to \"$APP_VERSION\"
try
    do shell script \"cd \" & quoted form of dir & \" && ./flow.sh status | grep RUNNING\"
    do shell script \"cd \" & quoted form of dir & \" && ./flow.sh stop\"
    display notification \"Dictation stopped\" with title \"FastWhisper Flow v\" & appVersion
on error
    do shell script \"cd \" & quoted form of dir & \" && ./flow.sh start\"
    display notification \"Starting… wait for 🎙 in the menu bar\" with title \"FastWhisper Flow v\" & appVersion
end try
" >/dev/null
plutil -replace CFBundleIdentifier -string "com.jtiapbn.fastwhisperflow.toggle" "FastWhisper Toggle.app/Contents/Info.plist"
plutil -replace CFBundleShortVersionString -string "$APP_VERSION" "FastWhisper Toggle.app/Contents/Info.plist"
plutil -replace CFBundleVersion -string "$APP_VERSION" "FastWhisper Toggle.app/Contents/Info.plist"
plutil -replace NSMicrophoneUsageDescription -string "FastWhisper Flow needs microphone access for local dictation." "FastWhisper Toggle.app/Contents/Info.plist"
plutil -replace NSAppleEventsUsageDescription -string "FastWhisper Flow uses System Events to paste dictated text into the active app." "FastWhisper Toggle.app/Contents/Info.plist"
codesign --force --deep -s - "FastWhisper Toggle.app" >/dev/null 2>&1 || true
echo "✓ สร้าง FastWhisper Toggle.app"

chmod +x flow.sh reset-permissions.sh
echo ""
echo "== ติดตั้งเสร็จ! ขั้นตอนที่เหลือ (ทำเองครั้งเดียว): =="
PYAPP=$(.venv/bin/python -c "import sys,os;p=os.path.join(sys.base_prefix,'Resources','Python.app');print(p if os.path.exists(p) else sys.base_prefix)")
[[ -d "$PYAPP" ]] || { echo "ERROR: ไม่พบ Python.app ที่ $PYAPP"; exit 1; }
echo "1. System Settings → Privacy & Security → Accessibility → กด + → ⌘⇧G → วางพาธนี้:"
echo "   $PYAPP"
echo "2. เปิด 'FastWhisper Toggle.app' เพื่อให้ macOS ลงทะเบียน Python.app แล้วเปิดสิทธิ์ Accessibility"
echo "3. กด Right ⌘ ค้างแล้วพูด — ครั้งแรก macOS จะถามสิทธิ์ Microphone/System Events → กด Allow"
