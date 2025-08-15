"""
回测相关的异步任务
"""

from typing import Dict, Any, Optional
from datetime import datetime
from celery import current_task
from celery.exceptions import Retry

from .celery_app import celery_app
from .task_models import TaskStatus, TaskProgress
from ..core.database import get_db_session
from ..models.strategy import Strategy
from ..models.backtest import Backtest
from ..backtest.engine import BacktestEngine
from ..backtest.report import BacktestReportGenerator
from ..strategy.validator import StrategyValidator
from ..core.exceptions import BacktestError, StrategyError
import logging
import traceback

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name='run_backtest_task')
def run_backtest_task(
    self,
    backtest_id: int,
    strategy_id: int,
    start_date: str,
    end_date: str,
    initial_capital: float,
    benchmark: Optional[str] = None,
    commission_rate: float = 0.0003,
    slippage_rate: float = 0.001,
    frequency: str = '1d'
) -> Dict[str, Any]:
    """运行回测任务"""
    
    task_id = self.request.id
    logger.info(f"Starting backtest task {task_id} for backtest {backtest_id}")
    
    try:
        with get_db_session() as db:
            # 更新任务状态
            self.update_state(
                state=TaskStatus.STARTED,
                meta={'progress': 0, 'message': '初始化回测环境...'}
            )
            
            # 获取策略和回测信息
            strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
            backtest = db.query(Backtest).filter(Backtest.id == backtest_id).first()
            
            if not strategy:
                raise StrategyError(f"策略不存在: {strategy_id}")
            
            if not backtest:
                raise BacktestError(f"回测不存在: {backtest_id}")
            
            # 更新回测状态
            backtest.status = 'running'
            backtest.started_at = datetime.utcnow()
            db.commit()
            
            # 创建回测引擎
            backtest_engine = BacktestEngine()
            
            # 设置回测参数
            backtest_config = {
                'start_date': start_date,
                'end_date': end_date,
                'initial_capital': initial_capital,
                'benchmark': benchmark,
                'commission_rate': commission_rate,
                'slippage_rate': slippage_rate,
                'frequency': frequency
            }
            
            # 进度回调函数
            def progress_callback(progress: float, message: str = None):
                self.update_state(
                    state=TaskStatus.PROGRESS,
                    meta={
                        'progress': progress,
                        'message': message or f'回测进行中... {progress:.1f}%'
                    }
                )
            
            # 执行回测
            self.update_state(
                state=TaskStatus.PROGRESS,
                meta={'progress': 10, 'message': '加载策略代码...'}
            )
            
            # 运行回测
            result = backtest_engine.run_backtest(
                strategy_code=strategy.code,
                config=backtest_config,
                progress_callback=progress_callback
            )
            
            # 生成回测报告
            self.update_state(
                state=TaskStatus.PROGRESS,
                meta={'progress': 90, 'message': '生成回测报告...'}
            )
            
            report_generator = BacktestReportGenerator()
            report = report_generator.generate_report(result)
            
            # 更新回测结果
            backtest.status = 'completed'
            backtest.completed_at = datetime.utcnow()
            backtest.final_value = result.get('final_value')
            backtest.total_return = result.get('total_return')
            backtest.annual_return = result.get('annual_return')
            backtest.max_drawdown = result.get('max_drawdown')
            backtest.sharpe_ratio = result.get('sharpe_ratio')
            backtest.volatility = result.get('volatility')
            backtest.beta = result.get('beta')
            backtest.alpha = result.get('alpha')
            backtest.total_trades = result.get('total_trades')
            backtest.profitable_trades = result.get('profitable_trades')
            backtest.win_rate = result.get('win_rate')
            
            db.commit()
            
            # 完成任务
            self.update_state(
                state=TaskStatus.SUCCESS,
                meta={
                    'progress': 100,
                    'message': '回测完成',
                    'result': {
                        'backtest_id': backtest_id,
                        'performance': result,
                        'report': report
                    }
                }
            )
            
            logger.info(f"Backtest task {task_id} completed successfully")
            
            return {
                'backtest_id': backtest_id,
                'status': 'completed',
                'performance': result,
                'report': report
            }
            
    except Exception as e:
        error_msg = str(e)
        error_traceback = traceback.format_exc()
        
        logger.error(f"Backtest task {task_id} failed: {error_msg}")
        logger.error(f"Traceback: {error_traceback}")
        
        # 更新回测状态为失败
        try:
            with get_db_session() as db:
                backtest = db.query(Backtest).filter(Backtest.id == backtest_id).first()
                if backtest:
                    backtest.status = 'failed'
                    backtest.completed_at = datetime.utcnow()
                    db.commit()
        except Exception as db_error:
            logger.error(f"Failed to update backtest status: {db_error}")
        
        # 更新任务状态
        self.update_state(
            state=TaskStatus.FAILURE,
            meta={
                'progress': 0,
                'message': f'回测失败: {error_msg}',
                'error': error_msg,
                'traceback': error_traceback
            }
        )
        
        raise


