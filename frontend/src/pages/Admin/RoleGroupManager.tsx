import React, { useState, useEffect } from 'react'
import {
  Card,
  Table,
  Button,
  Modal,
  Form,
  Input,
  message,
  Space,
  Popconfirm,
  Tag,
  Transfer,
  Tabs
} from 'antd'
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  SettingOutlined
} from '@ant-design/icons'
import {
  getRoleGroups,
  createRoleGroup,
  updateRoleGroup,
  deleteRoleGroup,
  getRoleGroup,
  addServiceToRoleGroup,
  removeServiceFromRoleGroup,
  addNamespaceToRoleGroup,
  removeNamespaceFromRoleGroup
} from '../../api/rbac'
import { serviceApi, clusterApi } from '../../api/index'

const { TabPane } = Tabs

interface RoleGroup {
  id: number
  name: string
  code: string
  description?: string
  created_at?: string
}

const RoleGroupManager: React.FC = () => {
  const [groups, setGroups] = useState<RoleGroup[]>([])
  const [loading, setLoading] = useState(false)
  const [modalVisible, setModalVisible] = useState(false)
  const [configModalVisible, setConfigModalVisible] = useState(false)
  const [editingGroup, setEditingGroup] = useState<RoleGroup | null>(null)
  const [selectedGroup, setSelectedGroup] = useState<RoleGroup | null>(null)
  const [form] = Form.useForm()
  
  const [services, setServices] = useState<any[]>([])
  const [namespaces, setNamespaces] = useState<any[]>([])
  const [selectedServices, setSelectedServices] = useState<string[]>([])
  const [selectedNamespaces, setSelectedNamespaces] = useState<string[]>([])

  // 获取角色组列表
  const fetchGroups = async () => {
    setLoading(true)
    try {
      const res: any = await getRoleGroups()
      setGroups(Array.isArray(res) ? res : (res.data || []))
    } catch (error) {
      message.error('获取角色组列表失败')
    } finally {
      setLoading(false)
    }
  }

  // 获取服务和命名空间
  const fetchResources = async () => {
    try {
      // 获取服务列表
      const servicesRes: any = await serviceApi.getServices()
      setServices((servicesRes.items || servicesRes.data?.items || []).map((s: any) => ({
        key: String(s.id),
        title: s.display_name || s.name,
        description: s.name
      })))
      
      // 获取所有命名空间（从所有集群）
      const clustersRes: any = await clusterApi.getClusters()
      const clusters = clustersRes.items || clustersRes.data?.items || []
      let allNamespaces: any[] = []
      
      for (const cluster of clusters) {
        try {
          const nsRes: any = await clusterApi.getNamespaces(cluster.id)
          const namespaces = nsRes.items || nsRes.data || []
          allNamespaces = allNamespaces.concat(
            namespaces.map((n: any) => ({
              ...n,
              cluster_name: cluster.name
            }))
          )
        } catch (e) {
          console.error(`获取集群 ${cluster.name} 的命名空间失败`, e)
        }
      }
      
      setNamespaces(allNamespaces.map((n: any) => ({
        key: String(n.id),
        title: n.name,
        description: n.cluster_name || ''
      })))
    } catch (error) {
      console.error('加载资源失败', error)
    }
  }

  useEffect(() => {
    fetchGroups()
    fetchResources()
  }, [])

  // 打开新增弹窗
  const handleAdd = () => {
    setEditingGroup(null)
    form.resetFields()
    setModalVisible(true)
  }

  // 打开编辑弹窗
  const handleEdit = (record: RoleGroup) => {
    setEditingGroup(record)
    form.setFieldsValue({
      name: record.name,
      code: record.code,
      description: record.description
    })
    setModalVisible(true)
  }

  // 打开配置弹窗
  const handleConfig = async (record: RoleGroup) => {
    setSelectedGroup(record)
    try {
      const res: any = await getRoleGroup(record.id)
      const groupDetail = res.data || res
      setSelectedServices((groupDetail.services || []).map((s: any) => String(s.id)))
      setSelectedNamespaces((groupDetail.namespaces || []).map((n: any) => String(n.id)))
      setConfigModalVisible(true)
    } catch (error) {
      message.error('获取角色组详情失败')
    }
  }

  // 提交表单
  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()
      
      if (editingGroup) {
        await updateRoleGroup(editingGroup.id, values)
        message.success('角色组已更新')
      } else {
        await createRoleGroup(values)
        message.success('角色组已创建')
      }
      
      setModalVisible(false)
      fetchGroups()
    } catch (error: any) {
      message.error(error.response?.data?.detail || '操作失败')
    }
  }

  // 删除角色组
  const handleDelete = async (id: number) => {
    try {
      await deleteRoleGroup(id)
      message.success('角色组已删除')
      fetchGroups()
    } catch (error: any) {
      message.error(error.response?.data?.detail || '删除失败')
    }
  }

  // 保存服务配置
  const handleSaveServices = async () => {
    if (!selectedGroup) return
    
    try {
      const res: any = await getRoleGroup(selectedGroup.id)
      const groupDetail = res.data || res
      const currentServiceIds = (groupDetail.services || []).map((s: any) => String(s.id))
      
      // 添加新服务
      const toAdd = selectedServices.filter(id => !currentServiceIds.includes(id))
      // 移除服务
      const toRemove = currentServiceIds.filter((id: string) => !selectedServices.includes(id))
      
      for (const serviceId of toAdd) {
        await addServiceToRoleGroup(selectedGroup.id, Number(serviceId))
      }
      for (const serviceId of toRemove) {
        await removeServiceFromRoleGroup(selectedGroup.id, Number(serviceId))
      }
      
      message.success('服务配置已保存')
    } catch (error) {
      message.error('保存服务配置失败')
    }
  }

  // 保存命名空间配置
  const handleSaveNamespaces = async () => {
    if (!selectedGroup) return
    
    try {
      const res: any = await getRoleGroup(selectedGroup.id)
      const groupDetail = res.data || res
      const currentNamespaceIds = (groupDetail.namespaces || []).map((n: any) => String(n.id))
      
      // 添加新命名空间
      const toAdd = selectedNamespaces.filter(id => !currentNamespaceIds.includes(id))
      // 移除命名空间
      const toRemove = currentNamespaceIds.filter((id: string) => !selectedNamespaces.includes(id))
      
      for (const namespaceId of toAdd) {
        await addNamespaceToRoleGroup(selectedGroup.id, Number(namespaceId))
      }
      for (const namespaceId of toRemove) {
        await removeNamespaceFromRoleGroup(selectedGroup.id, Number(namespaceId))
      }
      
      message.success('命名空间配置已保存')
    } catch (error) {
      message.error('保存命名空间配置失败')
    }
  }

  const columns = [
    {
      title: '组名称',
      dataIndex: 'name',
      key: 'name'
    },
    {
      title: '组编码',
      dataIndex: 'code',
      key: 'code',
      render: (code: string) => <Tag>{code}</Tag>
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: RoleGroup) => (
        <Space>
          <Button
            type="link"
            icon={<SettingOutlined />}
            onClick={() => handleConfig(record)}
          >
            配置权限
          </Button>
          <Button
            type="link"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确定删除此角色组吗？"
            onConfirm={() => handleDelete(record.id)}
          >
            <Button type="link" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      )
    }
  ]

  return (
    <div>
      <Card
        title="角色组管理"
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
            新增角色组
          </Button>
        }
      >
        <Table
          columns={columns}
          dataSource={groups}
          rowKey="id"
          loading={loading}
        />
      </Card>

      {/* 新增/编辑弹窗 */}
      <Modal
        title={editingGroup ? '编辑角色组' : '新增角色组'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="name"
            label="组名称"
            rules={[{ required: true, message: '请输入组名称' }]}
          >
            <Input placeholder="如：支付组" />
          </Form.Item>
          <Form.Item
            name="code"
            label="组编码"
            rules={[{ required: true, message: '请输入组编码' }]}
          >
            <Input placeholder="如：payment" disabled={!!editingGroup} />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={3} placeholder="角色组描述" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 配置权限弹窗 */}
      <Modal
        title={`配置权限 - ${selectedGroup?.name}`}
        open={configModalVisible}
        onCancel={() => setConfigModalVisible(false)}
        footer={null}
        width={700}
      >
        <Tabs defaultActiveKey="services">
          <TabPane tab="关联服务" key="services">
            <Transfer
              dataSource={services}
              titles={['可选服务', '已选服务']}
              targetKeys={selectedServices}
              onChange={(keys) => setSelectedServices(keys as string[])}
              render={item => item.title}
              listStyle={{ width: 280, height: 400 }}
            />
            <div style={{ textAlign: 'center', marginTop: 16 }}>
              <Button type="primary" onClick={handleSaveServices}>
                保存服务配置
              </Button>
            </div>
          </TabPane>
          <TabPane tab="关联命名空间" key="namespaces">
            <Transfer
              dataSource={namespaces}
              titles={['可选命名空间', '已选命名空间']}
              targetKeys={selectedNamespaces}
              onChange={(keys) => setSelectedNamespaces(keys as string[])}
              render={item => item.title}
              listStyle={{ width: 280, height: 400 }}
            />
            <div style={{ textAlign: 'center', marginTop: 16 }}>
              <Button type="primary" onClick={handleSaveNamespaces}>
                保存命名空间配置
              </Button>
            </div>
          </TabPane>
        </Tabs>
      </Modal>
    </div>
  )
}

export default RoleGroupManager
