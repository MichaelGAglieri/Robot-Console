# SPDX-License-Identifier: GPL-3.0-only
import copy,json,threading,time
from local_api import LocalAPI
from robot_console_client import RobotConsole,Adapter,APIError
from test_program import ProgramBase
from studio import Studio

class IOAdapterTests(ProgramBase):
    def setUp(self):
        super().setUp();self.s.define_sensor('presente','digital');self.s.action(dict(op='studio_output_add',name='lampada'))
        self.api=LocalAPI(self.c,self.s);self.api.start();self.api.commands.configure(True,True);self.client=RobotConsole(self.api.state()['url'],self.api.token);self.adapters=[]
    def tearDown(self):
        for a in self.adapters:a.close()
        self.api.stop();self.wait(timeout=3);super().tearDown()
    def adapter(self,**kwargs):
        a=Adapter(self.client,'Test',**kwargs);self.adapters.append(a);return a
    def output(self,timeout=.4):return [dict(kind='output',name='Segnale',output='lampada',output_value=True,timeout=timeout)]
    def test_unregistered_and_simulated_inputs_cannot_be_measurements(self):
        self.robot();self.client.sensor('presente',1)
        with self.assertRaisesRegex(ValueError,'simulato'):self.s.movej.read_sensor('presente')
        a=self.adapter(inputs=['presente'],simulated=True);a.publish('presente',1)
        with self.assertRaisesRegex(ValueError,'simulato'):self.s.movej.read_sensor('presente')
    def test_input_freshness_heartbeat_and_session_ownership(self):
        self.robot();a=self.adapter(inputs=['presente'],simulated=False);a.publish('presente',1)
        self.assertEqual(self.s.movej.read_sensor('presente'),1)
        with self.assertRaises(APIError):self.adapter(inputs=['presente'],simulated=False)
        self.s.sensors['presente']['stamp']-=2
        with self.assertRaisesRegex(ValueError,'non aggiornato'):self.s.movej.read_sensor('presente')
        a.publish('presente',1);self.s.io.adapters[a.id]['heartbeat']-=2
        with self.assertRaisesRegex(ValueError,'non disponibile'):self.s.movej.read_sensor('presente')
        with self.assertRaises(APIError):a.publish('presente',1)
    def test_output_is_planned_and_simulated_without_external_ack(self):
        p=self.client.plan(self.output());self.assertEqual(p['stages'][0]['kind'],'output');self.assertAlmostEqual(p['duration_max'],.4)
        run=self.client.execute(p);self.client.wait(run,timeout=5)
        value=self.client.io()['outputs'][0];self.assertTrue(value['value']);self.assertTrue(value['simulated']);self.assertEqual(self.lines,[])
        self.s.outputs['other']='digital'
        with self.assertRaises(ValueError):self.s.movej.validate(p['id'])
    def start_real_output(self,timeout=.4):
        self.robot();p=self.client.plan(self.output(timeout));run=self.client.execute(p);self.api.commands.approve(run['id'],True);return run
    def test_real_output_waits_for_its_adapter_and_matches_ack(self):
        a=self.adapter(outputs=['lampada'],simulated=False);run=self.start_real_output()
        self.wait(lambda:bool(a.requests()));request=a.requests()[0]
        self.assertFalse(self.s.movej.exec_done);a.acknowledge(request,True)
        self.assertEqual(self.client.wait(run,timeout=5)['status'],'completed')
        self.assertFalse(self.client.io()['outputs'][0]['simulated'])
        with self.assertRaises(APIError):a.acknowledge(request,True) # one-use
        self.assertEqual(self.lines,[])
    def test_missing_output_adapter_timeout_and_wrong_ack_stop(self):
        run=self.start_real_output();self.wait();self.assertIn('senza adattatore',self.s.movej.exec_error)
        self.c.home=True;a=self.adapter(outputs=['lampada'],simulated=False);run=self.start_real_output(.1);self.wait()
        self.assertIn('timeout',self.s.movej.exec_error)
        self.c.home=True;run=self.start_real_output();self.wait(lambda:bool(a.requests()));request=a.requests()[0]
        with self.assertRaises(APIError):a.acknowledge(request,False)
        self.wait();self.assertIn('failed',self.s.movej.exec_error)
    def test_stop_rejects_late_or_wrong_owner_ack(self):
        a=self.adapter(outputs=['lampada'],simulated=False);other=self.adapter(simulated=False)
        run=self.start_real_output();self.wait(lambda:bool(a.requests()));request=a.requests()[0]
        with self.assertRaises(APIError):other.acknowledge(request,True)
        self.client.stop()
        with self.assertRaises(APIError):a.acknowledge(request,True)
        self.wait();self.assertFalse(self.s.io.values)
    def test_output_adapter_disappears_during_wait(self):
        a=self.adapter(outputs=['lampada'],simulated=False);run=self.start_real_output(5)
        self.wait(lambda:bool(a.requests()));a.close();self.wait()
        self.assertIn('disconnected',self.s.movej.exec_error);self.assertFalse(self.c.home)
    def test_all_branches_include_outputs_and_undefined_output_is_localized(self):
        blocks=[dict(kind='if',name='Se',condition='presente == 1'),*self.output(),dict(kind='else',name='Altro'),dict(kind='note',name='Niente'),dict(kind='end',name='Fine')]
        p=self.client.plan(blocks);self.assertEqual(p['program']['branches'],3)
        self.assertTrue(any(st['kind']=='output' for seg in p['tree'] for st in seg['stages']))
        blocks[1]['output']='unknown'
        with self.assertRaises(APIError) as error:self.client.plan(blocks)
        self.assertEqual(error.exception.problem['block'],1)
    def test_legacy_sensor_wait_also_rejects_a_dead_adapter(self):
        self.robot();a=self.adapter(inputs=['presente'],simulated=False);a.publish('presente',1)
        a.close()
        self.s.action(dict(op='studio_blocks',blocks=[dict(kind='sensor',name='Attendi',sensor='presente',expected=1,timeout=.1),dict(kind='note',name='Non deve arrivare')]))
        self.s.run_program();self.wait()
        self.assertIn('Timeout sensore',self.s.program_error)
        self.assertNotIn('Non deve arrivare',self.c.events)

    def test_adapter_loss_at_a_condition_stops_before_its_branch(self):
        self.robot();a=self.adapter(inputs=['presente'],simulated=False);a.publish('presente',1)
        blocks=[dict(kind='movej',name='Primo',to='joints',angles=[1,0,0,0,0,0]),dict(kind='if',name='Se',condition='presente'),dict(kind='movej',name='Non deve arrivare',to='joints',angles=[2,0,0,0,0,0]),dict(kind='end',name='Fine')]
        p=self.client.plan(blocks);run=self.client.execute(p);decide=self.s.movej.decide
        def disconnect(end):a.close();return decide(end)
        self.s.movej.decide=disconnect;self.api.commands.approve(run['id'],True);self.wait()
        self.assertIn('adattatore non disponibile',self.s.movej.exec_error);self.assertEqual(len(self.multi_lines()),1)

    def test_definitions_save_without_live_values_sessions_or_requests(self):
        p=self.client.plan(self.output());run=self.client.execute(p);self.client.wait(run,timeout=5);self.s.save()
        saved=json.loads((self.s.folder/'project.json').read_text());self.assertEqual(saved['outputs'],{'lampada':'digital'});self.assertNotIn('io',saved)
        reopened=Studio(self.folder,self.c,builtin=False);self.assertEqual(reopened.outputs,self.s.outputs);self.assertEqual(reopened.io.values,{})
