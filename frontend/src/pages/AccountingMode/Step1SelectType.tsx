import { Alert, Button, Card, Radio, Space, Steps, Tag, Typography } from 'antd'
import {
  CloudUploadOutlined,
  EditOutlined,
  FileExcelOutlined,
  RobotOutlined,
  TableOutlined,
} from '@ant-design/icons'
import { useLocation, useNavigate } from 'react-router-dom'
import { useMemo, useState } from 'react'
import { FlowNav } from '../../components/FlowNav'

const { Title, Text, Paragraph } = Typography

/** 与 Step2 兼容的 inputMode 参数 */
type VoucherInputMode = 'ai_generated' | 'day_book_import' | 'manual_entry'

type StructuredKind =
  | 'day_book'
  | 'standard_entries'
  | 'trial_balance'
  | 'subsidiary_ledger'
  | 'financial_reports'

const STRUCTURED_KIND_OPTIONS: Array<{
  value: StructuredKind
  label: string
  hint: string
}> = [
  { value: 'day_book', label: '序时簿 / 日记账', hint: '按凭证号、日期排列的分录流水' },
  { value: 'standard_entries', label: '标准格式分录文件', hint: '凭证号、科目、借贷金额等标准列' },
  { value: 'trial_balance', label: '科目余额表', hint: '期初、本期发生、期末余额' },
  { value: 'subsidiary_ledger', label: '明细账', hint: '按科目展开的分录明细' },
  { value: 'financial_reports', label: '标准财务报表', hint: '资产负债表、利润表等导出表' },
]

const MODE_OPTIONS: Array<{
  value: VoucherInputMode
  title: string
  subtitle: string
  description: string
  pipeline: string
  icon: React.ReactNode
  examples: string[]
}> = [
  {
    value: 'ai_generated',
    title: '非结构化 · 支持性原始文件',
    subtitle: '证据链资料，需语义理解后再生成凭证草稿',
    description:
      '上传 PDF、图片、扫描件及非标准表格等原始资料。系统调用项目统一智能解析引擎，完成 OCR、单据类型识别与语义分解，登记模块台账并生成待复核凭证草稿。',
    pipeline: '智能解析引擎',
    icon: <RobotOutlined style={{ fontSize: 28, color: '#1677ff' }} />,
    examples: ['增值税发票', '银行回单', '合同协议', '报销影像', '收据扫描件'],
  },
  {
    value: 'day_book_import',
    title: '结构化 · 标准化财务文件',
    subtitle: '其他账套或财务软件导出的标准表格/报表',
    description:
      '上传 Excel/CSV 等结构化文件。系统先用规则引擎识别表头、模板与列映射以保证速度，再调用智能解析引擎做校验、补全与异常提示，兼顾导入效率与精度。',
    pipeline: '规则预识别 + 智能解析引擎',
    icon: <FileExcelOutlined style={{ fontSize: 28, color: '#52c41a' }} />,
    examples: ['序时簿', '标准分录', '科目余额表', '明细账', '资产负债表导出'],
  },
  {
    value: 'manual_entry',
    title: '传统人工录入凭证',
    subtitle: '纸质记账凭证样式，直接录入正式分录',
    description:
      '按摘要、科目、借方/贷方分列录入，支持快速录入、保存并新增。适合少量补录或现场制单，无需上传文件。',
    pipeline: '人工录入 · 已可用',
    icon: <EditOutlined style={{ fontSize: 28, color: '#722ed1' }} />,
    examples: ['记/收/付/转字凭证', '多行分录', '往来单位', '附单据张数'],
  },
]

