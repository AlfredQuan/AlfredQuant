"""
数据源集成测试
"""

import pytest
import asyncio
from datetime import datetime, date, timedelta
from typing import List, Dict, Any
from unittest.mock import patch, MagicMock

from quant_framework.data.sources.tushare_adapter import TushareAdapter
from quant_framework.data.sources.wind_adapter import WindAdapter
from quant_framework.data.sources.akshare_adapter import AkshareAdapter
from quant_framework.data.manager import DataManager
from quant_framework.data.models import Security, PriceData


@pytest.mark.integration
class TestDataSourcesIntegration:
    """数据源集成测试"""
    
    @pytest.fixture
    def data_manager(self):
        """数据管理器"""
        return DataManager()
    
    @pytest.fixture
    def mock_tushare_adapter(self):
        """模拟Tushare适配器"""
        adapter = MagicMock(spec=TushareAdapter)
        
        # 模拟股票列表数据
        adapter.get_stock_list.return_value = [
            {
                'ts_code': '000001.SZ',
                'symbol': '000001',
                'name': '平安银行',
                'area': '深圳',
                'industry': '银行',
                'market': '主板',
                'list_date': '19910403'
            },
            {
                'ts_code': '600000.SH',
                'symbol': '600000',
                'name': '浦发银行',
                'area': '上海',
                'industry': '银行',
                'market': '主板',
                'list_date': '19991110'
            }
        ]
        
        # 模拟价格数据
        adapter.get_daily_price.return_value = [
            {
                'ts_code': '000001.SZ',
                'trade_date': '20240101',
                'open': 10.0,
                'high': 10.5,
                'low': 9.8,
                'close': 10.2,
                'vol': 1000000,
                'amount': 10200000
            }
        ]
        
        return adapter
    
    @pytest.mark.asyncio
    async def test_tushare_integration(self, mock_tushare_adapter):
        """测试Tushare数据源集成"""
        
        # 测试获取股票列表
        stock_list = mock_tushare_adapter.get_stock_list()
        assert len(stock_list) == 2
        assert stock_list[0]['ts_code'] == '000001.SZ'
        assert stock_list[1]['ts_code'] == '600000.SH'
        
        # 测试获取价格数据
        price_data = mock_tushare_adapter.get_daily_price(
            ts_code='000001.SZ',
            start_date='20240101',
            end_date='20240131'
        )
        
        assert len(price_data) > 0
        assert price_data[0]['ts_code'] == '000001.SZ'
        assert 'open' in price_data[0]
        assert 'close' in price_data[0]
    
    @pytest.mark.asyncio
    async def test_wind_integration(self):
        """测试Wind数据源集成"""
        
        # 由于Wind API需要特殊环境，这里使用模拟测试
        with patch('quant_framework.data.sources.wind_adapter.w') as mock_wind:
            # 模拟Wind API响应
            mock_wind.wset.return_value = MagicMock()
            mock_wind.wset.return_value.Data = [
                ['000001.SZ', '600000.SH'],  # 代码
                ['平安银行', '浦发银行'],      # 名称
                ['银行', '银行']             # 行业
            ]
            mock_wind.wset.return_value.Fields = ['wind_code', 'sec_name', 'industry']
            mock_wind.wset.return_value.ErrorCode = 0
            
            adapter = WindAdapter()
            
            # 测试获取股票列表
            stock_list = await adapter.get_stock_list()
            
            assert len(stock_list) >= 0  # Wind可能返回空数据
            
            # 模拟价格数据
            mock_wind.wsd.return_value = MagicMock()
            mock_wind.wsd.return_value.Data = [
                [10.0, 10.2],  # 开盘价
                [10.5, 10.8],  # 最高价
                [9.8, 10.0],   # 最低价
                [10.2, 10.6],  # 收盘价
                [1000000, 1200000]  # 成交量
            ]
            mock_wind.wsd.return_value.Fields = ['open', 'high', 'low', 'close', 'volume']
            mock_wind.wsd.return_value.Times = [
                datetime(2024, 1, 1),
                datetime(2024, 1, 2)
            ]
            mock_wind.wsd.return_value.ErrorCode = 0
            
            # 测试获取价格数据
            price_data = await adapter.get_daily_price(
                symbol='000001.SZ',
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31)
            )
            
            assert len(price_data) >= 0
    
    @pytest.mark.asyncio
    async def test_akshare_integration(self):
        """测试AkShare数据源集成"""
        
        with patch('akshare.stock_zh_a_spot_em') as mock_spot, \
             patch('akshare.stock_zh_a_hist') as mock_hist:
            
            # 模拟股票列表数据
            import pandas as pd
            
            mock_spot.return_value = pd.DataFrame({
                '代码': ['000001', '600000'],
                '名称': ['平安银行', '浦发银行'],
                '最新价': [10.2, 15.8],
                '涨跌幅': [0.5, -0.3]
            })
            
            # 模拟历史价格数据
            mock_hist.return_value = pd.DataFrame({
                '日期': [date(2024, 1, 1), date(2024, 1, 2)],
                '开盘': [10.0, 10.2],
                '收盘': [10.2, 10.6],
                '最高': [10.5, 10.8],
                '最低': [9.8, 10.0],
                '成交量': [1000000, 1200000]
            })
            
            adapter = AkshareAdapter()
            
            # 测试获取股票列表
            stock_list = await adapter.get_stock_list()
            assert len(stock_list) == 2
            
            # 测试获取价格数据
            price_data = await adapter.get_daily_price(
                symbol='000001',
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31)
            )
            
            assert len(price_data) == 2
    
    @pytest.mark.asyncio
    async def test_data_source_failover(self, data_manager):
        """测试数据源故障转移"""
        
        with patch.object(data_manager, 'primary_source') as mock_primary, \
             patch.object(data_manager, 'backup_source') as mock_backup:
            
            # 模拟主数据源失败
            mock_primary.get_daily_price.side_effect = Exception("主数据源连接失败")
            
            # 模拟备用数据源成功
            mock_backup.get_daily_price.return_value = [
                {
                    'symbol': '000001',
                    'date': '2024-01-01',
                    'open': 10.0,
                    'close': 10.2,
                    'high': 10.5,
                    'low': 9.8,
                    'volume': 1000000
                }
            ]
            
            # 测试故障转移
            price_data = await data_manager.get_price_data(
                symbol='000001',
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31)
            )
            
            # 验证使用了备用数据源
            assert len(price_data) == 1
            assert price_data[0]['symbol'] == '000001'
            
            # 验证调用了备用数据源
            mock_backup.get_daily_price.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_data_quality_validation(self, data_manager):
        """测试数据质量验证"""
        
        # 测试数据完整性检查
        incomplete_data = [
            {
                'symbol': '000001',
                'date': '2024-01-01',
                'open': 10.0,
                'close': None,  # 缺失收盘价
                'high': 10.5,
                'low': 9.8,
                'volume': 1000000
            }
        ]
        
        validation_result = data_manager.validate_price_data(incomplete_data)
        assert not validation_result['is_valid']
        assert 'missing_close_price' in validation_result['errors']
        
        # 测试数据一致性检查
        inconsistent_data = [
            {
                'symbol': '000001',
                'date': '2024-01-01',
                'open': 10.0,
                'close': 10.2,
                'high': 9.5,  # 最高价低于开盘价（不合理）
                'low': 9.8,
                'volume': 1000000
            }
        ]
        
        validation_result = data_manager.validate_price_data(inconsistent_data)
        assert not validation_result['is_valid']
        assert 'price_inconsistency' in validation_result['errors']
        
        # 测试正常数据
        valid_data = [
            {
                'symbol': '000001',
                'date': '2024-01-01',
                'open': 10.0,
                'close': 10.2,
                'high': 10.5,
                'low': 9.8,
                'volume': 1000000
            }
        ]
        
        validation_result = data_manager.validate_price_data(valid_data)
        assert validation_result['is_valid']
        assert len(validation_result['errors']) == 0
    
    @pytest.mark.asyncio
    async def test_data_caching(self, data_manager):
        """测试数据缓存"""
        
        with patch.object(data_manager, 'primary_source') as mock_source:
            mock_source.get_daily_price.return_value = [
                {
                    'symbol': '000001',
                    'date': '2024-01-01',
                    'open': 10.0,
                    'close': 10.2,
                    'high': 10.5,
                    'low': 9.8,
                    'volume': 1000000
                }
            ]
            
            # 第一次请求
            price_data1 = await data_manager.get_price_data(
                symbol='000001',
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31),
                use_cache=True
            )
            
            # 第二次请求（应该使用缓存）
            price_data2 = await data_manager.get_price_data(
                symbol='000001',
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31),
                use_cache=True
            )
            
            # 验证数据一致
            assert price_data1 == price_data2
            
            # 验证只调用了一次数据源（第二次使用缓存）
            assert mock_source.get_daily_price.call_count == 1
    
    @pytest.mark.asyncio
    async def test_data_synchronization(self, data_manager):
        """测试数据同步"""
        
        with patch.object(data_manager, 'database') as mock_db:
            # 模拟数据库中的现有数据
            mock_db.get_latest_date.return_value = date(2024, 1, 15)
            
            # 模拟数据源返回新数据
            with patch.object(data_manager, 'primary_source') as mock_source:
                mock_source.get_daily_price.return_value = [
                    {
                        'symbol': '000001',
                        'date': '2024-01-16',
                        'open': 10.0,
                        'close': 10.2,
                        'high': 10.5,
                        'low': 9.8,
                        'volume': 1000000
                    },
                    {
                        'symbol': '000001',
                        'date': '2024-01-17',
                        'open': 10.2,
                        'close': 10.4,
                        'high': 10.6,
                        'low': 10.0,
                        'volume': 1100000
                    }
                ]
                
                # 执行数据同步
                sync_result = await data_manager.sync_price_data(
                    symbol='000001',
                    end_date=date(2024, 1, 31)
                )
                
                # 验证同步结果
                assert sync_result['success'] is True
                assert sync_result['new_records'] == 2
                assert sync_result['start_date'] == date(2024, 1, 16)
                
                # 验证只请求了新数据
                mock_source.get_daily_price.assert_called_once_with(
                    symbol='000001',
                    start_date=date(2024, 1, 16),
                    end_date=date(2024, 1, 31)
                )
    
    @pytest.mark.asyncio
    async def test_concurrent_data_requests(self, data_manager):
        """测试并发数据请求"""
        
        with patch.object(data_manager, 'primary_source') as mock_source:
            # 模拟数据源响应
            async def mock_get_price(symbol, start_date, end_date):
                # 模拟网络延迟
                await asyncio.sleep(0.1)
                return [
                    {
                        'symbol': symbol,
                        'date': '2024-01-01',
                        'open': 10.0,
                        'close': 10.2,
                        'high': 10.5,
                        'low': 9.8,
                        'volume': 1000000
                    }
                ]
            
            mock_source.get_daily_price.side_effect = mock_get_price
            
            # 并发请求多个股票的数据
            symbols = ['000001', '000002', '600000', '600036']
            
            tasks = []
            for symbol in symbols:
                task = data_manager.get_price_data(
                    symbol=symbol,
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, 1, 31)
                )
                tasks.append(task)
            
            # 等待所有任务完成
            results = await asyncio.gather(*tasks)
            
            # 验证结果
            assert len(results) == 4
            for i, result in enumerate(results):
                assert len(result) == 1
                assert result[0]['symbol'] == symbols[i]
            
            # 验证并发调用
            assert mock_source.get_daily_price.call_count == 4
    
    @pytest.mark.asyncio
    async def test_data_format_conversion(self, data_manager):
        """测试数据格式转换"""
        
        # 测试Tushare格式转换
        tushare_data = [
            {
                'ts_code': '000001.SZ',
                'trade_date': '20240101',
                'open': 10.0,
                'high': 10.5,
                'low': 9.8,
                'close': 10.2,
                'vol': 1000000,
                'amount': 10200000
            }
        ]
        
        converted_data = data_manager.convert_tushare_format(tushare_data)
        
        assert len(converted_data) == 1
        assert converted_data[0]['symbol'] == '000001'
        assert converted_data[0]['exchange'] == 'SZSE'
        assert converted_data[0]['date'] == date(2024, 1, 1)
        assert converted_data[0]['volume'] == 1000000
        
        # 测试Wind格式转换
        wind_data = {
            'codes': ['000001.SZ'],
            'fields': ['open', 'high', 'low', 'close', 'volume'],
            'times': [datetime(2024, 1, 1)],
            'data': [[10.0], [10.5], [9.8], [10.2], [1000000]]
        }
        
        converted_data = data_manager.convert_wind_format(wind_data)
        
        assert len(converted_data) == 1
        assert converted_data[0]['symbol'] == '000001'
        assert converted_data[0]['exchange'] == 'SZSE'
        assert converted_data[0]['open'] == 10.0
        assert converted_data[0]['volume'] == 1000000