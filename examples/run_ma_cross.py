"""端到端示例：在贵州茅台上跑双均线策略，打印指标并出图。

运行（先 conda activate quant）：
    python examples/run_ma_cross.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# 让脚本无需安装即可 import 到 quant 包（把项目根加入 sys.path）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from quant.analysis import compute_metrics, format_metrics, plot_result
from quant.backtest import BacktestEngine, BrokerConfig
from quant.data import get_daily
from quant.strategy import MaCrossStrategy


def main() -> None:
    # 用平安银行（股价低、一手便宜，10 万本金能全程交易，适合教学）。
    # 注意：别一上来用贵州茅台——它一手要 15 万+，10 万本金买不起一手，
    # 策略会因为"凑不齐 100 股"而长期空仓，曲线变成一条直线（这本身也是个教训）。
    symbol = "000001"  # 平安银行；想换标的改这里

    print(f"[1/4] 获取 {symbol} 日线数据（首次会联网，之后读本地缓存）...")
    data = get_daily(symbol, start="20190101", end="20231231", adjust="qfq")
    print(f"      共 {len(data)} 个交易日：{data.index[0].date()} ~ {data.index[-1].date()}")

    print("[2/4] 构建策略与回测引擎...")
    strategy = MaCrossStrategy(fast=5, slow=20)
    engine = BacktestEngine(
        strategy,
        initial_cash=100_000.0,
        broker_config=BrokerConfig(),  # 默认 A 股费用/涨跌停规则
    )

    print("[3/4] 运行回测...")
    result = engine.run(data, symbol=symbol)

    print("[4/4] 评估结果：\n")
    metrics = compute_metrics(result)
    print(format_metrics(metrics))
    print()

    out = Path(__file__).resolve().parents[1] / "output" / f"{symbol}_ma_cross.png"
    plot_result(result, save_path=str(out), show=False)


if __name__ == "__main__":
    main()
