"""Tiny dip-buy bot for the make.fun bars-replay/v1 harness.

Strategy (mean reversion on hourly Solana bars, validated on the dev
window, three 72-bar slices and two reversed windows in a local replay
simulator): buy an asset after it drops >= 190 bps over the last 6
hourly bars, hold at most 24 bars, take profit at +300 bps, stop loss
at -200 bps. The exits are measured against the close that triggered
the buy (the decision close), exactly as the simulator that validated
this strategy measures them; the fill price, slippage and fees are
already inside the net PnL the grader reports. Each buy is 24% of
equity (the weight cap is 25%).

hello: the harness greets the bot once; every batch of bars after that
carries the fills and each symbol's latest close, and the bot answers
that batch with its orders for the next bar. Orders decided on bar k
fill at bar k+1's open, so a sell's proceeds never fund a buy of the
same reply: buys are sized against the cash on hand before this
reply's sells. A batch with no bar for a symbol carries that symbol's
last recorded close forward, so the 6-bar drop lookback stays aligned
with the bar clock. Everything here is integer math in a fixed symbol
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
TAKE_BPS = 300          # take profit at +3% over the decision close
STOP_BPS = 200          # stop loss at -2% under the decision close
HOLD_MAX_BARS = 24      # give up after 24 bars even without a trigger
SIZE_BPS = 2400         # 24% of equity per new position (cap is 25%)
MAX_SLIPPAGE_BPS = 300  # reject a fill that moved this far from the close
MIN_NOTIONAL = 1000000  # 1 USDC, in quote units (the harness minimum)

closes = {s: [] for s in SYMBOLS}
entries = {}  # symbol -> (decision close, decision seq) recorded when a buy is ordered


def _drop_bps(hist):
    """(close_now - close_6h_ago) in bps, integer math; None if too short."""
    if len(hist) <= DROP_HOURS:
        return None
    old = hist[-1 - DROP_HOURS]
    new = hist[-1]
    return (new - old) * 10000 // old


def _chg_bps(now, ref):
    """(now - ref) in bps, integer math."""
    return (now - ref) * 10000 // ref


def on_hello(state):
    # hello: nothing to prepare before the first batch of bars arrives.
    return None


def on_batch(state, batch):
    # Record this batch of bars first: every symbol's latest close.
    # A symbol with no bar in this batch carries its last recorded
    # close forward, so its history stays one entry per bar and the
    # 6-bar drop lookback stays aligned with the bar clock; skipping
    # the append would silently shorten that symbol's history and
    # compare closes 7+ bars apart.
    for symbol in SYMBOLS:
        close = state.close(symbol)
        if close is None and closes[symbol]:
            close = closes[symbol][-1]
        if close is not None:
            closes[symbol].append(close)
    # Drop entries whose buy never filled: a fill lands in the next
    # batch's account, so a symbol with no position one bar after its
    # decision had its order rejected.
    for symbol in list(entries):
        if symbol not in state.positions and state.seq > entries[symbol][1] + 1:
            del entries[symbol]

    if state.warming_up:
        # Warm-up bars build history only; orders on them are rejected.
        return []

    orders = []
    cash_left = state.cash  # sells in this reply do not fund its buys
    # 1) Exits first: take profit, stop loss, or the max hold reached.
    # The change is measured from the decision close, not the fill cost:
    # measuring from the cost moves both triggers by the fill's slippage
    # and fees (stops fire ~1% early, take-profits ~1% late) and the
    # extra churn eats the edge the simulator validated.
    for symbol in SYMBOLS:
        holding = state.positions.get(symbol)
        if holding is None:
            continue
        ref = entries.get(symbol)
        if ref is None:
            # A position with no recorded decision (should not happen):
            # fall back to its cost so the stops still protect it.
            value = state.value(symbol, holding.qty)
            chg = (value - holding.cost) * 10000 // holding.cost if holding.cost > 0 else None
            held_bars = 0
        else:
            # Current close as the bot sees it: the last recorded
            # close, carried forward above if this batch had no bar
            # for the symbol, so exits still evaluate on a missing bar.
            close = closes[symbol][-1] if closes[symbol] else None
            chg = _chg_bps(close, ref[0]) if close is not None else None
            held_bars = state.seq - ref[1]
        if chg is not None and (
            chg >= TAKE_BPS or chg <= -STOP_BPS or held_bars >= HOLD_MAX_BARS
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
        entries[symbol] = (closes[symbol][-1], state.seq)
        cash_left -= spend
    # Defensive cap: the harness rejects the whole reply if it carries
    # more than max_orders_per_bar orders, so never emit more than
    # that. Exits are appended first, so a trim here would only ever
    # drop entries. With 7 symbols the most this bot can emit is 14,
    # so the cap never binds on this competition — it only guards
    # against a future symbol list growing past it.
    cap = state.hello["caps"].get("max_orders_per_bar", 16)
    return orders[:cap]


makefun_bars.run(on_batch, on_hello=on_hello)
