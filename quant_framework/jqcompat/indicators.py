"""
聚宽兼容技术指标函数
提供与聚宽平台兼容的技术分析指标
"""

import numpy as np
import pandas as pd
from typing import Union, Optional, Tuple
import warnings

# 尝试导入talib，如果没有安装则使用自实现
try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False
    talib = None


def SMA(data: Union[pd.Series, np.ndarray], timeperiod: int = 30) -> Union[pd.Series, np.ndarray]:
    """
    简单移动平均线
    
    Args:
        data: 价格数据
        timeperiod: 时间周期
        
    Returns:
        SMA值
    """
    if TALIB_AVAILABLE and isinstance(data, (pd.Series, np.ndarray)):
        values = data.values if isinstance(data, pd.Series) else data
        result = talib.SMA(values.astype(float), timeperiod=timeperiod)
        
        if isinstance(data, pd.Series):
            return pd.Series(result, index=data.index, name=f'SMA_{timeperiod}')
        return result
    else:
        # 自实现
        if isinstance(data, pd.Series):
            return data.rolling(window=timeperiod).mean()
        else:
            return pd.Series(data).rolling(window=timeperiod).mean().values


def EMA(data: Union[pd.Series, np.ndarray], timeperiod: int = 30) -> Union[pd.Series, np.ndarray]:
    """
    指数移动平均线
    
    Args:
        data: 价格数据
        timeperiod: 时间周期
        
    Returns:
        EMA值
    """
    if TALIB_AVAILABLE and isinstance(data, (pd.Series, np.ndarray)):
        values = data.values if isinstance(data, pd.Series) else data
        result = talib.EMA(values.astype(float), timeperiod=timeperiod)
        
        if isinstance(data, pd.Series):
            return pd.Series(result, index=data.index, name=f'EMA_{timeperiod}')
        return result
    else:
        # 自实现
        if isinstance(data, pd.Series):
            return data.ewm(span=timeperiod).mean()
        else:
            return pd.Series(data).ewm(span=timeperiod).mean().values


def RSI(data: Union[pd.Series, np.ndarray], timeperiod: int = 14) -> Union[pd.Series, np.ndarray]:
    """
    相对强弱指标
    
    Args:
        data: 价格数据
        timeperiod: 时间周期
        
    Returns:
        RSI值
    """
    if TALIB_AVAILABLE and isinstance(data, (pd.Series, np.ndarray)):
        values = data.values if isinstance(data, pd.Series) else data
        result = talib.RSI(values.astype(float), timeperiod=timeperiod)
        
        if isinstance(data, pd.Series):
            return pd.Series(result, index=data.index, name=f'RSI_{timeperiod}')
        return result
    else:
        # 自实现
        if isinstance(data, np.ndarray):
            data = pd.Series(data)
        
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=timeperiod).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=timeperiod).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        if isinstance(data, pd.Series):
            rsi.name = f'RSI_{timeperiod}'
        
        return rsi if isinstance(data, pd.Series) else rsi.values


def MACD(
    data: Union[pd.Series, np.ndarray],
    fastperiod: int = 12,
    slowperiod: int = 26,
    signalperiod: int = 9
) -> Tuple[Union[pd.Series, np.ndarray], Union[pd.Series, np.ndarray], Union[pd.Series, np.ndarray]]:
    """
    MACD指标
    
    Args:
        data: 价格数据
        fastperiod: 快线周期
        slowperiod: 慢线周期
        signalperiod: 信号线周期
        
    Returns:
        (MACD线, 信号线, 柱状图)
    """
    if TALIB_AVAILABLE and isinstance(data, (pd.Series, np.ndarray)):
        values = data.values if isinstance(data, pd.Series) else data
        macd, signal, hist = talib.MACD(
            values.astype(float),
            fastperiod=fastperiod,
            slowperiod=slowperiod,
            signalperiod=signalperiod
        )
        
        if isinstance(data, pd.Series):
            macd = pd.Series(macd, index=data.index, name='MACD')
            signal = pd.Series(signal, index=data.index, name='MACD_Signal')
            hist = pd.Series(hist, index=data.index, name='MACD_Hist')
        
        return macd, signal, hist
    else:
        # 自实现
        if isinstance(data, np.ndarray):
            data = pd.Series(data)
        
        ema_fast = data.ewm(span=fastperiod).mean()
        ema_slow = data.ewm(span=slowperiod).mean()
        
        macd = ema_fast - ema_slow
        signal = macd.ewm(span=signalperiod).mean()
        hist = macd - signal
        
        if isinstance(data, pd.Series):
            macd.name = 'MACD'
            signal.name = 'MACD_Signal'
            hist.name = 'MACD_Hist'
            return macd, signal, hist
        else:
            return macd.values, signal.values, hist.values


