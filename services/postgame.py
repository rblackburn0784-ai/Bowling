"""Idempotent post-game career and tournament bookkeeping (v2.8.5s).

The base game is saved atomically under its stable session_uid. Everything in
this module is then committed in ONE transaction, guarded by game_finalizations.
Discord announcements are deliberately outside the transaction.
"""
import json
import random
from contextlib import nullcontext

from services.pin_engine import ALL,roll_pins
from services.scoring import score_game
from services.career import add_tendency
from services.v25 import award_progression,unlock_achievements
from storage.database import connect


def tournament_rolloff(session, summaries, totals):
    """A reproducible, fresh-rack, one-ball sudden-death roll-off on tied totals.

    It never changes ordinary tenpin scores or career / lane state. Highest-game
    scorer from each side represents the team. One roll each per round; repeat
    tied rounds, exactly as a pre-declared tournament tiebreak convention.
    """
    if len(totals)!=2 or len(set(totals.values()))!=1:
        return None, []
    teams=sorted(totals)
    reps={name:max((p for p,sm in summaries if p.bowler.team_name==name),
                   key=lambda p:score_game(p.frames)) for name in teams}
    rng=random.Random(f'rolloff:{session.session_uid}:{session.seed}')
    log=[]
    for round_no in range(1,513):
        pins={}
        for name in teams:
            player=reps[name]
            down,_,_=roll_pins(rng,player.bowler,set(ALL),lane=session.lane,
                               ball_key=player.ball_key if player.ball_key!='auto' else 'hybrid',
                               target_mode='strike',shot_intent='normal')
            pins[name]=len(down)
        log.append({'round':round_no,'pins':pins})
        if pins[teams[0]]!=pins[teams[1]]:
            return max(pins,key=pins.get),log
    # Never invent a coin flip or silently award a tied elimination match.
    raise RuntimeError('Roll-off tied 512 rounds; ask an administrator to resolve it.')


