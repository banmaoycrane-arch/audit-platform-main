import { memo, useCallback, useEffect, useMemo, useState } from 'react'
import {
  Button,
  Card,
  Checkbox,
  Col,
  DatePicker,
  Form,
  Input,
  InputNumber,
  Modal,
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
import { DeleteOutlined, FileSearchOutlined, ReloadOutlined, SearchOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import {
  api,
  type AccountingEntry,
  type AccountingPeriod,
  type VoucherCard,
  type VoucherDeleteKey,
  type VoucherQueryFilters,
} from '../api/client'
import { useAuthStore } from '../stores/authStore'

type VoucherQueryFilterState = Omit<VoucherQueryFilters, 'ledger_id'>

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

function voucherSelectionKey(voucher: Pick<VoucherCard, 'voucher_no' | 'voucher_date'>) {
  return `${voucher.voucher_no ?? ''}||${voucher.voucher_date ?? ''}`
}

function toDeleteKey(voucher: Pick<VoucherCard, 'voucher_no' | 'voucher_date'>): VoucherDeleteKey {
  return {
    voucher_no: voucher.voucher_no,
    voucher_date: voucher.voucher_date,
  }
}

function voucherDisplayLabel(voucher: Pick<VoucherCard, 'voucher_no' | 'voucher_date'>) {
  const no = voucher.voucher_no || '无凭证号'
  const dt = voucher.voucher_date || '无日期'
  return `${no}（${dt}）`
}

function buildFiltersFromForm(values: FilterFormValues): VoucherQueryFilterState {
  const next: VoucherQueryFilterState = {
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
  return next
}

function hasScopeFilter(filters: VoucherQueryFilterState) {
  return Boolean(
    filters.period_id
    || filters.month
    || filters.date_from
    || filters.date_to
    || filters.account_code
    || filters.account_name
    || filters.summary
    || filters.voucher_word
    || filters.voucher_no
    || filters.debit_min != null
    || filters.debit_max != null
    || filters.credit_min != null
    || filters.credit_max != null
    || filters.total_min != null
    || filters.total_max != null,
  )
}

const VOUCHER_LINE_COLUMNS: ColumnsType<AccountingEntry> = [
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

const DEFAULT_FILTER_VALUES: FilterFormValues = {
  date_mode: 'month',
  filter_mode: 'line',
  month: dayjs(),
}

type VoucherCardViewProps = {
  voucher: VoucherCard
  selected: boolean
  deleting: boolean
  linesExpanded: boolean
  linesLoading: boolean
  lines: AccountingEntry[] | undefined
  onToggleSelect: (key: string, checked: boolean) => void
  onToggleLines: (voucher: VoucherCard) => void
  onDelete: (voucher: VoucherCard) => void
}

const VoucherCardView = memo(function VoucherCardView({
  voucher,
  selected,
  deleting,
  linesExpanded,
  linesLoading,
  lines,
  onToggleSelect,
  onToggleLines,
  onDelete,
}: VoucherCardViewProps) {
  const selectionKey = voucherSelectionKey(voucher)

  return (
    <Card
      size="small"
      title={
        <Space wrap>
          <Checkbox
            checked={selected}
            onChange={(event) => onToggleSelect(selectionKey, event.target.checked)}
          />
          <Text strong>{voucher.voucher_date || '无日期'}</Text>
          {voucher.voucher_word && <Tag color="blue">{voucher.voucher_word}</Tag>}
          <Text>{voucher.voucher_no || '无凭证号'}</Text>
        </Space>
      }
      extra={
        <Space wrap>
          <Text type="secondary">{voucher.line_count} 行</Text>
          <Text>借 {formatMoney(voucher.debit_total)}</Text>
          <Text>贷 {formatMoney(voucher.credit_total)}</Text>
          <Button size="small" loading={linesLoading} onClick={() => onToggleLines(voucher)}>
            {linesExpanded ? '收起分录' : '展开分录'}
          </Button>
          <Button
            danger
            size="small"
            icon={<DeleteOutlined />}
            loading={deleting}
            onClick={() => onDelete(voucher)}
          >
            删除凭证
          </Button>
        </Space>
      }
    >
      {voucher.summary_preview && (
        <Paragraph type="secondary" style={{ marginBottom: linesExpanded ? 8 : 0 }}>
          摘要：{voucher.summary_preview}
        </Paragraph>
      )}
      {linesExpanded && (
        <Table
          rowKey="id"
          size="small"
          pagination={false}
          loading={linesLoading && !lines}
          columns={VOUCHER_LINE_COLUMNS}
          dataSource={lines || []}
          scroll={{ x: 720 }}
        />
      )}
    </Card>
  )
})

export function VoucherQueryPage() {
  const { currentLedgerId } = useAuthStore()
  const [form] = Form.useForm<FilterFormValues>()
  const dateMode = Form.useWatch('date_mode', form) || 'day'
  const filterMode = Form.useWatch('filter_mode', form) || 'line'
  const [periods, setPeriods] = useState<AccountingPeriod[]>([])
  const [vouchers, setVouchers] = useState<VoucherCard[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [deletingKey, setDeletingKey] = useState<string | null>(null)
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set())
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(6)
  const [appliedFilters, setAppliedFilters] = useState<VoucherQueryFilterState | null>(null)
  const [expandedLineKeys, setExpandedLineKeys] = useState<Set<string>>(new Set())
  const [linesCache, setLinesCache] = useState<Record<string, AccountingEntry[]>>({})
  const [linesLoadingKeys, setLinesLoadingKeys] = useState<Set<string>>(new Set())

  useEffect(() => {
    if (!currentLedgerId) {
      setPeriods([])
      setAppliedFilters(null)
      setVouchers([])
      setTotal(0)
      setSelectedKeys(new Set())
      setExpandedLineKeys(new Set())
      setLinesCache({})
      setLinesLoadingKeys(new Set())
      return
    }
    api.listAccountingPeriods(undefined, currentLedgerId).then(setPeriods).catch(() => setPeriods([]))
    setAppliedFilters(null)
    setVouchers([])
    setTotal(0)
    setPage(1)
    setSelectedKeys(new Set())
    setExpandedLineKeys(new Set())
    setLinesCache({})
    setLinesLoadingKeys(new Set())
  }, [currentLedgerId])

  const loadVouchers = useCallback(async () => {
    if (!currentLedgerId || appliedFilters === null) {
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
        include_lines: false,
        ...appliedFilters,
      })
      setVouchers(resp.items)
      setTotal(resp.total)
      setExpandedLineKeys(new Set())
      setLinesCache({})
      setLinesLoadingKeys(new Set())
      setSelectedKeys((prev) => {
        const next = new Set<string>()
        for (const item of resp.items) {
          const key = voucherSelectionKey(item)
          if (prev.has(key)) next.add(key)
        }
        return next
      })
    } catch (error) {
      message.error(error instanceof Error ? error.message : '凭证查询失败')
      setVouchers([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }, [currentLedgerId, appliedFilters, page, pageSize])

  useEffect(() => {
    loadVouchers()
  }, [loadVouchers])

  const pageKeys = useMemo(() => vouchers.map(voucherSelectionKey), [vouchers])
  const allPageSelected = pageKeys.length > 0 && pageKeys.every((key) => selectedKeys.has(key))
  const somePageSelected = pageKeys.some((key) => selectedKeys.has(key))

  const applySearch = (next: VoucherQueryFilterState) => {
    setPage(1)
    setAppliedFilters(next)
    setSelectedKeys(new Set())
    setExpandedLineKeys(new Set())
    setLinesCache({})
    setLinesLoadingKeys(new Set())
  }

  const handleSearch = async () => {
    const values = await form.validateFields()
    const next = buildFiltersFromForm(values)
    if (!hasScopeFilter(next)) {
      Modal.confirm({
        title: '查询全部凭证',
        content: '未设置日期、期间或科目等筛选条件，将查询账簿内全部凭证，数据量大时可能较慢。是否继续？',
        okText: '继续查询',
        cancelText: '取消',
        onOk: () => applySearch(next),
      })
      return
    }
    applySearch(next)
  }

  const handleReset = () => {
    form.setFieldsValue(DEFAULT_FILTER_VALUES)
    setPage(1)
    setAppliedFilters(null)
    setVouchers([])
    setTotal(0)
    setSelectedKeys(new Set())
    setExpandedLineKeys(new Set())
    setLinesCache({})
    setLinesLoadingKeys(new Set())
  }

  const toggleLineDetails = useCallback(async (voucher: VoucherCard) => {
    if (!currentLedgerId) return
    const key = voucherSelectionKey(voucher)
    if (expandedLineKeys.has(key)) {
      setExpandedLineKeys((prev) => {
        const next = new Set(prev)
        next.delete(key)
        return next
      })
      return
    }
    setExpandedLineKeys((prev) => new Set(prev).add(key))
    if (linesCache[key]) return
    setLinesLoadingKeys((prev) => new Set(prev).add(key))
    try {
      const resp = await api.getVoucherLines(currentLedgerId, voucher.voucher_no, voucher.voucher_date)
      setLinesCache((prev) => ({ ...prev, [key]: resp.items }))
    } catch (error) {
      message.error(error instanceof Error ? error.message : '加载分录明细失败')
      setExpandedLineKeys((prev) => {
        const next = new Set(prev)
        next.delete(key)
        return next
      })
    } finally {
      setLinesLoadingKeys((prev) => {
        const next = new Set(prev)
        next.delete(key)
        return next
      })
    }
  }, [currentLedgerId, expandedLineKeys, linesCache])

  const toggleSelect = useCallback((key: string, checked: boolean) => {
    setSelectedKeys((prev) => {
      const next = new Set(prev)
      if (checked) next.add(key)
      else next.delete(key)
      return next
    })
  }, [])

  const toggleSelectAllOnPage = (checked: boolean) => {
    setSelectedKeys((prev) => {
      const next = new Set(prev)
      for (const key of pageKeys) {
        if (checked) next.add(key)
        else next.delete(key)
      }
      return next
    })
  }

  const confirmDeleteVouchers = (targets: VoucherCard[]) => {
    if (!currentLedgerId || targets.length === 0) return
    const labels = targets.slice(0, 5).map(voucherDisplayLabel).join('、')
    const suffix = targets.length > 5 ? ` 等 ${targets.length} 张凭证` : ''
    Modal.confirm({
      title: targets.length === 1 ? '确认删除凭证' : `确认批量删除 ${targets.length} 张凭证`,
      content: (
        <div>
          <Paragraph>
            将整单删除凭证及其全部分录行（共 {targets.reduce((sum, item) => sum + item.line_count, 0)} 行），在同一事务中提交，避免只删部分行导致借贷不平衡。
          </Paragraph>
          <Text type="secondary">
            {labels}
            {suffix}
          </Text>
        </div>
      ),
      okText: '确认删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk: async () => {
        setDeleting(true)
        if (targets.length === 1) {
          setDeletingKey(voucherSelectionKey(targets[0]))
        }
        try {
          const result = await api.deleteVouchersBatch(
            currentLedgerId,
            targets.map(toDeleteKey),
          )
          message.success(`已删除 ${result.deleted_vouchers} 张凭证，共 ${result.deleted_entries} 行分录`)
          setSelectedKeys((prev) => {
            const next = new Set(prev)
            for (const target of targets) {
              next.delete(voucherSelectionKey(target))
            }
            return next
          })
          await loadVouchers()
        } catch (error) {
          message.error(error instanceof Error ? error.message : '删除凭证失败')
          throw error
        } finally {
          setDeleting(false)
          setDeletingKey(null)
        }
      },
    })
  }

  const handleDeleteOne = (voucher: VoucherCard) => {
    confirmDeleteVouchers([voucher])
  }

  const handleBatchDelete = () => {
    const targets = vouchers.filter((voucher) => selectedKeys.has(voucherSelectionKey(voucher)))
    if (targets.length === 0) {
      message.warning('请先勾选要删除的凭证')
      return
    }
    confirmDeleteVouchers(targets)
  }

  if (!currentLedgerId) {
    return (
      <div style={{ padding: 24 }}>
        <Title level={4}>凭证查询</Title>
        <Text type="secondary">请先在顶部切换账簿。</Text>
      </div>
    )
  }

  return (
    <div style={{ padding: 24 }}>
      <Title level={4} style={{ marginTop: 0 }}>
        <FileSearchOutlined /> 凭证查询
      </Title>
      <Paragraph type="secondary">
        请先设置查询条件并点击「查询」；页面不会自动加载全部凭证。结果以卡片形式分页展示，分录明细默认收起，需查看时再展开。
      </Paragraph>

      <Card size="small" title="查询条件" style={{ marginBottom: 16 }}>
        <Form
          form={form}
          layout="vertical"
          initialValues={DEFAULT_FILTER_VALUES}
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
            <Button icon={<ReloadOutlined />} onClick={loadVouchers} disabled={appliedFilters === null}>
              刷新
            </Button>
          </Space>
        </Form>
      </Card>

      {appliedFilters !== null && (
        <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
          <Space>
            <Checkbox
              checked={allPageSelected}
              indeterminate={!allPageSelected && somePageSelected}
              onChange={(event) => toggleSelectAllOnPage(event.target.checked)}
              disabled={vouchers.length === 0}
            >
              全选本页
            </Checkbox>
            <Text type="secondary">共找到 {total} 张凭证</Text>
            {selectedKeys.size > 0 && <Text>已选 {selectedKeys.size} 张</Text>}
          </Space>
          <Button
            danger
            icon={<DeleteOutlined />}
            disabled={selectedKeys.size === 0}
            loading={deleting && deletingKey === null}
            onClick={handleBatchDelete}
          >
            删除选中凭证
          </Button>
        </div>
      )}

      {loading ? (
        <Card loading />
      ) : appliedFilters === null ? (
        <Empty description="请设置查询条件后点击「查询」" />
      ) : vouchers.length === 0 ? (
        <Empty description="暂无符合条件的凭证" />
      ) : (
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          {vouchers.map((voucher) => {
            const key = voucherSelectionKey(voucher)
            return (
              <VoucherCardView
                key={key}
                voucher={voucher}
                selected={selectedKeys.has(key)}
                deleting={deleting && deletingKey === key}
                linesExpanded={expandedLineKeys.has(key)}
                linesLoading={linesLoadingKeys.has(key)}
                lines={linesCache[key]}
                onToggleSelect={toggleSelect}
                onToggleLines={toggleLineDetails}
                onDelete={handleDeleteOne}
              />
            )
          })}
        </Space>
      )}

      {appliedFilters !== null && (
        <div style={{ marginTop: 24, textAlign: 'right' }}>
          <Pagination
            current={page}
            pageSize={pageSize}
            total={total}
            showSizeChanger
            pageSizeOptions={['6', '10', '20', '50']}
            showTotal={(t) => `共 ${t} 张凭证`}
            onChange={(p, size) => {
              setPage(p)
              setPageSize(Math.min(size, 50))
            }}
          />
        </div>
      )}
    </div>
  )
}
