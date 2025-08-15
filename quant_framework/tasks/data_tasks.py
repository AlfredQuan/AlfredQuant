"""
数据相关的异步任务
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from celery import current_task
import pandas as pd

from .celery_app import celery_app
from .task_models import TaskStatus
from ..core.database import get_db_session
from ..data.base import DataSourceManager
from ..data.cache import CacheManager
from ..core.exceptions import DataError
import logging
import traceback
import io
import json

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name='update_market_data_task')
def update_market_data_task(
    self,
    symbols: List[str],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    data_types: List[str] = None
) -> Dict[str, Any]:
    """更新市场数据任务"""
    
    task_id = self.request.id
    logger.info(f"Starting market data update task {task_id} for {len(symbols)} symbols")
    
    try:
        # 更新任务状态
        self.update_state(
            state=TaskStatus.STARTED,
            meta={'progress': 0, 'message': '初始化数据更新...'}
        )
        
        # 初始化数据源管理器
        data_manager = DataSourceManager()
        cache_manager = CacheManager()
        
        # 默认数据类型
        if not data_types:
            data_types = ['price', 'volume', 'market_cap']
        
        # 默认时间范围
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        results = {}
        total_symbols = len(symbols)
        
        for i, symbol in enumerate(symbols):
            # 更新进度
            progress = (i / total_symbols) * 100
            self.update_state(
                state=TaskStatus.PROGRESS,
                meta={
                    'progress': progress,
                    'message': f'更新数据: {symbol} ({i+1}/{total_symbols})',
                    'current_symbol': symbol
                }
            )
            
            try:
                symbol_results = {}
                
                for data_type in data_types:
                    # 获取数据
                    if data_type == 'price':
                        data = data_manager.get_price_data(
                            symbols=[symbol],
                            start_date=start_date,
                            end_date=end_date
                        )
                    elif data_type == 'fundamentals':
                        data = data_manager.get_fundamentals(
                            symbols=[symbol],
                            date=end_date
                        )
                    else:
                        # 其他数据类型
                        data = data_manager.get_custom_data(
                            symbols=[symbol],
                            data_type=data_type,
                            start_date=start_date,
                            end_date=end_date
                        )
                    
                    # 缓存数据
                    cache_key = f"{symbol}:{data_type}:{start_date}:{end_date}"
                    cache_manager.set(cache_key, data, expire=3600)  # 缓存1小时
                    
                    symbol_results[data_type] = {
                        'status': 'success',
                        'records': len(data) if isinstance(data, (list, pd.DataFrame)) else 1,
                        'cache_key': cache_key
                    }
                
                results[symbol] = {
                    'status': 'success',
                    'data_types': symbol_results
                }
                
            except Exception as e:
                logger.error(f"Failed to update data for {symbol}: {e}")
                results[symbol] = {
                    'status': 'failed',
                    'error': str(e)
                }
        
        # 统计结果
        successful = len([r for r in results.values() if r['status'] == 'success'])
        failed = len([r for r in results.values() if r['status'] == 'failed'])
        
        # 完成任务
        self.update_state(
            state=TaskStatus.SUCCESS,
            meta={
                'progress': 100,
                'message': f'数据更新完成: 成功 {successful}, 失败 {failed}',
                'result': {
                    'total_symbols': total_symbols,
                    'successful': successful,
                    'failed': failed,
                    'results': results
                }
            }
        )
        
        logger.info(f"Market data update task {task_id} completed")
        
        return {
            'total_symbols': total_symbols,
            'successful': successful,
            'failed': failed,
            'results': results
        }
        
    except Exception as e:
        error_msg = str(e)
        error_traceback = traceback.format_exc()
        
        logger.error(f"Market data update task {task_id} failed: {error_msg}")
        
        # 更新任务状态
        self.update_state(
            state=TaskStatus.FAILURE,
            meta={
                'progress': 0,
                'message': f'数据更新失败: {error_msg}',
                'error': error_msg,
                'traceback': error_traceback
            }
        )
        
        raise


@celery_app.task(bind=True, name='export_data_task')
def export_data_task(
    self,
    symbols: List[str],
    start_date: str,
    end_date: str,
    data_types: List[str],
    export_format: str = 'csv',
    user_id: Optional[int] = None
) -> Dict[str, Any]:
    """导出数据任务"""
    
    task_id = self.request.id
    logger.info(f"Starting data export task {task_id}")
    
    try:
        # 更新任务状态
        self.update_state(
            state=TaskStatus.STARTED,
            meta={'progress': 0, 'message': '开始导出数据...'}
        )
        
        # 初始化数据源管理器
        data_manager = DataSourceManager()
        
        # 收集数据
        self.update_state(
            state=TaskStatus.PROGRESS,
            meta={'progress': 20, 'message': '收集数据...'}
        )
        
        all_data = {}
        
        for data_type in data_types:
            if data_type == 'price':
                data = data_manager.get_price_data(
                    symbols=symbols,
                    start_date=start_date,
                    end_date=end_date
                )
            elif data_type == 'fundamentals':
                data = data_manager.get_fundamentals(
                    symbols=symbols,
                    date=end_date
                )
            else:
                data = data_manager.get_custom_data(
                    symbols=symbols,
                    data_type=data_type,
                    start_date=start_date,
                    end_date=end_date
                )
            
            all_data[data_type] = data
        
        # 格式化数据
        self.update_state(
            state=TaskStatus.PROGRESS,
            meta={'progress': 60, 'message': '格式化数据...'}
        )
        
        if export_format.lower() == 'csv':
            exported_files = {}
            for data_type, data in all_data.items():
                if isinstance(data, pd.DataFrame):
                    csv_buffer = io.StringIO()
                    data.to_csv(csv_buffer, index=False)
                    exported_files[f"{data_type}.csv"] = csv_buffer.getvalue()
                else:
                    # 转换为DataFrame
                    df = pd.DataFrame(data)
                    csv_buffer = io.StringIO()
                    df.to_csv(csv_buffer, index=False)
                    exported_files[f"{data_type}.csv"] = csv_buffer.getvalue()
            
            export_result = {
                'format': 'csv',
                'files': exported_files
            }
            
        elif export_format.lower() == 'excel':
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                for data_type, data in all_data.items():
                    if isinstance(data, pd.DataFrame):
                        data.to_excel(writer, sheet_name=data_type, index=False)
                    else:
                        df = pd.DataFrame(data)
                        df.to_excel(writer, sheet_name=data_type, index=False)
            
            export_result = {
                'format': 'excel',
                'file': excel_buffer.getvalue()
            }
            
        elif export_format.lower() == 'json':
            json_data = {}
            for data_type, data in all_data.items():
                if isinstance(data, pd.DataFrame):
                    json_data[data_type] = data.to_dict('records')
                else:
                    json_data[data_type] = data
            
            export_result = {
                'format': 'json',
                'data': json_data
            }
            
        else:
            raise ValueError(f"不支持的导出格式: {export_format}")
        
        # 保存导出文件信息
        self.update_state(
            state=TaskStatus.PROGRESS,
            meta={'progress': 90, 'message': '保存导出文件...'}
        )
        
        # TODO: 将导出文件保存到文件系统或云存储
        # 这里可以集成文件存储服务
        
        # 完成任务
        self.update_state(
            state=TaskStatus.SUCCESS,
            meta={
                'progress': 100,
                'message': '数据导出完成',
                'result': {
                    'symbols': symbols,
                    'date_range': f"{start_date} to {end_date}",
                    'data_types': data_types,
                    'export_format': export_format,
                    'export_result': export_result
                }
            }
        )
        
        logger.info(f"Data export task {task_id} completed")
        
        return {
            'symbols': symbols,
            'date_range': f"{start_date} to {end_date}",
            'data_types': data_types,
            'export_format': export_format,
            'export_result': export_result
        }
        
    except Exception as e:
        error_msg = str(e)
        error_traceback = traceback.format_exc()
        
        logger.error(f"Data export task {task_id} failed: {error_msg}")
        
        # 更新任务状态
        self.update_state(
            state=TaskStatus.FAILURE,
            meta={
                'progress': 0,
                'message': f'数据导出失败: {error_msg}',
                'error': error_msg,
                'traceback': error_traceback
            }
        )
        
        raise


@celery_app.task(bind=True, name='data_quality_check_task')
def data_quality_check_task(
    self,
    symbols: List[str],
    start_date: str,
    end_date: str,
    check_types: List[str] = None
) -> Dict[str, Any]:
    """数据质量检查任务"""
    
    task_id = self.request.id
    logger.info(f"Starting data quality check task {task_id}")
    
    try:
        # 更新任务状态
        self.update_state(
            state=TaskStatus.STARTED,
            meta={'progress': 0, 'message': '开始数据质量检查...'}
        )
        
        # 默认检查类型
        if not check_types:
            check_types = ['completeness', 'accuracy', 'consistency']
        
        # 初始化数据源管理器
        data_manager = DataSourceManager()
        
        results = {}
        total_symbols = len(symbols)
        
        for i, symbol in enumerate(symbols):
            # 更新进度
            progress = (i / total_symbols) * 100
            self.update_state(
                state=TaskStatus.PROGRESS,
                meta={
                    'progress': progress,
                    'message': f'检查数据质量: {symbol} ({i+1}/{total_symbols})',
                    'current_symbol': symbol
                }
            )
            
            try:
                # 获取价格数据
                price_data = data_manager.get_price_data(
                    symbols=[symbol],
                    start_date=start_date,
                    end_date=end_date
                )
                
                symbol_results = {}
                
                # 完整性检查
                if 'completeness' in check_types:
                    expected_days = pd.bdate_range(start_date, end_date)
                    actual_days = len(price_data) if isinstance(price_data, pd.DataFrame) else 0
                    completeness_ratio = actual_days / len(expected_days) if len(expected_days) > 0 else 0
                    
                    symbol_results['completeness'] = {
                        'ratio': completeness_ratio,
                        'expected_records': len(expected_days),
                        'actual_records': actual_days,
                        'missing_records': len(expected_days) - actual_days
                    }
                
                # 准确性检查
                if 'accuracy' in check_types and isinstance(price_data, pd.DataFrame):
                    # 检查价格异常值
                    price_cols = ['open', 'high', 'low', 'close']
                    anomalies = []
                    
                    for col in price_cols:
                        if col in price_data.columns:
                            # 使用3σ规则检测异常值
                            mean_val = price_data[col].mean()
                            std_val = price_data[col].std()
                            outliers = price_data[
                                (price_data[col] < mean_val - 3 * std_val) |
                                (price_data[col] > mean_val + 3 * std_val)
                            ]
                            if len(outliers) > 0:
                                anomalies.extend(outliers.index.tolist())
                    
                    symbol_results['accuracy'] = {
                        'anomaly_count': len(set(anomalies)),
                        'anomaly_ratio': len(set(anomalies)) / len(price_data) if len(price_data) > 0 else 0
                    }
                
                # 一致性检查
                if 'consistency' in check_types and isinstance(price_data, pd.DataFrame):
                    consistency_issues = []
                    
                    # 检查OHLC逻辑一致性
                    if all(col in price_data.columns for col in ['open', 'high', 'low', 'close']):
                        # High应该是最高价
                        high_issues = price_data[
                            (price_data['high'] < price_data['open']) |
                            (price_data['high'] < price_data['close']) |
                            (price_data['high'] < price_data['low'])
                        ]
                        
                        # Low应该是最低价
                        low_issues = price_data[
                            (price_data['low'] > price_data['open']) |
                            (price_data['low'] > price_data['close']) |
                            (price_data['low'] > price_data['high'])
                        ]
                        
                        consistency_issues.extend(high_issues.index.tolist())
                        consistency_issues.extend(low_issues.index.tolist())
                    
                    symbol_results['consistency'] = {
                        'issue_count': len(set(consistency_issues)),
                        'issue_ratio': len(set(consistency_issues)) / len(price_data) if len(price_data) > 0 else 0
                    }
                
                results[symbol] = {
                    'status': 'success',
                    'checks': symbol_results
                }
                
            except Exception as e:
                logger.error(f"Data quality check failed for {symbol}: {e}")
                results[symbol] = {
                    'status': 'failed',
                    'error': str(e)
                }
        
        # 汇总结果
        successful = len([r for r in results.values() if r['status'] == 'success'])
        failed = len([r for r in results.values() if r['status'] == 'failed'])
        
        # 完成任务
        self.update_state(
            state=TaskStatus.SUCCESS,
            meta={
                'progress': 100,
                'message': f'数据质量检查完成: 成功 {successful}, 失败 {failed}',
                'result': {
                    'total_symbols': total_symbols,
                    'successful': successful,
                    'failed': failed,
                    'check_types': check_types,
                    'results': results
                }
            }
        )
        
        logger.info(f"Data quality check task {task_id} completed")
        
        return {
            'total_symbols': total_symbols,
            'successful': successful,
            'failed': failed,
            'check_types': check_types,
            'results': results
        }
        
    except Exception as e:
        error_msg = str(e)
        error_traceback = traceback.format_exc()
        
        logger.error(f"Data quality check task {task_id} failed: {error_msg}")
        
        # 更新任务状态
        self.update_state(
            state=TaskStatus.FAILURE,
            meta={
                'progress': 0,
                'message': f'数据质量检查失败: {error_msg}',
                'error': error_msg,
                'traceback': error_traceback
            }
        )
        
        raise


@celery_app.task(bind=True, name='sync_data_sources_task')
def sync_data_sources_task(self) -> Dict[str, Any]:
    """同步数据源任务"""
    
    task_id = self.request.id
    logger.info(f"Starting data sources sync task {task_id}")
    
    try:
        # 更新任务状态
        self.update_state(
            state=TaskStatus.STARTED,
            meta={'progress': 0, 'message': '开始同步数据源...'}
        )
        
        # 初始化数据源管理器
        data_manager = DataSourceManager()
        
        # 获取所有数据源
        data_sources = data_manager.get_all_sources()
        total_sources = len(data_sources)
        
        sync_results = {}
        
        for i, source_name in enumerate(data_sources):
            # 更新进度
            progress = (i / total_sources) * 100
            self.update_state(
                state=TaskStatus.PROGRESS,
                meta={
                    'progress': progress,
                    'message': f'同步数据源: {source_name} ({i+1}/{total_sources})',
                    'current_source': source_name
                }
            )
            
            try:
                # 同步数据源
                source = data_manager.get_source(source_name)
                sync_result = source.sync()
                
                sync_results[source_name] = {
                    'status': 'success',
                    'result': sync_result
                }
                
            except Exception as e:
                logger.error(f"Failed to sync data source {source_name}: {e}")
                sync_results[source_name] = {
                    'status': 'failed',
                    'error': str(e)
                }
        
        # 统计结果
        successful = len([r for r in sync_results.values() if r['status'] == 'success'])
        failed = len([r for r in sync_results.values() if r['status'] == 'failed'])
        
        # 完成任务
        self.update_state(
            state=TaskStatus.SUCCESS,
            meta={
                'progress': 100,
                'message': f'数据源同步完成: 成功 {successful}, 失败 {failed}',
                'result': {
                    'total_sources': total_sources,
                    'successful': successful,
                    'failed': failed,
                    'results': sync_results
                }
            }
        )
        
        logger.info(f"Data sources sync task {task_id} completed")
        
        return {
            'total_sources': total_sources,
            'successful': successful,
            'failed': failed,
            'results': sync_results
        }
        
    except Exception as e:
        error_msg = str(e)
        error_traceback = traceback.format_exc()
        
        logger.error(f"Data sources sync task {task_id} failed: {error_msg}")
        
        # 更新任务状态
        self.update_state(
            state=TaskStatus.FAILURE,
            meta={
                'progress': 0,
                'message': f'数据源同步失败: {error_msg}',
                'error': error_msg,
                'traceback': error_traceback
            }
        )
        
        raise