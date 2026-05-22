# quant

一个面向 A 股、从零手写的事件驱动回测框架，配套中文入门教学。用来学习量化研究的基本流程：数据 → 策略 → 回测 → 评估。不依赖 backtrader/qlib，只做研究回测，不接实盘。

适合会写 Python、刚入门量化的人。

## 功能

- akshare 获取 A 股日线并本地缓存
- 写策略只需继承 `Strategy` 实现 `on_bar`（内置双均线示例）
- 事件驱动回测，处理 A 股规则：T+1、涨跌停、佣金/印花税、整手 100 股；订单在下一根 bar 开盘成交，避免未来函数
- 绩效指标（年化收益、夏普、最大回撤、胜率）与资金曲线图

## 快速开始

```bash
conda create -n quant python=3.12 -y
conda activate quant
pip install -r requirements.txt
python examples/run_ma_cross.py
```

运行后控制台打印绩效指标，资金曲线图保存到 `output/`。

> 数据首次联网获取，之后读本地缓存。国内网络/代理偶尔会拉取失败，稍等重跑即可（loader 已内置绕代理、重试、东财/新浪双源切换）。详见 `docs/tutorial/02-数据与K线.md`。

## 目录结构

```
quant/
├── quant/
│   ├── data/loader.py        # 行情获取 + 缓存
│   ├── strategy/             # 策略基类与双均线示例
│   ├── backtest/             # 账户、撮合(A股规则)、回测引擎
│   └── analysis/             # 绩效指标与可视化
├── examples/run_ma_cross.py  # 端到端示例
└── docs/tutorial/            # 入门教学，从 00 开始读
```

## 入门教学

`docs/tutorial/` 共 9 篇，建议顺序阅读：环境概览、量化是什么、数据与 K 线、写第一个策略、回测引擎原理、评估指标、新手避坑、进阶方向、参考资料。

## 写一个策略

```python
from quant.strategy import Strategy

class MyStrategy(Strategy):
    def on_bar(self, ctx):
        closes = ctx.history["close"]          # 只含截止当前 bar 的历史
        if len(closes) < 21:
            return
        if closes.iloc[-1] > closes.tail(20).mean() and ctx.position == 0:
            ctx.buy_pct(0.95)
        elif closes.iloc[-1] < closes.tail(20).mean() and ctx.available > 0:
            ctx.sell_all()
```

```python
from quant.data import get_daily
from quant.backtest import BacktestEngine

data = get_daily("000001", start="20200101", end="20231231")
result = BacktestEngine(MyStrategy(), initial_cash=100_000).run(data, symbol="000001")
```

## 免责声明

仅用于学习研究。内置策略是教学示例，不构成投资建议，回测表现不代表未来收益。
