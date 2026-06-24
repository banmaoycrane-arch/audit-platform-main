import { useEffect, useMemo, useState } from 'react'
import { Alert, Card, Col, Row, Select, Statistic, Table, Typography, message } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { api, type AccountingEntry, type TrialBalanceReport, type TrialBalanceRow } from '../../api/client'
import { PeriodSelector } from '../../components/PeriodSelector'
import { useAuthStore } from '../../stores/authStore'

const { Title, Paragraph } = Typography

type PeriodFilter = {
  organizationId: number | null
  periodId: number | null
}

const money = (value: number | null | undefined) => Number(value || 0).toLocaleString()

function groupVoucherEntries(entries: AccountingEntry[]) {
  const grouped = new Map<string, AccountingEntry[]>()
  entries.forEach((entry) => {
    const key = entry.voucher_no || `未编号-${entry.id}`
    grouped.set(key, [...(grouped.get(key) || []), entry])
  })
  return Array.from(grouped.entries()).map(([voucherNo, lines]) => {
    const debitTotal = lines.reduce((sum, line) => sum + Number(line.debit_amount || 0), 0)
    const creditTotal = lines.reduce((sum, line) => sum + Number(line.credit_amount || 0), 0)
    return {
      voucher_no: voucherNo,
      voucher_date: lines[0]?.voucher_date || '-',
      summary: lines.map((line) => line.summary).filter(Boolean).join('；'),
      debit_total: debitTotal,
      credit_total: creditTotal,
      line_count: lines.length,
      review_status: lines.every((line) => line.review_status === 'verified' || line.review_status === 'ready') ? '已复核' : '待复核',
    }
  })
}

export function LedgerBooksPage() {
  const { currentLedgerId } = useAuthStore()
  const [entries, setEntries] = useState<AccountingEntry[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!currentLedgerId) {
      setEntries([])
      return
    }
    setLoading(true)
    api.listEntries(undefined, currentLedgerId)
      .then(setEntries)
      .catch((error) => message.error(`加载凭证序时簿失败：${error instanceof Error ? error.message : String(error)}`))
      .finally(() => setLoading(false))
  }, [currentLedgerId])

  const voucherRows = useMemo(() => groupVoucherEntries(entries), [entries])
  const debitTotal = voucherRows.reduce((sum, row) => sum + row.debit_total, 0)
  const creditTotal = voucherRows.reduce((sum, row) => sum + row.credit_total, 0)

  return (
    <div>
      <Title level={3}>账簿管理</Title>
      <Paragraph type="secondary">凭证序时簿按凭证号汇总分录，是总账和明细账追溯凭证的入口。</Paragraph>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={8}><Card><Statistic title="凭证张数" value={voucherRows.length} /></Card></Col>
        <Col span={8}><Card><Statistic title="借方合计" value={debitTotal} prefix="¥" /></Card></Col>
        <Col span={8}><Card><Statistic title="贷方合计" value={creditTotal} prefix="¥" /></Card></Col>
      </Row>
      {Math.round((debitTotal - creditTotal) * 100) !== 0 && (
        <Alert type="error" showIcon title="凭证序时簿借贷合计不平衡" style={{ marginBottom: 16 }} />
      )}
      <Card title="凭证序时簿">
        <Table
          rowKey="voucher_no"
          loading={loading}
          dataSource={voucherRows}
          size="small"
          pagination={{ pageSize: 20 }}
          columns={[
            { title: '日期', dataIndex: 'voucher_date', key: 'voucher_date', width: 120 },
            { title: '凭证号', dataIndex: 'voucher_no', key: 'voucher_no', width: 150 },
            { title: '摘要', dataIndex: 'summary', key: 'summary' },
            { title: '分录行数', dataIndex: 'line_count', key: 'line_count', width: 90 },
            { title: '借方合计', dataIndex: 'debit_total', key: 'debit_total', width: 120, render: money },
            { title: '贷方合计', dataIndex: 'credit_total', key: 'credit_total', width: 120, render: money },
            { title: '复核状态', dataIndex: 'review_status', key: 'review_status', width: 100 },
          ]}
        />
      </Card>
    </div>
  )
}

