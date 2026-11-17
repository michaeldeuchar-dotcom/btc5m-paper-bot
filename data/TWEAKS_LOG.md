# Tweaks log (paper bot)

Every strategy/setting change, with time (PT) and reason. Paper only, no wallet key, $10 hard max per bet (including fee).

## 2026-11-16 11:36 AM PT — Week 1 paper run started (runs until 2026-11-23 11:30 AM PT)

Evidence used: today's 2-hour run (3 bets, -$1.49), its decisions.csv, and a backtest of 599 resolved
5-minute windows (Nov 14-16) using Polymarket's official price-to-beat/final price, Polymarket price history,
and Coinbase 1-minute candles (research/collect.py, analyze*.py, sim.py).

Fixes:
- Freeze fix: every network call now has a hard wall-clock deadline (net.py), spot feeds run in parallel,
  the hour filter no longer makes 12 silent Gamma calls a minute, each loop pass is wrapped in try/except,
  heartbeat line every minute + heartbeat.json every pass, stack dump if a pass stalls >90s,
  supervisor.py restarts the bot if it dies or the heartbeat is >3 min old. Logs rotate.
- Model fix: the old math jumped to 0% / 100% once 40s or less were left. That is why it bet the full $10 on Up at 63c
  at 10:24 "100% sure" when Bitcoin was only $4 above the start price. New model prices the 60-second average
  (what Polymarket actually settles on) and adds the measured ~$15-18 gap between our Coinbase price and Chainlink.
- Hard max now covers the fee too (today's "$10" bet actually cost $10.26).

Variants started side by side (each its own fake account, data/week1/trades_<variant>.csv):
- main: model blended 50/50 with market price, 4c min edge, 90-240s left, asks 20-80c, $1 +$1 per 2c extra edge, cap $5,
  cap $2 when ask >70c, never rounds up to the 5-share minimum (user's original rule).
  Why: backtest - blending with the market was the most consistent (+10-12% on ~100 bets, noisy); the model alone was
  worse than the market near the end of a window; the last 90 seconds lost money at mid prices.
- main_minfill: same as main, but rounds a too-small bet up to 5 shares if that costs $3 or less.
  Why: with the 5-share minimum, a $1 bet only fills at 20c or less, so `main` may rarely trade. This tests whether
  allowing a small round-up is worth it.
- model_early: model only, 8c min edge, 120-240s left, cap $5. Why: best pocket in backtest (+9-10%, ~100 bets).
- blend_wide: blend, 3c edge, 30-240s left, cap $5. Why: more bets, tests if lower bar still pays.
- legacy_fixed: today's original rules ($1 +$1 per 1c edge, up to $10, any time, 3c) with the fixed math. Control.
- ride_favorite: no model; buys the market favorite at 70-85c with 60-120s left, flat $4.50. Mirrors trading by hand
  "with the direction". Backtest: roughly break-even after fees.

Toggles: SKIP_FIRST_MINUTE=True, HOUR_FILTER=True (now uses each variant's own paper history per hour of day:
skips an hour once there are >= 8 settled bets in that hour and they are net negative; CLOB /trades is 401),
LOG_BET_REASONS=True. Paper loss limit: none (user request).

<!-- tweak:2026-11-16-trend-breakout-contrarian-scale-stakes -->
## 2026-11-16 ~20:45 PT — 4 new variants (10 total) + max bet raised to $10 on the original six

Requested by the user. Paper/fake money only, no order or wallet code. Every bet, and every scale_in round,
costs $10 or less INCLUDING the taker fee (shares are capped so shares × (price + fee) ≤ $10).

Max bet changes (entry rules, edges, time windows and price ranges NOT changed):
- main $5 -> $10; main_minfill $5 -> $10; model_early $5 -> $10; blend_wide $5 -> $10 (still $1 +$1 per 2c extra edge,
  so $10 needs about 22c more edge than the minimum; the existing "max $2 when the price is above 70c" rule is kept on all four).
- ride_favorite flat $4.50 -> flat $10. legacy_fixed stays $10 (confirmed).

New variants:
- trend_volume (max $5, new and untested so kept at the original ask): uses the last 60 finished 1-min Coinbase candles.
  Bets only WITH the trend when ALL agree: hour momentum z >= 1.0 (the hour's move is at least 1x what random wiggle
  would give), last 15 min moving the same way, structure = higher highs AND higher lows (or lower/lower) in >= 2 of 3
  steps across four 15-min chunks with the last chunk beyond the first, and trend-direction candles averaging >= 1.15x
  the volume of opposite candles. Sits out if choppy (straightness |net move| / total path < 0.15) or very volatile
  (> 90% annualized). Estimate = 50/50 model+market + 3c trend bonus; needs 3c edge after fee; asks 30-75c; 90-240s left;
  $1 +$1 per 2c, rounds up to 5 shares if <= $4.
- breakout (max $10, $4 above 70c): a finished 1-min candle closed above the prior 30-min high (or below the low) on
  >= 2x that range's average volume, and the live price is still past the level. Bets the break direction. Same
  estimate/edge as trend_volume (3c), asks 25-80c, 90-240s left, $2 +$1 per 2c.
- contrarian (flat $2): when the favorite is >= 90c (underdog 2-10c), buy the underdog, 90-240s left. Small stake because
  these mostly lose; one win pays 10-50x.
- scale_in (round total <= $10): first $3 on the side the 50/50 model+market blend favors (3c edge, 150-240s left,
  asks 30-75c, last 15 min must move the same way). Up to 2 adds of $3 each, >= 30s apart with >= 60s left, only if BTC
  is $15+ further past the price to beat than at the previous fill AND our side's price rose 2c+ (max 90c). Each piece
  is its own trade row with its own fee and settles on its own.

Also: the bot logs one "TREND" line per window (momentum, structure, volume, 30-min range) so every variant's results
can later be compared against the trend read.
