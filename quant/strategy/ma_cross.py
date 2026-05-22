"""双均线交叉策略（最经典的入门策略）。

思路：
    - 计算一条"快线"（短周期均线，如 5 日）和一条"慢线"（长周期均线，如 20 日）。
    - 快线上穿慢线 = "金叉"，代表近期走强 → 买入。
    - 快线下穿慢线 = "死叉"，代表近期走弱 → 清仓。

注意：这只是教学示例，不是能赚钱的策略。趋势震荡时双均线会频繁假信号、来回挨打。
它的价值在于让你跑通「指标 → 信号 → 下单」的完整链路。
"""

from __future__ import annotations

from .base import Strategy


class MaCrossStrategy(Strategy):
    def __init__(self, fast: int = 5, slow: int = 20, buy_pct: float = 0.95):
        if fast >= slow:
            raise ValueError("快线周期必须小于慢线周期")
        self.fast = fast
        self.slow = slow
        self.buy_pct = buy_pct

    def on_bar(self, ctx) -> None:
        closes = ctx.history["close"]

        # 数据还不够算出慢线 + 上一根，直接跳过（这正是"只用历史"的体现）
        if len(closes) < self.slow + 1:
            return

        fast_ma = closes.rolling(self.fast).mean()
        slow_ma = closes.rolling(self.slow).mean()

        # 用最近两根判断"穿越"：昨天 fast 在 slow 下方/上方，今天反过来
        fast_prev, fast_now = fast_ma.iloc[-2], fast_ma.iloc[-1]
        slow_prev, slow_now = slow_ma.iloc[-2], slow_ma.iloc[-1]

        golden_cross = fast_prev <= slow_prev and fast_now > slow_now
        death_cross = fast_prev >= slow_prev and fast_now < slow_now

        if golden_cross and ctx.position == 0:
            ctx.buy_pct(self.buy_pct)
        elif death_cross and ctx.available > 0:
            ctx.sell_all()
