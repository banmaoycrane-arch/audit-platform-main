import { useCallback, useMemo, useState } from 'react'
import { Alert, Button, Card, Col, Empty, Row, Statistic, Table, Typography, message, Space, Tag } from 'antd'
import { DownloadOutlined, FilePdfOutlined } from '@ant-design/icons'
import { useSearchParams } from 'react-router-dom'
import { api, type CashFlowStatementReport, type FinancialStatementLine } from '../../api/client'
import {
  LedgerReportFilterBar,
  type LedgerReportApplied,
} from '../../components/ledger/LedgerReportFilterBar'
import { ReportSignatureModal, type ReportSignatureForm } from '../../components/ledger/ReportSignatureModal'
import { ClassicReportFooter, ClassicReportHeader, ClassicReportSheet, ClassicReportTableWrap } from '../../components/ledger/ClassicReportChrome'
import { useAuthStore } from '../../stores/authStore'
import { formatAmount } from '../../money'
import { downloadBlobWithDisposition } from '../../utils/downloadBlob'

const { Title, Paragraph } = Typography

function parseAmount(value: string | number | undefined): number {
  if (value === undefined || value === null || value === '') return 0
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

export function CashFlowStatementPage() {
  const { currentLedgerId } = useAuthStore()
  const [searchParams] = useSearchParams()
  const urlPeriodId = Number(searchParams.get('period_id') || 0) || null
  const [applied, setApplied] = useState<LedgerReportApplied | null>(null)
  const [report, setReport] = useState<CashFlowStatementReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [pdfModalOpen, setPdfModalOpen] = useState(false)
  const [lastSignature, setLastSignature] = useState<ReportSignatureForm | undefined>()

  const loadReport = useCallback((query: LedgerReportApplied) => {
    if (!currentLedgerId) return
    setLoading(true)
    void api
      .getCashFlowStatementReport({
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

  const handleExport = async (format: 'xlsx' | 'pdf', signature?: ReportSignatureForm) => {
    if (!applied || !currentLedgerId) return
    if (signature) setLastSignature(signature)
    setExporting(true)
    try {
      const { blob, contentDisposition } = await api.exportCashFlowStatementReport(
        {
          ledgerId: currentLedgerId,
          periodId: applied.periodId,
          asOfDate: applied.asOfDate,
          ...signature,
        },
        format,
      )
      const fallback = `cash_flow_${applied.period.period_code}.${format === 'pdf' ? 'pdf' : 'xlsx'}`
      await downloadBlobWithDisposition(blob, contentDisposition, fallback)
    } catch (err) {
      message.error(`导出失败：${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setExporting(false)
      setPdfModalOpen(false)
    }
  }

  const directColumns = useMemo(
    () => [
      {
        title: '项目',
        dataIndex: 'label',
        key: 'label',
        width: '48%',
        ellipsis: true,
        render: (label: string, row: FinancialStatementLine) => (
          <span className={row.is_header || row.is_subtotal ? 'classic-report-label-strong' : undefined}>
            {label}
          </span>
        ),
      },
      { title: '行次', dataIndex: 'line_no', key: 'line_no', width: 56, align: 'center' as const },
      {
        title: '上期数',
        dataIndex: 'prior_amount',
        key: 'prior_amount',
        align: 'right' as const,
        width: '22%',
        render: (v: string | number | undefined, row: FinancialStatementLine) =>
          row.is_header ? '' : formatAmount(parseAmount(v)),
      },
      {
        title: '本期数',
        dataIndex: 'current_amount',
        key: 'current_amount',
        align: 'right' as const,
        width: '22%',
        render: (v: string | number | undefined, row: FinancialStatementLine) =>
          row.is_header ? '' : formatAmount(parseAmount(v)),
      },
    ],
    [],
  )

  const indirectColumns = useMemo(
    () => [
      {
        title: '调节项目',
        dataIndex: 'label',
        key: 'label',
        width: '70%',
        ellipsis: true,
        render: (label: string, row: FinancialStatementLine) => (
          <span className={row.is_subtotal ? 'classic-report-label-strong' : undefined}>{label}</span>
        ),
      },
      { title: '行次', dataIndex: 'line_no', key: 'line_no', width: 56, align: 'center' as const },
      {
        title: '金额',
        dataIndex: 'current_amount',
        key: 'current_amount',
        align: 'right' as const,
        width: '24%',
        render: (v: string | number | undefined) => formatAmount(parseAmount(v)),
      },
    ],
    [],
  )

  return (
    <div>
      <Title level={3}>现金流量表</Title>
      <Paragraph type="secondary">
        直接法按现金收付对方科目分项列示（销售收现、购货付现、职工薪酬等）；附间接法将净利润调节为经营活动净额。
        收入直接进银行与先挂应收后回款两种记账路径均可识别。
      </Paragraph>

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

          {report && (
            <>
              <Alert
                type={report.direct_indirect_reconciled ? 'success' : 'warning'}
                showIcon
                style={{ marginBottom: 16 }}
                title={
                  report.direct_indirect_reconciled
                    ? '直接法与间接法经营活动净额已勾稽一致'
                    : '直接法与间接法经营活动净额存在差异，请核对折旧、存货及往来变动'
                }
                description={
                  <Space direction="vertical" size={4}>
                    <span>
                      期间 {report.period_code || applied?.period.period_code} · 现金净增加{' '}
                      {formatAmount(report.net_increase_in_cash)}
                    </span>
                    {report.pattern_flags?.direct_revenue_to_bank && (
                      <Tag color="blue">含收入直接记入银行存款</Tag>
                    )}
                    {report.pattern_flags?.receivable_collection && (
                      <Tag color="cyan">含应收科目回款</Tag>
                    )}
                  </Space>
                }
              />

              {report.compilation_notes?.map((note) => (
                <Alert key={note} type="info" showIcon message={note} style={{ marginBottom: 8 }} />
              ))}

              <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                <Button icon={<DownloadOutlined />} loading={exporting} onClick={() => void handleExport('xlsx')}>
                  导出 Excel
                </Button>
                <Button icon={<FilePdfOutlined />} onClick={() => setPdfModalOpen(true)}>
                  导出签章 PDF
                </Button>
              </div>

              <Row gutter={16} style={{ marginBottom: 16 }}>
                <Col xs={24} md={8}>
                  <Card size="small">
                    <Statistic title="经营活动净额" value={parseAmount(report.operating_activities?.net)} prefix="¥" />
                  </Card>
                </Col>
                <Col xs={24} md={8}>
                  <Card size="small">
                    <Statistic title="投资活动净额" value={parseAmount(report.investing_activities?.net)} prefix="¥" />
                  </Card>
                </Col>
                <Col xs={24} md={8}>
                  <Card size="small">
                    <Statistic title="筹资活动净额" value={parseAmount(report.financing_activities?.net)} prefix="¥" />
                  </Card>
                </Col>
              </Row>

              <Card style={{ marginBottom: 16 }} loading={loading} styles={{ body: { padding: '16px 20px' } }}>
                <ClassicReportSheet orientation="portrait">
                  <ClassicReportHeader
                    kind="cash_flow"
                    ledgerName={report.ledger_name}
                    asOfDate={report.as_of_date}
                    periodCode={report.period_code || applied?.period.period_code}
                  />
                  <ClassicReportTableWrap>
                    <Table<FinancialStatementLine>
                      rowKey={(row) => `d-${row.line_no}-${row.line_code || row.label}`}
                      dataSource={report.statement_lines || []}
                      columns={directColumns}
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

              <Card title="附：净利润调节为经营活动现金流量（间接法）" loading={loading} styles={{ body: { padding: '16px 20px' } }}>
                <ClassicReportSheet orientation="portrait">
                  <ClassicReportTableWrap>
                    <Table<FinancialStatementLine>
                      rowKey={(row) => `i-${row.line_no}-${row.line_code || row.label}`}
                      dataSource={report.indirect_lines || []}
                      columns={indirectColumns}
                      pagination={false}
                      size="small"
                      bordered
                      tableLayout="fixed"
                    />
                  </ClassicReportTableWrap>
                </ClassicReportSheet>
              </Card>
            </>
          )}
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
