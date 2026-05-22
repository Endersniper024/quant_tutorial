# ΩuantLab —— 从零手写的 A 股量化研究回测框架（教学版）

一个**从零手写**、面向 A 股、用于**学习与研究回测**的事件驱动量化框架。
不依赖 backtrader/qlib 等现成框架，目的是把"数据 → 策略 → 回测 → 评估"这条
研究闭环的每一环都讲透、写透，让量化新手既能跑通、又能看懂原理。

> 适合人群：会写 Python、但量化是新手的同学。
> 第一阶段只做**研究回测**，不接实盘下单。

---

## 能做什么

- 用 [akshare](https://akshare.akfamily.xyz/) 免费获取 A 股日线，并本地缓存
- 用统一接口写自己的策略（已内置"双均线交叉"示例）
- 在手写的**事件驱动**引擎上回测，正确处理 A 股规则：
  **T+1、涨跌停、佣金/印花税、整手（100 股）**，订单延迟到下一根 bar 开盘成交（防未来函数）
- 计算关键绩效指标（年化收益、夏普、最大回撤、胜率等）并画资金曲线/回撤图

---

## 快速开始

```bash
# 1. 创建独立 conda 环境（已建好可跳过）
conda create -n quant python=3.12 -y
conda activate quant

# 2. 安装依赖
pip install -r requirements.txt

# 3. 跑通第一个例子（首次联网拉数据，之后读本地缓存）
python examples/run_ma_cross.py
```

运行后会在控制台打印绩效指标，并把资金曲线图保存到 `output/`。

> Windows 提示：若用 `conda run` 出现中文乱码报错，直接用环境内的 python：
> `conda activate quant` 后再 `python examples/run_ma_cross.py` 即可。

### 关于数据获取（重要）

数据层做了三重容错，应对国内常见的网络/代理问题：

1. **绕过代理**：自动把数据域名加入 `NO_PROXY`，强制直连——避免"系统代理挂了导致 `ProxyError`"。
2. **自动重试**：东方财富/新浪接口会间歇性断连，每个源自动重试若干次。
3. **双源容错**：优先东方财富，失败则自动切到新浪备用源。两者很少同时挂。

数据**一旦拉取成功就缓存到本地** `data/cache/`，之后回测不再联网、秒开。

如果两个源都暂时连不上（纯网络故障），稍等几分钟重跑即可；想强制重拉用
`from quant.data import clear_cache; clear_cache("000001")`。

---

## 目录结构

```
quant/
├── quant/                    # 核心包
│   ├── data/loader.py        # akshare 行情获取 + parquet 缓存
│   ├── strategy/base.py      # 策略基类
│   ├── strategy/ma_cross.py  # 双均线示例策略
│   ├── backtest/account.py   # 账户：现金/持仓/T+1
│   ├── backtest/broker.py    # 撮合 + A股规则（涨跌停/费用/整手）
│   ├── backtest/engine.py    # 事件驱动回测主循环
│   ├── analysis/metrics.py   # 绩效指标
│   └── analysis/plot.py      # 可视化
├── examples/run_ma_cross.py  # 端到端示例
└── docs/tutorial/            # 中文入门教学（强烈建议从 00 开始读）
```

## 入门教学

边看代码边读 [`docs/tutorial/`](docs/tutorial/)：

| 文档 | 内容 |
|------|------|
| `00-环境与项目概览.md` | 装环境、跑通第一个例子 |
| `01-量化交易是什么.md` | 量化 vs 主观、研究流程、能与不能 |
| `02-数据与K线.md` | OHLCV、复权、A 股交易规则 |
| `03-写第一个策略-双均线.md` | 均线、信号、金叉死叉 |
| `04-回测引擎原理.md` | 事件驱动、撮合、为何延迟成交 |
| `05-怎么评估策略好坏.md` | 收益/夏普/回撤/胜率的含义 |
| `06-量化新手常踩的坑.md` | 未来函数、过拟合、幸存者偏差等 |
| `07-下一步学什么.md` | 多标的、因子、参数优化、走向实盘 |
| `08-参考资料.md` | 权威出处：交易所规则、印花税公告、数据源/框架文档、经典书与论文 |

---

## 写一个自己的策略

继承 `Strategy`，实现 `on_bar`：

```python
from quant.strategy import Strategy

class MyStrategy(Strategy):
    def on_bar(self, ctx):
        # ctx.history 是截止当前 bar 的历史（看不到未来）
        closes = ctx.history["close"]
        if len(closes) < 21:
            return
        if closes.iloc[-1] > closes.tail(20).mean() and ctx.position == 0:
            ctx.buy_pct(0.95)        # 用 95% 资产买入
        elif closes.iloc[-1] < closes.tail(20).mean() and ctx.available > 0:
            ctx.sell_all()           # 清仓
```

然后丢给引擎跑：

```python
from quant.data import get_daily
from quant.backtest import BacktestEngine

data = get_daily("000001", start="20200101", end="20231231")
result = BacktestEngine(MyStrategy(), initial_cash=100_000).run(data, symbol="000001")
```

---

## 免责声明

本项目仅用于学习与研究。内置策略是教学示例，**不构成任何投资建议**，
回测表现不代表未来收益。实盘投资风险自负。
