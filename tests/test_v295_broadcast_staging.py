"""Broadcast Studio v2.9.5 regression contracts (offline)."""
import unittest
from types import SimpleNamespace
from services.broadcast_studio import replay_reason, shot_identity, mode

class TestBroadcastStudio(unittest.TestCase):
    def test_replay_policy(self):
        s=SimpleNamespace(layout='broadcast',fixture_id=None,tournament_id=None,practice_no_rewards=True)
        self.assertEqual(replay_reason({'strike':True},s),'STRIKE REPLAY')
        self.assertEqual(replay_reason({'split_conversion':True},s),'SPLIT CONVERSION')
        self.assertEqual(replay_reason({'spare':True,'before':[7]},s),'DIFFICULT SPARE')
        self.assertIsNone(replay_reason({'before':list(range(1,11)),'down':[3]},s))
    def test_mode(self):
        self.assertEqual(mode(SimpleNamespace(friendly_challenge=True)),'exhibition')
        self.assertEqual(mode(SimpleNamespace(layout='finals')),'finals')
        self.assertEqual(mode(SimpleNamespace(fixture_id=3)),'tournament')
        self.assertEqual(mode(SimpleNamespace(layout='broadcast')),'standard')
    def test_shot_identity(self):
        s=SimpleNamespace(session_uid='same',ball_count=3)
        a={'bowler_id':1,'frame':5,'ball':2}
        self.assertEqual(shot_identity(s,a),('same',3,1,5,2))

if __name__=='__main__':unittest.main()