def BOLL(
    data: Union[pd.Series, np.ndarray],
    timeperiod: int = 20,
    nbdevup: float = 2.0,
    nbdevdn: float = 2.0
) -> Tuple[Union[pd.Series, np.ndarray], Union[pd.Series, np.ndarray], Union[pd.Series, np.ndarray]]:
    """
    布林带指标
    
    Args:
        data: 价格数据
        timeperiod: 时间周期
        nbdevup: 上轨标准差倍数
        nbdevdn: 下轨标准差倍数
        
    Returns:
        (上轨, 中轨, 下轨)
    """
    if TALIB_AVAILABLE and isinstance(data, (pd.Series, np.ndarray)):
        values = data.values if isinstance(data, pd.Series) else data
        upper, middle, lower = talib.BBANDS(
            values.astype(float),
            timeperiod=timeperiod,
            nbdevup=nbdevup,
            nbdevdn=nbdevdn
        )
        
        if isinstance(data, pd.Series):
            upper = pd.Series(upper, index=data.index, name='BOLL_Upper')
            middle = pd.Series(middle, index=data.index, name='BOLL_Middle')
            lower = pd.Series(lower, index=data.index, name='BOLL_Lower')
        
        return upper, middle, lower
    else:
        # 自实现
        if isinstance(data, np.ndarray):
            data = pd.Series(data)
        
        middle = data.rolling(window=timeperiod).mean()
        std = data.rolling(window=timeperiod).std()
        
        upper = middle + (std * nbdevup)
        lower = middle - (std * nbdevdn)
        
        if isinstance(data, pd.Series):
            upper.name = 'BOLL_Upper'
            middle.name = 'BOLL_Middle'
            lower.name = 'BOLL_Lower'
            return upper, middle, lower
        else:
            return upper.values, middle.values, lower.values


def KDJ(
    high: Union[pd.Series, np.ndarray],
    low: Union[pd.Series, np.ndarray],
    close: Union[pd.Series, np.ndarray],
    fastk_period: int = 9,
    slowk_period: int = 3,
    slowd_period: int = 3
) -> Tuple[Union[pd.Series, np.ndarray], Union[pd.Series, np.ndarray], Union[pd.Series, np.ndarray]]:
    """
    KDJ指标
    
    Args:
        high: 最高价
        low: 最低价
        close: 收盘价
        fastk_period: FastK周期
        slowk_period: SlowK周期
        slowd_period: SlowD周期
        
    Returns:
        (K值, D值, J值)
    """
    if TALIB_AVAILABLE:
        high_vals = high.values if isinstance(high, pd.Series) else high
        low_vals = low.values if isinstance(low, pd.Series) else low
        close_vals = close.values if isinstance(close, pd.Series) else close
        
        slowk, slowd = talib.STOCH(
            high_vals.astype(float),
            low_vals.astype(float),
            close_vals.astype(float),
            fastk_period=fastk_period,
            slowk_period=slowk_period,
            slowd_period=slowd_period
        )
        
        # J = 3K - 2D
        j = 3 * slowk - 2 * slowd
        
        if isinstance(close, pd.Series):
            k = pd.Series(slowk, index=close.index, name='K')
            d = pd.Series(slowd, index=close.index, name='D')
            j = pd.Series(j, index=close.index, name='J')
        else:
            k, d = slowk, j
        
        return k, d, j
    else:
        # 自实现
        if isinstance(close, np.ndarray):
            high = pd.Series(high)
            low = pd.Series(low)
            close = pd.Series(close)
        
        # 计算RSV
        lowest_low = low.rolling(window=fastk_period).min()
        highest_high = high.rolling(window=fastk_period).max()
        rsv = (close - lowest_low) / (highest_high - lowest_low) * 100
        
        # 计算K值
        k = rsv.ewm(alpha=1/slowk_period).mean()
        
        # 计算D值
        d = k.ewm(alpha=1/slowd_period).mean()
        
        # 计算J值
        j = 3 * k - 2 * d
        
        if isinstance(close, pd.Series):
            k.name = 'K'
            d.name = 'D'
            j.name = 'J'
            return k, d, j
        else:
            return k.values, d.values, j.values


