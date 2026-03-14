import { Layout, Menu, Button } from 'antd'
import { useNavigate, useLocation, Outlet } from 'react-router-dom'
import {
  ClusterOutlined,
  TeamOutlined,
  SafetyOutlined,
  ArrowLeftOutlined,
  UserOutlined,
  KeyOutlined,
  GroupOutlined,
} from '@ant-design/icons'

const { Sider, Content } = Layout

const AdminLayout: React.FC = () => {
  const navigate = useNavigate()
  const location = useLocation()

  const menuItems = [
    {
      key: '/admin/clusters',
      icon: <ClusterOutlined />,
      label: '集群管理',
    },
    {
      key: '/admin/users',
      icon: <TeamOutlined />,
      label: '人员管理',
    },
    {
      key: 'rbac',
      icon: <SafetyOutlined />,
      label: '权限管理',
      children: [
        {
          key: '/admin/roles',
          icon: <KeyOutlined />,
          label: '角色管理',
        },
        {
          key: '/admin/user-roles',
          icon: <UserOutlined />,
          label: '用户角色',
        },
        {
          key: '/admin/permissions',
          icon: <SafetyOutlined />,
          label: '权限配置',
        },
        {
          key: '/admin/role-groups',
          icon: <GroupOutlined />,
          label: '角色组管理',
        },
      ]
    },
  ]

  const selectedKey = menuItems.find(item => location.pathname.startsWith(item.key))?.key || '/admin/clusters'

  return (
    <Layout style={{ minHeight: 'calc(100vh - 48px)' }}>
      <Sider width={200} theme="light">
        <div style={{ padding: '16px', borderBottom: '1px solid #f0f0f0' }}>
          <Button 
            icon={<ArrowLeftOutlined />} 
            onClick={() => navigate('/dashboard')}
            block
          >
            返回首页
          </Button>
        </div>
        <Menu
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{ borderRight: 0 }}
        />
      </Sider>
      <Content style={{ padding: '24px', background: '#f0f2f5' }}>
        <Outlet />
      </Content>
    </Layout>
  )
}

export default AdminLayout
