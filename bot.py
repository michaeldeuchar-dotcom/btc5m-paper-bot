#!/usr/bin/env python3
"""One-week PAPER bot for Polymarket 5-minute Bitcoin Up/Down markets.

PAPER ONLY: this build contains no order-signing or wallet code at all. It reads
public prices, simulates taker fills at the real best ask (with the taker fee),
holds every bet to the official resolution, and runs several strategy variants
side by side on the same data, each with its own ledger (data/week1/trades_<variant>.csv).
"""
from __future__ import annotations

import argparse
import collections
import faulthandler
import json
import logging
import logging.handlers
import os
import signal
import sys
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import config
import feeds
import polymarket
import store
import strategy

PT = ZoneInfo("America/Los_Angeles")
log = logging.getLogger("btc5m")
_SHUTDOWN = threading.Event()


def _on_signal(signum, _frame):
    if _SHUTDOWN.is_set():
        os._exit(0)
    _SHUTDOWN.set()
    log.info("received signal %s; stopping (forced exit in 20s if stuck)", signum)
    t = threading.Timer(20, lambda: os._exit(0))
    t.daemon = True
    t.start()


def setup_logging() -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    log.setLevel(logging.INFO)
    log.handlers.clear()
    h = logging.handlers.RotatingFileHandler(config.LOG_PATH, maxBytes=config.LOG_MAX_BYTES, backupCount=config.LOG_BACKUPS)
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S"))
    log.addHandler(h)


def _reason(msg: str) -> None:
    if config.LOG_BET_REASONS:
        log.info("REASON %s", msg)


# ---------------------------------------------------------------- variants
_variants = {"mtime": 0.0, "data": {}, "checked": 0.0}


def _tweak_log(text: str) -> None:
    config.TWEAKS_LOG.parent.mkdir(parents=True, exist_ok=True)
    new = not config.TWEAKS_LOG.exists()
    with config.TWEAKS_LOG.open("a") as f:
        if new:
            f.write("# Tweaks log (paper bot)\n\nEvery strategy/setting change, with time (PT) and reason.\n\n")
        f.write(text.rstrip() + "\n\n")


def load_variants(force: bool = False) -> dict:
    now = time.time()
    if not force and now - _variants["checked"] < 30:
        return _variants["data"]
    _variants["checked"] = now
    try:
        mt = config.VARIANTS_PATH.stat().st_mtime
        if force or mt != _variants["mtime"]:
            raw = json.loads(config.VARIANTS_PATH.read_text())
            data = {k: v for k, v in raw.items() if not k.startswith("_") and isinstance(v, dict) and v.get("enabled", True)}
            for k, v in data.items():  # hard ceiling, regardless of the file
                for key in ("base_stake", "max_stake", "high_ask_max_stake", "max_round_up_usd"):
                    if float(v.get(key, 0) or 0) > config.STAKE_HARD_MAX_USD:
                        log.warning("variant %s %s=%s clipped to $%.0f hard max", k, key, v[key], config.STAKE_HARD_MAX_USD)
                        v[key] = config.STAKE_HARD_MAX_USD
            if _variants["data"] and data != _variants["data"]:
                changed = []
                for k in sorted(set(data) | set(_variants["data"])):
                    a, b = _variants["data"].get(k), data.get(k)
                    if a != b:
                        diff = {x: f"{(a or {}).get(x)} -> {(b or {}).get(x)}" for x in sorted(set(a or {}) | set(b or {})) if (a or {}).get(x) != (b or {}).get(x)}
                        changed.append(f"- `{k}`: {diff}")
                _tweak_log(f"## {store.iso_pt()} — variants.json reloaded by running bot\n" + "\n".join(changed)
                           + "\n- Reason: see the entry written by whoever edited variants.json (above/below).")
                log.info("variants reloaded: %s", "; ".join(changed))
            _variants.update(mtime=mt, data=data)
    except Exception as exc:  # keep the last good set
        log.warning("variants.json reload failed (%s); keeping previous set", exc)
    return _variants["data"]


# ---------------------------------------------------------------- spot samples / price to beat
_samples: collections.deque = collections.deque(maxlen=2000)  # (ts, spot)


