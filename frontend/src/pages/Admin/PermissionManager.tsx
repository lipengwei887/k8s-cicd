import { useState, useEffect } from 'react'
import {
  Card,
  Button,
  Table,
  Modal,
  Form,
  Select,
  message,
  Tag,
  Popconfirm,
} from 'antd'
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import { userApi } from '@/api'
import { getRoles, getUserRoles, assignRoleToUser, removeRoleFromUser } from '@/api/rbac'

interface User {
  id: number
  username: string
  real_name?: string
  role: string
}

interface Role {
  id: number
  name: string
  code: string
  role_type: string
}

interface UserRoleItem {
  user_id: number
  username: string
  role_id: number
  role_name: string
  role_code: string
  role_type: string
}

const PermissionManager: React.FC = () => {
  const [users, setUsers] = useState<User[]>([])
  const [roles, setRoles] = useState<Role[]>([])
  const [userRoles, setUserRoles] = useState<UserRoleItem[]>([])
  const [loading, setLoading] = useState(false)
  const [modalVisible, setModalVisible] = useState(false)
  const [form] = Form.useForm()

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    setLoading(true)
    try {
      // 加载用户列表
      const usersRes: any = await userApi.getUsers()
      const userList = usersRes.items || []
      setUsers(userList)

      // 加载角色列表
      const rolesRes: any = await getRoles()
      setRoles(rolesRes.items || [])

      // 加载所有用户的角色
      await loadAllUserRoles(userList)
    } catch (error) {
      message.error('加载数据失败')
    } finally {
      setLoading(false)
    }
  }

  const loadAllUserRoles = async (userList: User[]) => {
    const allUserRoles: UserRoleItem[] = []
    for (const user of userList) {
      try {
        const res: any = await getUserRoles(user.id)
        for (const role of res.items || []) {
          allUserRoles.push({
            user_id: user.id,
            username: user.username,
            role_id: role.id,
            role_name: role.name,
            role_code: role.code,
            role_type: role.role_type,
          })
        }
      } catch (e) {
        console.error(`Failed to load roles for user ${user.id}`)
      }
    }
    setUserRoles(allUserRoles)
  }

  const handleAssignRole = async (values: any) => {
    try {
      await assignRoleToUser({
        user_id: values.user_id,
        role_id: values.role_id,
      })
      
      message.success('角色分配成功')
      setModalVisible(false)
      form.resetFields()
      loadData()
    } catch (error: any) {
      message.error(error.response?.data?.detail || '分配失败')
    }
  }

  const handleRemoveRole = async (userId: number, roleId: number) => {
    try {
      await removeRoleFromUser(userId, roleId)
      message.success('角色移除成功')
      loadData()
    } catch (error) {
      message.error('移除失败')
    }
  }

  const getRoleTypeTag = (roleType: string) => {
    const typeMap: Record<string, { color: string; text: string }> = {
      system: { color: 'red', text: '系统' },
      custom: { color: 'blue', text: '自定义' },
    }
    const { color, text } = typeMap[roleType] || { color: 'default', text: roleType }
    return <Tag color={color}>{text}</Tag>
  }

  const columns = [
    {
      title: '用户',
      dataIndex: 'username',
    },
    {
      title: '角色名称',
      dataIndex: 'role_name',
    },
    {
      title: '角色编码',
      dataIndex: 'role_code',
    },
    {
      title: '角色类型',
      dataIndex: 'role_type',
      render: (type: string) => getRoleTypeTag(type),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: UserRoleItem) => (
        <Popconfirm
          title="确定移除该角色吗？"
          onConfirm={() => handleRemoveRole(record.user_id, record.role_id)}
        >
          <Button size="small" danger icon={<DeleteOutlined />}>
            移除
          </Button>
        </Popconfirm>
      ),
    },
  ]

  return (
    <div>
      <Card
        title="用户角色管理 (RBAC)"
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalVisible(true)}>
            分配角色
          </Button>
        }
      >
        <Table
          columns={columns}
          dataSource={userRoles}
          rowKey={(record) => `${record.user_id}-${record.role_id}`}
          loading={loading}
        />
      </Card>

      {/* 分配角色弹窗 */}
      <Modal
        title="分配角色"
        open={modalVisible}
        onCancel={() => {
          setModalVisible(false)
          form.resetFields()
        }}
        onOk={() => form.submit()}
        width={500}
      >
        <Form form={form} layout="vertical" onFinish={handleAssignRole}>
          <Form.Item
            label="选择用户"
            name="user_id"
            rules={[{ required: true, message: '请选择用户' }]}
          >
            <Select placeholder="选择用户">
              {users.map(user => (
                <Select.Option key={user.id} value={user.id}>
                  {user.username} {user.real_name ? `(${user.real_name})` : ''}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            label="选择角色"
            name="role_id"
            rules={[{ required: true, message: '请选择角色' }]}
          >
            <Select placeholder="选择角色">
              {roles.map(role => (
                <Select.Option key={role.id} value={role.id}>
                  {role.name} ({role.code}) {role.role_type === 'system' && <Tag color="red">系统</Tag>}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default PermissionManager