export function Step1AccountingSelectType() {
  const navigate = useNavigate()
  const location = useLocation()
  const stepPath = (step: number) =>
    location.pathname.startsWith('/ledger/vouchers/step/')
      ? `/ledger/vouchers/step/${step}`
      : `/accounting/step/${step}`

  const [selectedInputMode, setSelectedInputMode] = useState<VoucherInputMode | undefined>(undefined)
  const [structuredKind, setStructuredKind] = useState<StructuredKind>('day_book')
  const currentStep = 0

  const selectedMode = useMemo(
    () => MODE_OPTIONS.find((option) => option.value === selectedInputMode),
    [selectedInputMode],
  )

  const handleNext = () => {
    if (!selectedInputMode) return
    const params = new URLSearchParams({ inputMode: selectedInputMode })
    if (selectedInputMode === 'day_book_import') {
      params.set('structuredKind', structuredKind)
    }
    navigate(`${stepPath(2)}?${params.toString()}`)
  }

  return (
    <div style={{ padding: '24px', maxWidth: '920px', margin: '0 auto' }}>
      <Steps
        current={currentStep}
        items={[
          { title: '选择模式' },
          { title: '导入资料' },
          { title: '生成草稿' },
          { title: '复核调整' },
          { title: '确认导出' },
        ]}
        style={{ marginBottom: '32px' }}
      />

      <FlowNav style={{ marginBottom: '16px' }} />

      <Title level={4}>选择凭证输入模式</Title>
      <Paragraph type="secondary" style={{ marginBottom: '20px' }}>
        财务总账凭证管理分为三条路径：非结构化原始证据走智能解析；结构化标准财务文件走规则加速 + 智能解析校验；少量业务可直接传统录入。
      </Paragraph>

      <Alert
        type="info"
        showIcon
        icon={<CloudUploadOutlined />}
        title="模块规划"
        description="Step 1 只选择路径；Step 2 上传文件或录入分录；Step 3 生成/确认草稿；Step 4 复核；Step 5 入账导出。"
        style={{ marginBottom: '20px' }}
      />

      <Radio.Group
        value={selectedInputMode}
        onChange={(event) => setSelectedInputMode(event.target.value)}
        style={{ display: 'flex', flexDirection: 'column', gap: '12px', width: '100%' }}
      >
        {MODE_OPTIONS.map((option) => (
          <Radio key={option.value} value={option.value} style={{ alignItems: 'flex-start' }}>
            <Card
              size="small"
              style={{
                marginLeft: 8,
                width: '100%',
                borderColor: selectedInputMode === option.value ? '#1677ff' : undefined,
              }}
            >
              <Space align="start" size={16}>
                {option.icon}
                <div style={{ flex: 1 }}>
                  <Space wrap style={{ marginBottom: 4 }}>
                    <Text strong>{option.title}</Text>
                    <Tag color={option.value === 'manual_entry' ? 'success' : 'processing'}>
                      {option.pipeline}
                    </Tag>
                  </Space>
                  <div>
                    <Text type="secondary">{option.subtitle}</Text>
                  </div>
                  <Paragraph type="secondary" style={{ marginBottom: 8, marginTop: 8 }}>
                    {option.description}
                  </Paragraph>
                  <Space wrap size={[4, 4]}>
                    {option.examples.map((example) => (
                      <Tag key={example}>{example}</Tag>
                    ))}
                  </Space>
                </div>
              </Space>
            </Card>
          </Radio>
        ))}
      </Radio.Group>

      {selectedInputMode === 'day_book_import' && (
        <Card
          size="small"
          title={
            <Space>
              <TableOutlined />
              <span>选择结构化文件类型（Step 2 将据此优化规则模板）</span>
            </Space>
          }
          style={{ marginTop: 16 }}
        >
          <Radio.Group
            value={structuredKind}
            onChange={(event) => setStructuredKind(event.target.value)}
            style={{ display: 'flex', flexDirection: 'column', gap: 8 }}
          >
            {STRUCTURED_KIND_OPTIONS.map((kind) => (
              <Radio key={kind.value} value={kind.value}>
                <Text strong>{kind.label}</Text>
                <Text type="secondary"> — {kind.hint}</Text>
              </Radio>
            ))}
          </Radio.Group>
        </Card>
      )}

      {selectedMode && (
        <Alert
          type="success"
          showIcon
          style={{ marginTop: 16 }}
          title={`已选择：${selectedMode.title}`}
          description={
            selectedInputMode === 'day_book_import'
              ? `下一步将上传结构化文件（${STRUCTURED_KIND_OPTIONS.find((k) => k.value === structuredKind)?.label}），先规则识别表头，再由智能解析引擎校验。`
              : `下一步将进入${selectedMode.title}流程。`
          }
        />
      )}

      <Button
        type="primary"
        onClick={handleNext}
        disabled={!selectedInputMode}
        style={{ marginTop: 24 }}
      >
        下一步：进入导入资料
      </Button>
    </div>
  )
}
