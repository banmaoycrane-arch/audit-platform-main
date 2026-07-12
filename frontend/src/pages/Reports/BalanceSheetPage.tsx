import { useCallback, useMemo, useState } from 'react'
import { Alert, Button, Card, Collapse, Empty, Row, Col, Statistic, Table, Typography, message, Space } from 'antd'
import { DownloadOutlined, FilePdfOutlined } from '@ant-design/icons'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api, type BalanceSheetReport, type TrialBalanceRow } from '../../api/client'
import {
  LedgerReportFilterBar,
  type LedgerReportApplied,
} from '../../components/ledger/LedgerReportFilterBar'
import { ReportSignatureModal, type ReportSignatureForm } from '../../components/ledger/ReportSignatureModal'
import { ClassicReportFooter, ClassicReportHeader, ClassicReportSheet, ClassicReportTableWrap } from '../../components/ledger/ClassicReportChrome'
import { useAuthStore } from '../../stores/authStore'
import { formatAmount } from '../../money'
import { exportBalanceSheetCsv } from '../../utils/exportReportCsv'
import { downloadBlobWithDisposition } from '../../utils/downloadBlob'

const { Title, Paragraph } = Typography

type DualColumnRow = {
  row_index: number
  asset_label: string
  asset_opening: string | number
  asset_closing: string | number
  asset_is_section?: boolean
  asset_is_subtotal?: boolean
  liability_label: string
  liability_opening: string | number
  liability_closing: string | number
  liability_is_section?: boolean
  liability_is_subtotal?: boolean
}

