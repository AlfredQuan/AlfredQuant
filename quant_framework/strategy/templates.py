"""
策略模板
提供常用的策略模板和示例代码
"""

from typing import Dict, List, Any
from datetime import datetime


class StrategyTemplate:
    """策略模板基类"""
    
    def __init__(self, name: str, description: str, code: str, parameters: Dict[str, Any] = None):
        self.name = name
        self.description = description
        self.code = code
        self.parameters = parameters or {}
    
    def get_template_info(self) -> Dict[str, Any]:
        """获取模板信息"""
        return {
            'name': self.name,
            'description': self.description,
            'parameters': self.parameters
        }


# 基础策略模板
BASIC_STRATEGY_TEMPLATE = StrategyTemplate(
    name="基础策略模板",
    description="包含基本结构的策略模板",
    code='''
# 基础策略模板
# 包含initialize和handle_data两个必需函数

def initialize(context):
    """
    初始化函数，在策略开始时调用一次
    
    Args:
        context: 策略上下文对象
    """
    # 设置基准
    context.set_benchmark('000300.XSHG')
    
    # 设置股票池
    context.set_universe(['000001.XSHE', '000002.XSHE', '600000.XSHG'])
    
    # 策略参数
    context.max_position_count = 10  # 最大持仓数量
    context.rebalance_period = 20    # 调仓周期（天）
    
    # 初始化计数器
    context.day_count = 0
    
    print("策略初始化完成")


def handle_data(context, data):
    """
    数据处理函数，每个交易日调用一次
    
    Args:
        context: 策略上下文对象
        data: 当日市场数据
    """
    context.day_count += 1
    
    # 每隔一定周期调仓
    if context.day_count % context.rebalance_period == 0:
        rebalance(context, data)


def rebalance(context, data):
    """
    调仓函数
    
    Args:
        context: 策略上下文对象
        data: 当日市场数据
    """
    # 获取当前持仓
    current_positions = list(context.portfolio.positions.keys())
    
    # 简单的等权重配置
    target_stocks = context.universe[:context.max_position_count]
    target_weight = 1.0 / len(target_stocks)
    
    # 调整持仓
    for stock in target_stocks:
        context.order_target_percent(stock, target_weight)
    
    # 清仓不在目标股票池中的股票
    for stock in current_positions:
        if stock not in target_stocks:
            context.order_target_percent(stock, 0)
    
    print(f"第{context.day_count}天调仓完成，目标股票: {target_stocks}")
''',
    parameters={
        'max_position_count': {'type': 'int', 'default': 10, 'description': '最大持仓数量'},
        'rebalance_period': {'type': 'int', 'default': 20, 'description': '调仓周期（天）'}
    }
)


# 均线策略模板
MA_STRATEGY_TEMPLATE = StrategyTemplate(
    name="双均线策略",
    description="基于双均线交叉的经典策略",
    code='''
# 双均线策略
# 当短期均线上穿长期均线时买入，下穿时卖出

def initialize(context):
    """初始化函数"""
    # 设置基准
    context.set_benchmark('000300.XSHG')
    
    # 策略参数
    context.stock = '000001.XSHE'  # 交易股票
    context.short_period = 5       # 短期均线周期
    context.long_period = 20       # 长期均线周期
    
    print(f"双均线策略初始化: 短期={context.short_period}日, 长期={context.long_period}日")


def handle_data(context, data):
    """数据处理函数"""
    stock = context.stock
    
    # 获取历史价格数据
    hist_data = attribute_history(
        stock, 
        context.long_period + 1, 
        '1d', 
        ['close']
    )
    
    if len(hist_data) < context.long_period:
        return
    
    # 计算均线
    short_ma = hist_data['close'][-context.short_period:].mean()
    long_ma = hist_data['close'][-context.long_period:].mean()
    
    # 获取前一日均线
    prev_short_ma = hist_data['close'][-(context.short_period+1):-1].mean()
    prev_long_ma = hist_data['close'][-(context.long_period+1):-1].mean()
    
    # 获取当前持仓
    current_position = context.portfolio.positions.get(stock)
    current_quantity = current_position.total_amount if current_position else 0
    
    # 交易信号
    if prev_short_ma <= prev_long_ma and short_ma > long_ma:
        # 金叉：买入
        if current_quantity == 0:
            context.order_target_percent(stock, 0.95)
            print(f"金叉买入信号: 短期均线={short_ma:.2f}, 长期均线={long_ma:.2f}")
    
    elif prev_short_ma >= prev_long_ma and short_ma < long_ma:
        # 死叉：卖出
        if current_quantity > 0:
            context.order_target_percent(stock, 0)
            print(f"死叉卖出信号: 短期均线={short_ma:.2f}, 长期均线={long_ma:.2f}")
''',
    parameters={
        'stock': {'type': 'str', 'default': '000001.XSHE', 'description': '交易股票代码'},
        'short_period': {'type': 'int', 'default': 5, 'description': '短期均线周期'},
        'long_period': {'type': 'int', 'default': 20, 'description': '长期均线周期'}
    }
)


