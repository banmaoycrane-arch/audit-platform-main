import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Form, Input, Button, Tabs, message, Alert } from 'antd'
import { UserOutlined, LockOutlined, MobileOutlined, SafetyOutlined } from '@ant-design/icons'
import { api } from '../../api/client'
import { useAuthStore } from '../../stores/authStore'
import { resolvePostLoginPath } from '../../utils/navigation'
import { SetPasswordModal } from './SetPasswordModal'

export function LoginPage() {
  const navigate = useNavigate()
  const { setToken, setUser, setUserLedgers, setCurrentLedger } = useAuthStore()
  const [activeTab, setActiveTab] = useState<'password' | 'sms'>('password')
  const [passwordLoading, setPasswordLoading] = useState(false)
  const [smsLoginLoading, setSmsLoginLoading] = useState(false)
  const [smsLoading, setSmsLoading] = useState(false)
  const [smsCountdown, setSmsCountdown] = useState(0)
  const [form] = Form.useForm()
  const [passwordError, setPasswordError] = useState<string | null>(null)
  const [smsLoginError, setSmsLoginError] = useState<string | null>(null)
  const [showSetPassword, setShowSetPassword] = useState(false)
  const [pendingToken, setPendingToken] = useState<string | null>(null)

  const finishLogin = async (accessToken: string, needsPasswordSetup: boolean = false) => {
    localStorage.setItem('token', accessToken)
    try {
      const context = await api.getAuthContext()
      setToken(accessToken)
      setUser({
        id: context.user.id,
        username: context.user.username || '',
        phone: context.user.phone || '',
      })
      setUserLedgers(context.ledgers)
      setCurrentLedger(context.current_ledger_id)

      // 如果需要设置密码，弹出设置密码弹窗
      if (needsPasswordSetup) {
        setPendingToken(accessToken)
        setShowSetPassword(true)
        return
      }

      message.success('登录成功')
      navigate(resolvePostLoginPath(context), { replace: true })
    } catch (error) {
      localStorage.removeItem('token')
      throw error
    }
  }

  const handlePasswordLogin = async (values: { username: string; password: string }) => {
    setPasswordError(null)
    try {
      setPasswordLoading(true)
      const res = await api.loginPassword(values.username, values.password)
      await finishLogin(res.access_token)
    } catch (e: any) {
      const msg = e.message || '账号密码登录失败，请检查用户名和密码'
      setPasswordError(msg)
      if (msg.includes('尚未设置密码')) {
        setPasswordError('该账号尚未设置密码，请先使用【验证码登录】或【立即注册】')
      } else if (msg.includes('账号不存在')) {
        setPasswordError('账号不存在，请先【立即注册】或使用【验证码登录】')
      } else if (msg.includes('密码错误')) {
        setPasswordError('密码错误，请重新输入或点击"忘记密码？"重置')
      }
    } finally {
      setPasswordLoading(false)
    }
  }

  const handleSmsLogin = async (values: { phone: string; code: string }) => {
    setSmsLoginError(null)
    try {
      setSmsLoginLoading(true)
      const res = await api.loginSms(values.phone, values.code)
      // 验证码登录后，检查是否需要设置密码
      // 如果用户名为空，说明是通过手机号注册的，需要设置密码
      await finishLogin(res.access_token, true)
    } catch (e: any) {
      const errorMsg = e.message || '验证码登录失败'
      // 根据错误消息类型显示友好的错误提示
      let friendlyMsg = errorMsg
      if (errorMsg.includes('验证码') || errorMsg.includes('code') || errorMsg.includes('Code')) {
        friendlyMsg = '验证码错误，请重新输入'
      } else if (errorMsg.includes('手机号') || errorMsg.includes('phone')) {
        friendlyMsg = '手机号不存在，请检查或使用其他方式登录'
      } else if (errorMsg.includes('过期') || errorMsg.includes('expired')) {
        friendlyMsg = '验证码已过期，请重新获取'
      }
      setSmsLoginError(friendlyMsg)
      // 保留手机号，清空验证码字段，让用户只需重新输入验证码
      form.setFieldsValue({ code: '' })
    } finally {
      setSmsLoginLoading(false)
    }
  }

  const handleSetPasswordSuccess = () => {
    setShowSetPassword(false)
    // 不在这里 navigate，而是等待 afterClose 回调
  }

  const handleSetPasswordSkip = () => {
    setShowSetPassword(false)
    // 不在这里 navigate，而是等待 afterClose 回调
  }

  const handleModalAfterClose = () => {
    message.success('登录成功')
    api.getAuthContext().then((context) => {
      navigate(resolvePostLoginPath(context), { replace: true })
    }).catch(() => navigate('/workspace', { replace: true }))
  }

  const sendSmsCode = async () => {
    const phone = form.getFieldValue('phone')
    if (!phone) {
      message.warning('请输入手机号')
      return
    }
    try {
      setSmsLoading(true)
      const res = await api.getSmsCode(phone)
      const smsCode = res.code || res.sms_code
      message.success(smsCode ? `验证码已发送: ${smsCode}` : res.message || '验证码已发送')
      setSmsCountdown(60)
      const timer = setInterval(() => {
        setSmsCountdown((c) => {
          if (c <= 1) {
            clearInterval(timer)
            return 0
          }
          return c - 1
        })
      }, 1000)
    } catch (e: any) {
      message.error(e.message || '获取验证码失败')
    } finally {
      setSmsLoading(false)
    }
  }

  const tabItems = [
    {
      key: 'password',
      label: '账号密码登录',
      children: (
        <Form onFinish={handlePasswordLogin} layout="vertical">
          {passwordError && (
            <Alert
              type="error"
              title={passwordError}
              showIcon
              style={{ marginBottom: 16 }}
              closable
              onClose={() => setPasswordError(null)}
            />
          )}
          <Form.Item name="username" rules={[{ required: true, message: '请输入用户名或手机号' }]}> 
            <Input prefix={<UserOutlined />} placeholder="用户名或手机号" size="large" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: '请输入密码' }]}> 
            <Input.Password prefix={<LockOutlined />} placeholder="密码" size="large" />
          </Form.Item>
          <Form.Item style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Link to="/forgot-password" style={{ fontSize: 12 }}>忘记密码？</Link>
              <Button type="link" size="small" onClick={() => { setActiveTab('sms'); setPasswordError(null) }}>
                使用验证码登录
              </Button>
            </div>
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block size="large" loading={passwordLoading}>
              登录
            </Button>
          </Form.Item>
        </Form>
      ),
    },
    {
      key: 'sms',
      label: '验证码登录',
      children: (
        <Form form={form} onFinish={handleSmsLogin} layout="vertical">
          {smsLoginError && (
            <Alert
              type="error"
              title={smsLoginError}
              description="请检查验证码后重新输入，或重新获取验证码"
              showIcon
              style={{ marginBottom: 16 }}
              closable
              onClose={() => setSmsLoginError(null)}
            />
          )}
          <Alert
            title="开发环境会显示本次随机验证码"
            description="点击获取验证码后，页面提示中会显示本次验证码。"
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
          />
          <Form.Item name="phone" rules={[{ required: true, message: '请输入手机号' }]}> 
            <Input prefix={<MobileOutlined />} placeholder="手机号" size="large" />
          </Form.Item>
          <Form.Item name="code" rules={[{ required: true, message: '请输入验证码' }]}> 
            <Input
              prefix={<SafetyOutlined />}
              placeholder="验证码"
              size="large"
              suffix={
                <Button
                  type="link"
                  loading={smsLoading}
                  disabled={smsCountdown > 0}
                  onClick={sendSmsCode}
                >
                  {smsCountdown > 0 ? `${smsCountdown}s` : '获取验证码'}
                </Button>
              }
            />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block size="large" loading={smsLoginLoading}>
              登录
            </Button>
          </Form.Item>
        </Form>
      ),
    },
  ]

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f5f5f5' }}>
      <div style={{ width: 400, padding: 40, background: '#fff', borderRadius: 8, boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}>
        <h2 style={{ textAlign: 'center', marginBottom: 24, fontWeight: 600 }}>财务向量审计系统</h2>
        <Tabs activeKey={activeTab} onChange={(k) => { setActiveTab(k as 'password' | 'sms'); setSmsLoginError(null); setPasswordError(null) }} centered items={tabItems} />
        <div style={{ textAlign: 'center', marginTop: 16 }}>
          <span>还没有账号？</span>
          <Link to="/register" style={{ marginLeft: 4 }}>立即注册</Link>
        </div>
      </div>
      <SetPasswordModal
        open={showSetPassword}
        onClose={handleSetPasswordSkip}
        onSuccess={handleSetPasswordSuccess}
        afterClose={handleModalAfterClose}
      />
    </div>
  )
}
