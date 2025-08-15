import React from 'react';
import {
  Card,
  Row,
  Col,
  Typography,
  Form,
  Input,
  Button,
  Switch,
  Select,
  InputNumber,
  Divider,
  message,
  Tabs,
} from 'antd';
import { SaveOutlined } from '@ant-design/icons';

const { Title } = Typography;
const { TextArea } = Input;
const { Option } = Select;
const { TabPane } = Tabs;

const Settings: React.FC = () => {
  const [form] = Form.useForm();

  const handleSave = (values: any) => {
    console.log('Settings saved:', values);
    message.success('设置保存成功');
  };

  return (
    <div>
      <Title level={2}>系统设置</Title>

      <Tabs defaultActiveKey="general">
        <TabPane tab="通用设置" key="general">
          <Card>
            <Form
              form={form}
              layout="vertical"
              onFinish={handleSave}
              initialValues={{
                theme: 'light',
                language: 'zh-CN',
                timezone: 'Asia/Shanghai',
                autoSave: true,
                notifications: true,
              }}
            >
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    name="theme"
                    label="主题"
                  >
                    <Select>
                      <Option value="light">浅色主题</Option>
                      <Option value="dark">深色主题</Option>
                      <Option value="auto">跟随系统</Option>
                    </Select>
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    name="language"
                    label="语言"
                  >
                    <Select>
                      <Option value="zh-CN">简体中文</Option>
                      <Option value="en-US">English</Option>
                    </Select>
                  </Form.Item>
                </Col>
              </Row>

              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    name="timezone"
                    label="时区"
                  >
                    <Select>
                      <Option value="Asia/Shanghai">Asia/Shanghai</Option>
                      <Option value="UTC">UTC</Option>
                      <Option value="America/New_York">America/New_York</Option>
                    </Select>
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    name="autoSave"
                    label="自动保存"
                    valuePropName="checked"
                  >
                    <Switch />
                  </Form.Item>
                </Col>
              </Row>

              <Form.Item
                name="notifications"
                label="启用通知"
                valuePropName="checked"
              >
                <Switch />
              </Form.Item>

              <Form.Item>
                <Button type="primary" htmlType="submit" icon={<SaveOutlined />}>
                  保存设置
                </Button>
              </Form.Item>
            </Form>
          </Card>
        </TabPane>

        <TabPane tab="交易设置" key="trading">
          <Card>
            <Form
              layout="vertical"
              onFinish={handleSave}
              initialValues={{
                defaultCommission: 0.0003,
                defaultSlippage: 0.001,
                maxPositionSize: 0.1,
                riskFreeRate: 0.03,
                benchmark: '000300.SH',
              }}
            >
              <Divider>默认参数</Divider>
              
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    name="defaultCommission"
                    label="默认手续费率"
                  >
                    <InputNumber
                      style={{ width: '100%' }}
                      min={0}
                      max={1}
                      step={0.0001}
                      formatter={value => `${(Number(value) * 100).toFixed(4)}%`}
                      parser={value => Number(value!.replace('%', '')) / 100}
                    />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    name="defaultSlippage"
                    label="默认滑点率"
                  >
                    <InputNumber
                      style={{ width: '100%' }}
                      min={0}
                      max={1}
                      step={0.0001}
                      formatter={value => `${(Number(value) * 100).toFixed(4)}%`}
                      parser={value => Number(value!.replace('%', '')) / 100}
                    />
                  </Form.Item>
                </Col>
              </Row>

              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    name="maxPositionSize"
                    label="最大持仓比例"
                  >
                    <InputNumber
                      style={{ width: '100%' }}
                      min={0}
                      max={1}
                      step={0.01}
                      formatter={value => `${(Number(value) * 100).toFixed(2)}%`}
                      parser={value => Number(value!.replace('%', '')) / 100}
                    />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    name="riskFreeRate"
                    label="无风险利率"
                  >
                    <InputNumber
                      style={{ width: '100%' }}
                      min={0}
                      max={1}
                      step={0.001}
                      formatter={value => `${(Number(value) * 100).toFixed(2)}%`}
                      parser={value => Number(value!.replace('%', '')) / 100}
                    />
                  </Form.Item>
                </Col>
              </Row>

              <Form.Item
                name="benchmark"
                label="默认基准指数"
              >
                <Select>
                  <Option value="000300.SH">沪深300</Option>
                  <Option value="000905.SH">中证500</Option>
                  <Option value="000852.SH">中证1000</Option>
                  <Option value="399006.SZ">创业板指</Option>
                </Select>
              </Form.Item>

              <Divider>风险控制</Divider>

              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    name="maxDrawdown"
                    label="最大回撤限制"
                  >
                    <InputNumber
                      style={{ width: '100%' }}
                      min={0}
                      max={1}
                      step={0.01}
                      formatter={value => `${(Number(value) * 100).toFixed(2)}%`}
                      parser={value => Number(value!.replace('%', '')) / 100}
                    />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    name="stopLoss"
                    label="止损比例"
                  >
                    <InputNumber
                      style={{ width: '100%' }}
                      min={0}
                      max={1}
                      step={0.01}
                      formatter={value => `${(Number(value) * 100).toFixed(2)}%`}
                      parser={value => Number(value!.replace('%', '')) / 100}
                    />
                  </Form.Item>
                </Col>
              </Row>

              <Form.Item>
                <Button type="primary" htmlType="submit" icon={<SaveOutlined />}>
                  保存设置
                </Button>
              </Form.Item>
            </Form>
          </Card>
        </TabPane>

        <TabPane tab="数据源设置" key="datasource">
          <Card>
            <Form
              layout="vertical"
              onFinish={handleSave}
              initialValues={{
                primarySource: 'tushare',
                backupSource: 'akshare',
                updateFrequency: 'daily',
                cacheEnabled: true,
              }}
            >
              <Form.Item
                name="primarySource"
                label="主要数据源"
              >
                <Select>
                  <Option value="tushare">Tushare</Option>
                  <Option value="akshare">AKShare</Option>
                  <Option value="wind">Wind</Option>
                  <Option value="choice">东方财富Choice</Option>
                </Select>
              </Form.Item>

              <Form.Item
                name="backupSource"
                label="备用数据源"
              >
                <Select>
                  <Option value="tushare">Tushare</Option>
                  <Option value="akshare">AKShare</Option>
                  <Option value="wind">Wind</Option>
                  <Option value="choice">东方财富Choice</Option>
                </Select>
              </Form.Item>

              <Form.Item
                name="updateFrequency"
                label="数据更新频率"
              >
                <Select>
                  <Option value="realtime">实时</Option>
                  <Option value="minute">每分钟</Option>
                  <Option value="hourly">每小时</Option>
                  <Option value="daily">每日</Option>
                </Select>
              </Form.Item>

              <Form.Item
                name="cacheEnabled"
                label="启用数据缓存"
                valuePropName="checked"
              >
                <Switch />
              </Form.Item>

              <Divider>API配置</Divider>

              <Form.Item
                name="tushareToken"
                label="Tushare Token"
              >
                <Input.Password placeholder="请输入Tushare API Token" />
              </Form.Item>

              <Form.Item
                name="windAccount"
                label="Wind账户"
              >
                <Input placeholder="请输入Wind账户" />
              </Form.Item>

              <Form.Item>
                <Button type="primary" htmlType="submit" icon={<SaveOutlined />}>
                  保存设置
                </Button>
              </Form.Item>
            </Form>
          </Card>
        </TabPane>

        <TabPane tab="通知设置" key="notifications">
          <Card>
            <Form
              layout="vertical"
              onFinish={handleSave}
              initialValues={{
                emailEnabled: true,
                smsEnabled: false,
                webhookEnabled: false,
                tradingAlerts: true,
                systemAlerts: true,
                performanceAlerts: true,
              }}
            >
              <Divider>通知方式</Divider>

              <Form.Item
                name="emailEnabled"
                label="邮件通知"
                valuePropName="checked"
              >
                <Switch />
              </Form.Item>

              <Form.Item
                name="emailAddress"
                label="邮箱地址"
              >
                <Input placeholder="请输入邮箱地址" />
              </Form.Item>

              <Form.Item
                name="smsEnabled"
                label="短信通知"
                valuePropName="checked"
              >
                <Switch />
              </Form.Item>

              <Form.Item
                name="phoneNumber"
                label="手机号码"
              >
                <Input placeholder="请输入手机号码" />
              </Form.Item>

              <Form.Item
                name="webhookEnabled"
                label="Webhook通知"
                valuePropName="checked"
              >
                <Switch />
              </Form.Item>

              <Form.Item
                name="webhookUrl"
                label="Webhook URL"
              >
                <Input placeholder="请输入Webhook URL" />
              </Form.Item>

              <Divider>通知类型</Divider>

              <Form.Item
                name="tradingAlerts"
                label="交易提醒"
                valuePropName="checked"
              >
                <Switch />
              </Form.Item>

              <Form.Item
                name="systemAlerts"
                label="系统提醒"
                valuePropName="checked"
              >
                <Switch />
              </Form.Item>

              <Form.Item
                name="performanceAlerts"
                label="业绩提醒"
                valuePropName="checked"
              >
                <Switch />
              </Form.Item>

              <Form.Item>
                <Button type="primary" htmlType="submit" icon={<SaveOutlined />}>
                  保存设置
                </Button>
              </Form.Item>
            </Form>
          </Card>
        </TabPane>
      </Tabs>
    </div>
  );
};

export default Settings;