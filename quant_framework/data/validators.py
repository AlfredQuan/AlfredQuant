"""
数据验证和清洗工具
提供数据质量检查和清洗功能
"""

import re
from datetime import datetime, date
from typing import List, Union, Optional, Dict, Any
import pandas as pd
from decimal import Decimal, InvalidOperation

from quant_framework.core.exceptions import DataValidationError
from quant_framework.core.constants import SecurityType, Exchange
from quant_framework.data.interfaces import IDataValidator
from quant_framework.utils.logger import LoggerMixin


class DataValidator(IDataValidator, LoggerMixin):
    """数据验证器"""
    
    # 证券代码格式规则
    SYMBOL_PATTERNS = {
        'A_STOCK': r'^[0-9]{6}\.(SH|SZ)$',  # A股：6位数字.交易所
        'INDEX': r'^[0-9]{6}\.(SH|SZ)$',    # 指数
        'FUND': r'^[0-9]{6}\.(OF|SH|SZ)$',  # 基金
        'BOND': r'^[0-9]{6}\.(IB|SH|SZ)$',  # 债券
    }
    
    # 必需字段定义
    REQUIRED_FIELDS = {
        'price_data': ['symbol', 'datetime', 'open', 'high', 'low', 'close', 'volume'],
        'fundamental_data': ['symbol', 'date'],
        'realtime_data': ['symbol', 'timestamp', 'current_price'],
        'security_info': ['symbol', 'name', 'security_type', 'exchange']
    }
    
    def validate_symbols(self, symbols: List[str]) -> List[str]:
        """
        验证证券代码格式
        
        Args:
            symbols: 证券代码列表
            
        Returns:
            验证通过的证券代码列表
            
        Raises:
            DataValidationError: 验证失败
        """
        if not symbols:
            raise DataValidationError("Symbol list cannot be empty")
        
        valid_symbols = []
        invalid_symbols = []
        
        for symbol in symbols:
            if self._is_valid_symbol(symbol):
                valid_symbols.append(symbol.upper())
            else:
                invalid_symbols.append(symbol)
        
        if invalid_symbols:
            self.logger.warning(
                "Invalid symbols found",
                invalid_symbols=invalid_symbols,
                valid_count=len(valid_symbols)
            )
            # 可以选择抛出异常或者只记录警告
            # raise DataValidationError(f"Invalid symbols: {invalid_symbols}")
        
        return valid_symbols
    
    def validate_date_range(
        self, 
        start_date: Union[str, date, datetime],
        end_date: Union[str, date, datetime]
    ) -> tuple[datetime, datetime]:
        """
        验证日期范围
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            标准化的日期范围
            
        Raises:
            DataValidationError: 验证失败
        """
        try:
            start_dt = self._parse_date(start_date)
            end_dt = self._parse_date(end_date)
        except ValueError as e:
            raise DataValidationError(f"Invalid date format: {e}")
        
        if start_dt > end_dt:
            raise DataValidationError("Start date cannot be after end date")
        
        # 检查日期范围是否合理（不超过10年）
        if (end_dt - start_dt).days > 3650:
            self.logger.warning(
                "Large date range detected",
                start_date=start_dt,
                end_date=end_dt,
                days=(end_dt - start_dt).days
            )
        
        return start_dt, end_dt
    
    def validate_fields(self, fields: List[str], data_type: str) -> List[str]:
        """
        验证字段名称
        
        Args:
            fields: 字段列表
            data_type: 数据类型
            
        Returns:
            验证通过的字段列表
        """
        if not fields:
            # 如果没有指定字段，返回默认字段
            return self.REQUIRED_FIELDS.get(data_type, [])
        
        # 检查是否包含必需字段
        required = self.REQUIRED_FIELDS.get(data_type, [])
        missing_fields = set(required) - set(fields)
        
        if missing_fields:
            self.logger.warning(
                "Missing required fields",
                data_type=data_type,
                missing_fields=list(missing_fields)
            )
        
        return fields
    
    def validate_dataframe(self, df: pd.DataFrame, expected_columns: List[str]) -> bool:
        """
        验证DataFrame结构
        
        Args:
            df: 待验证的DataFrame
            expected_columns: 期望的列名
            
        Returns:
            是否验证通过
        """
        if df.empty:
            self.logger.warning("DataFrame is empty")
            return False
        
        # 检查列名
        missing_columns = set(expected_columns) - set(df.columns)
        if missing_columns:
            self.logger.error(
                "Missing columns in DataFrame",
                missing_columns=list(missing_columns),
                actual_columns=list(df.columns)
            )
            return False
        
        # 检查数据类型和空值
        for col in expected_columns:
            if col in df.columns:
                null_count = df[col].isnull().sum()
                if null_count > 0:
                    self.logger.warning(
                        "Null values found in column",
                        column=col,
                        null_count=null_count,
                        total_rows=len(df)
                    )
        
        return True
    
    def _is_valid_symbol(self, symbol: str) -> bool:
        """检查证券代码是否有效"""
        if not symbol or not isinstance(symbol, str):
            return False
        
        symbol = symbol.upper()
        
        # 检查各种格式
        for pattern in self.SYMBOL_PATTERNS.values():
            if re.match(pattern, symbol):
                return True
        
        return False
    
    def _parse_date(self, date_input: Union[str, date, datetime]) -> datetime:
        """解析日期"""
        if isinstance(date_input, datetime):
            return date_input
        elif isinstance(date_input, date):
            return datetime.combine(date_input, datetime.min.time())
        elif isinstance(date_input, str):
            # 尝试多种日期格式
            formats = [
                '%Y-%m-%d',
                '%Y/%m/%d',
                '%Y%m%d',
                '%Y-%m-%d %H:%M:%S',
                '%Y/%m/%d %H:%M:%S'
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(date_input, fmt)
                except ValueError:
                    continue
            
            raise ValueError(f"Unable to parse date: {date_input}")
        else:
            raise ValueError(f"Invalid date type: {type(date_input)}")


class DataCleaner(LoggerMixin):
    """数据清洗器"""
    
    def clean_price_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        清洗价格数据
        
        Args:
            df: 原始价格数据
            
        Returns:
            清洗后的数据
        """
        if df.empty:
            return df
        
        df_clean = df.copy()
        
        # 移除重复数据
        initial_count = len(df_clean)
        df_clean = df_clean.drop_duplicates(subset=['symbol', 'datetime'])
        if len(df_clean) < initial_count:
            self.logger.info(
                "Removed duplicate records",
                removed_count=initial_count - len(df_clean)
            )
        
        # 处理价格异常值
        price_columns = ['open', 'high', 'low', 'close']
        for col in price_columns:
            if col in df_clean.columns:
                # 移除负价格
                negative_mask = df_clean[col] < 0
                if negative_mask.any():
                    self.logger.warning(
                        f"Negative prices found in {col}",
                        count=negative_mask.sum()
                    )
                    df_clean = df_clean[~negative_mask]
                
                # 检查异常波动（单日涨跌幅超过50%）
                if col == 'close' and len(df_clean) > 1:
                    df_clean = df_clean.sort_values(['symbol', 'datetime'])
                    pct_change = df_clean.groupby('symbol')[col].pct_change().abs()
                    outlier_mask = pct_change > 0.5
                    if outlier_mask.any():
                        self.logger.warning(
                            "Extreme price changes detected",
                            count=outlier_mask.sum()
                        )
        
        # 验证OHLC关系
        if all(col in df_clean.columns for col in price_columns):
            # High应该是最高价
            invalid_high = (df_clean['high'] < df_clean[['open', 'close']].max(axis=1))
            # Low应该是最低价
            invalid_low = (df_clean['low'] > df_clean[['open', 'close']].min(axis=1))
            
            invalid_mask = invalid_high | invalid_low
            if invalid_mask.any():
                self.logger.warning(
                    "Invalid OHLC relationships found",
                    count=invalid_mask.sum()
                )
                df_clean = df_clean[~invalid_mask]
        
        # 处理成交量
        if 'volume' in df_clean.columns:
            # 移除负成交量
            negative_volume = df_clean['volume'] < 0
            if negative_volume.any():
                self.logger.warning(
                    "Negative volume found",
                    count=negative_volume.sum()
                )
                df_clean = df_clean[~negative_volume]
        
        return df_clean
    
    def fill_missing_data(
        self, 
        df: pd.DataFrame, 
        method: str = 'forward'
    ) -> pd.DataFrame:
        """
        填充缺失数据
        
        Args:
            df: 包含缺失数据的DataFrame
            method: 填充方法 ('forward', 'backward', 'interpolate')
            
        Returns:
            填充后的DataFrame
        """
        if df.empty:
            return df
        
        df_filled = df.copy()
        
        if method == 'forward':
            df_filled = df_filled.fillna(method='ffill')
        elif method == 'backward':
            df_filled = df_filled.fillna(method='bfill')
        elif method == 'interpolate':
            numeric_columns = df_filled.select_dtypes(include=['number']).columns
            df_filled[numeric_columns] = df_filled[numeric_columns].interpolate()
        
        # 记录填充统计
        filled_count = df.isnull().sum().sum() - df_filled.isnull().sum().sum()
        if filled_count > 0:
            self.logger.info(
                "Missing data filled",
                method=method,
                filled_count=filled_count
            )
        
        return df_filled
    
    def normalize_symbol_format(self, symbols: List[str]) -> List[str]:
        """
        标准化证券代码格式
        
        Args:
            symbols: 原始证券代码列表
            
        Returns:
            标准化后的证券代码列表
        """
        normalized = []
        
        for symbol in symbols:
            if not symbol:
                continue
            
            # 转换为大写
            symbol = symbol.upper().strip()
            
            # 处理不同格式
            if '.' not in symbol and len(symbol) == 6:
                # 6位数字，需要添加交易所后缀
                if symbol.startswith(('0', '3')):
                    symbol += '.SZ'  # 深交所
                elif symbol.startswith(('6')):
                    symbol += '.SH'  # 上交所
            
            normalized.append(symbol)
        
        return normalized