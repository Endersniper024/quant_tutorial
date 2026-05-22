"""策略基类。

一个策略只需要回答一个问题：**看到当前这根 K 线（及之前的历史），我要不要下单？**

设计要点（务必理解，这是不亏钱的前提）：
    1. 策略在 `on_bar(ctx)` 里只能看到「截止当前 bar」的数据（ctx.history 已经
       帮你裁好），看不到未来。这样就不会写出「用明天的价格做今天的决策」这种
       自欺欺人的代码（即所谓"未来函数 / 前视偏差"）。
    2. 你下的单不会在当前 bar 立刻成交，而是在**下一根 bar 的开盘价**成交。
       因为现实里你看到今天收盘价时，今天已经收盘了，根本买不进。
       这个延迟由回测引擎自动处理，你只管下单即可。

下单只需调用 ctx 上的方法（见 quant/backtest/engine.py 的 Context）：
    ctx.buy(shares)        买入指定股数（会自动取整到 100 股）
    ctx.buy_pct(pct)       用当前总资产的 pct 比例买入（如 0.95）
    ctx.sell(shares)       卖出指定股数
    ctx.sell_all()         卖出全部可卖持仓
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class Strategy(ABC):
    """所有策略的基类。子类至少实现 on_bar。"""

    def on_start(self, ctx) -> None:  # noqa: B027  (允许空实现)
        """回测开始时调用一次，可用于初始化状态。"""

    @abstractmethod
    def on_bar(self, ctx) -> None:
        """每根 K 线调用一次，在这里读取 ctx 数据并决定是否下单。"""

    def on_finish(self, ctx) -> None:  # noqa: B027
        """回测结束时调用一次，可用于收尾。"""