def own_twap(t0: float, t1: float, min_n: int = 10):
    xs = [p for (t, p) in _samples if t0 <= t <= t1]
    ts = [t for (t, p) in _samples if t0 <= t <= t1]
    if len(xs) >= min_n and ts[-1] - ts[0] >= 0.75 * (t1 - t0):
        return sum(xs) / len(xs)
    return None


def price_to_beat(state: dict, ws: int):
    cache = state.setdefault("ptb", {})
    if str(ws) in cache:
        return cache[str(ws)]["p"], cache[str(ws)]["src"]
    own = own_twap(ws - 60, ws)
    if own is not None:
        p, src = own, "own_spot_samples_60s"
    else:
        p, src = feeds.candle_ptb(ws)
    cache[str(ws)] = {"p": p, "src": src}
    for k in list(cache):
        if int(k) < ws - 3600:
            del cache[k]
    return p, src


# ---------------------------------------------------------------- hour filter (Tweak 2)
_hour_cache: dict = {}


def hour_filter_blocks(variant: str) -> str | None:
    if not config.HOUR_FILTER:
        return None
    hr = datetime.now(PT).hour
    key = (variant, hr)
    c = _hour_cache.get(key)
    if c and time.time() - c[0] < 300:
        return c[1]
    n, pnl = 0, 0.0
    for r in store.read_trades(variant):
        if r.get("status") != "resolved" or not r.get("pnl_usd"):
            continue
        try:
            if datetime.strptime(r["ts_fill_pt"][:19], "%Y-%m-%d %H:%M:%S").hour == hr:
                n += 1
                pnl += float(r["pnl_usd"])
        except ValueError:
            continue
    msg = None
    if n >= config.HOUR_FILTER_MIN_TRADES and pnl < 0:
        msg = f"hour_filter: {n} past trades in the {hr}:00 PT hour net ${pnl:.2f}"
    _hour_cache[key] = (time.time(), msg)
    return msg


# ---------------------------------------------------------------- resolution
_last_resolve = [0.0]


def resolve_open(state: dict, force: bool = False) -> None:
    if not force and time.time() - _last_resolve[0] < 15:
        return
    _last_resolve[0] = time.time()
    still = []
    by_window: dict = {}
    for item in state.get("open", []):
        ws = int(item["window_start"])
        if time.time() < ws + config.WINDOW_SECONDS + 5:
            still.append(item)
            continue
        if ws not in by_window:
            try:
                by_window[ws] = polymarket.fetch_event(ws)
            except Exception as exc:  # noqa: BLE001
                log.warning("resolve fetch failed for %s: %s", ws, exc)
                by_window[ws] = None
        m = by_window[ws]
        outcome = m.resolved_outcome if m else None
        if outcome is None:
            still.append(item)
            continue
        won = outcome == item["side"]
        pnl = (float(item["shares"]) if won else 0.0) - float(item["total_cost"])
        prior = sum(float(r["pnl_usd"]) for r in store.read_trades(item["variant"]) if r.get("status") == "resolved" and r.get("pnl_usd"))
        store.update_trade(item["variant"], item["trade_id"], {
            "status": "resolved", "ts_resolve_utc": store.iso_utc(), "outcome": outcome, "won": "1" if won else "0",
            "payout_usd": f"{float(item['shares']) if won else 0.0:.4f}", "pnl_usd": f"{pnl:.6f}",
            "cumulative_pnl_usd": f"{prior + pnl:.6f}",
            "official_ptb": (m.meta or {}).get("priceToBeat", ""), "official_final": (m.meta or {}).get("finalPrice", ""),
        })
        log.info("RESOLVED [%s] %s %s outcome=%s %s pnl=$%+.2f variant_total=$%+.2f",
                 item["variant"], item["trade_id"], item["side"], outcome, "WON" if won else "LOST", pnl, prior + pnl)
    state["open"] = still


# ---------------------------------------------------------------- main cycle
_mkt_cache: dict = {}
_last_decision_log: dict = {}
_reason_seen: set = set()
_stats = collections.Counter()


def get_market(ws: int):
    if ws in _mkt_cache:
        return _mkt_cache[ws]
    m = polymarket.fetch_event(ws)
    if m is not None and m.token_ids:
        _mkt_cache.clear()
        _mkt_cache[ws] = m
    return m


