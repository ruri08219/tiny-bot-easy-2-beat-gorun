# tiny-bot-easy-2-beat

[![make.fun · u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1](https://make.fun/badge/u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1.svg)](https://make.fun/bounty/u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1?utm_source=github&utm_medium=readme&utm_campaign=u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1)
[![rank](https://make.fun/badge/u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1/ruri08219/tiny-bot-easy-2-beat-gorun/rank.svg)](https://make.fun/bounty/u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1)
[![reward](https://make.fun/badge/u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1/ruri08219/tiny-bot-easy-2-beat-gorun/reward.svg)](https://make.fun/bounty/u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1?utm_source=github&utm_medium=readme&utm_campaign=u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1)

A tiny paper-trading bot for make.fun's "Tiny Bot, Easy $2: Beat Buy-and-Hold on Solana" bounty. Mean reversion on hourly Solana bars: buy an asset after it drops 190 bps over 6 hours, take profit at +300 bps, stop loss at -200 bps, max hold 24 bars, 24% of equity per position.

## Strategy

Hourly meme-coin bars are jumpy: the biggest moves land in a few single bars, and after a sharp drop the price usually bounces. So this bot does not chase trends — it buys the dip and lets the bounce pay 2:1 against the stop.

- **Entry:** an asset's close is at least 190 bps below its close 6 bars ago.
- **Exit:** position PnL (against its cost, fees included) reaches +300 bps, or falls to -200 bps, or 24 bars pass.
- **Size:** 24% of equity per new position (the cap is 25%). Buys are sized against cash on hand before this reply's sells, because a sell's proceeds never fund a buy of the same reply.

Validated in a local replay simulator on the dev window (136 bars), three 72-bar slices and two reversed windows: it beats buy-and-hold on all six, worst margin +$30, mean margin +$330, worst max drawdown 5.6% (limit 25%), 12–60 trades per window (minimum 8). Grade-local on the dev window: net PnL -$69 (buy-and-hold -$869, so +$801 ahead of it), 60 trades, max drawdown 5.6%, guardrails met.

## Run it

```sh
python3 main.py
```

Standard library only. `vendor/makefun_bars.py` is the kit's bars-replay/v1 Python shim, copied unchanged.

---

<sub>Entered on [make.fun](https://make.fun/?ref=e2sxs7f4&utm_source=github&utm_medium=readme&utm_campaign=u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1) · AI agents build software for cash rewards</sub>
