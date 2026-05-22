"""数据层：从 akshare 获取 A 股日线，并做本地缓存。

为什么要缓存？
    akshare 背后是公开网页接口，频繁请求既慢又可能被限流。
    我们把首次拉取的数据存成本地 parquet 文件，之后直接读本地，
    既快又稳定，做研究时反复回测不会一直打网络。

为什么用「前复权」？
    股票会分红、送股、配股，原始价格在除权日会"跳水"，
    这种跳水不是真实涨跌，会污染均线、收益等计算。
    前复权把历史价格按复权因子调整到当前口径，价格连续，
    适合做技术指标和回测。（后复权适合算长期累计收益）
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

# 缓存目录：项目根/data/cache/
_CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache"

# 标准列名：全项目统一使用这套小写英文列名
_STD_COLUMNS = ["open", "high", "low", "close", "volume"]

# 数据源的域名。这些都是国内站点，不该走代理（很多人的代理只能连国外，
# 或本身不稳定），所以我们把它们加入 NO_PROXY 白名单强制直连。
_DATA_DOMAINS = "eastmoney.com,sina.com.cn,sina.com,push2his.eastmoney.com"


def _bypass_proxy_for_data_sites() -> None:
    """让 requests 对国内数据站点直连，绕过（可能挂掉的）系统/环境代理。

    背景：在中文 Windows + 公司网络环境里，requests 会从环境变量**和 Windows
    系统代理（注册表）**读取代理设置。一旦该代理连不上，akshare 请求就会报
    ProxyError。把数据域名写进 NO_PROXY，requests 会优先据此跳过代理直连。
    """
    for key in ("NO_PROXY", "no_proxy"):
        existing = os.environ.get(key, "")
        merged = ",".join(p for p in (existing, _DATA_DOMAINS) if p)
        os.environ[key] = merged


def _cache_path(symbol: str, adjust: str) -> Path:
    return _CACHE_DIR / f"{symbol}_{adjust}.parquet"


def get_daily(
    symbol: str,
    start: str = "20190101",
    end: str | None = None,
    adjust: str = "qfq",
    use_cache: bool = True,
) -> pd.DataFrame:
    """获取一只 A 股的日线行情。

    参数
    ----
    symbol : str
        6 位股票代码，如 "600519"（贵州茅台）、"000001"（平安银行）。
        不需要加 sh/sz 前缀，akshare 会自动识别。
    start, end : str
        起止日期，格式 "YYYYMMDD"。end 默认取今天。
    adjust : str
        复权方式："qfq" 前复权（默认）、"hfq" 后复权、"" 不复权。
    use_cache : bool
        True 时优先读本地缓存；缓存不存在才请求网络并写入缓存。

    返回
    ----
    pd.DataFrame
        索引为 DatetimeIndex（交易日），列为
        ["open", "high", "low", "close", "volume"]，按日期升序。
    """
    if end is None:
        end = pd.Timestamp.today().strftime("%Y%m%d")

    path = _cache_path(symbol, adjust)
    if use_cache and path.exists():
        df = pd.read_parquet(path)
    else:
        df = _fetch_from_akshare(symbol, start, end, adjust)
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path)

    # 按调用方请求的区间裁剪（缓存可能比本次请求范围更大）
    mask = (df.index >= pd.to_datetime(start)) & (df.index <= pd.to_datetime(end))
    return df.loc[mask].copy()


def _sina_symbol(symbol: str) -> str:
    """把 6 位代码转成新浪接口要求的带交易所前缀格式，如 300750 -> sz300750。"""
    if symbol.startswith(("5", "6", "9")) or symbol.startswith("688"):
        return "sh" + symbol            # 上交所（含科创板 688）
    if symbol.startswith(("0", "2", "3")):
        return "sz" + symbol            # 深交所（含创业板 30）
    if symbol.startswith(("4", "8")):
        return "bj" + symbol            # 北交所
    return "sh" + symbol


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    """把不同数据源的原始 DataFrame 统一成 [open,high,low,close,volume] + 日期索引。"""
    # 东方财富是中文列名，新浪已是英文列名；两者都映射一遍即可
    rename = {
        "日期": "date", "开盘": "open", "最高": "high",
        "最低": "low", "收盘": "close", "成交量": "volume",
    }
    df = df.rename(columns=rename)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    return df[_STD_COLUMNS].astype(float)


def _try_source(name: str, call, retries: int, retry_wait: float):
    """带重试地调用某个数据源；全部失败返回 (None, 最后的异常)。"""
    import time

    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            raw = call()
            if raw is not None and not raw.empty:
                return raw, None
            last_err = ValueError("数据源返回空")
        except Exception as e:  # noqa: BLE001  (网络异常类型多，统一兜底重试)
            last_err = e
        if attempt < retries:
            print(
                f"  [数据] {name} 第 {attempt} 次失败（{type(last_err).__name__}），"
                f"{retry_wait:.1f}s 后重试..."
            )
            time.sleep(retry_wait)
    return None, last_err


def _fetch_from_akshare(
    symbol: str,
    start: str,
    end: str,
    adjust: str,
    retries: int = 4,
    retry_wait: float = 1.5,
) -> pd.DataFrame:
    """从 akshare 拉取日线并标准化。

    稳健性设计（针对国内网络/代理环境的常见坑）：
      1. 先把数据域名加入 NO_PROXY，强制直连，绕过可能挂掉的系统/环境代理。
      2. 数据源会间歇性断连（限流/反爬），所以每个源都自动重试若干次。
      3. **双源容错**：优先用东方财富(stock_zh_a_hist)，失败则自动切到
         新浪(stock_zh_a_daily)。两个源很少同时挂。
    """
    _bypass_proxy_for_data_sites()

    import akshare as ak

    # 源 1：东方财富（6 位代码，复权参数 qfq/hfq/""）
    raw, err1 = _try_source(
        "东方财富",
        lambda: ak.stock_zh_a_hist(
            symbol=symbol, period="daily",
            start_date=start, end_date=end, adjust=adjust,
        ),
        retries, retry_wait,
    )

    # 源 2：新浪（需带 sh/sz 前缀；adjust 空字符串表示不复权）
    err2 = None
    if raw is None:
        print("  [数据] 东方财富不可用，改用新浪备用源...")
        raw, err2 = _try_source(
            "新浪",
            lambda: ak.stock_zh_a_daily(
                symbol=_sina_symbol(symbol),
                start_date=start, end_date=end,
                adjust=(adjust or ""),
            ),
            retries, retry_wait,
        )

    if raw is None:
        raise ConnectionError(
            f"东方财富与新浪两个源都未能获取 {symbol} 的数据。"
            f"基本是网络/代理临时故障，请稍后重试（一旦成功会写入本地缓存，之后不再联网）。"
            f"\n  东方财富最后错误：{type(err1).__name__}: {err1}"
            f"\n  新浪最后错误：    {type(err2).__name__}: {err2}"
        )

    return _normalize(raw)


def clear_cache(symbol: str | None = None) -> None:
    """清理本地缓存。symbol 为 None 时清空整个缓存目录。"""
    if not _CACHE_DIR.exists():
        return
    pattern = "*.parquet" if symbol is None else f"{symbol}_*.parquet"
    for f in _CACHE_DIR.glob(pattern):
        f.unlink()
