"""Finish-path regressions for completed exhibitions and post-game persistence.

A real temporary SQLite database is used rather than mocking the honours
path: catches closure-scoping errors and nested SQLite write-lock failures.
"""
import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch

from models.bowler import Bowler
from services.game_engine import GameSession
from storage import database
from cogs.games import Games
from services.state import SESSIONS


class GameCompletionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db_patch=patch.object(database,'DB_PATH',Path(self.tmp.name)/'finalise.db')
        self.db_patch.start()
        database.init_db()
        with database.connect() as c:
            for number,name in ((1,'Benny'),(2,'Josh')):
                c.execute('INSERT INTO bowlers(id,name,owner_id,handedness,rank,accuracy,style,flair,consistency,spin,nerves) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                          (number,name,number,'R',1,20,15,10,20,15,10))
        a=Bowler(id=1,name='Benny',owner_id=1,sprite_key='none')
        b=Bowler(id=2,name='Josh',owner_id=2,sprite_key='none')
        self.session=GameSession([a,b],seed=99121)
        for game in self.session.players:
            game.frames=[[4,5] for _ in range(10)]
            game.frame=11
            game.ball=1
            game.standing=set()
        self.channel=SimpleNamespace(id=1551,send=AsyncMock())
        SESSIONS[1551]=self.session

    def tearDown(self):
        SESSIONS.pop(1551,None)
        self.db_patch.stop()
        self.tmp.cleanup()

    async def test_normal_game_finishes_honours_career_and_history(self):
        # This is the exact non-friendly route which used to raise
        # NameError: cannot access free variable 'player_summary'.
        cog=Games(bot=object())
        with patch('cogs.games.match_story_summary',return_value=[]), \
             patch('cogs.games.send_media',new_callable=AsyncMock):
            await cog.finish(self.channel,self.session,self.channel.id)
        messages=[call.args[0] for call in self.channel.send.await_args_list
                  if call.args and isinstance(call.args[0],str)]
        self.assertTrue(any('GAME COMPLETE!' in m for m in messages))
        self.assertTrue(any('POST-GAME HONOURS' in m for m in messages))
        self.assertTrue(self.session.persisted)
        with database.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM games').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM game_results').fetchone()[0],2)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM game_history').fetchone()[0],2)
            stats=db.execute('SELECT bowler_id,games,total_pins FROM bowler_stats ORDER BY bowler_id').fetchall()
            self.assertEqual([(x['bowler_id'],x['games'],x['total_pins']) for x in stats],
                             [(1,1,90),(2,1,90)])
            progress=db.execute('SELECT bowler_id,xp FROM bowler_progression ORDER BY bowler_id').fetchall()
            self.assertEqual(len(progress),2)
            self.assertTrue(all(r['xp']>0 for r in progress))

    async def test_friendly_game_does_not_touch_ranked_career(self):
        self.session.friendly_challenge=True
        cog=Games(bot=object())
        await cog.finish(self.channel,self.session,self.channel.id)
        with database.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM games').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM game_results').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM game_history').fetchone()[0],0)
            result=db.execute('SELECT COUNT(*),SUM(xp) FROM bowler_progression').fetchone()
            self.assertEqual(tuple(result),(2,2))
        self.assertIsNone(SESSIONS.get(1551))

if __name__=='__main__':
    unittest.main()
