"""事件驱动回测引擎（单只股票）。

核心循环（理解了这段就理解了回测的本质）：

    对每一根 K 线 i：
      1. 先用「上一根 bar 下的单」在**本根 bar 的开盘价**撮合成交。
         （这就是订单延迟一根 bar 的地方，防止用收盘价当场成交的作弊。）
      2. 把数据切到「截止本根 bar 收盘」交给策略，策略据此决定要不要下新单
         （新单进入待成交队列，等下一根 bar 开盘再撮合）。
      3. 用本根 bar 的收盘价结算当日权益，并解冻 T+1 持仓。

为什么按日逐根推进，而不是用向量化一次算完？
    因为它和真实交易的时间顺序一致：你永远只能基于「已经发生的」做决策。
    向量化更快，但新手很容易不小心引用到未来数据。事件驱动更慢，但更直观、更安全。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import pandas as pd

from ..strategy.base import Strategy
from .account import Account
from .broker import Broker, BrokerConfig, Order, Trade


class Context:
    """传给策略的运行时上下文：既能读当前行情/持仓，又能下单。"""

    def __init__(self, engine: "BacktestEngine"):
        self._engine = engine
        self.date = None              # 当前 bar 日期
        self.bar: pd.Series | None = None   # 当前 bar 的 OHLCV
        self.history: pd.DataFrame | None = None  # 截止当前 bar 的全部历史

    # ---- 行情 / 持仓只读属性 ----
    @property
    def close(self) -> float:
        return float(self.bar["close"])

    @property
    def cash(self) -> float:
        return self._engine.account.cash

    @property
    def position(self) -> int:
        return self._engine.account.volume

    @property
    def available(self) -> int:
        return self._engine.account.available

    # ---- 下单接口（只是排队，下一根 bar 开盘成交）----
    def buy(self, shares: int) -> None:
        shares = (int(shares) // 100) * 100
        if shares > 0:
            self._engine.pending.append(Order("buy", shares))

    def buy_pct(self, pct: float) -> None:
        """用当前总资产的 pct 比例买入（以当前收盘价估算股数）。"""
        total = self._engine.account.total_value(self.close)
        target_amount = total * pct
        shares = math.floor(target_amount / self.close / 100) * 100
        self.buy(shares)

    def sell(self, shares: int) -> None:
        shares = (int(shares) // 100) * 100
        if shares > 0:
            self._engine.pending.append(Order("sell", shares))

    def sell_all(self) -> None:
        self.sell(self._engine.account.available)


@dataclass
class BacktestResult:
    symbol: str
    initial_cash: float
    equity: pd.DataFrame            # 每日权益曲线
    trades: list[Trade] = field(default_factory=list)

    @property
    def trades_df(self) -> pd.DataFrame:
        if not self.trades:
            return pd.DataFrame(
                columns=["date", "side", "price", "shares", "fee", "amount"]
            )
        return pd.DataFrame([t.__dict__ for t in self.trades]).set_index("date")


class BacktestEngine:
    def __init__(
        self,
        strategy: Strategy,
        initial_cash: float = 100_000.0,
        broker_config: BrokerConfig | None = None,
    ):
        self.strategy = strategy
        self.initial_cash = initial_cash
        self.account = Account(cash=initial_cash)
        self.broker = Broker(broker_config)
        self.pending: list[Order] = []
        self.trades: list[Trade] = []

    def run(self, data: pd.DataFrame, symbol: str = "") -> BacktestResult:
        """在单只股票的日线数据上跑回测。

        data 需含 open/high/low/close/volume 列，索引为升序日期。
        """
        if data.empty:
            raise ValueError("回测数据为空")
        data = data.sort_index()
        ctx = Context(self)

        self.strategy.on_start(ctx)

        closes = data["close"].to_numpy()
        opens = data["open"].to_numpy()
        dates = data.index

        for i in range(len(data)):
            date = dates[i]

            # 1) 撮合上一根 bar 排队的订单，按本根 bar 开盘价成交
            if self.pending:
                prev_close = closes[i - 1] if i > 0 else opens[i]
                for order in self.pending:
                    trade = self.broker.execute(
                        order, self.account, opens[i], prev_close, date
                    )
                    if trade is not None:
                        self.trades.append(trade)
                self.pending.clear()

            # 2) 把数据切到「截止当前 bar」，交给策略决策
            ctx.date = date
            ctx.bar = data.iloc[i]
            ctx.history = data.iloc[: i + 1]
            self.strategy.on_bar(ctx)

            # 3) 用收盘价结算当日权益，并解冻 T+1 持仓
            self.account.settle(date, closes[i])

        self.strategy.on_finish(ctx)

        equity = pd.DataFrame(self.account.equity_curve).set_index("date")
        return BacktestResult(
            symbol=symbol,
            initial_cash=self.initial_cash,
            equity=equity,
            trades=self.trades,
        )