# RSI策略模板
RSI_STRATEGY_TEMPLATE = StrategyTemplate(
    name="RSI超买超卖策略",
    description="基于RSI指标的超买超卖策略",
    code='''
# RSI超买超卖策略
# 当RSI低于超卖线时买入，高于超买线时卖出

import numpy as np

def initialize(context):
    """初始化函数"""
    # 设置基准
    context.set_benchmark('000300.XSHG')
    
    # 策略参数
    context.stock = '000001.XSHE'  # 交易股票
    context.rsi_period = 14        # RSI计算周期
    context.oversold_line = 30     # 超卖线
    context.overbought_line = 70   # 超买线
    
    print(f"RSI策略初始化: 周期={context.rsi_period}, 超卖线={context.oversold_line}, 超买线={context.overbought_line}")


def handle_data(context, data):
    """数据处理函数"""
    stock = context.stock
    
    # 获取历史价格数据
    hist_data = attribute_history(
        stock, 
        context.rsi_period + 10, 
        '1d', 
        ['close']
    )
    
    if len(hist_data) < context.rsi_period + 1:
        return
    
    # 计算RSI
    rsi = calculate_rsi(hist_data['close'], context.rsi_period)
    current_rsi = rsi[-1]
    
    # 获取当前持仓
    current_position = context.portfolio.positions.get(stock)
    current_quantity = current_position.total_amount if current_position else 0
    
    # 交易信号
    if current_rsi < context.oversold_line and current_quantity == 0:
        # 超卖买入
        context.order_target_percent(stock, 0.95)
        print(f"RSI超卖买入: RSI={current_rsi:.2f}")
    
    elif current_rsi > context.overbought_line and current_quantity > 0:
        # 超买卖出
        context.order_target_percent(stock, 0)
        print(f"RSI超买卖出: RSI={current_rsi:.2f}")


def calculate_rsi(prices, period):
    """
    计算RSI指标
    
    Args:
        prices: 价格序列
        period: 计算周期
        
    Returns:
        RSI值序列
    """
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    
    avg_gains = np.convolve(gains, np.ones(period)/period, mode='valid')
    avg_losses = np.convolve(losses, np.ones(period)/period, mode='valid')
    
    rs = avg_gains / (avg_losses + 1e-10)  # 避免除零
    rsi = 100 - (100 / (1 + rs))
    
    return rsi
''',
    parameters={
        'stock': {'type': 'str', 'default': '000001.XSHE', 'description': '交易股票代码'},
        'rsi_period': {'type': 'int', 'default': 14, 'description': 'RSI计算周期'},
        'oversold_line': {'type': 'int', 'default': 30, 'description': '超卖线'},
        'overbought_line': {'type': 'int', 'default': 70, 'description': '超买线'}
    }
)


