"""
万得数据适配器
实现万得数据接口的集成
"""

import asyncio
import time
from datetime import datetime, date
from typing import List, Dict, Any, Optional, Union
import pandas as pd
from decimal import Decimal

from quant_framework.core.constants import DataFrequency, SecurityType
from quant_framework.core.exceptions import (
    DataSourceError, NetworkError, RateLimitError, DataValidationError
)
from quant_framework.core.config import WindConfig
from quant_framework.data.base import BaseDataSource
from quant_framework.data.interfaces import IDataCache, IDataValidator
from quant_framework.utils.logger import LoggerMixin


class RateLimiter:
    """限流器"""
    
    def __init__(self, max_calls: int, time_window: int = 60):
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = []
    
    async def acquire(self):
        """获取调用许可"""
        now = time.time()
        
        # 清理过期的调用记录
        self.calls = [call_time for call_time in self.calls 
                     if now - call_time < self.time_window]
        
        # 检查是否超过限制
        if len(self.calls) >= self.max_calls:
            wait_time = self.time_window - (now - self.calls[0])
            if wait_time > 0:
                raise RateLimitError(
                    f"Rate limit exceeded, retry after {wait_time:.1f} seconds",
                    retry_after=int(wait_time) + 1
                )
        
        # 记录本次调用
        self.calls.append(now)


