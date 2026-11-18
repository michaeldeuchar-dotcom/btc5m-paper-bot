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

<!-- tweak:2026-11-17-breakout-scale -->
## 2026-11-17 ~20:50 PT — new paper variant breakout_scale (12 active)

Fake money only. Whole round (first bet + optional add, fees included) is capped at $5 (`round_cap: 5`, enforced in code per piece and again in bot.py).

Entry = breakout's signal AND scale_in's confirmation:
- Breakout: a finished 1-min candle closed above the prior 30-min high (or below the low) on >= 2x the average volume of that range, and the live price is still past that level.
- Confirmation (scale_in has no volume test of its own, so this is its 15-minute direction + edge check): the last 15 minutes must be moving the same way; >= 3c edge after the fee
  on the 50/50 model+market blend (no trend bonus); ask 30-75c; 120-240s left.
- Size: $2 base + $1 per extra 2c edge, capped at $5 incl. fee; rounds up to the 5-share minimum if that costs <= $4.
- Add (at most once): BTC at least $15 further past the price to beat than at the first fill AND our side's price at least 2c higher, 30s+ after the first fill, 60s+ left, ask <= 90c,
  only if the round total incl. fees stays <= $5. Note: with the 5-share minimum and $5 round cap an add only fits when the first piece is small (entry roughly under 47c), so adds will be rare.
- Cooldown: after a losing round, skip the next 2 qualifying setups (one per 5-minute window) AND at least 15 minutes, whichever is longer. Skips are logged as
  "Cooldown after a losing round: ..." in the bet reasons (plus COOLDOWN started/over lines in bot.log). Cooldown is kept in state.json so it survives restarts.

<!-- tweak:2026-11-17-disable-contrarian -->
## 2026-11-17 ~20:30 PT — contrarian variant disabled

Requested by the user. `contrarian` set to `"enabled": false` in variants.json, so it places no new paper bets.
Its past trades stay in data/week1/trades_contrarian.csv and still appear in the summaries (summarize.py reads every
trades_*.csv). Any of its bets still open settle normally (settlement doesn't depend on the variant being enabled).
The other 9 variants are unchanged. Fake money only.

<!-- tweak:2026-11-17-meta -->
## 2026-11-17 ~21:05 PT — new paper variant meta (14 active; contrarian stays off)

Fake money only. Cost incl. fee <= $4 per bet; `max_loss_per_bet: 10` also enforced.
- Scoring: every other ACTIVE variant (never itself) is scored on its settled bets filled in the last 3 hours (needs >= 5): score = net fake P&L / dollars bet. (Scale/add variants count each piece as a bet.)
  Scores are computed once per 5-minute round from the ledgers, so there is no extra network call or delay; meta uses the same spot/book/trend/model numbers as every other variant in that loop pass.
- Leader: the highest POSITIVE score. A new leader only takes over after being the best positive score at 2 straight checks (one check per round); if the current leader's score turns <= 0 meta stops betting until a new leader is confirmed.
- Bet: if the leader's own rules say "buy" this round (including its price range, timing, hour filter), meta copies the same side with its own size: $2, +$1 if the leader's 3h return > 10%, +$1 more if > 20%, max $4 incl. fee
  (rounds up to the 5-share minimum only if the cost stays <= $4). If the leader's rules don't fire: no bet from the leader.
- Fallback (my call: ON): if the leader doesn't fire, meta may copy the #2 variant, but only if #2 is also positive over 3h (5+ bets) and its rules fire; sized by #2's return the same way. Turn off with `fallback_to_second: false`.
- Everyone losing (no variant positive over 3h): meta sits out entirely.
- Cooldown (same as breakout_scale): after a losing bet, skip the next 2 qualifying setups AND at least 15 minutes, whichever is longer; skips are logged in bet reasons.
- Logging: every buy reason says which variant was copied, its rank, its 3h return/bets and the copied variant's own reason; skips say why (no leader yet, all losing, leader idle...). bot.log also logs "META: new leader ...".

<!-- tweak:2026-11-17-trend-spike-guarded-favorite -->
## 2026-11-17 ~20:45 PT — two new paper variants: trend_spike and guarded_favorite (11 active after contrarian was disabled)

Fake money only. Both cost $5 or less INCLUDING the fee (new `cap_incl_fee` setting caps shares at max_stake / (price + fee)).

- trend_spike: a stricter trend_volume. Needs all of trend_volume's rules (same chop skip < 0.15 straightness, same >90% volatility skip,
  hour momentum z >= 1, 15-min agrees) plus: the last 5 finished minutes must also move the same way; the last 5 minutes' volume must be a
  spike vs the hour's average 5-minute volume, with >= 3 of those 5 candles closing in the trend direction; trend-direction candles must
  carry >= 1.5x the volume of opposite candles (trend_volume: 1.15x). Entry: 120-210s left, asks 35-70c, >= 5c edge after fee
  (50/50 model+market blend + 3c trend bonus), $2 +$1 per 2c extra edge, max $5.
  THRESHOLD TWEAK (checked on ~4.1 days of live Coinbase 1-min candles, evaluated every minute): the spec as written (spike >= 2.0x, ALL 3 chunk
  steps showing higher highs/lows) passed the trend gate on only 22 of 5,929 minutes (0.4%, a handful of episodes in 4 days, before the price/edge
  filters), i.e. it would almost never trade. Loosened to spike >= 1.5x and 2 of 3 chunk steps -> 73 minutes (1.2%). Everything else kept as specified.
  For comparison trend_volume passed on 473 minutes (8%).
- guarded_favorite: buys the market favorite (side priced 60-85c) with 60-180s left, ONLY when trend_volume's filters (trend, structure,
  volume, same chop/volatility skips) all point at that same side; sits out if they point the other way or don't agree. Needs >= 2c edge after fee on
  the 50/50 blend + 3c trend bonus. $2 +$1 per 2c extra edge, max $5. New `max_loss_per_bet: 10` setting: stake and shares are capped so
  stake + fee can never exceed it, even if max_stake is raised later (tested with max_stake = 50).

<!-- tweak:2026-11-17-ultimate -->
## 2026-11-17 ~20:55 PT — new paper variant ultimate (13 active; contrarian stays off)

Fake money only. Round (first bet + optional add, fees included) <= $5; `max_loss_per_bet: 10` also enforced (stake, shares and the round total can never exceed it, even if the caps are raised).
- Entry needs ALL of trend_volume's filters: hour momentum (z >= 1) with the last 15 min the same way, higher highs AND higher lows (or lower/lower; 2 of 3 chunk steps), with-trend volume >= 1.15x
  against-trend volume, skip if choppy (straightness < 0.15) or very volatile (> 90% a year). Trend direction only.
- Plus >= 3c edge after the fee (50/50 model+market blend + the same 3c trend bonus trend_volume uses), asks 30-75c, 90-240s left.
- Size: $2 base + $1 per extra 2c of edge, $5 cap incl. fee, rounds up to the 5-share minimum if that costs <= $4.
- One add on scale_in's rule: BTC >= $15 further past the price to beat than at the first fill AND our side up >= 2c, >= 30s after, >= 60s left, only if the round stays <= $5 with fees
  (rare in practice because of the 5-share minimum).
- Cooldown (same as breakout_scale): after a losing round skip the next 2 qualifying setups AND at least 15 minutes, whichever is longer; skips are logged in the bet reasons.
