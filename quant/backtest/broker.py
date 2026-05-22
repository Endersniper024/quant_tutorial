"""撮合器：把策略下的订单，按 A 股规则在下一根 K 线开盘价成交。

A 股有几条和美股/加密很不一样的规则，回测必须考虑，否则结果会虚高：

1. 涨跌停：相对前一交易日收盘价，普通股票当日涨跌幅不能超过 ±10%
   （创业板/科创板 20%、ST 股 5%——这里默认 10%，可配置）。
   一字涨停时你根本买不进，一字跌停时你也卖不出。
2. 手续费：
   - 佣金：买卖双向收取，按成交额比例（常见万 2.5~万 3），单笔最低 5 元。
   - 印花税：只在**卖出**时收，目前为成交额的 0.05%（2023 年 8 月起减半）。
3. 整手：买入必须是 100 股的整数倍（卖出可以不足 100，这里简化为也按整手卖）。
4. 滑点：真实成交价往往比理想价差一点，用一个比例近似模拟。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .account import Account

_EPS = 1e-6


@dataclass
class BrokerConfig:
    commission_rate: float = 0.0003   # 佣金费率（万 3）
    min_commission: float = 5.0       # 单笔最低佣金（元）
    stamp_tax_rate: float = 0.0005    # 印花税（仅卖出，0.05%）
    slippage: float = 0.0             # 滑点比例，0 表示不模拟
    limit_pct: float = 0.10           # 涨跌停幅度（普通股 10%）


@dataclass
class Order:
    side: str       # "buy" 或 "sell"
    shares: int     # 期望成交股数（撮合时可能因资金/持仓/涨跌停被调整）


@dataclass
class Trade:
    date: object
    side: str
    price: float
    shares: int
    fee: float
    amount: float   # 成交金额（不含费用）


class Broker:
    def __init__(self, config: BrokerConfig | None = None):
        self.config = config or BrokerConfig()

    # ---- 费用计算 ----
    def _buy_fee(self, amount: float) -> float:
        return max(amount * self.config.commission_rate, self.config.min_commission)

    def _sell_fee(self, amount: float) -> float:
        commission = max(amount * self.config.commission_rate, self.config.min_commission)
        stamp = amount * self.config.stamp_tax_rate
        return commission + stamp

    # ---- 撮合 ----
    def execute(
        self,
        order: Order,
        account: Account,
        open_price: float,
        prev_close: float,
        date,
    ) -> Trade | None:
        """在 open_price 撮合一笔订单，返回成交记录；无法成交则返回 None。"""
        cfg = self.config
        limit_up = round(prev_close * (1 + cfg.limit_pct), 2)
        limit_down = round(prev_close * (1 - cfg.limit_pct), 2)

        if order.side == "buy":
            # 一字涨停（开盘价已到涨停）→ 买不进
            if open_price >= limit_up - _EPS:
                return None
            fill_price = open_price * (1 + cfg.slippage)
            shares = self._affordable_shares(account.cash, fill_price, order.shares)
            if shares <= 0:
                return None
            amount = fill_price * shares
            fee = self._buy_fee(amount)
            account.on_buy_filled(fill_price, shares, fee)
            return Trade(date, "buy", fill_price, shares, fee, amount)

        if order.side == "sell":
            # 一字跌停 → 卖不出
            if open_price <= limit_down + _EPS:
                return None
            shares = min(order.shares, account.available)
            shares = (shares // 100) * 100  # 简化：按整手卖
            if shares <= 0:
                return None
            fill_price = open_price * (1 - cfg.slippage)
            amount = fill_price * shares
            fee = self._sell_fee(amount)
            account.on_sell_filled(fill_price, shares, fee)
            return Trade(date, "sell", fill_price, shares, fee, amount)

        raise ValueError(f"未知订单方向：{order.side}")

    def _affordable_shares(self, cash: float, fill_price: float, want: int) -> int:
        """在现金约束下，能买的最大整手股数（不超过期望股数）。"""
        want = (want // 100) * 100
        # 从期望股数往下找，直到现金足够覆盖「成交额 + 佣金」
        shares = want
        while shares > 0:
            amount = fill_price * shares
            if amount + self._buy_fee(amount) <= cash + _EPS:
                return shares
            shares -= 100
        return 0
