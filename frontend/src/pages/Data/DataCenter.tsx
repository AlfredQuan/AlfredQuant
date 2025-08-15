import React, { useState } from 'react';
import {
  Card,
  Row,
  Col,
  Typography,
  Input,
  Select,
  Button,
  Table,
  DatePicker,
  Space,
  Tag,
  message,
} from 'antd';
import {
  SearchOutlined,
  DownloadOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { useQuery } from 'react-query';
import { dataAPI } from '../../services/api';
import dayjs from 'dayjs';

const { Title } = Typography;
const { Search } = Input;
const { Option } = Select;
const { RangePicker } = DatePicker;

const DataCenter: React.FC = () => {
  const [searchParams, setSearchParams] = useState({
    search: '',
    exchange: '',
    sector: '',
  });
  const [priceParams, setPriceParams] = useState({
    symbols: [] as string[],
    start_date: dayjs().subtract(30, 'day').format('YYYY-MM-DD'),
    end_date: dayjs().format('YYYY-MM-DD'),
    frequency: '1d',
  });

  // 获取证券列表
  const { data: securities, isLoading: securitiesLoading, refetch: refetchSecurities } = useQuery(
    ['securities', searchParams],
    () => dataAPI.getSecurities(searchParams),
    { enabled: true }
  );

  // 获取价格数据
  const { data: priceData, isLoading: priceLoading, refetch: refetchPriceData } = useQuery(
    ['priceData', priceParams],
    () => dataAPI.getPriceData(priceParams),
    { enabled: priceParams.symbols.length > 0 }
  );

  const handleSearch = (value: string) => {
    setSearchParams(prev => ({ ...prev, search: value }));
  };

  const handleExchangeChange = (value: string) => {
    setSearchParams(prev => ({ ...prev, exchange: value }));
  };

  const handleSectorChange = (value: string) => {
    setSearchParams(prev => ({ ...prev, sector: value }));
  };

  const handleSymbolSelect = (selectedRowKeys: React.Key[]) => {
    setPriceParams(prev => ({
      ...prev,
      symbols: selectedRowKeys as string[],
    }));
  };

  const handleDateRangeChange = (dates: any) => {
    if (dates && dates.length === 2) {
      setPriceParams(prev => ({
        ...prev,
        start_date: dates[0].format('YYYY-MM-DD'),
        end_date: dates[1].format('YYYY-MM-DD'),
      }));
    }
  };

  const handleFrequencyChange = (value: string) => {
    setPriceParams(prev => ({ ...prev, frequency: value }));
  };

  const handleDownloadData = () => {
    if (priceParams.symbols.length === 0) {
      message.warning('请先选择股票');
      return;
    }
    
    // TODO: 实现数据下载
    message.info('数据下载功能开发中');
  };

  const securitiesColumns = [
    {
      title: '股票代码',
      dataIndex: 'symbol',
      key: 'symbol',
    },
    {
      title: '股票名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '交易所',
      dataIndex: 'exchange',
      key: 'exchange',
      render: (exchange: string) => {
        const exchangeMap: Record<string, { text: string; color: string }> = {
          'SH': { text: '上交所', color: 'blue' },
          'SZ': { text: '深交所', color: 'green' },
          'BJ': { text: '北交所', color: 'orange' },
        };
        const info = exchangeMap[exchange] || { text: exchange, color: 'default' };
        return <Tag color={info.color}>{info.text}</Tag>;
      },
    },
    {
      title: '行业',
      dataIndex: 'sector',
      key: 'sector',
    },
    {
      title: '市值',
      dataIndex: 'market_cap',
      key: 'market_cap',
      render: (value: number) => value ? `${(value / 100000000).toFixed(2)}亿` : '-',
    },
    {
      title: '最新价',
      dataIndex: 'last_price',
      key: 'last_price',
      render: (value: number) => value ? `¥${value.toFixed(2)}` : '-',
    },
    {
      title: '涨跌幅',
      dataIndex: 'change_pct',
      key: 'change_pct',
      render: (value: number) => (
        <span style={{ color: value > 0 ? '#52c41a' : value < 0 ? '#ff4d4f' : '#666' }}>
          {value ? `${(value * 100).toFixed(2)}%` : '-'}
        </span>
      ),
    },
  ];

  const priceColumns = [
    {
      title: '日期',
      dataIndex: 'date',
      key: 'date',
    },
    {
      title: '股票代码',
      dataIndex: 'symbol',
      key: 'symbol',
    },
    {
      title: '开盘价',
      dataIndex: 'open',
      key: 'open',
      render: (value: number) => `¥${value.toFixed(2)}`,
    },
    {
      title: '最高价',
      dataIndex: 'high',
      key: 'high',
      render: (value: number) => `¥${value.toFixed(2)}`,
    },
    {
      title: '最低价',
      dataIndex: 'low',
      key: 'low',
      render: (value: number) => `¥${value.toFixed(2)}`,
    },
    {
      title: '收盘价',
      dataIndex: 'close',
      key: 'close',
      render: (value: number) => `¥${value.toFixed(2)}`,
    },
    {
      title: '成交量',
      dataIndex: 'volume',
      key: 'volume',
      render: (value: number) => value.toLocaleString(),
    },
    {
      title: '成交额',
      dataIndex: 'amount',
      key: 'amount',
      render: (value: number) => `¥${(value / 10000).toFixed(2)}万`,
    },
  ];

  // 模拟证券数据
  const mockSecurities = [
    {
      symbol: '000001.SZ',
      name: '平安银行',
      exchange: 'SZ',
      sector: '银行',
      market_cap: 250000000000,
      last_price: 12.85,
      change_pct: 0.0234,
    },
    {
      symbol: '000002.SZ',
      name: '万科A',
      exchange: 'SZ',
      sector: '房地产',
      market_cap: 180000000000,
      last_price: 16.42,
      change_pct: -0.0156,
    },
    {
      symbol: '600000.SH',
      name: '浦发银行',
      exchange: 'SH',
      sector: '银行',
      market_cap: 320000000000,
      last_price: 10.98,
      change_pct: 0.0089,
    },
    {
      symbol: '600036.SH',
      name: '招商银行',
      exchange: 'SH',
      sector: '银行',
      market_cap: 1200000000000,
      last_price: 42.15,
      change_pct: 0.0198,
    },
  ];

  // 模拟价格数据
  const mockPriceData = priceParams.symbols.length > 0 ? 
    Array.from({ length: 30 }, (_, i) => ({
      date: dayjs().subtract(29 - i, 'day').format('YYYY-MM-DD'),
      symbol: priceParams.symbols[0],
      open: 10 + Math.random() * 5,
      high: 12 + Math.random() * 5,
      low: 8 + Math.random() * 5,
      close: 10 + Math.random() * 5,
      volume: Math.floor(Math.random() * 1000000) + 100000,
      amount: Math.floor(Math.random() * 100000000) + 10000000,
    })) : [];

  return (
    <div>
      <Title level={2}>数据中心</Title>

      <Row gutter={16}>
        {/* 证券查询 */}
        <Col span={12}>
          <Card
            title="证券查询"
            extra={
              <Button
                size="small"
                icon={<ReloadOutlined />}
                onClick={() => refetchSecurities()}
                loading={securitiesLoading}
              >
                刷新
              </Button>
            }
          >
            <Space direction="vertical" style={{ width: '100%', marginBottom: 16 }}>
              <Search
                placeholder="搜索股票代码或名称"
                allowClear
                onSearch={handleSearch}
                style={{ width: '100%' }}
              />
              <Row gutter={8}>
                <Col span={12}>
                  <Select
                    placeholder="选择交易所"
                    allowClear
                    style={{ width: '100%' }}
                    onChange={handleExchangeChange}
                  >
                    <Option value="SH">上交所</Option>
                    <Option value="SZ">深交所</Option>
                    <Option value="BJ">北交所</Option>
                  </Select>
                </Col>
                <Col span={12}>
                  <Select
                    placeholder="选择行业"
                    allowClear
                    style={{ width: '100%' }}
                    onChange={handleSectorChange}
                  >
                    <Option value="银行">银行</Option>
                    <Option value="房地产">房地产</Option>
                    <Option value="科技">科技</Option>
                    <Option value="医药">医药</Option>
                  </Select>
                </Col>
              </Row>
            </Space>

            <Table
              columns={securitiesColumns}
              dataSource={securities || mockSecurities}
              loading={securitiesLoading}
              rowKey="symbol"
              rowSelection={{
                type: 'checkbox',
                onChange: handleSymbolSelect,
                selectedRowKeys: priceParams.symbols,
              }}
              pagination={{
                pageSize: 10,
                showSizeChanger: true,
              }}
              size="small"
              scroll={{ y: 400 }}
            />
          </Card>
        </Col>

        {/* 价格数据 */}
        <Col span={12}>
          <Card
            title="价格数据"
            extra={
              <Space>
                <Button
                  size="small"
                  icon={<DownloadOutlined />}
                  onClick={handleDownloadData}
                  disabled={priceParams.symbols.length === 0}
                >
                  下载
                </Button>
                <Button
                  size="small"
                  icon={<ReloadOutlined />}
                  onClick={() => refetchPriceData()}
                  loading={priceLoading}
                  disabled={priceParams.symbols.length === 0}
                >
                  刷新
                </Button>
              </Space>
            }
          >
            <Space direction="vertical" style={{ width: '100%', marginBottom: 16 }}>
              <Row gutter={8}>
                <Col span={12}>
                  <RangePicker
                    style={{ width: '100%' }}
                    value={[dayjs(priceParams.start_date), dayjs(priceParams.end_date)]}
                    onChange={handleDateRangeChange}
                  />
                </Col>
                <Col span={12}>
                  <Select
                    value={priceParams.frequency}
                    style={{ width: '100%' }}
                    onChange={handleFrequencyChange}
                  >
                    <Option value="1m">1分钟</Option>
                    <Option value="5m">5分钟</Option>
                    <Option value="15m">15分钟</Option>
                    <Option value="1h">1小时</Option>
                    <Option value="1d">1天</Option>
                    <Option value="1w">1周</Option>
                  </Select>
                </Col>
              </Row>
            </Space>

            {priceParams.symbols.length > 0 ? (
              <Table
                columns={priceColumns}
                dataSource={priceData || mockPriceData}
                loading={priceLoading}
                rowKey={(record) => `${record.symbol}-${record.date}`}
                pagination={{
                  pageSize: 10,
                  showSizeChanger: true,
                }}
                size="small"
                scroll={{ y: 400 }}
              />
            ) : (
              <div style={{ textAlign: 'center', padding: '40px', color: '#999' }}>
                请先选择股票代码
              </div>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default DataCenter;