"""
策略引擎核心实现
提供策略执行、验证和管理功能
"""

import ast
import sys
import traceback
import asyncio
from typing import Dict, Any, Optional, List, Callable, Set
from datetime import datetime, date
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
import importlib.util
import tempfile
import os

from quant_framework.core.constants import StrategyStatus, DataFrequency
from quant_framework.core.exceptions import StrategyError, ValidationError
from quant_framework.data.base import DataSourceManager
from quant_framework.jqcompat.context import JQCompatibleContext
from quant_framework.jqcompat.api import initialize_jq_api, get_jq_api
from quant_framework.database.models import Strategy
from quant_framework.utils.logger import LoggerMixin


class StrategyValidator(LoggerMixin):
    """策略代码验证器"""
    
    # 允许的模块和函数
    ALLOWED_MODULES = {
        'math', 'numpy', 'pandas', 'datetime', 'decimal', 'collections',
        'itertools', 'functools', 'operator', 'statistics', 'random'
    }
    
    # 禁止的函数和关键字
    FORBIDDEN_FUNCTIONS = {
        'exec', 'eval', 'compile', '__import__', 'open', 'file',
        'input', 'raw_input', 'reload', 'vars', 'locals', 'globals',
        'dir', 'hasattr', 'getattr', 'setattr', 'delattr'
    }
    
    # 禁止的AST节点类型
    FORBIDDEN_NODES = {
        ast.Import, ast.ImportFrom, ast.Exec, ast.Global, ast.Nonlocal
    }
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    def validate_strategy_code(self, code: str) -> bool:
        """
        验证策略代码安全性和正确性
        
        Args:
            code: 策略代码
            
        Returns:
            是否验证通过
        """
        self.errors.clear()
        self.warnings.clear()
        
        try:
            # 解析AST
            tree = ast.parse(code)
            
            # 检查AST节点
            self._check_ast_nodes(tree)
            
            # 检查函数定义
            self._check_function_definitions(tree)
            
            # 检查导入语句
            self._check_imports(tree)
            
            # 检查禁止的函数调用
            self._check_forbidden_calls(tree)
            
            # 语法检查
            compile(code, '<strategy>', 'exec')
            
            return len(self.errors) == 0
            
        except SyntaxError as e:
            self.errors.append(f"语法错误: {e}")
            return False
        except Exception as e:
            self.errors.append(f"验证失败: {e}")
            return False
    
    def _check_ast_nodes(self, tree: ast.AST):
        """检查AST节点"""
        for node in ast.walk(tree):
            if type(node) in self.FORBIDDEN_NODES:
                self.errors.append(f"禁止使用 {type(node).__name__}")
    
    def _check_function_definitions(self, tree: ast.AST):
        """检查函数定义"""
        required_functions = {'initialize', 'handle_data'}
        found_functions = set()
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                found_functions.add(node.name)
                
                # 检查函数参数
                if node.name == 'initialize':
                    if len(node.args.args) != 1:
                        self.errors.append("initialize函数必须有且仅有一个参数(context)")
                
                elif node.name == 'handle_data':
                    if len(node.args.args) != 2:
                        self.errors.append("handle_data函数必须有两个参数(context, data)")
        
        # 检查必需函数
        missing_functions = required_functions - found_functions
        if missing_functions:
            self.errors.append(f"缺少必需函数: {', '.join(missing_functions)}")
    
    def _check_imports(self, tree: ast.AST):
        """检查导入语句"""
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name not in self.ALLOWED_MODULES:
                        self.warnings.append(f"导入模块 {alias.name} 可能不安全")
            
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module not in self.ALLOWED_MODULES:
                    self.warnings.append(f"从模块 {node.module} 导入可能不安全")
    
    def _check_forbidden_calls(self, tree: ast.AST):
        """检查禁止的函数调用"""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in self.FORBIDDEN_FUNCTIONS:
                        self.errors.append(f"禁止调用函数 {node.func.id}")
    
    def get_validation_result(self) -> Dict[str, Any]:
        """获取验证结果"""
        return {
            'is_valid': len(self.errors) == 0,
            'errors': self.errors.copy(),
            'warnings': self.warnings.copy()
        }


