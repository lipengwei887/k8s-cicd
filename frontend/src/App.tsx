import type React from 'react'
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

function App() {
  return (
    <Router>
      <Layout style={{ minHeight: '100vh' }}>
        <Content style={{ padding: 0 }}>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/release/new" element={<ReleaseForm />} />
            
            {/* 管理员路由 */}
            <Route path="/admin" element={<AdminLayout />}>
              <Route path="clusters" element={<ClusterManager />} />
              <Route path="users" element={<UserManager />} />
              <Route path="permissions" element={<PermissionManager />} />
              <Route path="roles" element={<RoleManager />} />
              <Route path="user-roles" element={<UserRoleManager />} />
              <Route path="role-groups" element={<RoleGroupManager />} />
              <Route path="" element={<Navigate to="/admin/clusters" replace />} />
            </Route>
            
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </Content>
      </Layout>
    </Router>
  )
}

export default App
