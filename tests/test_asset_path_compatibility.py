"""Validate the preferred Gutter Saints cinematic asset structure."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image

from services import scene_renderer as scene

class CanonicalAssetLayoutTests(unittest.TestCase):
    def test_canonical_background(self):
        with tempfile.TemporaryDirectory() as d:
            lane=Path(d)/'assets'/'lane'/'gutter_saints_empty.png'
            lane.parent.mkdir(parents=True)
            Image.new('RGB',(40,70),(12,34,56)).save(lane)
            with patch.object(scene,'BG',lane):
                scene._background.cache_clear()
                self.assertEqual(scene._lane_file(),lane)
                self.assertTrue(scene.available())
                self.assertEqual(scene._background().size,scene.SIZE)
                scene._background.cache_clear()

    def test_missing_background_does_not_load_unrelated_image(self):
        with tempfile.TemporaryDirectory() as d:
            asset=Path(d)/'assets'
            asset.mkdir()
            Image.new('RGB',(20,20),(99,99,99)).save(asset/'Lane.png')
            with patch.object(scene,'BG',asset/'lane'/'gutter_saints_empty.png'):
                scene._background.cache_clear()
                self.assertFalse(scene.available())
                scene._background.cache_clear()

    def test_canonical_pin_folders(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'assets'/'pins'
            (root/'overhead').mkdir(parents=True)
            (root/'vertical').mkdir()
            Image.new('RGBA',(44,68),(250,33,33,255)).save(root/'overhead'/'pin_2.png')
            Image.new('RGBA',(26,68),(33,220,40,255)).save(root/'vertical'/'standing.png')
            with patch.object(scene,'PINS',root):
                scene._pin.cache_clear()
                overhead=scene._pin('overhead','pin_2')
                upright=scene._pin('vertical','standing')
                self.assertEqual(overhead.size,(44,68))
                self.assertEqual(overhead.getpixel((0,0)),(250,33,33,255))
                self.assertEqual(upright.size,(26,68))
                self.assertIsNone(scene._pin('overhead','pin_11'))
                scene._pin.cache_clear()

if __name__=='__main__':
    unittest.main()
