import React, { useEffect, useState, useRef } from 'react'
import { Card } from 'antd'
import {
  ClusterOutlined,
  CloudServerOutlined,
  RocketOutlined,
  SyncOutlined,
} from '@ant-design/icons'
import './style.css'

interface StatCardProps {
  title: string
  value: number
  icon: 'cluster' | 'service' | 'release' | 'running'
  gradient: 'blue' | 'green' | 'purple' | 'orange'
  trend?: number // 环比变化百分比
  loading?: boolean
}

const iconMap = {
  cluster: ClusterOutlined,
  service: CloudServerOutlined,
  release: RocketOutlined,
  running: SyncOutlined,
}

const gradientMap = {
  blue: 'linear-gradient(135deg, #3B82F6 0%, #8B5CF6 100%)',
  green: 'linear-gradient(135deg, #10B981 0%, #34D399 100%)',
  purple: 'linear-gradient(135deg, #8B5CF6 0%, #EC4899 100%)',
  orange: 'linear-gradient(135deg, #F59E0B 0%, #F97316 100%)',
}

// 数字滚动动画 - 简化版
// @ts-expect-error 函数暂时未使用但保留
const useCountUp = (end: number, duration: number = 1500) => {
  const [count, setCount] = useState(end)
  const rafRef = useRef<number>()
  const startTimeRef = useRef<number>()

  useEffect(() => {
    // 清除之前的动画
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current)
    }
    
    const startValue = count
    const targetValue = end
    startTimeRef.current = performance.now()

    const animate = (currentTime: number) => {
      const elapsed = currentTime - startTimeRef.current!
      const progress = Math.min(elapsed / duration, 1)
      
      // easeOutExpo 缓动函数
      const easeProgress = 1 - Math.pow(2, -10 * progress)
      const currentValue = Math.floor(startValue + (targetValue - startValue) * easeProgress)
      
      setCount(currentValue)

      if (progress < 1) {
        rafRef.current = requestAnimationFrame(animate)
      }
    }

    rafRef.current = requestAnimationFrame(animate)

    return () => {
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current)
      }
    }
  }, [end, duration])

  return count
}

const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  icon,
  gradient,
  trend,
  loading = false,
}) => {
  const IconComponent = iconMap[icon]

  if (loading) {
    return (
      <Card className="stat-card stat-card--loading" variant="borderless">
        <div className="stat-card__skeleton">
          <div className="skeleton skeleton--icon" />
          <div className="skeleton skeleton--title" />
          <div className="skeleton skeleton--value" />
        </div>
      </Card>
    )
  }

  return (
    <Card
      className="stat-card"
      style={{ background: gradientMap[gradient] }}
      variant="borderless"
    >
      <div className="stat-card__content">
        <div className="stat-card__header">
          <div className="stat-card__icon-wrapper">
            <IconComponent className="stat-card__icon" />
          </div>
          {trend !== undefined && (
            <div className={`stat-card__trend ${trend >= 0 ? 'stat-card__trend--up' : 'stat-card__trend--down'}`}>
              {trend >= 0 ? '+' : ''}{trend}%
            </div>
          )}
        </div>
        
        <div className="stat-card__body">
          <div className="stat-card__value font-mono">{value}</div>
          <div className="stat-card__title">{title}</div>
        </div>

        {/* 装饰性背景图案 */}
        <div className="stat-card__pattern" />
      </div>
    </Card>
  )
}

export default StatCard
