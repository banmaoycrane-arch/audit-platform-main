import { useEffect, useState } from 'react'
import {
  Button,
  Card,
  Col,
  DatePicker,
  Descriptions,
  Form,
  Input,
  InputNumber,
  message,
  Modal,
  Row,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  Alert,
} from 'antd'
import { FileTextOutlined, PlusOutlined, ReconciliationOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import {
  api,
  type BankAccount,
  type BankReconciliationDraft,
  type BankTransaction,
  type BankReconcileResult,
} from '../../api/client'
import { useAuthStore } from '../../stores/authStore'
import { formatAmount } from '../../money'

const { Title, Paragraph } = Typography

function getBankActionBlockMessage(currentLedgerId: number | null, accountCount: number): string | null {
  if (!currentLedgerId) {
    return '请先选择账簿，再录入银行流水或生成银行调节表。'
  }
  if (accountCount === 0) {
    return '请先维护银行账户，再录入银行流水或生成银行调节表。'
  }
  return null
}

export function BankReconciliationPage() {
  const { currentLedgerId } = useAuthStore()
  const [accounts, setAccounts] = useState<BankAccount[]>([])
  const [transactions, setTransactions] = useState<BankTransaction[]>([])
  const [reconciliations, setReconciliations] = useState<BankReconciliationDraft[]>([])
  const [selectedDraft, setSelectedDraft] = useState<BankReconciliationDraft | null>(null)
  const [result, setResult] = useState<BankReconcileResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [reconciling, setReconciling] = useState(false)
  const [drafting, setDrafting] = useState(false)
  const [open, setOpen] = useState(false)
  const [draftOpen, setDraftOpen] = useState(false)
  const [form] = Form.useForm()
  const [draftForm] = Form.useForm()

  const loadData = () => {
    if (!currentLedgerId) return
    setLoading(true)
    Promise.all([
      api.listBankAccounts(currentLedgerId),
      api.listBankTransactions(currentLedgerId),
      api.listBankReconciliations(currentLedgerId),
    ])
      .then(([accountRes, txnRes, draftRes]) => {
        setAccounts(accountRes)
        setTransactions(txnRes)
        setReconciliations(draftRes)
      })
      .catch((error: Error) => message.error(error.message || '加载对账数据失败'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadData()
  }, [currentLedgerId])

  const handleOpenTxnModal = () => {
    const blockMessage = getBankActionBlockMessage(currentLedgerId, accounts.length)
    if (blockMessage) {
      message.warning(blockMessage)
      return
    }
    setOpen(true)
  }

  const handleOpenDraftModal = () => {
    const blockMessage = getBankActionBlockMessage(currentLedgerId, accounts.length)
    if (blockMessage) {
      message.warning(blockMessage)
      return
    }
    setDraftOpen(true)
  }

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

  const handleCreateDraft = async () => {
    if (!currentLedgerId) return
    const values = await draftForm.validateFields()
    setDrafting(true)
    try {
      const draft = await api.createBankReconciliationDraft(currentLedgerId, {
        bank_account_id: values.bank_account_id,
        period_end: values.period_end.format('YYYY-MM-DD'),
        statement_balance: values.statement_balance,
      })
      setSelectedDraft(draft)
      setDraftOpen(false)
      draftForm.resetFields()
      message.success(draft.status === 'balanced' ? '调节表已平衡' : '调节表草稿已生成')
      loadData()
    } catch (error: any) {
      message.error(error.message || '生成调节表失败')
    } finally {
      setDrafting(false)
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
      render: (value: number) => formatAmount(value),
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

  const draftColumns = [
    { title: '截止日', dataIndex: 'period_end', key: 'period_end' },
    {
      title: '银行账户',
      key: 'account',
      render: (_: unknown, row: BankReconciliationDraft) =>
        `${row.bank_name || ''} ${row.account_no || ''}`.trim() || `#${row.bank_account_id}`,
    },
    {
      title: '调节后银行余额',
      dataIndex: 'adjusted_statement_balance',
      key: 'adjusted_statement_balance',
      render: (value: number) => formatAmount(value),
    },
    {
      title: '调节后账面余额',
      dataIndex: 'adjusted_book_balance',
      key: 'adjusted_book_balance',
      render: (value: number) => formatAmount(value),
    },
    {
      title: '差异',
      dataIndex: 'difference',
      key: 'difference',
      render: (value: number) => (
        <Tag color={Math.abs(value) < 0.01 ? 'success' : 'error'}>{formatAmount(value)}</Tag>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (value: string) => (
        <Tag color={value === 'balanced' ? 'success' : 'processing'}>
          {value === 'balanced' ? '已平衡' : '草稿'}
        </Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, row: BankReconciliationDraft) => (
        <Button type="link" onClick={() => setSelectedDraft(row)}>
          查看
        </Button>
      ),
    },
  ]

  const hasAutoReconcileDifference = Boolean(
    result && (result.unmatched_transactions.length > 0 || result.unmatched_entries.length > 0),
  )

  const itemColumns = [
    { title: '类型', dataIndex: 'item_type_label', key: 'item_type_label' },
    {
      title: '金额',
      dataIndex: 'amount',
      key: 'amount',
      render: (value: number) => formatAmount(value),
    },
    { title: '摘要', dataIndex: 'summary', key: 'summary', render: (v: string | null) => v || '-' },
    { title: '凭证号', dataIndex: 'note', key: 'note', render: (v: string | null) => v || '-' },
  ]

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Title level={4} style={{ margin: 0 }}>
            <ReconciliationOutlined /> 银行调节与自动对账
          </Title>
          <Paragraph type="secondary">
            先将银行流水与总账银行存款科目（1002）自动匹配，再生成银行余额调节表草稿。
          </Paragraph>
        </Col>
        <Col>
          <Space>
            <Button icon={<PlusOutlined />} onClick={handleOpenTxnModal}>
              录入流水
            </Button>
            <Button icon={<FileTextOutlined />} onClick={handleOpenDraftModal}>
              生成调节表
            </Button>
            <Button type="primary" loading={reconciling} onClick={handleAutoReconcile} disabled={!currentLedgerId}>
              执行自动对账
            </Button>
          </Space>
        </Col>
      </Row>

      <Card title="银行调节表草稿" style={{ marginBottom: 16 }}>
        <Table
          rowKey="id"
          columns={draftColumns}
          dataSource={reconciliations}
          loading={loading}
          pagination={false}
          locale={{ emptyText: '暂无调节表，请先执行自动对账后生成' }}
        />
      </Card>

      {selectedDraft && (
        <Card
          title={`调节表详情 · ${selectedDraft.period_end}`}
          style={{ marginBottom: 16 }}
          extra={
            <Button type="link" onClick={() => setSelectedDraft(null)}>
              关闭
            </Button>
          }
        >
          {Math.abs(selectedDraft.difference) >= 0.01 && (
            <Alert
              type="warning"
              showIcon
              style={{ marginBottom: 16 }}
              message="调节表存在差异，需先核实差异原因"
              description="请逐项检查未匹配银行流水、未匹配账簿分录、银行手续费、利息收入、企业已收银行未收、银行已付企业未付等事项。确认属于应入账事项后，再由人工在凭证复核流程中编制差异凭证。"
            />
          )}
          <Descriptions bordered size="small" column={{ xs: 1, sm: 2, md: 3 }}>
            <Descriptions.Item label="银行对账单余额">
              {formatAmount(selectedDraft.statement_balance)}
            </Descriptions.Item>
            <Descriptions.Item label="企业账面余额">
              {formatAmount(selectedDraft.book_balance)}
            </Descriptions.Item>
            <Descriptions.Item label="调节后银行余额">
              {formatAmount(selectedDraft.adjusted_statement_balance)}
            </Descriptions.Item>
            <Descriptions.Item label="调节后账面余额">
              {formatAmount(selectedDraft.adjusted_book_balance)}
            </Descriptions.Item>
            <Descriptions.Item label="差异">
              <Tag color={Math.abs(selectedDraft.difference) < 0.01 ? 'success' : 'error'}>
                {formatAmount(selectedDraft.difference)}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="状态">
              {selectedDraft.status === 'balanced' ? '已平衡' : '草稿'}
            </Descriptions.Item>
          </Descriptions>
          <Table
            style={{ marginTop: 16 }}
            rowKey="id"
            columns={itemColumns}
            dataSource={selectedDraft.items}
            pagination={false}
            locale={{ emptyText: '无未达账项，调节表已平衡' }}
          />
        </Card>
      )}

      <Card title="银行流水" style={{ marginBottom: 16 }}>
        <Table rowKey="id" columns={txnColumns} dataSource={transactions} loading={loading} pagination={false} />
      </Card>

      {result && (
        <>
          {hasAutoReconcileDifference && (
            <Alert
              type="warning"
              showIcon
              style={{ marginBottom: 16 }}
              message="自动对账发现差异，请先核实后处理"
              description="建议按顺序检查：1. 未匹配银行流水是否为手续费、利息、未入账收付款；2. 未匹配账簿分录是否缺少银行流水或日期金额不一致；3. 确认属于应入账差异后，再人工编制差异凭证并复核，不由系统自动入账。"
              action={(
                <Space direction="vertical">
                  <Button size="small" onClick={handleOpenDraftModal}>生成调节表草稿</Button>
                  <Button size="small" onClick={() => message.info('请在凭证复核流程中人工编制差异凭证，系统不会自动入账。')}>查看凭证处理提示</Button>
                </Space>
              )}
            />
          )}
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
            <Card title={`未匹配账簿分录（${result.unmatched_entries.length}）`} size="small">
              {result.unmatched_entries.length === 0 ? (
                <Paragraph type="secondary">暂无未匹配账簿分录</Paragraph>
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
        </>
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

      <Modal
        title="生成银行调节表草稿"
        open={draftOpen}
        onOk={handleCreateDraft}
        onCancel={() => setDraftOpen(false)}
        confirmLoading={drafting}
        okText="生成"
        cancelText="取消"
      >
        <Form
          form={draftForm}
          layout="vertical"
          initialValues={{ period_end: dayjs() }}
        >
          <Form.Item name="bank_account_id" label="银行账户" rules={[{ required: true, message: '请选择银行账户' }]}>
            <Select
              options={accounts.map((account) => ({
                value: account.id,
                label: `${account.bank_name} ${account.account_no}`,
              }))}
            />
          </Form.Item>
          <Form.Item name="period_end" label="截止日期" rules={[{ required: true, message: '请选择截止日期' }]}>
            <DatePicker style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="statement_balance" label="银行对账单余额（可选，默认取账户当前余额）">
            <InputNumber style={{ width: '100%' }} precision={2} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
