"""Live scoreboard name, affiliation and sprite-label regression tests."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from models.bowler import Bowler
from services.game_engine import GameSession
from ui.embeds import scoreboard_embed, scoreboard_identity, scoreboard_sprite
from services.v25 import session_dict, session_from_dict


def make_bowler(number,name,team=None,affiliation=None,sprite='none'):
    return Bowler(id=number,name=name,owner_id=number,
                  team_name=team,affiliation=affiliation,sprite_key=sprite)


class ScoreboardIdentityTests(unittest.TestCase):
    def test_team_name_replaces_duplicate_bowler_name(self):
        bowler=make_bowler(1,'TheDude','Minds in the Gutter',sprite='the_dude')
        with patch('ui.embeds.has_sequence',return_value=True):
            session=GameSession([bowler],seed=123)
            embed=scoreboard_embed(session)
        self.assertEqual(embed.fields[0].name,'TheDude — Minds in the Gutter')
        self.assertIn('🎭 Sprite: **The Dude**',embed.fields[0].value)

    def test_exhibition_shows_registered_affiliation_without_team_totals(self):
        bowler=make_bowler(2,'Josh Lannon',affiliation='P.U.R.G.E',sprite='jesus')
        session=GameSession([bowler],seed=444)
        # Simulate a finished exhibition to exercise the team totals section.
        with patch('ui.embeds.has_sequence',return_value=True):
            embed=scoreboard_embed(session)
        self.assertEqual(embed.fields[0].name,'Josh Lannon — P.U.R.G.E')
        self.assertIn('🎭 Sprite: **Jesus**',embed.fields[0].value)
        self.assertNotIn('🏆 Team Totals',[f.name for f in embed.fields])
        self.assertIsNone(bowler.team_name)

    def test_legacy_duplicate_and_no_team_are_independent(self):
        bowler=make_bowler(3,'Benny','Benny',sprite='none')
        self.assertEqual(scoreboard_identity(bowler),'Benny — Independent')
        self.assertEqual(scoreboard_sprite(bowler),'None (standard approach)')
        bowler.team_name=None
        self.assertEqual(scoreboard_identity(bowler),'Benny — Independent')

    def test_missing_sprite_art_is_reported(self):
        bowler=make_bowler(4,'Walter',sprite='jesus')
        with patch('ui.embeds.has_sequence',return_value=False):
            self.assertIn('art missing',scoreboard_sprite(bowler))

    def test_affiliation_survives_undo_restore(self):
        bowler=make_bowler(5,'TheDude',affiliation='Hallebrewja Strikers',sprite='the_dude')
        session=GameSession([bowler],seed=2718)
        restored=session_from_dict(session_dict(session))
        self.assertEqual(restored.players[0].bowler.affiliation,'Hallebrewja Strikers')
        self.assertIsNone(restored.players[0].bowler.team_name)
        self.assertEqual(restored.players[0].bowler.sprite_key,'the_dude')


if __name__=='__main__':
    unittest.main()
