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
