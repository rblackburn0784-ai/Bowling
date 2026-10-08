"""Offline regression checks for v2.8.5 sprite approach."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image

from services import bowler_sprites

class SpriteApproachTests(unittest.TestCase):
    def test_named_mapping_and_fallback(self):
        self.assertEqual(bowler_sprites.sprite_key(SimpleNamespace(name='TheDude',sprite_key=None)),'the_dude')
        self.assertEqual(bowler_sprites.sprite_key(SimpleNamespace(name='Jesus',sprite_key=None)),'jesus')
        self.assertIsNone(bowler_sprites.sprite_key(SimpleNamespace(name='New Bowler',sprite_key=None)))
        self.assertEqual(bowler_sprites.sprite_key(SimpleNamespace(name='New Bowler',sprite_key='jesus')),'jesus')

    def test_five_frames_and_missing_asset_fallback(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(bowler_sprites,'SPRITE_DIR',Path(folder)):
            bowler_sprites._image.cache_clear()
            self.assertFalse(bowler_sprites.has_sequence('the_dude'))
            sprites=Path(folder)/'the_dude'
            sprites.mkdir()
            for n in range(1,6):
                Image.new('RGBA',(50,90),(50,150,210,210)).save(sprites/f'{n}.png')
            bowler_sprites._image.cache_clear()
            self.assertTrue(bowler_sprites.has_sequence('the_dude'))
            self.assertFalse(bowler_sprites.has_sequence('jesus'))
            for n in range(1,6):
                canvas=Image.new('RGB',(680,760),(12,14,24))
                result=bowler_sprites.draw_approach(canvas,SimpleNamespace(name='TheDude',sprite_key=None),n)
                self.assertTrue(result)
                self.assertNotEqual(canvas.getpixel((340,535)),(12,14,24))
            (sprites/'3.png').unlink()
            bowler_sprites._image.cache_clear()
            self.assertFalse(bowler_sprites.has_sequence('the_dude'))
            bowler_sprites._image.cache_clear()

    def test_frame_count_and_timing(self):
        self.assertEqual(bowler_sprites.FRAMES,5)
        self.assertTrue(.12 <= bowler_sprites.APPROACH_FRAME_SECONDS <= .22)

if __name__=='__main__':
    unittest.main()
