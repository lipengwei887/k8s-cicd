import React, { useState } from 'react'
import { Form, Input, Button, Checkbox, message } from 'antd'
import { UserOutlined, LockOutlined, EyeOutlined, EyeInvisibleOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { authApi } from '@/api'
import { AnimatedCharacters } from '@/components/AnimatedLogin'
import { setStoredCurrentUser } from '@/utils/auth'
import './style.css'

const Login: React.FC = () => {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [isTyping, setIsTyping] = useState(false)
  const [rememberMe, setRememberMe] = useState(false)
  const [passwordValue, setPasswordValue] = useState('')
  const [form] = Form.useForm()

  const handleSubmit = async (values: { username: string; password: string }) => {
    setLoading(true)
    setError('')
    try {
      const res: any = await authApi.login(values.username, values.password)
      const token = res.access_token
      if (rememberMe) {
        // 记住我：存到 localStorage，设置 30 天过期时间戳
        const expiry = Date.now() + 30 * 24 * 60 * 60 * 1000
        localStorage.setItem('token', token)
        localStorage.setItem('tokenExpiry', String(expiry))
        sessionStorage.removeItem('token')
      } else {
        // 不记住：存到 sessionStorage，关闭浏览器即失效
        sessionStorage.setItem('token', token)
        localStorage.removeItem('token')
        localStorage.removeItem('tokenExpiry')
      }
      try {
        const me: any = await authApi.getMe()
        setStoredCurrentUser(me)
      } catch {
        if (res.user) {
          setStoredCurrentUser(res.user)
        }
      }
      message.success('登录成功')
      navigate('/dashboard')
    } catch (error) {
      setError('登录失败，请检查用户名和密码')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-page">
      {/* 左侧动画区域 */}
      <div className="login-animation-section">
        <div className="characters-wrapper">
          <AnimatedCharacters
            isTyping={isTyping}
            showPassword={showPassword}
            passwordLength={passwordValue.length}
          />
        </div>
      </div>

      {/* 右侧表单区域 */}
      <div className="login-form-section">
        <div className="login-card">
          <h1>同福 K8s 发版平台</h1>
          <p className="subtitle">欢迎回来，请登录您的账号</p>

          {error && <div className="login-error">{error}</div>}

          <Form
            form={form}
            name="login"
            onFinish={handleSubmit}
            autoComplete="off"
            className="login-form"
          >
            <Form.Item
              name="username"
              rules={[{ required: true, message: '请输入用户名' }]}
            >
              <Input
                prefix={<UserOutlined />}
                placeholder="用户名"
                size="large"
                onFocus={() => setIsTyping(true)}
                onBlur={() => setIsTyping(false)}
                onChange={() => setIsTyping(true)}
              />
            </Form.Item>

            <Form.Item
              name="password"
              rules={[{ required: true, message: '请输入密码' }]}
            >
              <Input
                prefix={<LockOutlined />}
                type={showPassword ? 'text' : 'password'}
                placeholder="密码"
                size="large"
                suffix={
                  <span
                    style={{ cursor: 'pointer', color: '#999' }}
                    onClick={() => setShowPassword(!showPassword)}
                  >
                    {showPassword ? <EyeOutlined /> : <EyeInvisibleOutlined />}
                  </span>
                }
                onFocus={() => setIsTyping(true)}
                onBlur={() => setIsTyping(false)}
                onChange={(e) => {
                  setIsTyping(true)
                  setPasswordValue(e.target.value)
                }}
              />
            </Form.Item>

            <div className="login-options">
              <Checkbox
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
              >
                记住我 30 天
              </Checkbox>
              <span className="forgot-password">忘记密码？</span>
            </div>

            <Form.Item>
              <Button
                type="primary"
                htmlType="submit"
                loading={loading}
                block
                size="large"
                className="login-button"
              >
                登 录
              </Button>
            </Form.Item>
          </Form>

          <div className="register-link">
            还没有账号？<a href="#">联系管理员</a>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Login
