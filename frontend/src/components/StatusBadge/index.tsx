import React from 'react'
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  SyncOutlined,
  PauseCircleOutlined,
  RollbackOutlined,
} from '@ant-design/icons'
import './style.css'

type StatusType = 
  | 'pending' 
  | 'approving' 
  | 'running' 
  | 'success' 
  | 'failed' 
  | 'rolled_back'

interface StatusBadgeProps {
  status: StatusType
  text?: string
  showIcon?: boolean
  pulse?: boolean
}

const statusConfig = {
  pending: {
    icon: PauseCircleOutlined,
    text: '等待中',
    className: 'status-badge--pending',
  },
  approving: {
    icon: ClockCircleOutlined,
    text: '审批中',
    className: 'status-badge--approving',
  },
  running: {
    icon: SyncOutlined,
    text: '执行中',
    className: 'status-badge--running',
  },
  success: {
    icon: CheckCircleOutlined,
    text: '成功',
    className: 'status-badge--success',
  },
  failed: {
    icon: CloseCircleOutlined,
    text: '失败',
    className: 'status-badge--failed',
  },
  rolled_back: {
    icon: RollbackOutlined,
    text: '已回滚',
    className: 'status-badge--rolled-back',
  },
}

const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  text,
  showIcon = true,
  pulse = false,
}) => {
  const config = statusConfig[status]
  const IconComponent = config.icon

  return (
    <span className={`status-badge ${config.className} ${pulse ? 'status-badge--pulse' : ''}`}>
      {showIcon && (
        <IconComponent 
          className={`status-badge__icon ${status === 'running' ? 'status-badge__icon--spin' : ''}`} 
        />
      )}
      <span className="status-badge__text">{text || config.text}</span>
      {pulse && <span className="status-badge__pulse" />}
    </span>
  )
}

export default StatusBadge