class StrategyExecutor(LoggerMixin):
    """策略执行器"""
    
    def __init__(self, data_manager: DataSourceManager):
        self.data_manager = data_manager
        self.context: Optional[JQCompatibleContext] = None
        self.strategy_globals: Dict[str, Any] = {}
        self.execution_stats = {
            'total_runs': 0,
            'successful_runs': 0,
            'failed_runs': 0,
            'last_run_time': None,
            'avg_execution_time': 0.0
        }
    
    def prepare_execution_environment(self, strategy: Strategy) -> Dict[str, Any]:
        """
        准备策略执行环境
        
        Args:
            strategy: 策略对象
            
        Returns:
            执行环境字典
        """
        try:
            # 创建上下文
            initial_cash = strategy.get_parameter('initial_cash', 1000000.0)
            self.context = JQCompatibleContext(initial_cash)
            
            # 设置策略参数
            self.context.options = strategy.parameters or {}
            self.context.benchmark = strategy.benchmark
            self.context.universe = strategy.universe or []
            
            # 初始化聚宽API
            initialize_jq_api(self.data_manager)
            
            # 准备全局环境
            self.strategy_globals = {
                # 基础模块
                '__builtins__': {
                    'len': len, 'range': range, 'enumerate': enumerate,
                    'zip': zip, 'map': map, 'filter': filter,
                    'sum': sum, 'min': min, 'max': max, 'abs': abs,
                    'round': round, 'int': int, 'float': float, 'str': str,
                    'bool': bool, 'list': list, 'dict': dict, 'set': set,
                    'tuple': tuple, 'print': print
                },
                
                # 聚宽兼容API
                'get_price': get_jq_api().get_price,
                'get_fundamentals': get_jq_api().get_fundamentals,
                'get_current_data': get_jq_api().get_current_data,
                'attribute_history': get_jq_api().attribute_history,
                'get_security_info': get_jq_api().get_security_info,
                
                # 上下文对象
                'g': self.context,
                'context': self.context,
                
                # 常用模块
                'datetime': __import__('datetime'),
                'math': __import__('math'),
                'pd': __import__('pandas'),
                'np': __import__('numpy'),
            }
            
            self.logger.info(
                "Strategy execution environment prepared",
                strategy_id=strategy.id,
                initial_cash=initial_cash
            )
            
            return self.strategy_globals
            
        except Exception as e:
            self.log_error(e, {
                "method": "prepare_execution_environment",
                "strategy_id": strategy.id
            })
            raise StrategyError(f"准备执行环境失败: {e}")
    
    async def execute_strategy_function(
        self,
        code: str,
        function_name: str,
        *args,
        **kwargs
    ) -> Any:
        """
        执行策略函数
        
        Args:
            code: 策略代码
            function_name: 函数名
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            函数执行结果
        """
        start_time = datetime.now()
        
        try:
            # 编译代码
            compiled_code = compile(code, '<strategy>', 'exec')
            
            # 执行代码以定义函数
            exec(compiled_code, self.strategy_globals)
            
            # 获取函数
            if function_name not in self.strategy_globals:
                raise StrategyError(f"函数 {function_name} 未定义")
            
            strategy_function = self.strategy_globals[function_name]
            
            # 捕获输出
            stdout_capture = StringIO()
            stderr_capture = StringIO()
            
            result = None
            
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                # 执行函数
                if asyncio.iscoroutinefunction(strategy_function):
                    result = await strategy_function(*args, **kwargs)
                else:
                    result = strategy_function(*args, **kwargs)
            
            # 记录输出
            stdout_output = stdout_capture.getvalue()
            stderr_output = stderr_capture.getvalue()
            
            if stdout_output:
                self.logger.info("Strategy output", output=stdout_output.strip())
            
            if stderr_output:
                self.logger.warning("Strategy stderr", stderr=stderr_output.strip())
            
            # 更新统计
            execution_time = (datetime.now() - start_time).total_seconds()
            self._update_execution_stats(True, execution_time)
            
            return result
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            self._update_execution_stats(False, execution_time)
            
            self.log_error(e, {
                "method": "execute_strategy_function",
                "function_name": function_name,
                "execution_time": execution_time
            })
            
            raise StrategyError(f"执行策略函数 {function_name} 失败: {e}")
    
    def _update_execution_stats(self, success: bool, execution_time: float):
        """更新执行统计"""
        self.execution_stats['total_runs'] += 1
        self.execution_stats['last_run_time'] = datetime.now()
        
        if success:
            self.execution_stats['successful_runs'] += 1
        else:
            self.execution_stats['failed_runs'] += 1
        
        # 更新平均执行时间
        total_time = (self.execution_stats['avg_execution_time'] * 
                     (self.execution_stats['total_runs'] - 1) + execution_time)
        self.execution_stats['avg_execution_time'] = total_time / self.execution_stats['total_runs']
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """获取执行统计"""
        return self.execution_stats.copy()
    
    def reset_stats(self):
        """重置统计"""
        self.execution_stats = {
            'total_runs': 0,
            'successful_runs': 0,
            'failed_runs': 0,
            'last_run_time': None,
            'avg_execution_time': 0.0
        }


