"""样本外验证：演示"回测调出来的最优参数，到了新数据就失效"。

这是对抗过拟合最重要的一课（见 docs/tutorial/06）。流程：
  1. 把历史切成样本内 IS（开发用）和样本外 OOS（假装没见过的"未来"）。
  2. 在 IS 上扫描所有参数，挑回测最好的那组——模拟你"调参找最优"的过程。
  3. 把这组"最优"参数拿到 OOS 上跑，看还成不成立。
  4. 再算全部参数的「IS 夏普」与「OOS 夏普」的相关性：
     接近 0 或为负 ⇒ 样本内好的参数样本外不成立 ⇒ 你挑的是噪声 ⇒ 过拟合。

运行（先 conda activate quant）：
    python examples/out_of_sample.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from quant.analysis import compute_metrics
from quant.backtest import BacktestEngine
from quant.data import get_daily
from quant.strategy import MaCrossStrategy

SYMBOL = "000001"
IS_START, IS_END = "2019-01-01", "2021-12-31"     # 样本内：开发/调参
OOS_START, OOS_END = "2022-01-01", "2023-12-31"   # 样本外：验证（绝不参与选参数）
FAST_LIST = [3, 5, 8, 10, 12, 15]
SLOW_LIST = [20, 30, 40, 50, 60]


def backtest_one(data: pd.DataFrame, fast: int, slow: int) -> dict:
    engine = BacktestEngine(MaCrossStrategy(fast=fast, slow=slow), initial_cash=100_000.0)
    return compute_metrics(engine.run(data, symbol=SYMBOL))


def sweep(data: pd.DataFrame) -> pd.DataFrame:
    """在给定数据上扫描所有 (fast, slow)，返回每组的指标。"""
    rows = []
    for fast in FAST_LIST:
        for slow in SLOW_LIST:
            if fast >= slow:
                continue
            m = backtest_one(data, fast, slow)
            rows.append({
                "fast": fast, "slow": slow,
                "累计收益率": m["累计收益率"],
                "夏普比率": m["夏普比率"],
                "最大回撤": m["最大回撤"],
            })
    return pd.DataFrame(rows)


def fmt(m: dict) -> str:
    return (f"累计收益 {m['累计收益率']:+.1%} | 夏普 {m['夏普比率']:.2f} | "
            f"最大回撤 {m['最大回撤']:.1%}")


def plot_scatter(merged: pd.DataFrame, best: pd.Series, save_path: Path) -> None:
    import matplotlib
    import matplotlib.pyplot as plt

    matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "PingFang SC", "DejaVu Sans"]
    matplotlib.rcParams["axes.unicode_minus"] = False

    fig, ax = plt.subplots(figsize=(7, 7))
    ax.axhline(0, color="gray", lw=0.8)
    ax.axvline(0, color="gray", lw=0.8)
    ax.scatter(merged["IS夏普"], merged["OOS夏普"], s=50, alpha=0.7, label="各参数组合")
    # 标出"IS 挑出的最优"那一点
    ax.scatter([best["IS夏普"]], [best["OOS夏普"]], s=160, marker="*",
               color="red", zorder=5, label=f"IS最优 ({int(best['fast'])},{int(best['slow'])})")
    # 对角线：若参数能泛化，点应大致落在这条线附近
    lo = min(merged["IS夏普"].min(), merged["OOS夏普"].min()) - 0.05
    hi = max(merged["IS夏普"].max(), merged["OOS夏普"].max()) + 0.05
    ax.plot([lo, hi], [lo, hi], ls="--", color="green", lw=1, label="理想：IS=OOS")
    ax.set_xlabel("样本内 IS 夏普")
    ax.set_ylabel("样本外 OOS 夏普")
    ax.set_title(f"{SYMBOL} 参数能否泛化：IS 夏普 vs OOS 夏普")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    save_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(save_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"\n散点图已保存到：{save_path}")


def main() -> None:
    print(f"加载 {SYMBOL} 全量数据并切分 IS / OOS ...")
    data = get_daily(SYMBOL, start="20190101", end="20231231", adjust="qfq")
    is_data = data.loc[IS_START:IS_END]
    oos_data = data.loc[OOS_START:OOS_END]
    print(f"  样本内 IS : {is_data.index[0].date()} ~ {is_data.index[-1].date()}（{len(is_data)} 天）")
    print(f"  样本外 OOS: {oos_data.index[0].date()} ~ {oos_data.index[-1].date()}（{len(oos_data)} 天）")

    # 1) 在 IS 上扫描，挑夏普最高的"最优"参数
    is_df = sweep(is_data).set_index(["fast", "slow"])
    best_idx = is_df["夏普比率"].idxmax()
    best_fast, best_slow = best_idx
    print(f"\n[第1步] 在样本内挑出回测最好的参数：fast={best_fast}, slow={best_slow}")
    print(f"        它在 IS 上的表现：{fmt(backtest_one(is_data, best_fast, best_slow))}")

    # 2) 把这组参数拿到 OOS 上跑
    oos_best = backtest_one(oos_data, best_fast, best_slow)
    print(f"\n[第2步] 把同一组参数拿到样本外 OOS：")
    print(f"        它在 OOS 上的表现：{fmt(oos_best)}")

    is_sharpe = is_df.loc[best_idx, "夏普比率"]
    print(f"\n        夏普变化：IS {is_sharpe:.2f}  →  OOS {oos_best['夏普比率']:.2f}")

    # 3) 全部参数：IS 夏普 vs OOS 夏普 的相关性
    oos_df = sweep(oos_data).set_index(["fast", "slow"])
    merged = pd.DataFrame({
        "IS夏普": is_df["夏普比率"],
        "OOS夏普": oos_df["夏普比率"],
    }).reset_index()
    # 用秩相关（对秩做皮尔逊 = 斯皮尔曼），不依赖 scipy
    ranks = merged[["IS夏普", "OOS夏普"]].rank()
    spearman = ranks["IS夏普"].corr(ranks["OOS夏普"])

    print(f"\n[第3步] 全部 {len(merged)} 组参数：IS夏普 与 OOS夏普 的秩相关 = {spearman:+.2f}")
    print("        ≈0 或为负 ⇒ 样本内好的参数样本外不成立 ⇒ 调参挑中的是噪声（过拟合）。")
    print("        接近 +1  ⇒ 参数有真实、可泛化的规律。")

    best_row = merged.set_index(["fast", "slow"]).loc[best_idx]
    best_row = pd.Series({"fast": best_fast, "slow": best_slow,
                          "IS夏普": best_row["IS夏普"], "OOS夏普": best_row["OOS夏普"]})
    out = Path(__file__).resolve().parents[1] / "output" / f"{SYMBOL}_oos_validation.png"
    plot_scatter(merged, best_row, out)


if __name__ == "__main__":
    main()