@celery_app.task(bind=True, name='validate_strategy_task')
def validate_strategy_task(self, strategy_id: int) -> Dict[str, Any]:
    """验证策略任务"""
    
    task_id = self.request.id
    logger.info(f"Starting strategy validation task {task_id} for strategy {strategy_id}")
    
    try:
        with get_db_session() as db:
            # 更新任务状态
            self.update_state(
                state=TaskStatus.STARTED,
                meta={'progress': 0, 'message': '开始验证策略...'}
            )
            
            # 获取策略
            strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
            if not strategy:
                raise StrategyError(f"策略不存在: {strategy_id}")
            
            # 创建策略验证器
            validator = StrategyValidator()
            
            # 语法检查
            self.update_state(
                state=TaskStatus.PROGRESS,
                meta={'progress': 25, 'message': '检查策略语法...'}
            )
            
            syntax_result = validator.validate_syntax(strategy.code)
            
            # 依赖检查
            self.update_state(
                state=TaskStatus.PROGRESS,
                meta={'progress': 50, 'message': '检查策略依赖...'}
            )
            
            dependency_result = validator.validate_dependencies(strategy.code)
            
            # 安全检查
            self.update_state(
                state=TaskStatus.PROGRESS,
                meta={'progress': 75, 'message': '检查策略安全性...'}
            )
            
            security_result = validator.validate_security(strategy.code)
            
            # 汇总验证结果
            validation_result = {
                'syntax': syntax_result,
                'dependencies': dependency_result,
                'security': security_result,
                'is_valid': all([
                    syntax_result.get('valid', False),
                    dependency_result.get('valid', False),
                    security_result.get('valid', False)
                ])
            }
            
            # 更新策略状态
            if validation_result['is_valid']:
                strategy.status = 'validated'
            else:
                strategy.status = 'invalid'
            
            db.commit()
            
            # 完成任务
            self.update_state(
                state=TaskStatus.SUCCESS,
                meta={
                    'progress': 100,
                    'message': '策略验证完成',
                    'result': validation_result
                }
            )
            
            logger.info(f"Strategy validation task {task_id} completed")
            
            return {
                'strategy_id': strategy_id,
                'validation_result': validation_result
            }
            
    except Exception as e:
        error_msg = str(e)
        error_traceback = traceback.format_exc()
        
        logger.error(f"Strategy validation task {task_id} failed: {error_msg}")
        
        # 更新任务状态
        self.update_state(
            state=TaskStatus.FAILURE,
            meta={
                'progress': 0,
                'message': f'策略验证失败: {error_msg}',
                'error': error_msg,
                'traceback': error_traceback
            }
        )
        
        raise


@celery_app.task(bind=True, name='generate_backtest_report_task')
def generate_backtest_report_task(
    self,
    backtest_id: int,
    report_format: str = 'json'
) -> Dict[str, Any]:
    """生成回测报告任务"""
    
    task_id = self.request.id
    logger.info(f"Starting report generation task {task_id} for backtest {backtest_id}")
    
    try:
        with get_db_session() as db:
            # 更新任务状态
            self.update_state(
                state=TaskStatus.STARTED,
                meta={'progress': 0, 'message': '开始生成报告...'}
            )
            
            # 获取回测信息
            backtest = db.query(Backtest).filter(Backtest.id == backtest_id).first()
            if not backtest:
                raise BacktestError(f"回测不存在: {backtest_id}")
            
            if backtest.status != 'completed':
                raise BacktestError(f"回测未完成，无法生成报告")
            
            # 创建报告生成器
            report_generator = BacktestReportGenerator()
            
            # 收集回测数据
            self.update_state(
                state=TaskStatus.PROGRESS,
                meta={'progress': 25, 'message': '收集回测数据...'}
            )
            
            backtest_data = {
                'backtest_id': backtest_id,
                'strategy_id': backtest.strategy_id,
                'start_date': backtest.start_date,
                'end_date': backtest.end_date,
                'initial_capital': backtest.initial_capital,
                'final_value': backtest.final_value,
                'total_return': backtest.total_return,
                'annual_return': backtest.annual_return,
                'max_drawdown': backtest.max_drawdown,
                'sharpe_ratio': backtest.sharpe_ratio,
                'volatility': backtest.volatility,
                'beta': backtest.beta,
                'alpha': backtest.alpha,
                'total_trades': backtest.total_trades,
                'profitable_trades': backtest.profitable_trades,
                'win_rate': backtest.win_rate
            }
            
            # 生成报告
            self.update_state(
                state=TaskStatus.PROGRESS,
                meta={'progress': 75, 'message': f'生成{report_format.upper()}报告...'}
            )
            
            if report_format.lower() == 'json':
                report = report_generator.generate_json_report(backtest_data)
            elif report_format.lower() == 'excel':
                report = report_generator.generate_excel_report(backtest_data)
            elif report_format.lower() == 'pdf':
                report = report_generator.generate_pdf_report(backtest_data)
            else:
                raise ValueError(f"不支持的报告格式: {report_format}")
            
            # 完成任务
            self.update_state(
                state=TaskStatus.SUCCESS,
                meta={
                    'progress': 100,
                    'message': '报告生成完成',
                    'result': {
                        'backtest_id': backtest_id,
                        'report_format': report_format,
                        'report': report
                    }
                }
            )
            
            logger.info(f"Report generation task {task_id} completed")
            
            return {
                'backtest_id': backtest_id,
                'report_format': report_format,
                'report': report
            }
            
    except Exception as e:
        error_msg = str(e)
        error_traceback = traceback.format_exc()
        
        logger.error(f"Report generation task {task_id} failed: {error_msg}")
        
        # 更新任务状态
        self.update_state(
            state=TaskStatus.FAILURE,
            meta={
                'progress': 0,
                'message': f'报告生成失败: {error_msg}',
                'error': error_msg,
                'traceback': error_traceback
            }
        )
        
        raise


