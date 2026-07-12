import {
  Alert,
  Button,
  Card,
  Checkbox,
  Collapse,
  Descriptions,
  Drawer,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { LeftOutlined, RightOutlined, SafetyCertificateOutlined } from '@ant-design/icons'
import { api, type AccountingEntry } from '../../api/client'
import { describeMasterSync } from '../dimensions/masterSyncUtils'
import { formatAmount } from '../../money'
import { TagDisplayNameEditor } from './TagDisplayNameEditor'
import { VoucherSignatureStrip, type VoucherSignatureInfo } from './VoucherSignatureStrip'

const { Text, Paragraph } = Typography

export type Step4ComplianceMode =
  | 'skip'
  | 'manual_each'
  | 'threshold_badge'
  | 'threshold_auto'
  | 'random_sample'

export type PreviewVoucherSummary = {
  group_key: string
  voucher_no: string | null
  voucher_date: string | null
  voucher_word: string | null
  line_count: number
  debit_total: number
  credit_total: number
  is_balanced: boolean
  review_status: string
  compliance_hint: string | null
  compliance_severity: string
  spot_check_flag?: boolean
  summary_preview: string | null
  anchor_entry_id: number
  source_preparer_name?: string | null
  cross_reviewed_by_user_id?: number | null
  cross_reviewed_by_name?: string | null
  cross_reviewed_at?: string | null
}

const REVIEW_STATUS_LABEL: Record<string, string> = {
  draft: '待复核',
  verified: '已复核',
  partial: '部分复核',
  ready: '待确认入账',
}

const COMPLIANCE_SEVERITY_COLOR: Record<string, string> = {
  info: 'blue',
  warning: 'orange',
  error: 'red',
}

type StagingVoucherReviewDrawerProps = {
  open: boolean
  jobId: number
  voucher: PreviewVoucherSummary | null
  voucherList: PreviewVoucherSummary[]
  complianceMode?: Step4ComplianceMode
  onClose: () => void
  /** 单张凭证复核状态变更（轻量，不触发整表重载） */
  onReviewStatusChanged?: (groupKey: string, reviewStatus: string) => void
  /** 分录/合规等内容变更后刷新 */
  onChanged?: () => void
  onNavigate: (voucher: PreviewVoucherSummary) => void
}

export function StagingVoucherReviewDrawer({
  open,
  jobId,
  voucher,
  voucherList,
  complianceMode = 'manual_each',
  onClose,
  onReviewStatusChanged,
  onChanged,
  onNavigate,
}: StagingVoucherReviewDrawerProps) {
  const [lines, setLines] = useState<AccountingEntry[]>([])
  const [signature, setSignature] = useState<VoucherSignatureInfo | null>(null)
  const [loadingLines, setLoadingLines] = useState(false)
  const [savingReview, setSavingReview] = useState(false)
  const [localReviewStatus, setLocalReviewStatus] = useState<string>('draft')
  const [complianceRunning, setComplianceRunning] = useState(false)
  const [complianceResult, setComplianceResult] = useState<{
    hint: string | null
    severity: string
    engine?: string
    llm_used?: boolean
    llm_error?: string | null
    llm_reasoning?: string | null
    llm_thinking?: string | null
    findings?: string[]
    similar_case_notes?: string | null
    similar_tag_refs?: Array<{
      score: number
      category_code?: string
      tag_value?: string
      display_name?: string
      voucher_no?: string
      summary?: string
    }>
  } | null>(null)
  const [complianceStreamStatus, setComplianceStreamStatus] = useState('')
  const [complianceStreamThinking, setComplianceStreamThinking] = useState('')
  const [complianceStreamContent, setComplianceStreamContent] = useState('')
  const [configuredLlmModel, setConfiguredLlmModel] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    let cancelled = false
    void api
      .getParserEngineConfig()
      .then((cfg) => {
        if (!cancelled) {
          setConfiguredLlmModel(cfg.ai_reasoning_model || cfg.ai_model || null)
        }
      })
      .catch(() => {
        if (!cancelled) setConfiguredLlmModel(null)
      })
    return () => {
      cancelled = true
    }
  }, [open])

  const groupKey = voucher?.group_key

  useEffect(() => {
    if (voucher) {
      setLocalReviewStatus(voucher.review_status)
    }
  }, [groupKey, voucher?.review_status])

  useEffect(() => {
    if (!open || !jobId || !voucher) {
      setLines([])
      setSignature(null)
      setComplianceResult(null)
      return
    }
    setComplianceResult(null)
    setLoadingLines(true)
    void api
      .getPreviewVoucherLines(jobId, voucher.group_key)
      .then((result) => {
        setLines(result.items as unknown as AccountingEntry[])
        setSignature(
          result.signature ?? {
            source_preparer_name: voucher.source_preparer_name,
            cross_reviewed_by_user_id: voucher.cross_reviewed_by_user_id,
            cross_reviewed_by_name: voucher.cross_reviewed_by_name,
            cross_reviewed_at: voucher.cross_reviewed_at,
          },
        )
      })
      .catch((error) => {
        message.error(error instanceof Error ? error.message : '加载凭证分录失败')
        setLines([])
      })
      .finally(() => setLoadingLines(false))
  }, [open, jobId, groupKey, voucher])

  const saveTagDisplayName = useCallback(
    async (lineId: number, tagIndex: number, displayName: string, syncToMaster: boolean) => {
      if (!jobId) return
      const result = await api.updatePreviewEntry(jobId, lineId, {
        tag_updates: [{ tag_index: tagIndex, display_name: displayName, name_standardized: true }],
        sync_to_master: syncToMaster,
      })
      if (result.entry) {
        setLines((prev) =>
          prev.map((line) =>
            line.id === lineId ? ({ ...line, ...result.entry } as AccountingEntry) : line,
          ),
        )
      }
      const syncMsg = describeMasterSync(result.master_sync)
      if (syncMsg) {
        message.info(syncMsg)
      }
      onChanged?.()
    },
    [jobId, onChanged],
  )

  const lineColumns: ColumnsType<AccountingEntry> = useMemo(
    () => [
      { title: '行', dataIndex: 'entry_line_no', width: 48 },
      {
        title: '入账科目',
        key: 'resolved_account',
        width: 180,
        ellipsis: true,
        render: (_: unknown, row) => {
          const code = row.resolved_account_code || row.account_code
          const name = row.resolved_account_name || row.account_name
          return code || name ? `${code || ''} ${name || ''}`.trim() : '-'
        },
      },
      {
        title: '维度实例（可编辑全称）',
        key: 'entry_tags',
        width: 240,
        render: (_: unknown, row) => {
          const tags = row.entry_tags_payload || []
          if (!tags.length) return '-'
          return (
            <Space size={4} wrap direction="vertical" style={{ width: '100%' }}>
              {tags.map((tag, tagIndex) => (
                <TagDisplayNameEditor
                  key={`${row.id}-${tag.category_code}-${tag.source_sub_code}-${tag.tag_value}-${tagIndex}`}
                  tag={tag}
                  tagIndex={tagIndex}
                  compact
                  onSave={(index, displayName, syncToMaster) =>
                    saveTagDisplayName(row.id, index, displayName, syncToMaster)
                  }
                />
              ))}
            </Space>
          )
        },
      },
      {
        title: '原科目',
        key: 'original_account',
        width: 160,
        ellipsis: true,
        render: (_: unknown, row) => {
          const text = `${row.account_code || ''} ${row.account_name || ''}`.trim()
          return text || '-'
        },
      },
      { title: '摘要', dataIndex: 'summary', ellipsis: true, render: (v) => v || '-' },
      {
        title: '借方',
        dataIndex: 'debit_amount',
        width: 100,
        align: 'right',
        render: (v: number) => (v > 0 ? formatAmount(v) : '-'),
      },
      {
        title: '贷方',
        dataIndex: 'credit_amount',
        width: 100,
        align: 'right',
        render: (v: number) => (v > 0 ? formatAmount(v) : '-'),
      },
      { title: '对方单位', dataIndex: 'counterparty', ellipsis: true, render: (v) => v || '-' },
    ],
    [saveTagDisplayName],
  )

  const toggleVerified = useCallback(async () => {
    if (!jobId || !voucher || savingReview) return
    const previousStatus = localReviewStatus
    const nextStatus = localReviewStatus === 'verified' ? 'draft' : 'verified'
    setSavingReview(true)
    setLocalReviewStatus(nextStatus)
    try {
      await api.updatePreviewEntry(jobId, voucher.anchor_entry_id, { review_status: nextStatus })
      message.success(nextStatus === 'draft' ? '已取消整张凭证复核' : '已标记本张凭证复核')
      onReviewStatusChanged?.(voucher.group_key, nextStatus)
      void api
        .getPreviewVoucherLines(jobId, voucher.group_key)
        .then((refreshed) => setSignature(refreshed.signature ?? null))
        .catch(() => undefined)
    } catch (error) {
      setLocalReviewStatus(previousStatus)
      message.error(error instanceof Error ? error.message : '更新复核状态失败')
    } finally {
      setSavingReview(false)
    }
  }, [jobId, voucher, savingReview, localReviewStatus, onReviewStatusChanged])

  const runComplianceForVoucher = useCallback(async () => {
    if (!jobId || !voucher?.group_key) {
      message.warning('无法定位当前凭证，请关闭后重新打开')
      return
    }
    setComplianceRunning(true)
    setComplianceStreamStatus('准备合规审查…')
    setComplianceStreamThinking('')
    setComplianceStreamContent('')
    try {
      const result = await api.complianceReviewStream(jobId, 'each', {
        groupKeys: [voucher.group_key],
        useLlm: true,
        onEvent: (event) => {
          if (event.type === 'models') {
            setConfiguredLlmModel(event.active_model)
            setComplianceStreamStatus(
              `解析模型：${event.parse_model} · 推理模型：${event.reasoning_model}${
                event.reasoning_configured ? '' : '（未单独配置，已回退解析模型）'
              }`,
            )
          } else if (event.type === 'status') {
            setComplianceStreamStatus(event.message)
          } else if (event.type === 'vector_done') {
            setComplianceStreamStatus(`向量检索完成，找到 ${event.count} 条相似参考`)
          } else if (event.type === 'thinking') {
            setComplianceStreamThinking(event.text)
          } else if (event.type === 'content') {
            setComplianceStreamContent(event.text)
          }
        },
      })
      if (result.reviewed_vouchers !== 1 || !result.items[0]) {
        message.error('未找到当前凭证的审查结果，请刷新后重试')
        return
      }
      const item = result.items[0]
      setComplianceResult({
        hint: item.compliance_hint,
        severity: item.compliance_severity,
        engine: item.engine,
        llm_used: item.llm_used,
        llm_error: item.llm_error,
        llm_reasoning: item.llm_reasoning,
        llm_thinking: item.llm_thinking,
        findings: item.findings,
        similar_case_notes: item.similar_case_notes,
        similar_tag_refs: item.similar_tag_refs,
      })
      const hint = item.compliance_hint
      message.success(hint ? `合规审查完成：${hint}` : '合规审查完成')
      const refreshed = await api.getPreviewVoucherLines(jobId, voucher.group_key)
      setLines(refreshed.items as unknown as AccountingEntry[])
      onChanged?.()
    } catch (error) {
      message.error(error instanceof Error ? error.message : '合规审查失败')
    } finally {
      setComplianceRunning(false)
      setComplianceStreamStatus('')
    }
  }, [jobId, voucher, onChanged])

  if (!voucher) {
    return null
  }

  const currentIndex = voucherList.findIndex((item) => item.group_key === voucher.group_key)
  const hasPrev = currentIndex > 0
  const hasNext = currentIndex >= 0 && currentIndex < voucherList.length - 1
  const isVerified = localReviewStatus === 'verified'

  const complianceHint =
    complianceResult?.hint ?? lines.find((line) => line.compliance_hint)?.compliance_hint ?? voucher.compliance_hint
  const complianceSeverity =
    complianceResult?.severity ??
    lines.find((line) => line.compliance_hint)?.compliance_severity ??
    voucher.compliance_severity
  const complianceDetail = complianceResult

  const complianceEnabled = complianceMode !== 'skip'
  const showComplianceButton =
    complianceMode === 'manual_each' ||
    (complianceMode === 'threshold_badge' && Boolean(voucher.spot_check_flag))

  return (
    <Drawer
      title={complianceEnabled ? '凭证复核与合规审查' : '凭证复核'}
      width={1200}
      open={open}
      onClose={onClose}
      destroyOnClose
      extra={
        <Space>
          <Button icon={<LeftOutlined />} disabled={!hasPrev} onClick={() => hasPrev && onNavigate(voucherList[currentIndex - 1])}>
            上一张
          </Button>
          <Button icon={<RightOutlined />} disabled={!hasNext} onClick={() => hasNext && onNavigate(voucherList[currentIndex + 1])}>
            下一张
          </Button>
        </Space>
      }
      footer={
        <Space style={{ width: '100%', justifyContent: 'space-between' }}>
          <Spin spinning={savingReview} size="small">
            <Checkbox
              checked={isVerified}
              disabled={savingReview}
              onChange={() => void toggleVerified()}
            >
              {savingReview ? '正在保存复核…' : '标记本张凭证已复核'}
            </Checkbox>
          </Spin>
          <Space>
            <Button onClick={onClose}>关闭</Button>
            {hasNext && (
              <Button type="primary" onClick={() => onNavigate(voucherList[currentIndex + 1])}>
                下一张凭证
              </Button>
            )}
          </Space>
        </Space>
      }
    >
      <Descriptions bordered size="small" column={3} style={{ marginBottom: 16 }}>
        <Descriptions.Item label="凭证日期">{voucher.voucher_date || '-'}</Descriptions.Item>
        <Descriptions.Item label="凭证号">{voucher.voucher_no || '-'}</Descriptions.Item>
        <Descriptions.Item label="分录行数">{voucher.line_count}</Descriptions.Item>
        <Descriptions.Item label="复核状态">
          <Tag color={isVerified ? 'green' : localReviewStatus === 'partial' ? 'orange' : 'default'}>
            {REVIEW_STATUS_LABEL[localReviewStatus] || localReviewStatus}
          </Tag>
        </Descriptions.Item>
        <Descriptions.Item label="借方合计">{formatAmount(voucher.debit_total)}</Descriptions.Item>
        <Descriptions.Item label="贷方合计">{formatAmount(voucher.credit_total)}</Descriptions.Item>
        <Descriptions.Item label="借贷平衡" span={2}>
          {voucher.is_balanced ? <Tag color="green">平衡</Tag> : <Tag color="red">不平衡</Tag>}
        </Descriptions.Item>
        {voucher.summary_preview && (
          <Descriptions.Item label="摘要预览" span={2}>
            {voucher.summary_preview}
          </Descriptions.Item>
        )}
      </Descriptions>

      <VoucherSignatureStrip
        signature={
          signature ?? {
            source_preparer_name: voucher.source_preparer_name,
            cross_reviewed_by_name: voucher.cross_reviewed_by_name,
            cross_reviewed_at: voucher.cross_reviewed_at,
          }
        }
        showReviewerHint
      />

      {complianceEnabled && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          title="按整张凭证审查"
          description={
            complianceMode === 'threshold_badge' && voucher.spot_check_flag
              ? '本张凭证已标记为「建议审查」，可点击下方按钮运行 LLM 合规审查。'
              : '合规审查仅针对当前这一张凭证：先从向量库检索相似 Tag 参考，再调用 LLM 做语义合规识别。'
          }
        />
      )}

      {showComplianceButton && (
        <Space direction="vertical" style={{ marginBottom: 16, width: '100%' }} size="small">
          {complianceRunning && (
            <Alert
              type="info"
              showIcon
              message="LLM 合规审查进行中"
              description={
                complianceStreamStatus
                || `使用「推理模型」${configuredLlmModel ? `（${configuredLlmModel}）` : ''}，单张凭证审查通常需要 1–10 分钟，下方可实时查看输出。`
              }
            />
          )}
          {(complianceRunning || complianceStreamThinking || complianceStreamContent) && (
            <Card size="small" title="本地大模型实时输出" style={{ width: '100%' }}>
              <Collapse
                defaultActiveKey={['thinking', 'content']}
                items={[
                  {
                    key: 'thinking',
                    label: `思索过程${complianceStreamThinking ? `（${complianceStreamThinking.length} 字）` : ''}`,
                    children: (
                      <pre
                        style={{
                          margin: 0,
                          maxHeight: 220,
                          overflow: 'auto',
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-word',
                          fontSize: 12,
                          background: '#fafafa',
                          padding: 12,
                          borderRadius: 6,
                        }}
                      >
                        {complianceStreamThinking || (
                          complianceRunning
                            ? '等待模型开始思索…（当前模型可能不支持思索输出，请查看「正式回复」）'
                            : '（无思索输出 — 仅 deepseek-r1、qwen3 等推理模型支持 Ollama thinking 通道）'
                        )}
                      </pre>
                    ),
                  },
                  {
                    key: 'content',
                    label: `正式回复${complianceStreamContent ? `（${complianceStreamContent.length} 字）` : ''}`,
                    children: (
                      <pre
                        style={{
                          margin: 0,
                          maxHeight: 220,
                          overflow: 'auto',
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-word',
                          fontSize: 12,
                          background: '#f6ffed',
                          padding: 12,
                          borderRadius: 6,
                        }}
                      >
                        {complianceStreamContent || (complianceRunning ? '等待模型输出 JSON 结论…' : '（无回复输出）')}
                      </pre>
                    ),
                  },
                ]}
              />
            </Card>
          )}
          <Space>
            <Button
              icon={<SafetyCertificateOutlined />}
              loading={complianceRunning}
              onClick={() => void runComplianceForVoucher()}
            >
              {complianceRunning ? '审查中…' : '审查本张凭证'}
            </Button>
            {voucher.spot_check_flag && <Tag color="orange">建议审查</Tag>}
          </Space>
        </Space>
      )}

      {complianceEnabled && complianceHint && (
        <Alert
          type={complianceSeverity === 'error' ? 'error' : complianceSeverity === 'warning' ? 'warning' : 'info'}
          showIcon
          style={{ marginBottom: 16 }}
          title="合规提示"
          description={
            <div>
              <div>{complianceHint}</div>
              {complianceDetail?.engine && (
                <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
                  审查引擎：{complianceDetail.engine}
                  {complianceDetail.llm_used ? '（已启用 LLM 语义识别）' : ''}
                </Text>
              )}
              {complianceDetail?.llm_error && !complianceDetail.llm_used && (
                <Text type="warning" style={{ display: 'block', marginTop: 8 }}>
                  LLM 未参与：{complianceDetail.llm_error}
                </Text>
              )}
              {complianceDetail?.llm_reasoning && (
                <Paragraph style={{ marginTop: 8, marginBottom: 0 }}>{complianceDetail.llm_reasoning}</Paragraph>
              )}
              {complianceDetail?.llm_thinking && (
                <Collapse
                  style={{ marginTop: 8 }}
                  items={[
                    {
                      key: 'thinking',
                      label: 'LLM 思索过程',
                      children: (
                        <Paragraph style={{ marginBottom: 0, whiteSpace: 'pre-wrap' }}>
                          {complianceDetail.llm_thinking}
                        </Paragraph>
                      ),
                    },
                  ]}
                />
              )}
              {complianceDetail?.findings && complianceDetail.findings.length > 0 && (
                <ul style={{ marginTop: 8, marginBottom: 0, paddingLeft: 20 }}>
                  {complianceDetail.findings.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              )}
              {complianceDetail?.similar_case_notes && (
                <Paragraph type="secondary" style={{ marginTop: 8, marginBottom: 0 }}>
                  向量参考对照：{complianceDetail.similar_case_notes}
                </Paragraph>
              )}
            </div>
          }
        />
      )}

      {complianceDetail?.similar_tag_refs && complianceDetail.similar_tag_refs.length > 0 && (
        <>
          <Text strong>向量库相似 Tag 参考</Text>
          <Table
            style={{ marginTop: 8, marginBottom: 16 }}
            rowKey={(row) => `${row.tag_value}-${row.voucher_no}-${row.score}`}
            size="small"
            pagination={false}
            dataSource={complianceDetail.similar_tag_refs}
            columns={[
              { title: '相似度', dataIndex: 'score', width: 72, render: (v: number) => v.toFixed(3) },
              { title: 'Tag', dataIndex: 'display_name', ellipsis: true, render: (v, row) => v || row.tag_value || '-' },
              { title: '分类', dataIndex: 'category_code', width: 88, render: (v) => v || '-' },
              { title: '参考凭证', dataIndex: 'voucher_no', width: 96, render: (v) => v || '-' },
              { title: '摘要', dataIndex: 'summary', ellipsis: true, render: (v) => v || '-' },
            ]}
          />
        </>
      )}

      <Text strong>分录明细</Text>
      <Table
        style={{ marginTop: 8 }}
        rowKey="id"
        size="small"
        loading={loadingLines}
        columns={lineColumns}
        dataSource={lines}
        pagination={false}
        scroll={{ x: 980, y: 360 }}
      />

      {!voucher.is_balanced && (
        <Paragraph type="danger" style={{ marginTop: 12 }}>
          本张凭证借贷不平衡，请返回上一步修正后再复核。
        </Paragraph>
      )}
    </Drawer>
  )
}
