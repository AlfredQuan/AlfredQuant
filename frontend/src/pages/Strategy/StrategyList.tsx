import React, { useState, useEffect } from 'react';
import {
  Table,
  Button,
  Space,
  Input,
  Select,
  Card,
  Tag,
  Popconfirm,
  message,
  Typography,
  Row,
  Col,
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  PlayCircleOutlined,
  PauseCircleOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import { AppDispatch, RootState } from '../../store';
import {
  fetchStrategies,
  deleteStrategy,
  setPagination,
} from '../../store/slices/strategySlice';
import { Strategy } from '../../types';

const { Title } = Typography;
const { Search } = Input;
const { Option } = Select;

const StrategyList: React.FC = () => {
  const navigate = useNavigate();
  const dispatch = useDispatch<AppDispatch>();
  const { strategies, loading, pagination } = useSelector((state: RootState) => state.strategy);
  
  const [searchText, setSearchText] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('');

  useEffect(() => {
    dispatch(fetchStrategies({
      page: pagination.current,
      size: pagination.pageSize,
      search: searchText,
    }));
  }, [dispatch, pagination.current, pagination.pageSize]);

  const handleSearch = (value: string) => {
    setSearchText(value);
    dispatch(setPagination({ current: 1 }));
    dispatch(fetchStrategies({
      page: 1,
      size: pagination.pageSize,
      search: value,
    }));
  };

  const handleStatusFilter = (status: string) => {
    setStatusFilter(status);
    dispatch(setPagination({ current: 1 }));
    dispatch(fetchStrategies({
      page: 1,
      size: pagination.pageSize,
      search: searchText,
      status: status || undefined,
    }));
  };

  const handleDelete = async (id: number) => {
    try {
      await dispatch(deleteStrategy(id)).unwrap();
      message.success('策略删除成功');
      dispatch(fetchStrategies({
        page: pagination.current,
        size: pagination.pageSize,
        search: searchText,
      }));
    } catch (error: any) {
      message.error(error || '删除失败');
    }
  };

  const handleTableChange = (paginationConfig: any) => {
    dispatch(setPagination({
      current: paginationConfig.current,
      pageSize: paginationConfig.pageSize,
    }));
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

  const columns = [
    {
      title: '策略名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: Strategy) => (
        <Button
          type="link"
          onClick={() => navigate(`/strategies/${record.id}`)}
          style={{ padding: 0 }}
        >
          {text}
        </Button>
      ),
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      render: (text: string) => text || '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => getStatusTag(status),
    },
    {
      title: '版本',
      dataIndex: 'version',
      key: 'version',
    },
    {
      title: '频率',
      dataIndex: 'frequency',
      key: 'frequency',
      render: (frequency: string) => {
        const frequencyMap: Record<string, string> = {
          '1d': '日频',
          '1h': '小时',
          '1m': '分钟',
          '1w': '周频',
        };
        return frequencyMap[frequency] || frequency;
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
      render: (_, record: Strategy) => (
        <Space size="middle">
          <Button
            type="text"
            icon={<EditOutlined />}
            onClick={() => navigate(`/strategies/${record.id}/edit`)}
          >
            编辑
          </Button>
          {record.status === 'active' ? (
            <Button
              type="text"
              icon={<PauseCircleOutlined />}
              onClick={() => {
                // TODO: 实现暂停策略
                message.info('暂停策略功能开发中');
              }}
            >
              暂停
            </Button>
          ) : (
            <Button
              type="text"
              icon={<PlayCircleOutlined />}
              onClick={() => {
                // TODO: 实现启动策略
                message.info('启动策略功能开发中');
              }}
            >
              启动
            </Button>
          )}
          <Popconfirm
            title="确定要删除这个策略吗？"
            onConfirm={() => handleDelete(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button
              type="text"
              danger
              icon={<DeleteOutlined />}
            >
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Title level={2}>策略管理</Title>
        </Col>
        <Col>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => navigate('/strategies/new')}
          >
            新建策略
          </Button>
        </Col>
      </Row>

      <Card>
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={8}>
            <Search
              placeholder="搜索策略名称或描述"
              allowClear
              onSearch={handleSearch}
              style={{ width: '100%' }}
            />
          </Col>
          <Col span={4}>
            <Select
              placeholder="状态筛选"
              allowClear
              style={{ width: '100%' }}
              onChange={handleStatusFilter}
            >
              <Option value="draft">草稿</Option>
              <Option value="active">运行中</Option>
              <Option value="paused">已暂停</Option>
              <Option value="stopped">已停止</Option>
              <Option value="error">错误</Option>
            </Select>
          </Col>
        </Row>

        <Table
          columns={columns}
          dataSource={strategies}
          loading={loading}
          rowKey="id"
          pagination={{
            current: pagination.current,
            pageSize: pagination.pageSize,
            total: pagination.total,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total, range) =>
              `第 ${range[0]}-${range[1]} 条，共 ${total} 条`,
          }}
          onChange={handleTableChange}
        />
      </Card>
    </div>
  );
};

export default StrategyList;