def paper_fill(state, name, d, m, ws, secs_left, spot, ptb, ptb_src, vol):
    if d.stake > config.STAKE_HARD_MAX_USD + 1e-9 or d.total_cost > config.STAKE_HARD_MAX_USD + 1e-9:
        log.error("REFUSED [%s] stake $%.2f above hard max", name, d.stake)
        return
    state["seq"] = int(state.get("seq", 0)) + 1
    tid = f"W{state['seq']:06d}"
    now = time.time()
    store.append_trade(name, {
        "trade_id": tid, "variant": name, "mode": "paper", "status": "open", "ts_fill_utc": store.iso_utc(now),
        "ts_fill_pt": store.iso_pt(now), "window_start": ws, "slug": m.slug, "title": m.title, "side": d.side,
        "ask": f"{d.ask:.4f}", "stake": f"{d.stake:.2f}", "shares": f"{d.shares:.2f}", "notional_usd": f"{d.notional:.4f}",
        "fee_usd": f"{d.fee:.6f}", "total_cost_usd": f"{d.total_cost:.6f}",
        "est_prob": "" if d.est_prob is None else f"{d.est_prob:.4f}", "model_p_up": f"{d.model_p_up:.4f}",
        "market_p_up": "" if d.market_p_up is None else f"{d.market_p_up:.4f}",
        "edge": "" if d.edge is None else f"{d.edge:.4f}", "btc_spot": f"{spot:.2f}", "price_to_beat": f"{ptb:.2f}",
        "ptb_source": ptb_src, "seconds_left": f"{secs_left:.1f}", "annual_vol": f"{vol:.4f}", "reason": d.english,
    })
    state.setdefault("open", []).append({"trade_id": tid, "variant": name, "window_start": ws, "side": d.side,
                                         "shares": d.shares, "total_cost": d.total_cost})
    state.setdefault("traded_windows", {}).setdefault(name, []).append(ws)
    state["traded_windows"][name] = state["traded_windows"][name][-50:]
    log.info("PAPER FILL [%s] %s %s $%.2f = %.2f sh @ %.2f (fee $%.3f) %.0fs left", name, tid, d.side, d.notional, d.shares, d.ask, d.fee, secs_left)
    _reason(f"[{name}] {d.english}")
    _stats["fills"] += 1


