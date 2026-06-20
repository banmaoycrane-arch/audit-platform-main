import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Form, Input, Button, message } from 'antd'
import { MobileOutlined, LockOutlined, SafetyOutlined } from '@ant-design/icons'
import { api } from '../../api/client'

export function ForgotPasswordPage() {
  const navigate = useNavigate()
  const [step, setStep] = useState<'verify' | 'setPassword'>(
    'verify'
  )
  const [phone, setPhone] = useState('')
  const [smsLoading, setSmsLoading] = useState(false)
  const [smsCountdown, setSmsCountdown] = useState(0)
  const [form] = Form.useForm()

  const sendSmsCode = async () => {
    const phoneValue = form.getFieldValue('phone')
    if (!phoneValue) {
      message.warning('请输入手机号')
      return
    }
    try {
      setSmsLoading(true)
      await api.getSmsCode(phoneValue)
      message.success('验证码已发送')
      setPhone(phoneValue)
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

  const handleVerify = async (values: { phone: string; code: string }) => {
    try {
      await api.loginSms(values.phone, values.code)
      message.success('验证通过')
      setPhone(values.phone)
      setStep('setPassword')
    } catch (e: any) {
      message.error(e.message || '验证失败')
    }
  }

  const handleSetPassword = async (values: { password: string; confirmPassword: string }) => {
    if (values.password !== values.confirmPassword) {
      message.error('两次输入的密码不一致')
      return
    }
    if (values.password.length < 6) {
      message.error('密码至少需要6位')
      return
    }
    try {
      await api.loginSms(phone, '123456')
      await api.registerUser({
        phone,
        password: values.password,
        agreed_terms: true,
        agreed_privacy: true,
      })
      message.success('密码设置成功，请登录')
      navigate('/login')
    } catch (e: any) {
      message.error(e.message || '设置密码失败')
    }
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#f5f5f5',
      }}
    >
      <div
        style={{
          width: 400,
          padding: 40,
          background: '#fff',
          borderRadius: 8,
          boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
        }}
      >
        <h2 style={{ textAlign: 'center', marginBottom: 24, fontWeight: 600 }}>
          {step === 'verify' ? '找回密码' : '设置新密码'}
        </h2>

        {step === 'verify' ? (
          <Form form={form} onFinish={handleVerify} layout="vertical">
            <Form.Item
              name="phone"
              rules={[{ required: true, message: '请输入手机号' }]}
            >
              <Input
                prefix={<MobileOutlined />}
                placeholder="手机号"
                size="large"
              />
            </Form.Item>
            <Form.Item
              name="code"
              rules={[{ required: true, message: '请输入验证码' }]}
            >
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
              <Button type="primary" htmlType="submit" block size="large">
                验证身份
              </Button>
            </Form.Item>
          </Form>
        ) : (
          <Form onFinish={handleSetPassword} layout="vertical">
            <Form.Item
              name="password"
              rules={[{ required: true, message: '请输入新密码' }]}
            >
              <Input.Password
                prefix={<LockOutlined />}
                placeholder="新密码"
                size="large"
              />
            </Form.Item>
            <Form.Item
              name="confirmPassword"
              rules={[{ required: true, message: '请确认新密码' }]}
            >
              <Input.Password
                prefix={<LockOutlined />}
                placeholder="确认密码"
                size="large"
              />
            </Form.Item>
            <Form.Item>
              <Button type="primary" htmlType="submit" block size="large">
                确认设置
              </Button>
            </Form.Item>
          </Form>
        )}

        <div style={{ textAlign: 'center', marginTop: 16 }}>
          <span>记得密码了？</span>
          <Link to="/login" style={{ marginLeft: 4 }}>返回登录</Link>
        </div>
      </div>
    </div>
  )
}