def commit_postgame(session, game_id, summaries, winner, totals, db=None):
    """Return (achievement_cards, winner, rolloff_log, newly_committed).

    A crash between base-game recording and this commit can be retried safely.
    """
    is_tourney=bool(session.tournament_id and session.match_id and len(totals)==2)
    rolloff=[]
    if is_tourney and winner is None:
        winner,rolloff=tournament_rolloff(session,summaries,totals)
    achievement_cards=[]
    with (nullcontext(db) if db is not None else connect()) as c:
        if c.execute('SELECT 1 FROM game_finalizations WHERE game_id=?',(game_id,)).fetchone():
            if is_tourney:
                m=c.execute('SELECT winner_id,rolloff_json FROM tournament_matches WHERE id=?',(session.match_id,)).fetchone()
                if m:
                    t=c.execute('SELECT name FROM teams WHERE id=?',(m['winner_id'],)).fetchone()
                    winner=t['name'] if t else winner
                    rolloff=json.loads(m['rolloff_json']) if m['rolloff_json'] else []
            if getattr(session,'fixture_id',None):
                fg=c.execute('''SELECT f.rolloff_json,f.winner_id,co.entrant_type FROM fixture_games f
                     JOIN fixtures fx ON fx.id=f.fixture_id
                     JOIN competitions co ON co.id=fx.competition_id
                     WHERE f.game_id=? AND f.fixture_id=?''',(game_id,session.fixture_id)).fetchone()
                if fg and fg['rolloff_json']:
                    rolloff=json.loads(fg['rolloff_json'])
                    table='teams' if fg['entrant_type']=='team' else 'bowlers'
                    row=c.execute(f'SELECT name FROM {table} WHERE id=?',(fg['winner_id'],)).fetchone()
                    if row:winner=row['name']
            return [],winner,rolloff,False
        season=c.execute("SELECT id FROM seasons WHERE status='active' ORDER BY id DESC LIMIT 1").fetchone()
        season_id=session.season_id or (season['id'] if season else None)
        for p,sm in summaries:
            name=p.bowler.team_name
            tr=c.execute('SELECT id FROM teams WHERE name=? COLLATE NOCASE',(name,)).fetchone() if name else None
            team_id=tr['id'] if tr else None
            # Backward-compatible if this DB has a partially processed pre-s release.
            already=c.execute('SELECT 1 FROM game_history WHERE game_id=? AND bowler_id=?',(game_id,p.bowler.id)).fetchone()
            if already:continue
            c.execute('''INSERT INTO game_history(game_id,bowler_id,season_id,tournament_id,team_id,score,strikes,spares,splits,split_conversions,longest_streak,clean,form)
                         VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                      (game_id,p.bowler.id,season_id,session.tournament_id,team_id,sm['score'],sm['strikes'],sm['spares'],sm['splits'],sm['split_conversions'],sm['longest_streak'],sm['clean'],getattr(p,'form',0)))
            if season_id:
                c.execute('INSERT OR IGNORE INTO season_bowler_stats(season_id,bowler_id) VALUES(?,?)',(season_id,p.bowler.id))
                c.execute('''UPDATE season_bowler_stats SET games=games+1,total_pins=total_pins+?,high_game=MAX(high_game,?),
                             strikes=strikes+?,spares=spares+?,split_conversions=split_conversions+? WHERE season_id=? AND bowler_id=?''',
                          (sm['score'],sm['score'],sm['strikes'],sm['spares'],sm['split_conversions'],season_id,p.bowler.id))
            award_progression(p.bowler.id,sm['score'],bool(session.tournament_id),winner==name,db=c)
            if sm['clean']:add_tendency(p.bowler.id,'consistency',2.2,'Repeated clean-game execution','game',db=c)
            if sm['longest_streak']>=6:add_tendency(p.bowler.id,'flair',1.8,'Produced a six-pack strike run','game',db=c)
            if sm['score']<120 and sm.get('opens',0)>=5:add_tendency(p.bowler.id,'consistency',-2.0,'Repeated game collapse with open frames','game',db=c)
            if sm['score']>=250:add_tendency(p.bowler.id,'nerves',1.5,'Delivered a 250+ pressure game','game',db=c)
            seven_ten='7–10 Split' in getattr(p,'special_conversions',set())
            for title,detail in unlock_achievements(p.bowler.id,sm,{'seven_ten':seven_ten},db=c):
                achievement_cards.append((p.bowler.name,title,detail))
        if is_tourney:
            from services.competition import _advance_byes
            m=c.execute('SELECT * FROM tournament_matches WHERE id=? AND tournament_id=?',
                        (session.match_id,session.tournament_id)).fetchone()
            if not m or not m['team_a_id'] or not m['team_b_id']:
                raise ValueError('Tournament match is missing its registered opponents')
            names={x['id']:x['name'] for x in c.execute('SELECT id,name FROM teams WHERE id IN (?,?)',(m['team_a_id'],m['team_b_id']))}
            if len(names)!=2 or set(names.values())!=set(totals):
                raise ValueError('Completed game does not match registered tournament teams')
            if winner not in totals:raise ValueError('Tournament must have a winner (roll-off required)')
            if m['status']=='complete':
                raise ValueError('Match already completed by another result; refusing duplicate advancement')
            winner_id=next(k for k,v in names.items() if v==winner)
            sa,sb=totals[names[m['team_a_id']]],totals[names[m['team_b_id']]]
            c.execute('UPDATE tournament_matches SET score_a=?,score_b=?,winner_id=?,status="complete",rolloff_json=? WHERE id=?',
                      (sa,sb,winner_id,json.dumps(rolloff) if rolloff else None,m['id']))
            c.execute('INSERT INTO head_to_head(team_a_id,team_b_id,winner_id,score_a,score_b,tournament_id,match_id) VALUES(?,?,?,?,?,?,?)',
                      (m['team_a_id'],m['team_b_id'],winner_id,sa,sb,session.tournament_id,m['id']))
            for team_id,won,score in [(m['team_a_id'],winner_id==m['team_a_id'],sa),(m['team_b_id'],winner_id==m['team_b_id'],sb)]:
                c.execute('INSERT OR IGNORE INTO team_history(team_id) VALUES(?)',(team_id,))
                c.execute('UPDATE team_history SET wins=wins+?,losses=losses+?,high_game=MAX(high_game,?) WHERE team_id=?',
                          (int(won),int(not won),score,team_id))
            detail=(f'{names[m["team_a_id"]]} and {names[m["team_b_id"]]} tied {sa}-{sb}; {winner} won the sudden-death roll-off.'
                    if rolloff else f'{winner} won {max(totals.values())}-{min(totals.values())}.')
            c.execute('INSERT INTO tournament_stories(tournament_id,match_id,kind,headline,detail) VALUES(?,?,?,?,?)',
                      (session.tournament_id,session.match_id,'result','Match decided',detail))
            _advance_byes(c,session.tournament_id)
        if getattr(session,'fixture_id',None):
            from services.league_engine import record_fixture_game_in_transaction
            fixture=record_fixture_game_in_transaction(c,session,game_id,totals,summaries)
            if fixture['rolloff']:
                winner=fixture['winner']
                rolloff=fixture['rolloff']
            # The result recorder owns fixture advancement in the same transaction.
        # LAST statement: if any effect fails, all writes above roll back.
        c.execute('INSERT INTO game_finalizations(game_id) VALUES(?)',(game_id,))
    return achievement_cards,winner,rolloff,True


def finalize_completed_session(session, session_key, summaries, winner, totals):
    """Atomic base game + career + fixture + tournament completion.

    A crash or constraint violation rolls ALL result/standings/stat changes back.
    The session UID permits safe retries, including a pre-s partially saved game.
    """
    from storage.database import record_completed_session
    from services.analytics import player_summary
    if not session.complete:
        raise ValueError('Incomplete session cannot be finalised.')
    # Never change an existing session's publication state on a failed commit.
    was_persisted=session.persisted
    try:
        with connect() as c:
            gid=record_completed_session(session,session_key,db=c)
            if gid is None:raise RuntimeError('Cannot resolve completed game')
            cards,winner,rounds,fresh=commit_postgame(
                session,gid,summaries,winner,totals,db=c)
        session.persisted=True
        return gid,cards,winner,rounds,fresh
    except Exception:
        session.persisted=was_persisted
        raise