def ATR(
    high: Union[pd.Series, np.ndarray],
    low: Union[pd.Series, np.ndarray],
    close: Union[pd.Series, np.ndarray],
    timeperiod: int = 14
) -> Union[pd.Series, np.ndarray]:
    """
    平均真实波幅
    
    Args:
        high: 最高价
        low: 最低价
        close: 收盘价
        timeperiod: 时间周期
        
    Returns:
        ATR值
    """
    if TALIB_AVAILABLE:
        high_vals = high.values if isinstance(high, pd.Series) else high
        low_vals = low.values if isinstance(low, pd.Series) else low
        close_vals = close.values if isinstance(close, pd.Series) else close
        
        result = talib.ATR(
            high_vals.astype(float),
            low_vals.astype(float),
            close_vals.astype(float),
            timeperiod=timeperiod
        )
        
        if isinstance(close, pd.Series):
            return pd.Series(result, index=close.index, name=f'ATR_{timeperiod}')
        return result
    else:
        # 自实现
        if isinstance(close, np.ndarray):
            high = pd.Series(high)
            low = pd.Series(low)
            close = pd.Series(close)
        
        # 计算真实波幅
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = abs(high - prev_close)
        tr3 = abs(low - prev_close)
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # 计算ATR
        atr = tr.rolling(window=timeperiod).mean()
        
        if isinstance(close, pd.Series):
            atr.name = f'ATR_{timeperiod}'
        
        return atr if isinstance(close, pd.Series) else atr.values


def CCI(
    high: Union[pd.Series, np.ndarray],
    low: Union[pd.Series, np.ndarray],
    close: Union[pd.Series, np.ndarray],
    timeperiod: int = 14
) -> Union[pd.Series, np.ndarray]:
    """
    顺势指标
    
    Args:
        high: 最高价
        low: 最低价
        close: 收盘价
        timeperiod: 时间周期
        
    Returns:
        CCI值
    """
    if TALIB_AVAILABLE:
        high_vals = high.values if isinstance(high, pd.Series) else high
        low_vals = low.values if isinstance(low, pd.Series) else low
        close_vals = close.values if isinstance(close, pd.Series) else close
        
        result = talib.CCI(
            high_vals.astype(float),
            low_vals.astype(float),
            close_vals.astype(float),
            timeperiod=timeperiod
        )
        
        if isinstance(close, pd.Series):
            return pd.Series(result, index=close.index, name=f'CCI_{timeperiod}')
        return result
    else:
        # 自实现
        if isinstance(close, np.ndarray):
            high = pd.Series(high)
            low = pd.Series(low)
            close = pd.Series(close)
        
        # 计算典型价格
        tp = (high + low + close) / 3
        
        # 计算移动平均
        ma = tp.rolling(window=timeperiod).mean()
        
        # 计算平均绝对偏差
        mad = tp.rolling(window=timeperiod).apply(
            lambda x: np.mean(np.abs(x - np.mean(x)))
        )
        
        # 计算CCI
        cci = (tp - ma) / (0.015 * mad)
        
        if isinstance(close, pd.Series):
            cci.name = f'CCI_{timeperiod}'
        
        return cci if isinstance(close, pd.Series) else cci.values


