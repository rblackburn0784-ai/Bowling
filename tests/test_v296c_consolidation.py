"""v2.9.6c: release integration contracts, no persistent game writes."""
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import AsyncMock, patch
from PIL import Image
from services.showtime_graphics import intro_card,final_card,WIDTH,HEIGHT
from services.lane_physics import PATTERNS
from services.bowler_sprites import SUPPORTED,has_sequence,installed_sprites
from services.game_engine import GameSession
from models.bowler import Bowler
from services.v25 import session_dict,session_from_dict

class Consolidation(unittest.TestCase):
    def test_neon_approved_templates(self):
        from services import showtime_graphics as neon
        self.assertEqual((WIDTH,HEIGHT),(1672,941))
        for file in ('start.png','end.png'):
            with Image.open(neon.TEMPLATES/file) as im:self.assertEqual(im.size,(1672,941))
    def test_two_team_intro_and_finish_do_not_discard_team_totals(self):
        players=[]
        for i,team in enumerate(('Saints','Saints','Sinners','Sinners')):
            b=Bowler(i+1,f'Bowler{i+1}',i+1,team_name=team)
            players.append(SimpleNamespace(bowler=b,frames=[[10]]*9+[[10,10,10]],split_frames=set()))
        session=SimpleNamespace(players=players,layout='broadcast',friendly_challenge=True,
            lane='house',lane_pair=SimpleNamespace(left=SimpleNamespace(number=3),right=SimpleNamespace(number=4)))
        session.team_totals=lambda:{'Saints':600,'Sinners':600}
        session.scores=lambda:{p.bowler.name:300 for p in players}
        from services import showtime_graphics as cards
        self.assertEqual([cards._name(p) for p in cards._players(session)],['Saints','Sinners'])
        self.assertEqual([cards._score(session,p) for p in cards._players(session)],[600,600])
        with Image.open(intro_card(session)) as im:self.assertEqual(im.size,(WIDTH,HEIGHT))
        with Image.open(final_card(session,'DRAW')) as im:self.assertEqual(im.size,(WIDTH,HEIGHT))
    def test_new_oil_patterns(self):
        self.assertIn('sport',PATTERNS)
        self.assertIn('heavy',PATTERNS)
    def test_legacy_sprite_names_remain_playable(self):
        self.assertTrue(all(has_sequence(key) for key in SUPPORTED))
    def test_saved_physics_dispatch_is_never_upgraded(self):
        b=Bowler(1,'Test',1)
        s=GameSession([b],seed=9001)
        self.assertEqual(s.physics_version,'2.9.6')
        s.physics_version='2.9.3'
        for _ in range(4):s.bowl()
        saved=session_from_dict(session_dict(s))
        self.assertEqual(saved.physics_version,'2.9.3')
        self.assertEqual(saved.rng.getstate(),s.rng.getstate())
        for _ in range(3):self.assertEqual(s.bowl(),saved.bowl())

class BroadcastFinish(unittest.IsolatedAsyncioTestCase):
    async def test_final_card_is_idempotent_without_scoring_writes(self):
        import cogs.games as games
        b=Bowler(1,'The Dude',1)
        session=GameSession([b],seed=104)
        channel=SimpleNamespace(send=AsyncMock())
        first=await games.publish_match_final(channel,session,'The Dude')
        second=await games.publish_match_final(channel,session,'The Dude')
        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(channel.send.await_count,1)
        self.assertEqual(session.ball_count,0)
    async def test_failure_can_be_retried(self):
        import cogs.games as games
        session=GameSession([Bowler(1,'Example',1)],seed=55)
        channel=SimpleNamespace(send=AsyncMock(side_effect=[RuntimeError('upload failed'),None]))
        with patch.object(games.logging,'exception'):
            self.assertFalse(await games.publish_match_final(channel,session,'Example'))
        self.assertTrue(await games.publish_match_final(channel,session,'Example'))
        self.assertEqual(channel.send.await_count,2)

if __name__=='__main__':unittest.main()
