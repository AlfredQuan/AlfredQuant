"""
聚宽兼容API实现
提供与聚宽平台完全兼容的数据获取接口
"""

import asyncio
from datetime import datetime, date, timedelta
from typing import List, Union, Optional, Dict, Any
import pandas as pd
import numpy as np

from quant_framework.core.constants import DataFrequency, SecurityType
from quant_framework.core.exceptions import DataSourceError
from quant_framework.data.interfaces import IDataSource
from quant_framework.data.base import DataSourceManager
from quant_framework.utils.logger import LoggerMixin


class JQCompatibleAPI(LoggerMixin):
    """聚宽兼容API类"""
    
    def __init__(self, data_source_manager: DataSourceManager):
        self.data_manager = data_source_manager
        self._current_data_source: Optional[IDataSource] = None
        
        # 聚宽字段映射
        self.jq_field_mapping = {
            'open': 'open',
            'close': 'close', 
            'high': 'high',
            'low': 'low',
            'volume': 'volume',
            'money': 'amount',
            'avg': 'avg_price',
            'high_limit': 'high_limit',
            'low_limit': 'low_limit',
            'pre_close': 'pre_close',
            'paused': 'paused'
        }
        
        # 聚宽频率映射
        self.jq_frequency_mapping = {
            '1m': DataFrequency.MINUTE,
            '5m': DataFrequency.MINUTE_5,
            '15m': DataFrequency.MINUTE_15,
            '30m': DataFrequency.MINUTE_30,
            '60m': DataFrequency.HOUR,
            '1d': DataFrequency.DAILY,
            'daily': DataFrequency.DAILY,
            '1w': DataFrequency.WEEKLY,
            'weekly': DataFrequency.WEEKLY,
            '1M': DataFrequency.MONTHLY,
            'monthly': DataFrequency.MONTHLY
        }
    
    async def initialize(self, data_source_name: Optional[str] = None):
        """初始化API"""
        try:
            self._current_data_source = self.data_manager.get_source(data_source_name)
            if not await self._current_data_source.health_check():
                await self._current_data_source.connect()
            
            self.logger.info("JQ Compatible API initialized")
            
        except Exception as e:
            self.log_error(e, {"method": "initialize"})
            raise DataSourceError(f"Failed to initialize JQ API: {e}")
    
    def get_price(
        self,
        security: Union[str, List[str]],
        start_date: Optional[Union[str, datetime, date]] = None,
        end_date: Optional[Union[str, datetime, date]] = None,
        frequency: str = 'daily',
        fields: Optional[List[str]] = None,
        skip_paused: bool = False,
        fq: Optional[str] = None,
        count: Optional[int] = None
    ) -> pd.DataFrame:
        """
        获取历史价格数据（聚宽兼容接口）
        
        Args:
            security: 证券代码或代码列表
            start_date: 开始日期
            end_date: 结束日期
            frequency: 数据频率
            fields: 字段列表
            skip_paused: 是否跳过停牌数据
            fq: 复权类型 ('pre', 'post', None)
            count: 获取数据条数
            
        Returns:
            价格数据DataFrame
        """
        return asyncio.run(self._get_price_async(
            security, start_date, end_date, frequency, fields, skip_paused, fq, count
        ))
    
    async def _get_price_async(
        self,
        security: Union[str, List[str]],
        start_date: Optional[Union[str, datetime, date]] = None,
        end_date: Optional[Union[str, datetime, date]] = None,
        frequency: str = 'daily',
        fields: Optional[List[str]] = None,
        skip_paused: bool = False,
        fq: Optional[str] = None,
        count: Optional[int] = None
    ) -> pd.DataFrame:
        """异步获取价格数据"""
        try:
            # 标准化证券代码
            symbols = self._normalize_securities(security)
            
            # 处理日期参数
            if count and not start_date:
                # 如果指定了count但没有start_date，计算start_date
                end_dt = self._parse_date(end_date) if end_date else datetime.now().date()
                start_dt = self._calculate_start_date_by_count(end_dt, count, frequency)
            else:
                start_dt = self._parse_date(start_date) if start_date else date.today() - timedelta(days=30)
                end_dt = self._parse_date(end_date) if end_date else date.today()
            
            # 转换频率
            data_frequency = self.jq_frequency_mapping.get(frequency, DataFrequency.DAILY)
            
            # 处理字段
            if fields is None:
                fields = ['open', 'close', 'high', 'low', 'volume']
            
            # 映射字段名
            mapped_fields = [self.jq_field_mapping.get(field, field) for field in fields]
            
            # 获取数据
            df = await self._current_data_source.get_price_data(
                symbols=symbols,
                start_date=start_dt,
                end_date=end_dt,
                frequency=data_frequency,
                fields=mapped_fields
            )
            
            if df.empty:
                return df
            
            # 转换为聚宽格式
            df = self._format_price_data_jq_style(df, symbols, fields, skip_paused, fq)
            
            # 如果指定了count，限制返回条数
            if count and len(df) > count:
                df = df.tail(count)
            
            return df
            
        except Exception as e:
            self.log_error(e, {"method": "_get_price_async", "security": security})
            raise DataSourceError(f"Failed to get price data: {e}")
    
    def get_fundamentals(
        self,
        query,
        date: Optional[Union[str, datetime, date]] = None,
        statDate: Optional[Union[str, datetime, date]] = None
    ) -> pd.DataFrame:
        """
        获取基本面数据（聚宽兼容接口）
        
        Args:
            query: 查询对象（简化实现，接受字典）
            date: 查询日期
            statDate: 统计日期
            
        Returns:
            基本面数据DataFrame
        """
        return asyncio.run(self._get_fundamentals_async(query, date, statDate))
    
    async def _get_fundamentals_async(
        self,
        query,
        date: Optional[Union[str, datetime, date]] = None,
        statDate: Optional[Union[str, datetime, date]] = None
    ) -> pd.DataFrame:
        """异步获取基本面数据"""
        try:
            # 简化实现：假设query是包含symbols和fields的字典
            if isinstance(query, dict):
                symbols = query.get('symbols', [])
                fields = query.get('fields', [])
            else:
                # 更复杂的查询对象处理可以在这里扩展
                symbols = []
                fields = []
            
            if not symbols or not fields:
                return pd.DataFrame()
            
            # 标准化证券代码
            symbols = self._normalize_securities(symbols)
            
            # 处理日期
            query_date = self._parse_date(date) if date else None
            
            # 获取数据
            df = await self._current_data_source.get_fundamental_data(
                symbols=symbols,
                fields=fields,
                date=query_date
            )
            
            return self._format_fundamental_data_jq_style(df)
            
        except Exception as e:
            self.log_error(e, {"method": "_get_fundamentals_async"})
            raise DataSourceError(f"Failed to get fundamental data: {e}")
    
    def get_current_data(
        self,
        security: Optional[Union[str, List[str]]] = None,
        fields: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        获取当前数据（聚宽兼容接口）
        
        Args:
            security: 证券代码或代码列表
            fields: 字段列表
            
        Returns:
            当前数据DataFrame
        """
        return asyncio.run(self._get_current_data_async(security, fields))
    
    async def _get_current_data_async(
        self,
        security: Optional[Union[str, List[str]]] = None,
        fields: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """异步获取当前数据"""
        try:
            if security is None:
                # 如果没有指定证券，返回空DataFrame
                return pd.DataFrame()
            
            # 标准化证券代码
            symbols = self._normalize_securities(security)
            
            # 处理字段
            if fields is None:
                fields = ['last_price', 'volume', 'money']
            
            # 映射字段名
            mapped_fields = [self.jq_field_mapping.get(field, field) for field in fields]
            
            # 获取实时数据
            df = await self._current_data_source.get_realtime_data(
                symbols=symbols,
                fields=mapped_fields
            )
            
            return self._format_current_data_jq_style(df, fields)
            
        except Exception as e:
            self.log_error(e, {"method": "_get_current_data_async"})
            raise DataSourceError(f"Failed to get current data: {e}")
    
    def attribute_history(
        self,
        security: Union[str, List[str]],
        count: int,
        unit: str = '1d',
        fields: List[str] = ['close'],
        skip_paused: bool = False,
        df: bool = True,
        fq: Optional[str] = None
    ) -> Union[pd.DataFrame, pd.Series, Dict]:
        """
        获取历史数据（聚宽兼容接口）
        
        Args:
            security: 证券代码
            count: 获取数据条数
            unit: 时间单位
            fields: 字段列表
            skip_paused: 是否跳过停牌
            df: 是否返回DataFrame
            fq: 复权类型
            
        Returns:
            历史数据
        """
        return asyncio.run(self._attribute_history_async(
            security, count, unit, fields, skip_paused, df, fq
        ))
    
    async def _attribute_history_async(
        self,
        security: Union[str, List[str]],
        count: int,
        unit: str = '1d',
        fields: List[str] = ['close'],
        skip_paused: bool = False,
        df: bool = True,
        fq: Optional[str] = None
    ) -> Union[pd.DataFrame, pd.Series, Dict]:
        """异步获取历史数据"""
        try:
            # 计算结束日期和开始日期
            end_date = date.today()
            start_date = self._calculate_start_date_by_count(end_date, count, unit)
            
            # 获取价格数据
            price_df = await self._get_price_async(
                security=security,
                start_date=start_date,
                end_date=end_date,
                frequency=unit,
                fields=fields,
                skip_paused=skip_paused,
                fq=fq,
                count=count
            )
            
            if price_df.empty:
                if df:
                    return pd.DataFrame()
                else:
                    return pd.Series() if len(fields) == 1 else {}
            
            # 根据返回格式要求处理数据
            if isinstance(security, str):
                # 单个证券
                security_data = price_df[price_df['symbol'] == security] if 'symbol' in price_df.columns else price_df
                
                if df:
                    return security_data[fields].set_index(security_data.index)
                elif len(fields) == 1:
                    return security_data[fields[0]]
                else:
                    return security_data[fields].to_dict('series')
            else:
                # 多个证券
                if df:
                    return price_df
                else:
                    return price_df.to_dict('series')
                    
        except Exception as e:
            self.log_error(e, {"method": "_attribute_history_async"})
            raise DataSourceError(f"Failed to get attribute history: {e}")
    
    def get_security_info(
        self,
        code: Union[str, List[str]]
    ) -> Union[Dict, pd.DataFrame]:
        """
        获取证券信息（聚宽兼容接口）
        
        Args:
            code: 证券代码
            
        Returns:
            证券信息
        """
        return asyncio.run(self._get_security_info_async(code))
    
    async def _get_security_info_async(
        self,
        code: Union[str, List[str]]
    ) -> Union[Dict, pd.DataFrame]:
        """异步获取证券信息"""
        try:
            symbols = self._normalize_securities(code)
            
            df = await self._current_data_source.get_security_info(symbols)
            
            if df.empty:
                return {} if isinstance(code, str) else pd.DataFrame()
            
            # 转换为聚宽格式
            df = self._format_security_info_jq_style(df)
            
            if isinstance(code, str):
                # 单个证券，返回字典
                if len(df) > 0:
                    return df.iloc[0].to_dict()
                else:
                    return {}
            else:
                # 多个证券，返回DataFrame
                return df
                
        except Exception as e:
            self.log_error(e, {"method": "_get_security_info_async"})
            raise DataSourceError(f"Failed to get security info: {e}")
    
    def _normalize_securities(self, security: Union[str, List[str]]) -> List[str]:
        """标准化证券代码"""
        if isinstance(security, str):
            return [self._normalize_single_security(security)]
        else:
            return [self._normalize_single_security(s) for s in security]
    
    def _normalize_single_security(self, security: str) -> str:
        """标准化单个证券代码"""
        # 聚宽格式转换为标准格式
        if '.' not in security:
            # 如果没有交易所后缀，根据代码规则添加
            if security.startswith(('0', '3')):
                return f"{security}.SZ"
            elif security.startswith('6'):
                return f"{security}.SH"
        
        return security.upper()
    
    def _parse_date(self, date_input: Union[str, datetime, date]) -> date:
        """解析日期"""
        if isinstance(date_input, date):
            return date_input
        elif isinstance(date_input, datetime):
            return date_input.date()
        elif isinstance(date_input, str):
            try:
                return datetime.strptime(date_input, '%Y-%m-%d').date()
            except ValueError:
                try:
                    return datetime.strptime(date_input, '%Y/%m/%d').date()
                except ValueError:
                    return datetime.strptime(date_input, '%Y%m%d').date()
        else:
            raise ValueError(f"Invalid date format: {date_input}")
    
    def _calculate_start_date_by_count(
        self, 
        end_date: date, 
        count: int, 
        frequency: str
    ) -> date:
        """根据数据条数计算开始日期"""
        if frequency in ['1d', 'daily']:
            # 考虑周末和节假日，实际需要更多天数
            days = count * 1.5  # 简化处理
            return end_date - timedelta(days=int(days))
        elif frequency in ['1w', 'weekly']:
            return end_date - timedelta(weeks=count)
        elif frequency in ['1M', 'monthly']:
            return end_date - timedelta(days=count * 30)
        else:
            # 分钟级数据
            if frequency == '1m':
                return end_date - timedelta(minutes=count)
            elif frequency == '5m':
                return end_date - timedelta(minutes=count * 5)
            elif frequency == '15m':
                return end_date - timedelta(minutes=count * 15)
            elif frequency == '30m':
                return end_date - timedelta(minutes=count * 30)
            elif frequency == '60m':
                return end_date - timedelta(hours=count)
            else:
                return end_date - timedelta(days=count)
    
    def _format_price_data_jq_style(
        self, 
        df: pd.DataFrame, 
        symbols: List[str], 
        fields: List[str],
        skip_paused: bool = False,
        fq: Optional[str] = None
    ) -> pd.DataFrame:
        """将价格数据格式化为聚宽风格"""
        if df.empty:
            return df
        
        # 重命名列以匹配聚宽格式
        column_mapping = {v: k for k, v in self.jq_field_mapping.items()}
        df = df.rename(columns=column_mapping)
        
        # 设置索引
        if 'datetime' in df.columns:
            df = df.set_index('datetime')
        
        # 如果是单个证券，移除symbol列
        if len(symbols) == 1 and 'symbol' in df.columns:
            df = df.drop('symbol', axis=1)
        
        # 处理复权（简化实现）
        if fq == 'pre':
            # 前复权处理
            pass
        elif fq == 'post':
            # 后复权处理
            pass
        
        # 跳过停牌数据
        if skip_paused and 'paused' in df.columns:
            df = df[df['paused'] != 1]
        
        return df
    
    def _format_fundamental_data_jq_style(self, df: pd.DataFrame) -> pd.DataFrame:
        """将基本面数据格式化为聚宽风格"""
        if df.empty:
            return df
        
        # 聚宽基本面数据通常以symbol为索引
        if 'symbol' in df.columns:
            df = df.set_index('symbol')
        
        return df
    
    def _format_current_data_jq_style(
        self, 
        df: pd.DataFrame, 
        fields: List[str]
    ) -> pd.DataFrame:
        """将当前数据格式化为聚宽风格"""
        if df.empty:
            return df
        
        # 重命名列
        column_mapping = {v: k for k, v in self.jq_field_mapping.items()}
        df = df.rename(columns=column_mapping)
        
        # 聚宽当前数据以symbol为索引
        if 'symbol' in df.columns:
            df = df.set_index('symbol')
        
        return df[fields] if fields else df
    
    def _format_security_info_jq_style(self, df: pd.DataFrame) -> pd.DataFrame:
        """将证券信息格式化为聚宽风格"""
        if df.empty:
            return df
        
        # 聚宽证券信息字段映射
        jq_info_mapping = {
            'symbol': 'code',
            'name': 'display_name',
            'exchange': 'exchange',
            'list_date': 'start_date',
            'delist_date': 'end_date'
        }
        
        df = df.rename(columns=jq_info_mapping)
        
        # 添加聚宽特有字段
        if 'type' not in df.columns:
            df['type'] = 'stock'  # 默认为股票类型
        
        if 'code' in df.columns:
            df = df.set_index('code')
        
        return df


# 全局API实例（单例模式）
_jq_api_instance: Optional[JQCompatibleAPI] = None


def initialize_jq_api(data_source_manager: DataSourceManager, data_source_name: Optional[str] = None):
    """初始化聚宽兼容API"""
    global _jq_api_instance
    _jq_api_instance = JQCompatibleAPI(data_source_manager)
    asyncio.run(_jq_api_instance.initialize(data_source_name))


def get_jq_api() -> JQCompatibleAPI:
    """获取聚宽兼容API实例"""
    if _jq_api_instance is None:
        raise RuntimeError("JQ API not initialized. Call initialize_jq_api() first.")
    return _jq_api_instance


# 聚宽兼容的全局函数
def get_price(
    security: Union[str, List[str]],
    start_date: Optional[Union[str, datetime, date]] = None,
    end_date: Optional[Union[str, datetime, date]] = None,
    frequency: str = 'daily',
    fields: Optional[List[str]] = None,
    skip_paused: bool = False,
    fq: Optional[str] = None,
    count: Optional[int] = None
) -> pd.DataFrame:
    """获取历史价格数据（全局函数）"""
    api = get_jq_api()
    return api.get_price(security, start_date, end_date, frequency, fields, skip_paused, fq, count)


def get_fundamentals(
    query,
    date: Optional[Union[str, datetime, date]] = None,
    statDate: Optional[Union[str, datetime, date]] = None
) -> pd.DataFrame:
    """获取基本面数据（全局函数）"""
    api = get_jq_api()
    return api.get_fundamentals(query, date, statDate)


def get_current_data(
    security: Optional[Union[str, List[str]]] = None,
    fields: Optional[List[str]] = None
) -> pd.DataFrame:
    """获取当前数据（全局函数）"""
    api = get_jq_api()
    return api.get_current_data(security, fields)


def attribute_history(
    security: Union[str, List[str]],
    count: int,
    unit: str = '1d',
    fields: List[str] = ['close'],
    skip_paused: bool = False,
    df: bool = True,
    fq: Optional[str] = None
) -> Union[pd.DataFrame, pd.Series, Dict]:
    """获取历史数据（全局函数）"""
    api = get_jq_api()
    return api.attribute_history(security, count, unit, fields, skip_paused, df, fq)


def get_security_info(code: Union[str, List[str]]) -> Union[Dict, pd.DataFrame]:
    """获取证券信息（全局函数）"""
    api = get_jq_api()
    return api.get_security_info(code)