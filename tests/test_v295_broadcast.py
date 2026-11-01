"""v2.9.5 consolidated Broadcast Studio contracts.

The old temporary install_v295.py overlay is not part of an installed bot.
Exercise the installed runtime instead of importing a removed installer.
"""
import ast
import unittest
from pathlib import Path

from services.broadcast_studio import replay_reason
from services.shot_animation import ANIMATION_SEQUENCE, REPLAY_SEQUENCE, DURATION_SECONDS

ROOT = Path(__file__).resolve().parents[1]


def function_named(tree, name):
    return next(n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)


def called(method, node):
    return [n for n in ast.walk(node) if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute) and n.func.attr == method]


class TestBroadcast295(unittest.TestCase):
    def test_one_gameplay_delivery_and_optional_visual_replay(self):
        tree = ast.parse((ROOT / 'cogs' / 'games.py').read_text(encoding='utf-8'))
        delivery = function_named(tree, '_deliver')
        self.assertEqual(len(called('bowl', delivery)), 1,
                         'One actual GameSession.bowl() call per delivery')
        for name in ('animate_delivery', 'broadcast_replay'):
            calls = [n for n in ast.walk(delivery) if isinstance(n, ast.Call)
                     and isinstance(n.func, ast.Name) and n.func.id == name]
            self.assertEqual(len(calls), 1, name)

    def test_replay_and_gif_render_do_not_advance_game_state(self):
        paths = (ROOT / 'cogs' / 'games.py', ROOT / 'services' / 'shot_animation.py')
        trees = [ast.parse(path.read_text(encoding='utf-8')) for path in paths]
        for tree, name in ((trees[0], 'broadcast_replay'),
                           (trees[1], 'animated_shot'),
                           (trees[1], 'replay_shot')):
            self.assertFalse(called('bowl', function_named(tree, name)), name)
        self.assertEqual(replay_reason({'strike': True, 'down': list(range(1,11))}, None),
                         'STRIKE REPLAY')

    def test_approach_timeline_preserved_and_replay_is_separate(self):
        self.assertEqual(len(ANIMATION_SEQUENCE), 23)
        self.assertEqual(ANIMATION_SEQUENCE[0][0], 'approach')
        self.assertEqual(ANIMATION_SEQUENCE[-1][0], 'impact')
        self.assertGreater(len(REPLAY_SEQUENCE), 0)
        self.assertAlmostEqual(DURATION_SECONDS, 2.795, places=3)


if __name__ == '__main__':
    unittest.main()
