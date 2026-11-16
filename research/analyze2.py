import json, math, statistics as st
exec(open('analyze.py').read().split("rows=[]")[0].replace("print(","(lambda *a,**k:None)("))
rows=[]
for w in W:
    c0=C.get(w['w']-60)
    if not c0: continue
    ptbp=typ(c0); v=vol(w['w'])
    for x in w['hist']:
        tp=x['t']
        if not (w['w']+20<tp<w['w']+295): continue
        ts=(tp//60)*60  # spot time <= market time (model is at an information DISADVANTAGE)
        c=C.get(ts-60)
        if not c or ts<=w['w']: continue
        rows.append(dict(s=w['w']+300-ts,sm=w['w']+300-tp,spot=c[4],ptb=ptbp,v=v,m=x['p'],y=1 if w['up_won'] else 0,w=w['w']))
print('rows',len(rows))
def brier(f,R): return st.mean((f(r)-r['y'])**2 for r in R)
for lo,hi in ((0,60),(60,120),(120,180),(180,300)):
    R=[r for r in rows if lo<=r['sm']<hi]
    print('secs left %d-%d n=%d market %.4f model %.4f'%(lo,hi,len(R),brier(lambda r:r['m'],R),brier(lambda r:p_new(r['spot'],r['ptb'],r['s'],r['v'],10,1.0),R)))
json.dump(rows,open('rows.json','w'))
