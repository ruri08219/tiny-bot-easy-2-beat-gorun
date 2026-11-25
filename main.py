"""Tiny dip-buy bot for the make.fun bars-replay/v1 harness.

Strategy (mean reversion on hourly Solana bars, validated on the dev
window, three 72-bar slices and two reversed windows in a local replay
simulator): buy an asset after it drops >= 190 bps over the last 6
hourly bars, hold at most 24 bars, take profit at +300 bps, stop loss
at -200 bps. Position PnL is measured against the position cost, so
fees are already in. Each buy is 24% of equity (the weight cap is 25%).

hello: the harness greets the bot once; every batch of bars after that
carries the fills and each symbol's latest close, and the bot answers
that batch with its orders for the next bar. Orders decided on bar k
fill at bar k+1's open, so a sell's proceeds never fund a buy of the
same reply: buys are sized against the cash on hand before this
reply's sells. Everything here is integer math in a fixed symbol
order, no clock, no environment, no randomness, so the two grading
runs produce byte-identical action logs.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYMBOLS = ("FARTCOIN", "JITOSOL", "POPCAT", "RAY", "SOL", "WETH", "WIF")
DROP_BPS = 190          # buy when the 6-hour drop is at least this deep
DROP_HOURS = 6          # lookback for the drop, in hourly bars
TAKE_BPS = 300          # take profit at +3% over the position cost
STOP_BPS = 200          # stop loss at -2% under the position cost
HOLD_MAX_BARS = 24      # give up after 24 bars even without a trigger
SIZE_BPS = 2400         # 24% of equity per new position (cap is 25%)
MAX_SLIPPAGE_BPS = 300  # reject a fill that moved this far from the close
MIN_NOTIONAL = 1000000  # 1 USDC, in quote units (the harness minimum)

closes = {s: [] for s in SYMBOLS}
opened_seq = {}  # symbol -> seq of the batch where its position appeared


def _drop_bps(hist):
    """(close_now - close_6h_ago) in bps, integer math; None if too short."""
    if len(hist) <= DROP_HOURS:
        return None
    old = hist[-1 - DROP_HOURS]
    new = hist[-1]
    return (new - old) * 10000 // old


def _pnl_bps(state, symbol):
    """The open position's PnL in bps against its cost (fees included)."""
    holding = state.positions.get(symbol)
    if holding is None or holding.cost <= 0:
        return None
    value = state.value(symbol, holding.qty)
    return (value - holding.cost) * 10000 // holding.cost


def on_hello(state):
    # hello: nothing to prepare before the first batch of bars arrives.
    return None


def on_batch(state, batch):
    # Record this batch of bars first: every symbol's latest close.
    for symbol in SYMBOLS:
        close = state.close(symbol)
        if close is not None:
            closes[symbol].append(close)
    # Track when each open position first appeared (its fill bar).
    for symbol in list(opened_seq):
        if symbol not in state.positions:
            del opened_seq[symbol]
    for symbol in state.positions:
        if symbol not in opened_seq:
            opened_seq[symbol] = state.seq

    if state.warming_up:
        # Warm-up bars build history only; orders on them are rejected.
        return []

    orders = []
    cash_left = state.cash  # sells in this reply do not fund its buys
    # 1) Exits first: take profit, stop loss, or the max hold reached.
    for symbol in SYMBOLS:
        holding = state.positions.get(symbol)
        if holding is None:
            continue
        pnl = _pnl_bps(state, symbol)
        held_bars = state.seq - opened_seq.get(symbol, state.seq)
        if pnl is not None and (
            pnl >= TAKE_BPS or pnl <= -STOP_BPS or held_bars >= HOLD_MAX_BARS
        ):
            orders.append(
                {
                    "side": "sell",
                    "symbol": symbol,
                    "qty": holding.qty,
                    "max_slippage_bps": MAX_SLIPPAGE_BPS,
                }
            )
    # 2) Entries: a dip of at least 190 bps over the last 6 hourly bars.
    for symbol in SYMBOLS:
        if symbol in state.positions:
            continue
        drop = _drop_bps(closes[symbol])
        if drop is None or drop > -DROP_BPS:
            continue
        target = state.equity * SIZE_BPS // 10000
        spend = min(target, state.weight_room(symbol), cash_left)
        if spend < MIN_NOTIONAL:
            continue
        orders.append(
            {
                "side": "buy",
                "symbol": symbol,
                "notional_quote_units": spend,
                "max_slippage_bps": MAX_SLIPPAGE_BPS,
            }
        )
        cash_left -= spend
    return orders


makefun_bars.run(on_batch, on_hello=on_hello)
