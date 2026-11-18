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
