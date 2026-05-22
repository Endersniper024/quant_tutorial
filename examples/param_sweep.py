"""参数扫描：遍历双均线的 (fast, slow) 组合，把"参数 → 表现"的曲面画出来。

目的不是帮你"找到最优参数"，恰恰相反——是让你**亲眼看到这个曲面有多崎岖**，
从而明白"挑回测里最好的那组参数"为什么基本等于过拟合（见 docs/tutorial/06）。
真正该关注的不是某个孤立的高点，而是**有没有一片连续的、都还不错的参数区域**。

运行（先 conda activate quant）：
    python examples/param_sweep.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from quant.analysis import compute_metrics
from quant.backtest import BacktestEngine
from quant.data import get_daily
from quant.strategy import MaCrossStrategy

SYMBOL = "000001"
START, END = "20190101", "20231231"
FAST_LIST = [3, 5, 8, 10, 12, 15]
SLOW_LIST = [20, 30, 40, 50, 60]
METRIC = "夏普比率"   # 用哪个指标作为热力图颜色；也可改 "累计收益率" / "年化波动率"


def run_sweep(data: pd.DataFrame) -> pd.DataFrame:
    """对每个 (fast, slow) 跑一次回测，返回长表（每行一个组合及其指标）。"""
    rows = []
    for fast in FAST_LIST:
        for slow in SLOW_LIST:
            if fast >= slow:
                continue
            engine = BacktestEngine(MaCrossStrategy(fast=fast, slow=slow), initial_cash=100_000.0)
            result = engine.run(data, symbol=SYMBOL)
            m = compute_metrics(result)
            rows.append({
                "fast": fast,
                "slow": slow,
                "累计收益率": m["累计收益率"],
                "年化波动率": m["年化波动率"],
                "夏普比率": m["夏普比率"],
                "最大回撤": m["最大回撤"],
                "交易回合数": m["交易回合数"],
            })
    return pd.DataFrame(rows)


def plot_heatmaps(df: pd.DataFrame, save_path: Path) -> None:
    import matplotlib
    import matplotlib.pyplot as plt

    # 传入整个候选列表，matplotlib 会自动挑第一个本机可用的字体
    matplotlib.rcParams["font.sans-serif"] = [
        "Microsoft YaHei", "SimHei", "PingFang SC", "DejaVu Sans"
    ]
    matplotlib.rcParams["axes.unicode_minus"] = False

    metrics_to_plot = ["累计收益率", "夏普比率", "年化波动率"]
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))

    for ax, metric in zip(axes, metrics_to_plot):
        grid = df.pivot(index="fast", columns="slow", values=metric)
        im = ax.imshow(grid.values, aspect="auto", cmap="RdYlGn", origin="lower")
        ax.set_xticks(range(len(grid.columns)))
        ax.set_xticklabels(grid.columns)
        ax.set_yticks(range(len(grid.index)))
        ax.set_yticklabels(grid.index)
        ax.set_xlabel("slow（慢线）")
        ax.set_ylabel("fast（快线）")
        ax.set_title(metric)
        # 在每个格子标数值
        for i in range(grid.shape[0]):
            for j in range(grid.shape[1]):
                v = grid.values[i, j]
                if not np.isnan(v):
                    ax.text(j, i, f"{v:.0%}" if metric != "夏普比率" else f"{v:.2f}",
                            ha="center", va="center", fontsize=8)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    fig.suptitle(f"双均线参数扫描 {SYMBOL}（{START}~{END}）", fontsize=13)
    fig.tight_layout()
    save_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(save_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"热力图已保存到：{save_path}")


def main() -> None:
    print(f"加载 {SYMBOL} 数据...")
    data = get_daily(SYMBOL, start=START, end=END, adjust="qfq")

    print(f"扫描 {len(FAST_LIST)}×{len(SLOW_LIST)} 个参数组合...")
    df = run_sweep(data)

    # 按夏普排序，直观感受"相邻参数表现却差很多"的非单调性
    df_sorted = df.sort_values(METRIC, ascending=False)
    pd.set_option("display.unicode.east_asian_width", True)
    print("\n按夏普比率排序（注意：相邻参数表现往往跳变，没有单调规律）：")
    print(df_sorted.to_string(index=False,
          formatters={
              "累计收益率": "{:+.1%}".format,
              "年化波动率": "{:.1%}".format,
              "夏普比率": "{:.2f}".format,
              "最大回撤": "{:.1%}".format,
          }))

    out = Path(__file__).resolve().parents[1] / "output" / f"{SYMBOL}_param_sweep.png"
    plot_heatmaps(df, out)


if __name__ == "__main__":
    main()
