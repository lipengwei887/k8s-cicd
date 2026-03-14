import { useState, useEffect } from 'react'
import {
  Card,
  Table,
  Button,
  Space,
  Modal,
  message,
  Tag,
  Descriptions,
  Transfer,
  Empty
} from 'antd'
import {
  UserOutlined,
  SafetyOutlined,
  PlusOutlined,
  DeleteOutlined
} from '@ant-design/icons'
import { userApi } from '../../api'
import { 
  getRoles, getUserRoles, assignRoleToUser, removeRoleFromUser,
  getRoleGroups, getUserRoleGroups, assignRoleGroupToUser, removeRoleGroupFromUser
} from '../../api/rbac'
import type { ColumnsType } from 'antd/es/table'



interface User {
  id: number
  username: string
  real_name?: string
  email: string
  role?: string
  status: number
}

interface Role {
  id: number
  name: string
  code: string
  description?: string
  role_type: string
}

interface UserRole {
  id: number
  role_id: number
  role_name: string
  role_code: string
  valid_until?: string
  created_at: string
}

interface RoleGroup {
  id: number
  name: string
  code: string
  description?: string
}

const UserRoleManager: React.FC = () => {
  const [users, setUsers] = useState<User[]>([])
  const [roles, setRoles] = useState<Role[]>([])
  const [roleGroups, setRoleGroups] = useState<RoleGroup[]>([])
  const [loading, setLoading] = useState(false)
  const [modalVisible, setModalVisible] = useState(false)
  const [selectedUser, setSelectedUser] = useState<User | null>(null)
  const [userRoles, setUserRoles] = useState<UserRole[]>([])
  const [userRoleGroups, setUserRoleGroups] = useState<RoleGroup[]>([])
  const [selectedRoles, setSelectedRoles] = useState<string[]>([])
  const [selectedRoleGroups, setSelectedRoleGroups] = useState<string[]>([])
  const [transferVisible, setTransferVisible] = useState(false)
  const [roleGroupTransferVisible, setRoleGroupTransferVisible] = useState(false)

  // 获取用户列表
  const fetchUsers = async () => {
    setLoading(true)
    try {
      const res: any = await userApi.getUsers()
      // 后端返回 {items, total}，api 拦截器返回 response.data
      setUsers(res.items || res.data?.items || [])
    } catch (error) {
      message.error('获取用户列表失败')
    } finally {
      setLoading(false)
    }
  }

  // 获取角色列表
  const fetchRoles = async () => {
    try {
      const res: any = await getRoles({ status: 1 })
      // 后端直接返回数组
      setRoles(Array.isArray(res) ? res : (res.data || []))
    } catch (error) {
      message.error('获取角色列表失败')
    }
  }

  // 获取角色组列表
  const fetchRoleGroups = async () => {
    try {
      const res: any = await getRoleGroups()
      setRoleGroups(Array.isArray(res) ? res : (res.data || []))
    } catch (error) {
      message.error('获取角色组列表失败')
    }
  }

  useEffect(() => {
    fetchUsers()
    fetchRoles()
    fetchRoleGroups()
  }, [])

  // 查看用户角色
  const handleViewRoles = async (user: User) => {
    setSelectedUser(user)
    try {
      const [rolesRes, roleGroupsRes] = await Promise.all([
        getUserRoles(user.id),
        getUserRoleGroups(user.id)
      ])
      // 后端直接返回数组
      setUserRoles(Array.isArray(rolesRes) ? rolesRes : (rolesRes.data || []))
      setUserRoleGroups(Array.isArray(roleGroupsRes) ? roleGroupsRes : (roleGroupsRes.data || []))
      setModalVisible(true)
    } catch (error) {
      message.error('获取用户角色失败')
    }
  }

  // 打开角色分配弹窗
  const handleAssignRole = (user: User) => {
    setSelectedUser(user)
    // 获取用户已有角色ID，转换为字符串
    const existingRoleIds = userRoles.map(ur => String(ur.role_id))
    setSelectedRoles(existingRoleIds)
    setTransferVisible(true)
  }

  // 打开角色组分配弹窗
  const handleAssignRoleGroup = (user: User) => {
    setSelectedUser(user)
    // 获取用户已有角色组ID，转换为字符串
    const existingRoleGroupIds = userRoleGroups.map(rg => String(rg.id))
    setSelectedRoleGroups(existingRoleGroupIds)
    setRoleGroupTransferVisible(true)
  }

  // 分配角色
  const handleTransferChange = async () => {
    if (!selectedUser) return
    
    const currentRoleIds = userRoles.map(ur => ur.role_id)
    const targetIds = selectedRoles.map(k => Number(k))
    
    // 新增的角色
    const toAdd = targetIds.filter(id => !currentRoleIds.includes(id))
    // 移除的角色
    const toRemove = currentRoleIds.filter(id => !targetIds.includes(id))
    
    try {
      // 添加新角色
      for (const roleId of toAdd) {
        await assignRoleToUser({ user_id: selectedUser.id, role_id: roleId })
      }
      
      // 移除角色
      for (const roleId of toRemove) {
        await removeRoleFromUser(selectedUser.id, roleId)
      }
      
      message.success('角色分配成功')
      setTransferVisible(false)
      
      // 刷新用户角色列表
      const res: any = await getUserRoles(selectedUser.id)
      setUserRoles(Array.isArray(res) ? res : (res.data || []))
    } catch (error: any) {
      message.error(error.response?.data?.detail || '角色分配失败')
    }
  }

  // 移除用户角色
  const handleRemoveRole = async (roleId: number) => {
    if (!selectedUser) return
    
    try {
      await removeRoleFromUser(selectedUser.id, roleId)
      message.success('角色已移除')
      
      // 刷新列表
      const res: any = await getUserRoles(selectedUser.id)
      setUserRoles(Array.isArray(res) ? res : (res.data || []))
    } catch (error) {
      message.error('移除角色失败')
    }
  }

  // 分配角色组
  const handleRoleGroupTransferChange = async () => {
    if (!selectedUser) return
    
    const currentRoleGroupIds = userRoleGroups.map(rg => rg.id)
    const targetIds = selectedRoleGroups.map(k => Number(k))
    
    // 新增的角色组
    const toAdd = targetIds.filter(id => !currentRoleGroupIds.includes(id))
    // 移除的角色组
    const toRemove = currentRoleGroupIds.filter(id => !targetIds.includes(id))
    
    try {
      // 添加新角色组
      for (const roleGroupId of toAdd) {
        await assignRoleGroupToUser(selectedUser.id, roleGroupId)
      }
      
      // 移除角色组
      for (const roleGroupId of toRemove) {
        await removeRoleGroupFromUser(selectedUser.id, roleGroupId)
      }
      
      message.success('角色组分配成功')
      setRoleGroupTransferVisible(false)
      
      // 刷新用户角色组列表
      const res: any = await getUserRoleGroups(selectedUser.id)
      setUserRoleGroups(Array.isArray(res) ? res : (res.data || []))
    } catch (error: any) {
      message.error(error.response?.data?.detail || '角色组分配失败')
    }
  }

  // 移除用户角色组
  const handleRemoveRoleGroup = async (roleGroupId: number) => {
    if (!selectedUser) return
    
    try {
      await removeRoleGroupFromUser(selectedUser.id, roleGroupId)
      message.success('角色组已移除')
      
      // 刷新列表
      const res: any = await getUserRoleGroups(selectedUser.id)
      setUserRoleGroups(Array.isArray(res) ? res : (res.data || []))
    } catch (error) {
      message.error('移除角色组失败')
    }
  }

  const columns: ColumnsType<User> = [
    {
      title: '用户名',
      dataIndex: 'username',
      key: 'username',
      render: (text, record) => (
        <Space>
          <UserOutlined />
          <span>{text}</span>
          {record.real_name && <span>({record.real_name})</span>}
        </Space>
      )
    },
    {
      title: '邮箱',
      dataIndex: 'email',
      key: 'email'
    },
    {
      title: '当前角色',
      dataIndex: 'role',
      key: 'role',
      render: (role) => role ? <Tag color="blue">{role}</Tag> : <Tag>无</Tag>
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status) => (
        <Tag color={status === 1 ? 'success' : 'default'}>
          {status === 1 ? '启用' : '禁用'}
        </Tag>
      )
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <Space size="small">
          <Button
            type="text"
            icon={<SafetyOutlined />}
            onClick={() => handleViewRoles(record)}
          >
            查看角色
          </Button>
          <Button
            type="primary"
            ghost
            icon={<PlusOutlined />}
            onClick={() => handleAssignRole(record)}
          >
            分配角色
          </Button>
          <Button
            type="primary"
            ghost
            icon={<PlusOutlined />}
            onClick={() => handleAssignRoleGroup(record)}
          >
            分配角色组
          </Button>
        </Space>
      )
    }
  ]

  return (
    <div className="user-role-manager">
      <Card
        title={
          <Space>
            <UserOutlined />
            <span>用户角色管理</span>
          </Space>
        }
      >
        <Table
          columns={columns}
          dataSource={users}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 10 }}
        />
      </Card>

      {/* 用户角色详情弹窗 */}
      <Modal
        title="用户角色详情"
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        footer={[
          <Button key="close" onClick={() => setModalVisible(false)}>
            关闭
          </Button>,
          <Button
            key="assign"
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => selectedUser && handleAssignRole(selectedUser)}
          >
            分配新角色
          </Button>
        ]}
        width={600}
      >
        {selectedUser && (
          <>
            <Descriptions bordered column={2} size="small" style={{ marginBottom: 16 }}>
              <Descriptions.Item label="用户名">{selectedUser.username}</Descriptions.Item>
              <Descriptions.Item label="姓名">{selectedUser.real_name || '-'}</Descriptions.Item>
              <Descriptions.Item label="邮箱">{selectedUser.email}</Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={selectedUser.status === 1 ? 'success' : 'default'}>
                  {selectedUser.status === 1 ? '启用' : '禁用'}
                </Tag>
              </Descriptions.Item>
            </Descriptions>

            <Card title="已分配角色" size="small" style={{ marginBottom: 16 }}>
              {userRoles.length === 0 ? (
                <Empty description="暂无角色" />
              ) : (
                <Space direction="vertical" style={{ width: '100%' }}>
                  {userRoles.map((ur) => (
                    <Card key={ur.id} size="small" style={{ marginBottom: 8 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div>
                          <Tag color="blue">{ur.role_name}</Tag>
                          <span style={{ color: '#999', fontSize: 12 }}>{ur.role_code}</span>
                          {ur.valid_until && (
                            <div style={{ color: '#ff4d4f', fontSize: 12, marginTop: 4 }}>
                              有效期至: {ur.valid_until}
                            </div>
                          )}
                        </div>
                        <Button
                          type="text"
                          danger
                          icon={<DeleteOutlined />}
                          onClick={() => handleRemoveRole(ur.role_id)}
                        >
                          移除
                        </Button>
                      </div>
                    </Card>
                  ))}
                </Space>
              )}
            </Card>

            <Card title="已分配角色组" size="small">
              {userRoleGroups.length === 0 ? (
                <Empty description="暂无角色组" />
              ) : (
                <Space direction="vertical" style={{ width: '100%' }}>
                  {userRoleGroups.map((rg) => (
                    <Card key={rg.id} size="small" style={{ marginBottom: 8 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div>
                          <Tag color="green">{rg.name}</Tag>
                          <span style={{ color: '#999', fontSize: 12 }}>{rg.code}</span>
                        </div>
                        <Button
                          type="text"
                          danger
                          icon={<DeleteOutlined />}
                          onClick={() => handleRemoveRoleGroup(rg.id)}
                        >
                          移除
                        </Button>
                      </div>
                    </Card>
                  ))}
                </Space>
              )}
            </Card>
          </>
        )}
      </Modal>

      {/* 角色分配弹窗 */}
      <Modal
        title="分配角色"
        open={transferVisible}
        onCancel={() => setTransferVisible(false)}
        footer={null}
        width={600}
      >
        <Transfer
          dataSource={roles.map(r => ({
            key: String(r.id),
            title: r.name,
            description: r.description || r.code
          }))}
          titles={['可选角色', '已选角色']}
          targetKeys={selectedRoles}
          onChange={(keys) => setSelectedRoles(keys as string[])}
          render={item => item.title}
          listStyle={{
            width: 250,
            height: 300
          }}
        />
        <div style={{ textAlign: 'center', marginTop: 16 }}>
          <Button type="primary" onClick={handleTransferChange}>确定</Button>
          <Button style={{ marginLeft: 8 }} onClick={() => setTransferVisible(false)}>取消</Button>
        </div>
      </Modal>

      {/* 角色组分配弹窗 */}
      <Modal
        title="分配角色组"
        open={roleGroupTransferVisible}
        onCancel={() => setRoleGroupTransferVisible(false)}
        footer={null}
        width={600}
      >
        <Transfer
          dataSource={roleGroups.map(rg => ({
            key: String(rg.id),
            title: rg.name,
            description: rg.code
          }))}
          titles={['可选角色组', '已选角色组']}
          targetKeys={selectedRoleGroups}
          onChange={(keys) => setSelectedRoleGroups(keys as string[])}
          render={item => item.title}
          listStyle={{
            width: 250,
            height: 300
          }}
        />
        <div style={{ textAlign: 'center', marginTop: 16 }}>
          <Button type="primary" onClick={handleRoleGroupTransferChange}>确定</Button>
          <Button style={{ marginLeft: 8 }} onClick={() => setRoleGroupTransferVisible(false)}>取消</Button>
        </div>
      </Modal>
    </div>
  )
}

export default UserRoleManager
