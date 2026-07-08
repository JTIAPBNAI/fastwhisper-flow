"""FastWhisper Flow — local hold-to-talk dictation for macOS.

Hold RIGHT COMMAND (⌘) to record, release to transcribe and paste into
the frontmost app. Everything runs on-device via mlx-whisper (Metal).
"""

import os
import queue
import hashlib
import json
import re
import shlex
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.request
import zipfile
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
# virtual/loopback inputs that deliver silence when recorded as a mic; never
# record dictation from these even if macOS makes one the default input
VIRTUAL_INPUTS = ("blackhole", "teams audio", "motiv", "maono ai",
                  "multi-output", "aggregate", "zoomaudio", "loopback")
REAL_MIC_PREFERENCE = ("maono dm40", "macbook pro microphone")
LOOPBACK_LANGUAGE = None  # auto-detect for system audio (may be English etc.)
LOOPBACK_MODEL = "mlx-community/whisper-large-v3-turbo"  # general multilingual
# model for system audio — the Thai fine-tune above skews detection to Thai
MULTILINGUAL_LANGUAGE = None  # hold Right ⌘ + Option: mic dictation with the
# multilingual model above, auto-detect language (for English / heavy mixing)
SILENCE_PEAK = 0.005      # quiet recordings below this are auto-boosted first
NO_SIGNAL_PEAK = 0.00002  # below this, CoreAudio effectively gave us silence
NO_SIGNAL_RMS = 0.000005
AUTO_GAIN_TARGET_PEAK = 0.2
MAX_AUTO_GAIN = 2000.0
SAMPLE_RATE = 16000
MIN_SECONDS = 0.5        # ignore accidental taps
TRANSCRIBE_TIMEOUT_SECONDS = 20
HEALTH_INTERVAL = 30     # lightweight status check; does not open the mic
LISTENER_REFRESH_SECONDS = 300
MENU_VALUE_MAX = 28
GITHUB_LATEST_RELEASE = (
    "https://api.github.com/repos/JTIAPBNAI/fastwhisper-flow/releases/latest"
)
GITHUB_ASSET_URL_PREFIX = (
    "https://github.com/JTIAPBNAI/fastwhisper-flow/releases/download/"
)
INSTALLER_ASSET = "FastWhisperFlow-Installer.zip"
MAX_UPDATE_ZIP_BYTES = 25 * 1024 * 1024
MAX_UPDATE_PAYLOAD_BYTES = 5 * 1024 * 1024
UPDATE_FILES = {
    "VERSION",
    "README.md",
    "cleanup.py",
    "flow.py",
    "flow.sh",
    "install.sh",
    "reset-permissions.sh",
    "requirements.txt",
}
# -----------------------------------------------------------------------

ICON_IDLE = "🎙"
ICON_REC = "🔴"
ICON_REC_EN = "🔵"        # multilingual mic mode (Right ⌘ + Option)
ICON_REC_SYS = "🟢"       # system-audio loopback mode (Right ⌘ + Shift)
ICON_BUSY = "⏳"
ICON_WARN = "⚠️"
LOG_PATH = "/tmp/fastwhisper-flow.log"
APP_DIR = Path(__file__).resolve().parent


