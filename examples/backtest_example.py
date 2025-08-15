"""
回测引擎使用示例
演示如何使用回测引擎进行策略回测和报告生成
"""

import asyncio
from datetime import date, datetime
from decimal import Decimal
import pandas as pd
import numpy as np

from quant_framework.core.config import DatabaseConfig, RedisConfig
from quant_framework.database.base import initialize_database
from quant_framework.database.models import Strategy, User
from quant_framework.database.repositories import RepositoryFactory
from quant_framework.database.base import get_async_session
from quant_framework.data.base import DataSourceManager
from quant_framework.data.sources.wind_adapter import MockWindDataSource
from quant_framework.backtest.engine import BacktestEngine, BacktestConfig
from quant_framework.backtest.reporter import BacktestReporter
from quant_framework.core.constants import DataFrequency


# 示例策略代码
SAMPLE_STRATEGY_CODE = '''
def initialize(context):
    """策略初始化"""
    # 设置股票池
    context.stocks = ['000001.XSHE', '000002.XSHE', '600000.XSHG']
    
    # 策略参数
    context.short_period = 5   # 短期均线
    context.long_period = 20   # 长期均线
    context.max_positions = 2  # 最大持仓数
    
    # 初始化变量
    context.day_count = 0
    context.rebalance_period = 5  # 每5天调仓一次
    
    print(f"策略初始化完成，股票池: {context.stocks}")


def handle_data(context, data):
    """每日数据处理"""
    context.day_count += 1
    
    # 定期调仓
    if context.day_count % context.rebalance_period == 0:
        rebalance(context, data)


def rebalance(context, data):
    """调仓函数"""
    print(f"第{context.day_count}天开始调仓")
    
    # 计算每只股票的信号
    signals = {}
    
    for stock in context.stocks:
        if stock not in data:
            continue
        
        # 获取历史价格数据
        try:
            hist_data = attribute_history(stock, context.long_period + 1, '1d', ['close'])
            
            if len(hist_data) < context.long_period:
                continue
            
            # 计算均线
            short_ma = hist_data['close'][-context.short_period:].mean()
            long_ma = hist_data['close'][-context.long_period:].mean()
            
            # 生成信号
            if short_ma > long_ma:
                signals[stock] = 1  # 买入信号
            else:
                signals[stock] = -1  # 卖出信号
                
        except Exception as e:
            print(f"计算{stock}信号失败: {e}")
            continue
    
    # 根据信号调整持仓
    buy_stocks = [stock for stock, signal in signals.items() if signal > 0]
    
    # 选择前N只股票
    selected_stocks = buy_stocks[:context.max_positions]
    
    if selected_stocks:
        # 等权重分配
        target_weight = 0.9 / len(selected_stocks)  # 保留10%现金
        
        for stock in selected_stocks:
            context.order_target_percent(stock, target_weight)
            print(f"买入 {stock}，目标权重: {target_weight:.2%}")
    
    # 清仓不在选择列表中的股票
    current_positions = list(context.portfolio.positions.keys())
    for stock in current_positions:
        if stock not in selected_stocks:
            context.order_target_percent(stock, 0)
            print(f"清仓 {stock}")
    
    print(f"调仓完成，选中股票: {selected_stocks}")
'''


async def create_sample_data():
    """创建示例数据"""
    print("创建示例用户和策略...")
    
    user_repo = RepositoryFactory.get_user_repository()
    strategy_repo = RepositoryFactory.get_strategy_repository()
    
    async with get_async_session() as session:
        # 创建用户
        user = await user_repo.create(
            session,
            username="demo_user",
            email="demo@example.com",
            password_hash="hashed_password",
            full_name="演示用户"
        )
        
        # 创建策略
        strategy = await strategy_repo.create(
            session,
            name="双均线策略示例",
            description="基于双均线交叉的经典策略",
            code=SAMPLE_STRATEGY_CODE,
            author_id=user.id,
            universe=['000001.XSHE', '000002.XSHE', '600000.XSHG'],
            benchmark='000300.XSHG',
            frequency='daily',
            parameters={
                'short_period': 5,
                'long_period': 20,
                'max_positions': 2,
                'rebalance_period': 5
            }
        )
        
        return user, strategy


