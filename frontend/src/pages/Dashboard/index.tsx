import React, { useEffect, useState } from 'react'
import { Card, Row, Col, Button, Table, Space, Avatar, Dropdown, Tag, message, Modal, Descriptions, Progress, Alert, Badge } from 'antd'
import { PlusOutlined, ReloadOutlined, SettingOutlined, UserOutlined, LogoutOutlined, CheckOutlined, CloseOutlined, PlayCircleOutlined, RollbackOutlined, EyeOutlined, FileTextOutlined, CheckCircleOutlined, CloseCircleOutlined, SyncOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { releaseApi, clusterApi, serviceApi, authApi, userApi, harborApi } from '@/api'
import StatCard from '@/components/StatCard'
import StatusBadge from '@/components/StatusBadge'
import useWebSocket from '@/hooks/useWebSocket'
import '@/styles/design-system.css'

const Dashboard: React.FC = () => {
  const navigate = useNavigate()
  const [stats, setStats] = useState({
    clusters: 0,
    services: 0,
    releases: 0,
    running: 0,
  })
  const [releases, setReleases] = useState<any[]>([])
  const [users, setUsers] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 10,
    total: 0,
  })
  const [currentUser, setCurrentUser] = useState<any>(null)
  const [detailModalVisible, setDetailModalVisible] = useState(false)
  const [selectedRelease, setSelectedRelease] = useState<any>(null)
  const [releaseProgress, setReleaseProgress] = useState<any>(null)
  
  // 再次发布弹窗状态
  const [reexecuteModalVisible, setReexecuteModalVisible] = useState(false)
  const [reexecuteRecord, setReexecuteRecord] = useState<any>(null)
  const [reexecuteImageTag, setReexecuteImageTag] = useState('')
  const [availableTags, setAvailableTags] = useState<string[]>([])
  const [tagsLoading, setTagsLoading] = useState(false)

  // WebSocket 连接 - 用于实时监听发布进度
  const wsUrl = selectedRelease?.id ? (() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    return `${protocol}//${host}/api/v1/releases/${selectedRelease.id}/progress`
  })() : null
  
  // 使用 ref 来跟踪是否已经显示过完成/失败消息，避免重复弹窗
  const completedRef = React.useRef(false)
  
  // 当 selectedRelease 变化时重置完成标记
  useEffect(() => {
    completedRef.current = false
  }, [selectedRelease?.id])
  
  const { close: closeWebSocket } = useWebSocket(wsUrl, {
    onConnect: () => {
      console.log('[Dashboard] WebSocket connected for release:', selectedRelease?.id)
    },
    onDisconnect: () => {
      console.log('[Dashboard] WebSocket disconnected for release:', selectedRelease?.id)
    },
    onMessage: (data) => {
      console.log('[Dashboard] WebSocket message received:', {
        status: data.status,
        pods: data.pods?.map((p: any) => ({ name: p.name, status: p.status, ready: p.ready })),
        progress_percent: data.progress_percent,
        elapsed: data.elapsed_seconds
      })
      setReleaseProgress(data)
      
      // 只有第一次收到完成/失败消息时才弹窗并关闭 WebSocket
      if (!completedRef.current) {
        if (data.status === 'completed') {
          completedRef.current = true
          message.success('发布成功！')
          // 更新 selectedRelease 状态为成功
          setSelectedRelease((prev: any) => prev ? { ...prev, status: 'success' } : prev)
          loadReleases(pagination.current, pagination.pageSize)
          // 发布成功后关闭 WebSocket 连接
          closeWebSocket()
        } else if (data.status === 'failed') {
          completedRef.current = true
          message.error(`发布失败: ${data.message}`)
          // 更新 selectedRelease 状态为失败
          setSelectedRelease((prev: any) => prev ? { ...prev, status: 'failed' } : prev)
          loadReleases(pagination.current, pagination.pageSize)
          // 发布失败后关闭 WebSocket 连接
          closeWebSocket()
        }
      }
    },
  })

  useEffect(() => {
    loadCurrentUser()
  }, [])

  const handleViewDetail = (record: any) => {
    setSelectedRelease(record)
    setDetailModalVisible(true)
  }

  const handleCloseDetail = () => {
    setDetailModalVisible(false)
    setSelectedRelease(null)
  }

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
    loadReleases(1, 10) // 初始加载第一页
  }, [])

  // 监听页面可见性变化，当从其他页面返回时刷新数据
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        loadStats()
        loadReleases(pagination.current, pagination.pageSize)
      }
    }
    document.addEventListener('visibilitychange', handleVisibilityChange)
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange)
  }, [pagination.current, pagination.pageSize])

  const loadStats = async () => {
    try {
      // 使用高性能统计接口，避免加载大量数据
      const [statsRes, releasesRes]: any = await Promise.all([
        clusterApi.getStatsSummary(),
        releaseApi.getReleases(),
      ])
      
      setStats({
        clusters: statsRes.clusters || 0,
        services: statsRes.services || 0,
        releases: releasesRes.total || 0,
        running: releasesRes.items?.filter((r: any) => r.status === 'running').length || 0,
      })
    } catch (error) {
      console.error('加载统计数据失败', error)
    }
  }

  // 服务名称缓存，避免重复请求
  const [serviceNamesMap, setServiceNamesMap] = useState<Record<number, { name: string; display_name: string }>>({})

  // 加载发布记录（支持分页）
  const loadReleases = async (page = 1, pageSize = 10) => {
    setLoading(true)
    try {
      // 分别加载，避免一个失败影响其他
      let releasesRes: any = { items: [], total: 0 }
      let usersRes: any = { items: [] }
      
      try {
        // 后端分页：只加载当前页数据
        const skip = (page - 1) * pageSize
        releasesRes = await releaseApi.getReleases({ skip, limit: pageSize })
      } catch (e) {
        console.error('加载发布记录失败', e)
      }
      
      try {
        usersRes = await userApi.getUsers({ limit: 100 })
      } catch (e) {
        console.error('加载用户失败', e)
      }
      
      // 收集需要查询的服务ID
      const serviceIds: number[] = []
      releasesRes.items?.forEach((release: any) => {
        if (release.service_id && !serviceNamesMap[release.service_id]) {
          serviceIds.push(release.service_id)
        }
      })
      
      // 批量获取服务名称（只获取需要的）
      if (serviceIds.length > 0) {
        try {
          const namesMap = await serviceApi.getServiceNamesBatch(serviceIds)
          setServiceNamesMap(prev => ({ ...prev, ...namesMap }))
        } catch (e) {
          console.error('批量获取服务名称失败', e)
        }
      }
      
      setReleases(releasesRes.items || [])
      setUsers(usersRes.items || [])
      setPagination({
        current: page,
        pageSize: pageSize,
        total: releasesRes.total || 0,
      })
    } catch (error) {
      console.error('加载数据失败', error)
    } finally {
      setLoading(false)
    }
  }

  // 处理分页变化
  const handleTableChange = (newPagination: any) => {
    loadReleases(newPagination.current, newPagination.pageSize)
  }

  // 根据用户ID获取用户名
  const getUserName = (userId: number) => {
    const user = users.find((u: any) => u.id === userId)
    return user ? (user.real_name || user.username) : `用户#${userId}`
  }

  // 根据服务ID获取服务名称（使用缓存）
  const getServiceName = (serviceId: number) => {
    const service = serviceNamesMap[serviceId]
    return service ? (service.display_name || service.name) : `服务#${serviceId}`
  }

  const handleRollback = async (id: number) => {
    try {
      await releaseApi.rollbackRelease(id)
      loadReleases(pagination.current, pagination.pageSize)
    } catch (error) {
      console.error('回滚失败', error)
    }
  }

  const handleApprove = async (record: any, approved: boolean) => {
    try {
      await releaseApi.approveRelease(record.id, { approved, comment: approved ? 'Approved' : 'Rejected' })
      if (approved) {
        message.success('审批通过，正在打开发布进度...')
        // 打开详情弹窗并启动 WebSocket 监听进度
        setSelectedRelease(record)
        setReleaseProgress(null)
        setDetailModalVisible(true)
      }
      loadReleases(pagination.current, pagination.pageSize)
    } catch (error) {
      console.error('审批失败', error)
      message.error('审批失败')
    }
  }

  // 打开再次发布弹窗
  const openReexecuteModal = async (record: any) => {
    try {
      // 先检查时效状态
      const validityRes: any = await releaseApi.checkReleaseValidity(record.id)
      if (!validityRes.can_reexecute) {
        message.error('该发布单已过期或您没有权限重新执行')
        return
      }
      
      setReexecuteRecord(record)
      setReexecuteImageTag(record.image_tag)
      setReexecuteModalVisible(true)
      
      // 加载可用的镜像标签
      loadServiceTags(record.service_id)
    } catch (error) {
      console.error('检查时效失败', error)
      message.error('检查时效失败')
    }
  }
  
  // 加载服务的镜像标签
  const loadServiceTags = async (serviceId: number) => {
    setTagsLoading(true)
    try {
      const res: any = await harborApi.getServiceImageTags(serviceId, 100)
      if (res.items && Array.isArray(res.items)) {
        setAvailableTags(res.items)
      } else if (res.tags && Array.isArray(res.tags)) {
        setAvailableTags(res.tags)
      }
    } catch (error) {
      console.error('加载镜像标签失败', error)
    } finally {
      setTagsLoading(false)
    }
  }
  
  // 关闭再次发布弹窗
  const closeReexecuteModal = () => {
    setReexecuteModalVisible(false)
    setReexecuteRecord(null)
    setReexecuteImageTag('')
    setAvailableTags([])
  }
  
  // 执行再次发布
  const handleReexecute = async () => {
    if (!reexecuteRecord || !reexecuteImageTag) return
    
    try {
      await releaseApi.reexecuteRelease(reexecuteRecord.id, {
        service_id: reexecuteRecord.service_id,
        image_tag: reexecuteImageTag,
      })
      
      message.success('已创建新的发布单（免审批）')
      closeReexecuteModal()
      loadReleases(pagination.current, pagination.pageSize)
    } catch (error) {
      console.error('重新执行失败', error)
      message.error('重新执行失败')
    }
  }

  const handleExecute = async (record: any) => {
    try {
      await releaseApi.executeRelease(record.id)
      message.success('发布已开始，正在打开详情查看进度...')
      // 打开详情弹窗并启动 WebSocket 监听进度
      setSelectedRelease(record)
      setReleaseProgress(null)
      setDetailModalVisible(true)
    } catch (error) {
      console.error('执行发布失败', error)
      message.error('执行发布失败')
    }
  }

  const getStatusBadge = (status: string) => {
    const statusMap: Record<string, any> = {
      pending: { status: 'pending', pulse: false },
      approving: { status: 'approving', pulse: true },
      running: { status: 'running', pulse: true },
      success: { status: 'success', pulse: false },
      failed: { status: 'failed', pulse: false },
      rolled_back: { status: 'rolled_back', pulse: false },
    }
    const config = statusMap[status] || { status: 'pending', pulse: false }
    return <StatusBadge status={config.status} pulse={config.pulse} />
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
      title: '镜像标签',
      dataIndex: 'image_tag',
    },
    {
      title: '状态',
      dataIndex: 'status',
      render: (status: string, record: any) => (
        <Space direction="vertical" size={0}>
          {getStatusBadge(status)}
          {/* 显示时效信息 */}
          {record.validity_period > 0 && record.status === 'approving' && (
            <Tag color="blue" style={{ fontSize: '11px' }}>
              时效: {record.validity_period}小时
            </Tag>
          )}
          {record.validity_period > 0 && record.validity_end_at && (
            <Tag 
              color={new Date(record.validity_end_at + 'Z') > new Date() ? 'green' : 'red'}
              style={{ fontSize: '11px' }}
            >
              {new Date(record.validity_end_at + 'Z') > new Date() ? '时效内' : '已过期'}
            </Tag>
          )}
          {record.is_repeated === 1 && (
            <Tag color="orange" style={{ fontSize: '11px' }}>
              重复执行
            </Tag>
          )}
        </Space>
      ),
    },
    {
      title: '发布人员',
      dataIndex: 'operator_id',
      render: (operatorId: number) => getUserName(operatorId),
    },
    {
      title: '发布时间',
      dataIndex: 'created_at',
      render: (created_at: string) => {
        if (!created_at) return '-'
        // 将 UTC 时间转换为本地时间显示
        const date = new Date(created_at + 'Z')
        return date.toLocaleString('zh-CN', {
          year: 'numeric',
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: false
        })
      }
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
                onClick={() => handleApprove(record, true)}
              >
                通过
              </Button>
              <Button
                size="small"
                danger
                icon={<CloseOutlined />}
                onClick={() => handleApprove(record, false)}
              >
                拒绝
              </Button>
            </>
          )}
          {record.status === 'pending' && (currentUser?.is_superuser || currentUser?.permissions?.includes('release:execute')) && (
            <Button
              size="small"
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={() => handleExecute(record)}
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
          {/* 时效内重新执行按钮 - 适用于成功状态且可以免审批执行的发布记录 */}
          {record.status === 'success' && record.can_execute_without_approval && (
            <Button
              size="small"
              type="primary"
              ghost
              icon={<ReloadOutlined />}
              onClick={() => openReexecuteModal(record)}
            >
              再次发布
            </Button>
          )}
          {/* 查看详情按钮 */}
          <Button
            size="small"
            icon={<EyeOutlined />}
            onClick={() => handleViewDetail(record)}
          >
            详情
          </Button>
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

      {/* Debug: stats.clusters = {stats.clusters} */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} lg={6}>
          <StatCard
            title="集群数量"
            value={stats.clusters}
            icon="cluster"
            gradient="blue"
            trend={5.2}
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <StatCard
            title="服务数量"
            value={stats.services}
            icon="service"
            gradient="green"
            trend={12.8}
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <StatCard
            title="发布总数"
            value={stats.releases}
            icon="release"
            gradient="purple"
            trend={-2.4}
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <StatCard
            title="进行中"
            value={stats.running}
            icon="running"
            gradient="orange"
          />
        </Col>
      </Row>

      <Card
        title="最近发布记录"
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={() => loadReleases(pagination.current, pagination.pageSize)}>
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
            current: pagination.current,
            pageSize: pagination.pageSize,
            total: pagination.total,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 条记录`,
            onChange: (page, pageSize) => handleTableChange({ current: page, pageSize }),
          }}
        />
      </Card>

      {/* 发布详情弹窗 */}
      <Modal
        title="发布详情"
        open={detailModalVisible}
        onCancel={handleCloseDetail}
        footer={[
          <Button key="close" onClick={handleCloseDetail}>
            关闭
          </Button>
        ]}
        width={860}
      >
        {selectedRelease && (() => {
          // 计算当前要展示的 Pod 列表
          // 优先使用 WebSocket 实时进度中的 pods，其次是数据库存的 pod_status
          let displayPods: any[] = []
          if (releaseProgress?.pods?.length > 0) {
            displayPods = releaseProgress.pods
          } else if (selectedRelease.pod_status) {
            try {
              const ps = typeof selectedRelease.pod_status === 'string'
                ? JSON.parse(selectedRelease.pod_status)
                : selectedRelease.pod_status
              // pod_status 可能是进度对象 {pods: [...]} 或直接是数组
              displayPods = ps?.pods || (Array.isArray(ps) ? ps : [])
            } catch {}
          }

          // 当前展示的 message
          const displayMsg = releaseProgress?.message || selectedRelease.message || ''

          // 当前状态：优先以 WebSocket 实时状态为准
          const currentStatus = releaseProgress?.status
            ? (releaseProgress.status === 'completed' ? 'success' : releaseProgress.status)
            : selectedRelease.status

          // 计算实际进度：基于已 Running Pod 数 / 期望副本数
          // 而不是直接用 ready_replicas，避免 Pods 未完全 Running 时就显示 100%
          const desiredCount = releaseProgress?.desired || 0
          const runningCount = displayPods.filter(
            (p: any) => p.status === 'Running' && p.ready === true
          ).length
          const progressPercent = desiredCount > 0
            ? Math.round((runningCount / desiredCount) * 100)
            : 0

          // Pod 表格列定义
          const podColumns = [
            { title: 'Pod 名称', dataIndex: 'name', key: 'name', ellipsis: true },
            { title: 'Pod IP', dataIndex: 'pod_ip', key: 'pod_ip', width: 120, render: (ip: string) => ip || '-' },
            {
              title: '状态', dataIndex: 'status', key: 'status',
              render: (s: string) => {
                if (s === 'Running') return <Tag color="success"><CheckCircleOutlined /> Running</Tag>
                if (s === 'Pending') return <Tag color="processing"><SyncOutlined spin /> Pending</Tag>
                if (['CrashLoopBackOff','Error','OOMKilled','ErrImagePull','ImagePullBackOff'].includes(s))
                  return <Tag color="error"><CloseCircleOutlined /> {s}</Tag>
                return <Tag>{s || '-'}</Tag>
              }
            },
            {
              title: 'Ready', dataIndex: 'ready', key: 'ready',
              render: (r: any) => {
                // r 可能是 boolean 或字符串如 "1/1"
                const isReady = r === true || r === 'true' || (typeof r === 'string' && r.includes('/') && r.split('/')[0] === r.split('/')[1] && r.split('/')[0] !== '0')
                return isReady
                  ? <Badge status="success" text="就绪" />
                  : <Badge status="default" text="未就绪" />
              }
            },
            { title: '重启次数', dataIndex: 'restarts', key: 'restarts', width: 80 },
          ]
      
          return (
            <div>
              {/* 基本信息 */}
              <Descriptions bordered column={2} size="small" style={{ marginBottom: 16 }}>
                <Descriptions.Item label="发布ID">{selectedRelease.id}</Descriptions.Item>
                <Descriptions.Item label="服务">{getServiceName(selectedRelease.service_id)}</Descriptions.Item>
                <Descriptions.Item label="镜像标签">{selectedRelease.image_tag}</Descriptions.Item>
                <Descriptions.Item label="状态">
                  <Tag color={
                    currentStatus === 'success' ? 'success' :
                    currentStatus === 'failed' ? 'error' :
                    currentStatus === 'running' || currentStatus === 'updating' ? 'processing' :
                    currentStatus === 'pending' ? 'warning' : 'default'
                  }>
                    {currentStatus === 'success' ? '成功' :
                     currentStatus === 'failed' ? '失败' :
                     currentStatus === 'running' || currentStatus === 'updating' ? '发布中...' :
                     currentStatus === 'completed' ? '成功' :
                     currentStatus || '-'}
                  </Tag>
                </Descriptions.Item>
                <Descriptions.Item label="发布策略">{selectedRelease.strategy}</Descriptions.Item>
                <Descriptions.Item label="创建时间">
                  {selectedRelease.created_at ? new Date(selectedRelease.created_at + 'Z').toLocaleString('zh-CN') : '-'}
                </Descriptions.Item>
                {selectedRelease.completed_at && (
                  <Descriptions.Item label="完成时间">
                    {new Date(selectedRelease.completed_at + 'Z').toLocaleString('zh-CN')}
                  </Descriptions.Item>
                )}
              </Descriptions>
      
              {/* 进行中：进度条 */}
              {(currentStatus === 'running' || currentStatus === 'updating') && (
                <Card size="small" style={{ marginBottom: 16, background: '#f0f5ff', border: '1px solid #adc6ff' }}>
                  <Space>
                    <SyncOutlined spin style={{ color: '#1677ff' }} />
                    <span style={{ color: '#1677ff', fontWeight: 500 }}>正在发布，请稿候...</span>
                    {releaseProgress?.elapsed_seconds != null && (
                      <span style={{ color: '#666' }}>已耗时 {releaseProgress.elapsed_seconds}s</span>
                    )}
                  </Space>
                  {releaseProgress && desiredCount > 0 && (
                    <Progress
                      percent={progressPercent}
                      size="small"
                      status={progressPercent < 100 ? 'active' : 'success'}
                      format={_p => `${runningCount}/${desiredCount} Running`}
                      style={{ marginTop: 8 }}
                    />
                  )}
                </Card>
              )}
      
              {/* 成功 */}
              {(currentStatus === 'success' || currentStatus === 'completed') && (
                <Alert
                  type="success"
                  icon={<CheckCircleOutlined />}
                  showIcon
                  message="发布成功"
                  description="所有 Pod 均已处于 Running 状态"
                  style={{ marginBottom: 16 }}
                />
              )}
      
              {/* 失败：展示失败原因 */}
              {currentStatus === 'failed' && displayMsg && (
                <Alert
                  type="error"
                  icon={<CloseCircleOutlined />}
                  showIcon
                  message="发布失败 - 失败原因"
                  description={
                    <pre style={{ margin: 0, whiteSpace: 'pre-wrap', fontSize: 12, fontFamily: 'monospace', maxHeight: 200, overflow: 'auto' }}>
                      {displayMsg}
                    </pre>
                  }
                  style={{ marginBottom: 16 }}
                />
              )}
      
              {/* Pod 状态列表 - 只在发布进行中或失败时显示，成功时隐藏 */}
              {displayPods.length > 0 && (currentStatus === 'running' || currentStatus === 'updating' || currentStatus === 'failed') && (
                <div style={{ marginBottom: 16 }}>
                  <h4 style={{ margin: '0 0 8px' }}>Pod 实时状态</h4>
                  <Table
                    dataSource={displayPods}
                    columns={podColumns}
                    rowKey="name"
                    size="small"
                    pagination={false}
                    bordered
                  />
                </div>
              )}
      
              {/* 成功无进度时，展示消息 */}
              {!releaseProgress && selectedRelease.message && currentStatus !== 'failed' && (
                <div style={{ marginBottom: 16 }}>
                  <Alert
                    type="info"
                    showIcon
                    message={selectedRelease.message}
                  />
                </div>
              )}
      
              {/* Pod 日志 */}
              {selectedRelease.logs && (
                <div>
                  <h4 style={{ margin: '0 0 8px' }}><FileTextOutlined /> Pod 日志</h4>
                  <pre style={{
                    background: '#1e1e1e',
                    color: '#d4d4d4',
                    padding: 12,
                    borderRadius: 4,
                    maxHeight: 300,
                    overflow: 'auto',
                    fontSize: 12,
                    fontFamily: 'monospace'
                  }}>
                    {selectedRelease.logs}
                  </pre>
                </div>
              )}
            </div>
          )
        })()}
      </Modal>

      {/* 再次发布弹窗 */}
      <Modal
        title="再次发布"
        open={reexecuteModalVisible}
        onCancel={closeReexecuteModal}
        onOk={handleReexecute}
        okText="发布"
        cancelText="取消"
        confirmLoading={tagsLoading}
      >
        {reexecuteRecord && (
          <div style={{ padding: '16px 0' }}>
            <p><strong>服务:</strong> {getServiceName(reexecuteRecord.service_id)}</p>
            <p><strong>原镜像标签:</strong> {reexecuteRecord.image_tag}</p>
            
            <div style={{ marginTop: 16 }}>
              <label style={{ display: 'block', marginBottom: 8, fontWeight: 500 }}>
                选择镜像标签:
              </label>
              <select
                value={reexecuteImageTag}
                onChange={(e) => setReexecuteImageTag(e.target.value)}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  borderRadius: 4,
                  border: '1px solid #d9d9d9',
                  fontSize: 14
                }}
              >
                <option value="">请选择镜像标签</option>
                {availableTags.map((tag) => (
                  <option key={tag} value={tag}>
                    {tag}
                  </option>
                ))}
              </select>
              {tagsLoading && (
                <p style={{ color: '#999', fontSize: 12, marginTop: 8 }}>
                  加载中...
                </p>
              )}
              {availableTags.length === 0 && !tagsLoading && (
                <p style={{ color: '#999', fontSize: 12, marginTop: 8 }}>
                  暂无可用标签，可手动输入
                </p>
              )}
            </div>
            
            <div style={{ marginTop: 16 }}>
              <label style={{ display: 'block', marginBottom: 8, fontWeight: 500 }}>
                或手动输入:
              </label>
              <input
                type="text"
                value={reexecuteImageTag}
                onChange={(e) => setReexecuteImageTag(e.target.value)}
                placeholder="输入镜像标签"
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  borderRadius: 4,
                  border: '1px solid #d9d9d9',
                  fontSize: 14
                }}
              />
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}

export default Dashboard
