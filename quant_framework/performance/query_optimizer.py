"""
数据库查询优化器
"""

import re
import time
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime, timedelta
from sqlalchemy import text, inspect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Query
from sqlalchemy.sql import Select

from ..monitoring.logger import get_logger

logger = get_logger(__name__)


class QueryOptimizer:
    """查询优化器"""
    
    def __init__(self):
        self.query_stats: Dict[str, Dict[str, Any]] = {}
        self.slow_query_threshold = 1.0  # 慢查询阈值（秒）
        self.optimization_rules = [
            self._add_missing_indexes,
            self._optimize_joins,
            self._add_query_hints,
            self._optimize_where_clauses,
            self._optimize_order_by
        ]
    
    async def analyze_query(self, session: AsyncSession, query: Union[str, Select]) -> Dict[str, Any]:
        """分析查询性能"""
        if isinstance(query, Select):
            query_str = str(query.compile(compile_kwargs={"literal_binds": True}))
        else:
            query_str = query
        
        # 生成查询ID
        query_id = self._generate_query_id(query_str)
        
        # 执行EXPLAIN ANALYZE
        explain_query = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query_str}"
        
        try:
            start_time = time.time()
            result = await session.execute(text(explain_query))
            execution_time = time.time() - start_time
            
            explain_result = result.fetchone()[0][0]
            
            analysis = {
                'query_id': query_id,
                'query': query_str,
                'execution_time': execution_time,
                'plan': explain_result,
                'total_cost': explain_result.get('Total Cost', 0),
                'actual_time': explain_result.get('Actual Total Time', 0),
                'rows': explain_result.get('Actual Rows', 0),
                'buffers': explain_result.get('Shared Hit Blocks', 0),
                'is_slow': execution_time > self.slow_query_threshold,
                'analyzed_at': datetime.now().isoformat()
            }
            
            # 更新查询统计
            self._update_query_stats(query_id, analysis)
            
            return analysis
            
        except Exception as e:
            logger.error(f"查询分析失败: {e}")
            return {
                'query_id': query_id,
                'query': query_str,
                'error': str(e),
                'analyzed_at': datetime.now().isoformat()
            }
    
    def suggest_optimizations(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """建议查询优化"""
        suggestions = []
        
        if 'plan' not in analysis:
            return suggestions
        
        plan = analysis['plan']
        query = analysis['query']
        
        # 检查是否有全表扫描
        if self._has_seq_scan(plan):
            suggestions.append({
                'type': 'index',
                'priority': 'high',
                'description': '检测到全表扫描，建议添加索引',
                'recommendation': self._suggest_indexes(query, plan)
            })
        
        # 检查是否有昂贵的排序操作
        if self._has_expensive_sort(plan):
            suggestions.append({
                'type': 'sort',
                'priority': 'medium',
                'description': '检测到昂贵的排序操作',
                'recommendation': '考虑添加复合索引或优化ORDER BY子句'
            })
        
        # 检查是否有嵌套循环连接
        if self._has_nested_loop(plan):
            suggestions.append({
                'type': 'join',
                'priority': 'medium',
                'description': '检测到嵌套循环连接',
                'recommendation': '考虑优化连接条件或添加索引'
            })
        
        # 检查缓冲区命中率
        if self._has_low_buffer_hit_rate(plan):
            suggestions.append({
                'type': 'buffer',
                'priority': 'low',
                'description': '缓冲区命中率较低',
                'recommendation': '考虑增加shared_buffers或优化查询'
            })
        
        return suggestions
    
    async def optimize_query(self, session: AsyncSession, query: Union[str, Select]) -> Dict[str, Any]:
        """优化查询"""
        # 分析原始查询
        original_analysis = await self.analyze_query(session, query)
        
        if 'error' in original_analysis:
            return original_analysis
        
        # 获取优化建议
        suggestions = self.suggest_optimizations(original_analysis)
        
        # 尝试应用优化规则
        optimized_query = query
        applied_optimizations = []
        
        for rule in self.optimization_rules:
            try:
                new_query, optimization = rule(optimized_query, original_analysis)
                if new_query != optimized_query:
                    optimized_query = new_query
                    applied_optimizations.append(optimization)
            except Exception as e:
                logger.warning(f"优化规则应用失败: {rule.__name__}, {e}")
        
        # 如果有优化，分析优化后的查询
        optimized_analysis = None
        if applied_optimizations:
            optimized_analysis = await self.analyze_query(session, optimized_query)
        
        return {
            'original': original_analysis,
            'optimized': optimized_analysis,
            'suggestions': suggestions,
            'applied_optimizations': applied_optimizations,
            'improvement': self._calculate_improvement(original_analysis, optimized_analysis)
        }
    
    def get_slow_queries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取慢查询列表"""
        slow_queries = []
        
        for query_id, stats in self.query_stats.items():
            if stats.get('is_slow', False):
                slow_queries.append({
                    'query_id': query_id,
                    'avg_execution_time': stats['total_time'] / stats['count'],
                    'max_execution_time': stats['max_time'],
                    'execution_count': stats['count'],
                    'last_executed': stats['last_executed'],
                    'query': stats.get('query', '')[:200] + '...' if len(stats.get('query', '')) > 200 else stats.get('query', '')
                })
        
        # 按平均执行时间排序
        slow_queries.sort(key=lambda x: x['avg_execution_time'], reverse=True)
        
        return slow_queries[:limit]
    
    def get_query_stats(self) -> Dict[str, Any]:
        """获取查询统计信息"""
        total_queries = len(self.query_stats)
        slow_queries = sum(1 for stats in self.query_stats.values() if stats.get('is_slow', False))
        
        if total_queries > 0:
            avg_execution_time = sum(
                stats['total_time'] / stats['count'] 
                for stats in self.query_stats.values()
            ) / total_queries
        else:
            avg_execution_time = 0
        
        return {
            'total_queries': total_queries,
            'slow_queries': slow_queries,
            'slow_query_percentage': (slow_queries / total_queries * 100) if total_queries > 0 else 0,
            'avg_execution_time': avg_execution_time,
            'threshold': self.slow_query_threshold
        }
    
    def _generate_query_id(self, query: str) -> str:
        """生成查询ID"""
        import hashlib
        # 标准化查询（移除空白字符和参数）
        normalized = re.sub(r'\s+', ' ', query.strip().lower())
        normalized = re.sub(r'\$\d+', '?', normalized)  # 替换参数占位符
        return hashlib.md5(normalized.encode()).hexdigest()[:16]
    
    def _update_query_stats(self, query_id: str, analysis: Dict[str, Any]):
        """更新查询统计"""
        execution_time = analysis.get('execution_time', 0)
        
        if query_id not in self.query_stats:
            self.query_stats[query_id] = {
                'count': 0,
                'total_time': 0,
                'max_time': 0,
                'min_time': float('inf'),
                'is_slow': False,
                'first_seen': datetime.now().isoformat(),
                'query': analysis.get('query', '')
            }
        
        stats = self.query_stats[query_id]
        stats['count'] += 1
        stats['total_time'] += execution_time
        stats['max_time'] = max(stats['max_time'], execution_time)
        stats['min_time'] = min(stats['min_time'], execution_time)
        stats['last_executed'] = datetime.now().isoformat()
        stats['is_slow'] = execution_time > self.slow_query_threshold
    
    def _has_seq_scan(self, plan: Dict[str, Any]) -> bool:
        """检查是否有全表扫描"""
        def check_node(node):
            if node.get('Node Type') == 'Seq Scan':
                return True
            for child in node.get('Plans', []):
                if check_node(child):
                    return True
            return False
        
        return check_node(plan)
    
    def _has_expensive_sort(self, plan: Dict[str, Any]) -> bool:
        """检查是否有昂贵的排序操作"""
        def check_node(node):
            if node.get('Node Type') == 'Sort' and node.get('Total Cost', 0) > 1000:
                return True
            for child in node.get('Plans', []):
                if check_node(child):
                    return True
            return False
        
        return check_node(plan)
    
    def _has_nested_loop(self, plan: Dict[str, Any]) -> bool:
        """检查是否有嵌套循环连接"""
        def check_node(node):
            if node.get('Node Type') == 'Nested Loop' and node.get('Actual Rows', 0) > 1000:
                return True
            for child in node.get('Plans', []):
                if check_node(child):
                    return True
            return False
        
        return check_node(plan)
    
    def _has_low_buffer_hit_rate(self, plan: Dict[str, Any]) -> bool:
        """检查缓冲区命中率是否较低"""
        shared_hit = plan.get('Shared Hit Blocks', 0)
        shared_read = plan.get('Shared Read Blocks', 0)
        
        if shared_hit + shared_read > 0:
            hit_rate = shared_hit / (shared_hit + shared_read)
            return hit_rate < 0.9  # 命中率低于90%
        
        return False
    
    def _suggest_indexes(self, query: str, plan: Dict[str, Any]) -> str:
        """建议索引"""
        # 简单的索引建议逻辑
        suggestions = []
        
        # 从WHERE子句提取条件
        where_match = re.search(r'WHERE\s+(.+?)(?:ORDER BY|GROUP BY|LIMIT|$)', query, re.IGNORECASE | re.DOTALL)
        if where_match:
            where_clause = where_match.group(1).strip()
            
            # 提取列名
            column_pattern = r'(\w+\.\w+|\w+)\s*[=<>!]'
            columns = re.findall(column_pattern, where_clause)
            
            if columns:
                suggestions.append(f"考虑在列 {', '.join(set(columns))} 上创建索引")
        
        # 从ORDER BY子句提取排序列
        order_match = re.search(r'ORDER BY\s+(.+?)(?:LIMIT|$)', query, re.IGNORECASE)
        if order_match:
            order_clause = order_match.group(1).strip()
            order_columns = [col.strip().split()[0] for col in order_clause.split(',')]
            suggestions.append(f"考虑在排序列 {', '.join(order_columns)} 上创建索引")
        
        return '; '.join(suggestions) if suggestions else "需要进一步分析查询模式"
    
    def _add_missing_indexes(self, query: Union[str, Select], analysis: Dict[str, Any]) -> Tuple[Union[str, Select], Dict[str, Any]]:
        """添加缺失索引的优化规则"""
        # 这里只是示例，实际实现需要更复杂的逻辑
        return query, {'type': 'index', 'description': '索引优化规则'}
    
    def _optimize_joins(self, query: Union[str, Select], analysis: Dict[str, Any]) -> Tuple[Union[str, Select], Dict[str, Any]]:
        """优化连接的规则"""
        return query, {'type': 'join', 'description': '连接优化规则'}
    
    def _add_query_hints(self, query: Union[str, Select], analysis: Dict[str, Any]) -> Tuple[Union[str, Select], Dict[str, Any]]:
        """添加查询提示的规则"""
        return query, {'type': 'hint', 'description': '查询提示优化规则'}
    
    def _optimize_where_clauses(self, query: Union[str, Select], analysis: Dict[str, Any]) -> Tuple[Union[str, Select], Dict[str, Any]]:
        """优化WHERE子句的规则"""
        return query, {'type': 'where', 'description': 'WHERE子句优化规则'}
    
    def _optimize_order_by(self, query: Union[str, Select], analysis: Dict[str, Any]) -> Tuple[Union[str, Select], Dict[str, Any]]:
        """优化ORDER BY的规则"""
        return query, {'type': 'order', 'description': 'ORDER BY优化规则'}
    
    def _calculate_improvement(self, original: Dict[str, Any], optimized: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """计算优化改进"""
        if not optimized or 'execution_time' not in optimized:
            return None
        
        original_time = original.get('execution_time', 0)
        optimized_time = optimized.get('execution_time', 0)
        
        if original_time > 0:
            improvement_percentage = ((original_time - optimized_time) / original_time) * 100
            return {
                'time_saved': original_time - optimized_time,
                'improvement_percentage': improvement_percentage,
                'is_better': optimized_time < original_time
            }
        
        return None


def optimize_query(query: Union[str, Select]):
    """查询优化装饰器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # 这里可以添加查询优化逻辑
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# 全局查询优化器实例
query_optimizer = QueryOptimizer()