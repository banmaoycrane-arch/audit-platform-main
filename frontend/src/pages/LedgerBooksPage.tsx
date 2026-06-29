import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Button,
  Card,
  Col,
  DatePicker,
  Form,
  Input,
  InputNumber,
  Row,
  Select,
  Space,
  Table,
  Tabs,
  Typography,
  message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { BookOutlined, ReloadOutlined, SearchOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { Link } from 'react-router-dom'
import {
  api,
  type AccountingEntry,
  type AccountingPeriod,
  type ChronologicalEntryFilters,
} from '../api/client'
import { useAuthStore } from '../stores/authStore'

type ChronologicalFilterState = Omit<ChronologicalEntryFilters, 'ledger_id'>

const { Title, Paragraph, Text } = Typography
const { RangePicker } = DatePicker

const VOUCHER_WORD_OPTIONS = [
  { value: '记', label: '记' },
  { value: '收', label: '收' },
  { value: '付', label: '付' },
  { value: '转', label: '转' },
  { value: '现收', label: '现收' },
  { value: '现付', label: '现付' },
]

function parseVoucherWord(voucherNo: string | null | undefined): string {
  if (!voucherNo) return '-'
  const dash = voucherNo.indexOf('-')
  if (dash > 0) return voucherNo.slice(0, dash)
  const match = voucherNo.match(/^([^\d]+)/)
  return match?.[1] || voucherNo
}

type FilterFormValues = {
  period_id?: number
  date_range?: [dayjs.Dayjs, dayjs.Dayjs]
  account_code?: string
  account_name?: string
  summary?: string
  voucher_word?: string
  voucher_no?: string
  amount_min?: number
  amount_max?: number
}

function DayBookTab() {
  const { currentLedgerId } = useAuthStore()
  const [form] = Form.useForm<FilterFormValues>()
  const [periods, setPeriods] = useState<AccountingPeriod[]>([])
  const [entries, setEntries] = useState<AccountingEntry[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [filters, setFilters] = useState<ChronologicalFilterState>({})

  useEffect(() => {
    if (!currentLedgerId) {
      setPeriods([])
      return
    }
    api.listAccountingPeriods(undefined, currentLedgerId).then(setPeriods).catch(() => setPeriods([]))
  }, [currentLedgerId])

  const loadEntries = useCallback(async () => {
    if (!currentLedgerId) {
      setEntries([])
      setTotal(0)
      return
    }
    setLoading(true)
    try {
      const resp = await api.listChronologicalEntries({
        ledger_id: currentLedgerId,
        limit: pageSize,
        offset: (page - 1) * pageSize,
        ...filters,
      })
      setEntries(resp.items)
      setTotal(resp.total)
    } catch (error) {
      message.error(error instanceof Error ? error.message : '加载序时簿失败')
      setEntries([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }, [currentLedgerId, filters, page, pageSize])

  useEffect(() => {
    loadEntries()
  }, [loadEntries])

  const handleSearch = async () => {
    const values = await form.validateFields()
    const next: ChronologicalFilterState = {}
    if (values.period_id) next.period_id = values.period_id
    if (values.date_range?.[0]) next.date_from = values.date_range[0].format('YYYY-MM-DD')
    if (values.date_range?.[1]) next.date_to = values.date_range[1].format('YYYY-MM-DD')
    if (values.account_code?.trim()) next.account_code = values.account_code.trim()
    if (values.account_name?.trim()) next.account_name = values.account_name.trim()
    if (values.summary?.trim()) next.summary = values.summary.trim()
    if (values.voucher_word) next.voucher_word = values.voucher_word
    if (values.voucher_no?.trim()) next.voucher_no = values.voucher_no.trim()
    if (values.amount_min != null) next.amount_min = values.amount_min
    if (values.amount_max != null) next.amount_max = values.amount_max
    setPage(1)
    setFilters(next)
  }

  const handleReset = () => {
    form.resetFields()
    setPage(1)
    setFilters({})
  }

  const columns: ColumnsType<AccountingEntry> = useMemo(
    () => [
      {
        title: '凭证日期',
        dataIndex: 'voucher_date',
        width: 110,
        render: (val: string | null) => val || '-',
      },
      {
        title: '记字号',
        key: 'voucher_word',
        width: 72,
        render: (_: unknown, row) => parseVoucherWord(row.voucher_no),
      },
      {
        title: '凭证号',
        dataIndex: 'voucher_no',
        width: 110,
        render: (val: string | null) => val || '-',
      },
      { title: '行号', dataIndex: 'entry_line_no', width: 64 },
      { title: '科目代码', dataIndex: 'account_code', width: 100, render: (v) => v || '-' },
      { title: '科目名称', dataIndex: 'account_name', ellipsis: true, render: (v) => v || '-' },
      { title: '摘要', dataIndex: 'summary', ellipsis: true, render: (v) => v || '-' },
      {
        title: '借方金额',
        dataIndex: 'debit_amount',
        width: 120,
        align: 'right',
        render: (val: number) => (val > 0 ? val.toLocaleString('zh-CN', { minimumFractionDigits: 2 }) : '-'),
      },
      {
        title: '贷方金额',
        dataIndex: 'credit_amount',
        width: 120,
        align: 'right',
        render: (val: number) => (val > 0 ? val.toLocaleString('zh-CN', { minimumFractionDigits: 2 }) : '-'),
      },
      { title: '对方单位', dataIndex: 'counterparty', ellipsis: true, render: (v) => v || '-' },
    ],
    [],
  )

  if (!currentLedgerId) {
    return (
      <Card>
        <Text type="secondary">请先在顶部切换账簿，再查看序时簿。</Text>
      </Card>
    )
  }

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Card size="small" title="筛选条件">
        <Form form={form} layout="vertical">
          <Row gutter={16}>
            <Col xs={24} md={8} lg={6}>
              <Form.Item name="period_id" label="会计期间">
                <Select
                  allowClear
                  placeholder="全部期间"
                  options={periods.map((p) => ({
                    value: p.id,
                    label: `${p.period_code}（${p.start_date} ~ ${p.end_date}）`,
                  }))}
                />
              </Form.Item>
            </Col>
            <Col xs={24} md={8} lg={6}>
              <Form.Item name="date_range" label="凭证日期">
                <RangePicker style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col xs={24} md={4} lg={3}>
              <Form.Item name="voucher_word" label="记字号">
                <Select allowClear placeholder="全部" options={VOUCHER_WORD_OPTIONS} />
              </Form.Item>
            </Col>
            <Col xs={24} md={4} lg={3}>
              <Form.Item name="voucher_no" label="凭证号">
                <Input placeholder="模糊匹配" allowClear />
              </Form.Item>
            </Col>
            <Col xs={24} md={4} lg={3}>
              <Form.Item name="account_code" label="科目代码">
                <Input placeholder="模糊匹配" allowClear />
              </Form.Item>
            </Col>
            <Col xs={24} md={4} lg={3}>
              <Form.Item name="account_name" label="科目名称">
                <Input placeholder="模糊匹配" allowClear />
              </Form.Item>
            </Col>
            <Col xs={24} md={8} lg={6}>
              <Form.Item name="summary" label="分录摘要">
                <Input placeholder="模糊匹配" allowClear />
              </Form.Item>
            </Col>
            <Col xs={12} md={4} lg={3}>
              <Form.Item name="amount_min" label="金额下限">
                <InputNumber style={{ width: '100%' }} min={0} precision={2} />
              </Form.Item>
            </Col>
            <Col xs={12} md={4} lg={3}>
              <Form.Item name="amount_max" label="金额上限">
                <InputNumber style={{ width: '100%' }} min={0} precision={2} />
              </Form.Item>
            </Col>
          </Row>
          <Space>
            <Button type="primary" icon={<SearchOutlined />} onClick={handleSearch}>
              查询
            </Button>
            <Button onClick={handleReset}>重置</Button>
            <Button icon={<ReloadOutlined />} onClick={loadEntries}>
              刷新
            </Button>
          </Space>
        </Form>
      </Card>

      <Card
        title={`序时簿分录（共 ${total} 条）`}
        extra={<Text type="secondary">按凭证日期、凭证号、行号升序排列</Text>}
      >
        <Table
          rowKey="id"
          size="small"
          loading={loading}
          columns={columns}
          dataSource={entries}
          scroll={{ x: 1200 }}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            showTotal: (t) => `共 ${t} 条`,
            onChange: (p, size) => {
              setPage(p)
              setPageSize(size)
            },
          }}
        />
      </Card>
    </Space>
  )
}

export function LedgerBooksPage() {
  return (
    <div style={{ padding: 24 }}>
      <Title level={4} style={{ marginTop: 0 }}>
        <BookOutlined /> 账簿管理
      </Title>
      <Paragraph type="secondary">
        按会计期间查看账簿。序时簿展示全部凭证分录流水，支持按科目、摘要、金额、日期、记字号等条件筛选。
      </Paragraph>

      <Tabs
        defaultActiveKey="daybook"
        items={[
          {
            key: 'daybook',
            label: '序时簿',
            children: <DayBookTab />,
          },
          {
            key: 'general',
            label: '总账',
            children: (
              <Card>
                <Paragraph>总账按科目汇总借贷发生额与余额。</Paragraph>
                <Link to="/ledger/general-ledger">前往总账页面</Link>
              </Card>
            ),
          },
          {
            key: 'subsidiary',
            label: '明细账',
            children: (
              <Card>
                <Paragraph>明细账按科目展示分录明细，可从序时簿按科目代码筛选后查看。</Paragraph>
                <Link to="/ledger/subsidiary-ledger">前往明细账页面</Link>
              </Card>
            ),
          },
        ]}
      />
    </div>
  )
}
