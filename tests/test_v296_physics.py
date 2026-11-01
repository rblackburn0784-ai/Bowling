"""v2.9.6 physics, fairness and recovery release gates."""
import random
import unittest
from copy import deepcopy
from models.bowler import Bowler
from services.game_engine import GameSession
from services.v25 import session_dict,session_from_dict
from services.physics_v296 import roll_pins,choose_spare_target,lane_read
from services.lane_physics import LaneState,PATTERNS
from services.pin_engine import ALL
from services.equipment import get_ball
from services.simulation_lab import SimProfile,run_profile

def bowler(i=1,stat=25,hand='R'):
    return Bowler(i,'Bowler'+str(i),i,hand,12,stat,stat,stat,stat,stat,stat)

class Physics296(unittest.TestCase):
    def test_new_sessions_use_296_and_older_recovery_never_upgrades_physics(self):
        s=GameSession([bowler()],seed=3001)
        self.assertEqual(s.physics_version,'2.9.6')
        s.physics_version='2.9.3'
        for _ in range(7):s.bowl()
        t=session_from_dict(session_dict(s))
        self.assertEqual(t.physics_version,'2.9.3')
        while not s.complete:
            self.assertEqual(s.bowl(),t.bowl())
        self.assertEqual(s.scores(),t.scores())
        self.assertEqual(s.rng.getstate(),t.rng.getstate())

    def test_recover_296_after_second_delivery_and_tenth_bonus(self):
        s=GameSession([bowler(),bowler(2,25,'L')],seed=3108,lane='sport')
        for _ in range(36):
            if s.complete:break
            s.bowl()
        t=session_from_dict(session_dict(s))
        while not s.complete:
            a,b=s.bowl(),t.bowl()
            self.assertEqual(a,b)
            self.assertEqual(set(a['before'])-set(a['down']),set(a['after']))
            self.assertEqual(set(a['physics']['contact_order']),set(a['down']))
        self.assertEqual(s.scores(),t.scores())
        self.assertTrue(all(0<=n<=300 for n in s.scores().values()))

    def test_spares_keep_standing_pins_and_wide_splits_are_not_free(self):
        b=bowler(stat=40)
        self.assertEqual(choose_spare_target({2,3})[1:],(0.,True))
        self.assertFalse(choose_spare_target({7,10})[2])
        clears=0
        for n in range(350):
            down,q,event=roll_pins(random.Random(n),b,{7,10},ball_key='plastic',target_mode='spare')
            self.assertTrue(down<={7,10})
            self.assertEqual(set(event['contact_order']),down)
            clears+=down=={7,10}
        self.assertLess(clears,15)

    def test_second_ball_after_zero_and_10th_frame_are_legal(self):
        for n in range(16):
            s=GameSession([bowler()],seed=n+2200,lane='heavy')
            events=[]
            while not s.complete:
                events.append(s.bowl())
            for ev in events:
                self.assertEqual(set(ev['before'])-set(ev['down']),set(ev['after']))
                self.assertEqual(set(ev['down']),set(ev['physics']['contact_order']))
                self.assertEqual(ev['physics']['physics_version'],'2.9.6')
            self.assertEqual(len(s.players[0].frames),10)
            self.assertTrue(0<=next(iter(s.scores().values()))<=300)

    def test_symmetric_hand_geometry_and_aim(self):
        r=bowler(hand='R');l=bowler(hand='L')
        metrics=[]
        for b in (r,l):
            down,q,details=roll_pins(random.Random(95),b,ALL,lane='house',line_boards=0)
            metrics.append(details)
        self.assertAlmostEqual(metrics[0]['impact_x'],-metrics[1]['impact_x'],places=4)
        self.assertAlmostEqual(metrics[0]['deflection'],-metrics[1]['deflection'],places=4)

    def test_lane_patterns_and_transition_read(self):
        for key in ('house','sport','heavy','dry'):
            self.assertIn(key,PATTERNS)
            state=LaneState(3,key)
            a=lane_read(state,get_ball('hybrid'))
            for _ in range(60):state.apply_shot(.88,.6)
            b=lane_read(state,get_ball('hybrid'))
            self.assertGreaterEqual(b['transition'],a['transition'])
            self.assertGreater(b['transition_penalty'],a['transition_penalty'])
        self.assertLess(PATTERNS['sport']['ratio'],PATTERNS['house']['ratio'])

    def test_shot_intents_have_control_and_carry_tradeoff(self):
        b=bowler()
        def samples(intent):
            return [roll_pins(random.Random(n),b,ALL,shot_intent=intent)[2] for n in range(180)]
        safe=samples('safe');agg=samples('aggressive')
        mean_abs=lambda arr:sum(abs(x['miss']) for x in arr)/len(arr)
        self.assertLess(mean_abs(safe),mean_abs(agg))
        self.assertGreater(sum(x['strike_chance'] for x in agg)/len(agg),
                           sum(x['strike_chance'] for x in safe)/len(safe))

    def test_simulation_is_repeatable_and_side_effect_free(self):
        p=SimProfile('Balanced')
        a=run_profile(p,games=18,lane='sport',seed=725)
        b=run_profile(p,games=18,lane='sport',seed=725)
        self.assertEqual(a,b)
        self.assertTrue(0<=a['avg']<=300)

if __name__=='__main__':unittest.main()
