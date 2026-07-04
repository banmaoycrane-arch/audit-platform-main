import { useEffect, useState } from 'react'
import {
  Button,
  Card,
  Form,
  InputNumber,
  Modal,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import { MailOutlined, PlusOutlined, SendOutlined } from '@ant-design/icons'
import { Link } from 'react-router-dom'
import { api, type CounterpartyConfirmation } from '../../api/client'
import { useAuthStore } from '../../stores/authStore'
import { formatAmount } from '../../money'

const { Title, Paragraph } = Typography

const STATUS_LABEL: Record<string, string> = {
  draft: '草稿',
  sent: '已发函',
  replied: '已回函',
  exception: '有差异',
}

const STATUS_COLOR: Record<string, string> = {
  draft: 'default',
  sent: 'processing',
  replied: 'success',
  exception: 'error',
}

export function ConfirmationsPage() {
  const { currentLedgerId } = useAuthStore()
  const [rows, setRows] = useState<CounterpartyConfirmation[]>([])
  const [loading, setLoading] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [replyOpen, setReplyOpen] = useState(false)
  const [activeRow, setActiveRow] = useState<CounterpartyConfirmation | null>(null)
  const [replyForm] = Form.useForm()

  const loadData = () => {
    if (!currentLedgerId) return
    setLoading(true)
    api
      .listConfirmations(currentLedgerId)
      .then(setRows)
      .catch((error: Error) => message.error(error.message || '加载函证控制表失败'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadData()
  }, [currentLedgerId])

  const handleGenerate = async () => {
    if (!currentLedgerId) return
    setGenerating(true)
    try {
      const created = await api.generateConfirmations(currentLedgerId, {})
      message.success(`已生成 ${created.length} 条函证控制记录`)
      loadData()
    } catch (error: any) {
      message.error(error.message || '生成函证失败')
    } finally {
      setGenerating(false)
    }
  }

  const handleMarkSent = async (row: CounterpartyConfirmation) => {
    if (!currentLedgerId) return
    try {
      await api.updateConfirmation(currentLedgerId, row.id, { status: 'sent' })
      message.success('已标记为已发函')
      loadData()
    } catch (error: any) {
      message.error(error.message || '更新状态失败')
    }
  }

  const handleReply = async () => {
    if (!currentLedgerId || !activeRow) return
    const values = await replyForm.validateFields()
    try {
      await api.recordConfirmationReply(currentLedgerId, activeRow.id, {
        reply_amount: values.reply_amount,
      })
      message.success('回函金额已登记')
      setReplyOpen(false)
      replyForm.resetFields()
      setActiveRow(null)
      loadData()
    } catch (error: any) {
      message.error(error.message || '登记回函失败')
    }
  }

  const columns = [
    { title: '往来单位', dataIndex: 'counterparty_name', key: 'counterparty_name' },
    {
      title: '余额方向',
      dataIndex: 'balance_type_label',
      key: 'balance_type_label',
      render: (value: string) => <Tag>{value}</Tag>,
    },
    {
      title: '账面余额',
      dataIndex: 'book_balance',
      key: 'book_balance',
      render: (value: number) => formatAmount(value),
    },
    {
      title: '发函金额',
      dataIndex: 'confirmation_amount',
      key: 'confirmation_amount',
      render: (value: number) => formatAmount(value),
    },
    {
      title: '回函金额',
      dataIndex: 'reply_amount',
      key: 'reply_amount',
      render: (value: number | null) => (value == null ? '-' : formatAmount(value)),
    },
    {
      title: '差异',
      dataIndex: 'difference',
      key: 'difference',
      render: (value: number | null) =>
        value == null ? (
          '-'
        ) : (
          <Tag color={Math.abs(value) < 0.01 ? 'success' : 'error'}>
            {formatAmount(value)}
          </Tag>
        ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (value: string) => <Tag color={STATUS_COLOR[value]}>{STATUS_LABEL[value] || value}</Tag>,
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, row: CounterpartyConfirmation) => (
        <Space>
          {row.status === 'draft' && (
            <Button type="link" icon={<SendOutlined />} onClick={() => handleMarkSent(row)}>
              标记发函
            </Button>
          )}
          {row.status !== 'replied' && row.status !== 'exception' && (
            <Button
              type="link"
              onClick={() => {
                setActiveRow(row)
                replyForm.setFieldsValue({ reply_amount: row.confirmation_amount })
                setReplyOpen(true)
              }}
            >
              登记回函
            </Button>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div>
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <Title level={4} style={{ margin: 0 }}>
              <MailOutlined /> 往来函证控制表
            </Title>
            <Paragraph type="secondary" style={{ marginBottom: 0 }}>
              从往来款项台账余额生成函证控制行，登记发函与回函金额；差异仅作审计发现，不自动调整账面。
              <Link to="/basic/receivable-payable" style={{ marginLeft: 8 }}>
                查看往来台账
              </Link>
            </Paragraph>
          </div>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            loading={generating}
            disabled={!currentLedgerId}
            onClick={handleGenerate}
          >
            从余额生成函证
          </Button>
        </div>

        <Card>
          <Table
            rowKey="id"
            loading={loading}
            columns={columns}
            dataSource={rows}
            pagination={{ pageSize: 20 }}
            locale={{ emptyText: '暂无函证记录，请先从往来余额生成' }}
          />
        </Card>
      </Space>

      <Modal
        title={`登记回函 · ${activeRow?.counterparty_name || ''}`}
        open={replyOpen}
        onOk={handleReply}
        onCancel={() => {
          setReplyOpen(false)
          setActiveRow(null)
          replyForm.resetFields()
        }}
        okText="保存"
        cancelText="取消"
      >
        <Form form={replyForm} layout="vertical">
          <Form.Item label="发函金额">
            <Typography.Text>{formatAmount(activeRow?.confirmation_amount || 0)}</Typography.Text>
          </Form.Item>
          <Form.Item
            name="reply_amount"
            label="回函金额"
            rules={[{ required: true, message: '请输入回函金额' }]}
          >
            <InputNumber style={{ width: '100%' }} min={0.01} precision={2} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
