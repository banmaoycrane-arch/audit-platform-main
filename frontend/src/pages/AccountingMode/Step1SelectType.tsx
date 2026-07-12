import { Alert, Button, Card, Radio, Space, Steps, Tag, Tooltip, Typography } from 'antd'
import {
  CloudUploadOutlined,
  EditOutlined,
  FileExcelOutlined,
  LockOutlined,
  RobotOutlined,
  TableOutlined,
} from '@ant-design/icons'
import { useLocation, useNavigate } from 'react-router-dom'
import { useEffect, useMemo, useState } from 'react'
import { FlowNav } from '../../components/FlowNav'
import {
  ACCOUNTING_ALLOWED_STRUCTURED_KINDS,
  type StructuredKind,
  STRUCTURED_KIND_OPTIONS,
  resolveStructuredKind,
} from '../../constants/structuredImportKinds'
import { useTrackBookkeepingStep } from '../../hooks/useTrackBookkeepingStep'

const { Title, Text, Paragraph } = Typography

/** 与 Step2 兼容的 inputMode 参数 */
type VoucherInputMode = 'ai_generated' | 'day_book_import' | 'manual_entry'

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
      '上传 PDF、图片、扫描件及非标准表格等原始资料。资料解析中心（场景 B）完成 OCR、单据识别与语义分解，登记模块台账并生成待复核凭证草稿。',
    pipeline: '智能解析引擎',
    icon: <RobotOutlined style={{ fontSize: 28, color: '#1677ff' }} />,
    examples: ['增值税发票', '银行回单', '合同协议', '报销影像', '收据扫描件'],
  },
  {
    value: 'day_book_import',
    title: '结构化 · 标准化财务文件',
    subtitle: '序时簿、日记账及标准分录表（Excel/CSV）',
    description:
      '上传 Excel/CSV 等结构化分录文件。系统先用规则引擎识别表头、模板与列映射，再调用智能解析引擎做校验与异常提示。科目余额表、明细账、财务报表请在审计系统中导入。',
    pipeline: '规则预识别 + 智能解析引擎',
    icon: <FileExcelOutlined style={{ fontSize: 28, color: '#52c41a' }} />,
    examples: ['序时簿', '日记账', '标准格式分录'],
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
  useTrackBookkeepingStep('step1_select')
  const navigate = useNavigate()
  const location = useLocation()
  const stepPath = (step: number) =>
    location.pathname.startsWith('/ledger/vouchers/step/')
      ? `/ledger/vouchers/step/${step}`
      : `/accounting/step/${step}`

  const [selectedInputMode, setSelectedInputMode] = useState<VoucherInputMode | undefined>(undefined)
  const [structuredKind, setStructuredKind] = useState<StructuredKind>('day_book')
  const currentStep = 0

  useEffect(() => {
    if (!ACCOUNTING_ALLOWED_STRUCTURED_KINDS.includes(structuredKind)) {
      setStructuredKind('day_book')
    }
  }, [structuredKind])

  const selectedMode = useMemo(
    () => MODE_OPTIONS.find((option) => option.value === selectedInputMode),
    [selectedInputMode],
  )

  const selectedKindOption = STRUCTURED_KIND_OPTIONS.find((kind) => kind.value === structuredKind)

  const handleNext = () => {
    if (!selectedInputMode) return
    const params = new URLSearchParams({ inputMode: selectedInputMode })
    if (selectedInputMode === 'day_book_import') {
      params.set('structuredKind', resolveStructuredKind(structuredKind, 'accounting'))
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
        <Alert
          type="warning"
          showIcon
          style={{ marginTop: 16 }}
          title="Step 2 上传前提示"
          description="结构化 Excel/CSV 导入时，系统会自动识别字符集与列分隔符。若文件来自老版财务软件或出现乱码，请在 Step 2 上传前配置 UTF-8 / GB18030 及逗号、Tab 分隔符，并可先预检测表头。"
        />
      )}

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
            onChange={(event) => {
              const next = event.target.value as StructuredKind
              if (ACCOUNTING_ALLOWED_STRUCTURED_KINDS.includes(next)) {
                setStructuredKind(next)
              }
            }}
            style={{ display: 'flex', flexDirection: 'column', gap: 8 }}
          >
            {STRUCTURED_KIND_OPTIONS.map((kind) => {
              const disabled = kind.auditOnly
              const radio = (
                <Radio key={kind.value} value={kind.value} disabled={disabled}>
                  <Text strong type={disabled ? 'secondary' : undefined}>
                    {kind.label}
                  </Text>
                  <Text type="secondary"> — {kind.hint}</Text>
                  {disabled && (
                    <Tag icon={<LockOutlined />} color="default" style={{ marginLeft: 8 }}>
                      审计系统专用
                    </Tag>
                  )}
                </Radio>
              )
              if (!disabled) return radio
              return (
                <Tooltip key={kind.value} title={kind.auditModuleHint}>
                  <div>{radio}</div>
                </Tooltip>
              )
            })}
          </Radio.Group>
          <Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 0 }}>
            科目余额表、明细账、标准财务报表属于审计底稿资料，请在「审计系统」对应导入步骤中使用；财务总账此处仅支持序时簿、日记账与标准分录。
          </Paragraph>
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
              ? `下一步将上传结构化文件（${selectedKindOption?.label || '序时簿 / 日记账'}），先规则识别表头，再由智能解析引擎校验。`
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
