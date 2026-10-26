# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
import json, urllib.request, urllib.error
from unittest.mock import patch
from test_studio import StudioFixture
from local_api import LocalAPI
class APITests(StudioFixture):
 def test_loopback_auth_sensor_input_and_no_motion(self):
  self.s.define_sensor('contact','digital');api=LocalAPI(self.c,self.s)
  try:
   api.start();url=api.state()['url'];token=api.token
   def call(path,data=None,authorized=True):
    raw=json.dumps(data).encode() if data is not None else None
    req=urllib.request.Request(url+path,data=raw,headers={'Authorization':'Bearer '+token} if authorized else {})
    try:
     with urllib.request.urlopen(req,timeout=2) as response:return response.status,json.load(response)
    except urllib.error.HTTPError as error:
     with error:return error.code,json.load(error)
   self.assertEqual(call('/v1/state',authorized=False)[0],403)
   self.assertEqual(call('/v1/state')[0],200)
   with patch.object(self.c,'action',side_effect=AssertionError('API cannot command controller')):
    self.assertEqual(call('/v1/sensors',{'name':'contact','value':1})[0],200)
    self.assertEqual(call('/v1/move',{'axis':0,'delta':1})[0],404)
    self.assertEqual(call('/v1/sensors',{'name':'unknown','value':1})[0],400)
   self.assertEqual(self.s.sensors['contact']['source'],'adattatore API locale');self.c.write.assert_not_called()
  finally:api.stop()
  self.assertFalse(api.state()['running']);self.assertEqual(api.token,'')
