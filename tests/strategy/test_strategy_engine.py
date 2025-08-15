"""
策略引擎单元测试
"""

import pytest
import asyncio
from datetime import datetime, date
from unittest.mock import Mock, AsyncMock, patch

from quant_framework.strategy.engine import (
    StrategyValidator, StrategyExecutor, StrategyEngine
)
from quant_framework.database.models import Strategy
from quant_framework.data.base import DataSourceManager
from quant_framework.core.exceptions import StrategyError


class TestStrategyValidator:
    """策略验证器测试"""
    
    def setup_method(self):
        """测试前设置"""
        self.validator = StrategyValidator()
    
    def test_validate_valid_strategy(self):
        """测试验证有效策略"""
        valid_code = '''
def initialize(context):
    context.stock = '000001.XSHE'

def handle_data(context, data):
    context.order_target_percent(context.stock, 0.5)
'''
        
        result = self.validator.validate_strategy_code(valid_code)
        assert result is True
        assert len(self.validator.errors) == 0
    
    def test_validate_missing_functions(self):
        """测试缺少必需函数"""
        invalid_code = '''
def some_function():
    pass
'''
        
        result = self.validator.validate_strategy_code(invalid_code)
        assert result is False
        assert any('缺少必需函数' in error for error in self.validator.errors)
    
    def test_validate_wrong_function_signature(self):
        """测试错误的函数签名"""
        invalid_code = '''
def initialize():  # 缺少context参数
    pass

def handle_data(context):  # 缺少data参数
    pass
'''
        
        result = self.validator.validate_strategy_code(invalid_code)
        assert result is False
        assert any('initialize函数必须有且仅有一个参数' in error for error in self.validator.errors)
        assert any('handle_data函数必须有两个参数' in error for error in self.validator.errors)
    
    def test_validate_forbidden_functions(self):
        """测试禁止的函数"""
        invalid_code = '''
def initialize(context):
    exec("print('hello')")  # 禁止使用exec

def handle_data(context, data):
    eval("1+1")  # 禁止使用eval
'''
        
        result = self.validator.validate_strategy_code(invalid_code)
        assert result is False
        assert any('禁止调用函数 exec' in error for error in self.validator.errors)
        assert any('禁止调用函数 eval' in error for error in self.validator.errors)
    
    def test_validate_syntax_error(self):
        """测试语法错误"""
        invalid_code = '''
def initialize(context):
    if True  # 缺少冒号
        pass

def handle_data(context, data):
    pass
'''
        
        result = self.validator.validate_strategy_code(invalid_code)
        assert result is False
        assert any('语法错误' in error for error in self.validator.errors)
    
    def test_get_validation_result(self):
        """测试获取验证结果"""
        self.validator.errors = ['error1', 'error2']
        self.validator.warnings = ['warning1']
        
        result = self.validator.get_validation_result()
        
        assert result['is_valid'] is False
        assert result['errors'] == ['error1', 'error2']
        assert result['warnings'] == ['warning1']


class TestStrategyExecutor:
    """策略执行器测试"""
    
    def setup_method(self):
        """测试前设置"""
        self.data_manager = Mock(spec=DataSourceManager)
        self.executor = StrategyExecutor(self.data_manager)
    
    def test_prepare_execution_environment(self):
        """测试准备执行环境"""
        strategy = Strategy(
            id=1,
            name="测试策略",
            code="",
            author_id=1,
            parameters={'initial_cash': 500000.0},
            benchmark='000300.XSHG',
            universe=['000001.XSHE', '000002.XSHE']
        )
        
        with patch('quant_framework.strategy.engine.initialize_jq_api'):
            env = self.executor.prepare_execution_environment(strategy)
        
        assert 'context' in env
        assert 'g' in env
        assert 'get_price' in env
        assert self.executor.context is not None
        assert self.executor.context.benchmark == '000300.XSHG'
        assert self.executor.context.universe == ['000001.XSHE', '000002.XSHE']
    
    @pytest.mark.asyncio
    async def test_execute_strategy_function_success(self):
        """测试成功执行策略函数"""
        code = '''
def test_function(x, y):
    return x + y
'''
        
        # 准备环境
        self.executor.strategy_globals = {'__builtins__': {}}
        
        result = await self.executor.execute_strategy_function(
            code, 'test_function', 3, 5
        )
        
        assert result == 8
        assert self.executor.execution_stats['total_runs'] == 1
        assert self.executor.execution_stats['successful_runs'] == 1
    
    @pytest.mark.asyncio
    async def test_execute_strategy_function_error(self):
        """测试执行策略函数错误"""
        code = '''
def test_function():
    raise ValueError("测试错误")
'''
        
        self.executor.strategy_globals = {'__builtins__': {}}
        
        with pytest.raises(StrategyError):
            await self.executor.execute_strategy_function(code, 'test_function')
        
        assert self.executor.execution_stats['total_runs'] == 1
        assert self.executor.execution_stats['failed_runs'] == 1
    
    @pytest.mark.asyncio
    async def test_execute_nonexistent_function(self):
        """测试执行不存在的函数"""
        code = '''
def other_function():
    pass
'''
        
        self.executor.strategy_globals = {'__builtins__': {}}
        
        with pytest.raises(StrategyError, match="函数 test_function 未定义"):
            await self.executor.execute_strategy_function(code, 'test_function')
    
    def test_update_execution_stats(self):
        """测试更新执行统计"""
        # 测试成功执行
        self.executor._update_execution_stats(True, 1.5)
        
        assert self.executor.execution_stats['total_runs'] == 1
        assert self.executor.execution_stats['successful_runs'] == 1
        assert self.executor.execution_stats['failed_runs'] == 0
        assert self.executor.execution_stats['avg_execution_time'] == 1.5
        
        # 测试失败执行
        self.executor._update_execution_stats(False, 2.0)
        
        assert self.executor.execution_stats['total_runs'] == 2
        assert self.executor.execution_stats['successful_runs'] == 1
        assert self.executor.execution_stats['failed_runs'] == 1
        assert self.executor.execution_stats['avg_execution_time'] == 1.75
    
    def test_get_execution_stats(self):
        """测试获取执行统计"""
        self.executor.execution_stats['total_runs'] = 10
        self.executor.execution_stats['successful_runs'] = 8
        
        stats = self.executor.get_execution_stats()
        
        assert stats['total_runs'] == 10
        assert stats['successful_runs'] == 8
        assert isinstance(stats, dict)
    
    def test_reset_stats(self):
        """测试重置统计"""
        self.executor.execution_stats['total_runs'] = 10
        self.executor.execution_stats['successful_runs'] = 8
        
        self.executor.reset_stats()
        
        assert self.executor.execution_stats['total_runs'] == 0
        assert self.executor.execution_stats['successful_runs'] == 0


