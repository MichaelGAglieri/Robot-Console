# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
import threading,unittest
from unittest.mock import patch
import server
class StopAck(unittest.TestCase):
 def make(self):
  with patch.object(threading.Thread,'start'):return server.Controller()
 def test_requested_stop_ack_preserves_reason(self):
  c=self.make();c.error='STOP operatore: ristabilisci HOME';c.awaiting_halt=True
  c.receive('HALTED');self.assertFalse(c.awaiting_halt);self.assertEqual(c.error,'STOP operatore: ristabilisci HOME')
 def test_unexpected_halt_invalidates_reference(self):
  c=self.make();c.home=True;c.busy=True;c.receive('HALTED')
  self.assertFalse(c.home);self.assertFalse(c.busy)
 def test_watchdog_remains_error(self):
  c=self.make();c.home=True;c.receive('ERROR WATCHDOG')
  self.assertFalse(c.home);self.assertIn('WATCHDOG',c.error)
if __name__=='__main__':unittest.main()
