
import React from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from 'antd'
import { authApi } from './api'
import Login from './pages/Login/index'
import Dashboard from './pages/Dashboard/index'
import ReleaseForm from './components/ReleaseForm/index'
import AdminLayout from './pages/Admin/index'
import ClusterManager from './pages/Admin/ClusterManager'
import UserManager from './pages/Admin/UserManager'
import PermissionManager from './pages/Admin/PermissionManager'
import RoleManager from './pages/Admin/RoleManager'
import UserRoleManager from './pages/Admin/UserRoleManager'
import RoleGroupManager from './pages/Admin/RoleGroupManager'
import { clearAuthStorage, getStoredCurrentUser, getStoredToken, hasAnyPermission, setStoredCurrentUser } from './utils/auth'
import './App.css'

const { Content } = Layout

const hasValidSession = () => {
  const token = localStorage.getItem('token')
  const expiry = localStorage.getItem('tokenExpiry')
  if (token && expiry) {
    if (Date.now() < parseInt(expiry, 10)) return true
    clearAuthStorage()
    return false
  }
  return !!sessionStorage.getItem('token')
}

const RequireAuth: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  if (!hasValidSession()) {
    return <Navigate to="/login" replace />
  }
  return <>{children}</>
}

const RequirePermission: React.FC<{ children: React.ReactNode; anyOf: string[] }> = ({ children, anyOf }) => {
  const [allowed, setAllowed] = React.useState<boolean | null>(null)

  React.useEffect(() => {
    let mounted = true

    const checkPermission = async () => {
      if (!getStoredToken()) {
        if (mounted) setAllowed(false)
        return
      }

      const storedUser = getStoredCurrentUser()
      if (storedUser?.permissions) {
        if (mounted) setAllowed(hasAnyPermission(storedUser, anyOf))
        return
      }

      try {
        const me: any = await authApi.getMe()
        setStoredCurrentUser(me)
        if (mounted) setAllowed(hasAnyPermission(me, anyOf))
      } catch {
        if (mounted) setAllowed(false)
      }
    }

    checkPermission()
    return () => {
      mounted = false
    }
  }, [anyOf])

  if (allowed === null) {
    return null
  }

  if (!allowed) {
    return <Navigate to="/dashboard" replace />
  }

  return <>{children}</>
}

const AdminDefaultRedirect: React.FC = () => {
  const user = getStoredCurrentUser()

  if (hasAnyPermission(user, ['cluster:read', 'cluster:create', 'cluster:update', 'cluster:delete'])) {
    return <Navigate to="/admin/clusters" replace />
  }
  if (hasAnyPermission(user, ['user:read', 'user:manage'])) {
    return <Navigate to="/admin/users" replace />
  }
  if (hasAnyPermission(user, ['role:read', 'role:manage'])) {
    return <Navigate to="/admin/roles" replace />
  }

  return <Navigate to="/dashboard" replace />
}

function App() {
  return (
    <Router>
      <Layout style={{ minHeight: '100vh' }}>
        <Content style={{ padding: 0 }}>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/dashboard" element={<RequireAuth><Dashboard /></RequireAuth>} />
            <Route path="/release/new" element={<RequireAuth><ReleaseForm /></RequireAuth>} />
            
            {/* 管理员路由 */}
            <Route
              path="/admin"
              element={
                <RequireAuth>
                  <RequirePermission anyOf={['cluster:read', 'user:read', 'role:read', 'role:manage', 'user:manage']}>
                    <AdminLayout />
                  </RequirePermission>
                </RequireAuth>
              }
            >
              <Route path="clusters" element={<RequirePermission anyOf={['cluster:read', 'cluster:create', 'cluster:update', 'cluster:delete']}><ClusterManager /></RequirePermission>} />
              <Route path="users" element={<RequirePermission anyOf={['user:read', 'user:manage']}><UserManager /></RequirePermission>} />
              <Route path="permissions" element={<RequirePermission anyOf={['role:read', 'role:manage']}><PermissionManager /></RequirePermission>} />
              <Route path="roles" element={<RequirePermission anyOf={['role:read', 'role:manage']}><RoleManager /></RequirePermission>} />
              <Route path="user-roles" element={<RequirePermission anyOf={['user:read', 'user:manage']}><UserRoleManager /></RequirePermission>} />
              <Route path="role-groups" element={<RequirePermission anyOf={['role:read', 'role:manage']}><RoleGroupManager /></RequirePermission>} />
              <Route path="" element={<AdminDefaultRedirect />} />
            </Route>
            
            <Route path="/" element={<Navigate to="/login" replace />} />
          </Routes>
        </Content>
      </Layout>
    </Router>
  )
}

export default App
