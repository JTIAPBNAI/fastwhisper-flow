"""FastWhisper Flow — local hold-to-talk dictation for macOS.

Hold RIGHT COMMAND (⌘) to record, release to transcribe and paste into
the frontmost app. Everything runs on-device via mlx-whisper (Metal).
"""

import os
import queue
import subprocess
import threading
import time

import numpy as np
import rumps
import sounddevice as sd
from pynput import keyboard
from pynput.keyboard import Key

from cleanup import clean

# ---------------------------------------------------------------- config
MODEL = "tawankri/distill-thonburian-whisper-large-v3-mlx"  # Thai fine-tune
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
# -----------------------------------------------------------------------

ICON_IDLE = "🎙"
ICON_REC = "🔴"
ICON_REC_EN = "🔵"        # multilingual mic mode (Right ⌘ + Option)
ICON_REC_SYS = "🟢"       # system-audio loopback mode (Right ⌘ + Shift)
ICON_BUSY = "⏳"


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
        self.menu = [
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
        self.shift_down = False
        self.option_down = False
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
        self._watchdog = rumps.Timer(self._watchdog_tick, 60)
        self._watchdog.start()

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

    def _watchdog_tick(self, _timer):
        # don't yank the listener mid-dictation; the tap can't be dead if
        # we're recording anyway
        if self.recording or self.busy:
            return
        self._start_listener()

    def _request_mic_access(self):
        """Force the macOS microphone permission dialog. Opening a CoreAudio
        input stream without an explicit request gets silently denied
        (recordings are all zeros, no prompt) on newer macOS."""
        try:
            import objc
            objc.loadBundle("AVFoundation", {},
                            "/System/Library/Frameworks/AVFoundation.framework")
            dev = objc.lookUpClass("AVCaptureDevice")
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
        import mlx_whisper  # heavy import; also triggers model download

        # warm up so the first real dictation is fast
        mlx_whisper.transcribe(
            np.zeros(SAMPLE_RATE, dtype=np.float32), path_or_hf_repo=MODEL
        )
        self.transcribe = mlx_whisper.transcribe
        self.title = ICON_IDLE

    def _flash_error(self, msg: str):
        print(msg, flush=True)
        self.title = "⚠️"
        threading.Timer(2.0, lambda: setattr(self, "title", ICON_IDLE)).start()

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
        if key == HOTKEY and not self.recording and not self.busy:
            if self.transcribe is None:
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
        if key == HOTKEY and self.recording:
            self.recording = False
            try:
                audio = self.recorder.stop()
            except Exception as e:
                # stream died mid-recording (device unplugged, sleep, …)
                self.recorder._stream = None
                self._flash_error(f"recording failed: {e}")
                return
            if len(audio) < SAMPLE_RATE * MIN_SECONDS:
                self.title = ICON_IDLE
                return
            self.busy = True
            self._busy_since = time.time()
            self.title = ICON_BUSY
            threading.Thread(
                target=self._process, args=(audio,), daemon=True
            ).start()

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
            if self.title != "⚠️":  # keep the error flash visible
                self.title = ICON_IDLE


if __name__ == "__main__":
    FlowApp().run()
