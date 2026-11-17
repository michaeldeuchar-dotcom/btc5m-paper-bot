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
