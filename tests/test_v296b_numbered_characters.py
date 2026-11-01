"""v2.9.6b: numbered character folders are selectable, safely capped at 20."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image
from services import bowler_sprites
from services.sprite_preview import render_sprite_preview

class NumberedSpriteTests(unittest.TestCase):
    def setUp(self):
        bowler_sprites._discover_installed.cache_clear()
        bowler_sprites._image.cache_clear()

    def tearDown(self):
        bowler_sprites._discover_installed.cache_clear()
        bowler_sprites._image.cache_clear()

    @staticmethod
    def make_pack(root, key, count=5):
        folder=root/key;folder.mkdir()
        for n in range(1,count+1):
            Image.new('RGBA',(40,75),(60+n,160,215,255)).save(folder/f'{n}.png')

    def test_all_20_numbered_packs_override_original_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for n in range(1,21):self.make_pack(root,f'{n:02}_test_bowler')
            for key in ('the_dude','jesus'):self.make_pack(root,key)
            with patch.object(bowler_sprites,'SPRITE_DIR',root):
                found=bowler_sprites.installed_sprites()
                self.assertEqual(found,tuple(f'{n:02}_test_bowler' for n in range(1,21)))
                self.assertEqual(bowler_sprites.sprite_label(found[0]),'01 · Test Bowler')
                self.assertTrue(bowler_sprites.has_sequence(found[-1]))
                self.assertEqual(bowler_sprites.sprite_key(SimpleNamespace(name='Someone',sprite_key='the_dude')),'the_dude')
                with Image.open(render_sprite_preview(found[-1])) as im:self.assertEqual(im.size,(640,480))

    def test_incomplete_character_missing_fifth_frame_is_not_offered(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.make_pack(root,'01_complete')
            self.make_pack(root,'02_missing_last_frame',4)
            self.make_pack(root,'the_dude')
            with patch.object(bowler_sprites,'SPRITE_DIR',root):
                self.assertEqual(bowler_sprites.installed_sprites(),('01_complete','the_dude'))

if __name__=='__main__':unittest.main()