# 布林带策略模板
BOLLINGER_STRATEGY_TEMPLATE = StrategyTemplate(
    name="布林带策略",
    description="基于布林带的均值回归策略",
    code='''
# 布林带策略
# 当价格触及下轨时买入，触及上轨时卖出

import numpy as np

def initialize(context):
    """初始化函数"""
    # 设置基准
    context.set_benchmark('000300.XSHG')
    
    # 策略参数
    context.stock = '000001.XSHE'  # 交易股票
    context.period = 20            # 布林带周期
    context.std_multiplier = 2.0   # 标准差倍数
    
    print(f"布林带策略初始化: 周期={context.period}, 标准差倍数={context.std_multiplier}")


def handle_data(context, data):
    """数据处理函数"""
    stock = context.stock
    
    # 获取历史价格数据
    hist_data = attribute_history(
        stock, 
        context.period + 1, 
        '1d', 
        ['close']
    )
    
    if len(hist_data) < context.period:
        return
    
    # 计算布林带
    prices = hist_data['close']
    middle_band = prices.rolling(context.period).mean().iloc[-1]
    std = prices.rolling(context.period).std().iloc[-1]
    
    upper_band = middle_band + context.std_multiplier * std
    lower_band = middle_band - context.std_multiplier * std
    
    current_price = prices.iloc[-1]
    
    # 获取当前持仓
    current_position = context.portfolio.positions.get(stock)
    current_quantity = current_position.total_amount if current_position else 0
    
    # 交易信号
    if current_price <= lower_band and current_quantity == 0:
        # 触及下轨买入
        context.order_target_percent(stock, 0.95)
        print(f"触及下轨买入: 价格={current_price:.2f}, 下轨={lower_band:.2f}")
    
    elif current_price >= upper_band and current_quantity > 0:
        # 触及上轨卖出
        context.order_target_percent(stock, 0)
        print(f"触及上轨卖出: 价格={current_price:.2f}, 上轨={upper_band:.2f}")
    
    elif current_price >= middle_band and current_quantity > 0:
        # 回归中轨部分卖出
        context.order_target_percent(stock, 0.5)
        print(f"回归中轨减仓: 价格={current_price:.2f}, 中轨={middle_band:.2f}")
''',
    parameters={
        'stock': {'type': 'str', 'default': '000001.XSHE', 'description': '交易股票代码'},
        'period': {'type': 'int', 'default': 20, 'description': '布林带周期'},
        'std_multiplier': {'type': 'float', 'default': 2.0, 'description': '标准差倍数'}
    }
)


