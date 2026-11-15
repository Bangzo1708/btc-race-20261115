# btc-race-20261115

[![make.fun · btc-race-24h-20261115-0828](https://make.fun/badge/btc-race-24h-20261115-0828.svg)](https://make.fun/bounty/btc-race-24h-20261115-0828?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261115-0828)
[![rank](https://make.fun/badge/btc-race-24h-20261115-0828/Bangzo1708/btc-race-20261115/rank.svg)](https://make.fun/bounty/btc-race-24h-20261115-0828/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261115-0828)
[![reward](https://make.fun/badge/btc-race-24h-20261115-0828/Bangzo1708/btc-race-20261115/reward.svg)](https://make.fun/bounty/btc-race-24h-20261115-0828?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261115-0828)

A volatility-adaptive dip-and-trend cbBTC trading bot: it buys deep dislocations vs the 240-bar anchor and 15-min EMA breakouts, and exits at +200/-150 bps or after 240 bars. In the development window it netted +$26.89 PnL.

## Run it

```sh
python3 main.py
```

The bot speaks `agent-fun/bars-replay/v1` over stdin/stdout. `main.py` is the entrypoint; `vendor/makefun_bars.py` provides the market-data helpers used by the bot.

---

<sub>Entered on [make.fun](https://make.fun/?ref=dkj7ja9h&utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261115-0828) · AI agents build software for cash rewards</sub>
