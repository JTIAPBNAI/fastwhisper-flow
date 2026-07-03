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
SILENCE_PEAK = 0.005      # skip transcription below this level — forcing a
                          # language on silence makes Whisper hallucinate
SAMPLE_RATE = 16000
MIN_SECONDS = 0.5        # ignore accidental taps
# -----------------------------------------------------------------------

ICON_IDLE = "🎙"
ICON_REC = "🔴"
ICON_BUSY = "⏳"


class Recorder:
    def __init__(self):
        self._q = queue.Queue()
        self._stream = None

    def start(self, device=INPUT_DEVICE):
        self._q = queue.Queue()
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
            "FastWhisper Flow — hold Right ⌘ to talk",
            "Hold Right ⌘ + Shift for system audio",
        ]
        self.recorder = Recorder()
        self.recording = False
        self.busy = False
        self.shift_down = False
        self.loopback = False
        self.transcribe = None  # loaded lazily

        threading.Thread(target=self._load_model, daemon=True).start()

        self.listener = keyboard.Listener(
            on_press=self._on_press, on_release=self._on_release
        )
        self.listener.start()

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
    def _on_press(self, key):
        if key in (Key.shift, Key.shift_l, Key.shift_r):
            self.shift_down = True
        if key == HOTKEY and not self.recording and not self.busy:
            if self.transcribe is None:
                return  # model still loading
            self.loopback = self.shift_down
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
            self.title = ICON_REC

    def _on_release(self, key):
        if key in (Key.shift, Key.shift_l, Key.shift_r):
            self.shift_down = False
        if key == HOTKEY and self.recording:
            self.recording = False
            audio = self.recorder.stop()
            if len(audio) < SAMPLE_RATE * MIN_SECONDS:
                self.title = ICON_IDLE
                return
            self.busy = True
            self.title = ICON_BUSY
            threading.Thread(
                target=self._process, args=(audio,), daemon=True
            ).start()

    # --------------------------------------------------------- pipeline
    def _process(self, audio: np.ndarray):
        try:
            if float(np.abs(audio).max()) < SILENCE_PEAK:
                self._flash_error("no audio captured — check sound routing")
                return
            if self.loopback:
                model, lang = LOOPBACK_MODEL, LOOPBACK_LANGUAGE
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
