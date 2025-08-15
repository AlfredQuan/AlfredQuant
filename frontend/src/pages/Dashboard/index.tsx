import React, { useEffect, useState } from 'react';
import { Row, Col, Card, Statistic, Table, List, Typography, Spin } from 'antd';
import {
  ArrowUpOutlined,
  ArrowDownOutlined,
  DollarOutlined,
  TrophyOutlined,
  RiseOutlined,
  FallOutlined,
} from '@ant-design/icons';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { useQuery } from 'react-query';
import { systemAPI, strategyAPI, backtestAPI, tradingAPI } from '../../services/api';

const { Title } = Typography;

const Dashboard: React.FC = () => {
  const [performanceData, setPerformanceData] = useState<any[]>([]);

  // 获取系统统计
  const { data: systemStats, isLoading: systemLoading } = useQuery(
    'systemStats',
    systemAPI.getStatistics,
    { refetchInterval: 30000 }
  );

  // 获取策略列表
  const { data: strategies, isLoading: strategiesLoading } = useQuery(
    'strategies',
    () => strategyAPI.getStrategies({ page: 1, size: 5 })
  );

  // 获取最近回测
  const { data: recentBacktests, isLoading: backtestsLoading } = useQuery(
    'recentBacktests',
    () => backtestAPI.getBacktests({ page: 1, size: 5 })
  );

  // 获取交易信号
  const { data: tradingSignals, isLoading: signalsLoading } = useQuery(
    'tradingSignals',
    () => tradingAPI.getSignals({ limit: 10 }),
    { refetchInterval: 10000 }
  );

  useEffect(() => {
    // 模拟性能数据
    const mockData = Array.from({ length: 30 }, (_, i) => ({
      date: new Date(Date.now() - (29 - i) * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
      value: 100000 + Math.random() * 20000 - 10000,
      benchmark: 100000 + Math.random() * 10000 - 5000,
    }));
    setPerformanceData(mockData);
  }, []);

  const strategyColumns = [
    {
      title: '策略名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <span style={{ color: status === 'active' ? '#52c41a' : '#faad14' }}>
          {status === 'active' ? '运行中' : '已停止'}
        </span>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => new Date(date).toLocaleDateString(),
    },
  ];

  const backtestColumns = [
    {
      title: '回测名称',
      dataIndex: 'name',
      key: 'name',
      render: (name: string) => name || '未命名回测',
    },
    {
      title: '总收益率',
      dataIndex: 'total_return',
      key: 'total_return',
      render: (value: number) => (
        <span style={{ color: value > 0 ? '#52c41a' : '#ff4d4f' }}>
          {value ? `${(value * 100).toFixed(2)}%` : '-'}
        </span>
      ),
    },
    {
      title: '夏普比率',
      dataIndex: 'sharpe_ratio',
      key: 'sharpe_ratio',
      render: (value: number) => value ? value.toFixed(2) : '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const statusMap: Record<string, { text: string; color: string }> = {
          completed: { text: '已完成', color: '#52c41a' },
          running: { text: '运行中', color: '#1890ff' },
          failed: { text: '失败', color: '#ff4d4f' },
          pending: { text: '等待中', color: '#faad14' },
        };
        const statusInfo = statusMap[status] || { text: status, color: '#666' };
        return <span style={{ color: statusInfo.color }}>{statusInfo.text}</span>;
      },
    },
  ];

  if (systemLoading || strategiesLoading || backtestsLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '400px' }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div>
      <Title level={2}>仪表板</Title>
      
      {/* 统计卡片 */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="总资产"
              value={1234567}
              precision={2}
              valueStyle={{ color: '#3f8600' }}
              prefix={<DollarOutlined />}
              suffix="¥"
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="今日收益"
              value={11.28}
              precision={2}
              valueStyle={{ color: '#3f8600' }}
              prefix={<ArrowUpOutlined />}
              suffix="%"
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="活跃策略"
              value={strategies?.data?.filter(s => s.status === 'active').length || 0}
              valueStyle={{ color: '#1890ff' }}
              prefix={<TrophyOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="总交易次数"
              value={1128}
              valueStyle={{ color: '#722ed1' }}
              prefix={<RiseOutlined />}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={16}>
        {/* 性能图表 */}
        <Col span={16}>
          <Card title="投资组合表现" style={{ marginBottom: 16 }}>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={performanceData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke="#1890ff"
                  strokeWidth={2}
                  name="投资组合"
                />
                <Line
                  type="monotone"
                  dataKey="benchmark"
                  stroke="#52c41a"
                  strokeWidth={2}
                  name="基准"
                />
              </LineChart>
            </ResponsiveContainer>
          </Card>
        </Col>

        {/* 交易信号 */}
        <Col span={8}>
          <Card title="最新交易信号" style={{ marginBottom: 16 }}>
            <List
              loading={signalsLoading}
              dataSource={tradingSignals?.slice(0, 5) || []}
              renderItem={(signal: any) => (
                <List.Item>
                  <div className="signal-item">
                    <div className="signal-info">
                      <div className="signal-symbol">{signal.symbol}</div>
                      <div className="signal-type">
                        <span style={{ 
                          color: signal.signal_type === 'BUY' ? '#52c41a' : '#ff4d4f' 
                        }}>
                          {signal.signal_type === 'BUY' ? '买入' : '卖出'}
                        </span>
                        <span style={{ marginLeft: 8 }}>
                          {signal.quantity}股
                        </span>
                      </div>
                      <div className="signal-time">
                        {new Date(signal.timestamp).toLocaleString()}
                      </div>
                    </div>
                  </div>
                </List.Item>
              )}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={16}>
        {/* 策略列表 */}
        <Col span={12}>
          <Card title="最近策略">
            <Table
              loading={strategiesLoading}
              dataSource={strategies?.data || []}
              columns={strategyColumns}
              pagination={false}
              size="small"
            />
          </Card>
        </Col>

        {/* 回测列表 */}
        <Col span={12}>
          <Card title="最近回测">
            <Table
              loading={backtestsLoading}
              dataSource={recentBacktests?.data || []}
              columns={backtestColumns}
              pagination={false}
              size="small"
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Dashboard;