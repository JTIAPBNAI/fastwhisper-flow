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


class ListenerRecoveryTests(unittest.TestCase):
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