export function GeneralLedgerPage() {
  const { currentLedgerId } = useAuthStore()
  const [filter, setFilter] = useState<PeriodFilter>({ organizationId: null, periodId: null })
  const [report, setReport] = useState<TrialBalanceReport | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!filter.organizationId || !filter.periodId) return
    setLoading(true)
    api.getTrialBalanceReport(filter.organizationId, filter.periodId)
      .then(setReport)
      .catch((error) => message.error(`加载总账失败：${error instanceof Error ? error.message : String(error)}`))
      .finally(() => setLoading(false))
  }, [filter])

  return (
    <div>
      <Title level={3}>总账</Title>
      <Paragraph type="secondary">总账按科目汇总期初余额、本期发生额和期末余额。</Paragraph>
      <Card style={{ marginBottom: 16 }}>
        <PeriodSelector ledgerId={currentLedgerId} value={filter} onChange={setFilter} />
      </Card>
      <Card>
        <Table<TrialBalanceRow>
          rowKey="account_code"
          loading={loading}
          dataSource={report?.rows || []}
          size="small"
          pagination={{ pageSize: 50 }}
          columns={[
            { title: '科目编码', dataIndex: 'account_code', key: 'account_code', width: 100 },
            { title: '科目名称', dataIndex: 'account_name', key: 'account_name' },
            { title: '期初借方', dataIndex: 'opening_debit', key: 'opening_debit', render: money },
            { title: '期初贷方', dataIndex: 'opening_credit', key: 'opening_credit', render: money },
            { title: '本期借方', dataIndex: 'period_debit', key: 'period_debit', render: money },
            { title: '本期贷方', dataIndex: 'period_credit', key: 'period_credit', render: money },
            { title: '期末借方', dataIndex: 'closing_debit', key: 'closing_debit', render: money },
            { title: '期末贷方', dataIndex: 'closing_credit', key: 'closing_credit', render: money },
          ]}
        />
      </Card>
    </div>
  )
}

export function SubsidiaryLedgerPage() {
  const { currentLedgerId } = useAuthStore()
  const [entries, setEntries] = useState<AccountingEntry[]>([])
  const [selectedAccountCode, setSelectedAccountCode] = useState<string | undefined>()
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!currentLedgerId) {
      setEntries([])
      return
    }
    setLoading(true)
    api.listEntries(undefined, currentLedgerId)
      .then(setEntries)
      .catch((error) => message.error(`加载明细账失败：${error instanceof Error ? error.message : String(error)}`))
      .finally(() => setLoading(false))
  }, [currentLedgerId])

  const accountOptions = useMemo(() => {
    const map = new Map<string, string>()
    entries.forEach((entry) => {
      if (entry.account_code) map.set(entry.account_code, entry.account_name || entry.account_code)
    })
    return Array.from(map.entries()).map(([code, name]) => ({ value: code, label: `${code} ${name}` }))
  }, [entries])

  const filteredEntries = selectedAccountCode
    ? entries.filter((entry) => entry.account_code === selectedAccountCode)
    : entries

  const columns: ColumnsType<AccountingEntry> = [
    { title: '日期', dataIndex: 'voucher_date', key: 'voucher_date', width: 110, render: (v) => v || '-' },
    { title: '凭证号', dataIndex: 'voucher_no', key: 'voucher_no', width: 130, render: (v) => v || '-' },
    { title: '摘要', dataIndex: 'summary', key: 'summary' },
    { title: '科目编码', dataIndex: 'account_code', key: 'account_code', width: 100 },
    { title: '科目名称', dataIndex: 'account_name', key: 'account_name', width: 140 },
    { title: '借方金额', dataIndex: 'debit_amount', key: 'debit_amount', width: 120, render: money },
    { title: '贷方金额', dataIndex: 'credit_amount', key: 'credit_amount', width: 120, render: money },
    { title: '往来单位', dataIndex: 'counterparty', key: 'counterparty', width: 140, render: (v) => v || '-' },
  ]

  return (
    <div>
      <Title level={3}>明细账</Title>
      <Paragraph type="secondary">明细账按科目展示逐笔分录流水，用于追查凭证、往来单位和业务来源。</Paragraph>
      <Card style={{ marginBottom: 16 }}>
        <Select
          allowClear
          showSearch
          value={selectedAccountCode}
          style={{ width: 320 }}
          placeholder="请选择科目，留空则显示全部"
          options={accountOptions}
          onChange={setSelectedAccountCode}
          optionFilterProp="label"
        />
      </Card>
      <Card>
        <Table<AccountingEntry>
          rowKey="id"
          loading={loading}
          dataSource={filteredEntries}
          columns={columns}
          size="small"
          pagination={{ pageSize: 50 }}
        />
      </Card>
    </div>
  )
}
