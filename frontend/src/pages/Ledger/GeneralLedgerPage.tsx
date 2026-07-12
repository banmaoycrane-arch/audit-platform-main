import { useCallback, useMemo, useState } from 'react'
import { Alert, Button, Card, Checkbox, Empty, Table, Typography, message } from 'antd'
import { useNavigate } from 'react-router-dom'
import { api, type TrialBalanceReport, type TrialBalanceRow } from '../../api/client'
import {
  LedgerReportFilterBar,
  type LedgerReportApplied,
} from '../../components/ledger/LedgerReportFilterBar'
import { useAuthStore } from '../../stores/authStore'
import { formatAmount } from '../../money'
import { buildGeneralLedgerGroups, rowHasBalance } from '../../utils/ledgerReportRows'

const { Title, Paragraph } = Typography

export function GeneralLedgerPage() {
  const navigate = useNavigate()
  const { currentLedgerId } = useAuthStore()
  const [applied, setApplied] = useState<LedgerReportApplied | null>(null)
  const [report, setReport] = useState<TrialBalanceReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [hideZeroBalance, setHideZeroBalance] = useState(true)

  const loadReport = useCallback((query: LedgerReportApplied) => {
    if (!currentLedgerId) return
    setLoading(true)
    void api
      .getTrialBalanceReport({
        ledgerId: currentLedgerId,
        periodId: query.periodId,
        asOfDate: query.asOfDate,
      })
      .then(setReport)
      .catch((error) => {
        message.error(`加载总账失败：${error instanceof Error ? error.message : String(error)}`)
        setReport(null)
      })
      .finally(() => setLoading(false))
  }, [currentLedgerId])

  const handleApply = (query: LedgerReportApplied) => {
    setApplied(query)
    loadReport(query)
  }

  const groupedRows = useMemo(() => {
    if (!report) return []
    const rows = hideZeroBalance ? report.rows.filter(rowHasBalance) : report.rows
    return buildGeneralLedgerGroups(rows)
  }, [report, hideZeroBalance])

  const openSubsidiary = (accountCode: string) => {
    if (!applied) return
    navigate('/ledger/subsidiary-ledger', {
      state: {
        accountCodes: [accountCode],
        periodIds: [applied.periodId],
        autoSearch: true,
      },
    })
  }

  return (
    <div>
      <Title level={3}>总账</Title>
      <Paragraph type="secondary">
        按一级科目汇总期初、本期发生与期末余额；开放期间默认展示截止今日的即时余额，已结账期间展示结账快照。
      </Paragraph>

      {!currentLedgerId ? (
        <Empty description="请先选择账簿" />
      ) : (
        <>
          <LedgerReportFilterBar ledgerId={currentLedgerId} applied={applied} onApply={handleApply} />

          {report && !report.is_balanced && (
            <Alert
              type="warning"
              showIcon
              style={{ marginBottom: 16 }}
              message="期末借贷不平衡"
              description={`借方 ${formatAmount(report.totals.closing_debit)}，贷方 ${formatAmount(report.totals.closing_credit)}`}
            />
          )}

          <Card
            title="总账汇总"
            extra={
              <Checkbox checked={hideZeroBalance} onChange={(e) => setHideZeroBalance(e.target.checked)}>
                仅显示有余额科目
              </Checkbox>
            }
          >
            {!applied ? (
              <Empty description="请选择期间并点击查询" />
            ) : (
              <Table
                rowKey="account_code"
                loading={loading}
                dataSource={groupedRows}
                size="small"
                pagination={{ pageSize: 50 }}
                expandable={{
                  rowExpandable: (row) => Boolean(row.isGroup && row.children && row.children.length > 1),
                  expandedRowRender: (row) =>
                    row.children ? (
                      <Table<TrialBalanceRow>
                        rowKey="account_code"
                        dataSource={row.children}
                        size="small"
                        pagination={false}
                        columns={detailColumns(openSubsidiary)}
                      />
                    ) : null,
                }}
                columns={[
                  { title: '科目编码', dataIndex: 'account_code', key: 'account_code', width: 110 },
                  { title: '科目名称', dataIndex: 'account_name', key: 'account_name' },
                  { title: '期初借方', dataIndex: 'opening_debit', key: 'opening_debit', render: (v: number) => formatAmount(v) },
                  { title: '期初贷方', dataIndex: 'opening_credit', key: 'opening_credit', render: (v: number) => formatAmount(v) },
                  { title: '本期借方', dataIndex: 'period_debit', key: 'period_debit', render: (v: number) => formatAmount(v) },
                  { title: '本期贷方', dataIndex: 'period_credit', key: 'period_credit', render: (v: number) => formatAmount(v) },
                  { title: '期末借方', dataIndex: 'closing_debit', key: 'closing_debit', render: (v: number) => formatAmount(v) },
                  { title: '期末贷方', dataIndex: 'closing_credit', key: 'closing_credit', render: (v: number) => formatAmount(v) },
                  {
                    title: '操作',
                    key: 'action',
                    width: 100,
                    render: (_: unknown, row) => (
                      <Button type="link" size="small" onClick={() => openSubsidiary(row.account_code)}>
                        明细账
                      </Button>
                    ),
                  },
                ]}
              />
            )}
          </Card>
        </>
      )}
    </div>
  )
}

function detailColumns(onDrill: (code: string) => void) {
  return [
    { title: '科目编码', dataIndex: 'account_code', key: 'account_code', width: 110 },
    { title: '科目名称', dataIndex: 'account_name', key: 'account_name' },
    { title: '期初借方', dataIndex: 'opening_debit', key: 'opening_debit', render: (v: number) => formatAmount(v) },
    { title: '期初贷方', dataIndex: 'opening_credit', key: 'opening_credit', render: (v: number) => formatAmount(v) },
    { title: '本期借方', dataIndex: 'period_debit', key: 'period_debit', render: (v: number) => formatAmount(v) },
    { title: '本期贷方', dataIndex: 'period_credit', key: 'period_credit', render: (v: number) => formatAmount(v) },
    { title: '期末借方', dataIndex: 'closing_debit', key: 'closing_debit', render: (v: number) => formatAmount(v) },
    { title: '期末贷方', dataIndex: 'closing_credit', key: 'closing_credit', render: (v: number) => formatAmount(v) },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_: unknown, row: TrialBalanceRow) => (
        <Button type="link" size="small" onClick={() => onDrill(row.account_code)}>
          明细账
        </Button>
      ),
    },
  ]
}
