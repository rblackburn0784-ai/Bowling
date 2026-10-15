"""Independent regression for real flattened-checkerboard victory PNGs.

Old RGB cheer.png files contain a fake transparency checker. Test both
opaque RGB checker art and already-transparent numbered sprite art.
"""
import unittest
from PIL import Image,ImageDraw
from services.bowler_sprites import _remove_flattened_checker


class CheerArtworkAlphaRegression(unittest.TestCase):
    def test_opaque_checker_recovers_alpha_without_damaging_character(self):
        frame=Image.new('RGB',(140,200),(253,253,253))
        draw=ImageDraw.Draw(frame)
        for y in range(0,200,20):
            for x in range(0,140,20):
                if (x//20+y//20)%2:
                    draw.rectangle((x,y,x+19,y+19),fill=(223,223,223))
        draw.rectangle((42,40,102,175),fill=(95,34,160))
        extracted=_remove_flattened_checker(frame)
        self.assertEqual(extracted.mode,'RGBA')
        self.assertEqual(extracted.getpixel((5,5))[3],0)
        self.assertEqual(extracted.getpixel((25,5))[3],0)
        self.assertEqual(extracted.getpixel((70,90))[3],255)
        self.assertEqual(extracted.getpixel((70,90))[:3],(95,34,160))

    def test_real_transparent_png_keeps_existing_alpha(self):
        source=Image.new('RGBA',(100,100),(255,255,255,0))
        ImageDraw.Draw(source).rectangle((20,20,60,90),fill=(240,220,200,255))
        returned=_remove_flattened_checker(source)
        self.assertEqual(returned.tobytes(),source.tobytes())

    def test_dark_opaque_presentation_background_is_not_stripped(self):
        photo=Image.new('RGB',(80,80),(12,20,30))
        returned=_remove_flattened_checker(photo)
        self.assertEqual(returned.getchannel('A').getextrema(),(255,255))


if __name__=='__main__':
    unittest.main()