def create_mock_data_source():
    """创建模拟数据源"""
    print("创建模拟数据源...")
    
    # 创建模拟价格数据
    symbols = ['000001.XSHE', '000002.XSHE', '600000.XSHG', '000300.XSHG']
    start_date = date(2022, 12, 1)
    end_date = date(2023, 3, 31)
    
    # 生成日期序列
    date_range = pd.date_range(start_date, end_date, freq='D')
    
    mock_data = {}
    
    for symbol in symbols:
        # 设置随机种子以获得可重复的结果
        np.random.seed(hash(symbol) % 2**32)
        
        # 生成价格数据
        base_price = 10.0 + hash(symbol) % 10  # 基础价格
        prices = []
        current_price = base_price
        
        for i in range(len(date_range)):
            # 模拟价格随机游走
            change = np.random.normal(0, 0.02)  # 2%的日波动率
            current_price *= (1 + change)
            
            # 添加一些趋势
            if i % 50 < 25:  # 前25天上涨趋势
                current_price *= 1.001
            else:  # 后25天下跌趋势
                current_price *= 0.999
            
            prices.append({
                'open': current_price * (1 + np.random.normal(0, 0.005)),
                'high': current_price * (1 + abs(np.random.normal(0, 0.01))),
                'low': current_price * (1 - abs(np.random.normal(0, 0.01))),
                'close': current_price,
                'volume': np.random.randint(1000000, 10000000),
                'amount': current_price * np.random.randint(1000000, 10000000)
            })
        
        # 创建DataFrame
        df = pd.DataFrame(prices, index=date_range)
        mock_data[symbol] = df
    
    # 创建模拟数据源
    data_source = MockWindDataSource()
    data_source._mock_data = mock_data
    
    return data_source


