import React, { useEffect, useState } from 'react';
import {
  Card,
  Row,
  Col,
  Typography,
  List,
  Tag,
  Button,
  Space,
  Statistic,
  Table,
  Switch,
  message,
} from 'antd';
import {
  PlayCircleOutlined,
  PauseCircleOutlined,
  StopOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { useQuery } from 'react-query';
import { tradingAPI } from '../../services/api';

const { Title } = Typography;

const TradingDashboard: React.FC = () => {
  const [activeStrategies, setActiveStrategies] = useState<any[]>([]);

  // 获取交易信号
  const { data: signals, isLoading: signalsLoading, refetch: refetchSignals } = useQuery(
    'tradingSignals',
    () => tradingAPI.getSignals({ limit: 20 }),
    { refetchInterval: 5000 }
  );

  // 获取交易记录
  const { data: records, isLoading: recordsLoading } = useQuery(
    'tradingRecords',
    () => tradingAPI.getRecords({ limit: 20 }),
    { refetchInterval: 10000 }
  );

  // 获取交易统计
  const { data: statistics, isLoading: statsLoading } = useQuery(
    'tradingStatistics',
    tradingAPI.getStatistics,
    { refetchInterval: 30000 }
  );

  // 获取活跃策略
  const { data: strategies, isLoading: strategiesLoading, refetch: refetchStrategies } = useQuery(
    'activeStrategies',
    tradingAPI.getActiveStrategies,
    { refetchInterval: 10000 }
  );

  useEffect(() => {
    if (strategies) {
      setActiveStrategies(strategies);
    }
  }, [strategies]);

  const handleStrategyToggle = async (strategyId: number, enabled: boolean) => {
    try {
      if (enabled) {
        await tradingAPI.addStrategy(strategyId);
        message.success('策略已启动');
      } else {
        await tradingAPI.removeStrategy(strategyId);
        message.success('策略已停止');
      }
      refetchStrategies();
    } catch (error: any) {
      message.error(error.message || '操作失败');
    }
  };

  const signalColumns = [
    {
      title: '时间',
      dataIndex: 'timestamp',
      key: 'timestamp',
      render: (timestamp: string) => new Date(timestamp).toLocaleString(),
    },
    {
      title: '股票代码',
      dataIndex: 'symbol',
      key: 'symbol',
    },
    {
      title: '信号类型',
      dataIndex: 'signal_type',
      key: 'signal_type',
      render: (type: string) => (
        <Tag color={type === 'BUY' ? 'green' : 'red'}>
          {type === 'BUY' ? '买入' : '卖出'}
        </Tag>
      ),
    },
    {
      title: '数量',
      dataIndex: 'quantity',
      key: 'quantity',
      render: (value: number) => value.toLocaleString(),
    },
    {
      title: '价格',
      dataIndex: 'price',
      key: 'price',
      render: (value: number) => value ? `¥${value.toFixed(2)}` : '-',
    },
    {
      title: '置信度',
      dataIndex: 'confidence',
      key: 'confidence',
      render: (value: number) => `${(value * 100).toFixed(1)}%`,
    },
    {
      title: '原因',
      dataIndex: 'reason',
      key: 'reason',
      ellipsis: true,
    },
  ];

  const recordColumns = [
    {
      title: '时间',
      dataIndex: 'timestamp',
      key: 'timestamp',
      render: (timestamp: string) => new Date(timestamp).toLocaleString(),
    },
    {
      title: '股票代码',
      dataIndex: 'symbol',
      key: 'symbol',
    },
    {
      title: '操作',
      dataIndex: 'action',
      key: 'action',
      render: (action: string) => (
        <Tag color={action === 'BUY' ? 'green' : 'red'}>
          {action === 'BUY' ? '买入' : '卖出'}
        </Tag>
      ),
    },
    {
      title: '数量',
      dataIndex: 'quantity',
      key: 'quantity',
      render: (value: number) => value.toLocaleString(),
    },
    {
      title: '价格',
      dataIndex: 'price',
      key: 'price',
      render: (value: number) => `¥${value.toFixed(2)}`,
    },
    {
      title: '金额',
      dataIndex: 'amount',
      key: 'amount',
      render: (value: number) => `¥${value.toLocaleString()}`,
    },
    {
      title: '手续费',
      dataIndex: 'commission',
      key: 'commission',
      render: (value: number) => `¥${value.toFixed(2)}`,
    },
  ];

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Title level={2}>实时交易</Title>
        </Col>
        <Col>
          <Space>
            <Button
              icon={<ReloadOutlined />}
              onClick={() => {
                refetchSignals();
                refetchStrategies();
              }}
            >
              刷新
            </Button>
          </Space>
        </Col>
      </Row>

      {/* 统计卡片 */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="今日收益"
              value={statistics?.daily_pnl || 0}
              precision={2}
              valueStyle={{ color: (statistics?.daily_pnl || 0) > 0 ? '#3f8600' : '#cf1322' }}
              prefix="¥"
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="总资产"
              value={statistics?.total_value || 0}
              precision={2}
              valueStyle={{ color: '#1890ff' }}
              prefix="¥"
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="活跃策略"
              value={activeStrategies.length}
              valueStyle={{ color: '#722ed1' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="今日交易"
              value={statistics?.daily_trades || 0}
              valueStyle={{ color: '#13c2c2' }}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={16}>
        {/* 活跃策略 */}
        <Col span={8}>
          <Card
            title="活跃策略"
            extra={
              <Button
                size="small"
                onClick={refetchStrategies}
                loading={strategiesLoading}
              >
                刷新
              </Button>
            }
          >
            <List
              loading={strategiesLoading}
              dataSource={activeStrategies}
              renderItem={(strategy: any) => (
                <List.Item
                  actions={[
                    <Switch
                      key="toggle"
                      checked={strategy.enabled}
                      onChange={(checked) => handleStrategyToggle(strategy.id, checked)}
                      size="small"
                    />,
                  ]}
                >
                  <List.Item.Meta
                    title={strategy.name}
                    description={
                      <Space>
                        <Tag color={strategy.status === 'running' ? 'green' : 'orange'}>
                          {strategy.status === 'running' ? '运行中' : '已暂停'}
                        </Tag>
                        <span>收益: {strategy.pnl ? `¥${strategy.pnl.toFixed(2)}` : '¥0.00'}</span>
                      </Space>
                    }
                  />
                </List.Item>
              )}
            />
          </Card>
        </Col>

        {/* 最新信号 */}
        <Col span={16}>
          <Card
            title="最新交易信号"
            extra={
              <Button
                size="small"
                onClick={() => refetchSignals()}
                loading={signalsLoading}
              >
                刷新
              </Button>
            }
          >
            <Table
              columns={signalColumns}
              dataSource={signals?.slice(0, 10) || []}
              loading={signalsLoading}
              pagination={false}
              size="small"
              scroll={{ y: 300 }}
            />
          </Card>
        </Col>
      </Row>

      {/* 交易记录 */}
      <Row style={{ marginTop: 16 }}>
        <Col span={24}>
          <Card title="最新交易记录">
            <Table
              columns={recordColumns}
              dataSource={records || []}
              loading={recordsLoading}
              pagination={{
                pageSize: 10,
                showSizeChanger: true,
                showQuickJumper: true,
              }}
              size="small"
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default TradingDashboard;