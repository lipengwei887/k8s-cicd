import React, { useState, useEffect } from 'react'
import {
  Card,
  Table,
  Button,
  Space,
  Modal,
  Form,
  Input,
  Select,
  Switch,
  message,
  Popconfirm,
  Tag,
  Tree,
  Divider
} from 'antd'
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  TeamOutlined,
  SafetyOutlined
} from '@ant-design/icons'
import { getRoles, getRole, createRole, updateRole, deleteRole, getPermissions } from '../../api/rbac'
import type { ColumnsType } from 'antd/es/table'

const { TextArea } = Input
const { Option } = Select

interface Role {
  id: number
  name: string
  code: string
  description?: string
  role_type: string
  status: number
  created_at: string
  permissions?: Permission[]
}

interface Permission {
  id: number
  name: string
  code: string
  resource_type: string
  action: string
  children?: Permission[]
}

const RoleManager: React.FC = () => {
  const [roles, setRoles] = useState<Role[]>([])
  const [permissions, setPermissions] = useState<Permission[]>([])
  const [loading, setLoading] = useState(false)
  const [modalVisible, setModalVisible] = useState(false)
  const [modalTitle, setModalTitle] = useState('新增角色')
  const [editingRole, setEditingRole] = useState<Role | null>(null)
  const [form] = Form.useForm()
  const [selectedPermissions, setSelectedPermissions] = useState<number[]>([])
  const [permissionTree, setPermissionTree] = useState<any[]>([])

  // 获取角色列表
  const fetchRoles = async () => {
    setLoading(true)
    try {
      const res = await getRoles()
      // 后端直接返回数组
      setRoles(Array.isArray(res) ? res : (res.data || []))
    } catch (error) {
      message.error('获取角色列表失败')
    } finally {
      setLoading(false)
    }
  }

  // 获取权限列表
  const fetchPermissions = async () => {
    try {
      const res = await getPermissions()
      const perms = Array.isArray(res) ? res : (res.data || [])
      setPermissions(perms)
      
      // 构建权限树
      const tree = buildPermissionTree(perms)
      setPermissionTree(tree)
    } catch (error) {
      message.error('获取权限列表失败')
    }
  }

  // 构建权限树
  const buildPermissionTree = (perms: Permission[]) => {
    const resourceTypes = ['cluster', 'namespace', 'service', 'release', 'user', 'role']
    const resourceNames: Record<string, string> = {
      cluster: '集群管理',
      namespace: '命名空间',
      service: '服务管理',
      release: '发布管理',
      user: '用户管理',
      role: '角色管理'
    }
    
    return resourceTypes.map(type => {
      const typePerms = perms.filter(p => p.resource_type === type)
      return {
        title: resourceNames[type] || type,
        key: type,
        children: typePerms.map(p => ({
          title: p.name,
          key: p.id,
          code: p.code
        }))
      }
    }).filter(node => node.children.length > 0)
  }

  useEffect(() => {
    fetchRoles()
    fetchPermissions()
  }, [])

  // 打开新增弹窗
  const handleAdd = () => {
    setEditingRole(null)
    setModalTitle('新增角色')
    setSelectedPermissions([])
    form.resetFields()
    setModalVisible(true)
  }

  // 打开编辑弹窗
  const handleEdit = async (record: Role) => {
    setEditingRole(record)
    setModalTitle('编辑角色')
    
    // 获取角色详情
    try {
      const res = await getRole(record.id)
      // 后端直接返回对象
      const roleDetail = res.data || res
      
      form.setFieldsValue({
        name: roleDetail.name,
        code: roleDetail.code,
        description: roleDetail.description,
        status: roleDetail.status === 1
      })
      
      const permIds = roleDetail.permissions?.map((p: Permission) => p.id) || []
      setSelectedPermissions(permIds)
      setModalVisible(true)
    } catch (error) {
      message.error('获取角色详情失败')
    }
  }

  // 提交表单
  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()
      
      const data = {
        ...values,
        status: values.status ? 1 : 0,
        permission_ids: selectedPermissions
      }
      
      if (editingRole) {
        await updateRole(editingRole.id, data)
        message.success('角色更新成功')
      } else {
        await createRole(data)
        message.success('角色创建成功')
      }
      
      setModalVisible(false)
      fetchRoles()
    } catch (error: any) {
      message.error(error.response?.data?.detail || '操作失败')
    }
  }

  // 删除角色
  const handleDelete = async (id: number) => {
    try {
      await deleteRole(id)
      message.success('角色删除成功')
      fetchRoles()
    } catch (error: any) {
      message.error(error.response?.data?.detail || '删除失败')
    }
  }

  // 权限树选择
  const onPermissionCheck = (checkedKeys: any) => {
    // 过滤掉父节点（只保留权限ID）
    const permIds = checkedKeys.filter((key: any) => typeof key === 'number')
    setSelectedPermissions(permIds)
  }

  const columns: ColumnsType<Role> = [
    {
      title: '角色名称',
      dataIndex: 'name',
      key: 'name',
      render: (text, record) => (
        <Space>
          <SafetyOutlined style={{ color: record.role_type === 'system' ? '#1890ff' : '#52c41a' }} />
          <span>{text}</span>
        </Space>
      )
    },
    {
      title: '角色编码',
      dataIndex: 'code',
      key: 'code'
    },
    {
      title: '类型',
      dataIndex: 'role_type',
      key: 'role_type',
      render: (type) => (
        <Tag color={type === 'system' ? 'blue' : 'green'}>
          {type === 'system' ? '系统角色' : '自定义'}
        </Tag>
      )
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true
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
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at'
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <Space size="small">
          <Button
            type="text"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
            disabled={record.role_type === 'system'}
          >
            编辑
          </Button>
          <Popconfirm
            title="确认删除"
            description="删除后无法恢复，是否继续？"
            onConfirm={() => handleDelete(record.id)}
            disabled={record.role_type === 'system'}
          >
            <Button
              type="text"
              danger
              icon={<DeleteOutlined />}
              disabled={record.role_type === 'system'}
            >
              删除
            </Button>
          </Popconfirm>
        </Space>
      )
    }
  ]

  return (
    <div className="role-manager">
      <Card
        title={
          <Space>
            <TeamOutlined />
            <span>角色管理</span>
          </Space>
        }
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
            新增角色
          </Button>
        }
      >
        <Table
          columns={columns}
          dataSource={roles}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 10 }}
        />
      </Card>

      <Modal
        title={modalTitle}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        width={700}
        destroyOnHidden
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{ status: true }}
        >
          <Form.Item
            name="name"
            label="角色名称"
            rules={[{ required: true, message: '请输入角色名称' }]}
          >
            <Input placeholder="如：运维工程师" />
          </Form.Item>

          <Form.Item
            name="code"
            label="角色编码"
            rules={[{ required: true, message: '请输入角色编码' }]}
          >
            <Input placeholder="如：ops_engineer" disabled={!!editingRole} />
          </Form.Item>

          <Form.Item
            name="description"
            label="描述"
          >
            <TextArea rows={2} placeholder="角色描述" />
          </Form.Item>

          <Form.Item
            name="status"
            label="状态"
            valuePropName="checked"
          >
            <Switch checkedChildren="启用" unCheckedChildren="禁用" />
          </Form.Item>

          <Divider orientation="left">权限配置</Divider>

          <Form.Item label="选择权限">
            <Tree
              checkable
              treeData={permissionTree}
              checkedKeys={selectedPermissions}
              onCheck={onPermissionCheck}
              defaultExpandAll
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default RoleManager
