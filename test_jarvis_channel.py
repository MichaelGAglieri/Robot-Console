# SPDX-License-Identifier: GPL-3.0-only
"""Private channel contract: isolated data, mock serial writes, no real hardware."""
import copy
import json
import os
import socket
import stat
import threading
import time
import uuid
from unittest.mock import patch
from jarvis_channel import JarvisChannel
from test_studio import StudioFixture


class ChannelTests(StudioFixture):
    def setUp(self):
        super().setUp()
        self.ch = JarvisChannel(self.c, self.s, self.folder)
        self.ch.update_ui()
        self.c.action(dict(op='connect', mode='demo'))
        self.c.action(dict(op='home_set'))
        self.c.limits = [[-30, 30] for _ in range(6)]
        self.c.write.reset_mock()
        self.spawned = []
        self.spawn = patch.object(self.c, 'spawn', side_effect=self.spawned.append)
        self.spawn.start()

    def tearDown(self):
        self.ch.close()
        self.spawn.stop()
        self.s.close()
        super().tearDown()

    def request(self, op, **args):
        return dict(op=op, session=self.ch.session, epoch=self.ch.cancelled,
                    id=str(uuid.uuid4()), expires=time.time()+20, **args)

    def call(self, op, **args):
        return self.ch.dispatch(self.request(op, **args))

    def pose(self, name, pos, enabled=True):
        return dict(name=name, mode='demo', pos=[pos,0,0,0,0,0], path=[], enabled=enabled, dwell=0., grip='non comandata')

    def test_relative_and_absolute_jog_keep_limits(self):
        self.c.pos[0] = 5
        with patch.object(self.c, 'action', wraps=self.c.action) as action:
            self.call('jog', joint=1, degrees=20, mode='relative')
            self.assertEqual(action.call_args.args[0], dict(op='jog', axis=0, delta=20))
            self.call('jog', joint=1, degrees=20, mode='absolute')
            self.assertEqual(action.call_args.args[0], dict(op='jog', axis=0, delta=15))
        self.assertEqual(self.c.limits[0], [-30,30])
        self.assertEqual(len(self.spawned), 2)

    def test_blocked_motion_never_spawns(self):
        for field, value in [('home',False), ('identified',False), ('busy',True), ('firmware_busy',True)]:
            old=getattr(self.c,field);setattr(self.c,field,value)
            with self.assertRaises(ValueError):self.call('jog',joint=1,degrees=20,mode='relative')
            setattr(self.c,field,old)
        self.c.limits[0]=[0,0]
        with self.assertRaisesRegex(ValueError,'limiti'):self.call('jog',joint=1,degrees=20,mode='relative')
        self.c.limits[0]=[-5,5]
        with self.assertRaisesRegex(ValueError,'limiti'):self.call('jog',joint=1,degrees=20,mode='relative')
        self.c.axes_enabled[0]=False
        with self.assertRaisesRegex(ValueError,'disabilitato'):self.call('jog',joint=1,degrees=1,mode='relative')
        self.assertEqual(self.spawned,[])
        self.c.write.assert_not_called()

    def test_sequence_uses_enabled_order_without_editing(self):
        self.c.sequence=[self.pose('allineamento 1',1),self.pose('esclusa',2,False),self.pose('allineamento 2',3)]
        before=copy.deepcopy(self.c.sequence)
        self.ch.update_ui(dict(return_home=True))
        with patch.object(self.c,'action',wraps=self.c.action) as action:
            reply=self.call('sequence')
            sent=action.call_args.args[0]
            self.assertEqual(sent['op'],'play');self.assertFalse(sent['repeat']);self.assertTrue(sent['return_home'])
        self.assertIn('allineamento 1, allineamento 2',reply['message'])
        self.assertEqual(before,self.c.sequence)
        self.assertEqual(len(self.spawned),1)

    def test_named_pose_and_ambiguous_names(self):
        self.c.sequence=[self.pose('A',1),self.pose('B',2)]
        before=copy.deepcopy(self.c.sequence)
        self.call('sequence',name='b')
        self.assertEqual(before,self.c.sequence)
        self.c.sequence.append(self.pose('B',3))
        with self.assertRaisesRegex(ValueError,'duplicato'):self.call('sequence',name='B')
        self.assertEqual(len(self.spawned),1)

    def test_sequence_preflight_blocks_bad_route_and_empty_selection(self):
        self.c.sequence=[self.pose('A',50)]
        with self.assertRaises(ValueError):self.call('sequence')
        self.c.sequence[0]['enabled']=False
        with self.assertRaisesRegex(ValueError,'almeno una'):self.call('sequence')
        self.assertEqual(self.spawned,[])

    def test_expired_session_duplicate_and_old_epoch_are_rejected(self):
        data=self.request('jog',joint=1,degrees=1,mode='relative')
        self.ch.dispatch(data)
        with self.assertRaisesRegex(ValueError,'duplicata'):self.ch.dispatch(data)
        for fields in [dict(session='old'),dict(expires=time.time()-1),dict(epoch=-1)]:
            bad=self.request('jog',joint=1,degrees=1,mode='relative');bad.update(fields)
            with self.assertRaises(ValueError):self.ch.dispatch(bad)
        self.assertEqual(len(self.spawned),1)

    def test_stop_invalidates_pending_command_and_quit_reuses_stop(self):
        pending=self.request('jog',joint=1,degrees=1,mode='relative')
        self.call('stop')
        with self.assertRaises(ValueError):self.ch.dispatch(pending)
        self.assertFalse(self.c.home)
        self.assertFalse(self.ch.quit_requested)
        self.call('quit')
        self.assertTrue(self.ch.quit_requested)
        self.assertEqual(self.spawned,[])
        self.c.write.assert_called_with('!')

    def test_quit_during_firmware_stops_without_quitting(self):
        self.c.firmware_busy=True
        with self.assertRaisesRegex(ValueError,'firmware'):self.call('quit')
        self.assertFalse(self.ch.quit_requested)
        self.c.write.assert_called_with('!')

    def test_exhausted_request_cache_does_not_block_stop_or_quit(self):
        self.ch.seen=set(str(i) for i in range(10000))
        self.call("stop");self.call("quit")
        self.assertTrue(self.ch.quit_requested)

    def test_disabled_named_pose_is_not_silently_enabled(self):
        self.c.sequence=[self.pose("A",1,False)]
        with self.assertRaisesRegex(ValueError,"disabilitata"):self.call("sequence",name="A")
        self.assertFalse(self.c.sequence[0]["enabled"])
        self.assertEqual(self.spawned,[])

    def test_ui_heartbeat_and_pending_speed_are_required(self):
        self.ch.ui_time=time.monotonic()-3
        with self.assertRaisesRegex(ValueError,'Interfaccia'):self.call('jog',joint=1,degrees=1,mode='relative')
        self.ch.update_ui(dict(speed_pending=True))
        with self.assertRaisesRegex(ValueError,'velocità'):self.call('jog',joint=1,degrees=1,mode='relative')
        self.assertEqual(self.spawned,[])

    def test_enable_already_ready_preserves_reference_limits_and_position(self):
        self.c.mode='robot';self.c.pos[0]=4
        with patch.object(self.c,'action',wraps=self.c.action) as action:
            self.call('enable',home_confirmed=True)
            self.assertFalse(any(c.args[0]['op'] in ('connect','home_set') for c in action.call_args_list))
        self.assertEqual(self.c.pos[0],4);self.assertEqual(self.c.limits[0],[-30,30])
        self.assertFalse(self.c.operator_collision_checks)
        self.c.write.assert_not_called()

    def test_enable_waits_then_sets_home_and_warning_mode_after_connect(self):
        self.c.connected=False
        original=self.c.action
        def fake_action(request):
            if request['op']=='connect':
                # Exercise orchestration without opening a serial device.
                original(dict(op='connect',mode='demo'));self.c.mode='robot'
            else:original(request)
        with patch.object(self.c,'state',wraps=self.c.state) as state, patch.object(self.c,'action',side_effect=fake_action) as action:
            state.side_effect=lambda:dict(ports=['/dev/cu.usbmodem123'])
            self.call('enable',home_confirmed=True)
            ops=[c.args[0]['op'] for c in action.call_args_list]
            self.assertEqual(ops,['connect','home_set'])
        self.assertTrue(self.c.home);self.assertFalse(self.c.operator_collision_checks)
        self.assertEqual(self.c.limits,[[0,0]]*6)
        self.c.write.assert_called_with('~arm\n')

    def test_enable_missing_or_ambiguous_port_and_demo_refused(self):
        with self.assertRaisesRegex(ValueError,'Anteprima'):self.call('enable',home_confirmed=True)
        self.c.connected=False
        for ports in [[],['/dev/cu.Bluetooth'],['/dev/cu.usbmodem1','/dev/cu.usbmodem2']]:
            with patch.object(self.c,'state',return_value=dict(ports=ports)):
                with self.assertRaises(ValueError):self.call('enable',home_confirmed=True)
        self.c.write.assert_not_called()

    def test_stop_during_enable_cannot_later_arm(self):
        self.c.mode='robot';self.c.identified=False;self.c.home=False
        errors=[]
        def enable():
            try:self.call('enable',home_confirmed=True)
            except ValueError as error:errors.append(str(error))
        worker=threading.Thread(target=enable);worker.start()
        time.sleep(.08);self.call('stop');self.c.identified=True
        worker.join(2)
        self.assertFalse(worker.is_alive());self.assertTrue(errors)
        self.assertFalse(self.c.home)
        self.assertNotIn('~arm\n',[c.args[0] for c in self.c.write.call_args_list])

    def test_socket_permissions_protocol_and_rejection(self):
        self.ch.start()
        self.assertEqual(stat.S_IMODE(self.ch.folder.stat().st_mode),0o700)
        self.assertEqual(stat.S_IMODE(self.ch.path.stat().st_mode),0o600)
        def wire(data):
            with socket.socket(socket.AF_UNIX) as client:
                client.settimeout(2);client.connect(str(self.ch.path));client.sendall(json.dumps(data).encode()+b'\n')
                return json.loads(client.makefile('rb').readline())
        self.assertEqual(wire(dict(op='status'))['session'],self.ch.session)
        self.assertFalse(wire(dict(op='firmware_upload'))['ok'])
        self.assertFalse(wire(dict(op='jog',session='bad'))['ok'])
        self.c.write.assert_not_called()
