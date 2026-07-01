import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Alert,
  Button,
  Card,
  Collapse,
  DatePicker,
  Descriptions,
  Empty,
  Input,
  InputNumber,
  Row,
  Col,
  Space,
  Spin,
  Table,
  Tag,
  Result,
  message,
} from 'antd'
import { InboxOutlined, CheckCircleOutlined, FileTextOutlined } from '@ant-design/icons'
import type { Dayjs } from 'dayjs'
import dayjs from 'dayjs'
import { Upload } from 'antd'
import { api } from '../api/client'
import { useAuthStore } from '../stores/authStore'

const { Dragger } = Upload

// 文档类型中文标签映射
const DOCUMENT_TYPE_LABELS: Record<string, string> = {
  invoice: '发票',
  bank_statement: '银行流水',
  expense_document: '费用单据',
  salary_table: '工资表',
  receipt: '收据凭证',
  contract: '合同协议',
  inventory_receipt: '入库单',
  accounting_entry: '会计分录',
  general: '通用文档',
  unknown: '未知',
}

// 候选分录行类型（_key 为前端生成的行唯一标识，仅用于 Table rowKey）
type DraftLine = {
  _key: string
  account_code: string
  account_name: string
  summary: string
  debit_amount: string
  credit_amount: string
  counterparty: string | null
}

// 候选凭证草稿类型
type CandidateDraft = {
  voucher_no: string
  voucher_date: string
  summary: string
  document_type: string
  source_confidence: number
  lines: DraftLine[]
  validation_errors: string[]
  raw_extracted_data: Record<string, unknown>
}

// 解析响应类型
type ParseResponse = {
  success: boolean
  document_type: string
  confidence: number
  drafts: CandidateDraft[]
  error_message: string | null
}

// 确认响应类型
type ConfirmResponse = {
  success: boolean
  created_count: number
  voucher_ids: number[]
  error_message: string | null
}

// 金额计算辅助函数：将金额字符串转为数字（避免 NaN）
const toAmountNumber = (value: string | number | null | undefined): number => {
  if (value === null || value === undefined || value === '') return 0
  const num = Number(value)
  return Number.isFinite(num) ? num : 0
}

// 金额格式化：保留 2 位小数
const formatAmount = (value: number): string => value.toFixed(2)

// 计算借方合计
const sumDebit = (draft: CandidateDraft): number =>
  Math.round(draft.lines.reduce((sum, line) => sum + toAmountNumber(line.debit_amount) * 100, 0)) / 100

// 计算贷方合计
const sumCredit = (draft: CandidateDraft): number =>
  Math.round(draft.lines.reduce((sum, line) => sum + toAmountNumber(line.credit_amount) * 100, 0)) / 100

// 判断借贷是否平衡
const isDraftBalanced = (draft: CandidateDraft): boolean => {
  const debit = Math.round(sumDebit(draft) * 100)
  const credit = Math.round(sumCredit(draft) * 100)
  return debit === credit
}

