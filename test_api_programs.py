# SPDX-License-Identifier: GPL-3.0-only
import copy,json,threading,time,urllib.request,urllib.error
from unittest.mock import patch
from local_api import LocalAPI
from robot_console_client import RobotConsole,APIError
from examples.python_pick_and_place import program
from test_program import ProgramBase

class ProgramAPITests(ProgramBase):
    def setUp(self):
        super().setUp();self.api=LocalAPI(self.c,self.s);self.api.start();self.client=RobotConsole(self.api.state()['url'],self.api.token)
    def tearDown(self):
        self.api.stop();self.wait(timeout=3);super().tearDown()
    def enable(self,demo=False):self.api.commands.configure(True,demo)
    def simple(self):return [dict(kind='movej',name='A',to='joints',angles=[1,0,0,0,0,0]),dict(kind='movej',name='H',to='home')]
    def test_default_permissions_telemetry_auth_and_no_privileged_routes(self):
        self.assertFalse(self.client.health()['motion_enabled'])
        self.assertEqual(self.client.state()['controller']['mode'],'demo')
        with self.assertRaisesRegex(APIError,'disattivata'):self.client.plan(self.simple())
        bad=RobotConsole(self.api.state()['url'],'wrong')
        with self.assertRaises(APIError) as error:bad.state()
        self.assertEqual(error.exception.status,403)
        for path in ('/v1/connect','/v1/firmware','/v1/home','/v1/limits','/v1/approve','/v1/permissions','/v1/move'):
            with self.assertRaises(APIError) as error:self.client.request(path,{})
            self.assertEqual(error.exception.status,404)
        self.c.write.assert_not_called()
        self.enable(True);self.api.stop();self.api.start();self.assertFalse(self.api.state()['motion_enabled']);self.assertFalse(self.api.state()['demo_execution'])
    def test_browser_origin_host_and_invalid_json_are_rejected(self):
        for headers,raw in [({'Origin':'https://example.org'},b'{}'),({'Host':'evil.example'},b'{}'),({},b'[]'),({},b'{"x":NaN}')]:
            req=urllib.request.Request(self.api.state()['url']+'/v1/program/plan',data=raw,headers={'Authorization':'Bearer '+self.api.token,**headers})
            with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(req,timeout=2)
            self.assertIn(e.exception.code,(400,403))
        for url in ('https://127.0.0.1:1','http://example.org:80','http://127.0.0.1:1/x','http://user@localhost:1'):
            with self.assertRaises(ValueError):RobotConsole(url,'a')
    def test_gui_and_python_demo_have_identical_plan_and_firmware_groups(self):
        self.robot();self.enable();blocks=program(self.t)
        self.s.action(dict(op='studio_blocks',blocks=blocks));self.s.action(dict(op='studio_program_plan'))
        gui=copy.deepcopy(self.s.movej.plan)
        api=self.client.plan(blocks)
        self.assertEqual(gui['stages'],api['stages']);self.assertEqual(gui['tree'],api['tree'])
        self.assertEqual(gui['duration'],api['duration']);self.assertEqual(self.lines,[])
        self.c.connected=False;self.s.action(dict(op='studio_verified',confirmed=True));self.c.connected=True
        api=self.client.plan(blocks);run=self.client.execute(api)
        self.assertEqual(run['status'],'awaiting_operator');self.assertEqual(self.lines,[])
        self.api.commands.approve(run['id'],True)
        result=self.client.wait(run,timeout=30)
        self.assertEqual(result['status'],'completed')
        expected=['~multi '+' '.join('%.2f %.2f'%(d,v) for d,v in zip(st['deltas'],st['requested']))+'\n' for st in api['stages'] if st['kind']=='movej' and st['axes']]
        self.assertEqual(self.multi_lines(),expected);self.assertEqual(self.c.pos,[0.]*6)
    def test_demo_requires_explicit_permission_and_plan_is_one_use(self):
        self.enable();p=self.client.plan(self.simple())
        with self.assertRaisesRegex(APIError,'Anteprima'):self.client.execute(p)
        self.enable(True);p=self.client.plan(self.simple());run=self.client.execute(p)
        self.assertEqual(self.client.wait(run,timeout=5)['status'],'completed')
        with self.assertRaises(APIError):self.client.execute(p)
        self.assertEqual(self.c.pos,[0.]*6)
    def test_real_approval_is_bound_to_context_and_cannot_be_replayed(self):
        self.robot();self.enable();p=self.client.plan(self.simple());run=self.client.execute(p)
        self.assertFalse(self.c.busy);self.assertEqual(self.lines,[])
        self.c.axis_speeds[0]=10
        with self.assertRaisesRegex(ValueError,'scaduto'):self.api.commands.approve(run['id'],True)
        self.assertIsNone(self.api.commands.pending);self.assertEqual(self.lines,[])
        p=self.client.plan(self.simple());run=self.client.execute(p);self.api.commands.approve(run['id'],False)
        self.assertEqual(self.client.run(run)['status'],'rejected')
        with self.assertRaises(ValueError):self.api.commands.approve(run['id'],True)
    def test_script_loss_and_permission_revocation_stop_without_resume(self):
        self.enable(True);p=self.client.plan([dict(kind='wait',name='Aspetta',seconds=10)])
        run=self.client.execute(p);self.api.commands.runs[run['id']]['heartbeat']-=4;self.api.commands.poll();self.wait()
        self.assertEqual(self.client.run(run)['status'],'stopped');self.assertFalse(self.c.home)
        self.c.action(dict(op='home_set'));p=self.client.plan([dict(kind='wait',name='Aspetta',seconds=10)]);run=self.client.execute(p)
        self.api.commands.configure(False,False);self.wait()
        self.assertEqual(self.client.run(run)['status'],'stopped')
        with self.assertRaises(APIError):self.client.execute(p)
    def test_stop_from_app_and_script_and_step_by_step(self):
        self.enable(True);p=self.client.plan(self.simple());run=self.client.execute(p,step=True)
        self.wait(lambda:self.s.movej.step_waiting);self.assertEqual(self.c.pos[0],1)
        self.client.step(run);self.assertEqual(self.client.wait(run,timeout=5)['status'],'completed')
        p=self.client.plan([dict(kind='wait',name='Aspetta',seconds=10)]);run=self.client.execute(p)
        self.s.action(dict(op='studio_cancel'));self.wait();self.assertEqual(self.client.run(run)['status'],'stopped')
        self.c.action(dict(op='home_set'));p=self.client.plan([dict(kind='wait',name='Aspetta',seconds=10)]);run=self.client.execute(p)
        self.client.stop();self.wait();self.assertEqual(self.client.run(run)['status'],'stopped')
    def test_pending_expiry_and_shutdown_never_authorize_motion(self):
        self.robot();self.enable();p=self.client.plan(self.simple());run=self.client.execute(p)
        self.api.commands.runs[run['id']]['expires']-=61;self.api.commands.poll()
        self.assertEqual(self.client.run(run)['status'],'expired')
        with self.assertRaises(ValueError):self.api.commands.approve(run['id'],True)
        self.assertEqual(self.lines,[])
    def test_plan_error_keeps_localized_problem_and_no_execution(self):
        self.enable(True)
        with self.assertRaises(APIError) as error:self.client.plan([dict(kind='movej',name='Fuori',to='joints',angles=[360]*6)])
        self.assertIsNotNone(error.exception.problem);self.assertEqual(error.exception.problem['block'],0);self.assertEqual(self.lines,[])
    def test_completion_receipt_survives_a_new_plan_from_the_gui(self):
        self.api.commands.stop_event.set();self.api.commands.thread.join(timeout=2)
        self.enable(True);p=self.client.plan(self.simple());run=self.client.execute(p);self.wait()
        self.s.action(dict(op='studio_movej_plan',source='joints',targets=[0.]*6))
        self.assertEqual(self.client.run(run)['status'],'completed')
        self.assertIsNone(self.api.commands.active);self.assertNotIn(run['id'],self.api.commands.execution_plans)

    def test_concurrent_execution_requests_start_only_one_job(self):
        self.enable(True);p=self.client.plan([dict(kind='wait',name='Aspetta',seconds=5)])
        results=[]
        def call():
            try:results.append(self.client.execute(p))
            except APIError:results.append(None)
        workers=[threading.Thread(target=call) for _ in range(2)]
        for t in workers:t.start()
        for t in workers:t.join()
        self.assertEqual(sum(x is not None for x in results),1);self.client.stop();self.wait()

    def test_client_timeout_requests_stop(self):
        self.enable(True);p=self.client.plan([dict(kind='wait',name='Aspetta',seconds=10)]);run=self.client.execute(p)
        with self.assertRaises(TimeoutError):self.client.wait(run,timeout=.05,poll_interval=.02)
        self.wait();self.assertEqual(self.client.run(run)['status'],'stopped')

    def test_functions_share_gui_api_plan_execution_and_stale_context_rules(self):
        from test_program_functions import definition,call,end,note,block,move
        self.robot();self.enable()
        blocks=[definition('cycle',['repeat']),block('loop',times='repeat'),move(1),move(0),end(),end(),call('cycle',{'repeat':'2'})]
        self.s.action(dict(op='studio_blocks',blocks=blocks));gui=self.program_plan()
        api=self.client.plan(blocks)
        self.assertEqual(gui['tree'],api['tree']);self.assertEqual(gui['stages'],api['stages'])
        self.assertTrue(all(stage['call_path'][0]['function']=='cycle' for stage in api['stages']))
        self.c.connected=False;self.s.action(dict(op='studio_verified',confirmed=True));self.c.connected=True
        api=self.client.plan(blocks);run=self.client.execute(api)
        changed=copy.deepcopy(blocks);changed[-1]['arguments']['repeat']='1'
        self.s.action(dict(op='studio_blocks',blocks=changed))
        with self.assertRaisesRegex(ValueError,'scaduto'):self.api.commands.approve(run['id'],True)
        self.assertEqual(self.lines,[])
        api=self.client.plan(blocks);run=self.client.execute(api);self.api.commands.approve(run['id'],True)
        result=self.client.wait(run,timeout=10);self.assertEqual(result['status'],'completed')
        expected=['~multi '+' '.join('%.2f %.2f'%(d,v) for d,v in zip(st['deltas'],st['requested']))+'\n'
                  for st in api['stages'] if st['kind']=='movej' and st['axes']]
        self.assertEqual(self.multi_lines(),expected);self.assertEqual(len(expected),4)
