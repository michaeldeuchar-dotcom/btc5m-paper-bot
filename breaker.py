"""Chop circuit breaker (paper only). Pauses NEW bets for variants that opt in when the market is choppy.

A check (one per 5-minute window) is CHOPPY when at least 2 of these 3 are true:
  1. straightness (last-hour |net move| / path length) < 0.15
  2. last-30-minute high-low range < 0.12% of price
  3. last-15-minute volume < 0.8x the hour's pace (the hour's average per-minute volume x 15)
It TRIPS after 3 choppy checks in a row. Once ON it stays on for at least 10 minutes and RESETS after
5 clean checks in a row, where "clean" means not choppy AND straightness >= 0.20.
It only blocks NEW bets. Open bets and scale-in adds on a position already open are left alone.
Per-variant switch in variants.json: "circuit_breaker": "block" (skips new bets while ON) or "watch"
(never blocks, only logs/marks what it would have blocked). Variants without the key are not touched or logged.
"""
from __future__ import annotations

STRAIGHT_MAX = 0.15
RANGE30_MAX_PCT = 0.12
VOL15_MAX_RATIO = 0.8
TRIP_AFTER = 3
CLEAR_AFTER = 5
CLEAR_STRAIGHT_MIN = 0.20
MIN_ON_SEC = 600


def choppy_flags(sig: dict) -> dict:
    return {"straight": sig["efficiency"] < STRAIGHT_MAX,
            "range": sig["range30_pct"] < RANGE30_MAX_PCT,
            "volume": sig["vol15_ratio"] < VOL15_MAX_RATIO}


def new_state() -> dict:
    return {"on": False, "choppy_run": 0, "clean_run": 0, "since": None, "last_ws": 0, "trips": 0,
            "checks": 0, "last": None, "blocked": {}, "would_block": {}}


def update(b: dict, sig: dict, ws: int, now: float) -> list[str]:
    """One check per window. Mutates b. Returns human-readable events (for the log)."""
    if b.get("last_ws") == ws or not sig or not sig.get("ok") or "range30_pct" not in sig:
        return []
    b["last_ws"] = ws
    b["checks"] = int(b.get("checks", 0)) + 1
    fl = choppy_flags(sig)
    n_true = sum(fl.values())
    choppy = n_true >= 2
    clean = (not choppy) and sig["efficiency"] >= CLEAR_STRAIGHT_MIN
    b["last"] = {"ws": ws, "choppy": choppy, "clean": clean, "straight": round(sig["efficiency"], 3),
                 "range30_pct": round(sig["range30_pct"], 3), "vol15_ratio": round(sig["vol15_ratio"], 2), "flags": n_true}
    ev = []
    b["choppy_run"] = int(b.get("choppy_run", 0)) + 1 if choppy else 0
    b["clean_run"] = int(b.get("clean_run", 0)) + 1 if clean else 0
    desc = (f"straightness {sig['efficiency']:.2f} (<{STRAIGHT_MAX}), 30m range {sig['range30_pct']:.3f}% (<{RANGE30_MAX_PCT}%), "
            f"15m volume {sig['vol15_ratio']:.2f}x hourly pace (<{VOL15_MAX_RATIO}x); {n_true}/3 flags")
    if not b.get("on"):
        if b["choppy_run"] >= TRIP_AFTER:
            b.update(on=True, since=now, clean_run=0, trips=int(b.get("trips", 0)) + 1)
            ev.append(f"BREAKER TRIPPED ON after {b['choppy_run']} choppy checks in a row: {desc}")
    else:
        if b["clean_run"] >= CLEAR_AFTER and now - float(b.get("since") or now) >= MIN_ON_SEC:
            ev.append(f"BREAKER RESET OFF after {b['clean_run']} clean checks, was on {(now - float(b['since'])) / 60:.0f} min: {desc}")
            b.update(on=False, since=None, choppy_run=0, clean_run=0)
    return ev
