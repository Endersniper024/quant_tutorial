"""账户：记录现金、持仓、成本，并支持 A 股的 T+1 规则。

为了让新手看得清楚，这里只支持**单只股票**的账户。
多标的组合是进阶内容（见教程 07）。

T+1 怎么实现？
    A 股今天买入的股票，当天不能卖，要到下一个交易日才能卖。
    我们用两个数字区分：
        volume     ——总持仓股数（含今天刚买的）
        available  ——当前可卖股数（不含今天买的）
    每天收盘后调用 settle()，把今天买的"解冻"为可卖（available = volume）。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Account:
    cash: float                       # 可用现金
    volume: int = 0                   # 总持仓股数
    available: int = 0                # 可卖股数（T+1：今日买入不可卖）
    cost: float = 0.0                 # 持仓平均成本价

    # 每日权益快照，回测结束后用于画资金曲线 / 算指标
    equity_curve: list[dict] = field(default_factory=list)

    def market_value(self, price: float) -> float:
        """当前持仓市值。"""
        return self.volume * price

    def total_value(self, price: float) -> float:
        """总资产 = 现金 + 持仓市值。"""
        return self.cash + self.market_value(price)

    def on_buy_filled(self, price: float, shares: int, fee: float) -> None:
        """买入成交后更新账户。新买入的股数当天不计入 available（T+1）。"""
        spend = price * shares
        # 重新计算加权平均成本（把手续费也摊进成本，更贴近真实持仓成本）
        old_cost_total = self.cost * self.volume
        self.cost = (old_cost_total + spend + fee) / (self.volume + shares)
        self.cash -= spend + fee
        self.volume += shares
        # available 不变：今天买的明天才能卖

    def on_sell_filled(self, price: float, shares: int, fee: float) -> None:
        """卖出成交后更新账户。"""
        self.cash += price * shares - fee
        self.volume -= shares
        self.available -= shares
        if self.volume == 0:
            self.cost = 0.0

    def settle(self, date, price: float) -> None:
        """每日收盘结算：解冻 T+1 持仓，并记录当日权益快照。"""
        self.available = self.volume
        self.equity_curve.append(
            {
                "date": date,
                "cash": self.cash,
                "volume": self.volume,
                "price": price,
                "market_value": self.market_value(price),
                "total_value": self.total_value(price),
            }
        )
