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

    def start(self):
        self._q = queue.Queue()
        self._stream = sd.InputStream(
            device=INPUT_DEVICE,
            samplerate=SAMPLE_RATE, channels=1, dtype="float32",
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
        return np.concatenate(chunks).flatten()


def paste_text(text: str):
    """Put text on the clipboard and simulate Cmd+V in the frontmost app."""
    env = {**os.environ, "LC_CTYPE": "UTF-8"}
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
        self.menu = ["FastWhisper Flow — hold Right ⌘ to talk"]
        self.recorder = Recorder()
        self.recording = False
        self.busy = False
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

    # ------------------------------------------------------------ hotkey
    def _on_press(self, key):
        if key == HOTKEY and not self.recording and not self.busy:
            if self.transcribe is None:
                return  # model still loading
            self.recording = True
            self.title = ICON_REC
            self.recorder.start()

    def _on_release(self, key):
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
            result = self.transcribe(
                audio, path_or_hf_repo=MODEL, language=LANGUAGE
            )
            text = clean(result["text"])
            if text:
                paste_text(text)
        except Exception as e:
            print(f"transcription error: {e}")
        finally:
            self.busy = False
            self.title = ICON_IDLE


if __name__ == "__main__":
    FlowApp().run()
