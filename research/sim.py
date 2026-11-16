import json, math
exec(open('analyze.py').read().split("rows=[]")[0].replace("print(","(lambda *a,**k:None)("))
rows=json.load(open('rows.json'))
fee=lambda p:0.07*p*(1-p)
def sim(name,est_fn,thr,band=(0.0,1.0),slo=0,shi=300,half=0.01,one_per_window=True):
    seen=set(); n=0;cost=0;pay=0;wins=0
    for r in sorted(rows,key=lambda r:(r['w'],-r['sm'])):
        if one_per_window and r['w'] in seen: continue
        if not (slo<=r['sm']<shi): continue
        pu=est_fn(r); side='Up' if pu>=.5 else 'Down'
        est=pu if side=='Up' else 1-pu
        mid=r['m'] if side=='Up' else 1-r['m']
        ask=min(mid+half,0.99)
        if not (band[0]<=ask<=band[1]): continue
        edge=est-ask-fee(ask)
        if edge<thr: continue
        seen.add(r['w']); n+=1; c=1+fee(ask)/ask  # $1 notional
        won=(r['y']==1)==(side=='Up'); cost+=c; pay+= (1/ask if won else 0); wins+=won
    return n, (pay-cost)/cost if cost else 0, wins/n if n else 0
M=lambda r:p_new(r['spot'],r['ptb'],r['s'],r['v'],10,1.0)
for thr in (0.03,0.05,0.08,0.12):
  for band in ((0.0,1.0),(0.2,0.6),(0.6,0.9),(0.05,0.35)):
    for (slo,shi) in ((0,300),(60,240),(120,300),(0,90)):
      n,roi,wr=sim('m',M,thr,band,slo,shi)
      if n>=15: print('thr %.2f ask %s secs %d-%d  n=%3d win %.2f ROI %+.1f%%'%(thr,band,slo,shi,n,wr,roi*100))
print('--- blend 50/50')
B=lambda r:0.5*M(r)+0.5*r['m']
for thr in (0.02,0.03,0.05):
    n,roi,wr=sim('b',B,thr); print('blend thr',thr,n,round(wr,2),'%+.1f%%'%(roi*100))
print('--- follow favorite (market), no model')
for band in ((0.55,0.7),(0.7,0.85),(0.85,0.95)):
  for (slo,shi) in ((0,60),(60,120),(120,240)):
    F=lambda r:r['m']
    seen=set();n=0;cost=pay=0
    for r in sorted(rows,key=lambda r:(r['w'],-r['sm'])):
        if r['w'] in seen or not(slo<=r['sm']<shi): continue
        side='Up' if r['m']>=.5 else 'Down'; ask=(r['m'] if side=='Up' else 1-r['m'])+0.01
        if not(band[0]<=ask<=band[1]): continue
        seen.add(r['w']);n+=1;won=(r['y']==1)==(side=='Up');cost+=1+fee(ask)/ask;pay+=1/ask if won else 0
    if n: print('fav ask %s secs %d-%d n=%d ROI %+.1f%%'%(band,slo,shi,n,(pay-cost)/cost*100))
