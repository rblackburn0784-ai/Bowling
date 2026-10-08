import discord
from services.commentary import event_text,perfect_watch
from services.dude_commentary import stage_line
from services.career import rank_title,rank_progress
from services.v25 import archetype
from services.v271 import bowler_loadout
from services.equipment import BALLS
from storage.database import connect

def bowler_embed(b):
    with connect() as c:
        s=c.execute('SELECT * FROM bowler_stats WHERE bowler_id=?',(b.id,)).fetchone()
        p=c.execute('SELECT * FROM bowler_progression WHERE bowler_id=?',(b.id,)).fetchone()
        o=c.execute('SELECT * FROM bowler_origins WHERE bowler_id=?',(b.id,)).fetchone()
        recent=c.execute('SELECT score FROM game_results WHERE bowler_id=? ORDER BY id DESC LIMIT 5',(b.id,)).fetchall()
        ac=c.execute('SELECT COUNT(*) n FROM achievements WHERE bowler_id=?',(b.id,)).fetchone()
        aw=c.execute('SELECT COUNT(*) n FROM awards WHERE bowler_id=?',(b.id,)).fetchone()
        ho=c.execute('SELECT COUNT(*) n FROM career_honours WHERE bowler_id=?',(b.id,)).fetchone()
        seasons=c.execute('SELECT COUNT(DISTINCT season_id) n FROM season_bowler_stats WHERE bowler_id=? AND games>0',(b.id,)).fetchone()
        champs=c.execute("SELECT COUNT(*) n FROM career_honours WHERE bowler_id=? AND code='champion'",(b.id,)).fetchone()
    s=dict(s) if s else {};xp=p['xp'] if p else 0;progress,nxt=rank_progress(xp,b.rank);games=s.get('games',0);avg=s.get('total_pins',0)/games if games else 0
    scores=[x['score'] for x in recent][::-1];form=' '.join('🟢' if x>=avg+10 else '🔴' if x<=avg-10 else '🟡' for x in scores) if scores else '—'
    load=bowler_loadout(b.id);ball=BALLS.get(load.get('primary_ball','hybrid'))
    e=discord.Embed(title=f'🎳 {b.name} — Career Profile',description=f"{b.handedness}-handed • **{rank_title(b.rank)} — Rank {b.rank}** • **{archetype(b)}**\nXP **{xp}**"+(f" / **{nxt}** • Next-rank progress **{progress:.0f}%**" if nxt else " • **MAX RANK**")+f"\nPreferred ball: **{ball.name if ball else 'Hybrid'}**")
    e.add_field(name='📈 Recent Form',value=f"{form}\n"+(('Last 5: '+' · '.join(map(str,scores))) if scores else 'No completed games yet')+f"\nCareer Avg **{avg:.1f}** • PB **{s.get('high_game',0)}**",inline=False)
    lines=[]
    for n in ('accuracy','consistency','spin','nerves','style','flair'):
        base=o[n] if o else getattr(b,n);now=getattr(b,n);d=now-base;mark=f"▲{d}" if d>0 else f"▼{abs(d)}" if d<0 else '—';lines.append(f"**{n.title()}** {base} → **{now}** {mark}")
    e.add_field(name='🧬 Rookie → Current',value='\n'.join(lines),inline=True)
    strike_pct=(s.get('strikes',0)/(games*10)*100) if games else 0;spare_chances=max(0,games*10-s.get('strikes',0));spare_pct=(s.get('spares',0)/spare_chances*100) if spare_chances else 0
    e.add_field(name='📊 Career',value=f"Games **{games}**\n200+ **{s.get('games_200',0)}** • 250+ **{s.get('games_250',0)}** • 300 **{s.get('perfect_games',0)}**\nClean **{s.get('clean_games',0)}**\nStrike **{strike_pct:.1f}%** • Spare **{spare_pct:.1f}%**\nSplits **{s.get('split_conversions',0)}/{s.get('splits',0)}**",inline=True)
    e.add_field(name='🏅 Legacy',value=f"Seasons **{seasons['n']}** • Championships **{champs['n']}**\nAchievements **{ac['n']}** • Awards **{aw['n']}** • Honours **{ho['n']}**\nCredits **{p['credits'] if p else 0}**",inline=False)
    e.set_footer(text=f'Attribute total: {b.stat_total} • Rank is career prestige')
    return e

def scoreboard_embed(session,last=None,team_names=None,director=None,stage=None,prior_cards=None,prior_scores=None):
    e=discord.Embed(title='🎳 Gutter Saints — Live Game',description=f'Lane: **{session.lane.title()}** • Seed: `{session.seed}`')
    cards=prior_cards if stage and stage!='leave' and prior_cards is not None else session.card()
    scores=prior_scores if stage and stage!='leave' and prior_scores is not None else session.scores()
    totals={}
    for p in session.players:
        frames=cards[p.bowler.name]+['·']*(10-len(cards[p.bowler.name]));value=' | '.join(f'{i+1}:{x}' for i,x in enumerate(frames[:10]))
        if p.complete and p.bowler.name in scores:value+=f"\n**Final: {scores[p.bowler.name]}**"
        team=getattr(p.bowler,'team_name',None)
        if p.bowler.name in scores and team:totals[team]=totals.get(team,0)+session.scores()[p.bowler.name]
        e.add_field(name=f"{p.bowler.name}"+(f' — {team}' if team else ''),value=value,inline=False)
    if totals:e.add_field(name='🏆 Team Totals',value='\n'.join(f'**{k}: {v}**' for k,v in totals.items()),inline=False)
    if last:
        intent=last.get('shot_intent','normal').title();ball=last.get('ball_key','hybrid').title();lane_no=last.get('lane_no','?');trans=last.get('transition',0)
        zones=last.get('lane_zones',{});line=last.get('line_boards',0);move=f' • Line {abs(line)} boards '+('left' if line>0 else 'right') if line else ''
        e.add_field(name='🎯 Shot Decision',value=f'**{ball}** • **{intent}** • Lane **{lane_no}** ({trans*100:.0f}% transition){move} • Target **{last.get("physics",{}).get("target","pocket")}**\nOil read: outside {zones.get("outside",0)*100:.0f}% • track {zones.get("track",0)*100:.0f}% • inside {zones.get("inside",0)*100:.0f}%',inline=False)
        if stage and stage!='leave':
            commentary=stage_line(session,stage,last)
        else:
            commentary=event_text(session,last)
            if director:commentary+='\n\n🎙️ **BROADCAST DIRECTOR**\n'+director
        e.add_field(name='🎙️ Game Updates',value=commentary[:1024],inline=False)
        p=next(x for x in session.players if x.bowler.name==last['bowler']);watch=perfect_watch(p) if not stage or stage=='leave' else None
        if watch:e.add_field(name='🚨 Perfect Game Watch',value=watch,inline=False)
    return e

def bracket_embed(t,rows):
    e=discord.Embed(title=f"🏆 {t['name']}",description=f"Status: **{t['status'].replace('_',' ').title()}** • Lane: **{t['lane_condition'].title()}**")
    rounds={}
    for r in rows:rounds.setdefault(r['round_no'],[]).append(r)
    for rn,ms in rounds.items():
        text=[]
        for m in ms:
            a=m['team_a'] or 'BYE';b=m['team_b'] or 'BYE';sc=f" ({m['score_a']}–{m['score_b']})" if m['score_a'] is not None else ''
            text.append(f"**M{m['match_no']}** {a} vs {b}{sc}"+(f" → **{m['winner']}**" if m['winner'] else ''))
        e.add_field(name=f'Round {rn}',value='\n'.join(text),inline=False)
    return e
