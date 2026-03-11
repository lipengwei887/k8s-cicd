import React, { useState, useEffect } from 'react'
import {
  Card,
  Button,
  Table,
  Modal,
  Form,
  Input,
  Select,
  message,
  Space,
  Tag,
  Popconfirm,
  Switch,
} from 'antd'
import { PlusOutlined, DeleteOutlined, EditOutlined, KeyOutlined } from '@ant-design/icons'
import { userApi } from '@/api'

interface User {
  id: number
  username: string
  email: string
  real_name?: string
  role: string
  status: number
  created_at: string
}

const UserManager: React.FC = () => {
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(false)
  const [modalVisible, setModalVisible] = useState(false)
  const [editModalVisible, setEditModalVisible] = useState(false)
  const [selectedUser, setSelectedUser] = useState<User | null>(null)
  const [form] = Form.useForm()
  const [editForm] = Form.useForm()

  useEffect(() => {
    loadUsers()
  }, [])

  const loadUsers = async () => {
    setLoading(true)
    try {
      const res: any = await userApi.getUsers()
      setUsers(res.items || [])
    } catch (error) {
      message.error('加载用户列表失败')
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async (values: any) => {
    try {
      await userApi.createUser(values)
      message.success('用户创建成功')
      setModalVisible(false)
      form.resetFields()
      loadUsers()
    } catch (error: any) {
      message.error(error.response?.data?.detail || '创建失败')
    }
  }

  const handleUpdate = async (values: any) => {
    if (!selectedUser) return
    
    try {
      await userApi.updateUser(selectedUser.id, values)
      message.success('用户更新成功')
      setEditModalVisible(false)
      editForm.resetFields()
      loadUsers()
    } catch (error: any) {
      message.error(error.response?.data?.detail || '更新失败')
    }
  }

  const handleDelete = async (userId: number) => {
    try {
      await userApi.deleteUser(userId)
      message.success('用户删除成功')
      loadUsers()
    } catch (error) {
      message.error('删除失败')
    }
  }

  const handleStatusChange = async (user: User, checked: boolean) => {
    try {
      await userApi.updateUser(user.id, { status: checked ? 1 : 0 })
      message.success('状态更新成功')
      loadUsers()
    } catch (error) {
      message.error('状态更新失败')
    }
  }

  const openEditModal = (user: User) => {
    setSelectedUser(user)
    editForm.setFieldsValue({
      email: user.email,
      real_name: user.real_name,
      role: user.role,
    })
    setEditModalVisible(true)
  }

  const getRoleTag = (role: string) => {
    const roleMap: Record<string, { color: string; text: string }> = {
      admin: { color: 'red', text: '管理员' },
      developer: { color: 'blue', text: '开发人员' },
      viewer: { color: 'green', text: '只读用户' },
      approver: { color: 'orange', text: '审批人员' },
    }
    const { color, text } = roleMap[role] || { color: 'default', text: role }
    return <Tag color={color}>{text}</Tag>
  }

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      width: 80,
    },
    {
      title: '用户名',
      dataIndex: 'username',
    },
    {
      title: '邮箱',
      dataIndex: 'email',
    },
    {
      title: '姓名',
      dataIndex: 'real_name',
      render: (text: string) => text || '-',
    },
    {
      title: '角色',
      dataIndex: 'role',
      render: (role: string) => getRoleTag(role),
    },
    {
      title: '状态',
      dataIndex: 'status',
      render: (status: number, record: User) => (
        <Switch
          checked={status === 1}
          onChange={(checked) => handleStatusChange(record, checked)}
          checkedChildren="启用"
          unCheckedChildren="禁用"
        />
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: User) => (
        <Space>
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={() => openEditModal(record)}
          >
            编辑
          </Button>
          <Button
            size="small"
            icon={<KeyOutlined />}
            onClick={() => {
              setSelectedUser(record)
              // TODO: 打开权限管理弹窗
            }}
          >
            权限
          </Button>
          <Popconfirm
            title="确定删除该用户吗？"
            onConfirm={() => handleDelete(record.id)}
          >
            <Button size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <Card
        title="人员管理"
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalVisible(true)}>
            新增用户
          </Button>
        }
      >
        <Table
          columns={columns}
          dataSource={users}
          rowKey="id"
          loading={loading}
        />
      </Card>

      {/* 创建用户弹窗 */}
      <Modal
        title="新增用户"
        open={modalVisible}
        onCancel={() => {
          setModalVisible(false)
          form.resetFields()
        }}
        onOk={() => form.submit()}
        width={500}
      >
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          <Form.Item
            label="用户名"
            name="username"
            rules={[{ required: true, message: '请输入用户名' }]}
          >
            <Input placeholder="登录用户名" />
          </Form.Item>

          <Form.Item
            label="密码"
            name="password"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password placeholder="登录密码" />
          </Form.Item>

          <Form.Item
            label="邮箱"
            name="email"
            rules={[
              { required: true, message: '请输入邮箱' },
              { type: 'email', message: '请输入有效的邮箱地址' },
            ]}
          >
            <Input placeholder="user@example.com" />
          </Form.Item>

          <Form.Item label="姓名" name="real_name">
            <Input placeholder="真实姓名" />
          </Form.Item>

          <Form.Item
            label="角色"
            name="role"
            initialValue="developer"
            rules={[{ required: true, message: '请选择角色' }]}
          >
            <Select placeholder="选择角色">
              <Select.Option value="admin">管理员</Select.Option>
              <Select.Option value="developer">开发人员</Select.Option>
              <Select.Option value="approver">审批人员</Select.Option>
              <Select.Option value="viewer">只读用户</Select.Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>

      {/* 编辑用户弹窗 */}
      <Modal
        title="编辑用户"
        open={editModalVisible}
        onCancel={() => {
          setEditModalVisible(false)
          editForm.resetFields()
        }}
        onOk={() => editForm.submit()}
        width={500}
      >
        <Form form={editForm} layout="vertical" onFinish={handleUpdate}>
          <Form.Item
            label="邮箱"
            name="email"
            rules={[
              { required: true, message: '请输入邮箱' },
              { type: 'email', message: '请输入有效的邮箱地址' },
            ]}
          >
            <Input />
          </Form.Item>

          <Form.Item label="姓名" name="real_name">
            <Input />
          </Form.Item>

          <Form.Item
            label="角色"
            name="role"
            rules={[{ required: true, message: '请选择角色' }]}
          >
            <Select placeholder="选择角色">
              <Select.Option value="admin">管理员</Select.Option>
              <Select.Option value="developer">开发人员</Select.Option>
              <Select.Option value="approver">审批人员</Select.Option>
              <Select.Option value="viewer">只读用户</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item label="新密码" name="password">
            <Input.Password placeholder="不修改请留空" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default UserManager