class TestStrategyEngine:
    """策略引擎测试"""
    
    def setup_method(self):
        """测试前设置"""
        self.data_manager = Mock(spec=DataSourceManager)
        self.engine = StrategyEngine(self.data_manager)
    
    @pytest.mark.asyncio
    async def test_validate_strategy_success(self):
        """测试策略验证成功"""
        strategy = Strategy(
            id=1,
            name="测试策略",
            code='''
def initialize(context):
    context.stock = '000001.XSHE'

def handle_data(context, data):
    pass
''',
            author_id=1
        )
        
        result = await self.engine.validate_strategy(strategy)
        
        assert result['is_valid'] is True
        assert len(result['errors']) == 0
    
    @pytest.mark.asyncio
    async def test_validate_strategy_failure(self):
        """测试策略验证失败"""
        strategy = Strategy(
            id=1,
            name="测试策略",
            code='''
def invalid_function():
    pass
''',
            author_id=1
        )
        
        result = await self.engine.validate_strategy(strategy)
        
        assert result['is_valid'] is False
        assert len(result['errors']) > 0
    
    @pytest.mark.asyncio
    async def test_initialize_strategy_success(self):
        """测试策略初始化成功"""
        strategy = Strategy(
            id=1,
            name="测试策略",
            code='''
def initialize(context):
    context.stock = '000001.XSHE'
    print("策略初始化")

def handle_data(context, data):
    pass
''',
            author_id=1
        )
        
        with patch('quant_framework.strategy.engine.initialize_jq_api'):
            result = await self.engine.initialize_strategy(strategy)
        
        assert result is True
        assert 1 in self.engine.running_strategies
        assert 1 in self.engine.strategy_contexts
        assert self.engine.engine_stats['total_strategies'] == 1
        assert self.engine.engine_stats['running_strategies'] == 1
    
    @pytest.mark.asyncio
    async def test_initialize_strategy_validation_failure(self):
        """测试策略初始化验证失败"""
        strategy = Strategy(
            id=1,
            name="测试策略",
            code='''
def invalid_function():
    pass
''',
            author_id=1
        )
        
        result = await self.engine.initialize_strategy(strategy)
        
        assert result is False
        assert 1 not in self.engine.running_strategies
        assert self.engine.engine_stats['failed_strategies'] == 1
    
    @pytest.mark.asyncio
    async def test_run_strategy_success(self):
        """测试运行策略成功"""
        strategy = Strategy(
            id=1,
            name="测试策略",
            code='''
def initialize(context):
    context.stock = '000001.XSHE'

def handle_data(context, data):
    print(f"处理数据: {context.current_dt}")
''',
            author_id=1
        )
        
        # 先初始化策略
        with patch('quant_framework.strategy.engine.initialize_jq_api'):
            await self.engine.initialize_strategy(strategy)
        
        # 运行策略
        current_date = date.today()
        market_data = {'000001.XSHE': {'last_price': 10.0}}
        
        result = await self.engine.run_strategy(1, current_date, market_data)
        
        assert result is True
        
        strategy_info = self.engine.running_strategies[1]
        assert strategy_info['run_count'] == 1
        assert strategy_info['status'] == 'running'
    
    @pytest.mark.asyncio
    async def test_run_strategy_not_initialized(self):
        """测试运行未初始化的策略"""
        current_date = date.today()
        
        result = await self.engine.run_strategy(999, current_date)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_stop_strategy_success(self):
        """测试停止策略成功"""
        strategy = Strategy(
            id=1,
            name="测试策略",
            code='''
def initialize(context):
    pass

def handle_data(context, data):
    pass
''',
            author_id=1
        )
        
        # 先初始化策略
        with patch('quant_framework.strategy.engine.initialize_jq_api'):
            await self.engine.initialize_strategy(strategy)
        
        # 停止策略
        result = await self.engine.stop_strategy(1)
        
        assert result is True
        assert 1 not in self.engine.running_strategies
        assert 1 not in self.engine.strategy_contexts
        assert self.engine.engine_stats['running_strategies'] == 0
        assert self.engine.engine_stats['completed_strategies'] == 1
    
    @pytest.mark.asyncio
    async def test_stop_strategy_not_running(self):
        """测试停止未运行的策略"""
        result = await self.engine.stop_strategy(999)
        
        assert result is False
    
    def test_get_strategy_status(self):
        """测试获取策略状态"""
        # 添加测试策略信息
        self.engine.running_strategies[1] = {
            'strategy': Mock(),
            'start_time': datetime.now(),
            'status': 'running',
            'run_count': 5,
            'errors': []
        }
        
        status = self.engine.get_strategy_status(1)
        
        assert status is not None
        assert status['status'] == 'running'
        assert status['run_count'] == 5
    
    def test_get_strategy_status_not_found(self):
        """测试获取不存在策略的状态"""
        status = self.engine.get_strategy_status(999)
        
        assert status is None
    
    def test_get_running_strategies(self):
        """测试获取运行中的策略"""
        # 添加测试策略
        strategy_info = {
            'strategy': Mock(),
            'start_time': datetime.now(),
            'status': 'running'
        }
        self.engine.running_strategies[1] = strategy_info
        self.engine.running_strategies[2] = strategy_info.copy()
        
        running_strategies = self.engine.get_running_strategies()
        
        assert len(running_strategies) == 2
    
    def test_get_strategy_context(self):
        """测试获取策略上下文"""
        # 添加测试上下文
        mock_context = Mock()
        self.engine.strategy_contexts[1] = mock_context
        
        context = self.engine.get_strategy_context(1)
        
        assert context is mock_context
    
    def test_get_strategy_context_not_found(self):
        """测试获取不存在策略的上下文"""
        context = self.engine.get_strategy_context(999)
        
        assert context is None
    
    def test_get_engine_statistics(self):
        """测试获取引擎统计"""
        self.engine.engine_stats['total_strategies'] = 5
        self.engine.engine_stats['running_strategies'] = 2
        
        stats = self.engine.get_engine_statistics()
        
        assert stats['total_strategies'] == 5
        assert stats['running_strategies'] == 2
        assert 'executor_stats' in stats
    
    @pytest.mark.asyncio
    async def test_cleanup(self):
        """测试清理资源"""
        # 添加运行中的策略
        strategy = Strategy(
            id=1,
            name="测试策略",
            code='''
def initialize(context):
    pass

def handle_data(context, data):
    pass
''',
            author_id=1
        )
        
        with patch('quant_framework.strategy.engine.initialize_jq_api'):
            await self.engine.initialize_strategy(strategy)
        
        # 执行清理
        await self.engine.cleanup()
        
        assert len(self.engine.running_strategies) == 0
        assert len(self.engine.strategy_contexts) == 0


