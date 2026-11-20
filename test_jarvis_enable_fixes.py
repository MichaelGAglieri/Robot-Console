# SPDX-License-Identifier: GPL-3.0-only
"""Fixes of 10 November 2026 for "abilita robot": stale serial lines, HOME after the
USB quiet window, last limits restored. Isolated data, mock serial, no hardware."""
import json
import os
import threading
import time
from unittest.mock import patch
import server
from test_jarvis_channel import ChannelTests


class StaleLines(ChannelTests):
    def test_leftover_halt_and_watchdog_before_identity_are_ignored(self):
        c = self.c
        c.connected = True; c.identified = False; c.home = False; c.busy = False; c.awaiting_halt = False
        generation = c.generation
        c.receive('HALTED'); c.receive('ERROR WATCHDOG')
        self.assertEqual(c.generation, generation)
        self.assertNotIn('WATCHDOG', c.error)

    def test_watchdog_after_identity_still_halts(self):
        c = self.c
        c.connected = True; c.identified = True; c.home = True
        c.receive('ERROR WATCHDOG')
        self.assertFalse(c.home); self.assertIn('WATCHDOG', c.error)


class EnableFixes(ChannelTests):
    def fake_connect(self):
        original = self.c.action
        def fake_action(request):
            if request['op'] == 'connect':
                original(dict(op='connect', mode='demo')); self.c.mode = 'robot'
            else:
                original(request)
        return fake_action

    def enable(self):
        self.c.connected = False
        with patch.object(self.c, 'state', wraps=self.c.state) as state, \
             patch.object(self.c, 'action', side_effect=self.fake_connect()) as action:
            state.side_effect = lambda: dict(ports=['/dev/cu.usbmodem123'])
            result = self.call('enable', home_confirmed=True)
            return result, [c.args[0] for c in action.call_args_list]

    def test_saved_robot_limits_are_applied_after_home(self):
        saved = [[-5, 5], [-90, 45], [-90, 0], [-180, 180], [-90, 90], [-90, 90]]
        (self.folder / 'limiti.json').write_text(json.dumps(dict(robot=saved, demo=[[-1, 1]] * 6)))
        result, requests = self.enable()
        self.assertEqual([r['op'] for r in requests], ['connect', 'home_set', 'limits'])
        self.assertEqual(self.c.limits, saved)
        self.assertIn('Ultimi limiti applicati', result['message'])

    def test_without_saved_limits_it_asks(self):
        result, requests = self.enable()
        self.assertEqual([r['op'] for r in requests], ['connect', 'home_set'])
        self.assertIn('Quali limiti', result['message'])

    def test_invalid_saved_limits_are_not_applied(self):
        (self.folder / 'limiti.json').write_text(json.dumps(dict(robot=[[5, 10]] * 6)))
        result, requests = self.enable()
        self.assertNotIn('limits', [r['op'] for r in requests])

    def test_home_waits_for_quiet_window_with_real_usb(self):
        # With a USB descriptor open the ARM must come after boot_ready_at (heartbeat flowing).
        self.c.connected = False
        original = self.c.action
        armed = []
        def fake_action(request):
            if request['op'] == 'connect':
                original(dict(op='connect', mode='demo')); self.c.mode = 'robot'
                self.c.fd = 99; self.c.boot_ready_at = time.monotonic() + .6
            elif request['op'] == 'home_set':
                armed.append(time.monotonic()); self.c.fd = None; original(request)
            else:
                original(request)
        refresh = threading.Event()
        def keep_ui_alive():
            while not refresh.wait(.1):
                self.ch.update_ui()
        thread = threading.Thread(target=keep_ui_alive); thread.start()
        try:
            with patch.object(self.c, 'state', wraps=self.c.state) as state, patch.object(self.c, 'action', side_effect=fake_action):
                state.side_effect = lambda: dict(ports=['/dev/cu.usbmodem123'])
                ready = self.c.boot_ready_at
                self.call('enable', home_confirmed=True)
        finally:
            refresh.set(); thread.join()
        self.assertTrue(armed)
        self.assertGreaterEqual(armed[0], self.c.boot_ready_at)


class SilentMega(ChannelTests):
    def test_silent_board_is_reopened_once_with_reset(self):
        self.c.connected = False
        original = self.c.action
        connects = []
        def fake_action(request):
            if request['op'] == 'connect':
                original(dict(op='connect', mode='demo')); self.c.mode = 'robot'
                self.c.identified = False; self.c.speed_confirmed = False
                self.c.fd, _ = os.pipe(); now = time.monotonic()  # a real, silent descriptor
                self.c.connected_at = now; self.c.boot_ready_at = now + .1; self.c.last_hello = now - 4
                connects.append(now)
                if len(connects) == 2:
                    def answer():
                        time.sleep(.3)
                        with self.c.lock:
                            self.c.identified = True; self.c.speed_confirmed = True
                    threading.Thread(target=answer).start()
            elif request['op'] == 'home_set':
                self.c.fd = None; original(request)
            else:
                original(request)
        alive = threading.Event()
        def keep_ui_alive():
            while not alive.wait(.1):
                self.ch.update_ui()
        thread = threading.Thread(target=keep_ui_alive); thread.start()
        try:
            with patch.object(self.c, 'state', wraps=self.c.state) as state, \
                 patch.object(self.c, 'action', side_effect=fake_action), \
                 patch('fcntl.ioctl') as ioctl:
                state.side_effect = lambda: dict(ports=['/dev/cu.usbmodem1301'])
                result = self.call('enable', home_confirmed=True)
        finally:
            alive.set(); thread.join()
        self.assertEqual(len(connects), 2)
        self.assertEqual(ioctl.call_count, 2)  # DTR/RTS down, then up: the board restarts
        self.assertTrue(self.c.home)
        self.assertIn('Robot abilitato', result['message'])

    def test_connected_but_unidentified_starts_again_from_the_port(self):
        self.c.mode = 'robot'; self.c.identified = False
        with patch.object(self.c, 'state', return_value=dict(ports=[])):
            with self.assertRaisesRegex(ValueError, 'Mega non collegata'):
                self.call('enable', home_confirmed=True)


class ReturnHome(ChannelTests):
    def test_home_plans_and_starts_the_return_without_token(self):
        self.c.pos = [5., 0., 0., 0., 0., 0.]
        result = self.call('home')
        self.assertIn('HOME avviato', result['message'])
        self.assertTrue(self.spawned)

    def test_home_when_already_there(self):
        self.c.pos = [0.] * 6
        self.assertIn('già in HOME', self.call('home')['message'])
        self.assertFalse(self.spawned)

    def test_home_refused_without_reference(self):
        self.c.pos = [5., 0., 0., 0., 0., 0.]; self.c.home = False
        with self.assertRaises(ValueError):
            self.call('home')


if __name__ == '__main__':
    import unittest
    unittest.main()
