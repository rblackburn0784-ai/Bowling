"""v2.8.5p regression checks for the three user-supplied PNG proportions.

The real camera photos are 1254x1254, the lane is 941x1672. CI uses
mocked plates/PNGs so art files need not be committed to GitHub.
"""
import unittest
from unittest.mock import patch
from PIL import Image, ImageChops
from services import scene_renderer as scene
from services import hybrid_broadcast as layout


class NewArtworkCalibrationTests(unittest.TestCase):
    def setUp(self):
        self.plates={
            'overhead':Image.new('RGBA',(1254,1254),(63,42,23,255)),
            'pit':Image.new('RGBA',(1254,1254),(25,25,32,255))}
        self.standing=Image.new('RGBA',(26,68),(249,228,210,255))
        self.top=Image.new('RGBA',(44,68),(247,216,205,255))
        self.fallen=Image.new('RGBA',(62,26),(210,36,35,255))
        self.event={'before':list(range(1,11)),'down':[1,3,7],
                    'after':[2,4,5,6,8,9,10]}
    def sprite(self,view,name):
        if name.startswith('fall_'):return self.fallen
        return self.top if view=='overhead' else self.standing
    def test_true_new_asset_dimensions_and_filenames(self):
        self.assertEqual(scene.BG.name,'gutter_saints_empty.png')
        self.assertEqual(scene.CAMERAS.name,'cameras')
        self.assertEqual(layout.SOURCE_SIZE,(941,1672))
        for name in ('overhead','pit'):
            self.assertEqual(self.plates[name].size,(1254,1254))
        self.assertEqual(set(scene.CAMERA_OVERHEAD),set(range(1,11)))
        self.assertEqual(set(scene.CAMERA_PIT),set(range(1,11)))
    def test_each_camera_shows_all_ten_at_calibrated_locations(self):
        with patch.object(scene,'_camera_background',side_effect=lambda k:self.plates[k]),\
             patch.object(scene,'_pin',side_effect=self.sprite):
            frames=scene.right_cameras(self.event)
        for view,anchors in [('overhead',scene.CAMERA_OVERHEAD),
                             ('pit',scene.CAMERA_PIT)]:
            camera=frames[view]
            self.assertEqual(camera.size,(1254,1254))
            for pin,(u,v) in anchors.items():
                x,y=round(u*1254),round(v*1254)
                sample=(x,y) if view=='overhead' else (x,y-42)
                self.assertNotEqual(camera.getpixel(sample),
                                    self.plates[view].getpixel(sample),
                                    f'{view} pin {pin} invisible at its anchor')
    def test_spare_impact_falls_only_selected_pins_in_both_cameras(self):
        before=dict(self.event)
        with patch.object(scene,'_camera_background',side_effect=lambda k:self.plates[k]),\
             patch.object(scene,'_pin',side_effect=self.sprite):
            impact=scene.right_cameras(self.event,'impact',impact_frame=3)
            leave=scene.right_cameras(self.event,'leave')
        for camera in ('overhead','pit'):
            self.assertIsNotNone(ImageChops.difference(impact[camera],leave[camera]).getbbox())
        self.assertEqual(before,self.event)
    def test_left_hero_fills_without_pixel_gaps_at_any_gif_size(self):
        full=Image.new('RGB',(941,1672),(73,84,95))
        for size in ((850,750),(765,675),(680,600)):
            image=layout.compose_hybrid_broadcast(full,output_size=size,cameras={
                'overhead':self.plates['overhead'],'pit':self.plates['pit']})
            self.assertEqual(image.size,size)
            right=round(layout.HERO_BOX[2]*size[0]/layout.BASE_SIZE[0])
            for x,y in ((0,0),(0,size[1]-1),(right-2,0),(right-2,size[1]-1)):
                self.assertEqual(image.getpixel((x,y)),(73,84,95))
    def test_camera_panels_keep_input_aspect(self):
        plate=self.plates['overhead']
        result=layout._camera_cover(plate,(0,0,410,330))
        self.assertEqual(result.size,(410,330))


if __name__=='__main__':
    unittest.main()
