<!-- tweak:2026-11-17-disable-contrarian -->
## 2026-11-17 ~20:30 PT — contrarian variant disabled

Requested by the user. `contrarian` set to `"enabled": false` in variants.json, so it places no new paper bets.
Its past trades stay in data/week1/trades_contrarian.csv and still appear in the summaries (summarize.py reads every
trades_*.csv). Any of its bets still open settle normally (settlement doesn't depend on the variant being enabled).
The other 9 variants are unchanged. Fake money only.