export function ParserVoucherPreview() {
  const navigate = useNavigate()
  const { currentLedgerId, userLedgers } = useAuthStore()

  // 从当前选中账簿上下文获取组织 ID
  const currentLedger = userLedgers.find((ledger) => ledger.id === currentLedgerId)
  const organizationId = currentLedger?.organization_id

  const [uploading, setUploading] = useState(false)
  const [parseResult, setParseResult] = useState<ParseResponse | null>(null)
  const [drafts, setDrafts] = useState<CandidateDraft[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [successResult, setSuccessResult] = useState<ConfirmResponse | null>(null)

  // 处理文件上传并调用解析接口
  const handleUpload = async (file: File): Promise<boolean> => {
    if (!currentLedgerId) {
      message.error('请先在顶部切换账簿后再上传文件')
      return false
    }
    if (!organizationId) {
      message.error('当前账簿缺少组织信息（organization_id），无法解析')
      return false
    }

    setUploading(true)
    setSuccessResult(null)
    setParseResult(null)
    setDrafts([])
    try {
      const result = await api.parseToVoucherDrafts(organizationId, file)
      setParseResult(result)
      if (!result.success) {
        message.error(result.error_message || '解析失败，请检查文件格式后重试')
        setDrafts([])
        return false
      }
      // 深拷贝草稿以便编辑（避免直接修改响应数据），并为每行生成 _key
      setDrafts(result.drafts.map((draft, draftIdx) => ({
        ...draft,
        lines: draft.lines.map((line, lineIdx) => ({
          ...line,
          _key: `draft-${draftIdx}-line-${lineIdx}`,
        })),
        validation_errors: [...draft.validation_errors],
        raw_extracted_data: { ...draft.raw_extracted_data },
      })))
      if (result.drafts.length > 0) {
        message.success(`解析完成，共生成 ${result.drafts.length} 张候选凭证草稿`)
      } else {
        message.warning('解析成功但未生成任何候选凭证草稿')
      }
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error)
      message.error(`解析失败：${detail}`)
    } finally {
      setUploading(false)
    }
    return false
  }

  // 更新草稿头部字段（凭证号、日期、摘要）
  const handleDraftFieldChange = (
    draftIndex: number,
    field: 'voucher_no' | 'summary',
    value: string,
  ) => {
    setDrafts((prev) => prev.map((draft, index) => {
      if (index !== draftIndex) return draft
      return { ...draft, [field]: value }
    }))
  }

  // 更新草稿凭证日期（Dayjs 转字符串）
  const handleDraftDateChange = (draftIndex: number, date: Dayjs | null) => {
    const dateStr = date ? date.format('YYYY-MM-DD') : ''
    setDrafts((prev) => prev.map((draft, index) => {
      if (index !== draftIndex) return draft
      return { ...draft, voucher_date: dateStr }
    }))
  }

  // 更新分录行字段（不含 _key 内部字段）
  const handleLineFieldChange = (
    draftIndex: number,
    lineIndex: number,
    field: Exclude<keyof DraftLine, '_key'>,
    value: string,
  ) => {
    setDrafts((prev) => prev.map((draft, di) => {
      if (di !== draftIndex) return draft
      return {
        ...draft,
        lines: draft.lines.map((line, li) => {
          if (li !== lineIndex) return line
          return { ...line, [field]: value }
        }),
      }
    }))
  }

  // 确认生成凭证草稿
  const handleConfirm = async () => {
    if (!currentLedgerId) {
      message.error('请先选择账簿')
      return
    }
    if (!organizationId) {
      message.error('当前账簿缺少组织信息，无法确认')
      return
    }
    if (drafts.length === 0) {
      message.error('没有可确认的草稿')
      return
    }

    // 校验所有草稿借贷平衡
    for (let i = 0; i < drafts.length; i++) {
      if (!isDraftBalanced(drafts[i])) {
        message.error(`第 ${i + 1} 张凭证借贷不平衡，请先调整后再确认`)
        return
      }
    }

    setSubmitting(true)
    try {
      const result = await api.confirmVoucherDrafts(currentLedgerId, organizationId, drafts)
      if (!result.success) {
        message.error(result.error_message || '确认失败，请稍后重试')
        return
      }
      setSuccessResult(result)
      message.success(`成功创建 ${result.created_count} 张凭证草稿`)
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error)
      message.error(`确认失败：${detail}`)
    } finally {
      setSubmitting(false)
    }
  }

  // 重置页面状态，允许继续上传
  const handleReset = () => {
    setParseResult(null)
    setDrafts([])
    setSuccessResult(null)
  }

  // 构建分录表格列定义
  const buildLineColumns = (draftIndex: number) => [
    {
      title: '科目编码',
      dataIndex: 'account_code',
      key: 'account_code',
      width: 140,
      render: (value: string, _record: DraftLine, lineIndex: number) => (
        <Input
          value={value}
          onChange={(e) => handleLineFieldChange(draftIndex, lineIndex, 'account_code', e.target.value)}
          size="small"
          placeholder="科目编码"
        />
      ),
    },
    {
      title: '科目名称',
      dataIndex: 'account_name',
      key: 'account_name',
      width: 160,
      render: (value: string, _record: DraftLine, lineIndex: number) => (
        <Input
          value={value}
          onChange={(e) => handleLineFieldChange(draftIndex, lineIndex, 'account_name', e.target.value)}
          size="small"
          placeholder="科目名称"
        />
      ),
    },
    {
      title: '摘要',
      dataIndex: 'summary',
      key: 'summary',
      width: 200,
      render: (value: string, _record: DraftLine, lineIndex: number) => (
        <Input
          value={value}
          onChange={(e) => handleLineFieldChange(draftIndex, lineIndex, 'summary', e.target.value)}
          size="small"
          placeholder="分录摘要"
        />
      ),
    },
    {
      title: '借方金额',
      dataIndex: 'debit_amount',
      key: 'debit_amount',
      width: 130,
      render: (value: string, _record: DraftLine, lineIndex: number) => (
        <InputNumber
          value={toAmountNumber(value)}
          onChange={(val) => handleLineFieldChange(draftIndex, lineIndex, 'debit_amount', String(val ?? 0))}
          precision={2}
          step={0.01}
          size="small"
          style={{ width: '100%' }}
          placeholder="0.00"
        />
      ),
    },
    {
      title: '贷方金额',
      dataIndex: 'credit_amount',
      key: 'credit_amount',
      width: 130,
      render: (value: string, _record: DraftLine, lineIndex: number) => (
        <InputNumber
          value={toAmountNumber(value)}
          onChange={(val) => handleLineFieldChange(draftIndex, lineIndex, 'credit_amount', String(val ?? 0))}
          precision={2}
          step={0.01}
          size="small"
          style={{ width: '100%' }}
          placeholder="0.00"
        />
      ),
    },
    {
      title: '对方单位',
      dataIndex: 'counterparty',
      key: 'counterparty',
      width: 160,
      render: (value: string | null, _record: DraftLine, lineIndex: number) => (
        <Input
          value={value || ''}
          onChange={(e) => handleLineFieldChange(draftIndex, lineIndex, 'counterparty', e.target.value)}
          size="small"
          placeholder="对方单位"
        />
      ),
    },
  ]

  // 未选择账簿时的提示
  if (!currentLedgerId) {
    return (
      <div style={{ padding: 24 }}>
        <Card>
          <Empty description="请先在顶部切换账簿后再使用解析结果预览功能" />
        </Card>
      </div>
    )
  }

  // 组织信息缺失时的提示
  if (!organizationId) {
    return (
      <div style={{ padding: 24 }}>
        <Card>
          <Empty description="当前账簿缺少组织信息（organization_id），无法调用解析接口" />
        </Card>
      </div>
    )
  }

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
      <style>{`
        .pv-unbalanced-row td {
          background-color: #fff1f0 !important;
        }
      `}</style>

      <Card
        title={(
          <span>
            <FileTextOutlined style={{ marginRight: 8 }} />
            解析结果预览与凭证草稿确认
          </span>
        )}
      >
        <Alert
          message="功能说明"
          description="上传原始资料文件（发票、银行流水、费用单据等），系统将自动解析并生成候选凭证草稿。您可以在预览页面编辑科目、金额等字段，确认借贷平衡后生成正式凭证草稿。"
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
        />

        {/* 文件上传区域 */}
        <Dragger
          name="file"
          multiple={false}
          disabled={uploading || submitting}
          beforeUpload={handleUpload}
          accept=".xlsx,.xls,.csv,.pdf,.jpg,.jpeg,.png,.txt,.xml,.ofd"
          style={{ padding: '32px' }}
        >
          <p className="ant-upload-drag-icon">
            <InboxOutlined />
          </p>
          <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
          <p className="ant-upload-hint">
            支持 PDF、图片、Excel/CSV 等格式。上传后系统将自动解析并生成候选凭证草稿。
          </p>
        </Dragger>

        {uploading && (
          <div style={{ textAlign: 'center', padding: 24 }}>
            <Spin tip="正在解析文件，请稍候..." />
          </div>
        )}
      </Card>

      {/* 解析结果头部信息 */}
      {parseResult && parseResult.success && (
        <Card style={{ marginTop: 16 }} title="解析结果概览">
          <Descriptions bordered column={3}>
            <Descriptions.Item label="文档类型">
              <Tag color="blue">
                {DOCUMENT_TYPE_LABELS[parseResult.document_type] || parseResult.document_type}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="解析置信度">
              {(parseResult.confidence * 100).toFixed(1)}%
            </Descriptions.Item>
            <Descriptions.Item label="候选凭证数量">
              {parseResult.drafts.length} 张
            </Descriptions.Item>
          </Descriptions>
        </Card>
      )}

      {/* 解析失败提示 */}
      {parseResult && !parseResult.success && (
        <Card style={{ marginTop: 16 }}>
          <Alert
            message="解析失败"
            description={parseResult.error_message || '未知错误，请检查文件格式后重试'}
            type="error"
            showIcon
          />
        </Card>
      )}

      {/* 候选凭证草稿列表 */}
      {drafts.length > 0 && (
        <div style={{ marginTop: 16 }}>
          {drafts.map((draft, draftIndex) => {
            const balanced = isDraftBalanced(draft)
            const debitTotal = sumDebit(draft)
            const creditTotal = sumCredit(draft)
            return (
              <Card
                key={draftIndex}
                style={{ marginBottom: 16 }}
                title={(
                  <Space>
                    <span>候选凭证 {draftIndex + 1}</span>
                    <Tag color="cyan">
                      {DOCUMENT_TYPE_LABELS[draft.document_type] || draft.document_type}
                    </Tag>
                    <Tag>来源置信度：{(draft.source_confidence * 100).toFixed(1)}%</Tag>
                    {balanced ? (
                      <Tag color="green">借贷平衡</Tag>
                    ) : (
                      <Tag color="red">借贷不平衡</Tag>
                    )}
                  </Space>
                )}
              >
                {/* 校验错误提示 */}
                {draft.validation_errors.length > 0 && (
                  <Alert
                    message="草稿校验错误"
                    description={(
                      <ul style={{ margin: 0, paddingLeft: 20 }}>
                        {draft.validation_errors.map((err, errIndex) => (
                          <li key={errIndex}>{err}</li>
                        ))}
                      </ul>
                    )}
                    type="error"
                    showIcon
                    style={{ marginBottom: 16 }}
                  />
                )}

                {/* 可编辑的凭证头部信息 */}
                <Row gutter={16} style={{ marginBottom: 16 }}>
                  <Col span={6}>
                    <div style={{ marginBottom: 4 }}>
                      <span style={{ color: '#666' }}>凭证号</span>
                    </div>
                    <Input
                      value={draft.voucher_no}
                      onChange={(e) => handleDraftFieldChange(draftIndex, 'voucher_no', e.target.value)}
                      placeholder="凭证号"
                    />
                  </Col>
                  <Col span={6}>
                    <div style={{ marginBottom: 4 }}>
                      <span style={{ color: '#666' }}>凭证日期</span>
                    </div>
                    <DatePicker
                      value={draft.voucher_date ? dayjs(draft.voucher_date) : null}
                      onChange={(date) => handleDraftDateChange(draftIndex, date)}
                      style={{ width: '100%' }}
                      placeholder="选择凭证日期"
                    />
                  </Col>
                  <Col span={12}>
                    <div style={{ marginBottom: 4 }}>
                      <span style={{ color: '#666' }}>凭证摘要</span>
                    </div>
                    <Input
                      value={draft.summary}
                      onChange={(e) => handleDraftFieldChange(draftIndex, 'summary', e.target.value)}
                      placeholder="凭证摘要"
                    />
                  </Col>
                </Row>

                {/* 分录表格 */}
                <Table
                  dataSource={draft.lines}
                  rowKey="_key"
                  rowClassName={() => balanced ? '' : 'pv-unbalanced-row'}
                  columns={buildLineColumns(draftIndex)}
                  pagination={false}
                  size="small"
                  bordered
                />

                {/* 借贷合计行 */}
                <Row gutter={16} style={{ marginTop: 12, padding: '8px 16px', background: '#fafafa', borderRadius: 4 }}>
                  <Col span={8}>
                    <span style={{ color: '#666' }}>借方合计：</span>
                    <strong style={{ fontSize: 16 }}>{formatAmount(debitTotal)}</strong>
                  </Col>
                  <Col span={8}>
                    <span style={{ color: '#666' }}>贷方合计：</span>
                    <strong style={{ fontSize: 16 }}>{formatAmount(creditTotal)}</strong>
                  </Col>
                  <Col span={8}>
                    <span style={{ color: '#666' }}>差额：</span>
                    <strong style={{ fontSize: 16, color: balanced ? '#52c41a' : '#f5222d' }}>
                      {formatAmount(Math.round((debitTotal - creditTotal) * 100) / 100)}
                    </strong>
                    {balanced ? (
                      <Tag color="green" style={{ marginLeft: 8 }}>平衡</Tag>
                    ) : (
                      <Tag color="red" style={{ marginLeft: 8 }}>不平衡</Tag>
                    )}
                  </Col>
                </Row>

                {/* 原始提取数据折叠面板 */}
                <Collapse
                  style={{ marginTop: 16 }}
                  items={[
                    {
                      key: 'raw_data',
                      label: '原始提取数据（解析引擎输出）',
                      children: (
                        <pre style={{ fontSize: 12, background: '#f5f5f5', padding: 12, maxHeight: 320, overflowY: 'auto', whiteSpace: 'pre-wrap', margin: 0 }}>
                          {JSON.stringify(draft.raw_extracted_data, null, 2)}
                        </pre>
                      ),
                    },
                  ]}
                />
              </Card>
            )
          })}

          {/* 底部确认生成凭证按钮 */}
          <Card style={{ marginTop: 16 }}>
            <Space>
              <Button
                type="primary"
                size="large"
                icon={<CheckCircleOutlined />}
                loading={submitting}
                onClick={handleConfirm}
              >
                确认生成凭证草稿
              </Button>
              <Button
                size="large"
                onClick={handleReset}
                disabled={submitting}
              >
                重新上传
              </Button>
            </Space>
            <Alert
              message="确认说明"
              description="确认前请检查所有凭证的借贷平衡。生成的凭证状态为「草稿」，需在凭证列表中进一步复核后才可入账。"
              type="warning"
              showIcon
              style={{ marginTop: 12 }}
            />
          </Card>
        </div>
      )}

      {/* 成功结果展示 */}
      {successResult && (
        <Card style={{ marginTop: 16 }}>
          <Result
            status="success"
            title={`成功创建 ${successResult.created_count} 张凭证草稿`}
            subTitle={successResult.voucher_ids.length > 0 ? `凭证 ID：${successResult.voucher_ids.join(', ')}` : undefined}
            extra={[
              <Button
                type="primary"
                key="view"
                onClick={() => navigate('/ledger/vouchers')}
              >
                查看凭证列表
              </Button>,
              <Button key="reset" onClick={handleReset}>
                继续上传
              </Button>,
            ]}
          />
        </Card>
      )}
    </div>
  )
}
