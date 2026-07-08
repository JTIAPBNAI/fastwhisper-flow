#!/bin/zsh
# FastWhisper Flow controller: ./flow.sh start|stop|restart|status|mic|log
DIR="$(cd "$(dirname "$0")" && pwd)"
PY="$DIR/.venv/bin/python"
LOG=/tmp/fastwhisper-flow.log
PIDFILE=/tmp/fastwhisper-flow.pid
DOMAIN="gui/$(id -u)"

pid_running() {
  [[ -f "$PIDFILE" ]] || return 1
  local pid
  pid="$(<"$PIDFILE")"
  [[ "$pid" == <-> ]] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  ps -p "$pid" -o command= | grep -F "$DIR/flow.py" >/dev/null
}

find_running_pid() {
  pgrep -f "$DIR/flow.py" | head -1
}

case "$1" in
  start)
    if pid_running; then echo "Already running (menu bar 🎙)."; exit 0; fi
    existing="$(find_running_pid)"
    if [[ -n "$existing" ]]; then
      echo "$existing" >"$PIDFILE"
      echo "Already running (menu bar 🎙)."
      exit 0
    fi
    # NOTE: must NOT run under launchd — macOS then attributes the mic
    # permission to bare Python and refuses to show the permission dialog
    # (recordings become all zeros). nohup keeps the Toggle app (a real
    # app bundle with a mic usage description) as the responsible process.
    # append (not truncate) so evidence from earlier sessions survives
    # restarts; keep the tail if the log grows past 1 MB
    if [[ -f "$LOG" && $(stat -f%z "$LOG") -gt 1048576 ]]; then
      tail -c 524288 "$LOG" >"$LOG.tmp" && mv "$LOG.tmp" "$LOG"
    fi
    echo "===== session start $(date '+%Y-%m-%d %H:%M:%S') =====" >>"$LOG"
    cd "$DIR" && nohup "$PY" "$DIR/flow.py" >>"$LOG" 2>&1 &
    echo $! >"$PIDFILE"
    sleep 0.5
    existing="$(find_running_pid)"
    if [[ -n "$existing" ]]; then
      echo "$existing" >"$PIDFILE"
    fi
    echo "Started. Wait for 🎙 in the menu bar (⏳ = model loading)."
    ;;
  stop)
    # stop any legacy launchd job from older installs before killing Python
    launchctl bootout "$DOMAIN/com.fastwhisper.flow" 2>/dev/null
    if pid_running; then
      kill "$(<"$PIDFILE")" && rm -f "$PIDFILE" && echo "Stopped."
    elif existing="$(find_running_pid)" && [[ -n "$existing" ]]; then
      kill "$existing" && rm -f "$PIDFILE" && echo "Stopped."
    else
      rm -f "$PIDFILE"
      echo "Not running."
    fi
    ;;
  restart)
    "$0" stop; sleep 1; "$0" start
    ;;
  status)
    if pid_running; then echo "RUNNING (pid $(<"$PIDFILE"))"
    elif existing="$(find_running_pid)" && [[ -n "$existing" ]]; then
      echo "$existing" >"$PIDFILE"
      echo "RUNNING (pid $existing)"
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