# 多因子选股策略模板
MULTI_FACTOR_STRATEGY_TEMPLATE = StrategyTemplate(
    name="多因子选股策略",
    description="基于多个因子的股票选择策略",
    code='''
# 多因子选股策略
# 综合多个因子对股票进行评分和选择

def initialize(context):
    """初始化函数"""
    # 设置基准
    context.set_benchmark('000300.XSHG')
    
    # 策略参数
    context.stock_pool = [
        '000001.XSHE', '000002.XSHE', '000858.XSHE', '002415.XSHE',
        '600000.XSHG', '600036.XSHG', '600519.XSHG', '600887.XSHG'
    ]
    context.max_positions = 5      # 最大持仓数量
    context.rebalance_period = 10  # 调仓周期
    
    # 因子权重
    context.factor_weights = {
        'momentum': 0.3,    # 动量因子
        'value': 0.3,       # 价值因子
        'quality': 0.2,     # 质量因子
        'volatility': 0.2   # 波动率因子
    }
    
    context.day_count = 0
    
    print("多因子选股策略初始化完成")


def handle_data(context, data):
    """数据处理函数"""
    context.day_count += 1
    
    # 定期调仓
    if context.day_count % context.rebalance_period == 0:
        rebalance(context, data)


def rebalance(context, data):
    """调仓函数"""
    # 计算股票评分
    stock_scores = {}
    
    for stock in context.stock_pool:
        try:
            score = calculate_stock_score(context, stock)
            stock_scores[stock] = score
        except Exception as e:
            print(f"计算{stock}评分失败: {e}")
            continue
    
    # 按评分排序选择股票
    sorted_stocks = sorted(stock_scores.items(), key=lambda x: x[1], reverse=True)
    selected_stocks = [stock for stock, score in sorted_stocks[:context.max_positions]]
    
    # 等权重配置
    target_weight = 1.0 / len(selected_stocks) if selected_stocks else 0
    
    # 调整持仓
    for stock in context.stock_pool:
        if stock in selected_stocks:
            context.order_target_percent(stock, target_weight)
        else:
            context.order_target_percent(stock, 0)
    
    print(f"第{context.day_count}天调仓: 选中股票{selected_stocks}")


def calculate_stock_score(context, stock):
    """
    计算股票综合评分
    
    Args:
        context: 策略上下文
        stock: 股票代码
        
    Returns:
        综合评分
    """
    # 获取历史数据
    hist_data = attribute_history(stock, 60, '1d', ['close', 'volume'])
    
    if len(hist_data) < 30:
        return 0
    
    # 动量因子（20日收益率）
    momentum_score = (hist_data['close'].iloc[-1] / hist_data['close'].iloc[-21] - 1) * 100
    
    # 价值因子（简化为价格相对位置）
    price_position = (hist_data['close'].iloc[-1] - hist_data['close'].min()) / (hist_data['close'].max() - hist_data['close'].min())
    value_score = (1 - price_position) * 100  # 价格越低价值越高
    
    # 质量因子（价格稳定性）
    price_std = hist_data['close'].pct_change().std()
    quality_score = (1 / (price_std + 0.01)) * 10  # 波动越小质量越高
    
    # 波动率因子
    volatility = hist_data['close'].pct_change().std() * 100
    volatility_score = max(0, 50 - volatility)  # 适中波动率得分高
    
    # 综合评分
    total_score = (
        momentum_score * context.factor_weights['momentum'] +
        value_score * context.factor_weights['value'] +
        quality_score * context.factor_weights['quality'] +
        volatility_score * context.factor_weights['volatility']
    )
    
    return total_score
''',
    parameters={
        'max_positions': {'type': 'int', 'default': 5, 'description': '最大持仓数量'},
        'rebalance_period': {'type': 'int', 'default': 10, 'description': '调仓周期（天）'},
        'momentum_weight': {'type': 'float', 'default': 0.3, 'description': '动量因子权重'},
        'value_weight': {'type': 'float', 'default': 0.3, 'description': '价值因子权重'},
        'quality_weight': {'type': 'float', 'default': 0.2, 'description': '质量因子权重'},
        'volatility_weight': {'type': 'float', 'default': 0.2, 'description': '波动率因子权重'}
    }
)


class StrategyTemplateManager:
    """策略模板管理器"""
    
    def __init__(self):
        self.templates = {
            'basic': BASIC_STRATEGY_TEMPLATE,
            'ma_cross': MA_STRATEGY_TEMPLATE,
            'rsi': RSI_STRATEGY_TEMPLATE,
            'bollinger': BOLLINGER_STRATEGY_TEMPLATE,
            'multi_factor': MULTI_FACTOR_STRATEGY_TEMPLATE
        }
    
    def get_template(self, template_name: str) -> StrategyTemplate:
        """获取策略模板"""
        if template_name not in self.templates:
            raise ValueError(f"未知的策略模板: {template_name}")
        
        return self.templates[template_name]
    
    def list_templates(self) -> List[Dict[str, Any]]:
        """列出所有模板"""
        return [
            {
                'name': name,
                'info': template.get_template_info()
            }
            for name, template in self.templates.items()
        ]
    
    def create_strategy_from_template(
        self,
        template_name: str,
        strategy_name: str,
        parameters: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """从模板创建策略"""
        template = self.get_template(template_name)
        
        # 合并参数
        final_parameters = template.parameters.copy()
        if parameters:
            for key, value in parameters.items():
                if key in final_parameters:
                    final_parameters[key]['default'] = value
        
        return {
            'name': strategy_name,
            'description': f"基于{template.name}创建的策略",
            'code': template.code,
            'parameters': final_parameters
        }
    
    def add_template(self, name: str, template: StrategyTemplate):
        """添加自定义模板"""
        self.templates[name] = template
    
    def remove_template(self, name: str) -> bool:
        """移除模板"""
        if name in self.templates:
            del self.templates[name]
            return True
        return False


# 全局模板管理器实例
template_manager = StrategyTemplateManager()


def get_template_manager() -> StrategyTemplateManager:
    """获取模板管理器实例"""
    return template_manager