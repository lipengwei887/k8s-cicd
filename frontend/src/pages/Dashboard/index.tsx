import React, { useEffect, useState } from 'react'
import { Card, Row, Col, Statistic, Button, Table, Tag, Space, Avatar, Dropdown } from 'antd'
import { PlusOutlined, ReloadOutlined, RollbackOutlined, SettingOutlined, UserOutlined, LogoutOutlined, CheckOutlined, CloseOutlined, PlayCircleOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { releaseApi, clusterApi, serviceApi, authApi, userApi } from '@/api'

const Dashboard: React.FC = () => {
  const navigate = useNavigate()
  const [stats, setStats] = useState({
    clusters: 0,
    services: 0,
    releases: 0,
    running: 0,
  })
  const [releases, setReleases] = useState<any[]>([])
  const [services, setServices] = useState<any[]>([])
  const [users, setUsers] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [currentUser, setCurrentUser] = useState<any>(null)

  useEffect(() => {
    loadCurrentUser()
  }, [])

  const loadCurrentUser = async () => {
    try {
      const res: any = await authApi.getMe()
      setCurrentUser(res)
    } catch (error) {
      console.error('获取用户信息失败', error)
    }
  }

  const handleLogout = () => {
    localStorage.removeItem('token')
    navigate('/login')
  }

  const userMenuItems = [
    ...(currentUser?.role === 'admin' ? [
      {
        key: 'admin',
        icon: <SettingOutlined />,
        label: '系统管理',
        onClick: () => navigate('/admin'),
      },
    ] : []),
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      onClick: handleLogout,
    },
  ]

  useEffect(() => {
    loadStats()
    loadReleases()
  }, [])

  const loadStats = async () => {
    try {
      const [clustersRes, servicesRes, releasesRes]: any = await Promise.all([
        clusterApi.getClusters(),
        serviceApi.getServices(),
        releaseApi.getReleases(),
      ])

      setServices(servicesRes.items || [])
      setStats({
        clusters: clustersRes.total || 0,
        services: servicesRes.total || 0,
        releases: releasesRes.total || 0,
        running: releasesRes.items?.filter((r: any) => r.status === 'running').length || 0,
      })
    } catch (error) {
      console.error('加载统计数据失败', error)
    }
  }

  const loadReleases = async () => {
    setLoading(true)
    try {
      // 分别加载，避免一个失败影响其他
      let releasesRes: any = { items: [] }
      let servicesRes: any = { items: [] }
      let usersRes: any = { items: [] }
      
      try {
        releasesRes = await releaseApi.getReleases({ limit: 1000 })
      } catch (e) {
        console.error('加载发布记录失败', e)
      }
      
      try {
        servicesRes = await serviceApi.getServices({ limit: 1000 })
      } catch (e) {
        console.error('加载服务失败', e)
      }
      
      try {
        usersRes = await userApi.getUsers({ limit: 100 })
      } catch (e) {
        console.error('加载用户失败', e)
      }
      
      console.log('Loaded services:', servicesRes.items?.length)
      console.log('Loaded releases:', releasesRes.items?.length)
      setReleases(releasesRes.items || [])
      setServices(servicesRes.items || [])
      setUsers(usersRes.items || [])
    } catch (error) {
      console.error('加载数据失败', error)
    } finally {
      setLoading(false)
    }
  }

  // 根据用户ID获取用户名
  const getUserName = (userId: number) => {
    const user = users.find((u: any) => u.id === userId)
    return user ? (user.real_name || user.username) : `用户#${userId}`
  }

  // 根据服务ID获取服务名称
  const getServiceName = (serviceId: number) => {
    console.log('Looking for service:', serviceId, 'type:', typeof serviceId)
    console.log('First service id:', services[0]?.id, 'type:', typeof services[0]?.id)
    const service = services.find((s: any) => s.id === serviceId || s.id === String(serviceId))
    return service ? (service.display_name || service.name) : `服务#${serviceId}`
  }

  const handleRollback = async (id: number) => {
    try {
      await releaseApi.rollbackRelease(id)
      loadReleases()
    } catch (error) {
      console.error('回滚失败', error)
    }
  }

  const handleApprove = async (id: number, approved: boolean) => {
    try {
      await releaseApi.approveRelease(id, { approved, comment: approved ? 'Approved' : 'Rejected' })
      loadReleases()
    } catch (error) {
      console.error('审批失败', error)
    }
  }

  const handleExecute = async (id: number) => {
    try {
      await releaseApi.executeRelease(id)
      loadReleases()
    } catch (error) {
      console.error('执行发布失败', error)
    }
  }

  const getStatusTag = (status: string) => {
    const statusMap: Record<string, { color: string; text: string }> = {
      pending: { color: 'default', text: '等待中' },
      approving: { color: 'warning', text: '审批中' },
      running: { color: 'processing', text: '发布中' },
      success: { color: 'success', text: '成功' },
      failed: { color: 'error', text: '失败' },
      rolled_back: { color: 'default', text: '已回滚' },
    }
    const { color, text } = statusMap[status] || { color: 'default', text: status }
    return <Tag color={color}>{text}</Tag>
  }

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      width: 80,
    },
    {
      title: '服务',
      dataIndex: 'service_id',
      render: (serviceId: number) => getServiceName(serviceId),
    },
    {
      title: '版本',
      dataIndex: 'version',
    },
    {
      title: '镜像标签',
      dataIndex: 'image_tag',
    },
    {
      title: '状态',
      dataIndex: 'status',
      render: (status: string) => getStatusTag(status),
    },
    {
      title: '发布人员',
      dataIndex: 'operator_id',
      render: (operatorId: number) => getUserName(operatorId),
    },
    {
      title: '发布时间',
      dataIndex: 'created_at',
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: any) => (
        <Space>
          {record.status === 'approving' && currentUser?.role === 'admin' && (
            <>
              <Button
                size="small"
                type="primary"
                icon={<CheckOutlined />}
                onClick={() => handleApprove(record.id, true)}
              >
                通过
              </Button>
              <Button
                size="small"
                danger
                icon={<CloseOutlined />}
                onClick={() => handleApprove(record.id, false)}
              >
                拒绝
              </Button>
            </>
          )}
          {record.status === 'pending' && (
            <Button
              size="small"
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={() => handleExecute(record.id)}
            >
              执行发布
            </Button>
          )}
          {record.status === 'success' && (
            <Button
              size="small"
              icon={<RollbackOutlined />}
              onClick={() => handleRollback(record.id)}
            >
              回滚
            </Button>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div style={{ padding: '24px' }}>
      {/* 顶部导航栏 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h1 style={{ margin: 0 }}>K8s 发版平台</h1>
        <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
          <Space style={{ cursor: 'pointer' }}>
            <Avatar icon={<UserOutlined />} />
            <span>{currentUser?.username || '用户'}</span>
          </Space>
        </Dropdown>
      </div>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic title="集群数量" value={stats.clusters} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="服务数量" value={stats.services} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="发布总数" value={stats.releases} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="进行中" value={stats.running} valueStyle={{ color: '#1890ff' }} />
          </Card>
        </Col>
      </Row>

      <Card
        title="最近发布记录"
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={loadReleases}>
              刷新
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/release/new')}>
              新建发布
            </Button>
          </Space>
        }
      >
        <Table
          columns={columns}
          dataSource={releases}
          rowKey="id"
          loading={loading}
          pagination={{
            pageSize: 10,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 条记录`,
          }}
        />
      </Card>
    </div>
  )
}

export default Dashboard