@pytest.mark.asyncio
async def test_strategy_engine_integration():
    """策略引擎集成测试"""
    data_manager = Mock(spec=DataSourceManager)
    engine = StrategyEngine(data_manager)
    
    # 创建测试策略
    strategy = Strategy(
        id=1,
        name="集成测试策略",
        code='''
def initialize(context):
    context.stock = '000001.XSHE'
    context.counter = 0
    print("策略初始化完成")

def handle_data(context, data):
    context.counter += 1
    print(f"第{context.counter}次运行")
    
    if context.counter >= 3:
        print("策略运行完成")
''',
        author_id=1,
        parameters={'initial_cash': 1000000.0}
    )
    
    with patch('quant_framework.strategy.engine.initialize_jq_api'):
        # 1. 验证策略
        validation_result = await engine.validate_strategy(strategy)
        assert validation_result['is_valid'] is True
        
        # 2. 初始化策略
        init_result = await engine.initialize_strategy(strategy)
        assert init_result is True
        
        # 3. 运行策略多次
        for i in range(3):
            run_result = await engine.run_strategy(1, date.today())
            assert run_result is True
        
        # 4. 检查策略状态
        status = engine.get_strategy_status(1)
        assert status is not None
        assert status['run_count'] == 3
        
        # 5. 停止策略
        stop_result = await engine.stop_strategy(1)
        assert stop_result is True
        
        # 6. 清理资源
        await engine.cleanup()
        assert len(engine.running_strategies) == 0


if __name__ == '__main__':
    pytest.main([__file__])