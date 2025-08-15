"""
聚宽兼容策略示例
演示如何使用聚宽兼容API编写策略
"""

import asyncio
from datetime import datetime, date
import pandas as pd

from quant_framework.core.config import WindConfig
from quant_framework.data.base import DataSourceManager
from quant_framework.data.sources.factory import DataSourceFactory
from quant_framework.jqcompat.api import initialize_jq_api, get_price, attribute_history
from quant_framework.jqcompat.context import JQCompatibleContext
from quant_framework.jqcompat.indicators import SMA, RSI, MACD
from quant_framework.utils.logger import setup_logging, get_logger


# 全局变量（聚宽风格）
g = type('GlobalVars', (), {})()


def initialize(context):
    """
    初始化函数（聚宽兼容）
    
    Args:
        context: 策略上下文
    """
    logger = get_logger("strategy")
    logger.info("Strategy initialization started")
    
    # 设置基准
    context.set_benchmark('000300.XSHG')  # 沪深300
    
    # 设置股票池
    g.stocks = ['000001.SZ', '000002.SZ', '600000.SH', '600036.SH']
    context.set_universe(g.stocks)
    
    # 策略参数
    g.ma_short = 5   # 短期均线
    g.ma_long = 20   # 长期均线
    g.rsi_period = 14  # RSI周期
    g.rsi_oversold = 30  # RSI超卖线
    g.rsi_overbought = 70  # RSI超买线
    
    # 持仓权重
    g.position_weight = 0.2  # 每只股票最大持仓权重
    
    logger.info(
        "Strategy initialized",
        stocks=g.stocks,
        ma_short=g.ma_short,
        ma_long=g.ma_long,
        position_weight=g.position_weight
    )


def handle_data(context, data):
    """
    主要交易逻辑（聚宽兼容）
    
    Args:
        context: 策略上下文
        data: 当前数据
    """
    logger = get_logger("strategy")
    
    # 获取当前时间
    current_time = context.current_dt
    logger.info(f"Processing data for {current_time}")
    
    # 遍历股票池
    for stock in g.stocks:
        try:
            # 获取历史数据
            hist_data = attribute_history(
                security=stock,
                count=max(g.ma_long, g.rsi_period) + 5,
                unit='1d',
                fields=['close', 'high', 'low', 'volume']
            )
            
            if len(hist_data) < g.ma_long:
                logger.warning(f"Insufficient data for {stock}")
                continue
            
            # 计算技术指标
            close_prices = hist_data['close']
            
            # 移动平均线
            ma_short = SMA(close_prices, g.ma_short).iloc[-1]
            ma_long = SMA(close_prices, g.ma_long).iloc[-1]
            
            # RSI指标
            rsi = RSI(close_prices, g.rsi_period).iloc[-1]
            
            # MACD指标
            macd, signal, hist = MACD(close_prices)
            macd_value = macd.iloc[-1]
            signal_value = signal.iloc[-1]
            
            # 当前价格
            current_price = close_prices.iloc[-1]
            
            # 获取当前持仓
            current_position = context.portfolio.positions.get(stock)
            current_shares = current_position.total_amount if current_position else 0
            
            logger.debug(
                f"Technical indicators for {stock}",
                price=current_price,
                ma_short=ma_short,
                ma_long=ma_long,
                rsi=rsi,
                macd=macd_value,
                signal=signal_value,
                current_shares=current_shares
            )
            
            # 交易信号判断
            buy_signal = (
                ma_short > ma_long and  # 短期均线上穿长期均线
                rsi < g.rsi_oversold and  # RSI超卖
                macd_value > signal_value and  # MACD金叉
                current_shares == 0  # 当前无持仓
            )
            
            sell_signal = (
                (ma_short < ma_long or  # 短期均线下穿长期均线
                 rsi > g.rsi_overbought or  # RSI超买
                 macd_value < signal_value) and  # MACD死叉
                current_shares > 0  # 当前有持仓
            )
            
            # 执行交易
            if buy_signal:
                # 买入信号
                order = context.order_percent(stock, g.position_weight)
                if order:
                    logger.info(
                        f"Buy signal for {stock}",
                        price=current_price,
                        order_id=order.order_id,
                        quantity=order.quantity
                    )
            
            elif sell_signal:
                # 卖出信号
                order = context.order_target_shares(stock, 0)
                if order:
                    logger.info(
                        f"Sell signal for {stock}",
                        price=current_price,
                        order_id=order.order_id,
                        quantity=order.quantity
                    )
            
        except Exception as e:
            logger.error(f"Error processing {stock}: {e}")
            continue
    
    # 输出投资组合状态
    portfolio = context.portfolio
    logger.info(
        "Portfolio status",
        total_value=portfolio.total_value,
        available_cash=portfolio.available_cash,
        positions_count=len(portfolio.positions)
    )


def before_trading_start(context):
    """
    开盘前运行（聚宽兼容）
    
    Args:
        context: 策略上下文
    """
    logger = get_logger("strategy")
    logger.debug("Before trading start")
    
    # 可以在这里进行一些准备工作
    # 比如更新股票池、计算因子等


