import { useCallback, useEffect, useState } from 'react'
import {
  Button,
  Card,
  Col,
  DatePicker,
  Form,
  Input,
  InputNumber,
  Pagination,
  Radio,
  Row,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
  Empty,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { FileSearchOutlined, ReloadOutlined, SearchOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import {
  api,
  type AccountingEntry,
  type AccountingPeriod,
  type VoucherCard,
  type VoucherQueryFilters,
} from '../api/client'
import { useAuthStore } from '../stores/authStore'

const { Title, Paragraph, Text } = Typography
const { RangePicker } = DatePicker

type DateMode = 'day' | 'month'

type FilterFormValues = {
  date_mode?: DateMode
  date_range?: [dayjs.Dayjs, dayjs.Dayjs]
  month?: dayjs.Dayjs
  period_id?: number
  filter_mode?: 'line' | 'voucher'
  account_code?: string
  account_name?: string
  summary?: string
  voucher_word?: string
  voucher_no?: string
  debit_min?: number
  debit_max?: number
  credit_min?: number
  credit_max?: number
  total_min?: number
  total_max?: number
}

const VOUCHER_WORD_OPTIONS = [
  { value: '记', label: '记' },
  { value: '收', label: '收' },
  { value: '付', label: '付' },
  { value: '转', label: '转' },
]

function formatMoney(value: number) {
  return value.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function VoucherCardView({ voucher }: { voucher: VoucherCard }) {
  const columns: ColumnsType<AccountingEntry> = [
    { title: '行', dataIndex: 'entry_line_no', width: 48 },
    { title: '科目代码', dataIndex: 'account_code', width: 96, render: (v) => v || '-' },
    { title: '科目名称', dataIndex: 'account_name', ellipsis: true, render: (v) => v || '-' },
    { title: '摘要', dataIndex: 'summary', ellipsis: true, render: (v) => v || '-' },
    {
      title: '借方',
      dataIndex: 'debit_amount',
      width: 110,
      align: 'right',
      render: (v: number) => (v > 0 ? formatMoney(v) : '-'),
    },
    {
      title: '贷方',
      dataIndex: 'credit_amount',
      width: 110,
      align: 'right',
      render: (v: number) => (v > 0 ? formatMoney(v) : '-'),
    },
  ]

  return (
    <Card
      size="small"
      title={
        <Space wrap>
          <Text strong>{voucher.voucher_date || '无日期'}</Text>
          {voucher.voucher_word && <Tag color="blue">{voucher.voucher_word}</Tag>}
          <Text>{voucher.voucher_no || '无凭证号'}</Text>
        </Space>
      }
      extra={
        <Space>
          <Text type="secondary">{voucher.line_count} 行</Text>
          <Text>借 {formatMoney(voucher.debit_total)}</Text>
          <Text>贷 {formatMoney(voucher.credit_total)}</Text>
        </Space>
      }
    >
      {voucher.summary_preview && (
        <Paragraph type="secondary" style={{ marginBottom: 8 }}>
          摘要：{voucher.summary_preview}
        </Paragraph>
      )}
      <Table
        rowKey="id"
        size="small"
        pagination={false}
        columns={columns}
        dataSource={voucher.lines}
        scroll={{ x: 720 }}
      />
    </Card>
  )
}

export function VoucherQueryPage() {
  const { currentLedgerId } = useAuthStore()
  const [form] = Form.useForm<FilterFormValues>()
  const dateMode = Form.useWatch('date_mode', form) || 'day'
  const filterMode = Form.useWatch('filter_mode', form) || 'line'
  const [periods, setPeriods] = useState<AccountingPeriod[]>([])
  const [vouchers, setVouchers] = useState<VoucherCard[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(6)
  const [filters, setFilters] = useState<VoucherQueryFilters>({ filter_mode: 'line' })

  useEffect(() => {
    if (!currentLedgerId) {
      setPeriods([])
      return
    }
    api.listAccountingPeriods(undefined, currentLedgerId).then(setPeriods).catch(() => setPeriods([]))
  }, [currentLedgerId])

  const loadVouchers = useCallback(async () => {
    if (!currentLedgerId) {
      setVouchers([])
      setTotal(0)
      return
    }
    setLoading(true)
    try {
      const resp = await api.queryVouchers({
        ledger_id: currentLedgerId,
        limit: pageSize,
        offset: (page - 1) * pageSize,
        ...filters,
      })
      setVouchers(resp.items)
      setTotal(resp.total)
    } catch (error) {
      message.error(error instanceof Error ? error.message : '凭证查询失败')
      setVouchers([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }, [currentLedgerId, filters, page, pageSize])

  useEffect(() => {
    loadVouchers()
  }, [loadVouchers])

  const handleSearch = async () => {
    const values = await form.validateFields()
    const next: VoucherQueryFilters = {
      filter_mode: values.filter_mode || 'line',
    }
    if (values.period_id) next.period_id = values.period_id
    if (values.date_mode === 'month' && values.month) {
      next.month = values.month.format('YYYY-MM')
    } else if (values.date_range?.[0]) {
      next.date_from = values.date_range[0].format('YYYY-MM-DD')
      next.date_to = values.date_range[1].format('YYYY-MM-DD')
    }
    if (values.account_code?.trim()) next.account_code = values.account_code.trim()
    if (values.account_name?.trim()) next.account_name = values.account_name.trim()
    if (values.summary?.trim()) next.summary = values.summary.trim()
    if (values.voucher_word) next.voucher_word = values.voucher_word
    if (values.voucher_no?.trim()) next.voucher_no = values.voucher_no.trim()
    if (values.debit_min != null) next.debit_min = values.debit_min
    if (values.debit_max != null) next.debit_max = values.debit_max
    if (values.credit_min != null) next.credit_min = values.credit_min
    if (values.credit_max != null) next.credit_max = values.credit_max
    if (values.total_min != null) next.total_min = values.total_min
    if (values.total_max != null) next.total_max = values.total_max
    setPage(1)
    setFilters(next)
  }

  const handleReset = () => {
    form.resetFields()
    setPage(1)
    setFilters({ filter_mode: 'line' })
  }

  if (!currentLedgerId) {
    return (
      <div style={{ padding: 24 }}>
        <Title level={4}>凭证查询</Title>
        <Text type="secondary">请先在顶部切换账套。</Text>
      </div>
    )
  }

  return (
    <div style={{ padding: 24 }}>
      <Title level={4} style={{ marginTop: 0 }}>
        <FileSearchOutlined /> 凭证查询
      </Title>
      <Paragraph type="secondary">
        按日期、科目、金额等条件筛选凭证集合，结果以卡片形式分页展示；支持按分录行或按凭证整体两种筛选模式。
      </Paragraph>

      <Card size="small" title="查询条件" style={{ marginBottom: 16 }}>
        <Form
          form={form}
          layout="vertical"
          initialValues={{ date_mode: 'day', filter_mode: 'line' }}
        >
          <Row gutter={16}>
            <Col xs={24} md={8}>
              <Form.Item name="filter_mode" label="筛选模式">
                <Radio.Group>
                  <Radio.Button value="line">按行筛选</Radio.Button>
                  <Radio.Button value="voucher">按凭证整体</Radio.Button>
                </Radio.Group>
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item name="date_mode" label="日期精度">
                <Radio.Group>
                  <Radio.Button value="day">按天</Radio.Button>
                  <Radio.Button value="month">按月</Radio.Button>
                </Radio.Group>
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
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
            <Col xs={24} md={8}>
              {dateMode === 'month' ? (
                <Form.Item name="month" label="凭证月份">
                  <DatePicker picker="month" style={{ width: '100%' }} />
                </Form.Item>
              ) : (
                <Form.Item name="date_range" label="凭证日期">
                  <RangePicker style={{ width: '100%' }} />
                </Form.Item>
              )}
            </Col>
            <Col xs={12} md={4}>
              <Form.Item name="voucher_word" label="记字号">
                <Select allowClear placeholder="全部" options={VOUCHER_WORD_OPTIONS} />
              </Form.Item>
            </Col>
            <Col xs={12} md={4}>
              <Form.Item name="voucher_no" label="凭证号">
                <Input allowClear placeholder="模糊匹配" />
              </Form.Item>
            </Col>
            <Col xs={12} md={4}>
              <Form.Item name="account_code" label="科目代码">
                <Input allowClear placeholder="模糊匹配" />
              </Form.Item>
            </Col>
            <Col xs={12} md={4}>
              <Form.Item name="account_name" label="科目名称">
                <Input allowClear placeholder="模糊匹配" />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item name="summary" label="分录摘要">
                <Input allowClear placeholder="模糊匹配" />
              </Form.Item>
            </Col>
            <Col xs={12} md={4}>
              <Form.Item name="debit_min" label="借方下限">
                <InputNumber style={{ width: '100%' }} min={0} precision={2} />
              </Form.Item>
            </Col>
            <Col xs={12} md={4}>
              <Form.Item name="debit_max" label="借方上限">
                <InputNumber style={{ width: '100%' }} min={0} precision={2} />
              </Form.Item>
            </Col>
            <Col xs={12} md={4}>
              <Form.Item name="credit_min" label="贷方下限">
                <InputNumber style={{ width: '100%' }} min={0} precision={2} />
              </Form.Item>
            </Col>
            <Col xs={12} md={4}>
              <Form.Item name="credit_max" label="贷方上限">
                <InputNumber style={{ width: '100%' }} min={0} precision={2} />
              </Form.Item>
            </Col>
            {filterMode === 'voucher' && (
              <>
                <Col xs={12} md={4}>
                  <Form.Item name="total_min" label="合计下限">
                    <InputNumber style={{ width: '100%' }} min={0} precision={2} />
                  </Form.Item>
                </Col>
                <Col xs={12} md={4}>
                  <Form.Item name="total_max" label="合计上限">
                    <InputNumber style={{ width: '100%' }} min={0} precision={2} />
                  </Form.Item>
                </Col>
              </>
            )}
          </Row>
          <Space>
            <Button type="primary" icon={<SearchOutlined />} onClick={handleSearch}>
              查询
            </Button>
            <Button onClick={handleReset}>重置</Button>
            <Button icon={<ReloadOutlined />} onClick={loadVouchers}>
              刷新
            </Button>
          </Space>
        </Form>
      </Card>

      <div style={{ marginBottom: 12 }}>
        <Text type="secondary">共找到 {total} 张凭证</Text>
      </div>

      {loading ? (
        <Card loading />
      ) : vouchers.length === 0 ? (
        <Empty description="暂无符合条件的凭证" />
      ) : (
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          {vouchers.map((voucher) => (
            <VoucherCardView
              key={`${voucher.voucher_no}-${voucher.voucher_date}`}
              voucher={voucher}
            />
          ))}
        </Space>
      )}

      <div style={{ marginTop: 24, textAlign: 'right' }}>
        <Pagination
          current={page}
          pageSize={pageSize}
          total={total}
          showSizeChanger
          pageSizeOptions={['6', '10', '20']}
          showTotal={(t) => `共 ${t} 张凭证`}
          onChange={(p, size) => {
            setPage(p)
            setPageSize(size)
          }}
        />
      </div>
    </div>
  )
}