@celery_app.task(bind=True, name='batch_backtest_task')
def batch_backtest_task(
    self,
    strategy_ids: list,
    backtest_config: Dict[str, Any]
) -> Dict[str, Any]:
    """批量回测任务"""
    
    task_id = self.request.id
    logger.info(f"Starting batch backtest task {task_id} for {len(strategy_ids)} strategies")
    
    try:
        results = []
        total_strategies = len(strategy_ids)
        
        for i, strategy_id in enumerate(strategy_ids):
            # 更新进度
            progress = (i / total_strategies) * 100
            self.update_state(
                state=TaskStatus.PROGRESS,
                meta={
                    'progress': progress,
                    'message': f'回测策略 {i+1}/{total_strategies}...',
                    'current_strategy': strategy_id
                }
            )
            
            try:
                # 创建单个回测任务
                with get_db_session() as db:
                    # 创建回测记录
                    backtest = Backtest(
                        strategy_id=strategy_id,
                        user_id=backtest_config.get('user_id'),
                        **backtest_config
                    )
                    db.add(backtest)
                    db.commit()
                    db.refresh(backtest)
                    
                    # 运行回测
                    result = run_backtest_task.apply(
                        args=[
                            backtest.id,
                            strategy_id,
                            backtest_config['start_date'],
                            backtest_config['end_date'],
                            backtest_config['initial_capital']
                        ],
                        kwargs={
                            'benchmark': backtest_config.get('benchmark'),
                            'commission_rate': backtest_config.get('commission_rate', 0.0003),
                            'slippage_rate': backtest_config.get('slippage_rate', 0.001),
                            'frequency': backtest_config.get('frequency', '1d')
                        }
                    ).get()
                    
                    results.append({
                        'strategy_id': strategy_id,
                        'backtest_id': backtest.id,
                        'status': 'success',
                        'result': result
                    })
                    
            except Exception as e:
                logger.error(f"Batch backtest failed for strategy {strategy_id}: {e}")
                results.append({
                    'strategy_id': strategy_id,
                    'status': 'failed',
                    'error': str(e)
                })
        
        # 完成任务
        self.update_state(
            state=TaskStatus.SUCCESS,
            meta={
                'progress': 100,
                'message': '批量回测完成',
                'result': {
                    'total_strategies': total_strategies,
                    'successful': len([r for r in results if r['status'] == 'success']),
                    'failed': len([r for r in results if r['status'] == 'failed']),
                    'results': results
                }
            }
        )
        
        logger.info(f"Batch backtest task {task_id} completed")
        
        return {
            'total_strategies': total_strategies,
            'results': results
        }
        
    except Exception as e:
        error_msg = str(e)
        error_traceback = traceback.format_exc()
        
        logger.error(f"Batch backtest task {task_id} failed: {error_msg}")
        
        # 更新任务状态
        self.update_state(
            state=TaskStatus.FAILURE,
            meta={
                'progress': 0,
                'message': f'批量回测失败: {error_msg}',
                'error': error_msg,
                'traceback': error_traceback
            }
        )
        
        raise