class Recorder:
    def __init__(self):
        self._q = queue.Queue()
        self._stream = None

    @staticmethod
    def _refresh_devices():
        """PortAudio snapshots the device list once at init; a USB mic that
        re-enumerated (sleep, hub power) leaves the snapshot stale and streams
        open against a dead device that records silence. Re-init before each
        recording so hot-plugged devices are seen."""
        try:
            sd._terminate()
            sd._initialize()
        except Exception as e:
            print(f"device refresh failed: {e}", flush=True)

    @staticmethod
    def _is_virtual(name: str) -> bool:
        # some drivers use non-breaking spaces in names ("Maono\xa0AI\xa0…")
        low = " ".join(name.lower().split())
        return any(v in low for v in VIRTUAL_INPUTS)

    @staticmethod
    def _real_mic():
        """Fallback when the system default input is a virtual/loopback
        device: recording from those in mic mode captures silence. Pick a
        real microphone instead (USB mic first, then the built-in one)."""
        inputs = [d for d in sd.query_devices()
                  if d["max_input_channels"] > 0
                  and not Recorder._is_virtual(d["name"])]
        for pref in REAL_MIC_PREFERENCE:
            for d in inputs:
                if pref in d["name"].lower():
                    return d["index"]
        return inputs[0]["index"] if inputs else None

    def start(self, device=INPUT_DEVICE):
        self._q = queue.Queue()
        self._refresh_devices()
        if device is None:
            default = sd.query_devices(sd.default.device[0])
            if self._is_virtual(default["name"]):
                device = self._real_mic()
                name = sd.query_devices(device)["name"] if device is not None else None
                print(f"default input is {default['name']!r} (virtual); "
                      f"using {name!r} instead", flush=True)
        info = sd.query_devices(device if device is not None else sd.default.device[0])
        print(f"recording device: {info['name']!r}", flush=True)
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


def _frontmost_app_info():
    try:
        from AppKit import NSWorkspace
        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        if app is None:
            return None
        return {
            "pid": int(app.processIdentifier()),
            "name": str(app.localizedName() or app.bundleIdentifier() or "Unknown"),
        }
    except Exception as e:
        print(f"frontmost app lookup failed: {e}", flush=True)
        return None


def paste_text(text: str, target=None):
    """Put text on the clipboard and paste into the currently focused field."""
    # force a full UTF-8 locale — LC_ALL=C in the parent env would otherwise
    # make pbcopy mangle Thai text into "?"
    env = {**os.environ, "LANG": "en_US.UTF-8", "LC_ALL": "en_US.UTF-8",
           "LC_CTYPE": "en_US.UTF-8"}
    subprocess.run("pbcopy", input=text.encode("utf-8"), env=env)
    if target and target.get("pid"):
        print(
            f"paste observed target: {target.get('name')} "
            f"(pid {target.get('pid')}); preserving current focus",
            flush=True,
        )
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


def _version_tuple(version: str):
    parts = re.findall(r"\d+", version)
    return tuple(int(p) for p in parts[:3])


def _is_newer_version(latest: str, current: str):
    latest_tuple = _version_tuple(latest)
    current_tuple = _version_tuple(current)
    if not latest_tuple or not current_tuple:
        return latest.strip() != current.strip()
    max_len = max(len(latest_tuple), len(current_tuple), 3)
    latest_tuple += (0,) * (max_len - len(latest_tuple))
    current_tuple += (0,) * (max_len - len(current_tuple))
    return latest_tuple > current_tuple


