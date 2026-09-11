"""Focused regression tests for long-running resource management."""

import threading
import unittest
from unittest import mock

from Quartz import kCGEventTapDisabledByTimeout

import flow


class RecorderRecoveryTests(unittest.TestCase):
    def test_failed_stream_is_closed_before_one_device_refresh_retry(self):
        recorder = flow.Recorder()
        failed_stream = mock.Mock()
        starts = 0

        def start_locked(_device):
            nonlocal starts
            starts += 1
            if starts == 1:
                recorder._stream = failed_stream
                raise RuntimeError("stale device")

        recorder._start_locked = start_locked
        recorder._refresh_devices_locked = mock.Mock()

        recorder.start()

        self.assertEqual(starts, 2)
        failed_stream.close.assert_called_once_with()
        recorder._refresh_devices_locked.assert_called_once_with()


class AudioOutputRouterTests(unittest.TestCase):
    @mock.patch.object(flow.shutil, "which", return_value=None)
    @mock.patch.object(flow.Path, "is_file")
    def test_finds_homebrew_tool_when_app_path_is_minimal(
        self, is_file, _which
    ):
        is_file.return_value = True

        self.assertEqual(
            flow.AudioOutputRouter._tool_path(),
            "/opt/homebrew/bin/SwitchAudioSource",
        )

    def test_switches_to_multi_output_and_restores_previous_output(self):
        router = flow.AudioOutputRouter()
        calls = []
        router._current = "MacBook Pro Speakers"
        router._error = None
        router._spawn = lambda *args: calls.append(args)
        router.start()
        router.stop()

        self.assertIn(
            ("-t", "output", "-s", "Multi-Output Device"), calls
        )
        self.assertEqual(
            calls[-1], ("-t", "output", "-s", "MacBook Pro Speakers")
        )

    def test_reports_missing_multi_output_device(self):
        router = flow.AudioOutputRouter()
        router._run = mock.Mock(return_value="MacBook Pro Speakers")
        router.refresh()

        with self.assertRaisesRegex(RuntimeError, "Audio MIDI Setup"):
            router.start()

    def test_unmutes_blackhole_and_restores_original_input(self):
        router = flow.AudioOutputRouter()
        calls = []

        def run(*args):
            calls.append(args)
            if args == ("-c", "-t", "input"):
                return "Maono DM40 Mic USB 2"
            return ""

        router._run = run
        router.prepare_loopback()

        self.assertEqual(
            calls,
            [
                ("-c", "-t", "input"),
                ("-t", "input", "-s", "BlackHole 2ch", "-m", "unmute"),
                ("-t", "input", "-s", "Maono DM40 Mic USB 2"),
            ],
        )

    def test_loopback_unmute_failure_still_restores_original_input(self):
        router = flow.AudioOutputRouter()
        calls = []

        def run(*args):
            calls.append(args)
            if args == ("-c", "-t", "input"):
                return "MacBook Pro Microphone"
            if "unmute" in args:
                raise RuntimeError("driver unavailable")
            return ""

        router._run = run
        router.prepare_loopback()

        self.assertEqual(
            calls[-1],
            ("-t", "input", "-s", "MacBook Pro Microphone"),
        )

    def test_hotkey_path_does_not_run_synchronous_commands(self):
        router = flow.AudioOutputRouter()
        router._current = "MacBook Pro Speakers"
        router._error = None
        router._run = mock.Mock(side_effect=AssertionError("blocking command"))
        router._spawn = mock.Mock()

        router.start()

        router._run.assert_not_called()
        router._spawn.assert_called_once_with(
            "-t", "output", "-s", "Multi-Output Device"
        )


class ListenerRecoveryTests(unittest.TestCase):
    def test_shift_arriving_after_command_selects_loopback(self):
        app = object.__new__(flow.FlowApp)
        app.shift_down = False
        app.option_down = False
        app.hotkey_down = False
        app.recording = False
        app.busy = False
        app.transcribe = object()
        app.recorder = mock.Mock()
        app.output_router = mock.Mock()
        app.paste_target = None
        app._start_timer = None

        with mock.patch.object(flow.threading, "Timer") as timer_type:
            app._handle_press(flow.HOTKEY)
            app._handle_press(flow.Key.shift_r)
            begin_recording = timer_type.call_args.args[1]
        with mock.patch.object(flow, "_frontmost_app_info", return_value=None):
            begin_recording()

        app.output_router.start.assert_called_once_with()
        app.recorder.start.assert_called_once_with(flow.LOOPBACK_DEVICE)
        self.assertTrue(app.loopback)
        self.assertEqual(app.title, flow.ICON_REC_SYS)

    def test_disabled_event_tap_is_reenabled_in_place(self):
        listener = object.__new__(flow.ResilientKeyboardListener)
        with mock.patch("Quartz.CGEventTapEnable") as enable:
            listener._handle_message(
                "event-tap", kCGEventTapDisabledByTimeout, None, None, False
            )
        enable.assert_called_once_with("event-tap", True)

    @mock.patch.object(flow, "ResilientKeyboardListener")
    def test_listener_is_joined_before_replacement(self, listener_type):
        app = object.__new__(flow.FlowApp)
        app._listener_lock = threading.Lock()
        old = mock.Mock()
        old.is_alive.return_value = False
        app.listener = old
        replacement = listener_type.return_value

        self.assertTrue(app._start_listener())

        old.stop.assert_called_once_with()
        old.join.assert_called_once_with(timeout=2.0)
        replacement.start.assert_called_once_with()
        self.assertIs(app.listener, replacement)


if __name__ == "__main__":
    unittest.main()
