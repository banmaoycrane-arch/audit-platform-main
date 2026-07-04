import { Card, Table, Button, Steps, Typography, Tag, Space, Checkbox, Input, Select, Alert, message, Modal } from 'antd'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { useEffect, useState } from 'react'
import type { TablePaginationConfig } from 'antd/es/table'
import type { ColumnsType } from 'antd/es/table'
import { api, type AccountingEntry } from '../../api/client'
import { FlowNav } from '../../components/FlowNav'
import { formatAmount } from '../../money'

const { Title } = Typography

const REVIEW_STATUS_LABEL: Record<string, string> = {
  draft: '待复核',
  verified: '已复核',
  ready: '待确认入账',
}

function isVerifiedStatus(status: string) {
  return status === 'verified' || status === 'ready'
}

export function Step4ReviewEntries() {
  const navigate = useNavigate()
  const location = useLocation()
  const stepPath = (step: number) => location.pathname.startsWith('/ledger/vouchers/step/') ? `/ledger/vouchers/step/${step}` : `/accounting/step/${step}`
  const [searchParams] = useSearchParams()
  const jobId = Number(searchParams.get('jobId') || 0)
  const periodId = Number(searchParams.get('periodId') || 0)
  const currentStep = 3

  const [entries, setEntries] = useState<AccountingEntry[]>([])
  const [entryTotal, setEntryTotal] = useState(0)
  const [verifiedTotal, setVerifiedTotal] = useState(0)
  const [readyTotal, setReadyTotal] = useState(0)
  const [unreviewedTotal, setUnreviewedTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(100)
  const [loading, setLoading] = useState(false)
  const [savingIds, setSavingIds] = useState<Set<number>>(new Set())
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const [batchStatus, setBatchStatus] = useState('verified')

  const loadReviewStats = async () => {
    if (!jobId) return
    const stats = await api.getEntryReviewStats(jobId)
    setEntryTotal(stats.total)
    setVerifiedTotal(stats.verified)
    setReadyTotal(stats.ready)
    setUnreviewedTotal(stats.unreviewed)
  }

  const loadEntries = async (nextPage = page, nextPageSize = pageSize) => {
    if (!jobId) return
    setLoading(true)
    try {
      const [result] = await Promise.all([
        api.listEntries(jobId, undefined, undefined, undefined, undefined, nextPageSize, (nextPage - 1) * nextPageSize),
        loadReviewStats(),
      ])
      setEntries(result.items)
      setEntryTotal(result.total)
    } catch (error) {
      console.error('获取分录失败', error)
      message.error('获取分录失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadEntries(1, pageSize)
    setPage(1)
  }, [jobId])

  const onSelectChange = (keys: React.Key[]) => {
    setSelectedRowKeys(keys)
  }

  const rowSelection = {
    selectedRowKeys,
    onChange: onSelectChange,
  }

  const handleTableChange = (pagination: TablePaginationConfig) => {
    const nextPage = pagination.current || 1
    const nextPageSize = pagination.pageSize || pageSize
    setPage(nextPage)
    setPageSize(nextPageSize)
    setSelectedRowKeys([])
    void loadEntries(nextPage, nextPageSize)
  }

  const isVerified = (entry: AccountingEntry) => isVerifiedStatus(entry.review_status)

  const updateEntryStatus = async (entryId: number, reviewStatus: string) => {
    setSavingIds((prev) => new Set(prev).add(entryId))
    try {
      const updated = await api.reviewEntry(entryId, reviewStatus)
      setEntries((prev) => prev.map((item) => (item.id === entryId ? updated : item)))
      await loadReviewStats()
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error)
      message.error(`更新复核状态失败：${detail}`)
    } finally {
      setSavingIds((prev) => {
        const next = new Set(prev)
        next.delete(entryId)
        return next
      })
    }
  }

  const toggleVerified = async (entry: AccountingEntry) => {
    const nextStatus = isVerified(entry) ? 'draft' : 'verified'
    await updateEntryStatus(entry.id, nextStatus)
  }

  const batchVerify = async () => {
    const ids = selectedRowKeys.map((key) => Number(key))
    if (ids.length === 0) return
    setLoading(true)
    try {
      await api.batchReviewEntries(ids, batchStatus)
      setEntries((prev) =>
        prev.map((item) => (ids.includes(item.id) ? { ...item, review_status: batchStatus } : item))
      )
      await loadReviewStats()
      setSelectedRowKeys([])
      message.success(`已批量更新 ${ids.length} 条分录`)
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error)
      message.error(`批量复核失败：${detail}`)
    } finally {
      setLoading(false)
    }
  }

  const reviewAll = () => {
    if (!jobId) return
    Modal.confirm({
      title: '确认全量更新复核状态？',
      content: `将把当前任务全部 ${entryTotal} 条分录标记为「${REVIEW_STATUS_LABEL[batchStatus] || batchStatus}」。该操作会影响所有分页，不只是当前页。`,
      okText: '确认更新全部',
      cancelText: '取消',
      onOk: async () => {
        setLoading(true)
        try {
          const result = await api.reviewAllJobEntries(jobId, batchStatus)
          await loadEntries(page, pageSize)
          setSelectedRowKeys([])
          message.success(`已全量更新 ${result.updated} 条分录`)
        } catch (error) {
          const detail = error instanceof Error ? error.message : String(error)
          message.error(`全量复核失败：${detail}`)
        } finally {
          setLoading(false)
        }
      },
    })
  }

  const columns: ColumnsType<AccountingEntry> = [
    {
      title: '状态',
      key: 'verified',
      width: 80,
      render: (_: unknown, record: AccountingEntry) => (
        <Checkbox
          checked={isVerified(record)}
          disabled={savingIds.has(record.id)}
          onChange={() => void toggleVerified(record)}
        />
      ),
    },
    {
      title: '复核',
      dataIndex: 'review_status',
      key: 'review_status',
      width: 110,
      render: (status: string) => (
        <Tag color={status === 'verified' ? 'green' : status === 'ready' ? 'blue' : 'default'}>
          {REVIEW_STATUS_LABEL[status] || status}
        </Tag>
      ),
    },
    {
      title: '凭证号',
      dataIndex: 'voucher_no',
      key: 'voucher_no',
      render: (val: string | null) => val || '-',
    },
    {
      title: '行号',
      dataIndex: 'entry_line_no',
      key: 'entry_line_no',
    },
    {
      title: '日期',
      dataIndex: 'voucher_date',
      key: 'voucher_date',
      render: (val: string | null) => val || '-',
    },
    {
      title: '科目',
      dataIndex: 'account_name',
      key: 'account_name',
      render: (val: string | null, record: AccountingEntry) => (
        <Input
          defaultValue={val || ''}
          style={{ width: '150px' }}
          disabled={isVerified(record)}
        />
      ),
    },
    {
      title: '摘要',
      dataIndex: 'summary',
      key: 'summary',
      render: (val: string | null, record: AccountingEntry) => (
        <Input
          defaultValue={val || ''}
          disabled={isVerified(record)}
        />
      ),
    },
    {
      title: '借方金额',
      dataIndex: 'debit_amount',
      key: 'debit_amount',
      render: (val: number) => (val > 0 ? formatAmount(val) : '-'),
    },
    {
      title: '贷方金额',
      dataIndex: 'credit_amount',
      key: 'credit_amount',
      render: (val: number) => (val > 0 ? formatAmount(val) : '-'),
    },
    {
      title: '对方单位',
      dataIndex: 'counterparty',
      key: 'counterparty',
      render: (val: string | null) => val || '-',
    },
  ]

  const verifiedCount = verifiedTotal + readyTotal
  const allVerified = entryTotal > 0 && unreviewedTotal === 0

  const goPrev = () => {
    const params = new URLSearchParams()
    if (jobId) params.set('jobId', String(jobId))
    if (periodId) params.set('periodId', String(periodId))
    const qs = params.toString()
    navigate(qs ? `${stepPath(3)}?${qs}` : stepPath(3))
  }

  const goNext = () => {
    if (!jobId) return
    const params = new URLSearchParams()
    params.set('jobId', String(jobId))
    if (periodId) params.set('periodId', String(periodId))
    navigate(`${stepPath(5)}?${params.toString()}`)
  }

  return (
    <div style={{ padding: '24px', maxWidth: '1000px', margin: '0 auto' }}>
      <Steps
        current={currentStep}
        items={[
          { title: '选择类型' },
          { title: '导入资料' },
          { title: '生成草稿' },
          { title: '复核调整' },
          { title: '确认入账与导出' },
        ]}
        style={{ marginBottom: '32px' }}
      />

      <FlowNav prev={stepPath(3)} onNext={goNext} nextDisabled={!jobId || entryTotal === 0 || !allVerified} style={{ marginBottom: '16px' }} />

      <Space style={{ marginBottom: '16px', width: '100%', justifyContent: 'space-between' }}>
        <Title level={4} style={{ margin: 0 }}>复核调整待复核凭证草稿</Title>
        <Tag color={allVerified ? 'green' : 'blue'}>
          已复核 {verifiedCount}/{entryTotal || entries.length}
        </Tag>
        {unreviewedTotal > 0 && <Tag color="orange">未复核 {unreviewedTotal}</Tag>}
      </Space>

      {!jobId && (
        <Alert
          title="尚未找到待复核凭证草稿"
          description="请从「生成草稿」步骤保存待复核凭证草稿后再进入本步骤。"
          type="warning"
          showIcon
          style={{ marginBottom: '16px' }}
        />
      )}

      <Card loading={loading}>
        <Alert
          title="当前步骤用于复核调整待复核凭证草稿"
          description="请重点复核摘要、科目、金额、往来单位和借贷平衡；全部标记已复核后，可进入确认入账与导出步骤。复核状态会保存到服务器。"
          type="info"
          showIcon
          style={{ marginBottom: '16px' }}
        />
        <div style={{ marginBottom: '16px', display: 'flex', gap: '12px', alignItems: 'center' }}>
          <Button
            type="primary"
            onClick={() => void batchVerify()}
            disabled={selectedRowKeys.length === 0}
          >
            批量标记当前选择 ({selectedRowKeys.length})
          </Button>
          <Button
            danger={batchStatus === 'draft'}
            onClick={reviewAll}
            disabled={!jobId || entryTotal === 0}
          >
            全量标记全部 {entryTotal} 条
          </Button>
          <Select value={batchStatus} onChange={setBatchStatus} style={{ width: 150 }}>
            <Select.Option value="draft">待复核</Select.Option>
            <Select.Option value="verified">已复核</Select.Option>
            <Select.Option value="ready">待确认入账与导出</Select.Option>
          </Select>
        </div>

        <Table
          rowSelection={rowSelection}
          columns={columns}
          dataSource={entries}
          rowKey="id"
          pagination={{
            current: page,
            pageSize,
            total: entryTotal,
            showSizeChanger: true,
            pageSizeOptions: ['50', '100', '200', '500'],
            showTotal: (total, range) => `第 ${range[0]}-${range[1]} 条 / 共 ${total} 条`,
          }}
          onChange={handleTableChange}
          scroll={{ x: 1300, y: 560 }}
          size="small"
          locale={{ emptyText: jobId ? '暂无待复核凭证草稿，请先在上一步生成并保存草稿' : '请先选择或生成待复核凭证草稿' }}
        />
      </Card>

      <div style={{ marginTop: '24px', display: 'flex', gap: '12px' }}>
        <Button onClick={goPrev}>
          上一步
        </Button>
        <Button
          type="primary"
          onClick={goNext}
          disabled={!jobId || entryTotal === 0 || !allVerified}
        >
          确认复核，进入确认入账与导出
        </Button>
      </div>
    </div>
  )
}
