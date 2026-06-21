import { useState } from 'react'
import { Modal, Form, Input, Button, message } from 'antd'
import { LockOutlined } from '@ant-design/icons'
import { api } from '../../api/client'

interface SetPasswordModalProps {
  open: boolean
  onClose: () => void
  onSuccess: () => void
  afterClose?: () => void
}

export function SetPasswordModal({ open, onClose, onSuccess, afterClose }: SetPasswordModalProps) {
  const [loading, setLoading] = useState(false)
  const [form] = Form.useForm()

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
      setLoading(true)
      await api.setPassword(values.password)
      message.success('密码设置成功！下次可使用密码登录')
      form.resetFields()
      onSuccess()
    } catch (e: any) {
      message.error(e.message || '设置密码失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      title="设置密码"
      open={open}
      onCancel={onClose}
      afterClose={afterClose}
      footer={null}
      closable={true}
      mask={{ closable: false }}
    >
      <div style={{ marginBottom: 16 }}>
        <p style={{ color: '#666', fontSize: 14 }}>
          设置密码后，您可以使用账号密码登录，无需每次输入验证码。
        </p>
      </div>
      <Form form={form} onFinish={handleSetPassword} layout="vertical">
        <Form.Item
          name="password"
          rules={[
            { required: true, message: '请输入密码' },
            { min: 6, message: '密码至少需要6位' }
          ]}
        >
          <Input.Password
            prefix={<LockOutlined />}
            placeholder="输入密码"
            size="large"
          />
        </Form.Item>
        <Form.Item
          name="confirmPassword"
          rules={[
            { required: true, message: '请确认密码' },
            { min: 6, message: '密码至少需要6位' }
          ]}
        >
          <Input.Password
            prefix={<LockOutlined />}
            placeholder="确认密码"
            size="large"
          />
        </Form.Item>
        <Form.Item style={{ marginBottom: 0 }}>
          <div style={{ display: 'flex', gap: 8 }}>
            <Button onClick={onClose} style={{ flex: 1 }}>
              稍后设置
            </Button>
            <Button type="primary" htmlType="submit" loading={loading} style={{ flex: 1 }}>
              确认设置
            </Button>
          </div>
        </Form.Item>
      </Form>
    </Modal>
  )
}