function parseAmount(value: string | number | undefined): number {
  if (value === undefined || value === null || value === '') return 0
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

export function BalanceSheetPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const urlPeriodId = Number(searchParams.get('period_id') || 0) || null
  const { currentLedgerId } = useAuthStore()
  const [applied, setApplied] = useState<LedgerReportApplied | null>(null)
  const [report, setReport] = useState<BalanceSheetReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [pdfModalOpen, setPdfModalOpen] = useState(false)
  const [lastSignature, setLastSignature] = useState<ReportSignatureForm | undefined>()

  const loadReport = useCallback((query: LedgerReportApplied) => {
    if (!currentLedgerId) return
    setLoading(true)
    void api
      .getBalanceSheetReport({
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
      const { blob, contentDisposition } = await api.exportBalanceSheetReport(
        {
          ledgerId: currentLedgerId,
          periodId: applied.periodId,
          asOfDate: applied.asOfDate,
          ...signature,
        },
        format,
      )
      const fallback = `balance_sheet_${applied.period.period_code}.${format === 'pdf' ? 'pdf' : 'xlsx'}`
      await downloadBlobWithDisposition(blob, contentDisposition, fallback)
    } catch (err) {
      message.error(`导出失败：${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setExporting(false)
      setPdfModalOpen(false)
    }
  }

  const isBalanced = report?.statement_balanced ?? report?.is_balanced ?? false
  const pairedRows = (report?.classic_dual_column?.paired_rows || []) as DualColumnRow[]

  const dualColumns = useMemo(
    () => [
      {
        title: '资产',
        dataIndex: 'asset_label',
        key: 'asset_label',
        width: '22%',
        ellipsis: true,
        render: (label: string, row: DualColumnRow) => (
          <span className={row.asset_is_section || row.asset_is_subtotal ? 'classic-report-label-strong' : undefined}>
            {label}
          </span>
        ),
      },
      {
        title: '年初数',
        dataIndex: 'asset_opening',
        key: 'asset_opening',
        align: 'right' as const,
        width: '11%',
        render: (v: string | number, row: DualColumnRow) =>
          row.asset_is_section ? '' : formatAmount(parseAmount(v)),
      },
      {
        title: '年末数',
        dataIndex: 'asset_closing',
        key: 'asset_closing',
        align: 'right' as const,
        width: '11%',
        render: (v: string | number, row: DualColumnRow) =>
          row.asset_is_section ? '' : formatAmount(parseAmount(v)),
      },
      {
        title: '负债及所有者权益',
        dataIndex: 'liability_label',
        key: 'liability_label',
        width: '22%',
        ellipsis: true,
        render: (label: string, row: DualColumnRow) => (
          <span className={row.liability_is_section || row.liability_is_subtotal ? 'classic-report-label-strong' : undefined}>
            {label}
          </span>
        ),
      },
      {
        title: '年初数',
        dataIndex: 'liability_opening',
        key: 'liability_opening',
        align: 'right' as const,
        width: '11%',
        render: (v: string | number, row: DualColumnRow) =>
          row.liability_is_section ? '' : formatAmount(parseAmount(v)),
      },
      {
        title: '年末数',
        dataIndex: 'liability_closing',
        key: 'liability_closing',
        align: 'right' as const,
        width: '11%',
        render: (v: string | number, row: DualColumnRow) =>
          row.liability_is_section ? '' : formatAmount(parseAmount(v)),
      },
    ],
    [],
  )

  const detailColumns = [
    { title: '代码', dataIndex: 'account_code', key: 'account_code', width: 100 },
    { title: '科目', dataIndex: 'account_name', key: 'account_name' },
    {
      title: '期末借',
      dataIndex: 'closing_debit',
      key: 'closing_debit',
      render: (v: number) => formatAmount(v),
    },
    {
      title: '期末贷',
      dataIndex: 'closing_credit',
      key: 'closing_credit',
      render: (v: number) => formatAmount(v),
    },
    {
      title: '操作',
      key: 'action',
      width: 90,
      render: (_: unknown, row: TrialBalanceRow) => (
        <Button
          type="link"
          size="small"
          onClick={() => {
            if (!applied) return
            navigate('/ledger/subsidiary-ledger', {
              state: {
                accountCodes: [row.account_code],
                periodIds: [applied.periodId],
                autoSearch: true,
              },
            })
          }}
        >
          分录/凭证
        </Button>
      ),
    },
  ]

  return (
    <div>
      <Title level={3}>资产负债表</Title>
      <Paragraph type="secondary">
        通用左右双栏格式：左侧资产、右侧负债及所有者权益；列示年初数与年末数（货币资金合计、固定资产净值等按报表项目聚合）。
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

          {!applied ? (
            <Empty description="请选择期间并点击查询" />
          ) : report ? (
            <>
              {isBalanced ? (
                <Alert type="success" title="资产总计 = 负债及所有者权益合计" showIcon style={{ marginBottom: 16 }} />
              ) : (
                <Alert
                  type="error"
                  title="资产负债恒等式不平衡"
                  description="请检查科目列报项设置并执行损益结转。"
                  showIcon
                  style={{ marginBottom: 16 }}
                />
              )}

              <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                <Button icon={<DownloadOutlined />} loading={exporting} onClick={() => void handleExport('xlsx')}>
                  导出 Excel
                </Button>
                <Button icon={<FilePdfOutlined />} onClick={() => setPdfModalOpen(true)}>
                  签章 PDF
                </Button>
                <Button icon={<DownloadOutlined />} onClick={() => exportBalanceSheetCsv(report)}>
                  导出 CSV
                </Button>
              </div>

              <Row gutter={16} style={{ marginBottom: 16 }}>
                <Col span={8}>
                  <Card><Statistic title="资产总计" value={report.assets_total} prefix="¥" /></Card>
                </Col>
                <Col span={8}>
                  <Card><Statistic title="负债合计" value={report.liabilities_total} prefix="¥" /></Card>
                </Col>
                <Col span={8}>
                  <Card><Statistic title="所有者权益合计" value={report.equity_total} prefix="¥" /></Card>
                </Col>
              </Row>

              <Card style={{ marginBottom: 12 }} styles={{ body: { padding: '16px 20px' } }}>
                <ClassicReportSheet orientation="landscape">
                  <ClassicReportHeader
                    kind="balance_sheet"
                    ledgerName={report.ledger_name}
                    asOfDate={report.as_of_date}
                    periodCode={report.period_code}
                  />
                  <ClassicReportTableWrap>
                    <Table<DualColumnRow>
                      rowKey="row_index"
                      dataSource={pairedRows}
                      columns={dualColumns}
                      pagination={false}
                      size="small"
                      loading={loading}
                      bordered
                      tableLayout="fixed"
                      scroll={{ x: 960 }}
                    />
                  </ClassicReportTableWrap>
                  <ClassicReportFooter
                    preparerName={lastSignature?.preparer_name}
                    approverName={lastSignature?.approver_name}
                    reviewerName={lastSignature?.reviewer_name}
                  />
                </ClassicReportSheet>
              </Card>

              <Collapse
                items={[
                  {
                    key: 'detail',
                    label: '科目余额明细（编制备查）',
                    children: (
                      <>
                        <Card title="资产" size="small" style={{ marginBottom: 12 }}>
                          <Table<TrialBalanceRow>
                            rowKey="account_code"
                            dataSource={report.assets}
                            columns={detailColumns}
                            pagination={false}
                            size="small"
                          />
                        </Card>
                        <Card title="负债" size="small" style={{ marginBottom: 12 }}>
                          <Table<TrialBalanceRow>
                            rowKey="account_code"
                            dataSource={report.liabilities}
                            columns={detailColumns}
                            pagination={false}
                            size="small"
                          />
                        </Card>
                        <Card title="所有者权益" size="small">
                          <Table<TrialBalanceRow>
                            rowKey="account_code"
                            dataSource={report.equity}
                            columns={detailColumns}
                            pagination={false}
                            size="small"
                          />
                        </Card>
                      </>
                    ),
                  },
                ]}
              />
            </>
          ) : (
            <Card loading={loading}>
              <Empty description="暂无余额数据，请确认该期间已有凭证分录" />
            </Card>
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
