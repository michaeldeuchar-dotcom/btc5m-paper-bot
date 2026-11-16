# btc5m-paper-bot — PAPER-TRADING EXPERIMENT ONLY

A fake-money experiment on Polymarket's 5-minute "Bitcoin Up or Down" markets. **It never places real
orders**: the code has no wallet, no order-signing, and uses no secrets. It reads public prices
(Coinbase, Kraken, Bitstamp, Polymarket Gamma + CLOB order books), pretends to buy at the real best ask
(including Polymarket's taker fee), and holds each pretend bet until the official result. Per-bet size is
hard-capped at $10 (fee included). Nothing here is financial advice.

- Several strategy variants run side by side, each with its own fake account (`variants.json`).
- Results: the `data` branch (`data/week1/trades_<variant>.csv`, `state.json`, log tails, `data/TWEAKS_LOG.md`).
- Summary: `python3 summarize.py` after copying the `data/` folder from the `data` branch.
- Runs on GitHub Actions in ~5h40m slices (`.github/workflows/paper-bot.yml`) until 2026-11-23 11:30 AM PT.
  Each slice starts the next one; an hourly schedule restarts the chain if it ever breaks.
- Stop it: commit a file named `STOP` to `main`, or disable the workflow.
- `research/` holds the backtest scripts used to pick the starting settings.
