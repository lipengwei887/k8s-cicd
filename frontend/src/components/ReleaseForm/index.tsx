import React, { useState, useEffect } from 'react'
import {
  Form,
  Select,
  Button,
  Card,
  Steps,
  Alert,
  Tag,
  Descriptions,
  Progress,
  message,
  Spin,
  Checkbox,
  Input,
} from 'antd'
import { useNavigate } from 'react-router-dom'
import { clusterApi, serviceApi, releaseApi, harborApi } from '@/api'
import { useWebSocket } from '@/hooks/useWebSocket'
import type { Cluster, Namespace, Service, ReleaseProgress } from '@/types'

const { Step } = Steps
const { Option } = Select

const ReleaseForm: React.FC = () => {
  const [form] = Form.useForm()
  const navigate = useNavigate()
  const [currentStep, setCurrentStep] = useState(0)
  const [loading, setLoading] = useState(false)

  // 数据状态
  const [clusters, setClusters] = useState<Cluster[]>([])
  const [namespaces, setNamespaces] = useState<Namespace[]>([])
  const [services, setServices] = useState<Service[]>([])
  const [imageTags, setImageTags] = useState<Record<number, string[]>>({})
  const [selectedService, setSelectedService] = useState<Service | null>(null)
  const [selectedServices, setSelectedServices] = useState<Service[]>([])
  const [currentImage, setCurrentImage] = useState<string>('未知')

  // 发布状态
  const [releaseId, setReleaseId] = useState<number | null>(null)
  const [releaseProgress, setReleaseProgress] = useState<ReleaseProgress | null>(null)
  const [releaseStatus, setReleaseStatus] = useState<'idle' | 'running' | 'success' | 'failed'>('idle')

  // WebSocket 连接 - 动态构建 URL，支持相对路径和自动切换 ws/wss
  const wsUrl = releaseId ? (() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    return `${protocol}//${host}/api/v1/releases/${releaseId}/progress`
  })() : null
  const { readyState } = useWebSocket(wsUrl, {
    onMessage: (data) => {
      setReleaseProgress(data)
      if (data.status === 'completed') {
        setReleaseStatus('success')
        message.success('发布成功！')
      } else if (data.status === 'failed') {
        setReleaseStatus('failed')
        message.error(`发布失败: ${data.message}`)
      }
    },
  })

  // 初始化加载集群列表
  useEffect(() => {
    loadClusters()
  }, [])

  const loadClusters = async () => {
    try {
      const res: any = await clusterApi.getClusters()
      setClusters(res.items || [])
    } catch (error) {
      message.error('加载集群列表失败')
    }
  }

  const loadNamespaces = async (clusterId: number) => {
    try {
      const res: any = await clusterApi.getNamespaces(clusterId)
      setNamespaces(res.items || [])
      form.setFieldsValue({ namespace_id: undefined, service_id: undefined, image_tag: undefined })
    } catch (error) {
      message.error('加载命名空间失败')
    }
  }

  const loadServices = async (namespaceId: number) => {
    try {
      const res: any = await serviceApi.getServices({ namespace_id: namespaceId })
      setServices(res.items || [])
      form.setFieldsValue({ service_id: undefined, image_tag: undefined })
    } catch (error) {
      message.error('加载服务列表失败')
    }
  }

  const loadImageTags = async (serviceId: number) => {
    try {
      const service = services.find((s) => s.id === serviceId)
      if (!service) return

      setSelectedService(service)
      setCurrentImage(service.current_image || '未知')

      // 使用 Harbor API 获取镜像标签
      const res: any = await harborApi.getServiceImageTags(serviceId, 100)
      setImageTags(res.items || [])
    } catch (error) {
      message.error('加载镜像标签失败，请检查 Harbor 配置')
      console.error('Failed to load image tags:', error)
    }
  }

  const handleClusterChange = (clusterId: number) => {
    loadNamespaces(clusterId)
  }

  const handleNamespaceChange = (namespaceId: number) => {
    loadServices(namespaceId)
  }

  const handleServiceChange = async (serviceIds: number[]) => {
    const selected = services.filter(s => serviceIds.includes(s.id))
    setSelectedServices(selected)
    // 为每个选中的服务加载镜像标签
    for (const service of selected) {
      await loadImageTagsForService(service)
    }
  }

  const loadImageTagsForService = async (service: Service) => {
    try {
      const res: any = await harborApi.getServiceImageTags(service.id, 100)
      setImageTags(prev => ({ ...prev, [service.id]: res.items || [] }))
    } catch (error: any) {
      console.error(`Failed to load image tags for service ${service.id}:`, error)
      // 显示错误提示，但不阻断用户操作
      const errorMsg = error?.response?.data?.detail || '获取镜像标签失败'
      message.warning(`服务 "${service.name}": ${errorMsg}`)
      setImageTags(prev => ({ ...prev, [service.id]: [] }))
    }
  }

  // 创建发布单（支持批量创建，每个服务独立镜像版本）
  const handleCreateRelease = async (values: any) => {
    setLoading(true)
    try {
      // 从 form 获取所有字段值（包括之前步骤的字段）
      const allValues = form.getFieldsValue()
      console.log('All form values:', allValues)
      
      // 使用 selectedServices 获取服务列表（因为 service_ids 可能不在当前步骤的表单中）
      const serviceIds: number[] = selectedServices.map(s => s.id)
      
      // 从动态字段名中读取镜像版本
      const imageTags: Record<number, string> = {}
      for (const serviceId of serviceIds) {
        const tag = allValues[`image_tag_${serviceId}`]
        if (tag) {
          imageTags[serviceId] = tag
        }
      }
      
      if (serviceIds.length === 0) {
        message.error('请先选择服务')
        return
      }

      // 为每个服务创建发布单（使用各自的镜像版本）
      const releaseIds: number[] = []
      for (const serviceId of serviceIds) {
        const imageTag = imageTags[serviceId]
        if (!imageTag) {
          message.error(`请为服务 #${serviceId} 输入镜像版本`)
          return
        }
        const res: any = await releaseApi.createRelease({
          service_id: serviceId,
          image_tag: imageTag,
          require_approval: values.require_approval,
          validity_period: values.validity_period || 0,
        })
        releaseIds.push(res.id)
      }

      setReleaseId(releaseIds[0]) // 设置第一个用于WebSocket

      if (allValues.require_approval) {
        message.success(`已创建 ${serviceIds.length} 个发布单，等待审批`)
        setCurrentStep(3)
      } else {
        setCurrentStep(3)
        // 顺序执行每个发布
        for (const id of releaseIds) {
          await handleExecuteRelease(id)
        }
      }
    } catch (error) {
      message.error('创建发布单失败')
    } finally {
      setLoading(false)
    }
  }

  // 执行发布
  const handleExecuteRelease = async (id: number) => {
    setReleaseStatus('running')
    try {
      await releaseApi.executeRelease(id)
    } catch (error) {
      setReleaseStatus('failed')
      message.error('发布执行失败')
    }
  }

  // 步骤内容
  const steps = [
    {
      title: '选择环境',
      content: (
        <Form.Item
          label="选择集群"
          name="cluster_id"
          rules={[{ required: true, message: '请选择集群' }]}
        >
          <Select
            placeholder="请选择集群"
            onChange={handleClusterChange}
            style={{ width: 300 }}
          >
            {clusters.map((cluster) => (
              <Option key={cluster.id} value={cluster.id}>
                {cluster.display_name || cluster.name}
              </Option>
            ))}
          </Select>
        </Form.Item>
      ),
    },
    {
      title: '选择服务',
      content: (
        <>
          <Form.Item
            label="命名空间"
            name="namespace_id"
            rules={[{ required: true, message: '请选择命名空间' }]}
          >
            <Select
              placeholder="请选择命名空间"
              onChange={handleNamespaceChange}
              style={{ width: 300 }}
            >
              {namespaces.map((ns) => (
                <Option key={ns.id} value={ns.id}>
                  <Tag color={ns.env_type === 'prod' ? 'red' : 'blue'}>{ns.env_type}</Tag>
                  {ns.display_name || ns.name}
                </Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            label="服务（可多选）"
            name="service_ids"
            rules={[{ required: true, message: '请选择服务' }]}
          >
            <Select
              mode="multiple"
              placeholder="请选择服务"
              onChange={handleServiceChange}
              style={{ width: 400 }}
            >
              {services.map((service) => (
                <Option key={service.id} value={service.id}>
                  {service.display_name || service.name}
                </Option>
              ))}
            </Select>
          </Form.Item>
        </>
      ),
    },
    {
      title: '选择版本',
      content: (
        <>
          <Card style={{ marginBottom: 24 }}>
            <Descriptions title="已选服务" bordered size="small">
              <Descriptions.Item label="服务数量">
                <Tag color="blue">{selectedServices.length} 个服务</Tag>
              </Descriptions.Item>
            </Descriptions>
          </Card>

          {selectedServices.map((service) => {
            const tags = imageTags[service.id] || []
            const currentTag = service.current_image ? service.current_image.split(':').pop() : ''
            return (
              <Card key={service.id} style={{ marginBottom: 16 }} size="small">
                <div style={{ marginBottom: 8 }}>
                  <Tag color="blue">{service.display_name || service.name}</Tag>
                  <span style={{ color: '#999', fontSize: 12, marginLeft: 8 }}>
                    当前镜像: {service.current_image || '未知'}
                  </span>
                </div>
                <Form.Item
                  label="目标镜像版本"
                  name={`image_tag_${service.id}`}
                  rules={[{ required: true, message: `请选择 ${service.display_name || service.name} 的镜像版本` }]}
                  style={{ marginBottom: 0 }}
                >
                  <Select
                    placeholder="请选择镜像版本"
                    style={{ width: 300 }}
                    showSearch
                    optionFilterProp="children"
                    loading={tags.length === 0}
                  >
                    {tags.map((tag: string) => (
                      <Option key={tag} value={tag}>
                        {tag}
                        {tag === currentTag && (
                          <Tag color="green" style={{ marginLeft: 8 }}>当前</Tag>
                        )}
                      </Option>
                    ))}
                  </Select>
                </Form.Item>
              </Card>
            )
          })}

          <Form.Item name="require_approval" valuePropName="checked">
            <Checkbox>需要审批</Checkbox>
          </Form.Item>
          
          <Form.Item
            noStyle
            shouldUpdate={(prevValues, currentValues) => prevValues.require_approval !== currentValues.require_approval}
          >
            {({ getFieldValue }) => {
              return getFieldValue('require_approval') ? (
                <Form.Item
                  label="审批时效"
                  name="validity_period"
                  initialValue={0}
                  tooltip="审批通过后，在时效内可以免审批再次发布"
                >
                  <Select placeholder="选择时效（可选）" style={{ width: 200 }}>
                    <Option value={0}>不限制（每次都需要审批）</Option>
                    <Option value={1}>1小时</Option>
                    <Option value={2}>2小时</Option>
                    <Option value={4}>4小时</Option>
                    <Option value={8}>8小时</Option>
                    <Option value={24}>1天</Option>
                    <Option value={48}>2天</Option>
                    <Option value={72}>3天</Option>
                    <Option value={168}>7天</Option>
                  </Select>
                </Form.Item>
              ) : null
            }}
          </Form.Item>
        </>
      ),
    },
    {
      title: '执行发布',
      content: (
        <div>
          {releaseStatus === 'idle' && (
            <Alert message="准备就绪" description="点击确认开始发布" type="info" showIcon />
          )}

          {releaseStatus === 'running' && (
            <div>
              <Alert
                message="发布进行中..."
                type="warning"
                showIcon
                style={{ marginBottom: 16 }}
              />
              {releaseProgress && (
                <Card>
                  <Progress percent={Math.round(releaseProgress.progress_percent)} status="active" />
                  <Descriptions size="small" column={2}>
                    <Descriptions.Item label="期望副本">{releaseProgress.desired}</Descriptions.Item>
                    <Descriptions.Item label="已更新">{releaseProgress.updated}</Descriptions.Item>
                    <Descriptions.Item label="就绪">{releaseProgress.ready}</Descriptions.Item>
                    <Descriptions.Item label="不可用">{releaseProgress.unavailable}</Descriptions.Item>
                    <Descriptions.Item label="耗时">{releaseProgress.elapsed_seconds}s</Descriptions.Item>
                  </Descriptions>
                </Card>
              )}
              <Spin tip="正在发布，请稍候..." />
            </div>
          )}

          {releaseStatus === 'success' && (
            <Alert
              message="发布成功"
              description="服务已成功更新到目标版本"
              type="success"
              showIcon
            />
          )}

          {releaseStatus === 'failed' && (
            <Alert
              message="发布失败"
              description={releaseProgress?.message || '未知错误'}
              type="error"
              showIcon
            />
          )}
        </div>
      ),
    },
  ]

  const nextStep = async () => {
    // 验证当前步骤的表单字段
    let fieldsToValidate: string[] = []
    if (currentStep === 0) {
      fieldsToValidate = ['cluster_id']
    } else if (currentStep === 1) {
      fieldsToValidate = ['namespace_id', 'service_ids']
    } else if (currentStep === 2) {
      // 第三步验证所有服务的镜像版本
      const serviceIds = form.getFieldValue('service_ids') || []
      fieldsToValidate = serviceIds.map((id: number) => `image_tag_${id}`)
    }
    
    try {
      await form.validateFields(fieldsToValidate)
      if (currentStep < steps.length - 1) {
        setCurrentStep(currentStep + 1)
      }
    } catch (error) {
      // 验证失败，不继续
    }
  }

  const prevStep = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1)
    }
  }

  return (
    <Card title="新建发布" style={{ maxWidth: 800, margin: '0 auto' }}>
      <Steps current={currentStep} style={{ marginBottom: 24 }}>
        {steps.map((item) => (
          <Step key={item.title} title={item.title} />
        ))}
      </Steps>

      <Form
        form={form}
        layout="vertical"
        preserve={true}
        onFinish={currentStep === 2 ? handleCreateRelease : undefined}
      >
        {steps[currentStep].content}

        <Form.Item style={{ marginTop: 24 }}>
          {currentStep > 0 && (
            <Button style={{ marginRight: 8 }} onClick={prevStep}>
              上一步
            </Button>
          )}

          {currentStep < steps.length - 1 && currentStep < 2 && (
            <Button type="primary" onClick={nextStep}>
              下一步
            </Button>
          )}

          {currentStep === 2 && (
            <Button type="primary" htmlType="submit" loading={loading}>
              确认发布
            </Button>
          )}

          {currentStep === 3 && (
            <>
              {releaseStatus === 'success' && (
                <Button type="primary" onClick={() => navigate('/dashboard')}>
                  返回首页
                </Button>
              )}
              {releaseStatus !== 'success' && (
                <Button onClick={() => navigate('/dashboard')}>
                  返回
                </Button>
              )}
            </>
          )}
        </Form.Item>
      </Form>
    </Card>
  )
}

export default ReleaseForm
