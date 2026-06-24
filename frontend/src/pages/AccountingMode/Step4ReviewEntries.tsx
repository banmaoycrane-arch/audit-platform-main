import { Card, Table, Button, Steps, Typography, Tag, Space, Checkbox, Input, Select, Alert, message } from 'antd'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { useEffect, useState } from 'react'
import type { ColumnsType } from 'antd/es/table'
import { api, type AccountingEntry, type AccountingEntryUpdate } from '../../api/client'
import { FlowNav } from '../../components/FlowNav'

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
  const [draftEdits, setDraftEdits] = useState<Record<number, AccountingEntryUpdate>>({})
  const [loading, setLoading] = useState(false)
  const [savingIds, setSavingIds] = useState<Set<number>>(new Set())
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const [batchStatus, setBatchStatus] = useState('verified')

  const loadEntries = async () => {
    if (!jobId) return
    setLoading(true)
    try {
      const list = await api.listEntries(jobId)
      setEntries(list)
      setDraftEdits({})
    } catch (error) {
      console.error('获取分录失败', error)
      message.error('获取分录失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadEntries()
  }, [jobId])

  const onSelectChange = (keys: React.Key[]) => {
    setSelectedRowKeys(keys)
  }

  const rowSelection = {
    selectedRowKeys,
    onChange: onSelectChange,
  }

  const isVerified = (entry: AccountingEntry) => isVerifiedStatus(entry.review_status)

  const updateEntryStatus = async (entryId: number, reviewStatus: string) => {
    setSavingIds((prev) => new Set(prev).add(entryId))
    try {
      const updated = await api.reviewEntry(entryId, reviewStatus)
      setEntries((prev) => prev.map((item) => (item.id === entryId ? updated : item)))
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

  const getEntryValue = (entry: AccountingEntry, field: keyof AccountingEntryUpdate) => {
    const edited = draftEdits[entry.id]?.[field]
    return edited ?? entry[field]
  }

  const updateDraftEdit = (entryId: number, field: keyof AccountingEntryUpdate, value: string | number | null) => {
    setDraftEdits((prev) => ({
      ...prev,
      [entryId]: {
        ...(prev[entryId] || {}),
        [field]: value,
      },
    }))
  }

  const saveEntryEdit = async (entry: AccountingEntry) => {
    const edit = draftEdits[entry.id]
    if (!edit) return
    setSavingIds((prev) => new Set(prev).add(entry.id))
    try {
      const updated = await api.updateEntry(entry.id, edit)
      setEntries((prev) => prev.map((item) => (item.id === entry.id ? updated : item)))
      setDraftEdits((prev) => {
        const next = { ...prev }
        delete next[entry.id]
        return next
      })
      message.success('分录调整已保存')
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error)
      message.error(`保存分录调整失败：${detail}`)
    } finally {
      setSavingIds((prev) => {
        const next = new Set(prev)
        next.delete(entry.id)
        return next
      })
    }
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
      setSelectedRowKeys([])
      message.success(`已批量更新 ${ids.length} 条分录`)
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error)
      message.error(`批量复核失败：${detail}`)
    } finally {
      setLoading(false)
    }
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
      render: (_val: string | null, record: AccountingEntry) => (
        <Input
          value={String(getEntryValue(record, 'voucher_no') || '')}
          disabled={isVerified(record)}
          onChange={(event) => updateDraftEdit(record.id, 'voucher_no', event.target.value)}
        />
      ),
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
      render: (_val: string | null, record: AccountingEntry) => (
        <Input
          value={String(getEntryValue(record, 'voucher_date') || '')}
          disabled={isVerified(record)}
          placeholder="YYYY-MM-DD"
          onChange={(event) => updateDraftEdit(record.id, 'voucher_date', event.target.value)}
        />
      ),
    },
    {
      title: '科目代码',
      dataIndex: 'account_code',
      key: 'account_code',
      width: 110,
      render: (_val: string | null, record: AccountingEntry) => (
        <Input
          value={String(getEntryValue(record, 'account_code') || '')}
          disabled={isVerified(record)}
          onChange={(event) => updateDraftEdit(record.id, 'account_code', event.target.value)}
        />
      ),
    },
    {
      title: '科目名称',
      dataIndex: 'account_name',
      key: 'account_name',
      render: (_val: string | null, record: AccountingEntry) => (
        <Input
          value={String(getEntryValue(record, 'account_name') || '')}
          style={{ width: '150px' }}
          disabled={isVerified(record)}
          onChange={(event) => updateDraftEdit(record.id, 'account_name', event.target.value)}
        />
      ),
    },
    {
      title: '摘要',
      dataIndex: 'summary',
      key: 'summary',
      render: (_val: string | null, record: AccountingEntry) => (
        <Input
          value={String(getEntryValue(record, 'summary') || '')}
          disabled={isVerified(record)}
          onChange={(event) => updateDraftEdit(record.id, 'summary', event.target.value)}
        />
      ),
    },
    {
      title: '借方金额',
      dataIndex: 'debit_amount',
      key: 'debit_amount',
      width: 120,
      render: (_val: number, record: AccountingEntry) => (
        <Input
          type="number"
          value={Number(getEntryValue(record, 'debit_amount') || 0)}
          disabled={isVerified(record)}
          onChange={(event) => updateDraftEdit(record.id, 'debit_amount', Number(event.target.value || 0))}
        />
      ),
    },
    {
      title: '贷方金额',
      dataIndex: 'credit_amount',
      key: 'credit_amount',
      width: 120,
      render: (_val: number, record: AccountingEntry) => (
        <Input
          type="number"
          value={Number(getEntryValue(record, 'credit_amount') || 0)}
          disabled={isVerified(record)}
          onChange={(event) => updateDraftEdit(record.id, 'credit_amount', Number(event.target.value || 0))}
        />
      ),
    },
    {
      title: '对方单位',
      dataIndex: 'counterparty',
      key: 'counterparty',
      render: (_val: string | null, record: AccountingEntry) => (
        <Input
          value={String(getEntryValue(record, 'counterparty') || '')}
          disabled={isVerified(record)}
          onChange={(event) => updateDraftEdit(record.id, 'counterparty', event.target.value)}
        />
      ),
    },
    {
      title: '操作',
      key: 'action',
      fixed: 'right',
      width: 90,
      render: (_: unknown, record: AccountingEntry) => (
        <Button
          size="small"
          disabled={isVerified(record) || !draftEdits[record.id]}
          loading={savingIds.has(record.id)}
          onClick={() => void saveEntryEdit(record)}
        >
          保存
        </Button>
      ),
    },
  ]

  const verifiedCount = entries.filter((e) => isVerified(e)).length
  const allVerified = entries.length > 0 && verifiedCount === entries.length

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

      <FlowNav prev={stepPath(3)} onNext={goNext} nextDisabled={!jobId || entries.length === 0 || !allVerified} style={{ marginBottom: '16px' }} />

      <Space style={{ marginBottom: '16px', width: '100%', justifyContent: 'space-between' }}>
        <Title level={4} style={{ margin: 0 }}>复核调整待复核凭证草稿</Title>
        <Tag color={allVerified ? 'green' : 'blue'}>
          已复核 {verifiedCount}/{entries.length}
        </Tag>
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
            批量标记已复核 ({selectedRowKeys.length})
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
          pagination={{ pageSize: 10 }}
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
          disabled={!jobId || entries.length === 0 || !allVerified}
        >
          确认复核，进入确认入账与导出
        </Button>
      </div>
    </div>
  )
}
