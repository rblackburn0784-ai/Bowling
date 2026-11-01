"""Run against the complete Bowling checkout after copying this overlay."""
import unittest
from io import BytesIO
from types import SimpleNamespace
from PIL import Image
from services.showtime_graphics import intro_card,final_card,WIDTH,HEIGHT

class Dummy:
    def __init__(self):
        def p(n,i):
            b=SimpleNamespace(id=i,name=n,rank=5,handedness='R',team=None)
            return SimpleNamespace(bowler=b,frames=[[10]]*9+[[10,10,10]],split_frames=set())
        self.players=[p('THE DUDE',1),p('JESUS',2)]
        self.lane='house'; self.tournament_id=None; self.fixture_id=None
        self.friendly_challenge=True; self.competition_id=None;self.layout='broadcast'
        self.lane_pair=SimpleNamespace(left=SimpleNamespace(number=3),right=SimpleNamespace(number=4))
    def card(self):return {p.bowler.name:['X']*9+['XXX'] for p in self.players}
    def scores(self):return {p.bowler.name:300 for p in self.players}

class Smoke(unittest.TestCase):
    def test_opening_and_end_dimensions_and_no_state_changes(self):
        s=Dummy(); before=str(s.card())
        for blob in (intro_card(s),final_card(s,'THE DUDE')):
            img=Image.open(blob)
            self.assertEqual(img.size,(WIDTH,HEIGHT))
            self.assertEqual(img.format,'PNG')
        self.assertEqual(s.card().__str__(),before)

if __name__=='__main__':unittest.main()
