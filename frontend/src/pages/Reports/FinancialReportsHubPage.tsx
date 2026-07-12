import { useState } from 'react'
import { Card, Col, Row, Typography, Steps, Alert, Button, Space, Tag, message } from 'antd'
import { useNavigate } from 'react-router-dom'
import {
  PieChartOutlined,
  DollarOutlined,
  LineChartOutlined,
  DownloadOutlined,
  FilePdfOutlined,
  FundOutlined,
  FileZipOutlined,
} from '@ant-design/icons'
import { api } from '../../api/client'
import {
  LedgerReportFilterBar,
  type LedgerReportApplied,
} from '../../components/ledger/LedgerReportFilterBar'
import { ReportSignatureModal, type ReportSignatureForm } from '../../components/ledger/ReportSignatureModal'
import { useAuthStore } from '../../stores/authStore'
import { LEDGER_WORKFLOW_PHASES } from '../../utils/ledgerNavTaxonomy'
import { downloadBlobWithDisposition } from '../../utils/downloadBlob'

const { Title, Paragraph, Text } = Typography

const REPORT_CARDS = [
  {
    key: 'trial-balance',
    title: '科目余额表',
    path: '/reports/trial-balance',
    icon: <PieChartOutlined style={{ fontSize: 32, color: '#1677ff' }} />,
    description: '核对全部科目期初、本期发生与期末六列；编制报表前的第一道勾稽。',
    order: 1,
  },
  {
    key: 'balance-sheet',
    title: '资产负债表',
    path: '/reports/balance-sheet',
    icon: <DollarOutlined style={{ fontSize: 32, color: '#52c41a' }} />,
    description: '资产 = 负债 + 所有者权益；需先完成损益结转后核对存量口径。',
    order: 2,
  },
  {
    key: 'income-statement',
    title: '利润表',
    path: '/reports/income-statement',
    icon: <LineChartOutlined style={{ fontSize: 32, color: '#fa8c16' }} />,
    description: '收入、成本、期间费用与净利润；与损益结转凭证勾稽。',
    order: 3,
  },
  {
    key: 'cash-flow-statement',
    title: '现金流量表',
    path: '/reports/cash-flow-statement',
    icon: <FundOutlined style={{ fontSize: 32, color: '#722ed1' }} />,
    description: '直接法分项（销售收现、购货付现等）+ 间接法净利润调节；支持收入直接进银行与应收回款两种路径。',
    order: 4,
  },
]

