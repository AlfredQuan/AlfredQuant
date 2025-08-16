"""
数据提供者基础类
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime, date
import pandas as pd


class DataProvider(ABC):
    """数据提供者抽象基类"""
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        self.name = name
        self.config = config or {}
        self._connected = False
    
    @abstractmethod
    def connect(self) -> bool:
        """连接到数据源"""
        pass
    
    @abstractmethod
    def disconnect(self) -> bool:
        """断开数据源连接"""
        pass
    
    @abstractmethod
    def get_price_data(
        self, 
        symbol: str, 
        start_date: date, 
        end_date: date,
        frequency: str = "daily"
    ) -> pd.DataFrame:
        """获取价格数据"""
        pass
    
    @abstractmethod
    def get_market_data(
        self, 
        symbols: List[str], 
        start_date: date, 
        end_date: date
    ) -> Dict[str, pd.DataFrame]:
        """获取市场数据"""
        pass
    
    @abstractmethod
    def get_fundamental_data(
        self, 
        symbol: str, 
        start_date: date, 
        end_date: date
    ) -> pd.DataFrame:
        """获取基本面数据"""
        pass
    
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._connected
    
    def __enter__(self):
        """上下文管理器入口"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.disconnect()


class TushareProvider(DataProvider):
    """Tushare数据提供者"""
    
    def __init__(self, token: Optional[str] = None):
        super().__init__("tushare", {"token": token})
        self.client = None
    
    def connect(self) -> bool:
        """连接到Tushare"""
        try:
            import tushare as ts
            if self.config.get("token"):
                ts.set_token(self.config["token"])
                self.client = ts.pro_api()
            else:
                self.client = ts
            self._connected = True
            return True
        except ImportError:
            print("Tushare not installed. Please install: pip install tushare")
            return False
        except Exception as e:
            print(f"Failed to connect to Tushare: {e}")
            return False
    
    def disconnect(self) -> bool:
        """断开Tushare连接"""
        self.client = None
        self._connected = False
        return True
    
    def get_price_data(
        self, 
        symbol: str, 
        start_date: date, 
        end_date: date,
        frequency: str = "daily"
    ) -> pd.DataFrame:
        """获取价格数据"""
        if not self._connected:
            raise RuntimeError("Not connected to data source")
        
        # 这里是示例实现，实际需要根据Tushare API调用
        # 返回模拟数据
        dates = pd.date_range(start_date, end_date, freq='D')
        data = pd.DataFrame({
            'date': dates,
            'open': 100.0,
            'high': 105.0,
            'low': 95.0,
            'close': 102.0,
            'volume': 1000000
        })
        return data
    
    def get_market_data(
        self, 
        symbols: List[str], 
        start_date: date, 
        end_date: date
    ) -> Dict[str, pd.DataFrame]:
        """获取市场数据"""
        result = {}
        for symbol in symbols:
            result[symbol] = self.get_price_data(symbol, start_date, end_date)
        return result
    
    def get_fundamental_data(
        self, 
        symbol: str, 
        start_date: date, 
        end_date: date
    ) -> pd.DataFrame:
        """获取基本面数据"""
        # 返回模拟基本面数据
        dates = pd.date_range(start_date, end_date, freq='Q')
        data = pd.DataFrame({
            'date': dates,
            'revenue': 1000000000,
            'profit': 100000000,
            'eps': 1.5,
            'pe_ratio': 15.0
        })
        return data


class WindProvider(DataProvider):
    """Wind数据提供者"""
    
    def __init__(self, username: Optional[str] = None, password: Optional[str] = None):
        super().__init__("wind", {"username": username, "password": password})
        self.client = None
    
    def connect(self) -> bool:
        """连接到Wind"""
        try:
            from WindPy import w
            result = w.start()
            if result.ErrorCode == 0:
                self.client = w
                self._connected = True
                return True
            else:
                print(f"Failed to connect to Wind: {result.Data}")
                return False
        except ImportError:
            print("WindPy not installed. Please install Wind terminal and WindPy")
            return False
        except Exception as e:
            print(f"Failed to connect to Wind: {e}")
            return False
    
    def disconnect(self) -> bool:
        """断开Wind连接"""
        if self.client:
            try:
                self.client.stop()
            except:
                pass
        self.client = None
        self._connected = False
        return True
    
    def get_price_data(
        self, 
        symbol: str, 
        start_date: date, 
        end_date: date,
        frequency: str = "daily"
    ) -> pd.DataFrame:
        """获取价格数据"""
        if not self._connected:
            raise RuntimeError("Not connected to data source")
        
        # 返回模拟数据
        dates = pd.date_range(start_date, end_date, freq='D')
        data = pd.DataFrame({
            'date': dates,
            'open': 100.0,
            'high': 105.0,
            'low': 95.0,
            'close': 102.0,
            'volume': 1000000
        })
        return data
    
    def get_market_data(
        self, 
        symbols: List[str], 
        start_date: date, 
        end_date: date
    ) -> Dict[str, pd.DataFrame]:
        """获取市场数据"""
        result = {}
        for symbol in symbols:
            result[symbol] = self.get_price_data(symbol, start_date, end_date)
        return result
    
    def get_fundamental_data(
        self, 
        symbol: str, 
        start_date: date, 
        end_date: date
    ) -> pd.DataFrame:
        """获取基本面数据"""
        # 返回模拟基本面数据
        dates = pd.date_range(start_date, end_date, freq='Q')
        data = pd.DataFrame({
            'date': dates,
            'revenue': 1000000000,
            'profit': 100000000,
            'eps': 1.5,
            'pe_ratio': 15.0
        })
        return data


# 数据提供者工厂
class DataProviderFactory:
    """数据提供者工厂"""
    
    _providers = {
        "tushare": TushareProvider,
        "wind": WindProvider
    }
    
    @classmethod
    def create_provider(cls, provider_type: str, **kwargs) -> DataProvider:
        """创建数据提供者"""
        if provider_type not in cls._providers:
            raise ValueError(f"Unknown provider type: {provider_type}")
        
        provider_class = cls._providers[provider_type]
        return provider_class(**kwargs)
    
    @classmethod
    def get_available_providers(cls) -> List[str]:
        """获取可用的数据提供者列表"""
        return list(cls._providers.keys())