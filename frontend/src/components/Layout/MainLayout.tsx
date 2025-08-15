import React, { useEffect } from 'react';
import { Layout, Menu, Avatar, Dropdown, Space, Button, theme } from 'antd';
import {
  DashboardOutlined,
  CodeOutlined,
  BarChartOutlined,
  TradingViewOutlined,
  DatabaseOutlined,
  SettingOutlined,
  UserOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
} from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';
import { useSelector, useDispatch } from 'react-redux';
import { RootState, AppDispatch } from '../../store';
import { logout, getCurrentUser } from '../../store/slices/authSlice';
import { toggleSidebar } from '../../store/slices/uiSlice';
import { MenuItem } from '../../types';

const { Header, Sider, Content } = Layout;

interface MainLayoutProps {
  children: React.ReactNode;
}

const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const dispatch = useDispatch<AppDispatch>();
  const { user } = useSelector((state: RootState) => state.auth);
  const { sidebarCollapsed } = useSelector((state: RootState) => state.ui);
  const {
    token: { colorBgContainer },
  } = theme.useToken();

  useEffect(() => {
    if (!user) {
      dispatch(getCurrentUser());
    }
  }, [dispatch, user]);

  const menuItems: MenuItem[] = [
    {
      key: '/dashboard',
      label: '仪表板',
      icon: <DashboardOutlined />,
      path: '/dashboard',
    },
    {
      key: '/strategies',
      label: '策略管理',
      icon: <CodeOutlined />,
      path: '/strategies',
    },
    {
      key: '/backtests',
      label: '回测管理',
      icon: <BarChartOutlined />,
      path: '/backtests',
    },
    {
      key: '/trading',
      label: '实时交易',
      icon: <TradingViewOutlined />,
      path: '/trading',
    },
    {
      key: '/data',
      label: '数据中心',
      icon: <DatabaseOutlined />,
      path: '/data',
    },
    {
      key: '/settings',
      label: '系统设置',
      icon: <SettingOutlined />,
      path: '/settings',
    },
  ];

  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(key);
  };

  const handleLogout = () => {
    dispatch(logout());
  };

  const userMenuItems = [
    {
      key: 'profile',
      label: '个人资料',
      icon: <UserOutlined />,
    },
    {
      key: 'logout',
      label: '退出登录',
      icon: <LogoutOutlined />,
      onClick: handleLogout,
    },
  ];

  const selectedKeys = [location.pathname];

  return (
    <Layout className="main-layout">
      <Sider
        trigger={null}
        collapsible
        collapsed={sidebarCollapsed}
        style={{
          overflow: 'auto',
          height: '100vh',
          position: 'fixed',
          left: 0,
          top: 0,
          bottom: 0,
        }}
      >
        <div className="logo">
          {sidebarCollapsed ? '量化' : '量化投资研究框架'}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={selectedKeys}
          items={menuItems.map(item => ({
            key: item.key,
            icon: item.icon,
            label: item.label,
          }))}
          onClick={handleMenuClick}
        />
      </Sider>
      <Layout
        style={{
          marginLeft: sidebarCollapsed ? 80 : 200,
          transition: 'margin-left 0.2s',
        }}
      >
        <Header
          style={{
            padding: '0 24px',
            background: colorBgContainer,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <Button
            type="text"
            icon={sidebarCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => dispatch(toggleSidebar())}
            style={{
              fontSize: '16px',
              width: 64,
              height: 64,
            }}
          />
          <Space>
            <Dropdown
              menu={{
                items: userMenuItems,
                onClick: ({ key }) => {
                  const item = userMenuItems.find(item => item.key === key);
                  if (item?.onClick) {
                    item.onClick();
                  }
                },
              }}
              placement="bottomRight"
            >
              <Space className="user-info">
                <Avatar icon={<UserOutlined />} />
                <span>{user?.full_name || user?.username || '用户'}</span>
              </Space>
            </Dropdown>
          </Space>
        </Header>
        <Content
          style={{
            margin: '24px 16px',
            padding: 24,
            minHeight: 280,
            background: colorBgContainer,
          }}
        >
          {children}
        </Content>
      </Layout>
    </Layout>
  );
};

export default MainLayout;