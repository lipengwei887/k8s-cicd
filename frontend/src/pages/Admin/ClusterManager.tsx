import React, { useState, useEffect } from 'react'
import {
  Card,
  Button,
  Table,
  Modal,
  Form,
  Input,
  Upload,
  message,
  Space,
  Tag,
  Popconfirm,
  Descriptions,
} from 'antd'
import { PlusOutlined, UploadOutlined, SyncOutlined, DeleteOutlined, EyeOutlined } from '@ant-design/icons'
import type { UploadFile } from 'antd/es/upload/interface'
import { clusterApi } from '@/api'

interface Cluster {
  id: number
  name: string
  display_name: string
  api_server: string
  status: number
  description?: string
  created_at: string
}

const ClusterManager: React.FC = () => {
  const [clusters, setClusters] = useState<Cluster[]>([])
  const [loading, setLoading] = useState(false)
  const [modalVisible, setModalVisible] = useState(false)
  const [detailVisible, setDetailVisible] = useState(false)
  const [selectedCluster, setSelectedCluster] = useState<Cluster | null>(null)
  const [form] = Form.useForm()
  const [fileList, setFileList] = useState<UploadFile[]>([])

  useEffect(() => {
    loadClusters()
  }, [])

  const loadClusters = async () => {
    setLoading(true)
    try {
      const res: any = await clusterApi.getClusters()
      setClusters(res.items || [])
    } catch (error) {
      message.error('加载集群列表失败')
    } finally {
      setLoading(false)
    }
  }

  const handleUpload = async (values: any) => {
    if (fileList.length === 0) {
      message.error('请选择 kubeconfig 文件')
      return
    }

    const formData = new FormData()
    formData.append('name', values.name)
    formData.append('display_name', values.display_name)
    formData.append('description', values.description || '')
    
    // 获取文件对象
    const uploadFile = fileList[0]
    const file = uploadFile.originFileObj
    if (!file) {
      message.error('文件对象不存在，请重新选择文件')
      return
    }
    formData.append('kubeconfig_file', file, uploadFile.name)

    try {
      await clusterApi.uploadKubeconfig(formData)
      message.success('集群添加成功')
      setModalVisible(false)
      form.resetFields()
      setFileList([])
      loadClusters()
    } catch (error: any) {
      console.error('Upload error:', error.response?.data)
      message.error(error.response?.data?.detail || '添加集群失败')
    }
  }

  const handleSync = async (clusterId: number) => {
    try {
      await clusterApi.syncCluster(clusterId)
      message.success('集群同步成功')
    } catch (error: any) {
      message.error(error.response?.data?.detail || '同步失败')
    }
  }

  const handleDelete = async (clusterId: number) => {
    try {
      await clusterApi.deleteCluster(clusterId)
      message.success('集群删除成功')
      loadClusters()
    } catch (error) {
      message.error('删除失败')
    }
  }

  const showDetail = (cluster: Cluster) => {
    setSelectedCluster(cluster)
    setDetailVisible(true)
  }

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      width: 80,
    },
    {
      title: '名称',
      dataIndex: 'name',
    },
    {
      title: '显示名称',
      dataIndex: 'display_name',
    },
    {
      title: 'API Server',
      dataIndex: 'api_server',
      ellipsis: true,
    },
    {
      title: '状态',
      dataIndex: 'status',
      render: (status: number) => (
        <Tag color={status === 1 ? 'success' : 'error'}>
          {status === 1 ? '正常' : '禁用'}
        </Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: Cluster) => (
        <Space>
          <Button
            size="small"
            icon={<EyeOutlined />}
            onClick={() => showDetail(record)}
          >
            详情
          </Button>
          <Button
            size="small"
            icon={<SyncOutlined />}
            onClick={() => handleSync(record.id)}
          >
            同步
          </Button>
          <Popconfirm
            title="确定删除该集群吗？"
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

  const uploadProps = {
    onRemove: () => {
      setFileList([])
    },
    beforeUpload: (file: any) => {
      const isYaml = file.name.endsWith('.yaml') || file.name.endsWith('.yml')
      if (!isYaml) {
        message.error('请上传 YAML 格式的 kubeconfig 文件')
        return false
      }
      // 保存文件对象
      setFileList([{
        uid: file.uid || Date.now().toString(),
        name: file.name,
        status: 'done',
        originFileObj: file,
      }])
      return false
    },
    fileList,
  }

  return (
    <div>
      <Card
        title="集群管理"
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalVisible(true)}>
            添加集群
          </Button>
        }
      >
        <Table
          columns={columns}
          dataSource={clusters}
          rowKey="id"
          loading={loading}
        />
      </Card>

      {/* 添加集群弹窗 */}
      <Modal
        title="添加集群"
        open={modalVisible}
        onCancel={() => {
          setModalVisible(false)
          form.resetFields()
          setFileList([])
        }}
        onOk={() => form.submit()}
        width={600}
      >
        <Form form={form} layout="vertical" onFinish={handleUpload}>
          <Form.Item
            label="集群标识"
            name="name"
            rules={[{ required: true, message: '请输入集群标识' }]}
          >
            <Input placeholder="如: fushang" />
          </Form.Item>

          <Form.Item
            label="显示名称"
            name="display_name"
            rules={[{ required: true, message: '请输入显示名称' }]}
          >
            <Input placeholder="如: 富尚集群" />
          </Form.Item>

          <Form.Item label="描述" name="description">
            <Input.TextArea placeholder="集群描述信息" />
          </Form.Item>

          <Form.Item
            label="Kubeconfig 文件"
            required
            tooltip="上传集群的 kubeconfig 文件，系统将自动解析并同步命名空间和服务"
          >
            <Upload {...uploadProps}>
              <Button icon={<UploadOutlined />}>选择文件</Button>
            </Upload>
            <div style={{ marginTop: 8, color: '#999' }}>
              支持 .yaml 或 .yml 格式，上传后将自动同步集群信息
            </div>
          </Form.Item>
        </Form>
      </Modal>

      {/* 集群详情弹窗 */}
      <Modal
        title="集群详情"
        open={detailVisible}
        onCancel={() => setDetailVisible(false)}
        footer={null}
      >
        {selectedCluster && (
          <Descriptions column={1} bordered>
            <Descriptions.Item label="ID">{selectedCluster.id}</Descriptions.Item>
            <Descriptions.Item label="名称">{selectedCluster.name}</Descriptions.Item>
            <Descriptions.Item label="显示名称">{selectedCluster.display_name}</Descriptions.Item>
            <Descriptions.Item label="API Server">{selectedCluster.api_server}</Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={selectedCluster.status === 1 ? 'success' : 'error'}>
                {selectedCluster.status === 1 ? '正常' : '禁用'}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="描述">{selectedCluster.description || '-'}</Descriptions.Item>
            <Descriptions.Item label="创建时间">{selectedCluster.created_at}</Descriptions.Item>
          </Descriptions>
        )}
      </Modal>
    </div>
  )
}

export default ClusterManager
