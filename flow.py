"""FastWhisper Flow — local hold-to-talk dictation for macOS.

Hold RIGHT COMMAND (⌘) to record, release to transcribe and paste into
the frontmost app. Everything runs on-device via mlx-whisper (Metal).
"""

import os
import queue
import subprocess
import threading
import time
from pathlib import Path

import numpy as np
import rumps
import sounddevice as sd
from pynput import keyboard
from pynput.keyboard import Key

from cleanup import clean

# ---------------------------------------------------------------- config
MODEL = "tawankri/distill-thonburian-whisper-large-v3-mlx"  # Thai fine-tune
APP_VERSION = (
    Path(__file__).with_name("VERSION").read_text(encoding="utf-8").strip()
    if Path(__file__).with_name("VERSION").exists()
    else "dev"
)
# fallback general model: "mlx-community/whisper-large-v3-turbo"
LANGUAGE = "th"          # force Thai (best accuracy); None = auto-detect
HOTKEY = Key.cmd_r       # hold Right Command to talk
INPUT_DEVICE = None      # None = system default; or a name like
                         # "MacBook Pro Microphone" / "Maono DM40 Mic USB"
LOOPBACK_DEVICE = "BlackHole 2ch"  # hold Right ⌘ + Shift to capture system
                                   # audio; needs the BlackHole driver and a
                                   # Multi-Output Device routing sound to it
LOOPBACK_LANGUAGE = None  # auto-detect for system audio (may be English etc.)
LOOPBACK_MODEL = "mlx-community/whisper-large-v3-turbo"  # general multilingual
# model for system audio — the Thai fine-tune above skews detection to Thai
MULTILINGUAL_LANGUAGE = None  # hold Right ⌘ + Option: mic dictation with the
# multilingual model above, auto-detect language (for English / heavy mixing)
SILENCE_PEAK = 0.005      # skip transcription below this level — forcing a
                          # language on silence makes Whisper hallucinate
SAMPLE_RATE = 16000
MIN_SECONDS = 0.5        # ignore accidental taps
HEALTH_INTERVAL = 30     # lightweight status check; does not open the mic
LISTENER_REFRESH_SECONDS = 300
MENU_VALUE_MAX = 28
# -----------------------------------------------------------------------

ICON_IDLE = "🎙"
ICON_REC = "🔴"
ICON_REC_EN = "🔵"        # multilingual mic mode (Right ⌘ + Option)
ICON_REC_SYS = "🟢"       # system-audio loopback mode (Right ⌘ + Shift)
ICON_BUSY = "⏳"
ICON_WARN = "⚠️"
LOG_PATH = "/tmp/fastwhisper-flow.log"


class Recorder:
    def __init__(self):
        self._q = queue.Queue()
        self._stream = None

    @staticmethod
    def _real_mic():
        """Fallback when the system default input is the loopback driver:
        recording from BlackHole in mic mode captures silence. Pick a real
        microphone instead (USB mic first, then the built-in one)."""
        inputs = [d for d in sd.query_devices()
                  if d["max_input_channels"] > 0
                  and LOOPBACK_DEVICE.split()[0].lower() not in d["name"].lower()]
        for pref in ("maono", "macbook"):
            for d in inputs:
                if pref in d["name"].lower():
                    return d["index"]
        return inputs[0]["index"] if inputs else None

    def start(self, device=INPUT_DEVICE):
        self._q = queue.Queue()
        if device is None:
            default = sd.query_devices(sd.default.device[0])
            if LOOPBACK_DEVICE.split()[0].lower() in default["name"].lower():
                device = self._real_mic()
                name = sd.query_devices(device)["name"] if device is not None else None
                print(f"default input is {default['name']!r} (loopback); "
                      f"using {name!r} instead", flush=True)
        info = sd.query_devices(device if device is not None else sd.default.device[0])
        # loopback drivers (BlackHole) run at their own rate; capture natively
        # and resample to SAMPLE_RATE in stop()
        self._rate = int(info["default_samplerate"])
        channels = min(2, info["max_input_channels"])
        self._stream = sd.InputStream(
            device=device,
            samplerate=self._rate, channels=channels, dtype="float32",
            callback=lambda data, *_: self._q.put(data.copy()),
        )
        self._stream.start()

    def stop(self) -> np.ndarray:
        self._stream.stop()
        self._stream.close()
        self._stream = None
        chunks = []
        while not self._q.empty():
            chunks.append(self._q.get())
        if not chunks:
            return np.zeros(0, dtype=np.float32)
        audio = np.concatenate(chunks)
        if audio.ndim > 1:
            audio = audio.mean(axis=1)  # downmix stereo to mono
        if self._rate != SAMPLE_RATE:
            n = int(len(audio) * SAMPLE_RATE / self._rate)
            audio = np.interp(
                np.linspace(0, len(audio) - 1, n),
                np.arange(len(audio)), audio,
            ).astype(np.float32)
        return audio.flatten()


