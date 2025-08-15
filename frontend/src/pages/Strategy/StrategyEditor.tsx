import React, { useState, useEffect } from 'react';
import {
  Form,
  Input,
  Button,
  Card,
  Row,
  Col,
  Select,
  InputNumber,
  message,
  Typography,
  Space,
  Divider,
} from 'antd';
import { SaveOutlined, PlayCircleOutlined, ArrowLeftOutlined } from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import MonacoEditor from '@monaco-editor/react';
import { AppDispatch, RootState } from '../../store';
import {
  createStrategy,
  updateStrategy,
  fetchStrategy,
  validateStrategy,
} from '../../store/slices/strategySlice';
import { StrategyCreate, StrategyUpdate } from '../../types';

const { Title } = Typography;
const { TextArea } = Input;
const { Option } = Select;

const StrategyEditor: React.FC = () => {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const dispatch = useDispatch<AppDispatch>();
  const { currentStrategy, loading } = useSelector((state: RootState) => state.strategy);
  
  const [form] = Form.useForm();
  const [code, setCode] = useState('');
  const [validating, setValidating] = useState(false);
  
  const isEditing = !!id;

  useEffect(() => {
    if (isEditing && id) {
      dispatch(fetchStrategy(parseInt(id)));
    }
  }, [dispatch, id, isEditing]);

  useEffect(() => {
    if (currentStrategy && isEditing) {
      form.setFieldsValue({
        name: currentStrategy.name,
        description: currentStrategy.description,
        universe: currentStrategy.universe,
        benchmark: currentStrategy.benchmark,
        frequency: currentStrategy.frequency,
        parameters: currentStrategy.parameters,
      });
      // TODO: 从后端获取策略代码
      setCode('# 策略代码将在这里显示\n# 请实现您的策略逻辑');
    }
  }, [currentStrategy, form, isEditing]);

  const handleSave = async (values: any) => {
    try {
      const strategyData = {
        ...values,
        code,
        universe: values.universe || [],
        parameters: values.parameters || {},
      };

      if (isEditing && id) {
        await dispatch(updateStrategy({
          id: parseInt(id),
          data: strategyData as StrategyUpdate,
        })).unwrap();
        message.success('策略更新成功');
      } else {
        const result = await dispatch(createStrategy(strategyData as StrategyCreate)).unwrap();
        message.success('策略创建成功');
        navigate(`/strategies/${result.id}`);
      }
    } catch (error: any) {
      message.error(error || '保存失败');
    }
  };

  const handleValidate = async () => {
    if (!isEditing || !id) {
      message.warning('请先保存策略后再进行验证');
      return;
    }

    setValidating(true);
    try {
      await dispatch(validateStrategy(parseInt(id))).unwrap();
      message.success('策略验证通过');
    } catch (error: any) {
      message.error(error || '策略验证失败');
    } finally {
      setValidating(false);
    }
  };

  const defaultCode = `# 量化策略模板
import pandas as pd
import numpy as np
from typing import Dict, List, Any

class Strategy:
    def __init__(self, context):
        \"\"\"
        策略初始化
        \"\"\"
        self.context = context
        
    def initialize(self):
        \"\"\"
        策略初始化函数
        在策略开始运行前调用一次
        \"\"\"
        pass
        
    def handle_data(self, data):
        \"\"\"
        数据处理函数
        每个交易周期调用一次
        
        Args:
            data: 当前周期的市场数据
        \"\"\"
        # 获取当前持仓
        positions = self.context.portfolio.positions
        
        # 获取价格数据
        prices = data.current_prices
        
        # 实现您的策略逻辑
        # 例如：简单的移动平均策略
        for symbol in self.context.universe:
            if symbol in prices:
                # 获取历史价格
                hist_prices = data.history(symbol, 'close', 20)
                
                if len(hist_prices) >= 20:
                    # 计算移动平均
                    ma_short = hist_prices[-5:].mean()
                    ma_long = hist_prices[-20:].mean()
                    
                    current_price = prices[symbol]
                    current_position = positions.get(symbol, 0)
                    
                    # 交易信号
                    if ma_short > ma_long and current_position <= 0:
                        # 买入信号
                        self.context.order_target_percent(symbol, 0.1)
                    elif ma_short < ma_long and current_position > 0:
                        # 卖出信号
                        self.context.order_target_percent(symbol, 0)
    
    def before_trading_start(self, data):
        \"\"\"
        交易开始前调用
        \"\"\"
        pass
        
    def after_trading_end(self, data):
        \"\"\"
        交易结束后调用
        \"\"\"
        pass`;

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
              {isEditing ? '编辑策略' : '新建策略'}
            </Title>
          </Space>
        </Col>
        <Col>
          <Space>
            <Button
              loading={validating}
              onClick={handleValidate}
              disabled={!isEditing}
            >
              验证策略
            </Button>
            <Button
              type="primary"
              icon={<SaveOutlined />}
              onClick={() => form.submit()}
              loading={loading}
            >
              保存策略
            </Button>
          </Space>
        </Col>
      </Row>

      <Row gutter={16}>
        {/* 策略配置 */}
        <Col span={8}>
          <Card title="策略配置" style={{ height: '100%' }}>
            <Form
              form={form}
              layout="vertical"
              onFinish={handleSave}
            >
              <Form.Item
                name="name"
                label="策略名称"
                rules={[{ required: true, message: '请输入策略名称' }]}
              >
                <Input placeholder="请输入策略名称" />
              </Form.Item>

              <Form.Item
                name="description"
                label="策略描述"
              >
                <TextArea
                  rows={3}
                  placeholder="请输入策略描述"
                />
              </Form.Item>

              <Form.Item
                name="frequency"
                label="运行频率"
                initialValue="1d"
              >
                <Select>
                  <Option value="1m">1分钟</Option>
                  <Option value="5m">5分钟</Option>
                  <Option value="15m">15分钟</Option>
                  <Option value="1h">1小时</Option>
                  <Option value="1d">1天</Option>
                  <Option value="1w">1周</Option>
                </Select>
              </Form.Item>

              <Form.Item
                name="universe"
                label="股票池"
              >
                <Select
                  mode="tags"
                  placeholder="输入股票代码，如 000001.SZ"
                  style={{ width: '100%' }}
                />
              </Form.Item>

              <Form.Item
                name="benchmark"
                label="基准指数"
              >
                <Select
                  placeholder="选择基准指数"
                  allowClear
                >
                  <Option value="000300.SH">沪深300</Option>
                  <Option value="000905.SH">中证500</Option>
                  <Option value="000852.SH">中证1000</Option>
                  <Option value="399006.SZ">创业板指</Option>
                </Select>
              </Form.Item>

              <Divider>策略参数</Divider>

              <Form.Item
                name={['parameters', 'initial_capital']}
                label="初始资金"
                initialValue={1000000}
              >
                <InputNumber
                  style={{ width: '100%' }}
                  formatter={value => `¥ ${value}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
                  parser={value => value!.replace(/¥\s?|(,*)/g, '')}
                />
              </Form.Item>

              <Form.Item
                name={['parameters', 'commission_rate']}
                label="手续费率"
                initialValue={0.0003}
              >
                <InputNumber
                  style={{ width: '100%' }}
                  min={0}
                  max={1}
                  step={0.0001}
                  formatter={value => `${(Number(value) * 100).toFixed(2)}%`}
                  parser={value => Number(value!.replace('%', '')) / 100}
                />
              </Form.Item>

              <Form.Item
                name={['parameters', 'slippage_rate']}
                label="滑点率"
                initialValue={0.001}
              >
                <InputNumber
                  style={{ width: '100%' }}
                  min={0}
                  max={1}
                  step={0.0001}
                  formatter={value => `${(Number(value) * 100).toFixed(2)}%`}
                  parser={value => Number(value!.replace('%', '')) / 100}
                />
              </Form.Item>
            </Form>
          </Card>
        </Col>

        {/* 代码编辑器 */}
        <Col span={16}>
          <Card title="策略代码" style={{ height: '100%' }}>
            <MonacoEditor
              height="600px"
              language="python"
              theme="vs-dark"
              value={code || defaultCode}
              onChange={(value) => setCode(value || '')}
              options={{
                selectOnLineNumbers: true,
                automaticLayout: true,
                fontSize: 14,
                minimap: { enabled: false },
                scrollBeyondLastLine: false,
                wordWrap: 'on',
              }}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default StrategyEditor;