async def run_backtest_example():
    """运行回测示例"""
    print("=" * 60)
    print("回测引擎使用示例")
    print("=" * 60)
    
    try:
        # 1. 初始化数据库
        print("\n1. 初始化数据库...")
        db_config = DatabaseConfig(url="sqlite:///backtest_example.db")
        await initialize_database(db_config)
        
        # 2. 创建示例数据
        user, strategy = await create_sample_data()
        print(f"创建用户: {user.username}")
        print(f"创建策略: {strategy.name}")
        
        # 3. 设置数据源
        print("\n2. 设置数据源...")
        data_manager = DataSourceManager()
        mock_data_source = create_mock_data_source()
        data_manager.add_source("mock_wind", mock_data_source)
        data_manager.set_default_source("mock_wind")
        
        # 4. 创建回测引擎
        print("\n3. 创建回测引擎...")
        backtest_engine = BacktestEngine(data_manager)
        
        # 5. 配置回测参数
        print("\n4. 配置回测参数...")
        backtest_config = BacktestConfig(
            start_date=date(2023, 1, 1),
            end_date=date(2023, 3, 31),
            initial_capital=Decimal('1000000'),  # 100万初始资金
            frequency=DataFrequency.DAILY,
            benchmark='000300.XSHG',
            commission_rate=Decimal('0.0003'),  # 0.03%手续费
            slippage_rate=Decimal('0.001'),     # 0.1%滑点
            min_commission=Decimal('5.0')       # 最低5元手续费
        )
        
        print(f"回测期间: {backtest_config.start_date} 至 {backtest_config.end_date}")
        print(f"初始资金: {backtest_config.initial_capital:,} 元")
        print(f"手续费率: {backtest_config.commission_rate:.4%}")
        print(f"滑点率: {backtest_config.slippage_rate:.3%}")
        
        # 6. 运行回测
        print("\n5. 运行回测...")
        print("回测进行中，请稍候...")
        
        backtest_result = await backtest_engine.run_backtest(
            strategy=strategy,
            config=backtest_config,
            user_id=user.id,
            name=f"{strategy.name}_回测_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        
        print(f"回测完成！回测ID: {backtest_result.id}")
        
        # 7. 生成回测报告
        print("\n6. 生成回测报告...")
        reporter = BacktestReporter()
        report = await reporter.generate_report(backtest_result.id)
        
        # 8. 显示回测结果
        print("\n" + "=" * 60)
        print("回测结果摘要")
        print("=" * 60)
        
        basic_info = report['basic_info']
        metrics = report['performance_metrics']
        trade_analysis = report['trade_analysis']
        
        print(f"回测名称: {basic_info['name']}")
        print(f"回测期间: {basic_info['start_date']} 至 {basic_info['end_date']}")
        print(f"回测天数: {basic_info['duration_days']} 天")
        print(f"初始资金: {basic_info['initial_capital']:,.0f} 元")
        print(f"最终资金: {basic_info['final_value']:,.0f} 元")
        
        print(f"\n📈 收益指标:")
        print(f"  总收益率: {metrics['total_return_pct']}")
        print(f"  年化收益率: {metrics['annual_return_pct']}")
        
        print(f"\n📉 风险指标:")
        print(f"  最大回撤: {metrics['max_drawdown_pct']}")
        print(f"  年化波动率: {metrics['volatility_pct']}")
        print(f"  夏普比率: {metrics['sharpe_ratio']:.2f}")
        
        print(f"\n🔄 交易指标:")
        print(f"  总交易次数: {trade_analysis['total_trades']}")
        print(f"  买入次数: {trade_analysis['buy_trades']}")
        print(f"  卖出次数: {trade_analysis['sell_trades']}")
        print(f"  胜率: {metrics['win_rate_pct']}")
        
        print(f"\n💰 成本分析:")
        print(f"  总手续费: {trade_analysis['total_commission']:.2f} 元")
        print(f"  总滑点: {trade_analysis['total_slippage']:.2f} 元")
        
        if trade_analysis['symbols_traded']:
            print(f"\n📊 交易股票: {', '.join(trade_analysis['symbols_traded'])}")
        
        # 9. 导出报告
        print("\n7. 导出报告...")
        
        # 导出JSON报告
        json_file = f"backtest_report_{backtest_result.id}.json"
        json_success = await reporter.export_to_json(backtest_result.id, json_file)
        if json_success:
            print(f"JSON报告已导出: {json_file}")
        
        # 导出Excel报告
        excel_file = f"backtest_report_{backtest_result.id}.xlsx"
        excel_success = await reporter.export_to_excel(backtest_result.id, excel_file)
        if excel_success:
            print(f"Excel报告已导出: {excel_file}")
        
        print("\n" + "=" * 60)
        print("回测示例完成！")
        print("=" * 60)
        
        return backtest_result, report
        
    except Exception as e:
        print(f"\n❌ 回测过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return None, None


async def run_multiple_backtest_example():
    """运行多个回测对比示例"""
    print("\n" + "=" * 60)
    print("多策略回测对比示例")
    print("=" * 60)
    
    # 不同参数的策略配置
    strategy_configs = [
        {"short_period": 5, "long_period": 20, "name": "5-20均线"},
        {"short_period": 10, "long_period": 30, "name": "10-30均线"},
        {"short_period": 5, "long_period": 30, "name": "5-30均线"}
    ]
    
    results = []
    
    for config in strategy_configs:
        print(f"\n运行 {config['name']} 策略...")
        
        # 修改策略代码中的参数
        modified_code = SAMPLE_STRATEGY_CODE.replace(
            "context.short_period = 5",
            f"context.short_period = {config['short_period']}"
        ).replace(
            "context.long_period = 20",
            f"context.long_period = {config['long_period']}"
        )
        
        # 创建策略
        strategy_repo = RepositoryFactory.get_strategy_repository()
        async with get_async_session() as session:
            strategy = await strategy_repo.create(
                session,
                name=f"双均线策略_{config['name']}",
                description=f"参数: {config['short_period']}-{config['long_period']}",
                code=modified_code,
                author_id=1,  # 假设用户ID为1
                universe=['000001.XSHE', '000002.XSHE', '600000.XSHG'],
                parameters=config
            )
        
        # 运行回测
        data_manager = DataSourceManager()
        mock_data_source = create_mock_data_source()
        data_manager.add_source("mock_wind", mock_data_source)
        data_manager.set_default_source("mock_wind")
        
        backtest_engine = BacktestEngine(data_manager)
        backtest_config = BacktestConfig(
            start_date=date(2023, 1, 1),
            end_date=date(2023, 3, 31),
            initial_capital=Decimal('1000000')
        )
        
        try:
            backtest_result = await backtest_engine.run_backtest(
                strategy=strategy,
                config=backtest_config,
                user_id=1,
                name=f"{config['name']}_对比回测"
            )
            
            # 生成报告
            reporter = BacktestReporter()
            report = await reporter.generate_report(backtest_result.id)
            
            results.append({
                'name': config['name'],
                'config': config,
                'result': backtest_result,
                'report': report
            })
            
            print(f"✅ {config['name']} 策略回测完成")
            
        except Exception as e:
            print(f"❌ {config['name']} 策略回测失败: {e}")
    
    # 对比结果
    if results:
        print("\n" + "=" * 80)
        print("策略对比结果")
        print("=" * 80)
        
        print(f"{'策略名称':<15} {'总收益率':<10} {'年化收益率':<12} {'最大回撤':<10} {'夏普比率':<10} {'交易次数':<8}")
        print("-" * 80)
        
        for result in results:
            metrics = result['report']['performance_metrics']
            trade_analysis = result['report']['trade_analysis']
            
            print(f"{result['name']:<15} "
                  f"{metrics['total_return_pct']:<10} "
                  f"{metrics['annual_return_pct']:<12} "
                  f"{metrics['max_drawdown_pct']:<10} "
                  f"{metrics['sharpe_ratio']:<10.2f} "
                  f"{trade_analysis['total_trades']:<8}")
        
        # 找出最佳策略
        best_strategy = max(results, key=lambda x: x['report']['performance_metrics']['sharpe_ratio'])
        print(f"\n🏆 最佳策略（按夏普比率）: {best_strategy['name']}")
        print(f"   夏普比率: {best_strategy['report']['performance_metrics']['sharpe_ratio']:.2f}")
        print(f"   总收益率: {best_strategy['report']['performance_metrics']['total_return_pct']}")


if __name__ == "__main__":
    # 运行单个回测示例
    asyncio.run(run_backtest_example())
    
    # 运行多策略对比示例
    # asyncio.run(run_multiple_backtest_example())