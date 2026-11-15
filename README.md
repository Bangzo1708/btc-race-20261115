# BTC Race Bot — Volatility-Adaptive Dip-and-Trend

A trading bot for the make.fun BTC race competition. It trades BTC perpetuals
with a volatility-adaptive dip-and-trend strategy: it buys dips when short-term
momentum turns up after a pullback, rides the trend with a trailing stop, and
scales position size down as realized volatility rises. Risk is capped per
trade and the bot flattens exposure on regime shifts.

- Owner: Bangzo1708
- Referral code: dkj7ja9h

## Run

```
python main.py
```

`main.py` is the entrypoint; `vendor/makefun_bars.py` provides the market-data
helpers used by the bot.
