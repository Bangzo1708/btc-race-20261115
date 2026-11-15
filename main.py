"""Volatility-adaptive dip-and-trend bot for cbBTC (agent-fun/bars-replay/v1).

Strategy (designed for this competition, distinct from every kit baseline):
  * Anchor: the 240-bar (4h) simple moving average of 1-minute closes. It is the
    slow mean the price keeps coming back to.
  * Volatility gauge: Wilder's ATR(14) of the 1-minute true ranges, read in
    basis points of the price. A dip only counts when it is large *for current
    conditions*: at least max(80 bps, 5 x ATR) below the anchor.
  * Dip entry (mean reversion): the close sits that far below the anchor and
    the last two closes are rising again (the fall is stabilising). Buy the
    dislocation, full size. It exits when the price recovers to the anchor.
  * Trend entry (momentum): the 15-minute aggregated EMA(2) crosses above
    EMA(6) while the close is above the 240-bar anchor, i.e. an uptrend is
    starting from above the mean. Buy the breakout, full size. It exits when
    the aggregated fast EMA turns back below the slow one.
  * Exits, whole position: +200 bps take-profit from the entry close, -150 bps
    stop-loss, or 240 bars held, for either leg.

Costs matter: a full round trip pays ~26 bps in fees, slippage and impact, so
entries wait for dislocations / confirmed turns of 80+ bps instead of chasing
every 1-minute wiggle. Everything is deterministic: indicators are plain
float64 recurrences over the bars in order, no clock, no network, no files,
no randomness.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYMBOL = "CBBTC"

# --- parameters (chosen on the published dev window, kept in the flat region
# --- of the sensitivity grid rather than at a sharp optimum) ---
ANCHOR_BARS = 240        # 4h simple moving average of closes
ATR_BARS = 14            # Wilder ATR lookback
DIP_FLOOR_BPS = 200      # smallest dislocation that counts, in bps
DIP_ATR_MULT = 5         # ...or this many ATRs, whichever is larger
AGG_BARS = 15            # minutes per aggregated bar for the trend EMAs
EMA_FAST = 2             # fast EMA span on aggregated bars
EMA_SLOW = 6             # slow EMA span on aggregated bars
TAKE_PROFIT_BPS = 200
STOP_LOSS_BPS = 150
MAX_HOLD_BARS = 240
MAX_SLIPPAGE_BPS = 100   # 1% past the close the order was decided on


class Bot:
    def __init__(self):
        self.closes = []          # int closes, price_scale units
        self.highs = []
        self.lows = []
        self.anchor_sum = 0       # rolling sum of the last ANCHOR_BARS closes
        self.atr = None           # Wilder ATR, price units (float)
        self.atr_seed = []        # first ATR_BARS true ranges, before seeding
        self.agg_closes = []      # closes of completed aggregated bars
        self.ema_fast = None
        self.ema_slow = None
        self.prev_up = False      # fast EMA above slow EMA on the last bar
        self.in_position = False
        self.entry_close = 0
        self.leg = None           # "dip" or "trend"
        self.held_bars = 0

    # -- indicator updates, one new bar -----------------------------------
    def _update(self, bar):
        close = int(bar["c"])
        high = int(bar["h"])
        low = int(bar["l"])
        prev_close = self.closes[-1] if self.closes else close

        # True range and Wilder ATR.
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        if self.atr is None:
            self.atr_seed.append(tr)
            if len(self.atr_seed) >= ATR_BARS:
                self.atr = sum(self.atr_seed) / float(ATR_BARS)
        else:
            self.atr = (self.atr * (ATR_BARS - 1) + tr) / float(ATR_BARS)

        self.closes.append(close)
        self.highs.append(high)
        self.lows.append(low)
        self.anchor_sum += close
        if len(self.closes) > ANCHOR_BARS:
            self.anchor_sum -= self.closes[-ANCHOR_BARS - 1]

        # Aggregated bar: a block of AGG_BARS closes ends on this bar.
        if len(self.closes) % AGG_BARS == 0:
            self._close_agg_bar(close)

    def _close_agg_bar(self, close):
        self.agg_closes.append(close)
        if self.ema_fast is None:
            self.ema_fast = float(close)
            self.ema_slow = float(close)
        else:
            kf = 2.0 / (EMA_FAST + 1)
            ks = 2.0 / (EMA_SLOW + 1)
            self.ema_fast = close * kf + self.ema_fast * (1.0 - kf)
            self.ema_slow = close * ks + self.ema_slow * (1.0 - ks)

    # -- indicator reads ---------------------------------------------------
    def _anchor(self):
        if len(self.closes) < ANCHOR_BARS:
            return None
        return self.anchor_sum / float(ANCHOR_BARS)

    def _trend_up(self):
        if self.ema_fast is None:
            return False
        return self.ema_fast > self.ema_slow

    def _dip_threshold_bps(self, close):
        if self.atr is None:
            return float(DIP_FLOOR_BPS)
        atr_bps = self.atr / float(close) * 10000.0
        return max(float(DIP_FLOOR_BPS), DIP_ATR_MULT * atr_bps)

    # -- decision ----------------------------------------------------------
    def on_batch(self, state, batch):
        if state.warming_up:
            return []
        bar = None
        for b in batch.get("bars", []):
            if b.get("symbol") == SYMBOL:
                bar = b
                break
        if bar is None:
            return []  # no bar for CBBTC this minute: decide nothing
        self._update(bar)

        close = self.closes[-1]
        anchor = self._anchor()
        if anchor is None:
            return []
        up = self._trend_up()
        held = state.positions.get(SYMBOL)

        if held is None:
            orders = self._maybe_enter(state, close, anchor, up)
        else:
            orders = self._maybe_exit(state, close, anchor, up, held)
        self.prev_up = up
        return orders

    def _maybe_enter(self, state, close, anchor, up):
        # Dip leg: deep dislocation below the anchor, stabilising. No trend
        # filter here: when the price is far below its 4h mean the 15-minute
        # trend is down by construction, so requiring it up would almost never
        # fire; the stabilising closes are the confirmation instead.
        if len(self.closes) >= 3:
            thresh = self._dip_threshold_bps(close)
            deep = close <= anchor * (1.0 - thresh / 10000.0)
            stabilising = close > self.closes[-2] and self.closes[-2] >= self.closes[-3]
            if deep and stabilising:
                return self._buy(state, "dip", close)
        # Trend leg: aggregated fast EMA just crossed above the slow one
        # while the price sits above its slow anchor.
        if up and not self.prev_up and close > anchor:
            return self._buy(state, "trend", close)
        return []

    def _buy(self, state, leg, close):
        room = state.weight_room(SYMBOL)
        amount = state.cash if state.cash < room else room
        if amount < int(state.hello["fees"]["min_notional_quote_units"]):
            return []
        self.in_position = True
        self.entry_close = close
        self.leg = leg
        self.held_bars = 0
        return [{"side": "buy", "symbol": SYMBOL,
                 "notional_quote_units": amount,
                 "max_slippage_bps": MAX_SLIPPAGE_BPS}]

    def _maybe_exit(self, state, close, anchor, up, held):
        self.held_bars += 1
        entry = self.entry_close
        take = entry * (10000 + TAKE_PROFIT_BPS) / 10000.0
        stop = entry * (10000 - STOP_LOSS_BPS) / 10000.0
        reason = None
        if close >= take:
            reason = "take-profit"
        elif close <= stop:
            reason = "stop-loss"
        elif self.leg == "trend" and not up:
            # Only trend entries exit on the trend turning down: a dip entry
            # is bought while the short-term trend is down, so this rule
            # would dump it on the next bar.
            reason = "trend turned down"
        elif self.leg == "dip" and close >= anchor:
            reason = "recovered to anchor"
        elif self.held_bars >= MAX_HOLD_BARS:
            reason = "max hold"
        if reason is None:
            return []
        self.in_position = False
        self.leg = None
        return [{"side": "sell", "symbol": SYMBOL, "qty": held.qty,
                 "max_slippage_bps": MAX_SLIPPAGE_BPS}]


BOT = Bot()


def on_batch(state, batch):
    return BOT.on_batch(state, batch)


makefun_bars.run(on_batch)
