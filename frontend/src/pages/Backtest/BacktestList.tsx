import React, { useEffect } from 'react';
import {
  Table,
  Button,
  Space,
  Card,
  Tag,
  Typography,
  Row,
  Col,
  Progress,
} from 'antd';
import {
  PlusOutlined,
  EyeOutlined,
  DownloadOutlined,
  BarChartOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import { AppDispatch, RootState } from '../../store';
import { fetchBacktests } from '../../store/slices/backtestSlice';

const { Title } = Typography;

const BacktestList: React.FC = () => {
  const navigate = useNavigate();
  const dispatch = useDispatch<AppDispatch>();
  const { backtests, loading } = useSelector((state: RootState) => state.backtest);

  useEffect(() => {
    dispatch(fetchBacktests());
  }, [dispatch]);

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

  const columns = [
    {
      title: '回测名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: any) => (
        <Button
          type="link"
          onClick={() => navigate(`/backtests/${record.id}`)}
          style={{ padding: 0 }}
        >
          {text || '未命名回测'}
        </Button>
      ),
    },
    {
      title: '策略',
      dataIndex: 'strategy_name',
      key: 'strategy_name',
      render: (text: string) => text || '-',
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
      title: '初始资金',
      dataIndex: 'initial_capital',
      key: 'initial_capital',
      render: (value: number) => `¥${value.toLocaleString()}`,
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
      render: (status: string) => getStatusTag(status),
    },
    {
      title: '进度',
      key: 'progress',
      render: (_, record: any) => {
        if (record.status === 'running') {
          return <Progress percent={Math.floor(Math.random() * 100)} size="small" />;
        }
        if (record.status === 'completed') {
          return <Progress percent={100} size="small" status="success" />;
        }
        if (record.status === 'failed') {
          return <Progress percent={0} size="small" status="exception" />;
        }
        return <Progress percent={0} size="small" />;
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => new Date(date).toLocaleDateString(),
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record: any) => (
        <Space size="middle">
          <Button
            type="text"
            icon={<EyeOutlined />}
            onClick={() => navigate(`/backtests/${record.id}`)}
          >
            查看
          </Button>
          {record.status === 'completed' && (
            <Button
              type="text"
              icon={<DownloadOutlined />}
              onClick={() => {
                // TODO: 实现下载报告
                console.log('Download report for backtest:', record.id);
              }}
            >
              下载
            </Button>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Title level={2}>回测管理</Title>
        </Col>
        <Col>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => navigate('/backtests/new')}
          >
            新建回测
          </Button>
        </Col>
      </Row>

      <Card>
        <Table
          columns={columns}
          dataSource={backtests}
          loading={loading}
          rowKey="id"
          pagination={{
            pageSize: 20,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total, range) =>
              `第 ${range[0]}-${range[1]} 条，共 ${total} 条`,
          }}
        />
      </Card>
    </div>
  );
};

export default BacktestList;