class StrategyEngine(LoggerMixin):
    """策略引擎"""
    
    def __init__(self, data_manager: DataSourceManager):
        self.data_manager = data_manager
        self.validator = StrategyValidator()
        self.executor = StrategyExecutor(data_manager)
        
        # 策略实例管理
        self.running_strategies: Dict[int, Dict[str, Any]] = {}
        self.strategy_contexts: Dict[int, JQCompatibleContext] = {}
        
        # 执行统计
        self.engine_stats = {
            'total_strategies': 0,
            'running_strategies': 0,
            'completed_strategies': 0,
            'failed_strategies': 0
        }
    
    async def validate_strategy(self, strategy: Strategy) -> Dict[str, Any]:
        """
        验证策略
        
        Args:
            strategy: 策略对象
            
        Returns:
            验证结果
        """
        try:
            self.logger.info("Validating strategy", strategy_id=strategy.id, name=strategy.name)
            
            # 代码验证
            is_valid = self.validator.validate_strategy_code(strategy.code)
            result = self.validator.get_validation_result()
            
            # 尝试编译测试
            if is_valid:
                try:
                    compile(strategy.code, f'<strategy_{strategy.id}>', 'exec')
                except SyntaxError as e:
                    result['is_valid'] = False
                    result['errors'].append(f"编译错误: {e}")
            
            self.logger.info(
                "Strategy validation completed",
                strategy_id=strategy.id,
                is_valid=result['is_valid'],
                error_count=len(result['errors']),
                warning_count=len(result['warnings'])
            )
            
            return result
            
        except Exception as e:
            self.log_error(e, {
                "method": "validate_strategy",
                "strategy_id": strategy.id
            })
            return {
                'is_valid': False,
                'errors': [f"验证过程中发生错误: {e}"],
                'warnings': []
            }
    
    async def initialize_strategy(self, strategy: Strategy) -> bool:
        """
        初始化策略
        
        Args:
            strategy: 策略对象
            
        Returns:
            是否初始化成功
        """
        try:
            self.logger.info("Initializing strategy", strategy_id=strategy.id, name=strategy.name)
            
            # 验证策略
            validation_result = await self.validate_strategy(strategy)
            if not validation_result['is_valid']:
                raise StrategyError(f"策略验证失败: {validation_result['errors']}")
            
            # 准备执行环境
            self.executor.prepare_execution_environment(strategy)
            
            # 执行initialize函数
            await self.executor.execute_strategy_function(
                strategy.code,
                'initialize',
                self.executor.context
            )
            
            # 保存策略上下文
            self.strategy_contexts[strategy.id] = self.executor.context
            
            # 记录运行状态
            self.running_strategies[strategy.id] = {
                'strategy': strategy,
                'start_time': datetime.now(),
                'status': 'initialized',
                'run_count': 0,
                'last_run_time': None,
                'errors': []
            }
            
            # 更新统计
            self.engine_stats['total_strategies'] += 1
            self.engine_stats['running_strategies'] += 1
            
            self.logger.info("Strategy initialized successfully", strategy_id=strategy.id)
            
            return True
            
        except Exception as e:
            self.log_error(e, {
                "method": "initialize_strategy",
                "strategy_id": strategy.id
            })
            
            # 记录失败
            self.engine_stats['failed_strategies'] += 1
            
            return False
    
    async def run_strategy(
        self,
        strategy_id: int,
        current_date: date,
        market_data: Dict[str, Any] = None
    ) -> bool:
        """
        运行策略
        
        Args:
            strategy_id: 策略ID
            current_date: 当前日期
            market_data: 市场数据
            
        Returns:
            是否运行成功
        """
        try:
            if strategy_id not in self.running_strategies:
                raise StrategyError(f"策略 {strategy_id} 未初始化")
            
            strategy_info = self.running_strategies[strategy_id]
            strategy = strategy_info['strategy']
            context = self.strategy_contexts[strategy_id]
            
            # 更新上下文
            context.current_dt = datetime.combine(current_date, datetime.min.time())
            context.previous_date = current_date
            
            # 设置当前数据
            if market_data:
                context.set_current_data(market_data)
            
            self.logger.debug(
                "Running strategy",
                strategy_id=strategy_id,
                current_date=current_date
            )
            
            # 执行handle_data函数
            await self.executor.execute_strategy_function(
                strategy.code,
                'handle_data',
                context,
                market_data or {}
            )
            
            # 更新运行状态
            strategy_info['run_count'] += 1
            strategy_info['last_run_time'] = datetime.now()
            strategy_info['status'] = 'running'
            
            return True
            
        except Exception as e:
            self.log_error(e, {
                "method": "run_strategy",
                "strategy_id": strategy_id,
                "current_date": current_date
            })
            
            # 记录错误
            if strategy_id in self.running_strategies:
                self.running_strategies[strategy_id]['errors'].append({
                    'time': datetime.now(),
                    'error': str(e),
                    'traceback': traceback.format_exc()
                })
            
            return False
    
    async def stop_strategy(self, strategy_id: int) -> bool:
        """
        停止策略
        
        Args:
            strategy_id: 策略ID
            
        Returns:
            是否停止成功
        """
        try:
            if strategy_id not in self.running_strategies:
                return False
            
            strategy_info = self.running_strategies[strategy_id]
            
            # 更新状态
            strategy_info['status'] = 'stopped'
            strategy_info['stop_time'] = datetime.now()
            
            # 从运行列表中移除
            del self.running_strategies[strategy_id]
            
            # 清理上下文
            if strategy_id in self.strategy_contexts:
                del self.strategy_contexts[strategy_id]
            
            # 更新统计
            self.engine_stats['running_strategies'] -= 1
            self.engine_stats['completed_strategies'] += 1
            
            self.logger.info("Strategy stopped", strategy_id=strategy_id)
            
            return True
            
        except Exception as e:
            self.log_error(e, {
                "method": "stop_strategy",
                "strategy_id": strategy_id
            })
            return False
    
    def get_strategy_status(self, strategy_id: int) -> Optional[Dict[str, Any]]:
        """获取策略状态"""
        return self.running_strategies.get(strategy_id)
    
    def get_running_strategies(self) -> List[Dict[str, Any]]:
        """获取所有运行中的策略"""
        return list(self.running_strategies.values())
    
    def get_strategy_context(self, strategy_id: int) -> Optional[JQCompatibleContext]:
        """获取策略上下文"""
        return self.strategy_contexts.get(strategy_id)
    
    def get_engine_statistics(self) -> Dict[str, Any]:
        """获取引擎统计信息"""
        return {
            **self.engine_stats,
            'executor_stats': self.executor.get_execution_stats()
        }
    
    async def cleanup(self):
        """清理资源"""
        try:
            # 停止所有运行中的策略
            strategy_ids = list(self.running_strategies.keys())
            for strategy_id in strategy_ids:
                await self.stop_strategy(strategy_id)
            
            # 重置统计
            self.executor.reset_stats()
            
            self.logger.info("Strategy engine cleanup completed")
            
        except Exception as e:
            self.log_error(e, {"method": "cleanup"})