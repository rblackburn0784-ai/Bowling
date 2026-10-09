import unittest
from types import SimpleNamespace
from services.dude_commentary import STAGES, EVENTS, stage_line, event_line

class DudeCommentaryTests(unittest.TestCase):
 def setUp(self):self.session=SimpleNamespace()
 def test_twenty_five_variants_per_category(self):
  for category,pairs in {**STAGES,**EVENTS}.items():
   self.assertGreaterEqual(len(pairs[0])*len(pairs[1]),25,category)
 def test_stage_no_repeat_within_cycle(self):
  # Different deliveries receive different calls until 25 combinations cycle.
  # Repainting the same delivery (for GIF or Discord message refresh) must
  # keep its commentary unchanged.
  for stage in STAGES:
   lines=[]
   for _ in range(25):
    delivery={'bowler':'TheDude'}
    first=stage_line(self.session,stage,delivery)
    self.assertEqual(stage_line(self.session,stage,delivery),first)
    lines.append(first)
   self.assertEqual(len(set(lines)),25,stage)
 def test_result_no_repeat_within_cycle(self):
  event={'bowler':'TheDude','pins':8,'leave_name':'7-10'}
  for kind in EVENTS:
   lines=[event_line(self.session,kind,event) for _ in range(25)]
   self.assertEqual(len(set(lines)),25,kind)
 def test_no_result_spoilers_during_animation(self):
  for stage in STAGES:
   text=stage_line(self.session,stage,{'bowler':'TheDude'})
   for word in ('STRIKE','SPARE','300'):
    self.assertNotIn(word,text.upper())

if __name__=='__main__':unittest.main()
