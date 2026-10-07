"""Offline v2.7.9.9 release gate. Run: python -m services.release_audit"""
import ast, pathlib
from models.bowler import Bowler
from services.game_engine import GameSession
from services.scoring import score_game
from services.simulation_lab import rookie_balance_suite

ROOT=pathlib.Path(__file__).resolve().parents[1]
CORE=['storage/database.py','services/game_engine.py','services/pin_engine.py','services/lane_physics.py','services/shot_strategy.py','services/lane_adaptation.py','services/career.py','services/honours.py','services/broadcast_director.py','services/gazette.py','services/v25.py','services/league_engine.py','cogs/league.py','cogs/competition_ui.py','cogs/games.py','cogs/director.py','cogs/menu.py','ui/embeds.py']

def run():
 checks=[]
 for rel in CORE:
  ast.parse((ROOT/rel).read_text(encoding='utf-8'));checks.append(('syntax '+rel,True))
 assert score_game([[10]]*12)==300;checks.append(('perfect 300 scoring',True))
 assert score_game([[9,1]]*9+[[9,1,9]])==190;checks.append(('all-spare scoring',True))
 b=Bowler(-1,'Audit',0,'R',1,15,15,15,15,15,15);s=GameSession([b],7279)
 for _ in range(8):s.bowl()
 from services.v25 import session_dict,session_from_dict
 restored=session_from_dict(session_dict(s));a=s.bowl();b_ev=restored.bowl()
 assert (a['pins'],a['down'],a['quality'])==(b_ev['pins'],b_ev['down'],b_ev['quality']);checks.append(('deterministic restore',True))
 from services.league_engine import STATES,FORMATS
 assert STATES==('draft','registration','locked','active','completed','archived');checks.append(('competition lifecycle',True))
 assert {'single_elimination','double_elimination','round_robin','groups_knockout','stepladder','best_of','qualifying'}<=set(FORMATS);checks.append(('competition formats',True))
 from services.league_engine import progress_fixture,record_series_game,fixture_roster,execute_movements
 assert all(callable(x) for x in (progress_fixture,record_series_game,fixture_roster,execute_movements));checks.append(('competition operations',True))
 from services.league_engine import competition_view,next_fixture,entrant_status,bowler_competitions
 assert all(callable(x) for x in (competition_view,next_fixture,entrant_status,bowler_competitions));checks.append(('competition director read model',True))
 rows,flags=rookie_balance_suite(1000)
 checks.append(('rookie balance suite',not flags))
 print('\n'.join(('PASS' if ok else 'WARN')+' '+name for name,ok in checks))
 if flags:print('\n'.join('WARN '+x for x in flags))
 return not flags

if __name__=='__main__':raise SystemExit(0 if run() else 1)
