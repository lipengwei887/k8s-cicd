
import React from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from 'antd'
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
import './App.css'

const { Content } = Layout

// 认证守卫：校验 token 是否存在且未过期
const RequireAuth: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const isAuthenticated = () => {
    // 优先检查 localStorage（记住我模式）
    const token = localStorage.getItem('token')
    const expiry = localStorage.getItem('tokenExpiry')
    if (token && expiry) {
      if (Date.now() < parseInt(expiry)) return true
      // 已过期，清除
      localStorage.removeItem('token')
      localStorage.removeItem('tokenExpiry')
      return false
    }
    // 其次检查 sessionStorage（会话模式）
    return !!sessionStorage.getItem('token')
  }

  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />
  }
  return <>{children}</>
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
            <Route path="/admin" element={<RequireAuth><AdminLayout /></RequireAuth>}>
              <Route path="clusters" element={<ClusterManager />} />
              <Route path="users" element={<UserManager />} />
              <Route path="permissions" element={<PermissionManager />} />
              <Route path="roles" element={<RoleManager />} />
              <Route path="user-roles" element={<UserRoleManager />} />
              <Route path="role-groups" element={<RoleGroupManager />} />
              <Route path="" element={<Navigate to="/admin/clusters" replace />} />
            </Route>
            
            <Route path="/" element={<Navigate to="/login" replace />} />
          </Routes>
        </Content>
      </Layout>
    </Router>
  )
}

export default App
