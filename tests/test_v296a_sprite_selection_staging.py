"""v2.9.6a character selection release smoke tests.

Runs against the installed sprite pack without creating game sessions or
modifying player ranks.
"""
import unittest
from io import BytesIO
from PIL import Image
from services.bowler_sprites import installed_sprites,sprite_key,has_sequence,MAX_CHOICES
from services.sprite_preview import render_sprite_preview
from models.bowler import Bowler

class BowlerSelectionTests(unittest.TestCase):
    def test_complete_character_sets(self):
        choices=installed_sprites()
        self.assertLessEqual(len(choices),MAX_CHOICES)
        if not choices:self.skipTest('PNG artwork not yet present in GitHub staging')
        self.assertTrue(has_sequence('the_dude'))
        self.assertTrue(has_sequence('jesus'))
        self.assertTrue(all(has_sequence(x) for x in choices))

    def test_saved_sprite_overrides_name(self):
        bowler=Bowler(None,'Random Name',42)
        bowler.sprite_key='jesus'
        self.assertEqual(sprite_key(bowler),'jesus')
        bowler.sprite_key='the_dude'
        self.assertEqual(sprite_key(bowler),'the_dude')

    def test_preview_is_png(self):
        if not installed_sprites():self.skipTest('PNG artwork not yet present in GitHub staging')
        for key in installed_sprites():
            raw=render_sprite_preview(key)
            self.assertIsInstance(raw,BytesIO)
            with Image.open(raw) as im:
                self.assertEqual(im.size,(640,480))
                self.assertEqual(im.format,'PNG')

    def test_roster_restricts_sprite_to_owner(self):
        from unittest.mock import patch,MagicMock
        from services.roster import update_owned_sprite
        class MockCursor:
            rowcount=0
        class MockConn:
            def execute(self,*args,**kw):
                self.statement=args[0]
                self.params=args[1]
                return MockCursor()
            def __enter__(self):return self
            def __exit__(self,*args):return False
        conn=MockConn()
        with patch('services.roster.connect',return_value=conn), patch('services.roster.installed_sprites',return_value=('the_dude',)):
            success,msg=update_owned_sprite(404,'the_dude')
        self.assertFalse(success)
        self.assertIn('owner_id=?',conn.statement)
        self.assertEqual(conn.params,('the_dude',404,404))

if __name__=='__main__':unittest.main()
