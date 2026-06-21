import { useEffect, useState } from 'react'
import { Button, Card, Col, DatePicker, Form, Input, InputNumber, message, Modal, Row, Select, Space, Table, Tag, Typography } from 'antd'
import { PlusOutlined, ReconciliationOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { api, type BankAccount, type BankTransaction, type BankReconcileResult } from '../../api/client'
import { useAuthStore } from '../../stores/authStore'

const { Title, Paragraph } = Typography

export function BankReconciliationPage() {
  const { currentLedgerId } = useAuthStore()
  const [accounts, setAccounts] = useState<BankAccount[]>([])
  const [transactions, setTransactions] = useState<BankTransaction[]>([])
  const [result, setResult] = useState<BankReconcileResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [reconciling, setReconciling] = useState(false)
  const [open, setOpen] = useState(false)
  const [form] = Form.useForm()

  const loadData = () => {
    if (!currentLedgerId) return
    setLoading(true)
    Promise.all([
      api.listBankAccounts(currentLedgerId),
      api.listBankTransactions(currentLedgerId),
    ])
      .then(([accountRes, txnRes]) => {
        setAccounts(accountRes)
        setTransactions(txnRes)
      })
      .catch((error: Error) => message.error(error.message || '加载对账数据失败'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadData()
  }, [currentLedgerId])

  const handleCreateTxn = async () => {
    if (!currentLedgerId) return
    const values = await form.validateFields()
    try {
      await api.createBankTransaction(currentLedgerId, {
        bank_account_id: values.bank_account_id,
        transaction_date: values.transaction_date.format('YYYY-MM-DD'),
        direction: values.direction,
        amount: values.amount,
        summary: values.summary,
        counterparty: values.counterparty,
      })
      message.success('银行流水已录入')
      setOpen(false)
      form.resetFields()
      loadData()
    } catch (error: any) {
      message.error(error.message || '录入失败')
    }
  }

  const handleAutoReconcile = async () => {
    if (!currentLedgerId) return
    setReconciling(true)
    try {
      const res = await api.autoReconcile(currentLedgerId)
      setResult(res)
      message.success(`自动对账完成，匹配 ${res.matched_count} 笔`)
      loadData()
    } catch (error: any) {
      message.error(error.message || '自动对账失败')
    } finally {
      setReconciling(false)
    }
  }

  const txnColumns = [
    { title: '日期', dataIndex: 'transaction_date', key: 'transaction_date' },
    {
      title: '方向',
      dataIndex: 'direction',
      key: 'direction',
      render: (value: string) => (
        <Tag color={value === 'in' ? 'green' : 'red'}>{value === 'in' ? '收入' : '支出'}</Tag>
      ),
    },
    {
      title: '金额',
      dataIndex: 'amount',
      key: 'amount',
      render: (value: number) => `¥ ${Number(value).toLocaleString()}`,
    },
    { title: '摘要', dataIndex: 'summary', key: 'summary', render: (v: string | null) => v || '-' },
    {
      title: '对账状态',
      dataIndex: 'reconciliation_status',
      key: 'reconciliation_status',
      render: (value: string) => (
        <Tag color={value === 'matched' ? 'success' : 'warning'}>
          {value === 'matched' ? '已匹配' : '未匹配'}
        </Tag>
      ),
    },
  ]

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Title level={4} style={{ margin: 0 }}>
            <ReconciliationOutlined /> 自动对账
          </Title>
          <Paragraph type="secondary">
            将银行流水与总账银行存款科目（1002）分录按金额和日期自动匹配，识别未达账项。
          </Paragraph>
        </Col>
        <Col>
          <Space>
            <Button icon={<PlusOutlined />} onClick={() => setOpen(true)} disabled={!currentLedgerId || accounts.length === 0}>
              录入流水
            </Button>
            <Button type="primary" loading={reconciling} onClick={handleAutoReconcile} disabled={!currentLedgerId}>
              执行自动对账
            </Button>
          </Space>
        </Col>
      </Row>

      <Card title="银行流水" style={{ marginBottom: 16 }}>
        <Table rowKey="id" columns={txnColumns} dataSource={transactions} loading={loading} pagination={false} />
      </Card>

      {result && (
        <Row gutter={16}>
          <Col xs={24} lg={12}>
            <Card title={`未匹配银行流水（${result.unmatched_transactions.length}）`} size="small">
              {result.unmatched_transactions.length === 0 ? (
                <Paragraph type="secondary">暂无未匹配银行流水</Paragraph>
              ) : (
                result.unmatched_transactions.map((item) => (
                  <div key={item.id} style={{ marginBottom: 8 }}>
                    {item.transaction_date} · {item.direction === 'in' ? '收入' : '支出'} ¥{item.amount} · {item.summary || '-'}
                  </div>
                ))
              )}
            </Card>
          </Col>
          <Col xs={24} lg={12}>
            <Card title={`未匹配账套分录（${result.unmatched_entries.length}）`} size="small">
              {result.unmatched_entries.length === 0 ? (
                <Paragraph type="secondary">暂无未匹配账套分录</Paragraph>
              ) : (
                result.unmatched_entries.map((item) => (
                  <div key={item.id} style={{ marginBottom: 8 }}>
                    {item.voucher_date} · {item.voucher_no} · ¥{item.amount} · {item.summary || '-'}
                  </div>
                ))
              )}
            </Card>
          </Col>
        </Row>
      )}

      <Modal title="录入银行流水" open={open} onOk={handleCreateTxn} onCancel={() => setOpen(false)} okText="保存" cancelText="取消">
        <Form form={form} layout="vertical" initialValues={{ direction: 'in', transaction_date: dayjs() }}>
          <Form.Item name="bank_account_id" label="银行账户" rules={[{ required: true, message: '请选择银行账户' }]}>
            <Select
              options={accounts.map((account) => ({
                value: account.id,
                label: `${account.bank_name} ${account.account_no}`,
              }))}
            />
          </Form.Item>
          <Form.Item name="transaction_date" label="交易日期" rules={[{ required: true, message: '请选择日期' }]}>
            <DatePicker style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="direction" label="收支方向" rules={[{ required: true }]}>
            <Select
              options={[
                { value: 'in', label: '收入' },
                { value: 'out', label: '支出' },
              ]}
            />
          </Form.Item>
          <Form.Item name="amount" label="金额" rules={[{ required: true, message: '请输入金额' }]}>
            <InputNumber style={{ width: '100%' }} min={0.01} precision={2} />
          </Form.Item>
          <Form.Item name="summary" label="摘要">
            <Input placeholder="例如：支付供应商货款" />
          </Form.Item>
          <Form.Item name="counterparty" label="对方户名">
            <Input />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
