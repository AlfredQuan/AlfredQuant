"""
数据服务基础类
提供数据源管理和统一接口
"""

from abc import ABC
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, date
import asyncio
import pandas as pd

from quant_framework.core.constants import DataFrequency, SecurityType
from quant_framework.core.exceptions import DataSourceError, NetworkError
from quant_framework.data.interfaces import IDataSource, IDataCache, IDataValidator
from quant_framework.data.validators import DataValidator, DataCleaner
from quant_framework.utils.logger import LoggerMixin


class BaseDataSource(IDataSource, LoggerMixin):
    """数据源基础类"""
    
    def __init__(
        self,
        name: str,
        config: Dict[str, Any],
        validator: Optional[IDataValidator] = None,
        cache: Optional[IDataCache] = None
    ):
        self.name = name
        self.config = config
        self.validator = validator or DataValidator()
        self.cache = cache
        self.cleaner = DataCleaner()
        self._connected = False
        self._connection_pool = None
    
    async def connect(self) -> bool:
        """连接数据源"""
        try:
            self.log_method_call("connect", source=self.name)
            success = await self._do_connect()
            self._connected = success
            
            if success:
                self.logger.info("Data source connected", source=self.name)
            else:
                self.logger.error("Failed to connect data source", source=self.name)
            
            return success
        except Exception as e:
            self.log_error(e, {"source": self.name, "method": "connect"})
            raise DataSourceError(f"Connection failed: {e}")
    
    async def disconnect(self) -> None:
        """断开连接"""
        try:
            self.log_method_call("disconnect", source=self.name)
            await self._do_disconnect()
            self._connected = False
            self.logger.info("Data source disconnected", source=self.name)
        except Exception as e:
            self.log_error(e, {"source": self.name, "method": "disconnect"})
    
    async def health_check(self) -> bool:
        """健康检查"""
        try:
            if not self._connected:
                return False
            
            return await self._do_health_check()
        except Exception as e:
            self.log_error(e, {"source": self.name, "method": "health_check"})
            return False
    
    async def get_price_data(
        self,
        symbols: List[str],
        start_date: Union[str, date, datetime],
        end_date: Union[str, date, datetime],
        frequency: DataFrequency = DataFrequency.DAILY,
        fields: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """获取价格数据"""
        # 验证输入参数
        valid_symbols = self.validator.validate_symbols(symbols)
        start_dt, end_dt = self.validator.validate_date_range(start_date, end_date)
        valid_fields = self.validator.validate_fields(
            fields or ['open', 'high', 'low', 'close', 'volume'], 
            'price_data'
        )
        
        # 生成缓存键
        cache_key = self._generate_cache_key(
            'price', valid_symbols, start_dt, end_dt, frequency, valid_fields
        )
        
        # 尝试从缓存获取
        if self.cache:
            cached_data = await self.cache.get(cache_key)
            if cached_data is not None:
                self.logger.debug("Cache hit for price data", cache_key=cache_key)
                return cached_data
        
        try:
            # 从数据源获取
            self.log_method_call(
                "get_price_data",
                symbols=len(valid_symbols),
                start_date=start_dt,
                end_date=end_dt,
                frequency=frequency
            )
            
            raw_data = await self._fetch_price_data(
                valid_symbols, start_dt, end_dt, frequency, valid_fields
            )
            
            # 数据清洗
            clean_data = self.cleaner.clean_price_data(raw_data)
            
            # 验证结果
            if not self.validator.validate_dataframe(clean_data, valid_fields):
                raise DataSourceError("Invalid data structure returned")
            
            # 缓存结果
            if self.cache and not clean_data.empty:
                await self.cache.set(cache_key, clean_data, ttl=300)  # 5分钟缓存
            
            self.logger.info(
                "Price data retrieved",
                source=self.name,
                symbols_count=len(valid_symbols),
                records_count=len(clean_data)
            )
            
            return clean_data
            
        except Exception as e:
            self.log_error(e, {
                "source": self.name,
                "method": "get_price_data",
                "symbols": valid_symbols[:5]  # 只记录前5个symbol
            })
            raise DataSourceError(f"Failed to get price data: {e}")
    
    async def get_fundamental_data(
        self,
        symbols: List[str],
        fields: List[str],
        date: Optional[Union[str, date, datetime]] = None
    ) -> pd.DataFrame:
        """获取基本面数据"""
        valid_symbols = self.validator.validate_symbols(symbols)
        valid_fields = self.validator.validate_fields(fields, 'fundamental_data')
        
        query_date = None
        if date:
            query_date, _ = self.validator.validate_date_range(date, date)
        
        cache_key = self._generate_cache_key(
            'fundamental', valid_symbols, query_date, None, None, valid_fields
        )
        
        if self.cache:
            cached_data = await self.cache.get(cache_key)
            if cached_data is not None:
                return cached_data
        
        try:
            raw_data = await self._fetch_fundamental_data(
                valid_symbols, valid_fields, query_date
            )
            
            if self.cache and not raw_data.empty:
                await self.cache.set(cache_key, raw_data, ttl=3600)  # 1小时缓存
            
            return raw_data
            
        except Exception as e:
            self.log_error(e, {"source": self.name, "method": "get_fundamental_data"})
            raise DataSourceError(f"Failed to get fundamental data: {e}")
    
    async def get_realtime_data(
        self,
        symbols: List[str],
        fields: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """获取实时数据"""
        valid_symbols = self.validator.validate_symbols(symbols)
        valid_fields = self.validator.validate_fields(
            fields or ['current_price', 'volume'], 
            'realtime_data'
        )
        
        try:
            raw_data = await self._fetch_realtime_data(valid_symbols, valid_fields)
            return raw_data
            
        except Exception as e:
            self.log_error(e, {"source": self.name, "method": "get_realtime_data"})
            raise DataSourceError(f"Failed to get realtime data: {e}")
    
    async def get_security_info(self, symbols: List[str]) -> pd.DataFrame:
        """获取证券信息"""
        valid_symbols = self.validator.validate_symbols(symbols)
        
        cache_key = self._generate_cache_key('security_info', valid_symbols)
        
        if self.cache:
            cached_data = await self.cache.get(cache_key)
            if cached_data is not None:
                return cached_data
        
        try:
            raw_data = await self._fetch_security_info(valid_symbols)
            
            if self.cache and not raw_data.empty:
                await self.cache.set(cache_key, raw_data, ttl=86400)  # 1天缓存
            
            return raw_data
            
        except Exception as e:
            self.log_error(e, {"source": self.name, "method": "get_security_info"})
            raise DataSourceError(f"Failed to get security info: {e}")
    
    async def search_securities(
        self,
        keyword: str,
        security_type: Optional[SecurityType] = None,
        exchange: Optional[str] = None
    ) -> pd.DataFrame:
        """搜索证券"""
        try:
            return await self._search_securities(keyword, security_type, exchange)
        except Exception as e:
            self.log_error(e, {"source": self.name, "method": "search_securities"})
            raise DataSourceError(f"Failed to search securities: {e}")
    
    def _generate_cache_key(self, data_type: str, *args) -> str:
        """生成缓存键"""
        key_parts = [self.name, data_type]
        for arg in args:
            if arg is not None:
                if isinstance(arg, (list, tuple)):
                    key_parts.append('_'.join(str(x) for x in arg))
                else:
                    key_parts.append(str(arg))
        return ':'.join(key_parts)
    
    # 子类需要实现的抽象方法
    async def _do_connect(self) -> bool:
        """实际连接逻辑"""
        raise NotImplementedError
    
    async def _do_disconnect(self) -> None:
        """实际断开连接逻辑"""
        raise NotImplementedError
    
    async def _do_health_check(self) -> bool:
        """实际健康检查逻辑"""
        raise NotImplementedError
    
    async def _fetch_price_data(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        frequency: DataFrequency,
        fields: List[str]
    ) -> pd.DataFrame:
        """实际获取价格数据"""
        raise NotImplementedError
    
    async def _fetch_fundamental_data(
        self,
        symbols: List[str],
        fields: List[str],
        date: Optional[datetime]
    ) -> pd.DataFrame:
        """实际获取基本面数据"""
        raise NotImplementedError
    
    async def _fetch_realtime_data(
        self,
        symbols: List[str],
        fields: List[str]
    ) -> pd.DataFrame:
        """实际获取实时数据"""
        raise NotImplementedError
    
    async def _fetch_security_info(self, symbols: List[str]) -> pd.DataFrame:
        """实际获取证券信息"""
        raise NotImplementedError
    
    async def _search_securities(
        self,
        keyword: str,
        security_type: Optional[SecurityType],
        exchange: Optional[str]
    ) -> pd.DataFrame:
        """实际搜索证券"""
        raise NotImplementedError


class DataSourceManager(LoggerMixin):
    """数据源管理器"""
    
    def __init__(self):
        self._sources: Dict[str, IDataSource] = {}
        self._default_source: Optional[str] = None
    
    def register_source(self, name: str, source: IDataSource, is_default: bool = False):
        """注册数据源"""
        self._sources[name] = source
        if is_default or not self._default_source:
            self._default_source = name
        
        self.logger.info(
            "Data source registered",
            name=name,
            is_default=is_default,
            total_sources=len(self._sources)
        )
    
    def get_source(self, name: Optional[str] = None) -> IDataSource:
        """获取数据源"""
        source_name = name or self._default_source
        
        if not source_name or source_name not in self._sources:
            available = list(self._sources.keys())
            raise DataSourceError(
                f"Data source '{source_name}' not found. Available: {available}"
            )
        
        return self._sources[source_name]
    
    async def connect_all(self) -> Dict[str, bool]:
        """连接所有数据源"""
        results = {}
        
        for name, source in self._sources.items():
            try:
                results[name] = await source.connect()
            except Exception as e:
                self.log_error(e, {"source": name, "method": "connect_all"})
                results[name] = False
        
        return results
    
    async def disconnect_all(self) -> None:
        """断开所有数据源"""
        for name, source in self._sources.items():
            try:
                await source.disconnect()
            except Exception as e:
                self.log_error(e, {"source": name, "method": "disconnect_all"})
    
    async def health_check_all(self) -> Dict[str, bool]:
        """检查所有数据源健康状态"""
        results = {}
        
        for name, source in self._sources.items():
            results[name] = await source.health_check()
        
        return results
    
    def list_sources(self) -> List[str]:
        """列出所有数据源"""
        return list(self._sources.keys())