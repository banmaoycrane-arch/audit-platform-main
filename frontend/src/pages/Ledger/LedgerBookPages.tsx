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
    const key = entry.voucher_no || `鏈紪鍙?${entry.id}`
    grouped.set(key, [...(grouped.get(key) || []), entry])
  })
  return Array.from(grouped.entries()).map(([voucherNo, lines]) => {
    const debitTotal = lines.reduce((sum, line) => sum + Number(line.debit_amount || 0), 0)
    const creditTotal = lines.reduce((sum, line) => sum + Number(line.credit_amount || 0), 0)
    return {
      voucher_no: voucherNo,
      voucher_date: lines[0]?.voucher_date || '-',
      summary: lines.map((line) => line.summary).filter(Boolean).join('锛?),
      debit_total: debitTotal,
      credit_total: creditTotal,
      line_count: lines.length,
      review_status: lines.every((line) => line.review_status === 'verified' || line.review_status === 'ready') ? '宸插鏍? : '寰呭鏍?,
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
      .catch((error) => message.error(`鍔犺浇鍑瘉搴忔椂绨垮け璐ワ細${error instanceof Error ? error.message : String(error)}`))
      .finally(() => setLoading(false))
  }, [currentLedgerId])

  const voucherRows = useMemo(() => groupVoucherEntries(entries), [entries])
  const debitTotal = voucherRows.reduce((sum, row) => sum + row.debit_total, 0)
  const creditTotal = voucherRows.reduce((sum, row) => sum + row.credit_total, 0)

  return (
    <div>
      <Title level={3}>璐︾翱绠＄悊</Title>
      <Paragraph type="secondary">鍑瘉搴忔椂绨挎寜鍑瘉鍙锋眹鎬诲垎褰曪紝鏄€昏处鍜屾槑缁嗚处杩芥函鍑瘉鐨勫叆鍙ｃ€?/Paragraph>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={8}><Card><Statistic title="鍑瘉寮犳暟" value={voucherRows.length} /></Card></Col>
        <Col span={8}><Card><Statistic title="鍊熸柟鍚堣" value={debitTotal} prefix="楼" /></Card></Col>
        <Col span={8}><Card><Statistic title="璐锋柟鍚堣" value={creditTotal} prefix="楼" /></Card></Col>
      </Row>
      {Math.round((debitTotal - creditTotal) * 100) !== 0 && (
        <Alert type="error" showIcon title="鍑瘉搴忔椂绨垮€熻捶鍚堣涓嶅钩琛? style={{ marginBottom: 16 }} />
      )}
      <Card title="鍑瘉搴忔椂绨?>
        <Table
          rowKey="voucher_no"
          loading={loading}
          dataSource={voucherRows}
          size="small"
          pagination={{ pageSize: 20 }}
          columns={[
            { title: '鏃ユ湡', dataIndex: 'voucher_date', key: 'voucher_date', width: 120 },
            { title: '鍑瘉鍙?, dataIndex: 'voucher_no', key: 'voucher_no', width: 150 },
            { title: '鎽樿', dataIndex: 'summary', key: 'summary' },
            { title: '鍒嗗綍琛屾暟', dataIndex: 'line_count', key: 'line_count', width: 90 },
            { title: '鍊熸柟鍚堣', dataIndex: 'debit_total', key: 'debit_total', width: 120, render: money },
            { title: '璐锋柟鍚堣', dataIndex: 'credit_total', key: 'credit_total', width: 120, render: money },
            { title: '澶嶆牳鐘舵€?, dataIndex: 'review_status', key: 'review_status', width: 100 },
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
      .catch((error) => message.error(`鍔犺浇鎬昏处澶辫触锛?{error instanceof Error ? error.message : String(error)}`))
      .finally(() => setLoading(false))
  }, [filter])

  return (
    <div>
      <Title level={3}>鎬昏处</Title>
      <Paragraph type="secondary">鎬昏处鎸夌鐩眹鎬绘湡鍒濅綑棰濄€佹湰鏈熷彂鐢熼鍜屾湡鏈綑棰濄€?/Paragraph>
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
            { title: '绉戠洰缂栫爜', dataIndex: 'account_code', key: 'account_code', width: 100 },
            { title: '绉戠洰鍚嶇О', dataIndex: 'account_name', key: 'account_name' },
            { title: '鏈熷垵鍊熸柟', dataIndex: 'opening_debit', key: 'opening_debit', render: money },
            { title: '鏈熷垵璐锋柟', dataIndex: 'opening_credit', key: 'opening_credit', render: money },
            { title: '鏈湡鍊熸柟', dataIndex: 'period_debit', key: 'period_debit', render: money },
            { title: '鏈湡璐锋柟', dataIndex: 'period_credit', key: 'period_credit', render: money },
            { title: '鏈熸湯鍊熸柟', dataIndex: 'closing_debit', key: 'closing_debit', render: money },
            { title: '鏈熸湯璐锋柟', dataIndex: 'closing_credit', key: 'closing_credit', render: money },
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
      .catch((error) => message.error(`鍔犺浇鏄庣粏璐﹀け璐ワ細${error instanceof Error ? error.message : String(error)}`))
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
    { title: '鏃ユ湡', dataIndex: 'voucher_date', key: 'voucher_date', width: 110, render: (v) => v || '-' },
    { title: '鍑瘉鍙?, dataIndex: 'voucher_no', key: 'voucher_no', width: 130, render: (v) => v || '-' },
    { title: '鎽樿', dataIndex: 'summary', key: 'summary' },
    { title: '绉戠洰缂栫爜', dataIndex: 'account_code', key: 'account_code', width: 100 },
    { title: '绉戠洰鍚嶇О', dataIndex: 'account_name', key: 'account_name', width: 140 },
    { title: '鍊熸柟閲戦', dataIndex: 'debit_amount', key: 'debit_amount', width: 120, render: money },
    { title: '璐锋柟閲戦', dataIndex: 'credit_amount', key: 'credit_amount', width: 120, render: money },
    { title: '寰€鏉ュ崟浣?, dataIndex: 'counterparty', key: 'counterparty', width: 140, render: (v) => v || '-' },
  ]

  return (
    <div>
      <Title level={3}>鏄庣粏璐?/Title>
      <Paragraph type="secondary">鏄庣粏璐︽寜绉戠洰灞曠ず閫愮瑪鍒嗗綍娴佹按锛岀敤浜庤拷鏌ュ嚟璇併€佸線鏉ュ崟浣嶅拰涓氬姟鏉ユ簮銆?/Paragraph>
      <Card style={{ marginBottom: 16 }}>
        <Select
          allowClear
          showSearch
          value={selectedAccountCode}
          style={{ width: 320 }}
          placeholder="璇烽€夋嫨绉戠洰锛岀暀绌哄垯鏄剧ず鍏ㄩ儴"
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
