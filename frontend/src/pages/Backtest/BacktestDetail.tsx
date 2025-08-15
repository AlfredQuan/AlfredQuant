import React, { useEffect, useState } from 'react';
import {
  Card,
  Row,
  Col,
  Button,
  Space,
  Typography,
  Descriptions,
  Tag,
  Table,
  Tabs,
  Statistic,
  Progress,
} from 'antd';
import {
  ArrowLeftOutlined,
  DownloadOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
} from 'recharts';
import { backtestAPI } from '../../services/api';

const { Title } = Typography;
const { TabPane } = Tabs;

const BacktestDetail: React.FC = () => {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const [backtest, setBacktest] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [performanceData, setPerformanceData] = useState<any[]>([]);
  const [drawdownData, setDrawdownData] = useState<any[]>([]);
  const [trades, setTrades] = useState<any[]>([]);

  useEffect(() => {
    if (id) {
      loadBacktestDetail();
    }
  }, [id]);

  const loadBacktestDetail = async () => {
    if (!id) return;

    setLoading(true);
    try {
      const backtestData = await backtestAPI.getBacktest(parseInt(id));
      setBacktest(backtestData);

      // 模拟性能数据
      const mockPerformanceData = Array.from({ length: 100 }, (_, i) => ({
        date: new Date(Date.now() - (99 - i) * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
        portfolio: 100000 + Math.random() * 20000 - 10000,
        benchmark: 100000 + Math.random() * 10000 - 5000,
      }));
      setPerformanceData(mockPerformanceData);

      // 模拟回撤数据
      const mockDrawdownData = Array.from({ length: 100 }, (_, i) => ({
        date: new Date(Date.now() - (99 - i) * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
        drawdown: -Math.random() * 0.15,
      }));
      setDrawdownData(mockDrawdownData);

      // 模拟交易记录
      const mockTrades = Array.from({ length: 20 }, (_, i) => ({
        id: i + 1,
        date: new Date(Date.now() - Math.random() * 30 * 24 * 60 * 60 * 1000).toISOString(),
        symbol: ['000001.SZ', '000002.SZ', '600000.SH', '600036.SH'][Math.floor(Math.random() * 4)],
        action: Math.random() > 0.5 ? 'BUY' : 'SELL',
        quantity: Math.floor(Math.random() * 1000) + 100,
        price: 10 + Math.random() * 50,
        amount: 0,
        pnl: (Math.random() - 0.5) * 10000,
      }));
      mockTrades.forEach(trade => {
        trade.amount = trade.quantity * trade.price;
      });
      setTrades(mockTrades);
    } catch (error) {
      console.error('Failed to load backtest detail:', error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusTag = (status: string) => {
    const statusMap: Record<string, { color: string; text: string }> = {
      completed: { color: 'success', text: '已完成' },
      running: { color: 'processing', text: '运行中' },
      failed: { color: 'error', text: '失败' },
      pending: { color: 'warning', text: '等待中' },
    };
    const config = statusMap[status] || { color: 'default', text: status };
    return <Tag color={config.color}>{config.text}</Tag>;
  };

  const tradeColumns = [
    {
      title: '时间',
      dataIndex: 'date',
      key: 'date',
      render: (date: string) => new Date(date).toLocaleString(),
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
      title: '盈亏',
      dataIndex: 'pnl',
      key: 'pnl',
      render: (value: number) => (
        <span style={{ color: value > 0 ? '#52c41a' : '#ff4d4f' }}>
          ¥{value.toFixed(2)}
        </span>
      ),
    },
  ];

  if (loading || !backtest) {
    return <div>加载中...</div>;
  }

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Space>
            <Button
              icon={<ArrowLeftOutlined />}
              onClick={() => navigate('/backtests')}
            >
              返回
            </Button>
            <Title level={2} style={{ margin: 0 }}>
              {backtest.name || '回测详情'}
            </Title>
            {getStatusTag(backtest.status)}
          </Space>
        </Col>
        <Col>
          <Space>
            <Button
              icon={<ReloadOutlined />}
              onClick={loadBacktestDetail}
            >
              刷新
            </Button>
            {backtest.status === 'completed' && (
              <Button
                type="primary"
                icon={<DownloadOutlined />}
                onClick={() => {
                  // TODO: 实现下载报告
                  console.log('Download report');
                }}
              >
                下载报告
              </Button>
            )}
          </Space>
        </Col>
      </Row>

      <Tabs defaultActiveKey="overview">
        <TabPane tab="概览" key="overview">
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col span={12}>
              <Card title="基本信息">
                <Descriptions column={1}>
                  <Descriptions.Item label="回测名称">
                    {backtest.name || '未命名回测'}
                  </Descriptions.Item>
                  <Descriptions.Item label="策略ID">
                    {backtest.strategy_id}
                  </Descriptions.Item>
                  <Descriptions.Item label="时间范围">
                    {new Date(backtest.start_date).toLocaleDateString()} - {new Date(backtest.end_date).toLocaleDateString()}
                  </Descriptions.Item>
                  <Descriptions.Item label="初始资金">
                    ¥{backtest.initial_capital.toLocaleString()}
                  </Descriptions.Item>
                  <Descriptions.Item label="最终价值">
                    ¥{(backtest.final_value || backtest.initial_capital).toLocaleString()}
                  </Descriptions.Item>
                  <Descriptions.Item label="基准指数">
                    {backtest.benchmark || '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label="手续费率">
                    {(backtest.commission_rate * 100).toFixed(4)}%
                  </Descriptions.Item>
                  <Descriptions.Item label="滑点率">
                    {(backtest.slippage_rate * 100).toFixed(4)}%
                  </Descriptions.Item>
                </Descriptions>
              </Card>
            </Col>
            <Col span={12}>
              <Card title="运行状态">
                {backtest.status === 'running' && (
                  <Progress
                    percent={Math.floor(Math.random() * 100)}
                    status="active"
                    style={{ marginBottom: 16 }}
                  />
                )}
                <Descriptions column={1}>
                  <Descriptions.Item label="状态">
                    {getStatusTag(backtest.status)}
                  </Descriptions.Item>
                  <Descriptions.Item label="开始时间">
                    {backtest.started_at ? new Date(backtest.started_at).toLocaleString() : '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label="完成时间">
                    {backtest.completed_at ? new Date(backtest.completed_at).toLocaleString() : '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label="创建时间">
                    {new Date(backtest.created_at).toLocaleString()}
                  </Descriptions.Item>
                </Descriptions>
              </Card>
            </Col>
          </Row>

          {/* 关键指标 */}
          <Row gutter={16}>
            <Col span={6}>
              <Card>
                <Statistic
                  title="总收益率"
                  value={backtest.total_return ? (backtest.total_return * 100) : 0}
                  precision={2}
                  suffix="%"
                  valueStyle={{ color: (backtest.total_return || 0) > 0 ? '#3f8600' : '#cf1322' }}
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic
                  title="年化收益率"
                  value={backtest.annual_return ? (backtest.annual_return * 100) : 0}
                  precision={2}
                  suffix="%"
                  valueStyle={{ color: (backtest.annual_return || 0) > 0 ? '#3f8600' : '#cf1322' }}
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic
                  title="夏普比率"
                  value={backtest.sharpe_ratio || 0}
                  precision={2}
                  valueStyle={{ color: '#1890ff' }}
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic
                  title="最大回撤"
                  value={backtest.max_drawdown ? (backtest.max_drawdown * 100) : 0}
                  precision={2}
                  suffix="%"
                  valueStyle={{ color: '#cf1322' }}
                />
              </Card>
            </Col>
          </Row>
        </TabPane>

        <TabPane tab="收益曲线" key="performance">
          <Card title="投资组合表现" style={{ marginBottom: 16 }}>
            <ResponsiveContainer width="100%" height={400}>
              <LineChart data={performanceData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="portfolio"
                  stroke="#1890ff"
                  strokeWidth={2}
                  name="投资组合"
                />
                <Line
                  type="monotone"
                  dataKey="benchmark"
                  stroke="#52c41a"
                  strokeWidth={2}
                  name="基准指数"
                />
              </LineChart>
            </ResponsiveContainer>
          </Card>

          <Card title="回撤分析">
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={drawdownData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="drawdown" fill="#ff4d4f" />
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </TabPane>

        <TabPane tab="交易记录" key="trades">
          <Card title="交易明细">
            <Table
              columns={tradeColumns}
              dataSource={trades}
              rowKey="id"
              pagination={{
                pageSize: 20,
                showSizeChanger: true,
                showQuickJumper: true,
              }}
            />
          </Card>
        </TabPane>

        <TabPane tab="风险分析" key="risk">
          <Row gutter={16}>
            <Col span={12}>
              <Card title="风险指标">
                <Descriptions column={1}>
                  <Descriptions.Item label="波动率">
                    {backtest.volatility ? `${(backtest.volatility * 100).toFixed(2)}%` : '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label="Beta">
                    {backtest.beta ? backtest.beta.toFixed(2) : '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label="Alpha">
                    {backtest.alpha ? backtest.alpha.toFixed(2) : '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label="信息比率">
                    {/* TODO: 计算信息比率 */}
                    -
                  </Descriptions.Item>
                  <Descriptions.Item label="卡尔马比率">
                    {/* TODO: 计算卡尔马比率 */}
                    -
                  </Descriptions.Item>
                </Descriptions>
              </Card>
            </Col>
            <Col span={12}>
              <Card title="交易统计">
                <Descriptions column={1}>
                  <Descriptions.Item label="总交易次数">
                    {backtest.total_trades || 0}
                  </Descriptions.Item>
                  <Descriptions.Item label="盈利交易次数">
                    {backtest.profitable_trades || 0}
                  </Descriptions.Item>
                  <Descriptions.Item label="胜率">
                    {backtest.win_rate ? `${(backtest.win_rate * 100).toFixed(2)}%` : '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label="平均持仓天数">
                    {/* TODO: 计算平均持仓天数 */}
                    -
                  </Descriptions.Item>
                  <Descriptions.Item label="换手率">
                    {/* TODO: 计算换手率 */}
                    -
                  </Descriptions.Item>
                </Descriptions>
              </Card>
            </Col>
          </Row>
        </TabPane>
      </Tabs>
    </div>
  );
};

export default BacktestDetail;