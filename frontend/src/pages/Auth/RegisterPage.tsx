import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Form, Input, Button, Checkbox, Modal, message, Alert } from 'antd'
import { UserOutlined, LockOutlined, MobileOutlined, FileTextOutlined } from '@ant-design/icons'
import { api } from '../../api/client'
import { useAuthStore } from '../../stores/authStore'
import { resolvePostLoginPath } from '../../utils/navigation'

export function RegisterPage() {
  const navigate = useNavigate()
  const { setToken, setUser, setUserLedgers, setCurrentLedger } = useAuthStore()
  const [agreedTerms, setAgreedTerms] = useState(false)
  const [agreedPrivacy, setAgreedPrivacy] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [modalTitle, setModalTitle] = useState('')
  const [modalContent, setModalContent] = useState('')
  const [registerError, setRegisterError] = useState<string | null>(null)

  const canRegister = agreedTerms && agreedPrivacy

  const showTerms = () => {
    setModalTitle('用户协议')
    setModalContent('本用户协议为占位文本，用于演示协议查看功能。实际使用时请替换为正式的用户协议内容。')
    setModalOpen(true)
  }

  const showPrivacy = () => {
    setModalTitle('隐私政策')
    setModalContent('本隐私政策为占位文本，用于演示隐私政策查看功能。实际使用时请替换为正式的隐私政策内容。')
    setModalOpen(true)
  }

  const getRegisterErrorMessage = (error: unknown) => {
    const rawMessage = error instanceof Error ? error.message : ''
    if rawMessage.includes('JWT 密钥未配置') || rawMessage.includes('auth_not_configured')) {
      return '系统尚未完成安全配置，请联系管理员设置 SECRET_KEY 后重试'
    }
    if (rawMessage.includes('Username already exists')) {
      return '用户名已存在，请更换用户名或直接登录'
    }
    if (rawMessage.includes('Phone already exists')) {
      return '该手机号已绑定完整账号，请直接登录'
    }
    if (rawMessage.includes('Must agree to terms and privacy policy')) {
      return '请先同意用户协议和隐私政策'
    }
    if (rawMessage.includes('Username or phone required')) {
      return '请填写用户名或手机号'
    }
    return rawMessage || '注册失败，请检查网络或稍后重试'
  }

  const handleRegister = async (values: {
    username: string
    phone?: string
    password: string
    confirmPassword: string
  }) => {
    setRegisterError(null)
    if (values.password !== values.confirmPassword) {
      message.error('两次输入的密码不一致')
      return
    }
    if (!canRegister) {
      message.error('请先同意用户协议和隐私政策')
      return
    }

    let res: { access_token: string; account_upgraded?: boolean }
    try {
      const phone = values.phone?.trim() || undefined
      res = await api.registerUser({
        username: values.username,
        ...(phone ? { phone } : {}),
        password: values.password,
        agreed_terms: agreedTerms,
        agreed_privacy: agreedPrivacy,
      })
    } catch (e: unknown) {
      const errorMsg = getRegisterErrorMessage(e)
      setRegisterError(errorMsg)
      if (errorMsg.includes('已注册')) {
        message.warning('该手机号已注册')
      } else {
        message.error(errorMsg)
      }
      return
    }

    localStorage.setItem('token', res.access_token)
    message.success(res.account_upgraded ? '账号已完善，注册成功' : '注册成功')

    try {
      const context = await api.getAuthContext()
      setToken(res.access_token)
      setUser({
        id: context.user.id,
        username: context.user.username || '',
        phone: context.user.phone || '',
      })
      setUserLedgers(context.ledgers)
      setCurrentLedger(context.current_ledger_id)
      navigate(resolvePostLoginPath(context))
    } catch {
      localStorage.removeItem('token')
      message.warning('注册已成功，但初始化工作台信息失败，请重新登录')
      navigate('/login')
    }
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f5f5f5' }}>
      <div style={{ width: 400, padding: 40, background: '#fff', borderRadius: 8, boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}>
        <h2 style={{ textAlign: 'center', marginBottom: 24, fontWeight: 600 }}>注册账号</h2>
        <Form onFinish={handleRegister} layout="vertical">
          {registerError && (
            <Alert
              type="error"
              title={registerError}
              description={
                registerError.includes('已注册') ? (
                  <span>
                    账号已存在，<Link to="/login">立即登录</Link>
                  </span>
                ) : undefined
              }
              showIcon
              style={{ marginBottom: 16 }}
              closable
              onClose={() => setRegisterError(null)}
            />
          )}
          <Form.Item name="username" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input prefix={<UserOutlined />} placeholder="用户名" size="large" />
          </Form.Item>
          <Form.Item name="phone">
            <Input prefix={<MobileOutlined />} placeholder="手机号（选填，用于找回账号）" size="large" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="密码" size="large" />
          </Form.Item>
          <Form.Item name="confirmPassword" rules={[{ required: true, message: '请确认密码' }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="确认密码" size="large" />
          </Form.Item>
          <Form.Item>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <Checkbox checked={agreedTerms} onChange={(e) => setAgreedTerms(e.target.checked)}>
                我已阅读并同意
                <Button type="link" style={{ padding: 0, height: 'auto' }} onClick={showTerms}>
                  《用户协议》
                </Button>
              </Checkbox>
              <Checkbox checked={agreedPrivacy} onChange={(e) => setAgreedPrivacy(e.target.checked)}>
                我已阅读并同意
                <Button type="link" style={{ padding: 0, height: 'auto' }} onClick={showPrivacy}>
                  《隐私政策》
                </Button>
              </Checkbox>
            </div>
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block size="large" disabled={!canRegister}>
              注册
            </Button>
          </Form.Item>
        </Form>
        <div style={{ textAlign: 'center', marginTop: 16 }}>
          <span>已有账号？</span>
          <Link to="/login" style={{ marginLeft: 4 }}>立即登录</Link>
        </div>
      </div>
      <Modal title={modalTitle} open={modalOpen} onOk={() => setModalOpen(false)} onCancel={() => setModalOpen(false)}>
        <p>{modalContent}</p>
      </Modal>
    </div>
  )
}
