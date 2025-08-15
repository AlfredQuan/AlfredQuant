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
  message,
  Modal,
} from 'antd';
import {
  ArrowLeftOutlined,
  EditOutlined,
  PlayCircleOutlined,
  PauseCircleOutlined,
  BarChartOutlined,
  DeleteOutlined,
} from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { AppDispatch, RootState } from '../../store';
import { fetchStrategy, deleteStrategy } from '../../store/slices/strategySlice';
import { backtestAPI } from '../../services/api';

const { Title, Text } = Typography;
const { TabPane } = Tabs;

const StrategyDetail: React.FC = () => {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const dispatch = useDispatch<AppDispatch>();
  const { currentStrategy, loading } = useSelector((state: RootState) => state.strategy);
  
  const [backtests, setBacktests] = useState<any[]>([]);
  const [backtestsLoading, setBacktestsLoading] = useState(false);
  const [performanceData, setPerformanceData] = useState<any[]>([]);

  useEffect(() => {
    if (id) {
      dispatch(fetchStrategy(parseInt(id)));
      loadBacktests();
    }
  }, [dispatch, id]);

  const loadBacktests = async () => {
    if (!id) return;
    
    setBacktestsLoading(true);
    try {
      const response = await backtestAPI.getBacktests({
        strategy_id: parseInt(id),
        page: 1,
        size: 10,
      });
      setBacktests(response.data || []);
      
      // 模拟性能数据
      const mockData = Array.from({ length: 30 }, (_, i) => ({
        date: new Date(Date.now() - (29 - i) * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
        value: 100000 + Math.random() * 20000 - 10000,
        benchmark: 100000 + Math.random() * 10000 - 5000,
      }));
      setPerformanceData(mockData);
    } catch (error) {
      console.error('Failed to load backtests:', error);
    } finally {
      setBacktestsLoading(false);
    }
  };

  const handleDelete = () => {
    if (!id) return;
    
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除这个策略吗？此操作不可恢复。',
      okText: '确定',
      cancelText: '取消',
      onOk: async () => {
        try {
          await dispatch(deleteStrategy(parseInt(id))).unwrap();
          message.success('策略删除成功');
          navigate('/strategies');
        } catch (error: any) {
          message.error(error || '删除失败');
        }
      },
    });
  };

  const handleCreateBacktest = () => {
    navigate('/backtests/new', {
      state: { strategyId: id },
    });
  };

  const getStatusTag = (status: string) => {
    const statusMap: Record<string, { color: string; text: string }> = {
      draft: { color: 'default', text: '草稿' },
      active: { color: 'success', text: '运行中' },
      paused: { color: 'warning', text: '已暂停' },
      stopped: { color: 'error', text: '已停止' },
      error: { color: 'error', text: '错误' },
    };
    const config = statusMap[status] || { color: 'default', text: status };
    return <Tag color={config.color}>{config.text}</Tag>;
  };

  const backtestColumns = [
    {
      title: '回测名称',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record: any) => (
        <Button
          type="link"
          onClick={() => navigate(`/backtests/${record.id}`)}
          style={{ padding: 0 }}
        >
          {name || '未命名回测'}
        </Button>
      ),
    },
    {
      title: '时间范围',
      key: 'dateRange',
      render: (_, record: any) => (
        <span>
          {new Date(record.start_date).toLocaleDateString()} - {new Date(record.end_date).toLocaleDateString()}
        </span>
      ),
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
      title: '最大回撤',
      dataIndex: 'max_drawdown',
      key: 'max_drawdown',
      render: (value: number) => (
        <span style={{ color: '#ff4d4f' }}>
          {value ? `${(value * 100).toFixed(2)}%` : '-'}
        </span>
      ),
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
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => new Date(date).toLocaleDateString(),
    },
  ];

  if (loading || !currentStrategy) {
    return <div>加载中...</div>;
  }

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Space>
            <Button
              icon={<ArrowLeftOutlined />}
              onClick={() => navigate('/strategies')}
            >
              返回
            </Button>
            <Title level={2} style={{ margin: 0 }}>
              {currentStrategy.name}
            </Title>
            {getStatusTag(currentStrategy.status)}
          </Space>
        </Col>
        <Col>
          <Space>
            <Button
              icon={<BarChartOutlined />}
              onClick={handleCreateBacktest}
            >
              创建回测
            </Button>
            <Button
              icon={<EditOutlined />}
              onClick={() => navigate(`/strategies/${id}/edit`)}
            >
              编辑
            </Button>
            {currentStrategy.status === 'active' ? (
              <Button
                icon={<PauseCircleOutlined />}
                onClick={() => message.info('暂停策略功能开发中')}
              >
                暂停
              </Button>
            ) : (
              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                onClick={() => message.info('启动策略功能开发中')}
              >
                启动
              </Button>
            )}
            <Button
              danger
              icon={<DeleteOutlined />}
              onClick={handleDelete}
            >
              删除
            </Button>
          </Space>
        </Col>
      </Row>

      <Tabs defaultActiveKey="overview">
        <TabPane tab="概览" key="overview">
          <Row gutter={16}>
            <Col span={12}>
              <Card title="基本信息" style={{ marginBottom: 16 }}>
                <Descriptions column={1}>
                  <Descriptions.Item label="策略名称">
                    {currentStrategy.name}
                  </Descriptions.Item>
                  <Descriptions.Item label="描述">
                    {currentStrategy.description || '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label="版本">
                    {currentStrategy.version}
                  </Descriptions.Item>
                  <Descriptions.Item label="运行频率">
                    {currentStrategy.frequency}
                  </Descriptions.Item>
                  <Descriptions.Item label="基准指数">
                    {currentStrategy.benchmark || '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label="创建时间">
                    {new Date(currentStrategy.created_at).toLocaleString()}
                  </Descriptions.Item>
                  <Descriptions.Item label="更新时间">
                    {new Date(currentStrategy.updated_at).toLocaleString()}
                  </Descriptions.Item>
                </Descriptions>
              </Card>
            </Col>
            <Col span={12}>
              <Card title="股票池" style={{ marginBottom: 16 }}>
                <div>
                  {currentStrategy.universe && currentStrategy.universe.length > 0 ? (
                    currentStrategy.universe.map((symbol, index) => (
                      <Tag key={index} style={{ marginBottom: 8 }}>
                        {symbol}
                      </Tag>
                    ))
                  ) : (
                    <Text type="secondary">未设置股票池</Text>
                  )}
                </div>
              </Card>
            </Col>
          </Row>
        </TabPane>

        <TabPane tab="性能分析" key="performance">
          <Card title="策略表现" style={{ marginBottom: 16 }}>
            <ResponsiveContainer width="100%" height={400}>
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
                  name="策略收益"
                />
                <Line
                  type="monotone"
                  dataKey="benchmark"
                  stroke="#52c41a"
                  strokeWidth={2}
                  name="基准收益"
                />
              </LineChart>
            </ResponsiveContainer>
          </Card>

          <Row gutter={16}>
            <Col span={6}>
              <Card>
                <div className="metric-card">
                  <div className="metric-value">12.34%</div>
                  <div className="metric-label">总收益率</div>
                </div>
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <div className="metric-card">
                  <div className="metric-value">1.45</div>
                  <div className="metric-label">夏普比率</div>
                </div>
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <div className="metric-card">
                  <div className="metric-value" style={{ color: '#ff4d4f' }}>-8.76%</div>
                  <div className="metric-label">最大回撤</div>
                </div>
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <div className="metric-card">
                  <div className="metric-value">18.92%</div>
                  <div className="metric-label">年化波动率</div>
                </div>
              </Card>
            </Col>
          </Row>
        </TabPane>

        <TabPane tab="回测历史" key="backtests">
          <Card
            title="回测记录"
            extra={
              <Button
                type="primary"
                icon={<BarChartOutlined />}
                onClick={handleCreateBacktest}
              >
                新建回测
              </Button>
            }
          >
            <Table
              columns={backtestColumns}
              dataSource={backtests}
              loading={backtestsLoading}
              rowKey="id"
              pagination={{
                pageSize: 10,
                showSizeChanger: true,
                showQuickJumper: true,
              }}
            />
          </Card>
        </TabPane>

        <TabPane tab="参数配置" key="parameters">
          <Card title="策略参数">
            <Descriptions column={2}>
              {currentStrategy.parameters && Object.entries(currentStrategy.parameters).map(([key, value]) => (
                <Descriptions.Item key={key} label={key}>
                  {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                </Descriptions.Item>
              ))}
            </Descriptions>
          </Card>
        </TabPane>
      </Tabs>
    </div>
  );
};

export default StrategyDetail;