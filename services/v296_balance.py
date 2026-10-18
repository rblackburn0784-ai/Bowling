"""100,000-game capable deterministic balance audit, no SQLite writes.
Run: python -m services.v296_balance --games 100000 --out report.json
"""
import argparse,json
from services.simulation_lab import SimProfile,run_profile,dominance_flags

PROFILES=(
 SimProfile('Balanced'),
 SimProfile('Technician',accuracy=25,consistency=25,spin=10,nerves=10,style=10,flair=10),
 SimProfile('Power Shape',accuracy=10,consistency=10,spin=25,nerves=10,style=25,flair=10),
 SimProfile('Clutch Control',accuracy=20,consistency=20,spin=10,nerves=25,style=10,flair=5),
 SimProfile('Showman',accuracy=10,consistency=10,spin=15,nerves=10,style=20,flair=25),
)
LANES=('house','sport','heavy','dry')

def report(total_games=100000,lanes=('house','sport','heavy','dry'),seed=7275):
    total_games=int(total_games)
    if not 20<=total_games<=100000:
        raise ValueError('Total simulated games must be between 20 and 100,000')
    if not lanes or any(x not in LANES for x in lanes):
        raise ValueError('Use one or more of house, sport, heavy, dry')
    scenarios=len(lanes)*len(PROFILES)
    base,extra=divmod(total_games,scenarios)
    if base==0:raise ValueError('Not enough games for every scenario')
    rows=[]
    for idx,(lane,profile) in enumerate((l,p) for l in lanes for p in PROFILES):
        n=base+int(idx<extra)
        r=run_profile(profile,n,lane=lane,seed=seed+idx*104729)
        r['lane']=lane
        rows.append(r)
    flags={}
    for lane in lanes:
        flags[lane]=dominance_flags([r for r in rows if r['lane']==lane])
    return {'release':'2.9.6','requested_games':total_games,
            'simulated_games':sum(r['games'] for r in rows),
            'seed':seed,'lanes':list(lanes),'results':rows,'warnings':flags,
            'note':'Statistical simulations; results depend on sample size and seed. No gameplay or progression writes.'}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--games',type=int,default=100000)
    parser.add_argument('--lanes',nargs='+',choices=LANES,default=LANES)
    parser.add_argument('--seed',type=int,default=7275)
    parser.add_argument('--out',type=str,default='v296_balance_report.json')
    args=parser.parse_args()
    report_data=report(args.games,args.lanes,args.seed)
    with open(args.out,'w',encoding='utf8') as f:json.dump(report_data,f,indent=2)
    print(f"v2.9.6: {report_data['simulated_games']:,} simulated games -> {args.out}")
    for ln,warnings in report_data['warnings'].items():print(ln,':', ', '.join(warnings) or 'No automatic thresholds exceeded')

if __name__=='__main__':main()