export function FinancialReportsHubPage() {
  const navigate = useNavigate()
  const { currentLedgerId } = useAuthStore()
  const reportsPhase = LEDGER_WORKFLOW_PHASES.find((p) => p.key === 'reports')
  const periodPhase = LEDGER_WORKFLOW_PHASES.find((p) => p.key === 'period-close')
  const [applied, setApplied] = useState<LedgerReportApplied | null>(null)
  const [exporting, setExporting] = useState(false)
  const [packageModalOpen, setPackageModalOpen] = useState(false)
  const [packageIncludePdf, setPackageIncludePdf] = useState(true)
  const [delivering, setDelivering] = useState(false)
  const [deliveryPath, setDeliveryPath] = useState<string | null>(null)
  const [deliverMode, setDeliverMode] = useState(false)

  const handlePackageExport = async (signature: ReportSignatureForm, includePdf = packageIncludePdf) => {
    if (!applied || !currentLedgerId) return
    setExporting(true)
    try {
      const { blob, contentDisposition } = await api.exportReportsPackage({
        ledgerId: currentLedgerId,
        periodId: applied.periodId,
        asOfDate: applied.asOfDate,
        includePdf,
        ...signature,
      })
      const fallback = `reports_package_${applied.period.period_code}.zip`
      await downloadBlobWithDisposition(blob, contentDisposition, fallback)
      message.success(includePdf ? '四大报表 ZIP（含签章 PDF）已下载' : '四大报表 Excel ZIP 已下载')
    } catch (err) {
      message.error(`打包导出失败：${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setExporting(false)
      setPackageModalOpen(false)
    }
  }

  const openPackageModal = (includePdf: boolean) => {
    if (!applied) {
      message.warning('请先选择期间并点击查询')
      return
    }
    if (!includePdf) {
      void handlePackageExport({ preparer_name: '', reviewer_name: '', approver_name: '' }, false)
      return
    }
    setPackageIncludePdf(includePdf)
    setDeliverMode(false)
    setPackageModalOpen(true)
  }

  const handleDeliverToDisk = async (signature: ReportSignatureForm) => {
    if (!applied || !currentLedgerId) return
    setDelivering(true)
    try {
      const result = await api.deliverReportsPackage({
        ledgerId: currentLedgerId,
        periodId: applied.periodId,
        asOfDate: applied.asOfDate,
        includePdf: true,
        includeSubsidiary: true,
        ...signature,
      })
      setDeliveryPath(result.delivery_folder)
      message.success(`标准报表已落盘，交付目录：${result.delivery_folder}`)
    } catch (err) {
      message.error(`落盘失败：${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setDelivering(false)
      setPackageModalOpen(false)
    }
  }

  return (
    <div style={{ padding: '0 4px' }}>
      <Title level={3}>财务报表编制中心</Title>
      <Paragraph type="secondary">
        对应记账 v1.0 验收步骤 A11：在期末处理完成后，按顺序编制并导出四大报表。
        各报表页支持导出 Excel、CSV 与签章 PDF；本页支持一键打包 ZIP 下载。
      </Paragraph>

      {!currentLedgerId && (
        <Alert type="warning" showIcon message="请先在顶部选择账簿" style={{ marginBottom: 16 }} />
      )}

      <Card size="small" style={{ marginBottom: 16 }}>
        <Steps
          size="small"
          items={[
            { title: '凭证入账', description: 'Step5 确认过账' },
            {
              title: '损益结转',
              description: (
                <Button type="link" size="small" style={{ padding: 0 }} onClick={() => navigate('/accounting-periods')}>
                  前往期末处理
                </Button>
              ),
            },
            { title: '报表编制', description: '本页' },
            { title: '导出归档', description: 'ZIP / 签章 PDF' },
            { title: '期间结账', description: '可选' },
          ]}
        />
      </Card>

      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="编制顺序建议"
        description={
          <Space direction="vertical" size={4}>
            <Text>1. 科目余额表 — 确认借贷合计平衡</Text>
            <Text>2. 资产负债表 — 确认资产 = 负债 + 权益（需已结转损益）</Text>
            <Text>3. 利润表 — 与结转凭证净利润勾稽</Text>
            <Text>4. 现金流量表 — 核对经营/投资/筹资活动净额</Text>
            <Text type="secondary">
              期末处理入口：
              <Button type="link" size="small" onClick={() => navigate(periodPhase?.path || '/accounting-periods')}>
                {periodPhase?.title ?? '损益结转与结账'}
              </Button>
              （文档 {periodPhase?.docStep}）
            </Text>
          </Space>
        }
      />

      {currentLedgerId && (
        <Card size="small" title="打包导出（四大报表）" style={{ marginBottom: 16 }}>
          <LedgerReportFilterBar
            ledgerId={currentLedgerId}
            title="选择期间后打包下载"
            applied={applied}
            onApply={setApplied}
          />
          <Space wrap style={{ marginTop: 8 }}>
            <Button
              type="primary"
              icon={<FileZipOutlined />}
              loading={exporting}
              disabled={!applied}
              onClick={() => openPackageModal(true)}
            >
              打包下载 ZIP（Excel + 签章 PDF）
            </Button>
            <Button
              icon={<DownloadOutlined />}
              loading={exporting}
              disabled={!applied}
              onClick={() => openPackageModal(false)}
            >
              仅 Excel 打包
            </Button>
            <Button
              type="primary"
              ghost
              icon={<FileZipOutlined />}
              loading={delivering}
              disabled={!applied}
              onClick={() => {
                setDeliverMode(true)
                setPackageModalOpen(true)
              }}
            >
              生成邮递交付包（落盘）
            </Button>
            <Text type="secondary" style={{ fontSize: 12 }}>
              正式对外报送请填写编制/复核/审核人；「邮递交付包」将标准格式报表写入服务器目录并生成清单。
            </Text>
          </Space>
          {deliveryPath && (
            <Alert
              type="success"
              showIcon
              style={{ marginTop: 12 }}
              message="最新交付目录"
              description={<Text copyable>{deliveryPath}</Text>}
            />
          )}
        </Card>
      )}

      <Row gutter={[16, 16]}>
        {REPORT_CARDS.map((card) => (
          <Col xs={24} md={12} lg={6} key={card.key}>
            <Card
              hoverable
              onClick={() => navigate(card.path)}
              styles={{ body: { minHeight: 200 } }}
            >
              <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                <Space>
                  <Tag color="blue">第 {card.order} 步</Tag>
                  {card.icon}
                </Space>
                <Title level={5} style={{ margin: 0 }}>{card.title}</Title>
                <Paragraph type="secondary" style={{ margin: 0, fontSize: 13 }}>
                  {card.description}
                </Paragraph>
                <Space>
                  <Button type="primary" size="small" onClick={(e) => { e.stopPropagation(); navigate(card.path) }}>
                    编制
                  </Button>
                  <Button size="small" icon={<FilePdfOutlined />} onClick={(e) => { e.stopPropagation(); navigate(card.path) }}>
                    签章 PDF
                  </Button>
                </Space>
              </Space>
            </Card>
          </Col>
        ))}
      </Row>

      <Card size="small" style={{ marginTop: 16 }} title="验收对照">
        <Paragraph type="secondary" style={{ marginBottom: 8 }}>
          文档能力编号 {reportsPhase?.docStep}（{reportsPhase?.summary}）
        </Paragraph>
        <Space wrap>
          <Tag>科目余额表 GET /api/reports/trial-balance</Tag>
          <Tag>资产负债表 GET /api/reports/balance-sheet</Tag>
          <Tag>利润表 GET /api/reports/income-statement</Tag>
          <Tag>现金流量表 GET /api/reports/cash-flow-statement</Tag>
          <Tag>ZIP 打包 GET /api/reports/package/export</Tag>
        </Space>
      </Card>

      <ReportSignatureModal
        open={packageModalOpen}
        loading={exporting || delivering}
        title={deliverMode ? '填写签章信息（邮递交付包落盘）' : packageIncludePdf ? '填写签章信息（正式报表 ZIP）' : '填写签章信息（可选，仅 Excel 打包不需签章）'}
        onCancel={() => {
          setPackageModalOpen(false)
          setDeliverMode(false)
        }}
        onConfirm={(values) => {
          if (deliverMode) {
            void handleDeliverToDisk(values)
            setDeliverMode(false)
            return
          }
          void handlePackageExport(values)
        }}
      />
    </div>
  )
}
