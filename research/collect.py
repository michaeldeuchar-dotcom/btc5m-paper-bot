"""Collect recent resolved 5m windows: official ptb/final, outcome, Up price history, Coinbase 1m candles."""
import requests, json, time, sys
from concurrent.futures import ThreadPoolExecutor
N=int(sys.argv[1]) if len(sys.argv)>1 else 400
S=requests.Session()
now=(int(time.time())//300)*300
wins=[now-300*i for i in range(2,N+2)]
def one(w):
    for a in range(3):
        try:
            ev=S.get(f"https://gamma-api.polymarket.com/events?slug=btc-updown-5m-{w}",timeout=10).json()
            if not ev: return None
            m=ev[0]['markets'][0]; md=ev[0].get('eventMetadata') or {}
            toks=json.loads(m['clobTokenIds']); px=json.loads(m['outcomePrices'])
            h=S.get(f"https://clob.polymarket.com/prices-history?market={toks[0]}&startTs={w}&endTs={w+300}&fidelity=1",timeout=10).json().get('history',[])
            return dict(w=w,ptb=md.get('priceToBeat'),final=md.get('finalPrice'),up_won=float(px[0])>0.5,hist=h,vol=m.get('volumeNum'))
        except Exception as e:
            time.sleep(1)
    return None
with ThreadPoolExecutor(8) as ex: rows=[r for r in ex.map(one,wins) if r]
# coinbase candles
c={}
lo=min(wins)-7200; hi=max(wins)+300
t=lo
from datetime import datetime,timezone
f=lambda x: datetime.fromtimestamp(x,tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
while t<hi:
    e=min(t+300*60,hi)
    for a in range(3):
        try:
            d=S.get(f"https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=60&start={f(t)}&end={f(e)}",timeout=10).json()
            for r in d: c[int(r[0])]=r
            break
        except Exception: time.sleep(1)
    t=e; time.sleep(0.3)
json.dump(dict(windows=rows,candles=c),open('dataset.json','w'))
print(len(rows),'windows',len(c),'candles')
