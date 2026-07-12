import { useCallback, useMemo, useState } from 'react'
import { Alert, Button, Card, Checkbox, Empty, Table, Typography, message, Space } from 'antd'
import { DownloadOutlined, FilePdfOutlined } from '@ant-design/icons'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api, type TrialBalanceReport, type TrialBalanceRow } from '../../api/client'
import {
  LedgerReportFilterBar,
  type LedgerReportApplied,
} from '../../components/ledger/LedgerReportFilterBar'
import { ReportSignatureModal, type ReportSignatureForm } from '../../components/ledger/ReportSignatureModal'
import { useAuthStore } from '../../stores/authStore'
import { formatAmount } from '../../money'
import { rowHasBalance } from '../../utils/ledgerReportRows'
import { exportTrialBalanceCsv } from '../../utils/exportReportCsv'
import { downloadBlobWithDisposition } from '../../utils/downloadBlob'

const { Title, Paragraph } = Typography

const CATEGORY_LABEL: Record<string, string> = {
  asset: '资产',
  liability: '负债',
  common: '共同',
  equity: '权益',
  cost: '成本',
  profit: '损益',
}

export function TrialBalancePage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const urlPeriodId = Number(searchParams.get('period_id') || 0) || null
  const { currentLedgerId } = useAuthStore()
  const [applied, setApplied] = useState<LedgerReportApplied | null>(null)
  const [report, setReport] = useState<TrialBalanceReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [hideZeroBalance, setHideZeroBalance] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [pdfModalOpen, setPdfModalOpen] = useState(false)

  const handleExport = async (format: 'xlsx' | 'pdf', signature?: ReportSignatureForm) => {
    if (!applied || !currentLedgerId) return
    setExporting(true)
    try {
      const { blob, contentDisposition } = await api.exportTrialBalanceReport(
        {
          ledgerId: currentLedgerId,
          periodId: applied.periodId,
          asOfDate: applied.asOfDate,
          ...signature,
        },
        format,
      )
      const fallback = `trial_balance_${applied.period.period_code}.${format === 'pdf' ? 'pdf' : 'xlsx'}`
      await downloadBlobWithDisposition(blob, contentDisposition, fallback)
    } catch (err) {
      message.error(`导出失败：${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setExporting(false)
      setPdfModalOpen(false)
    }
  }

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
      .catch((err) => {
        message.error(`加载失败：${err instanceof Error ? err.message : String(err)}`)
        setReport(null)
      })
      .finally(() => setLoading(false))
  }, [currentLedgerId])

  const handleApply = (query: LedgerReportApplied) => {
    setApplied(query)
    loadReport(query)
  }

  const tableRows = useMemo(() => {
    if (!report) return []
    return hideZeroBalance ? report.rows.filter(rowHasBalance) : report.rows
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
      <Title level={3}>科目余额表</Title>
      <Paragraph type="secondary">
        展示全部科目的期初、本期发生、本年累计发生与期末十列余额；开放期间按截止日实时计算，已结账期间读取结账时固化的唯一快照。
      </Paragraph>

      {report?.snapshot_frozen && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          title="已结账期间 — 科目余额表已固化"
          description="本期发生额与本年累计发生额均为结账当日冻结口径，不可再通过系统修改。"
        />
      )}

      {!currentLedgerId ? (
        <Empty description="请先选择账簿" />
      ) : (
        <>
          <LedgerReportFilterBar
            ledgerId={currentLedgerId}
            applied={applied}
            onApply={handleApply}
            initialPeriodId={urlPeriodId}
          />

          {report && !report.is_balanced && (
            <Alert
              type="error"
              showIcon
              title="期末借贷不平衡"
              description={`借方合计 ${formatAmount(report.totals.closing_debit)}，贷方合计 ${formatAmount(report.totals.closing_credit)}`}
              style={{ marginBottom: 16 }}
            />
          )}

          <Card
            title="科目余额表"
            extra={
              <Space>
                {report && (
                  <>
                    <Button
                      size="small"
                      icon={<DownloadOutlined />}
                      loading={exporting}
                      onClick={() => void handleExport('xlsx')}
                    >
                      导出 Excel
                    </Button>
                    <Button
                      size="small"
                      icon={<FilePdfOutlined />}
                      onClick={() => setPdfModalOpen(true)}
                    >
                      签章 PDF
                    </Button>
                    <Button
                      size="small"
                      icon={<DownloadOutlined />}
                      onClick={() => exportTrialBalanceCsv(report)}
                    >
                      导出 CSV
                    </Button>
                  </>
                )}
                <Checkbox checked={hideZeroBalance} onChange={(e) => setHideZeroBalance(e.target.checked)}>
                  隐藏零余额科目
                </Checkbox>
              </Space>
            }
          >
            {!applied ? (
              <Empty description="请选择期间并点击查询" />
            ) : (
              <Table<TrialBalanceRow>
                rowKey="account_code"
                dataSource={tableRows}
                loading={loading}
                size="small"
                pagination={{ pageSize: 50 }}
                columns={[
                  { title: '科目编码', dataIndex: 'account_code', key: 'account_code', width: 90 },
                  { title: '科目名称', dataIndex: 'account_name', key: 'account_name' },
                  {
                    title: '科目类别',
                    dataIndex: 'category',
                    key: 'category',
                    render: (v: string) => CATEGORY_LABEL[v] || v,
                    width: 90,
                  },
                  { title: '期初借方余额', dataIndex: 'opening_debit', key: 'opening_debit', render: (v: number) => formatAmount(v) },
                  { title: '期初贷方余额', dataIndex: 'opening_credit', key: 'opening_credit', render: (v: number) => formatAmount(v) },
                  { title: '本期借方发生额', dataIndex: 'period_debit', key: 'period_debit', render: (v: number) => formatAmount(v) },
                  { title: '本期贷方发生额', dataIndex: 'period_credit', key: 'period_credit', render: (v: number) => formatAmount(v) },
                  { title: '本年借方累计', dataIndex: 'ytd_debit', key: 'ytd_debit', render: (v: number) => formatAmount(v) },
                  { title: '本年贷方累计', dataIndex: 'ytd_credit', key: 'ytd_credit', render: (v: number) => formatAmount(v) },
                  { title: '期末借方余额', dataIndex: 'closing_debit', key: 'closing_debit', render: (v: number) => formatAmount(v) },
                  { title: '期末贷方余额', dataIndex: 'closing_credit', key: 'closing_credit', render: (v: number) => formatAmount(v) },
                  {
                    title: '操作',
                    key: 'action',
                    width: 90,
                    render: (_: unknown, row) => (
                      <Button type="link" size="small" onClick={() => openSubsidiary(row.account_code)}>
                        明细
                      </Button>
                    ),
                  },
                ]}
                summary={() =>
                  report ? (
                    <Table.Summary.Row>
                      <Table.Summary.Cell index={0} colSpan={3}><strong>合计</strong></Table.Summary.Cell>
                      <Table.Summary.Cell index={1}><strong>{formatAmount(report.totals.opening_debit)}</strong></Table.Summary.Cell>
                      <Table.Summary.Cell index={2}><strong>{formatAmount(report.totals.opening_credit)}</strong></Table.Summary.Cell>
                      <Table.Summary.Cell index={3}><strong>{formatAmount(report.totals.period_debit)}</strong></Table.Summary.Cell>
                      <Table.Summary.Cell index={4}><strong>{formatAmount(report.totals.period_credit)}</strong></Table.Summary.Cell>
                      <Table.Summary.Cell index={5}><strong>{formatAmount(report.totals.ytd_debit)}</strong></Table.Summary.Cell>
                      <Table.Summary.Cell index={6}><strong>{formatAmount(report.totals.ytd_credit)}</strong></Table.Summary.Cell>
                      <Table.Summary.Cell index={7}><strong>{formatAmount(report.totals.closing_debit)}</strong></Table.Summary.Cell>
                      <Table.Summary.Cell index={8}><strong>{formatAmount(report.totals.closing_credit)}</strong></Table.Summary.Cell>
                      <Table.Summary.Cell index={9} />
                    </Table.Summary.Row>
                  ) : null
                }
              />
            )}
          </Card>
        </>
      )}

      <ReportSignatureModal
        open={pdfModalOpen}
        loading={exporting}
        onCancel={() => setPdfModalOpen(false)}
        onConfirm={(values) => void handleExport('pdf', values)}
      />
    </div>
  )
}
