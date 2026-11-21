# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Platform layer: data folder, single instance, tool lookup and serial port names."""
import os, subprocess, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import platform_support as ps
import serial_transport as st


class DataFolderTests(unittest.TestCase):
    def test_override_wins(self):
        with patch.dict(os.environ, {'DOC_REGIA_DATA': '/tmp/robot-console-x'}):
            self.assertEqual(ps.data_folder(), Path('/tmp/robot-console-x'))

    def test_per_system_default(self):
        env = {k: v for k, v in os.environ.items() if k not in ('DOC_REGIA_DATA', 'XDG_DATA_HOME')}
        with patch.dict(os.environ, env, clear=True):
            with patch.object(ps, 'MACOS', True), patch.object(ps, 'WINDOWS', False):
                self.assertTrue(str(ps.data_folder()).endswith(os.path.join('Library', 'Application Support', 'DOC Regia')))
            with patch.object(ps, 'MACOS', False), patch.object(ps, 'WINDOWS', False):
                self.assertTrue(str(ps.data_folder()).endswith(os.path.join('.local', 'share', 'doc-regia')))
            with patch.object(ps, 'MACOS', False), patch.object(ps, 'WINDOWS', True), patch.dict(os.environ, {'APPDATA': 'C:/Users/x/AppData/Roaming'}):
                self.assertEqual(ps.data_folder(), Path('C:/Users/x/AppData/Roaming') / 'DOC Regia')
        with patch.dict(os.environ, {**env, 'XDG_DATA_HOME': '/xdg'}, clear=True), patch.object(ps, 'MACOS', False), patch.object(ps, 'WINDOWS', False):
            self.assertEqual(ps.data_folder(), Path('/xdg/doc-regia'))


class InstanceLockTests(unittest.TestCase):
    def test_second_controller_is_refused_in_another_process(self):
        with tempfile.TemporaryDirectory() as folder:
            first = ps.InstanceLock(folder)
            self.assertTrue(first.acquire())
            code = 'import sys,platform_support as p;sys.exit(0 if p.InstanceLock(sys.argv[1]).acquire() else 3)'
            root = str(Path(ps.__file__).parent)
            result = subprocess.run([sys.executable, '-c', code, folder], cwd=root, env={**os.environ, 'PYTHONPATH': root})
            self.assertEqual(result.returncode, 3)
            first.release()
            result = subprocess.run([sys.executable, '-c', code, folder], cwd=root, env={**os.environ, 'PYTHONPATH': root})
            self.assertEqual(result.returncode, 0)


class ToolLookupTests(unittest.TestCase):
    def test_missing_tools_give_empty_strings(self):
        with patch.object(ps.shutil, 'which', return_value=None), patch.object(ps, '_executable', return_value=False):
            self.assertEqual(ps.find_arduino_cli('/nowhere'), '')
            self.assertEqual(ps.find_ollama(), '')
            self.assertEqual(ps.find_pixi(), '')
            self.assertEqual(ps.find_webots(), '')

    def test_path_lookup_first(self):
        with tempfile.TemporaryDirectory() as folder:
            tool = Path(folder) / ('arduino-cli.exe' if ps.WINDOWS else 'arduino-cli')
            tool.write_text('')
            tool.chmod(0o755)
            with patch.object(ps.shutil, 'which', return_value=str(tool)):
                self.assertEqual(ps.find_arduino_cli('/nowhere'), str(tool))

    def test_pixi_environment_layout(self):
        with patch.object(ps, 'WINDOWS', False):
            self.assertEqual(ps.pixi_env_binary('/p', 'rviz2'), Path('/p/.pixi/envs/default/bin/rviz2'))


class SerialNameTests(unittest.TestCase):
    def test_board_names_per_system(self):
        with patch.object(st, 'WINDOWS', False), patch.object(st, 'MACOS', True):
            self.assertTrue(st.looks_like_board('/dev/cu.usbmodem1101'))
            self.assertTrue(st.looks_like_board('/dev/cu.wchusbserial110'))
            self.assertFalse(st.looks_like_board('/dev/cu.Bluetooth-Incoming-Port'))
        with patch.object(st, 'WINDOWS', False), patch.object(st, 'MACOS', False):
            self.assertTrue(st.looks_like_board('/dev/ttyACM0'))
            self.assertTrue(st.looks_like_board('/dev/ttyUSB1'))
            self.assertFalse(st.looks_like_board('/dev/ttyS0'))
        with patch.object(st, 'WINDOWS', True):
            self.assertTrue(st.looks_like_board('COM7'))
            self.assertFalse(st.looks_like_board('/dev/ttyACM0'))

    def test_clone_boards_can_connect_on_macos(self):
        # Before 2.1 a CH340 Mega could be programmed but not connected.
        listing = {'/dev/cu.usbmodem*': ['/dev/cu.usbmodem1'], '/dev/cu.wchusbserial*': ['/dev/cu.wchusbserial2']}
        with patch.object(st, 'WINDOWS', False), patch.object(st, 'MACOS', True), \
             patch.object(st.glob, 'glob', side_effect=lambda pattern: listing.get(pattern, [])):
            self.assertEqual(st.candidate_ports(), ['/dev/cu.usbmodem1', '/dev/cu.wchusbserial2'])

    @unittest.skipIf(st.WINDOWS, 'POSIX descriptors')
    def test_posix_read_write_close_on_a_pipe(self):
        r, w = os.pipe()
        st.write(w, b'DOC REGIA 4\n')
        self.assertEqual(st.read(r), b'DOC REGIA 4\n')
        self.assertIsNone(st.read(r))
        st.close(w)
        with self.assertRaises(OSError):
            st.read(r)
        st.close(r)


if __name__ == '__main__':
    unittest.main()
