import React from 'react'
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
import { authApi } from '@/api'
import { getStoredCurrentUser, hasAnyPermission, setStoredCurrentUser, type AuthUser } from '@/utils/auth'

const { Sider, Content } = Layout

const AdminLayout: React.FC = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const [currentUser, setCurrentUser] = React.useState<AuthUser | null>(getStoredCurrentUser())

  React.useEffect(() => {
    let mounted = true

    const loadCurrentUser = async () => {
      try {
        const me: any = await authApi.getMe()
        setStoredCurrentUser(me)
        if (mounted) {
          setCurrentUser(me)
        }
      } catch {
        if (mounted) {
          setCurrentUser(getStoredCurrentUser())
        }
      }
    }

    loadCurrentUser()
    return () => {
      mounted = false
    }
  }, [])

  const menuItems = [
    {
      key: '/admin/clusters',
      icon: <ClusterOutlined />,
      label: '集群管理',
      visible: hasAnyPermission(currentUser, ['cluster:read', 'cluster:create', 'cluster:update', 'cluster:delete']),
    },
    {
      key: '/admin/users',
      icon: <TeamOutlined />,
      label: '人员管理',
      visible: hasAnyPermission(currentUser, ['user:read', 'user:manage']),
    },
    {
      key: 'rbac',
      icon: <SafetyOutlined />,
      label: '权限管理',
      visible: hasAnyPermission(currentUser, ['role:read', 'role:manage', 'user:read', 'user:manage']),
      children: [
        {
          key: '/admin/roles',
          icon: <KeyOutlined />,
          label: '角色管理',
          visible: hasAnyPermission(currentUser, ['role:read', 'role:manage']),
        },
        {
          key: '/admin/user-roles',
          icon: <UserOutlined />,
          label: '用户角色',
          visible: hasAnyPermission(currentUser, ['user:read', 'user:manage']),
        },
        {
          key: '/admin/permissions',
          icon: <SafetyOutlined />,
          label: '权限配置',
          visible: hasAnyPermission(currentUser, ['role:read', 'role:manage']),
        },
        {
          key: '/admin/role-groups',
          icon: <GroupOutlined />,
          label: '角色组管理',
          visible: hasAnyPermission(currentUser, ['role:read', 'role:manage']),
        },
      ]
    },
  ]

  const visibleMenuItems = menuItems
    .filter(item => item.visible !== false)
    .map(item => item.children ? { ...item, children: item.children.filter(child => child.visible !== false) } : item)
    .filter(item => !item.children || item.children.length > 0)

  const selectedKey = visibleMenuItems
    .flatMap(item => item.children ? item.children : [item])
    .find(item => location.pathname.startsWith(item.key))?.key || visibleMenuItems[0]?.key || ''

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
          items={visibleMenuItems}
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
