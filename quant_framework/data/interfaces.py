"""
数据源接口定义
定义数据源的抽象接口和协议
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, date
import pandas as pd

from quant_framework.core.constants import DataFrequency, SecurityType


class IDataSource(ABC):
    """数据源抽象接口"""
    
    @abstractmethod
    async def connect(self) -> bool:
        """连接数据源"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """断开数据源连接"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """健康检查"""
        pass
    
    @abstractmethod
    async def get_price_data(
        self,
        symbols: List[str],
        start_date: Union[str, date, datetime],
        end_date: Union[str, date, datetime],
        frequency: DataFrequency = DataFrequency.DAILY,
        fields: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        获取价格数据
        
        Args:
            symbols: 证券代码列表
            start_date: 开始日期
            end_date: 结束日期
            frequency: 数据频率
            fields: 字段列表，默认为 ['open', 'high', 'low', 'close', 'volume']
            
        Returns:
            包含价格数据的DataFrame
        """
        pass
    
    @abstractmethod
    async def get_fundamental_data(
        self,
        symbols: List[str],
        fields: List[str],
        date: Optional[Union[str, date, datetime]] = None
    ) -> pd.DataFrame:
        """
        获取基本面数据
        
        Args:
            symbols: 证券代码列表
            fields: 字段列表
            date: 查询日期，None表示最新数据
            
        Returns:
            包含基本面数据的DataFrame
        """
        pass
    
    @abstractmethod
    async def get_realtime_data(
        self,
        symbols: List[str],
        fields: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        获取实时数据
        
        Args:
            symbols: 证券代码列表
            fields: 字段列表
            
        Returns:
            包含实时数据的DataFrame
        """
        pass
    
    @abstractmethod
    async def get_security_info(
        self,
        symbols: List[str]
    ) -> pd.DataFrame:
        """
        获取证券基本信息
        
        Args:
            symbols: 证券代码列表
            
        Returns:
            包含证券信息的DataFrame
        """
        pass
    
    @abstractmethod
    async def search_securities(
        self,
        keyword: str,
        security_type: Optional[SecurityType] = None,
        exchange: Optional[str] = None
    ) -> pd.DataFrame:
        """
        搜索证券
        
        Args:
            keyword: 搜索关键词
            security_type: 证券类型
            exchange: 交易所
            
        Returns:
            包含搜索结果的DataFrame
        """
        pass


class IDataCache(ABC):
    """数据缓存接口"""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存数据"""
        pass
    
    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存数据"""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """删除缓存数据"""
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        """检查缓存是否存在"""
        pass
    
    @abstractmethod
    async def clear(self, pattern: Optional[str] = None) -> int:
        """清除缓存"""
        pass


class IDataValidator(ABC):
    """数据验证接口"""
    
    @abstractmethod
    def validate_symbols(self, symbols: List[str]) -> List[str]:
        """验证证券代码格式"""
        pass
    
    @abstractmethod
    def validate_date_range(
        self, 
        start_date: Union[str, date, datetime],
        end_date: Union[str, date, datetime]
    ) -> tuple[datetime, datetime]:
        """验证日期范围"""
        pass
    
    @abstractmethod
    def validate_fields(self, fields: List[str], data_type: str) -> List[str]:
        """验证字段名称"""
        pass
    
    @abstractmethod
    def validate_dataframe(self, df: pd.DataFrame, expected_columns: List[str]) -> bool:
        """验证DataFrame结构"""
        pass