def paste_text(text: str):
    """Put text on the clipboard and simulate Cmd+V in the frontmost app."""
    # force a full UTF-8 locale — LC_ALL=C in the parent env would otherwise
    # make pbcopy mangle Thai text into "?"
    env = {**os.environ, "LANG": "en_US.UTF-8", "LC_ALL": "en_US.UTF-8",
           "LC_CTYPE": "en_US.UTF-8"}
    subprocess.run("pbcopy", input=text.encode("utf-8"), env=env)
    time.sleep(0.1)
    r = subprocess.run(
        ["osascript", "-e",
         'tell application "System Events" to keystroke "v" using command down'],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print(f"paste failed: {r.stderr.strip()}", flush=True)
    else:
        print(f"pasted {len(text)} chars", flush=True)


class FlowApp(rumps.App):
    def __init__(self):
        super().__init__(ICON_IDLE, quit_button="Quit")
        self.status_item = rumps.MenuItem("State: Start")
        self.listener_item = rumps.MenuItem("Keys: Start")
        self.mic_item = rumps.MenuItem("Mic: Check")
        self.access_item = rumps.MenuItem("Access: Check")
        self.input_item = rumps.MenuItem("Input: Check")
        self.model_item = rumps.MenuItem("Model: Load")
        self.last_error_item = rumps.MenuItem("Error: None")
        self.menu = [
            f"FastWhisper Flow v{APP_VERSION}",
            None,
            self.status_item,
            self.listener_item,
            self.mic_item,
            self.access_item,
            self.input_item,
            self.model_item,
            self.last_error_item,
            None,
            rumps.MenuItem("Restart Listener", callback=self._menu_restart_listener),
            rumps.MenuItem("Test Mic", callback=self._menu_test_mic),
            rumps.MenuItem("Open Log", callback=self._menu_open_log),
            None,
            "🎙 Right ⌘ (ค้าง) — พูดไทย → 🔴",
            "🌐 Right ⌘ + Option — English / auto-detect → 🔵",
            "🔊 Right ⌘ + Shift — เสียงจากระบบ → 🟢",
            None,
            "ปล่อยปุ่ม = ถอดเสียง (⏳) แล้วพิมพ์ให้เอง",
        ]
        self.recorder = Recorder()
        self.recording = False
        self.busy = False
        self._busy_since = 0.0
        self._error_until = 0.0
        self._last_error = "None"
        self._last_listener_restart = 0.0
        self.shift_down = False
        self.option_down = False
        self.hotkey_down = False
        self.loopback = False
        self.multilingual = False
        self.transcribe = None  # loaded lazily

        self._request_mic_access()
        threading.Thread(target=self._load_model, daemon=True).start()

        self.listener = None
        self._listener_lock = threading.Lock()
        self._start_listener()

        # macOS silently disables pynput's CGEventTap after sleep / screen
        # lock (kCGEventTapDisabledByTimeout|UserInput) and pynput never
        # re-enables it: the thread stays alive and the icon looks normal,
        # but keys stop arriving. Rebuild the listener on wake and on a
        # periodic watchdog so a dead tap never lasts more than a minute.
        self._register_wake_observer()
        self._health_timer = rumps.Timer(self._health_tick, HEALTH_INTERVAL)
        self._health_timer.start()
        self._health_tick(None)

    def _start_listener(self):
        with self._listener_lock:
            old, self.listener = self.listener, None
            if old is not None:
                try:
                    old.stop()
                except Exception:
                    pass
            self.listener = keyboard.Listener(
                on_press=self._on_press, on_release=self._on_release
            )
            self.listener.start()
            self._last_listener_restart = time.time()

    def _register_wake_observer(self):
        try:
            from AppKit import NSWorkspace
            nc = NSWorkspace.sharedWorkspace().notificationCenter()
            for name in ("NSWorkspaceDidWakeNotification",
                         "NSWorkspaceScreensDidWakeNotification",
                         "NSWorkspaceSessionDidBecomeActiveNotification"):
                nc.addObserverForName_object_queue_usingBlock_(
                    name, None, None, self._on_wake
                )
        except Exception as e:
            print(f"wake observer unavailable: {e}", flush=True)

    def _on_wake(self, _note):
        print("system woke — restarting hotkey listener", flush=True)
        self._reset_state()
        self._start_listener()
        self._health_tick(None)

    def _health_tick(self, _timer):
        """Cheap self-healing check. It does not open the microphone or run
        Whisper; it only inspects app state, permissions, and device metadata."""
        try:
            if self.busy and time.time() - self._busy_since > 60:
                print("busy watchdog: resetting stuck state", flush=True)
                self._reset_state()

            listener_alive = self.listener is not None and self.listener.is_alive()
            stale_listener = (
                time.time() - self._last_listener_restart
                > LISTENER_REFRESH_SECONDS
            )
            input_active = self.hotkey_down or self.shift_down or self.option_down
            if not self.recording and not self.busy and not input_active:
                if not listener_alive:
                    print("health: hotkey listener not alive; restarting", flush=True)
                    self._start_listener()
                    listener_alive = True
                elif stale_listener:
                    print("health: refreshing hotkey listener", flush=True)
                    self._start_listener()

            self._update_health_menu()
        except Exception as e:
            print(f"health check failed: {e}", flush=True)

    def _update_health_menu(self):
        listener_ok = self.listener is not None and self.listener.is_alive()
        mic_status = self._mic_permission_status()
        access_status = self._accessibility_status()
        input_status = self._input_status()

        if self.recording:
            status = "Recording"
        elif self.busy:
            status = "Transcribing"
        elif self.transcribe is None:
            status = "Loading"
        elif not listener_ok:
            status = "Keys restarting"
        elif not mic_status.startswith("Authorized"):
            status = "Mic permission"
        elif access_status.startswith("Missing"):
            status = "Access permission"
        elif input_status.startswith("Unavailable"):
            status = "No input"
        else:
            status = "Ready"

        self.status_item.title = f"State: {status}"
        self.listener_item.title = (
            "Keys: Active" if listener_ok else "Keys: Restarting"
        )
        self.mic_item.title = f"Mic: {self._compact(mic_status)}"
        self.access_item.title = f"Access: {self._compact(access_status)}"
        self.input_item.title = f"Input: {self._compact(input_status)}"
        self.model_item.title = (
            "Model: Ready" if self.transcribe is not None else "Model: Loading"
        )
        self.last_error_item.title = f"Error: {self._compact(self._last_error)}"

        if not self.recording and not self.busy and time.time() >= self._error_until:
            if self.transcribe is None:
                self.title = ICON_BUSY
            else:
                self.title = ICON_IDLE if status == "Ready" else ICON_WARN

    @staticmethod
    def _compact(text, limit=MENU_VALUE_MAX):
        text = str(text).replace("\n", " ").strip()
        if len(text) <= limit:
            return text
        return text[:limit - 1].rstrip() + "…"

    def _mic_permission_status(self):
        try:
            from AVFoundation import AVCaptureDevice as dev
            status = int(dev.authorizationStatusForMediaType_("soun"))
            return {
                0: "Not requested",
                1: "Restricted",
                2: "Denied",
                3: "Authorized",
            }.get(status, f"Unknown ({status})")
        except Exception as e:
            return f"Unknown ({e})"

    def _accessibility_status(self):
        try:
            try:
                from ApplicationServices import AXIsProcessTrusted
            except Exception:
                import Quartz
                AXIsProcessTrusted = Quartz.AXIsProcessTrusted
            return "Allowed" if AXIsProcessTrusted() else "Missing"
        except Exception as e:
            print(f"accessibility status unavailable: {e}", flush=True)
            return "Unknown"

    def _input_status(self):
        try:
            device = sd.query_devices(kind="input")
            channels = int(device.get("max_input_channels", 0))
            name = device.get("name", "Unknown")
            if channels <= 0:
                return "Unavailable"
            return name
        except Exception as e:
            print(f"input status unavailable: {e}", flush=True)
            return "Unavailable"

    def _menu_restart_listener(self, _sender):
        print("menu: restarting hotkey listener", flush=True)
        self._reset_state()
        self._start_listener()
        self._update_health_menu()
        rumps.notification("FastWhisper Flow", "Hotkey listener restarted", "")

    def _menu_open_log(self, _sender):
        subprocess.run(["touch", LOG_PATH])
        subprocess.run(["open", LOG_PATH])

    def _menu_test_mic(self, _sender):
        if self.recording or self.busy:
            rumps.notification("FastWhisper Flow", "Mic test skipped", "App is busy")
            return
        threading.Thread(target=self._test_mic, daemon=True).start()

    def _test_mic(self):
        try:
            rumps.notification("FastWhisper Flow", "Testing microphone", "Speak now")
            rate = SAMPLE_RATE
            rec = sd.rec(int(1.5 * rate), samplerate=rate, channels=1)
            sd.wait()
            peak = float(np.abs(rec).max())
            msg = "OK" if peak > 0.05 else "Too low or blocked"
            self._last_error = "None" if peak > 0.05 else f"Mic test: peak {peak:.3f}"
            print(f"mic test peak: {peak:.3f} -> {msg}", flush=True)
            rumps.notification(
                "FastWhisper Flow",
                f"Mic test: {msg}",
                f"Peak {peak:.3f}",
            )
        except Exception as e:
            self._last_error = f"Mic test failed: {e}"
            self._flash_error(self._last_error)
        finally:
            self._update_health_menu()

    def _request_mic_access(self):
        """Force the macOS microphone permission dialog. Opening a CoreAudio
        input stream without an explicit request gets silently denied
        (recordings are all zeros, no prompt) on newer macOS."""
        try:
            from AVFoundation import AVCaptureDevice as dev
            status = int(dev.authorizationStatusForMediaType_("soun"))
            names = {0: "not determined", 1: "restricted",
                     2: "DENIED", 3: "authorized"}
            print(f"mic permission: {names.get(status, status)}", flush=True)
            if status == 0:
                dev.requestAccessForMediaType_completionHandler_(
                    "soun",
                    lambda ok: print(f"mic permission granted: {bool(ok)}",
                                     flush=True),
                )
            elif status == 2:
                self._flash_error(
                    "mic DENIED — System Settings → Privacy & Security → "
                    "Microphone → enable Python"
                )
        except Exception as e:
            print(f"mic permission check failed: {e}", flush=True)

    def _load_model(self):
        self.title = ICON_BUSY
        try:
            import mlx_whisper  # heavy import; also triggers model download

            # warm up so the first real dictation is fast
            mlx_whisper.transcribe(
                np.zeros(SAMPLE_RATE, dtype=np.float32), path_or_hf_repo=MODEL
            )
            self.transcribe = mlx_whisper.transcribe
            self.title = ICON_IDLE
        except Exception as e:
            self._flash_error(f"model load failed: {e}")

    def _flash_error(self, msg: str):
        print(msg, flush=True)
        self._last_error = msg[:80]
        self.last_error_item.title = f"Error: {self._compact(self._last_error)}"
        self.title = ICON_WARN
        self._error_until = time.time() + 3.0
        threading.Timer(3.0, self._clear_error_if_current).start()

    def _clear_error_if_current(self):
        if self.title == ICON_WARN and not self.recording and not self.busy:
            self._update_health_menu()

    # ------------------------------------------------------------ hotkey
    # NOTE: pynput kills the listener thread permanently if a callback
    # raises, so both handlers must never let an exception escape.
    def _on_press(self, key):
        try:
            self._handle_press(key)
        except Exception as e:
            print(f"hotkey press error: {e}", flush=True)
            self._reset_state()

    def _on_release(self, key):
        try:
            self._handle_release(key)
        except Exception as e:
            print(f"hotkey release error: {e}", flush=True)
            self._reset_state()

    def _reset_state(self):
        self.recording = False
        self.busy = False
        self.hotkey_down = False
        self.shift_down = False
        self.option_down = False
        if self.recorder._stream is not None:
            try:
                self.recorder._stream.stop()
                self.recorder._stream.close()
            except Exception:
                pass
            self.recorder._stream = None
        self.title = ICON_IDLE

    def _handle_press(self, key):
        if key in (Key.shift, Key.shift_l, Key.shift_r):
            self.shift_down = True
        if key in (Key.alt, Key.alt_l, Key.alt_r):
            self.option_down = True
        # failsafe: if transcription hung and left busy stuck, recover
        if self.busy and time.time() - self._busy_since > 60:
            print("busy watchdog: resetting stuck state", flush=True)
            self.busy = False
            self.title = ICON_IDLE
        if key == HOTKEY:
            self.hotkey_down = True
        if key == HOTKEY and not self.recording and not self.busy:
            if self.transcribe is None:
                print("hotkey pressed while model is still loading", flush=True)
                self._update_health_menu()
                return  # model still loading
            self.loopback = self.shift_down
            self.multilingual = self.option_down
            device = LOOPBACK_DEVICE if self.loopback else INPUT_DEVICE
            try:
                self.recorder.start(device)
            except Exception as e:
                msg = f"cannot open input '{device}': {e}"
                if self.shift_down:
                    msg += " (is BlackHole installed?)"
                self._flash_error(msg)
                return
            self.recording = True
            print(
                "recording started "
                f"(loopback={self.loopback}, multilingual={self.multilingual})",
                flush=True,
            )
            if self.loopback:
                self.title = ICON_REC_SYS
            elif self.multilingual:
                self.title = ICON_REC_EN
            else:
                self.title = ICON_REC

    def _handle_release(self, key):
        if key in (Key.shift, Key.shift_l, Key.shift_r):
            self.shift_down = False
        if key in (Key.alt, Key.alt_l, Key.alt_r):
            self.option_down = False
        if key == HOTKEY:
            self.hotkey_down = False
        if key == HOTKEY and self.recording:
            self.recording = False
            try:
                audio = self.recorder.stop()
            except Exception as e:
                # stream died mid-recording (device unplugged, sleep, …)
                self.recorder._stream = None
                self._flash_error(f"recording failed: {e}")
                return
            duration = len(audio) / SAMPLE_RATE if SAMPLE_RATE else 0
            print(
                f"recording stopped: {duration:.2f}s, samples={len(audio)}",
                flush=True,
            )
            if len(audio) < SAMPLE_RATE * MIN_SECONDS:
                print("recording ignored: too short", flush=True)
                self.title = ICON_IDLE
                return
            self.busy = True
            self._busy_since = time.time()
            self.title = ICON_BUSY
            threading.Thread(
                target=self._process, args=(audio,), daemon=True
            ).start()
        elif key == HOTKEY:
            print(
                "hotkey release ignored "
                f"(recording={self.recording}, busy={self.busy}, "
                f"model_ready={self.transcribe is not None})",
                flush=True,
            )

    # --------------------------------------------------------- pipeline
    def _process(self, audio: np.ndarray):
        try:
            peak = float(np.abs(audio).max())
            if peak < SILENCE_PEAK:
                if peak == 0.0:
                    # exact zeros = macOS gave us no signal at all: mic
                    # permission denied/reset, or a loopback device with
                    # nothing routed to it
                    self._flash_error(
                        "no audio (all zeros) — check System Settings → "
                        "Privacy & Security → Microphone allows Python"
                    )
                else:
                    self._flash_error(
                        f"audio too quiet (peak {peak:.4f}) — "
                        "check mic input volume"
                    )
                return
            if self.loopback:
                model, lang = LOOPBACK_MODEL, LOOPBACK_LANGUAGE
            elif self.multilingual:
                model, lang = LOOPBACK_MODEL, MULTILINGUAL_LANGUAGE
            else:
                model, lang = MODEL, LANGUAGE
            result = self.transcribe(
                audio, path_or_hf_repo=model, language=lang
            )
            text = clean(result["text"])
            if text:
                paste_text(text)
        except Exception as e:
            print(f"transcription error: {e}")
        finally:
            self.busy = False
            if self.title == ICON_WARN and time.time() < self._error_until:
                pass  # keep the current error flash visible
            else:
                self.title = ICON_IDLE
            self._update_health_menu()


if __name__ == "__main__":
    FlowApp().run()
