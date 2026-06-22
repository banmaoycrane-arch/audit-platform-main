import { useEffect, useState } from 'react'
import { Button, Card, Col, Form, Input, InputNumber, message, Modal, Row, Select, Space, Table, Tag, Typography } from 'antd'
import { PlusOutlined, BankOutlined } from '@ant-design/icons'
import { api, type BankAccount } from '../../api/client'
import { useAuthStore } from '../../stores/authStore'

const { Title, Paragraph } = Typography

export function BankAccountsPage() {
  const { currentLedgerId } = useAuthStore()
  const [accounts, setAccounts] = useState<BankAccount[]>([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const [form] = Form.useForm()

  const loadAccounts = () => {
    if (!currentLedgerId) return
    setLoading(true)
    api
      .listBankAccounts(currentLedgerId)
      .then(setAccounts)
      .catch((error: Error) => message.error(error.message || '加载银行账户失败'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadAccounts()
  }, [currentLedgerId])

  const handleCreate = async () => {
    if (!currentLedgerId) {
      message.warning('请先在顶部切换账套')
      return
    }
    const values = await form.validateFields()
    try {
      await api.createBankAccount(currentLedgerId, values)
      message.success('银行账户创建成功')
      setOpen(false)
      form.resetFields()
      loadAccounts()
    } catch (error: any) {
      message.error(error.message || '创建失败')
    }
  }

  const columns = [
    { title: '银行', dataIndex: 'bank_name', key: 'bank_name' },
    { title: '账号', dataIndex: 'account_no', key: 'account_no' },
    { title: '户名', dataIndex: 'account_name', key: 'account_name' },
    { title: '关联科目', dataIndex: 'coa_account_code', key: 'coa_account_code' },
    {
      title: '当前余额',
      dataIndex: 'current_balance',
      key: 'current_balance',
      render: (value: number) => `¥ ${Number(value).toLocaleString()}`,
    },
    {
      title: '状态',
      key: 'status',
      render: () => <Tag color="success">启用</Tag>,
    },
  ]

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Title level={4} style={{ margin: 0 }}>
            <BankOutlined /> 银行账户
          </Title>
          <Paragraph type="secondary">维护银行账户档案，并与总账银行存款科目（1002）关联。</Paragraph>
        </Col>
        <Col>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)} disabled={!currentLedgerId}>
            新增账户
          </Button>
        </Col>
      </Row>

      <Card>
        <Table rowKey="id" columns={columns} dataSource={accounts} loading={loading} pagination={false} />
      </Card>

      <Modal title="新增银行账户" open={open} onOk={handleCreate} onCancel={() => setOpen(false)} okText="保存" cancelText="取消">
        <Form form={form} layout="vertical" initialValues={{ coa_account_code: '1002', opening_balance: 0 }}>
          <Form.Item name="bank_name" label="开户银行" rules={[{ required: true, message: '请输入开户银行' }]}>
            <Input placeholder="例如：中国工商银行" />
          </Form.Item>
          <Form.Item name="account_no" label="银行账号" rules={[{ required: true, message: '请输入银行账号' }]}>
            <Input placeholder="6222..." />
          </Form.Item>
          <Form.Item name="account_name" label="账户名称" rules={[{ required: true, message: '请输入账户名称' }]}>
            <Input placeholder="公司全称" />
          </Form.Item>
          <Form.Item name="coa_account_code" label="关联总账科目">
            <Select options={[{ value: '1002', label: '1002 银行存款' }]} />
          </Form.Item>
          <Form.Item name="opening_balance" label="期初余额">
            <InputNumber style={{ width: '100%' }} min={0} precision={2} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
