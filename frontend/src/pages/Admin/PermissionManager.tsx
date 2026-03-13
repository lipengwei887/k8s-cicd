import React, { useState, useEffect } from 'react'
import {
  Card,
  Button,
  Table,
  Modal,
  Form,
  Select,
  message,
  Space,
  Tag,
  Popconfirm,
  TreeSelect,
  Divider,
} from 'antd'
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import { userApi, clusterApi } from '@/api'

interface User {
  id: number
  username: string
  real_name?: string
  role: string
}

interface Cluster {
  id: number
  name: string
  display_name: string
}

interface Namespace {
  id: number
  name: string
  display_name: string
  cluster_id: number
}

interface Permission {
  id: number
  user_id: number
  cluster_id?: number
  namespace_id?: number
  role: string
  username?: string
  cluster_name?: string
  namespace_name?: string
}

const PermissionManager: React.FC = () => {
  const [users, setUsers] = useState<User[]>([])
  const [clusters, setClusters] = useState<Cluster[]>([])
  const [namespaces, setNamespaces] = useState<Namespace[]>([])
  const [permissions, setPermissions] = useState<Permission[]>([])
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
      setUsers(usersRes.items || [])

      // 加载集群列表
      const clustersRes: any = await clusterApi.getClusters()
      setClusters(clustersRes.items || [])

      // 加载所有命名空间
      const allNamespaces: Namespace[] = []
      for (const cluster of clustersRes.items || []) {
        try {
          const nsRes: any = await clusterApi.getNamespaces(cluster.id)
          for (const ns of nsRes.items || []) {
            allNamespaces.push({
              ...ns,
              cluster_id: cluster.id,
            })
          }
        } catch (e) {
          console.error(`Failed to load namespaces for cluster ${cluster.id}`)
        }
      }
      setNamespaces(allNamespaces)

      // 加载所有用户的权限
      await loadAllPermissions(usersRes.items || [])
    } catch (error) {
      message.error('加载数据失败')
    } finally {
      setLoading(false)
    }
  }

  const loadAllPermissions = async (userList: User[]) => {
    const allPermissions: Permission[] = []
    for (const user of userList) {
      try {
        const res: any = await userApi.getUserPermissions(user.id)
        for (const perm of res.items || []) {
          allPermissions.push({
            ...perm,
            username: user.username,
            cluster_name: clusters.find(c => c.id === perm.cluster_id)?.display_name,
            namespace_name: namespaces.find(n => n.id === perm.namespace_id)?.display_name,
          })
        }
      } catch (e) {
        console.error(`Failed to load permissions for user ${user.id}`)
      }
    }
    setPermissions(allPermissions)
  }

  const handleCreate = async (values: any) => {
    try {
      // 处理多选的权限范围
      const scopeIds: (string | number)[] = values.scope_ids || []
      
      // 为每个选中的范围创建权限
      for (const scopeId of scopeIds) {
        let clusterId: number | null = null
        let namespaceId: number | null = null
        
        if (typeof scopeId === 'string' && scopeId.startsWith('cluster-')) {
          // 选择的是集群
          clusterId = parseInt(scopeId.replace('cluster-', ''))
        } else {
          // 选择的是命名空间
          namespaceId = scopeId as number
          // 找到命名空间对应的集群
          const ns = namespaces.find(n => n.id === namespaceId)
          if (ns) {
            clusterId = ns.cluster_id
          }
        }
        
        await userApi.addUserPermission(values.user_id, {
          cluster_id: clusterId,
          namespace_id: namespaceId,
          role: values.role,
        })
      }
      
      // 如果没有选择任何范围，则创建全局权限
      if (scopeIds.length === 0) {
        await userApi.addUserPermission(values.user_id, {
          cluster_id: null,
          namespace_id: null,
          role: values.role,
        })
      }
      
      message.success('权限添加成功')
      setModalVisible(false)
      form.resetFields()
      loadData()
    } catch (error: any) {
      message.error(error.response?.data?.detail || '添加失败')
    }
  }

  const handleDelete = async (userId: number, permissionId: number) => {
    try {
      await userApi.removeUserPermission(userId, permissionId)
      message.success('权限删除成功')
      loadData()
    } catch (error) {
      message.error('删除失败')
    }
  }

  const getRoleTag = (role: string) => {
    const roleMap: Record<string, { color: string; text: string }> = {
      admin: { color: 'red', text: '管理员' },
      operator: { color: 'blue', text: '操作员' },
      viewer: { color: 'green', text: '只读' },
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
      title: '用户',
      dataIndex: 'username',
    },
    {
      title: '集群',
      dataIndex: 'cluster_name',
      render: (text: string) => text || '全部集群',
    },
    {
      title: '命名空间',
      dataIndex: 'namespace_name',
      render: (text: string) => text || '全部命名空间',
    },
    {
      title: '权限角色',
      dataIndex: 'role',
      render: (role: string) => getRoleTag(role),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: Permission) => (
        <Popconfirm
          title="确定删除该权限吗？"
          onConfirm={() => handleDelete(record.user_id, record.id)}
        >
          <Button size="small" danger icon={<DeleteOutlined />}>
            删除
          </Button>
        </Popconfirm>
      ),
    },
  ]

  // 构建命名空间树形数据
  const buildNamespaceTree = () => {
    return clusters.map(cluster => ({
      title: cluster.display_name,
      value: `cluster-${cluster.id}`,
      selectable: false,
      children: namespaces
        .filter(ns => ns.cluster_id === cluster.id)
        .map(ns => ({
          title: ns.display_name,
          value: ns.id,
        })),
    }))
  }

  return (
    <div>
      <Card
        title="权限管理"
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalVisible(true)}>
            添加权限
          </Button>
        }
      >
        <Table
          columns={columns}
          dataSource={permissions}
          rowKey="id"
          loading={loading}
        />
      </Card>

      {/* 添加权限弹窗 */}
      <Modal
        title="添加权限"
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
            label="权限范围"
            name="scope_ids"
          >
            <TreeSelect
              treeData={buildNamespaceTree()}
              placeholder="选择命名空间（不选则拥有全部权限）"
              allowClear
              treeDefaultExpandAll
              multiple
              treeCheckable
              showCheckedStrategy={TreeSelect.SHOW_PARENT}
              maxTagCount={3}
            />
          </Form.Item>

          <Form.Item
            label="权限角色"
            name="role"
            initialValue="operator"
            rules={[{ required: true, message: '请选择权限角色' }]}
          >
            <Select placeholder="选择权限角色">
              <Select.Option value="admin">管理员 - 所有操作权限</Select.Option>
              <Select.Option value="operator">操作员 - 发布、查看</Select.Option>
              <Select.Option value="viewer">只读 - 仅查看</Select.Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default PermissionManager