def cycle(state: dict, accepting: bool) -> None:
    now = time.time()
    try:
        spot, readings = feeds.current_btc_spot()
        _samples.append((now, spot))
        _stats["spot_ok"] += 1
    except Exception as exc:  # noqa: BLE001
        _stats["spot_fail"] += 1
        log.warning("spot fetch failed: %s", str(exc)[:300])
        resolve_open(state)
        return
    resolve_open(state)
    if not accepting:
        return
    ws = polymarket.window_start_ts(now)
    elapsed = now - ws
    secs_left = config.WINDOW_SECONDS - elapsed
    variants = load_variants()
    if config.SKIP_FIRST_MINUTE and elapsed < 60:
        key = ("*", ws, "first_minute")
        if key not in _reason_seen:
            _reason_seen.add(key)
            _reason("[all] Skipping: Tweak 1 SKIP_FIRST_MINUTE is on and this window is in its first 60 seconds.")
        return
    traded = state.setdefault("traded_windows", {})
    spos = state.setdefault("scale_pos", {})

    def _scale_open(n):  # scale_in may add to its own position later in the same round
        pos = spos.get(n)
        return bool(pos) and int(pos.get("ws", 0)) == ws

    todo = {n: v for n, v in variants.items() if (ws not in traded.get(n, []) or (v.get("mode") == "scale" and _scale_open(n)))
            and float(v.get("min_secs_left", 0)) - 3 <= secs_left <= float(v.get("max_secs_left", 300)) + 3}
    if not todo:
        return
    m = get_market(ws)
    if m is None or not m.token_ids:
        log.info("no market yet for %s", polymarket.slug_for(ws))
        return
    books = polymarket.fetch_books(m)
    vol = feeds.realized_annual_vol()
    ptb, ptb_src = price_to_beat(state, ws)
    obs = own_twap(ws + config.WINDOW_SECONDS - 60, now, min_n=3) if secs_left <= 60 else None
    p_up = strategy.p_up_model(spot, ptb, secs_left, vol, obs)
    _stats["evals"] += 1
    trend = feeds.trend_signals()  # cached 30s, one candle call; never raises
    tk = ("*", ws, "trend")
    if tk not in _reason_seen:  # record the trend read once per window for every variant to compare later
        _reason_seen.add(tk)
        log.info("TREND window=%s %s", ws, feeds.trend_summary(trend))
    for name, v in todo.items():
        block = hour_filter_blocks(name)
        if block:
            d = strategy.Decision(name, "skip", "hour_filter", f"Tweak 2 HOUR_FILTER: {block}.", model_p_up=p_up)
        else:
            if v.get("mode") == "scale" and _scale_open(name):
                d = strategy.decide_scale_add(name, v, spos[name], books=books, secs_left=secs_left, spot=spot, ptb=ptb, now=now)
                d.model_p_up = p_up
            else:
                d = strategy.decide(name, v, p_model=p_up, books=books, secs_left=secs_left, trend=trend, spot=spot)
        if d.action == "buy" and v.get("mode") == "scale":
            pos = spos.get(name) if _scale_open(name) else None
            spent = sum(float(f["cost"]) for f in pos["fills"]) if pos else 0.0
            if spent + d.total_cost > config.STAKE_HARD_MAX_USD + 1e-9:
                log.error("REFUSED [%s] round total $%.2f would exceed $10", name, spent + d.total_cost)
                d = strategy.Decision(name, "skip", "round_cap", "Round total would exceed $10.", model_p_up=p_up)
            else:
                if pos is None:
                    pos = spos[name] = {"ws": ws, "side": d.side, "fills": []}
                gap = (spot - ptb) if d.side == "Up" else (ptb - spot)
                pos["fills"].append({"ts": now, "ask": d.ask, "gap": gap, "cost": d.total_cost})
        if d.action == "buy":
            paper_fill(state, name, d, m, ws, secs_left, spot, ptb, ptb_src, vol)
        else:
            rk = (name, ws, d.reason)
            if rk not in _reason_seen:
                _reason_seen.add(rk)
                _reason(f"[{name}] Not betting: {d.english}")
        if d.action == "buy" or now - _last_decision_log.get(name, 0) >= config.DECISION_LOG_EVERY_SEC:
            _last_decision_log[name] = now
            f = lambda x, n=4: "" if x is None else f"{x:.{n}f}"  # noqa: E731
            store.append_decision({"ts_pt": store.iso_pt(now), "variant": name, "window_start": ws, "secs_left": f(secs_left, 1),
                                   "action": d.action, "reason": d.reason, "side": d.side or "", "est_prob": f(d.est_prob),
                                   "model_p_up": f(p_up), "market_p_up": f(d.market_p_up), "ask": f(d.ask), "edge": f(d.edge),
                                   "stake": f"{d.stake:.2f}", "shares": f"{d.shares:.2f}", "btc_spot": f"{spot:.2f}", "price_to_beat": f"{ptb:.2f}"})
    if len(_reason_seen) > 5000:
        _reason_seen.clear()


def heartbeat(state: dict, cycles: int, force_log: bool, last_log: list) -> None:
    now = time.time()
    hb = {"ts": now, "ts_pt": store.iso_pt(now), "pid": os.getpid(), "cycles": cycles, "open": len(state.get("open", [])),
          "last_spot": _samples[-1][1] if _samples else None, "stats": dict(_stats)}
    tmp = config.HEARTBEAT_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(hb))
    os.replace(tmp, config.HEARTBEAT_PATH)
    if force_log or now - last_log[0] >= config.HEARTBEAT_EVERY_SEC:
        last_log[0] = now
        log.info("HEARTBEAT pid=%s cycles=%d spot=%s open_bets=%d fills=%d spot_ok=%d spot_fail=%d errors=%d",
                 os.getpid(), cycles, hb["last_spot"], hb["open"], _stats["fills"], _stats["spot_ok"], _stats["spot_fail"], _stats["errors"])


