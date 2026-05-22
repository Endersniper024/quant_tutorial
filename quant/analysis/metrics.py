"""绩效评估：把一条资金曲线和一串交易，浓缩成几个关键数字。

光看"赚了多少"是不够的，必须看"承担了多大风险、过程多颠簸"。常用指标：

- 累计收益率：整段时间总共赚了百分之多少。
- 年化收益率：把累计收益折算成"每年"的速度，方便和别的策略/存款利率比。
- 年化波动率：收益的颠簸程度，越大越刺激（也越危险）。
- 夏普比率：每承担一单位波动，换来多少超额收益。>1 还行，>2 不错（回测里要警惕过拟合）。
- 最大回撤：从某个高点跌到之后最低点的最大跌幅，衡量"最难熬的时候有多惨"。
- 胜率：完整买卖回合里赚钱的比例。注意：高胜率不等于赚钱（可能赚小亏大）。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252  # A 股一年约 242~250 个交易日，惯例取 252


def compute_metrics(result) -> dict:
    """从 BacktestResult 计算指标字典。"""
    equity = result.equity["total_value"]
    daily_ret = equity.pct_change().dropna()
    n = len(equity)

    total_return = equity.iloc[-1] / equity.iloc[0] - 1.0

    # 年化：按交易日数折算
    if n > 1:
        annual_return = (1 + total_return) ** (TRADING_DAYS / n) - 1
    else:
        annual_return = 0.0

    annual_vol = daily_ret.std() * np.sqrt(TRADING_DAYS) if len(daily_ret) else 0.0

    if daily_ret.std() > 0:
        sharpe = daily_ret.mean() / daily_ret.std() * np.sqrt(TRADING_DAYS)
    else:
        sharpe = 0.0

    max_dd = _max_drawdown(equity)

    round_trips, win_rate = _win_rate(result.trades)

    return {
        "起始资金": result.initial_cash,
        "期末资金": float(equity.iloc[-1]),
        "累计收益率": float(total_return),
        "年化收益率": float(annual_return),
        "年化波动率": float(annual_vol),
        "夏普比率": float(sharpe),
        "最大回撤": float(max_dd),
        "交易回合数": round_trips,
        "胜率": float(win_rate),
    }


def _max_drawdown(equity: pd.Series) -> float:
    """最大回撤（负数，如 -0.23 表示最大跌了 23%）。"""
    running_max = equity.cummax()
    drawdown = equity / running_max - 1.0
    return drawdown.min()


def _win_rate(trades) -> tuple[int, float]:
    """用平均成本法回放交易，统计完整买卖回合的胜率。"""
    position = 0
    cost = 0.0
    realized = []
    for t in trades:
        if t.side == "buy":
            cost = (cost * position + t.amount + t.fee) / (position + t.shares)
            position += t.shares
        else:  # sell
            pnl = (t.price - cost) * t.shares - t.fee
            realized.append(pnl)
            position -= t.shares
            if position == 0:
                cost = 0.0
    if not realized:
        return 0, 0.0
    wins = sum(1 for p in realized if p > 0)
    return len(realized), wins / len(realized)


def format_metrics(metrics: dict) -> str:
    """把指标字典格式化成易读的多行文本。"""
    pct = {"累计收益率", "年化收益率", "年化波动率", "最大回撤", "胜率"}
    money = {"起始资金", "期末资金"}
    lines = []
    for k, v in metrics.items():
        if k in pct:
            lines.append(f"{k:<8}: {v:+.2%}")
        elif k in money:
            lines.append(f"{k:<8}: {v:,.2f} 元")
        elif k == "夏普比率":
            lines.append(f"{k:<8}: {v:.2f}")
        else:
            lines.append(f"{k:<8}: {v}")
    return "\n".join(lines)