def after_trading_end(context):
    """
    收盘后运行（聚宽兼容）
    
    Args:
        context: 策略上下文
    """
    logger = get_logger("strategy")
    logger.debug("After trading end")
    
    # 可以在这里进行一些收盘后的处理
    # 比如风险检查、报告生成等


def process_initialize(context):
    """
    进程初始化（聚宽兼容）
    
    Args:
        context: 策略上下文
    """
    logger = get_logger("strategy")
    logger.debug("Process initialize")


async def run_strategy_simulation():
    """运行策略模拟"""
    logger = get_logger("strategy_sim")
    logger.info("Starting strategy simulation")
    
    # 创建上下文
    context = JQCompatibleContext(initial_cash=1000000.0)
    
    # 初始化策略
    initialize(context)
    
    # 模拟几天的交易
    simulation_dates = pd.date_range('2023-01-01', '2023-01-10', freq='D')
    
    for sim_date in simulation_dates:
        # 跳过周末
        if sim_date.weekday() >= 5:
            continue
        
        logger.info(f"Simulating trading day: {sim_date.date()}")
        
        # 设置当前时间
        context.current_dt = sim_date
        
        # 获取当前数据（模拟）
        current_data = {}
        for stock in g.stocks:
            try:
                # 获取当前价格数据
                price_data = get_price(
                    security=stock,
                    start_date=sim_date.date(),
                    end_date=sim_date.date(),
                    fields=['close', 'volume']
                )
                
                if not price_data.empty:
                    current_data[stock] = {
                        'last_price': price_data['close'].iloc[-1],
                        'volume': price_data['volume'].iloc[-1]
                    }
                else:
                    # 使用模拟数据
                    current_data[stock] = {
                        'last_price': 10.0 + hash(stock + str(sim_date)) % 20,
                        'volume': 1000000
                    }
            except Exception as e:
                logger.warning(f"Failed to get data for {stock}: {e}")
                current_data[stock] = {
                    'last_price': 10.0,
                    'volume': 1000000
                }
        
        # 设置当前数据
        context.set_current_data(current_data)
        
        # 执行策略逻辑
        try:
            before_trading_start(context)
            handle_data(context, current_data)
            after_trading_end(context)
        except Exception as e:
            logger.error(f"Strategy execution error on {sim_date.date()}: {e}")
    
    # 输出最终结果
    final_portfolio = context.portfolio
    logger.info(
        "Strategy simulation completed",
        initial_cash=1000000.0,
        final_value=final_portfolio.total_value,
        total_return=(final_portfolio.total_value - 1000000.0) / 1000000.0,
        final_positions=len(final_portfolio.positions)
    )


async def demonstrate_jq_api():
    """演示聚宽API使用"""
    logger = get_logger("jq_demo")
    logger.info("=== JQ API Demo ===")
    
    try:
        # 1. 获取价格数据
        logger.info("Getting price data...")
        price_data = get_price(
            security=['000001.SZ', '600000.SH'],
            start_date='2023-01-01',
            end_date='2023-01-10',
            frequency='daily'
        )
        logger.info(f"Price data shape: {price_data.shape}")
        
        # 2. 获取历史数据
        logger.info("Getting attribute history...")
        hist_data = attribute_history(
            security='000001.SZ',
            count=20,
            unit='1d',
            fields=['close', 'volume']
        )
        logger.info(f"History data shape: {hist_data.shape}")
        
        # 3. 计算技术指标
        if not hist_data.empty and 'close' in hist_data.columns:
            logger.info("Calculating technical indicators...")
            
            close_prices = hist_data['close']
            
            # SMA
            sma_5 = SMA(close_prices, 5)
            sma_20 = SMA(close_prices, 20)
            
            # RSI
            rsi = RSI(close_prices, 14)
            
            # MACD
            macd, signal, hist_macd = MACD(close_prices)
            
            logger.info(
                "Technical indicators calculated",
                sma_5_last=sma_5.iloc[-1] if not sma_5.empty else None,
                sma_20_last=sma_20.iloc[-1] if not sma_20.empty else None,
                rsi_last=rsi.iloc[-1] if not rsi.empty else None,
                macd_last=macd.iloc[-1] if not macd.empty else None
            )
        
        logger.info("JQ API demo completed successfully")
        
    except Exception as e:
        logger.error(f"JQ API demo failed: {e}")


async def main():
    """主函数"""
    # 设置日志
    setup_logging(log_level="INFO", log_format="console")
    logger = get_logger("main")
    
    logger.info("Starting JQ compatibility demonstration")
    
    try:
        # 初始化数据源
        manager = DataSourceManager()
        
        wind_config = WindConfig(
            username="demo_user",
            password="demo_pass"
        )
        wind_source = DataSourceFactory.create_wind_source(wind_config)
        await wind_source.connect()
        
        manager.register_source("wind", wind_source, is_default=True)
        
        # 初始化聚宽API
        initialize_jq_api(manager)
        
        # 演示聚宽API
        await demonstrate_jq_api()
        
        # 运行策略模拟
        await run_strategy_simulation()
        
        logger.info("JQ compatibility demonstration completed")
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        raise
    
    finally:
        # 清理资源
        if 'wind_source' in locals():
            await wind_source.disconnect()


if __name__ == "__main__":
    asyncio.run(main())