COV_PATH = config.DATA_DIR / "coverage.json"


def _load_cov() -> dict:
    try:
        c = json.loads(COV_PATH.read_text())
        return {"awake_sec": float(c.get("awake_sec", 0)), "asleep_sec": float(c.get("asleep_sec", 0)), "sleeps": int(c.get("sleeps", 0))}
    except Exception:  # noqa: BLE001
        return {"awake_sec": 0.0, "asleep_sec": 0.0, "sleeps": 0}


def _save_cov(c: dict) -> None:
    tmp = COV_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(c))
    os.replace(tmp, COV_PATH)


def main() -> int:
    ap = argparse.ArgumentParser(description="PAPER-ONLY 5-minute BTC Up/Down bot")
    ap.add_argument("--mode", default="paper", help="only 'paper' is accepted")
    ap.add_argument("--until", default=config.RUN_UNTIL)
    a = ap.parse_args()
    if a.mode != "paper":
        print("This build is paper-only. Refusing to start.", file=sys.stderr)
        return 2
    until = datetime.fromisoformat(a.until)
    if until.tzinfo is None:
        until = until.replace(tzinfo=PT)
    setup_logging()
    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)
    fault_f = open(config.FAULT_PATH, "a")
    faulthandler.enable(fault_f)
    config.PID_PATH.write_text(f"{os.getpid()}\n")
    vs = load_variants(force=True)
    log.info("START paper-only bot pid=%s until=%s variants=%s hard_max=$%.0f toggles: SKIP_FIRST_MINUTE=%s HOUR_FILTER=%s(min %d) LOG_BET_REASONS=%s",
             os.getpid(), until.isoformat(), ",".join(vs), config.STAKE_HARD_MAX_USD, config.SKIP_FIRST_MINUTE,
             config.HOUR_FILTER, config.HOUR_FILTER_MIN_TRADES, config.LOG_BET_REASONS)
    state = store.load_state()
    cycles, last_log = 0, [0.0]
    grace_end = None
    last_pass = time.time()
    cov = _load_cov()
    while not _SHUTDOWN.is_set():
        gap = time.time() - last_pass
        last_pass = time.time()
        if gap > 30:
            # The box (VM) was paused: nothing on it ran, including this bot. Count it, don't treat it as a bot hang.
            cov["asleep_sec"] += gap
            cov["sleeps"] += 1
            _stats["box_sleeps"] += 1
            log.warning("BOX WAS ASLEEP for %.0fs (VM paused; no prices seen, no bets possible). Resuming.", gap)
        else:
            cov["awake_sec"] += gap
        if cycles % 15 == 0:
            _save_cov(cov)
        if config.KILL_SWITCH_PATH.exists():
            log.info("STOP file present; exiting")
            break
        accepting = datetime.now(PT) < until
        if not accepting and grace_end is None:
            grace_end = time.time() + config.RESOLVE_GRACE_SEC
            log.info("reached end time %s; no new bets, settling open ones for up to %ds", until.isoformat(), config.RESOLVE_GRACE_SEC)
        if grace_end and (not state.get("open") or time.time() > grace_end):
            (config.DATA_DIR / "FINISHED").write_text(store.iso_pt() + "\n")
            log.info("run finished; open bets left: %d", len(state.get("open", [])))
            break
        t0 = time.time()
        faulthandler.dump_traceback_later(config.CYCLE_STALL_DUMP_SEC, exit=False, file=fault_f)
        try:
            cycle(state, accepting)
        except Exception:  # noqa: BLE001 - one bad pass must never kill or hang the loop
            _stats["errors"] += 1
            log.exception("cycle error (continuing)")
        finally:
            faulthandler.cancel_dump_traceback_later()
        try:
            store.save_state(state)
        except Exception:  # noqa: BLE001
            log.exception("state save failed")
        cycles += 1
        dt = time.time() - t0
        if dt > 20:
            log.warning("slow cycle: %.1fs", dt)
        heartbeat(state, cycles, False, last_log)
        _SHUTDOWN.wait(max(0.2, config.POLL_INTERVAL_SEC - dt))
    store.save_state(state)
    log.info("bot exit")
    return 0


if __name__ == "__main__":
    sys.exit(main())
