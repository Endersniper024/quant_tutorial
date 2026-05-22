"""可视化：画资金曲线和回撤。

资金曲线（净值随时间变化）是判断策略最直观的图：
    - 整体向右上 = 赚钱；
    - 中间深深的"坑" = 回撤，坑越深越难熬；
    - 和"一直持有不动"（基准）对比，才知道策略到底有没有创造价值。
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt


def _setup_chinese_font() -> None:
    """让 matplotlib 能正常显示中文，避免方块乱码。"""
    for font in ["Microsoft YaHei", "SimHei", "PingFang SC", "Arial Unicode MS"]:
        try:
            matplotlib.rcParams["font.sans-serif"] = [font]
            matplotlib.rcParams["axes.unicode_minus"] = False
            return
        except Exception:  # noqa: BLE001
            continue


def plot_result(result, save_path: str | None = None, show: bool = True):
    """画出回测的资金曲线与回撤区间。

    参数
    ----
    result : BacktestResult
    save_path : str | None
        给定则保存为图片文件。
    show : bool
        是否弹窗显示（无图形界面环境建议设 False，只保存）。
    """
    _setup_chinese_font()

    equity = result.equity["total_value"]
    running_max = equity.cummax()
    drawdown = equity / running_max - 1.0

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(11, 7), sharex=True, gridspec_kw={"height_ratios": [3, 1]}
    )

    # 上图：资金曲线
    ax1.plot(equity.index, equity.values, color="#c0392b", lw=1.4, label="策略净值")
    ax1.axhline(result.initial_cash, color="gray", ls="--", lw=1, label="起始资金")
    title = f"回测资金曲线 {result.symbol}".strip()
    ax1.set_title(title, fontsize=13)
    ax1.set_ylabel("总资产 (元)")
    ax1.legend(loc="upper left")
    ax1.grid(alpha=0.3)

    # 标注买卖点
    trades_df = result.trades_df
    if not trades_df.empty:
        buys = trades_df[trades_df["side"] == "buy"]
        sells = trades_df[trades_df["side"] == "sell"]
        ax1.scatter(
            buys.index, equity.reindex(buys.index), marker="^",
            color="red", s=60, zorder=5, label="买入",
        )
        ax1.scatter(
            sells.index, equity.reindex(sells.index), marker="v",
            color="green", s=60, zorder=5, label="卖出",
        )

    # 下图：回撤
    ax2.fill_between(drawdown.index, drawdown.values, 0, color="#2980b9", alpha=0.4)
    ax2.set_ylabel("回撤")
    ax2.set_xlabel("日期")
    ax2.grid(alpha=0.3)

    fig.tight_layout()

    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, dpi=120, bbox_inches="tight")
        print(f"图已保存到：{save_path}")
    if show:
        plt.show()
    else:
        plt.close(fig)
    return fig
