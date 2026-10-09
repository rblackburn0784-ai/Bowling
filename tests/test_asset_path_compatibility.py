"""Compatibility tests for v2.8.5d's two sprite-folder conventions."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image

from services import scene_renderer as scene


class AssetLayoutCompatibilityTests(unittest.TestCase):
    def test_lane_found_at_assets_root_when_canonical_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            existing=root/'Lane.png'
            Image.new('RGB',(94,167),(24,36,48)).save(existing)
            with patch.object(scene,'BG',root/'lane'/'gutter_saints_empty.png'), \
                 patch.object(scene,'LANE_ALTERNATES',(existing,)):
                scene._background.cache_clear()
                self.assertEqual(scene._lane_file(),existing)
                self.assertTrue(scene.available())
                self.assertEqual(scene._background().size,scene.SIZE)
                scene._background.cache_clear()

    def test_canonical_background_takes_priority(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            canonical=root/'gutter_saints_empty.png'
            alternate=root/'Lane.png'
            Image.new('RGB',(20,20),(1,2,3)).save(canonical)
            Image.new('RGB',(20,20),(90,80,70)).save(alternate)
            with patch.object(scene,'BG',canonical),patch.object(scene,'LANE_ALTERNATES',(alternate,)):
                scene._background.cache_clear()
                self.assertEqual(scene._lane_file(),canonical)
                self.assertEqual(scene._background().getpixel((0,0)),(1,2,3,255))
                scene._background.cache_clear()

    def test_legacy_pin_subfolders_and_number_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            overhead=root/'overhead';overhead.mkdir()
            vertical=root/'vertical';vertical.mkdir()
            # Legacy pin_2.png actually shows pin 4, legacy pin_4.png shows 2.
            Image.new('RGBA',(44,68),(20,40,60,255)).save(overhead/'pin_4.png')
            Image.new('RGBA',(25,66),(60,40,20,255)).save(vertical/'standing.png')
            with patch.object(scene,'PINS',root/'pins'),patch.object(scene,'PINS_ALTERNATE',root):
                scene._pin.cache_clear()
                overhead_two=scene._pin('overhead','pin_2')
                upright=scene._pin('vertical','standing')
                self.assertEqual(overhead_two.size,(44,68))
                self.assertEqual(upright.size,(25,66))
                scene._pin.cache_clear()

    def test_canonical_pin_assets_do_not_get_legacy_number_remapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            direct=root/'pins'/'overhead';direct.mkdir(parents=True)
            legacy=root/'overhead';legacy.mkdir()
            Image.new('RGBA',(33,50),(255,20,20,255)).save(direct/'pin_2.png')
            Image.new('RGBA',(40,55),(30,220,60,255)).save(legacy/'pin_4.png')
            with patch.object(scene,'PINS',root/'pins'),patch.object(scene,'PINS_ALTERNATE',root):
                scene._pin.cache_clear()
                pin=scene._pin('overhead','pin_2')
                self.assertEqual(pin.size,(33,50))
                self.assertEqual(pin.getpixel((0,0)),(255,20,20,255))
                scene._pin.cache_clear()


if __name__=='__main__':
    unittest.main()
