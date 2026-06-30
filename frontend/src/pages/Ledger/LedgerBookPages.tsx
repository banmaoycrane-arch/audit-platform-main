import { useEffect, useMemo, useState } from 'react'
import { Alert, Card, Col, Empty, Pagination, Row, Select, Statistic, Table, Typography, message } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import dayjs from 'dayjs'
import {
  api,
  type AccountingEntry,
  type ChartOfAccount,
  type TrialBalanceReport,
  type TrialBalanceRow,
  type VoucherCard,
} from '../../api/client'
import { PeriodSelector } from '../../components/PeriodSelector'
import { useAuthStore } from '../../stores/authStore'

const { Title, Paragraph } = Typography

type PeriodFilter = {
  organizationId: number | null
  periodId: number | null
}

const money = (value: number | null | undefined) => Number(value || 0).toLocaleString()

export function LedgerBooksPage() {
  const { currentLedgerId } = useAuthStore()
  const [vouchers, setVouchers] = useState<VoucherCard[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const currentMonth = dayjs().format('YYYY-MM')

  useEffect(() => {
    if (!currentLedgerId) {
      setVouchers([])
      setTotal(0)
      return
    }
    setLoading(true)
    api
      .queryVouchers({
        ledger_id: currentLedgerId,
        month: currentMonth,
        limit: 50,
        offset: (page - 1) * 50,
        include_lines: false,
      })
      .then((resp) => {
        setVouchers(resp.items)
        setTotal(resp.total)
      })
      .catch((error) => message.error(`加载凭证序时簿失败：${error instanceof Error ? error.message : String(error)}`))
      .finally(() => setLoading(false))
  }, [currentLedgerId, page, currentMonth])

  const voucherRows = useMemo(
    () =>
      vouchers.map((voucher) => ({
        key: `${voucher.voucher_no ?? ''}||${voucher.voucher_date ?? ''}`,
        voucher_no: voucher.voucher_no || '无凭证号',
        voucher_date: voucher.voucher_date || '-',
        summary: voucher.summary_preview || '-',
        line_count: voucher.line_count,
        debit_total: voucher.debit_total,
        credit_total: voucher.credit_total,
      })),
    [vouchers],
  )
  const debitTotal = voucherRows.reduce((sum, row) => sum + row.debit_total, 0)
  const creditTotal = voucherRows.reduce((sum, row) => sum + row.credit_total, 0)

  return (
    <div>
      <Title level={3}>账簿管理</Title>
      <Paragraph type="secondary">
        凭证序时簿默认展示本月凭证（{currentMonth}），分页加载，避免一次拉取全账簿。
      </Paragraph>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={8}><Card><Statistic title="本月凭证张数" value={total} /></Card></Col>
        <Col span={8}><Card><Statistic title="本页借方合计" value={debitTotal} prefix="¥" /></Card></Col>
        <Col span={8}><Card><Statistic title="本页贷方合计" value={creditTotal} prefix="¥" /></Card></Col>
      </Row>
      {Math.round((debitTotal - creditTotal) * 100) !== 0 && (
        <Alert type="warning" showIcon title="本页凭证借贷合计不平衡（可能因分页仅展示部分凭证）" style={{ marginBottom: 16 }} />
      )}
      <Card title="凭证序时簿">
        <Table
          rowKey="key"
          loading={loading}
          dataSource={voucherRows}
          size="small"
          pagination={false}
          columns={[
            { title: '日期', dataIndex: 'voucher_date', key: 'voucher_date', width: 120 },
            { title: '凭证号', dataIndex: 'voucher_no', key: 'voucher_no', width: 150 },
            { title: '摘要', dataIndex: 'summary', key: 'summary' },
            { title: '分录行数', dataIndex: 'line_count', key: 'line_count', width: 90 },
            { title: '借方合计', dataIndex: 'debit_total', key: 'debit_total', width: 120, render: money },
            { title: '贷方合计', dataIndex: 'credit_total', key: 'credit_total', width: 120, render: money },
          ]}
        />
        <div style={{ marginTop: 16, textAlign: 'right' }}>
          <Pagination
            current={page}
            pageSize={50}
            total={total}
            showSizeChanger={false}
            showTotal={(t) => `共 ${t} 张凭证`}
            onChange={setPage}
          />
        </div>
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
  const [accounts, setAccounts] = useState<ChartOfAccount[]>([])
  const [selectedAccountCode, setSelectedAccountCode] = useState<string | undefined>()
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    api.listChartOfAccounts()
      .then(setAccounts)
      .catch(() => setAccounts([]))
  }, [])

  useEffect(() => {
    setPage(1)
  }, [selectedAccountCode, currentLedgerId])

  useEffect(() => {
    if (!currentLedgerId || !selectedAccountCode) {
      setEntries([])
      setTotal(0)
      return
    }
    setLoading(true)
    api
      .listChronologicalEntries({
        ledger_id: currentLedgerId,
        account_code: selectedAccountCode,
        limit: 50,
        offset: (page - 1) * 50,
      })
      .then((resp) => {
        setEntries(resp.items)
        setTotal(resp.total)
      })
      .catch((error) => message.error(`加载明细账失败：${error instanceof Error ? error.message : String(error)}`))
      .finally(() => setLoading(false))
  }, [currentLedgerId, selectedAccountCode, page])

  const accountOptions = useMemo(
    () => accounts.map((account) => ({ value: account.code, label: `${account.code} ${account.name}` })),
    [accounts],
  )

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
      <Paragraph type="secondary">请先选择科目，系统将按科目分页加载分录流水，避免一次加载全账簿。</Paragraph>
      <Card style={{ marginBottom: 16 }}>
        <Select
          allowClear
          showSearch
          value={selectedAccountCode}
          style={{ width: 320 }}
          placeholder="请选择科目"
          options={accountOptions}
          onChange={setSelectedAccountCode}
          optionFilterProp="label"
        />
      </Card>
      <Card>
        {!selectedAccountCode ? (
          <Empty description="请选择科目后查看明细账" />
        ) : (
          <>
            <Table<AccountingEntry>
              rowKey="id"
              loading={loading}
              dataSource={entries}
              columns={columns}
              size="small"
              pagination={false}
            />
            <div style={{ marginTop: 16, textAlign: 'right' }}>
              <Pagination
                current={page}
                pageSize={50}
                total={total}
                showSizeChanger={false}
                showTotal={(t) => `共 ${t} 条分录`}
                onChange={setPage}
              />
            </div>
          </>
        )}
      </Card>
    </div>
  )
}
