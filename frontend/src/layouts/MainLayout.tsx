import React, { useState } from 'react';
import { Layout, Menu } from 'antd';
import {
  DesktopOutlined,
  LineChartOutlined,
  ExperimentOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import { useNavigate, useLocation, Outlet } from 'react-router-dom';

const { Header, Sider, Content } = Layout;

// 菜单项配置
const menuItems = [
  {
    key: '/sites',
    icon: <DesktopOutlined />,
    label: '站点管理',
  },
  {
    key: '/statistics',
    icon: <LineChartOutlined />,
    label: '统计数据',
  },
  {
    key: '/test',
    icon: <ExperimentOutlined />,
    label: '功能测试',
  },
  {
    key: '/settings',
    icon: <SettingOutlined />,
    label: '系统设置',
  },
];

const MainLayout: React.FC = () => {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  const handleMenuClick = (key: string) => {
    navigate(key);
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider 
        collapsible 
        collapsed={collapsed} 
        onCollapse={setCollapsed}
        theme="light"
      >
        <div style={{ 
          height: 32, 
          margin: 16, 
          background: '#001529', 
          borderRadius: 4,
        }} />
        <Menu
          theme="light"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => handleMenuClick(key)}
        />
      </Sider>
      <Layout>
        <Header style={{ 
          padding: 0, 
          background: '#fff',
          display: 'flex',
          alignItems: 'center',
          paddingLeft: 24,
          boxShadow: '0 1px 4px rgba(0,21,41,.08)',
        }}>
          <h1 style={{ margin: 0, fontSize: '18px' }}>PT Linker</h1>
        </Header>
        <Content style={{ 
          margin: '24px 16px', 
          padding: 24, 
          background: '#fff',
          borderRadius: 4,
          minHeight: 280,
        }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
};

export default MainLayout; 
