"""v2.9.6 staged physics smoke tests; no Discord dependency."""
import unittest
from services.lane_physics import PATTERNS,LaneState
from services.physics_v296 import lane_read,choose_spare_target

class PhysicsStaging(unittest.TestCase):
    def test_patterns(self):
        self.assertIn('sport',PATTERNS)
        self.assertIn('heavy',PATTERNS)
        self.assertLess(PATTERNS['sport']['ratio'],PATTERNS['house']['ratio'])
    def test_nonmutating_lane_read(self):
        from services.equipment import get_ball
        lane=LaneState(3,'sport')
        before=vars(lane).copy()
        self.assertEqual(lane_read(lane,get_ball('hybrid')),lane_read(lane,get_ball('hybrid')))
        self.assertEqual(vars(lane),before)
    def test_spare_target_empty(self):
        self.assertEqual(choose_spare_target(set()),(1,0.0,False))

if __name__=='__main__':unittest.main()