def WR(
    high: Union[pd.Series, np.ndarray],
    low: Union[pd.Series, np.ndarray],
    close: Union[pd.Series, np.ndarray],
    timeperiod: int = 14
) -> Union[pd.Series, np.ndarray]:
    """
    威廉指标
    
    Args:
        high: 最高价
        low: 最低价
        close: 收盘价
        timeperiod: 时间周期
        
    Returns:
        WR值
    """
    if TALIB_AVAILABLE:
        high_vals = high.values if isinstance(high, pd.Series) else high
        low_vals = low.values if isinstance(low, pd.Series) else low
        close_vals = close.values if isinstance(close, pd.Series) else close
        
        result = talib.WILLR(
            high_vals.astype(float),
            low_vals.astype(float),
            close_vals.astype(float),
            timeperiod=timeperiod
        )
        
        if isinstance(close, pd.Series):
            return pd.Series(result, index=close.index, name=f'WR_{timeperiod}')
        return result
    else:
        # 自实现
        if isinstance(close, np.ndarray):
            high = pd.Series(high)
            low = pd.Series(low)
            close = pd.Series(close)
        
        # 计算最高价和最低价
        highest_high = high.rolling(window=timeperiod).max()
        lowest_low = low.rolling(window=timeperiod).min()
        
        # 计算WR
        wr = -100 * (highest_high - close) / (highest_high - lowest_low)
        
        if isinstance(close, pd.Series):
            wr.name = f'WR_{timeperiod}'
        
        return wr if isinstance(close, pd.Series) else wr.values


def OBV(
    close: Union[pd.Series, np.ndarray],
    volume: Union[pd.Series, np.ndarray]
) -> Union[pd.Series, np.ndarray]:
    """
    能量潮指标
    
    Args:
        close: 收盘价
        volume: 成交量
        
    Returns:
        OBV值
    """
    if TALIB_AVAILABLE:
        close_vals = close.values if isinstance(close, pd.Series) else close
        volume_vals = volume.values if isinstance(volume, pd.Series) else volume
        
        result = talib.OBV(close_vals.astype(float), volume_vals.astype(float))
        
        if isinstance(close, pd.Series):
            return pd.Series(result, index=close.index, name='OBV')
        return result
    else:
        # 自实现
        if isinstance(close, np.ndarray):
            close = pd.Series(close)
            volume = pd.Series(volume)
        
        # 计算价格变化方向
        price_change = close.diff()
        
        # 计算OBV
        obv = volume.copy()
        obv[price_change < 0] = -volume[price_change < 0]
        obv[price_change == 0] = 0
        obv = obv.cumsum()
        
        if isinstance(close, pd.Series):
            obv.name = 'OBV'
        
        return obv if isinstance(close, pd.Series) else obv.values


# 聚宽兼容的技术指标别名
def MA(data: Union[pd.Series, np.ndarray], timeperiod: int = 30) -> Union[pd.Series, np.ndarray]:
    """移动平均线（SMA别名）"""
    return SMA(data, timeperiod)


def EXPMA(data: Union[pd.Series, np.ndarray], timeperiod: int = 30) -> Union[pd.Series, np.ndarray]:
    """指数移动平均线（EMA别名）"""
    return EMA(data, timeperiod)


# 警告信息
if not TALIB_AVAILABLE:
    warnings.warn(
        "TA-Lib not available. Using simplified implementations. "
        "For better performance and accuracy, install TA-Lib: pip install TA-Lib",
        UserWarning
    )