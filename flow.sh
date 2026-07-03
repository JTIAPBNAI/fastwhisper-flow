#!/bin/zsh
# FastWhisper Flow controller: ./flow.sh start|stop|restart|status|mic|log
DIR="$(cd "$(dirname "$0")" && pwd)"
PY="$DIR/.venv/bin/python"
LOG=/tmp/fastwhisper-flow.log

running() { pgrep -f "flow.py" >/dev/null; }

case "$1" in
  start)
    if running; then echo "Already running (menu bar 🎙)."; exit 0; fi
    cd "$DIR" && nohup "$PY" flow.py >"$LOG" 2>&1 &
    echo "Started. Wait for 🎙 in the menu bar (⏳ = model loading)."
    ;;
  stop)
    pkill -f "flow.py" && echo "Stopped." || echo "Not running."
    ;;
  restart)
    "$0" stop; sleep 1; "$0" start
    ;;
  status)
    if running; then echo "RUNNING (pid $(pgrep -f flow.py | head -1))"
    else echo "NOT RUNNING"; fi
    ;;
  mic)
    "$PY" -c "
import sounddevice as sd, numpy as np
print('using:', sd.query_devices(kind='input')['name'])
print('speak now (3s)...')
rec = sd.rec(int(3*16000), samplerate=16000, channels=1); sd.wait()
lvl = round(float(abs(rec).max()), 3)
print('mic level:', lvl, '->', 'OK' if lvl > 0.05 else 'TOO LOW / BLOCKED')
"
    ;;
  log)
    tail -20 "$LOG"
    ;;
  *)
    echo "Usage: ./flow.sh start|stop|restart|status|mic|log"
    ;;
esac
