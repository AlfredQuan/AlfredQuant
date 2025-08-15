"""
数据源工厂
用于创建和配置不同的数据源实例
"""

from typing import Dict, Any, Optional
from quant_framework.core.config import WindConfig
from quant_framework.core.exceptions import ConfigurationError
from quant_framework.data.interfaces import IDataSource, IDataCache, IDataValidator
from quant_framework.data.sources.wind_adapter import WindDataAdapter
from quant_framework.data.validators import DataValidator
from quant_framework.utils.logger import LoggerMixin


class DataSourceFactory(LoggerMixin):
    """数据源工厂类"""
    
    # 支持的数据源类型
    SUPPORTED_SOURCES = {
        'wind': WindDataAdapter,
        # 未来可以添加其他数据源
        # 'tushare': TushareAdapter,
        # 'akshare': AkshareAdapter,
    }
    
    @classmethod
    def create_wind_source(
        cls,
        config: WindConfig,
        validator: Optional[IDataValidator] = None,
        cache: Optional[IDataCache] = None
    ) -> WindDataAdapter:
        """
        创建万得数据源
        
        Args:
            config: 万得配置
            validator: 数据验证器
            cache: 缓存实例
            
        Returns:
            万得数据适配器实例
        """
        if not config.username or not config.password:
            raise ConfigurationError("Wind username and password are required")
        
        validator = validator or DataValidator()
        
        adapter = WindDataAdapter(config, validator, cache)
        
        cls._get_logger().info(
            "Wind data source created",
            username=config.username,
            server=config.server,
            rate_limit=config.rate_limit
        )
        
        return adapter
    
    @classmethod
    def create_source(
        cls,
        source_type: str,
        config: Dict[str, Any],
        validator: Optional[IDataValidator] = None,
        cache: Optional[IDataCache] = None
    ) -> IDataSource:
        """
        创建数据源实例
        
        Args:
            source_type: 数据源类型
            config: 配置字典
            validator: 数据验证器
            cache: 缓存实例
            
        Returns:
            数据源实例
            
        Raises:
            ConfigurationError: 配置错误
        """
        if source_type not in cls.SUPPORTED_SOURCES:
            raise ConfigurationError(
                f"Unsupported data source type: {source_type}. "
                f"Supported types: {list(cls.SUPPORTED_SOURCES.keys())}"
            )
        
        source_class = cls.SUPPORTED_SOURCES[source_type]
        
        try:
            if source_type == 'wind':
                wind_config = WindConfig(**config)
                return cls.create_wind_source(wind_config, validator, cache)
            else:
                # 其他数据源的创建逻辑
                return source_class(config, validator, cache)
                
        except Exception as e:
            cls._get_logger().error(
                "Failed to create data source",
                source_type=source_type,
                error=str(e)
            )
            raise ConfigurationError(f"Failed to create {source_type} data source: {e}")
    
    @classmethod
    def create_from_config_dict(
        cls,
        sources_config: Dict[str, Dict[str, Any]],
        validator: Optional[IDataValidator] = None,
        cache: Optional[IDataCache] = None
    ) -> Dict[str, IDataSource]:
        """
        从配置字典创建多个数据源
        
        Args:
            sources_config: 数据源配置字典
            validator: 数据验证器
            cache: 缓存实例
            
        Returns:
            数据源实例字典
            
        Example:
            sources_config = {
                'wind_primary': {
                    'type': 'wind',
                    'username': 'user1',
                    'password': 'pass1',
                    'server': 'server1'
                },
                'wind_backup': {
                    'type': 'wind',
                    'username': 'user2',
                    'password': 'pass2',
                    'server': 'server2'
                }
            }
        """
        sources = {}
        
        for name, config in sources_config.items():
            if 'type' not in config:
                cls._get_logger().warning(
                    "Data source config missing type",
                    source_name=name
                )
                continue
            
            source_type = config.pop('type')
            
            try:
                source = cls.create_source(source_type, config, validator, cache)
                sources[name] = source
                
                cls._get_logger().info(
                    "Data source created from config",
                    source_name=name,
                    source_type=source_type
                )
                
            except Exception as e:
                cls._get_logger().error(
                    "Failed to create data source from config",
                    source_name=name,
                    source_type=source_type,
                    error=str(e)
                )
                # 继续创建其他数据源，不因为一个失败而全部失败
                continue
        
        return sources
    
    @classmethod
    def get_supported_sources(cls) -> list[str]:
        """获取支持的数据源类型列表"""
        return list(cls.SUPPORTED_SOURCES.keys())
    
    @classmethod
    def _get_logger(cls):
        """获取日志记录器"""
        from quant_framework.utils.logger import get_logger
        return get_logger(cls.__name__)


# 便捷函数
def create_wind_source(
    username: str,
    password: str,
    server: str = "default",
    timeout: int = 30,
    max_retries: int = 3,
    rate_limit: int = 100,
    validator: Optional[IDataValidator] = None,
    cache: Optional[IDataCache] = None
) -> WindDataAdapter:
    """
    便捷函数：创建万得数据源
    
    Args:
        username: 万得用户名
        password: 万得密码
        server: 服务器地址
        timeout: 超时时间
        max_retries: 最大重试次数
        rate_limit: 限流阈值
        validator: 数据验证器
        cache: 缓存实例
        
    Returns:
        万得数据适配器实例
    """
    config = WindConfig(
        username=username,
        password=password,
        server=server,
        timeout=timeout,
        max_retries=max_retries,
        rate_limit=rate_limit
    )
    
    return DataSourceFactory.create_wind_source(config, validator, cache)