class WindDataAdapter(BaseDataSource):
    """万得数据适配器"""
    
    def __init__(
        self,
        config: WindConfig,
        validator: Optional[IDataValidator] = None,
        cache: Optional[IDataCache] = None
    ):
        super().__init__("Wind", config.__dict__, validator, cache)
        self.wind_config = config
        self.rate_limiter = RateLimiter(
            max_calls=config.rate_limit,
            time_window=60
        )
        self._wind_api = None
        self._retry_count = 0
        
        # 万得字段映射
        self.field_mapping = {
            'open': 'open',
            'high': 'high', 
            'low': 'low',
            'close': 'close',
            'volume': 'volume',
            'amount': 'amt',
            'adj_close': 'adjclose',
            'current_price': 'rt_last',
            'bid_price': 'rt_bid1',
            'ask_price': 'rt_ask1',
            'bid_volume': 'rt_bsize1',
            'ask_volume': 'rt_asize1'
        }
        
        # 频率映射
        self.frequency_mapping = {
            DataFrequency.DAILY: 'D',
            DataFrequency.WEEKLY: 'W',
            DataFrequency.MONTHLY: 'M',
            DataFrequency.MINUTE: '1',
            DataFrequency.MINUTE_5: '5',
            DataFrequency.MINUTE_15: '15',
            DataFrequency.MINUTE_30: '30',
            DataFrequency.HOUR: '60'
        }
    
    async def _do_connect(self) -> bool:
        """连接万得API"""
        try:
            # 动态导入万得API（避免在没有安装时报错）
            try:
                from WindPy import w
                self._wind_api = w
            except ImportError:
                # 如果没有安装WindPy，使用模拟API
                self.logger.warning("WindPy not installed, using mock API")
                self._wind_api = MockWindAPI()
                return True
            
            # 启动万得API
            error_code = self._wind_api.start()
            
            if error_code.ErrorCode != 0:
                self.logger.error(
                    "Failed to start Wind API",
                    error_code=error_code.ErrorCode,
                    error_msg=error_code.Data
                )
                return False
            
            # 检查连接状态
            if not self._wind_api.isconnected():
                self.logger.error("Wind API not connected")
                return False
            
            self.logger.info("Wind API connected successfully")
            return True
            
        except Exception as e:
            self.log_error(e, {"method": "_do_connect"})
            return False
    
    async def _do_disconnect(self) -> None:
        """断开万得API连接"""
        try:
            if self._wind_api and hasattr(self._wind_api, 'stop'):
                self._wind_api.stop()
            self._wind_api = None
        except Exception as e:
            self.log_error(e, {"method": "_do_disconnect"})
    
    async def _do_health_check(self) -> bool:
        """健康检查"""
        try:
            if not self._wind_api:
                return False
            
            if hasattr(self._wind_api, 'isconnected'):
                return self._wind_api.isconnected()
            
            # 对于模拟API，总是返回True
            return True
            
        except Exception as e:
            self.log_error(e, {"method": "_do_health_check"})
            return False
    
    async def _fetch_price_data(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        frequency: DataFrequency,
        fields: List[str]
    ) -> pd.DataFrame:
        """获取价格数据"""
        await self.rate_limiter.acquire()
        
        # 转换字段名
        wind_fields = [self.field_mapping.get(field, field) for field in fields]
        wind_frequency = self.frequency_mapping.get(frequency, 'D')
        
        # 格式化日期
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        
        try:
            # 调用万得API
            result = await self._call_wind_api_with_retry(
                'wsd',
                symbols,
                wind_fields,
                start_str,
                end_str,
                f"Period={wind_frequency}"
            )
            
            if result.ErrorCode != 0:
                raise DataSourceError(f"Wind API error: {result.Data}")
            
            # 转换为DataFrame
            df = self._convert_wsd_result_to_dataframe(result, symbols, fields)
            
            return df
            
        except Exception as e:
            self.log_error(e, {
                "method": "_fetch_price_data",
                "symbols": symbols[:3],  # 只记录前3个
                "start_date": start_str,
                "end_date": end_str
            })
            raise
    
    async def _fetch_fundamental_data(
        self,
        symbols: List[str],
        fields: List[str],
        date: Optional[datetime]
    ) -> pd.DataFrame:
        """获取基本面数据"""
        await self.rate_limiter.acquire()
        
        # 转换字段名
        wind_fields = [self.field_mapping.get(field, field) for field in fields]
        
        # 确定查询日期
        query_date = date.strftime('%Y-%m-%d') if date else datetime.now().strftime('%Y-%m-%d')
        
        try:
            # 调用万得API
            result = await self._call_wind_api_with_retry(
                'wss',
                symbols,
                wind_fields,
                f"tradeDate={query_date}"
            )
            
            if result.ErrorCode != 0:
                raise DataSourceError(f"Wind API error: {result.Data}")
            
            # 转换为DataFrame
            df = self._convert_wss_result_to_dataframe(result, symbols, fields)
            
            return df
            
        except Exception as e:
            self.log_error(e, {
                "method": "_fetch_fundamental_data",
                "symbols": symbols[:3],
                "date": query_date
            })
            raise
    
    async def _fetch_realtime_data(
        self,
        symbols: List[str],
        fields: List[str]
    ) -> pd.DataFrame:
        """获取实时数据"""
        await self.rate_limiter.acquire()
        
        # 转换字段名
        wind_fields = [self.field_mapping.get(field, field) for field in fields]
        
        try:
            # 调用万得API
            result = await self._call_wind_api_with_retry(
                'wsq',
                symbols,
                wind_fields
            )
            
            if result.ErrorCode != 0:
                raise DataSourceError(f"Wind API error: {result.Data}")
            
            # 转换为DataFrame
            df = self._convert_wsq_result_to_dataframe(result, symbols, fields)
            
            return df
            
        except Exception as e:
            self.log_error(e, {
                "method": "_fetch_realtime_data",
                "symbols": symbols[:3]
            })
            raise
    
    async def _fetch_security_info(self, symbols: List[str]) -> pd.DataFrame:
        """获取证券信息"""
        await self.rate_limiter.acquire()
        
        info_fields = ['sec_name', 'exch_city', 'ipo_date', 'delist_date']
        
        try:
            result = await self._call_wind_api_with_retry(
                'wss',
                symbols,
                info_fields
            )
            
            if result.ErrorCode != 0:
                raise DataSourceError(f"Wind API error: {result.Data}")
            
            # 转换为DataFrame
            df = self._convert_security_info_to_dataframe(result, symbols)
            
            return df
            
        except Exception as e:
            self.log_error(e, {
                "method": "_fetch_security_info",
                "symbols": symbols[:3]
            })
            raise
    
    async def _search_securities(
        self,
        keyword: str,
        security_type: Optional[SecurityType] = None,
        exchange: Optional[str] = None
    ) -> pd.DataFrame:
        """搜索证券"""
        await self.rate_limiter.acquire()
        
        try:
            # 构建搜索条件
            options = []
            if security_type:
                type_mapping = {
                    SecurityType.STOCK: 'equity',
                    SecurityType.FUND: 'fund',
                    SecurityType.BOND: 'bond'
                }
                if security_type in type_mapping:
                    options.append(f"sectorid={type_mapping[security_type]}")
            
            if exchange:
                options.append(f"exchmarket={exchange}")
            
            option_str = ';'.join(options) if options else ""
            
            # 调用万得API搜索
            result = await self._call_wind_api_with_retry(
                'wset',
                'sectorconstituent',
                f"sectorid=a001010100000000;field=wind_code,sec_name",
                option_str
            )
            
            if result.ErrorCode != 0:
                raise DataSourceError(f"Wind API error: {result.Data}")
            
            # 转换结果并过滤
            df = pd.DataFrame(result.Data, columns=result.Fields)
            if not df.empty and keyword:
                # 按关键词过滤
                mask = df['sec_name'].str.contains(keyword, case=False, na=False)
                df = df[mask]
            
            return df
            
        except Exception as e:
            self.log_error(e, {
                "method": "_search_securities",
                "keyword": keyword
            })
            raise
    
    async def _call_wind_api_with_retry(self, method: str, *args, **kwargs):
        """带重试的万得API调用"""
        for attempt in range(self.wind_config.max_retries):
            try:
                # 获取API方法
                api_method = getattr(self._wind_api, method)
                
                # 调用API（同步转异步）
                result = await asyncio.get_event_loop().run_in_executor(
                    None, api_method, *args, **kwargs
                )
                
                return result
                
            except Exception as e:
                self._retry_count += 1
                
                if attempt == self.wind_config.max_retries - 1:
                    # 最后一次重试失败
                    raise NetworkError(f"Wind API call failed after {self.wind_config.max_retries} retries: {e}")
                
                # 等待后重试
                wait_time = 2 ** attempt  # 指数退避
                self.logger.warning(
                    "Wind API call failed, retrying",
                    attempt=attempt + 1,
                    wait_time=wait_time,
                    error=str(e)
                )
                
                await asyncio.sleep(wait_time)
    
    def _convert_wsd_result_to_dataframe(
        self, 
        result, 
        symbols: List[str], 
        fields: List[str]
    ) -> pd.DataFrame:
        """转换wsd结果为DataFrame"""
        if not result.Data or len(result.Data) == 0:
            return pd.DataFrame()
        
        # 构建DataFrame
        data_dict = {}
        
        # 处理多个证券的情况
        if len(symbols) == 1:
            # 单个证券
            data_dict['symbol'] = [symbols[0]] * len(result.Times)
            data_dict['datetime'] = result.Times
            
            for i, field in enumerate(fields):
                if i < len(result.Data):
                    data_dict[field] = result.Data[i]
        else:
            # 多个证券
            all_data = []
            for i, symbol in enumerate(symbols):
                for j, timestamp in enumerate(result.Times):
                    row = {'symbol': symbol, 'datetime': timestamp}
                    for k, field in enumerate(fields):
                        if i * len(result.Times) + j < len(result.Data[k]):
                            row[field] = result.Data[k][i * len(result.Times) + j]
                    all_data.append(row)
            
            return pd.DataFrame(all_data)
        
        df = pd.DataFrame(data_dict)
        
        # 数据类型转换
        numeric_fields = ['open', 'high', 'low', 'close', 'volume', 'amount']
        for field in numeric_fields:
            if field in df.columns:
                df[field] = pd.to_numeric(df[field], errors='coerce')
        
        return df
    
    def _convert_wss_result_to_dataframe(
        self, 
        result, 
        symbols: List[str], 
        fields: List[str]
    ) -> pd.DataFrame:
        """转换wss结果为DataFrame"""
        if not result.Data or len(result.Data) == 0:
            return pd.DataFrame()
        
        data_dict = {'symbol': symbols}
        
        for i, field in enumerate(fields):
            if i < len(result.Data):
                data_dict[field] = result.Data[i]
        
        df = pd.DataFrame(data_dict)
        return df
    
    def _convert_wsq_result_to_dataframe(
        self, 
        result, 
        symbols: List[str], 
        fields: List[str]
    ) -> pd.DataFrame:
        """转换wsq结果为DataFrame"""
        if not result.Data or len(result.Data) == 0:
            return pd.DataFrame()
        
        data_dict = {
            'symbol': symbols,
            'timestamp': [datetime.now()] * len(symbols)
        }
        
        for i, field in enumerate(fields):
            if i < len(result.Data):
                data_dict[field] = result.Data[i]
        
        df = pd.DataFrame(data_dict)
        return df
    
    def _convert_security_info_to_dataframe(self, result, symbols: List[str]) -> pd.DataFrame:
        """转换证券信息为DataFrame"""
        if not result.Data or len(result.Data) == 0:
            return pd.DataFrame()
        
        data = []
        for i, symbol in enumerate(symbols):
            info = {
                'symbol': symbol,
                'name': result.Data[0][i] if len(result.Data) > 0 else '',
                'exchange': result.Data[1][i] if len(result.Data) > 1 else '',
                'list_date': result.Data[2][i] if len(result.Data) > 2 else None,
                'delist_date': result.Data[3][i] if len(result.Data) > 3 else None,
            }
            data.append(info)
        
        return pd.DataFrame(data)


