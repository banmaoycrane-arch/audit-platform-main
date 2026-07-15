import { useEffect, useMemo, useState } from 'react'
import { Button, Card, Typography, Row, Col, Statistic, Table, message } from 'antd'
import { DownloadOutlined, FilePdfOutlined } from '@ant-design/icons'
import { useSearchParams } from 'react-router-dom'
import { api, type AccountingPeriod, type FinancialStatementLine, type IncomeStatementReport } from '../../api/client'
import { PeriodSelector } from '../../components/PeriodSelector'
import { ReportSignatureModal, type ReportSignatureForm } from '../../components/ledger/ReportSignatureModal'
import { ClassicReportFooter, ClassicReportHeader, ClassicReportSheet, ClassicReportTableWrap } from '../../components/ledger/ClassicReportChrome'
import { useAuthStore } from '../../stores/authStore'
import { formatAmount } from '../../money'
import { exportIncomeStatementCsv } from '../../utils/exportReportCsv'
import { downloadBlobWithDisposition } from '../../utils/downloadBlob'

const { Title } = Typography

function parseAmount(value: string | number | undefined): number {
  if (value === undefined || value === null || value === '') return 0
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

export function IncomeStatementPage() {
  const { currentLedgerId } = useAuthStore()
  const [searchParams] = useSearchParams()
  const urlPeriodId = Number(searchParams.get('period_id') || 0) || null
  const [filter, setFilter] = useState<{ organizationId: number | null; periodId: number | null }>({
    organizationId: null,
    periodId: urlPeriodId,
  })
  const [report, setReport] = useState<IncomeStatementReport | null>(null)
  const [periodCode, setPeriodCode] = useState('')
  const [exporting, setExporting] = useState(false)
  const [pdfModalOpen, setPdfModalOpen] = useState(false)
  const [lastSignature, setLastSignature] = useState<ReportSignatureForm | undefined>()

  useEffect(() => {
    if (!currentLedgerId || !filter.periodId) {
      setPeriodCode('')
      return
    }
    void api.listAccountingPeriods(undefined, currentLedgerId).then((periods: AccountingPeriod[]) => {
      const match = periods.find((p) => p.id === filter.periodId)
      setPeriodCode(match?.period_code ?? String(filter.periodId))
    })
  }, [currentLedgerId, filter.periodId])

  useEffect(() => {
    if (!filter.organizationId || !filter.periodId) return
    api.getIncomeStatementReport(filter.organizationId, filter.periodId)
      .then(setReport)
      .catch((err) => message.error(`加载失败：${err instanceof Error ? err.message : String(err)}`))
  }, [filter])

  const handleExport = async (format: 'xlsx' | 'pdf', signature?: ReportSignatureForm) => {
    if (!filter.organizationId || !filter.periodId || !currentLedgerId) return
    if (signature) setLastSignature(signature)
    setExporting(true)
    try {
      const { blob, contentDisposition } = await api.exportIncomeStatementReport(
        {
          organizationId: filter.organizationId,
          periodId: filter.periodId,
          ledgerId: currentLedgerId,
          ...signature,
        },
        format,
      )
      const ext = format === 'pdf' ? 'pdf' : 'xlsx'
      await downloadBlobWithDisposition(blob, contentDisposition, `income_statement_${periodCode || filter.periodId}.${ext}`)
    } catch (err) {
      message.error(`导出失败：${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setExporting(false)
      setPdfModalOpen(false)
    }
  }

  const columns = useMemo(
    () => [
      {
        title: '财务项目',
        dataIndex: 'label',
        key: 'label',
        width: '48%',
        ellipsis: true,
        render: (label: string, row: FinancialStatementLine) => (
          <span className={[4, 9, 14, 16].includes(Number(row.line_no)) ? 'classic-report-label-strong' : undefined}>
            {label}
          </span>
        ),
      },
      { title: '行次', dataIndex: 'line_no', key: 'line_no', width: 56, align: 'center' as const },
      {
        title: '本月数',
        dataIndex: 'current_amount',
        key: 'current_amount',
        align: 'right' as const,
        width: '22%',
        render: (v: string | number | undefined, row: FinancialStatementLine) =>
          formatAmount(parseAmount(row.month_amount ?? v)),
      },
      {
        title: '本年累计数',
        dataIndex: 'ytd_amount',
        key: 'ytd_amount',
        align: 'right' as const,
        width: '22%',
        render: (v: string | number | undefined, row: FinancialStatementLine) =>
          formatAmount(parseAmount(row.year_to_date_amount ?? v)),
      },
    ],
    [],
  )

  return (
    <div>
      <Title level={3}>损益表</Title>
      <Card style={{ marginBottom: 16 }}>
        <PeriodSelector ledgerId={currentLedgerId} value={filter} onChange={setFilter} />
      </Card>

      {report && (
        <>
          <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
            <Button icon={<DownloadOutlined />} loading={exporting} onClick={() => void handleExport('xlsx')}>
              导出 Excel
            </Button>
            <Button icon={<FilePdfOutlined />} onClick={() => setPdfModalOpen(true)}>
              签章 PDF
            </Button>
            <Button icon={<DownloadOutlined />} onClick={() => exportIncomeStatementCsv(report, periodCode)}>
              导出 CSV
            </Button>
          </div>

          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col span={6}>
              <Card><Statistic title="营业利润（本期）" value={report.operating_profit} prefix="¥" /></Card>
            </Col>
            <Col span={6}>
              <Card><Statistic title="利润总额（本期）" value={report.total_profit} prefix="¥" /></Card>
            </Col>
            <Col span={6}>
              <Card><Statistic title="所得税费用（本期）" value={report.income_tax} prefix="¥" /></Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic
                  title="净利润（本期）"
                  value={report.net_profit}
                  prefix="¥"
                  valueStyle={{ color: report.net_profit >= 0 ? '#3f8600' : '#cf1322' }}
                />
              </Card>
            </Col>
          </Row>

          <Card styles={{ body: { padding: '16px 20px' } }}>
            <ClassicReportSheet orientation="portrait">
              <ClassicReportHeader
                kind="income_statement"
                ledgerName={report.ledger_name}
                asOfDate={report.as_of_date}
                periodCode={periodCode || report.period_code}
              />
              <ClassicReportTableWrap>
                <Table<FinancialStatementLine>
                  rowKey={(row) => `${row.line_no}-${row.label}`}
                  dataSource={report.statement_lines || []}
                  columns={columns}
                  pagination={false}
                  size="small"
                  bordered
                  tableLayout="fixed"
                />
              </ClassicReportTableWrap>
              <ClassicReportFooter
                preparerName={lastSignature?.preparer_name}
                approverName={lastSignature?.approver_name}
                reviewerName={lastSignature?.reviewer_name}
              />
            </ClassicReportSheet>
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
