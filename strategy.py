"""Probability model + per-variant decision rules (paper only).

Model: Polymarket resolves Up if the Chainlink 60-second TWAP at window end is >=
the 60-second TWAP at window start. We estimate P(Up) with a random walk on the
END TWAP, not the spot price:
  * more than 60s left: end-TWAP variance = sigma^2 * ((s-60) + 60/3)
  * inside the last 60s:  part of the TWAP is already observed (our own spot samples);
    only the remaining s seconds are uncertain: variance = sigma^2 * s^3 / (3*60^2)
  * plus a fixed basis noise (our Coinbase proxy vs Chainlink, measured ~$18 sd).
This replaces the old model, which jumped to exactly 0% or 100% once 40s or less
remained (that is what produced the $10 "100% sure" Up bet at 63c that lost).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import config

SPY = 365.25 * 24 * 3600


def ncdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def fee_per_share(p: float) -> float:
    p = min(max(float(p), 0.0), 1.0)
    return config.TAKER_FEE_RATE * p * (1.0 - p)


def p_up_model(spot: float, ptb: float, secs_left: float, annual_vol: float,
               observed_twap: Optional[float] = None) -> float:
    if spot <= 0 or ptb <= 0:
        return 0.5
    s = max(float(secs_left), 0.0)
    sig2 = (annual_vol * config.VOL_MULT) ** 2 / SPY * spot * spot  # $^2 per second
    if s > 60:
        mean = spot
        var = sig2 * ((s - 60.0) + 20.0)
    else:
        obs = observed_twap if observed_twap is not None else spot
        mean = ((60.0 - s) * obs + s * spot) / 60.0
        var = sig2 * s ** 3 / (3.0 * 3600.0)
    var += config.BASIS_NOISE_USD ** 2
    return ncdf((mean - ptb) / math.sqrt(var))


@dataclass
class Decision:
    variant: str
    action: str                 # buy / skip
    reason: str
    english: str
    side: Optional[str] = None
    est_prob: Optional[float] = None
    model_p_up: Optional[float] = None
    market_p_up: Optional[float] = None
    ask: Optional[float] = None
    ask_size: float = 0.0
    fee_ps: Optional[float] = None
    edge: Optional[float] = None
    stake: float = 0.0
    shares: float = 0.0
    notional: float = 0.0
    fee: float = 0.0
    total_cost: float = 0.0
    extra: dict = field(default_factory=dict)


def _mid(book) -> Optional[float]:
    if book is None:
        return None
    if book.best_bid is not None and book.best_ask is not None:
        return (book.best_bid + book.best_ask) / 2.0
    return book.best_ask if book.best_ask is not None else book.best_bid


def size_bet(v: dict, edge: float, ask: float) -> tuple[float, float, str]:
    """Return (stake, shares, note). Stake never exceeds the $10 hard max."""
    hard = config.STAKE_HARD_MAX_USD
    if v.get("mode") == "favorite":
        stake = float(v.get("base_stake", 1))
    else:
        steps = math.floor((edge - float(v["min_edge"])) / float(v.get("edge_per_dollar", 0.02)) + 1e-9)
        stake = float(v.get("base_stake", 1)) + max(steps, 0)
    stake = min(stake, float(v.get("max_stake", 5)))
    if ask > float(v.get("high_ask", 1.0)):
        stake = min(stake, float(v.get("high_ask_max_stake", stake)))
    stake = min(stake, hard)
    shares = math.floor(stake / ask * 100) / 100
    # the $10 hard max covers the whole cost of the bet, including the taker fee
    hard_shares = math.floor(hard / (ask + fee_per_share(ask)) * 100) / 100
    shares = min(shares, hard_shares)
    note = ""
    if shares + 1e-9 < config.MIN_ORDER_SHARES and v.get("round_up_to_min_shares"):
        need = config.MIN_ORDER_SHARES * ask
        if need + config.MIN_ORDER_SHARES * fee_per_share(ask) <= min(float(v.get("max_round_up_usd", 0)), hard) + 1e-9:
            note = f"rounded ${stake:.2f} up to ${need:.2f} for the 5-share minimum"
            stake, shares = need, float(config.MIN_ORDER_SHARES)
    return stake, shares, note


def decide(name: str, v: dict, *, p_model: float, books: dict, secs_left: float) -> Decision:
    D = lambda action, reason, english, **kw: Decision(name, action, reason, english, **kw)  # noqa: E731
    up, down = books.get("Up"), books.get("Down")
    m_up = _mid(up)
    if m_up is None and down is not None and _mid(down) is not None:
        m_up = 1.0 - _mid(down)
    base = dict(model_p_up=p_model, market_p_up=m_up)

    if not (float(v.get("min_secs_left", 0)) <= secs_left <= float(v.get("max_secs_left", 300))):
        return D("skip", "timing", f"Only bets with {v.get('min_secs_left')}-{v.get('max_secs_left')}s left; {secs_left:.0f}s left now.", **base)

    if v.get("mode") == "favorite":
        if m_up is None:
            return D("skip", "no_book", "No prices in the order book.", **base)
        side = "Up" if m_up >= 0.5 else "Down"
        est = None
    else:
        w = float(v.get("blend_market", 0.0))
        p = p_model if m_up is None else (1 - w) * p_model + w * m_up
        side = "Up" if p >= 0.5 else "Down"
        est = p if side == "Up" else 1 - p
    book = up if side == "Up" else down
    if book is None or book.best_ask is None:
        return D("skip", "no_ask", f"Nobody is selling {side} right now.", side=side, est_prob=est, **base)
    ask = float(book.best_ask)
    fps = fee_per_share(ask)
    edge = None if est is None else est - ask - fps
    kw = dict(side=side, est_prob=est, ask=ask, ask_size=book.best_ask_size, fee_ps=fps, edge=edge, **base)
    if not (float(v.get("min_ask", 0)) <= ask <= float(v.get("max_ask", 1))):
        return D("skip", "ask_band", f"{side} costs {ask*100:.0f}c, outside this variant's {v.get('min_ask')}-{v.get('max_ask')} price range.", **kw)
    if edge is not None and edge < float(v["min_edge"]) - 1e-12:
        return D("skip", "edge_small", f"{side} at {ask*100:.0f}c: my estimate {est:.0%} beats price+fee by only {edge*100:.1f}c (need {float(v['min_edge'])*100:.0f}c).", **kw)
    stake, shares, note = size_bet(v, edge or 0.0, ask)
    if shares + 1e-9 < config.MIN_ORDER_SHARES:
        return D("skip", "min_shares", f"${stake:.2f} only buys {shares:.2f} shares of {side} at {ask*100:.0f}c; Polymarket's minimum is 5.", stake=stake, shares=shares, **kw)
    if book.best_ask_size + 1e-9 < shares:
        return D("skip", "thin_book", f"Only {book.best_ask_size:.1f} shares offered at {ask*100:.0f}c; need {shares:.2f}.", stake=stake, shares=shares, **kw)
    if stake > config.STAKE_HARD_MAX_USD + 1e-9:
        return D("skip", "hard_max", "Stake would exceed the $10 hard max.", **kw)
    notional = shares * ask
    fee = shares * fps
    why = (f"market favorite {side} at {ask*100:.0f}c with {secs_left:.0f}s left" if est is None else
           f"I put {side} at {est:.0%}, price+fee is {(ask+fps)*100:.1f}c, edge {edge*100:.1f}c")
    return D("buy", "ok", f"Buying ${notional:.2f} of {side}: {why}." + (f" ({note})" if note else ""),
             stake=stake, shares=shares, notional=notional, fee=fee, total_cost=notional + fee, extra={"note": note}, **kw)