class MockWindAPI:
    """模拟万得API（用于测试和开发）"""
    
    def __init__(self):
        self._connected = False
    
    def start(self):
        """启动API"""
        self._connected = True
        return MockResult(0, "Success")
    
    def stop(self):
        """停止API"""
        self._connected = False
    
    def isconnected(self):
        """检查连接状态"""
        return self._connected
    
    def wsd(self, symbols, fields, start_date, end_date, options=""):
        """模拟历史数据查询"""
        import random
        from datetime import datetime, timedelta
        
        # 生成模拟数据
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        
        dates = []
        current = start
        while current <= end:
            dates.append(current)
            current += timedelta(days=1)
        
        data = []
        for field in fields:
            field_data = []
            for _ in dates:
                if field in ['open', 'high', 'low', 'close']:
                    field_data.append(round(random.uniform(10, 100), 2))
                elif field == 'volume':
                    field_data.append(random.randint(1000, 100000))
                else:
                    field_data.append(random.uniform(1, 1000))
            data.append(field_data)
        
        return MockResult(0, data, fields, dates)
    
    def wss(self, symbols, fields, options=""):
        """模拟截面数据查询"""
        import random
        
        data = []
        for field in fields:
            field_data = []
            for _ in symbols:
                if 'name' in field:
                    field_data.append(f"股票{random.randint(1, 999)}")
                elif 'price' in field:
                    field_data.append(round(random.uniform(10, 100), 2))
                else:
                    field_data.append(random.uniform(1, 1000))
            data.append(field_data)
        
        return MockResult(0, data, fields)
    
    def wsq(self, symbols, fields, options=""):
        """模拟实时数据查询"""
        return self.wss(symbols, fields, options)
    
    def wset(self, table_name, options="", **kwargs):
        """模拟数据集查询"""
        # 返回模拟的证券列表
        mock_data = [
            ['000001.SZ', '平安银行'],
            ['000002.SZ', '万科A'],
            ['600000.SH', '浦发银行']
        ]
        
        return MockResult(0, mock_data, ['wind_code', 'sec_name'])


class MockResult:
    """模拟万得API返回结果"""
    
    def __init__(self, error_code, data=None, fields=None, times=None):
        self.ErrorCode = error_code
        self.Data = data or []
        self.Fields = fields or []
        self.Times = times or []