import json, math, statistics as st, sys
from collections import defaultdict
D=json.load(open('dataset.json')); C={int(k):v for k,v in D['candles'].items()}
W=[w for w in D['windows'] if w['ptb'] and w['final'] and w['hist']]
print('usable windows',len(W))
SPY=365.25*24*3600
def ncdf(x): return 0.5*(1+math.erf(x/math.sqrt(2)))
def typ(c): return (c[1]+c[2]+c[4])/3
def vol(t):
    cl=[C[k][4] for k in range(t-7200,t,60) if k in C]
    r=[math.log(cl[i]/cl[i-1]) for i in range(1,len(cl))]
    return min(max(st.pstdev(r)*math.sqrt(SPY/60),0.2),1.2) if len(r)>30 else .45
def mkt(h,t):
    p=None
    for x in h:
        if x['t']<=t: p=x['p']
    return p
# proxy errors
e1=[];e2=[]
for w in W:
    c=C.get(w['w']-60); c2=C.get(w['w']+240)
    if c: e1.append(typ(c)-w['ptb'])
    if c2: e2.append(typ(c2)-w['final'])
print('ptb proxy err mean %.2f sd %.2f; final proxy err mean %.2f sd %.2f  n=%d'%(st.mean(e1),st.pstdev(e1),st.mean(e2),st.pstdev(e2),len(e1)))
# per-window moves
mv=[w['final']-w['ptb'] for w in W]; print('final-ptb sd $%.1f, up rate %.3f'%(st.pstdev(mv),sum(w['up_won'] for w in W)/len(W)))
def p_old(spot,ptb,s,v):
    te=max(s-40,0)
    if te<=0: p=1.0 if spot>=ptb else 0.0
    else: p=ncdf(math.log(spot/ptb)/(v*math.sqrt(te/SPY)))
    if s>120: p=min(max(p,.05),.95)
    return p
def p_new(spot,ptb,s,v,b,mult=1.0):
    sig2=(v*mult)**2/SPY*spot*spot  # $^2 per second
    if s>60: var=sig2*((s-60)+20)
    else: var=sig2*s**3/3/3600
    var+=b*b
    return ncdf((spot-ptb)/math.sqrt(var))
rows=[]
for w in W:
    for k in (1,2,3,4):
        t=w['w']+60*k; c=C.get(t-60)
        if not c: continue
        spot=c[4]; s=300-60*k; m=mkt(w['hist'],t)
        if m is None: continue
        c0=C.get(w['w']-60); ptbp=typ(c0) if c0 else None
        if not ptbp: continue
        rows.append(dict(s=s,spot=spot,ptb=ptbp,optb=w['ptb'],v=vol(w['w']),m=m,y=1 if w['up_won'] else 0))
print('rows',len(rows))
def brier(f): return st.mean((f(r)-r['y'])**2 for r in rows)
def ll(f):
    return -st.mean(math.log(min(max(f(r) if r['y'] else 1-f(r),1e-4),1)) for r in rows)
print('market brier %.4f ll %.4f'%(brier(lambda r:r['m']),ll(lambda r:r['m'])))
print('old model brier %.4f'%brier(lambda r:p_old(r['spot'],r['ptb'],r['s'],r['v'])))
for b in (0,10,20,30,50):
  for mult in (0.8,1.0,1.25,1.5):
    print('new b=%d mult=%.2f brier %.4f ll %.4f'%(b,mult,brier(lambda r:p_new(r['spot'],r['ptb'],r['s'],r['v'],b,mult)),ll(lambda r:p_new(r['spot'],r['ptb'],r['s'],r['v'],b,mult))))
json.dump(rows,open('rows.json','w'))