class FlowApp(rumps.App):
    def __init__(self):
        super().__init__(ICON_IDLE, quit_button="Quit")
        self.status_item = rumps.MenuItem("State: Start")
        self.listener_item = rumps.MenuItem("Keys: Start")
        self.mic_item = rumps.MenuItem("Mic: Check")
        self.access_item = rumps.MenuItem("Access: Check")
        self.input_item = rumps.MenuItem("Input: Check")
        self.model_item = rumps.MenuItem("Model: Load")
        self.update_item = rumps.MenuItem("Update: Ready")
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
            self.update_item,
            self.last_error_item,
            None,
            rumps.MenuItem("Restart Listener", callback=self._menu_restart_listener),
            rumps.MenuItem("Test Mic", callback=self._menu_test_mic),
            rumps.MenuItem("Check Update", callback=self._menu_check_update),
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
        self.paste_target = None
        self._job_id = 0
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

    def _menu_check_update(self, _sender):
        if self.recording or self.busy:
            self.update_item.title = "Update: Busy"
            rumps.notification(
                "FastWhisper Flow",
                "Update skipped",
                "Finish recording/transcribing first",
            )
            return
        self.update_item.title = "Update: Checking"
        self._last_error = "None"
        self._update_health_menu()
        threading.Thread(target=self._check_update, daemon=True).start()

    @staticmethod
    def _alert(title: str, message: str):
        """Modal dialog via osascript: always visible, unlike notifications,
        which macOS hides unless the app is allowed in Notification settings."""
        subprocess.Popen(
            ["osascript",
             "-e", "on run argv",
             "-e", "display alert (item 1 of argv) message (item 2 of argv)"
                   " giving up after 15",
             "-e", "end run",
             title, message],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

    def _check_update(self):
        try:
            print("update: checking latest release", flush=True)
            release = self._fetch_latest_release()
            tag = release.get("tag_name", "")
            latest_version = tag.removeprefix("v")
            if not latest_version:
                raise RuntimeError("latest release has no tag")
            if not _is_newer_version(latest_version, APP_VERSION):
                self.update_item.title = f"Update: Current v{APP_VERSION}"
                self._update_health_menu()
                print(f"update: already current ({APP_VERSION})", flush=True)
                rumps.notification(
                    "FastWhisper Flow",
                    "Already up to date",
                    f"Current version {APP_VERSION}",
                )
                self._alert(
                    "FastWhisper Flow ✅",
                    f"You're up to date.\n\nInstalled: v{APP_VERSION}\n"
                    f"Latest release: v{latest_version}",
                )
                return

            asset = self._find_update_asset(release)
            self._validate_update_asset(asset)
            self.update_item.title = f"Update: v{latest_version}"
            rumps.notification(
                "FastWhisper Flow",
                f"Updating to v{latest_version}",
                "Downloading update",
            )
            self._alert(
                "FastWhisper Flow ⬇️",
                f"Update found: v{APP_VERSION} → v{latest_version}\n\n"
                "Downloading and installing now. The app restarts by itself "
                "when done.",
            )
            self._apply_update(asset, latest_version)
        except Exception as e:
            self.update_item.title = "Update: Failed"
            self._flash_error(f"update failed: {e}")
            self._alert(
                "FastWhisper Flow ⚠️",
                f"Update check failed:\n{e}",
            )

    def _fetch_latest_release(self):
        req = urllib.request.Request(
            GITHUB_LATEST_RELEASE,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": f"FastWhisperFlow/{APP_VERSION}",
            },
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _find_update_asset(self, release):
        assets = release.get("assets") or []
        for asset in assets:
            if asset.get("name") == INSTALLER_ASSET:
                return asset
        raise RuntimeError(f"{INSTALLER_ASSET} not found in latest release")

    def _validate_update_asset(self, asset):
        url = asset.get("browser_download_url", "")
        size = int(asset.get("size") or 0)
        digest = asset.get("digest") or ""
        if not url.startswith(GITHUB_ASSET_URL_PREFIX):
            raise RuntimeError("update asset URL is not trusted")
        if size <= 0 or size > MAX_UPDATE_ZIP_BYTES:
            raise RuntimeError("update asset size is invalid")
        if not digest or not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", digest):
            raise RuntimeError("update asset digest is invalid")

    def _apply_update(self, asset, latest_version):
        with tempfile.TemporaryDirectory(prefix="fastwhisper-update-") as tmp:
            tmp_path = Path(tmp)
            zip_path = tmp_path / INSTALLER_ASSET
            url = asset["browser_download_url"]
            req = urllib.request.Request(
                url,
                headers={"User-Agent": f"FastWhisperFlow/{APP_VERSION}"},
            )
            self.update_item.title = "Update: Downloading"
            expected_digest = asset.get("digest") or ""
            with urllib.request.urlopen(req, timeout=120) as resp:
                self._download_update(resp, zip_path, expected_digest)
            self.update_item.title = "Update: Installing"
            with zipfile.ZipFile(zip_path) as zf:
                payload_prefix = self._find_payload_prefix(zf)
                stage_dir = tmp_path / "payload-stage"
                updated = self._stage_update_payload(zf, payload_prefix, stage_dir)
            if "flow.py" not in updated or "VERSION" not in updated:
                raise RuntimeError("update payload is incomplete")
            self._install_update_payload(stage_dir, updated)

        print(
            f"updated to v{latest_version}; files: {', '.join(sorted(updated))}",
            flush=True,
        )
        rumps.notification(
            "FastWhisper Flow",
            f"Updated to v{latest_version}",
            "Restarting app",
        )
        self._alert(
            "FastWhisper Flow ✅",
            f"Updated to v{latest_version}. Restarting now — the 🎙 icon "
            "reappears in a few seconds.",
        )
        self.update_item.title = "Update: Restarting"
        time.sleep(1)
        self._restart_app()

    @staticmethod
    def _download_update(resp, zip_path: Path, expected_digest: str):
        expected_sha = expected_digest.removeprefix("sha256:").lower()
        digest = hashlib.sha256()
        total = 0
        with zip_path.open("wb") as out:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_UPDATE_ZIP_BYTES:
                    raise RuntimeError("update download is too large")
                digest.update(chunk)
                out.write(chunk)
        actual_sha = digest.hexdigest()
        if expected_sha and actual_sha != expected_sha:
            raise RuntimeError("update digest mismatch")

    @staticmethod
    def _find_payload_prefix(zf: zipfile.ZipFile):
        prefixes = {
            name.split("Contents/Resources/payload/", 1)[0]
            + "Contents/Resources/payload/"
            for name in zf.namelist()
            if "Contents/Resources/payload/" in name and not name.endswith("/")
        }
        if len(prefixes) != 1:
            raise RuntimeError("installer payload is ambiguous")
        return prefixes.pop()

    @staticmethod
    def _stage_update_payload(zf: zipfile.ZipFile, payload_prefix: str, stage_dir: Path):
        stage_dir.mkdir()
        updated = []
        total = 0
        infos = {info.filename: info for info in zf.infolist()}
        for name in sorted(UPDATE_FILES):
            member = payload_prefix + name
            info = infos.get(member)
            if info is None:
                continue
            if info.is_dir() or info.file_size < 0:
                raise RuntimeError("update payload contains invalid entry")
            total += info.file_size
            if total > MAX_UPDATE_PAYLOAD_BYTES:
                raise RuntimeError("update payload is too large")
            dst = stage_dir / name
            with zf.open(info) as src, dst.open("wb") as out:
                shutil.copyfileobj(src, out)
            updated.append(name)
        return updated

    @staticmethod
    def _install_update_payload(stage_dir: Path, updated):
        for name in updated:
            src = stage_dir / name
            dst = APP_DIR / name
            tmp_dst = APP_DIR / f".{name}.update"
            shutil.copy2(src, tmp_dst)
            if name.endswith(".sh"):
                tmp_dst.chmod(tmp_dst.stat().st_mode | 0o755)
            os.replace(tmp_dst, dst)

    def _restart_app(self):
        pid = os.getpid()
        app_dir = shlex.quote(str(APP_DIR))
        log_path = shlex.quote(LOG_PATH)
        script = (
            f"PID={pid}; APP_DIR={app_dir}; LOG={log_path}; "
            "("
            "while kill -0 \"$PID\" 2>/dev/null; do sleep 0.2; done; "
            "cd \"$APP_DIR\"; "
            "if [[ -d \"FastWhisper Toggle.app\" ]]; then "
            "open -g -n \"FastWhisper Toggle.app\"; "
            "else ./flow.sh start; fi"
            ") >> \"$LOG\" 2>&1 &"
        )
        print("update: scheduling external restart through Toggle app", flush=True)
        subprocess.Popen(
            ["/bin/zsh", "-lc", script],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        self._reset_state()
        with self._listener_lock:
            if self.listener is not None:
                try:
                    self.listener.stop()
                except Exception:
                    pass
        os._exit(0)

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
        self._job_id += 1
        self.recording = False
        self.busy = False
        self.hotkey_down = False
        self.shift_down = False
        self.option_down = False
        self.paste_target = None
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
            self.paste_target = _frontmost_app_info()
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
                f"(loopback={self.loopback}, multilingual={self.multilingual}, "
                f"target={self.paste_target})",
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
            self._job_id += 1
            job_id = self._job_id
            loopback = self.loopback
            multilingual = self.multilingual
            paste_target = self.paste_target
            timeout = threading.Timer(
                TRANSCRIBE_TIMEOUT_SECONDS,
                self._timeout_job,
                args=(job_id,),
            )
            timeout.daemon = True
            timeout.start()
            threading.Thread(
                target=self._process,
                args=(audio, job_id, loopback, multilingual, paste_target),
                daemon=True,
            ).start()
        elif key == HOTKEY:
            print(
                "hotkey release ignored "
                f"(recording={self.recording}, busy={self.busy}, "
                f"model_ready={self.transcribe is not None})",
                flush=True,
            )

    # --------------------------------------------------------- pipeline
    def _timeout_job(self, job_id: int):
        if self.busy and job_id == self._job_id:
            print(
                f"transcription timeout after {TRANSCRIBE_TIMEOUT_SECONDS}s; "
                "resetting UI and discarding stale result",
                flush=True,
            )
            self._job_id += 1
            self.busy = False
            self.title = ICON_WARN
            self._flash_error("transcription timed out — try again")
            self._update_health_menu()

    def _process(
        self,
        audio: np.ndarray,
        job_id: int,
        loopback: bool,
        multilingual: bool,
        paste_target,
    ):
        try:
            peak = float(np.abs(audio).max())
            rms = float(np.sqrt(np.mean(np.square(audio)))) if len(audio) else 0.0
            print(f"audio level: peak {peak:.4f}, rms {rms:.6f}", flush=True)
            if peak <= NO_SIGNAL_PEAK or rms <= NO_SIGNAL_RMS:
                # near-zero samples = macOS/CoreAudio gave us no usable signal:
                # mic permission reset, muted input, or an unrouted loopback.
                self._flash_error(
                    f"no usable audio (peak {peak:.4f}) — check mic input"
                )
                return
            if peak < SILENCE_PEAK:
                gain = min(AUTO_GAIN_TARGET_PEAK / peak, MAX_AUTO_GAIN)
                audio = np.clip(audio * gain, -1.0, 1.0).astype(np.float32)
                boosted_peak = float(np.abs(audio).max())
                print(
                    "quiet audio auto-boosted "
                    f"(peak {peak:.4f}, rms {rms:.6f}, gain {gain:.1f}, "
                    f"new_peak {boosted_peak:.3f})",
                    flush=True,
                )
            if loopback:
                model, lang = LOOPBACK_MODEL, LOOPBACK_LANGUAGE
            elif multilingual:
                model, lang = LOOPBACK_MODEL, MULTILINGUAL_LANGUAGE
            else:
                model, lang = MODEL, LANGUAGE
            result = self.transcribe(
                audio, path_or_hf_repo=model, language=lang
            )
            if job_id != self._job_id:
                print("discarding stale transcription result", flush=True)
                return
            text = clean(result["text"])
            if text:
                paste_text(text, paste_target)
        except Exception as e:
            print(f"transcription error: {e}")
        finally:
            if job_id == self._job_id:
                self.busy = False
                if self.title == ICON_WARN and time.time() < self._error_until:
                    pass  # keep the current error flash visible
                else:
                    self.title = ICON_IDLE
                self._update_health_menu()


if __name__ == "__main__":
    FlowApp().run()
