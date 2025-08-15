"""
万得数据适配器使用示例
演示如何使用万得数据适配器获取数据
"""

import asyncio
from datetime import date, datetime
from quant_framework.core.config import WindConfig
from quant_framework.core.constants import DataFrequency, SecurityType
from quant_framework.data.sources.factory import create_wind_source
from quant_framework.utils.logger import setup_logging, get_logger


async def main():
    """主函数"""
    # 设置日志
    setup_logging(log_level="INFO", log_format="console")
    logger = get_logger("wind_example")
    
    logger.info("Starting Wind data adapter example")
    
    # 创建万得数据源（使用模拟API）
    wind_source = create_wind_source(
        username="demo_user",
        password="demo_pass",
        server="demo_server",
        rate_limit=10  # 降低限流阈值用于演示
    )
    
    try:
        # 连接数据源
        logger.info("Connecting to Wind data source...")
        connected = await wind_source.connect()
        
        if not connected:
            logger.error("Failed to connect to Wind data source")
            return
        
        logger.info("Connected successfully")
        
        # 健康检查
        health = await wind_source.health_check()
        logger.info(f"Health check result: {health}")
        
        # 示例1: 获取价格数据
        logger.info("Example 1: Getting price data")
        symbols = ['000001.SZ', '600000.SH']
        start_date = date(2023, 1, 1)
        end_date = date(2023, 1, 10)
        
        price_data = await wind_source.get_price_data(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            frequency=DataFrequency.DAILY,
            fields=['open', 'high', 'low', 'close', 'volume']
        )
        
        logger.info(f"Price data shape: {price_data.shape}")
        if not price_data.empty:
            logger.info(f"Price data sample:\n{price_data.head()}")
        
        # 示例2: 获取基本面数据
        logger.info("Example 2: Getting fundamental data")
        fundamental_data = await wind_source.get_fundamental_data(
            symbols=['000001.SZ'],
            fields=['pe_ttm', 'pb_lf', 'roe_ttm'],
            date=date(2023, 1, 1)
        )
        
        logger.info(f"Fundamental data shape: {fundamental_data.shape}")
        if not fundamental_data.empty:
            logger.info(f"Fundamental data:\n{fundamental_data}")
        
        # 示例3: 获取实时数据
        logger.info("Example 3: Getting realtime data")
        realtime_data = await wind_source.get_realtime_data(
            symbols=['000001.SZ', '600000.SH'],
            fields=['current_price', 'volume', 'bid_price', 'ask_price']
        )
        
        logger.info(f"Realtime data shape: {realtime_data.shape}")
        if not realtime_data.empty:
            logger.info(f"Realtime data:\n{realtime_data}")
        
        # 示例4: 获取证券信息
        logger.info("Example 4: Getting security info")
        security_info = await wind_source.get_security_info(
            symbols=['000001.SZ', '600000.SH']
        )
        
        logger.info(f"Security info shape: {security_info.shape}")
        if not security_info.empty:
            logger.info(f"Security info:\n{security_info}")
        
        # 示例5: 搜索证券
        logger.info("Example 5: Searching securities")
        search_results = await wind_source.search_securities(
            keyword="银行",
            security_type=SecurityType.STOCK
        )
        
        logger.info(f"Search results shape: {search_results.shape}")
        if not search_results.empty:
            logger.info(f"Search results:\n{search_results.head()}")
        
        # 示例6: 演示限流
        logger.info("Example 6: Demonstrating rate limiting")
        try:
            # 快速连续调用，触发限流
            for i in range(15):  # 超过限流阈值
                logger.info(f"Making call {i+1}")
                await wind_source.get_realtime_data(['000001.SZ'], ['current_price'])
                
        except Exception as e:
            logger.warning(f"Rate limiting triggered: {e}")
        
        logger.info("All examples completed successfully")
        
    except Exception as e:
        logger.error(f"Example failed: {e}")
        
    finally:
        # 断开连接
        logger.info("Disconnecting from Wind data source...")
        await wind_source.disconnect()
        logger.info("Disconnected")


if __name__ == "__main__":
    asyncio.run(main())