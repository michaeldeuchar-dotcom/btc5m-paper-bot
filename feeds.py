"""Public BTC spot feeds (Binance.com is geo-blocked here). All calls have hard deadlines."""
from __future__ import annotations

import logging
import math
import statistics
import time
from datetime import datetime, timezone

import config
import net

log = logging.getLogger("btc5m")


def _cb_exchange():
    return float(net.hard_get_json("https://api.exchange.coinbase.com/products/BTC-USD/ticker", 5)["price"])


def _cb_retail():
    return float(net.hard_get_json("https://api.coinbase.com/v2/prices/BTC-USD/spot", 5)["data"]["amount"])


def _kraken():
    d = net.hard_get_json("https://api.kraken.com/0/public/Ticker?pair=XBTUSD", 5)
    if d.get("error"):
        raise RuntimeError(d["error"])
    return float(next(iter(d["result"].values()))["c"][0])


def _bitstamp():
    return float(net.hard_get_json("https://www.bitstamp.net/api/v2/ticker/btcusd", 5)["last"])


FEEDS = {"coinbase_exchange": _cb_exchange, "coinbase": _cb_retail, "kraken": _kraken, "bitstamp": _bitstamp}


def current_btc_spot() -> tuple[float, dict]:
    ok, err = net.parallel(FEEDS, deadline=6)
    if not ok:
        raise RuntimeError(f"all spot feeds failed: {err}")
    return float(statistics.median(ok.values())), ok


def coinbase_candles(start_ts: int, end_ts: int, granularity: int = 60) -> list:
    f = lambda t: datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")  # noqa: E731
    url = (f"https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity={granularity}"
           f"&start={f(start_ts)}&end={f(end_ts)}")
    data = net.hard_get_json(url, 8)
    if not isinstance(data, list):
        raise RuntimeError(f"bad candles payload {str(data)[:100]}")
    return sorted(data, key=lambda r: r[0])


def candle_ptb(window_start: int) -> tuple[float, str]:
    rows = coinbase_candles(window_start - 60, window_start + 1)
    for r in rows:
        if int(r[0]) == window_start - 60:
            return (float(r[1]) + float(r[2]) + float(r[4])) / 3.0, f"coinbase_1m_typical t={int(r[0])}"
    raise RuntimeError("no candle for price-to-beat")


_vol_cache = {"ts": 0.0, "v": config.DEFAULT_ANNUAL_VOL}


def realized_annual_vol() -> float:
    now = time.time()
    if now - _vol_cache["ts"] < 120:
        return _vol_cache["v"]
    _vol_cache["ts"] = now  # even on failure, don't retry every cycle
    try:
        rows = coinbase_candles(int(now) - config.VOL_LOOKBACK_MINUTES * 60 - 60, int(now))
        closes = [float(r[4]) for r in rows if float(r[4]) > 0]
        rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
        if len(rets) >= 30:
            v = statistics.pstdev(rets) * math.sqrt(365.25 * 24 * 60)
            _vol_cache["v"] = min(max(v, config.VOL_MIN), config.VOL_MAX)
    except Exception as exc:  # noqa: BLE001
        log.warning("vol candles failed (%s); keeping %.2f", exc, _vol_cache["v"])
    return _vol_cache["v"]
