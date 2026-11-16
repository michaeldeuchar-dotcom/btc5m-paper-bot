"""Configuration for the one-week PAPER run of the 5-minute BTC Up/Down bot.

PAPER ONLY. This build has no live-order path. Per-trade stake can never exceed
STAKE_HARD_MAX_USD ($10); that ceiling is enforced in code at fill time, no matter
what variants.json says.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUN_NAME = "week1"
DATA_DIR = ROOT / "data" / RUN_NAME          # week run lives here; today's 2-hour run stays in data/
STATE_PATH = DATA_DIR / "state.json"
LOG_PATH = DATA_DIR / "bot.log"
DECISIONS_CSV = DATA_DIR / "decisions.csv"
HEARTBEAT_PATH = DATA_DIR / "heartbeat.json"
PID_PATH = DATA_DIR / "bot.pid"
FAULT_PATH = DATA_DIR / "stack_dumps.log"
VARIANTS_PATH = ROOT / "variants.json"
TWEAKS_LOG = ROOT / "data" / "TWEAKS_LOG.md"
KILL_SWITCH_PATH = ROOT / "STOP"             # touch this file to stop bot + supervisor

GAMMA_BASE = "https://gamma-api.polymarket.com"
CLOB_BASE = "https://clob.polymarket.com"
SLUG_TEMPLATE = "btc-updown-5m-{start}"
WINDOW_SECONDS = 300

RUN_UNTIL = "2026-11-23T11:30:00-08:00"      # hard end of the week run (PT)
RESOLVE_GRACE_SEC = 900                      # after RUN_UNTIL keep settling open paper bets

STAKE_HARD_MAX_USD = 10.00                   # ABSOLUTE ceiling per trade. Never raise.
MIN_ORDER_SHARES = 5
TAKER_FEE_RATE = 0.07                        # fee = shares * 0.07 * p * (1-p)

# Model (calibrated on 599 resolved windows, see research/)
BASIS_NOISE_USD = 15.0                       # Coinbase-vs-Chainlink price-to-beat proxy error (measured sd ~$18)
VOL_MULT = 1.0
DEFAULT_ANNUAL_VOL = 0.45
VOL_MIN, VOL_MAX = 0.20, 1.20
VOL_LOOKBACK_MINUTES = 120

# Loop / network
POLL_INTERVAL_SEC = 2.0
HTTP_CONNECT_TIMEOUT = 4
HTTP_READ_TIMEOUT = 6
HTTP_HARD_DEADLINE = 8                       # wall-clock cap per request (covers DNS too)
CYCLE_STALL_DUMP_SEC = 90                    # dump a stack trace if one loop pass takes longer
HEARTBEAT_EVERY_SEC = 60
DECISION_LOG_EVERY_SEC = 20                  # per variant, plus every buy
LOG_MAX_BYTES = 5_000_000
LOG_BACKUPS = 5
DECISIONS_MAX_BYTES = 20_000_000
DECISIONS_BACKUPS = 3
USER_AGENT = "btc5m-bot/2.0 (paper; research)"

# ---------------------------------------------------------------------------
# The three labeled tweaks (global on/off switches; each also applies per variant)
# ---------------------------------------------------------------------------
# Tweak 1: SKIP_FIRST_MINUTE — never trade in the first 60 seconds of a 5-minute window.
SKIP_FIRST_MINUTE = True
# Tweak 2: HOUR_FILTER — skip an hour of the day (PT) once a variant has at least
# HOUR_FILTER_MIN_TRADES settled paper trades in that hour-of-day this run AND is net
# negative there. (CLOB /trades needs auth / 401s, so this uses the bot's own history.)
HOUR_FILTER = True
HOUR_FILTER_MIN_TRADES = 8
# Tweak 3: LOG_BET_REASONS — write a plain-English reason for buys and skips to the log.
LOG_BET_REASONS = True
