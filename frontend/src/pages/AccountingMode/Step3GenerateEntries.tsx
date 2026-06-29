import { Card, Table, Button, Steps, Typography, Tag, Space, message, Alert, Radio } from 'antd'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { useEffect, useState } from 'react'
import type { ColumnsType } from 'antd/es/table'
import { api, type EntryDraft } from '../../api/client'
import { FlowNav } from '../../components/FlowNav'

const ACCOUNTING_JUDGMENT_OPTIONS = [
  {
    value: 'compliant_default',
    label: '默认合规（谨慎）',
    hint: '有出库单时先确认收入，发票主要补销项税；无出库则发票确认收入+销项税+应收。',
  },
  {
    value: 'revenue_first',
    label: '收入确认优先',
    hint: '出库/履约时点优先确认收入，发票主要用于补齐税额。',
  },
  {
    value: 'counterparty_first',
    label: '往来确认优先',
    hint: '发票优先挂应收或冲减预收，再匹配收款与出库资料。',
  },
] as const

type AccountingJudgmentPolicy = (typeof ACCOUNTING_JUDGMENT_OPTIONS)[number]['value']

const { Title } = Typography

const getStringArray = (value: unknown): string[] => {
if (!Array.isArray(value)) return []
return value.map((item) => String(item)).filter(Boolean)
}

const getRecordArray = (value: unknown): Array<Record<string, unknown>> => {
if (!Array.isArray(value)) return []
return value
.filter((item) => item && typeof item === 'object' && !Array.isArray(item))
.map((item) => item as Record<string, unknown>)
}

const isDraftBlocked = (draft: EntryDraft) => {
const metadata = draft.metadata || {}
return metadata.is_blocked === true || metadata.evidence_status === 'insufficient'
}

const isPartialEvidenceDraft = (draft: EntryDraft) => {
const metadata = draft.metadata || {}
return metadata.evidence_status === 'partial'
}

export function Step3GenerateEntries() {
const navigate = useNavigate()
const location = useLocation()
const stepPath = (step: number) => location.pathname.startsWith('/ledger/vouchers/step/') ? `/ledger/vouchers/step/${step}` : `/accounting/step/${step}`
const [searchParams] = useSearchParams()
const inputMode = searchParams.get('inputMode') || 'ai_generated'
const jobId = Number(searchParams.get('jobId') || 0)
const periodId = Number(searchParams.get('periodId') || 0)
const sourceTypes = (searchParams.get('sourceTypes') || '').split(',').filter(Boolean)
const parseSummary = searchParams.get('parseSummary') || ''
const periodMode = searchParams.get('periodMode') || 'fixed'
const adaptiveStartDate = searchParams.get('adaptiveStartDate') || ''
const adaptiveEndDate = searchParams.get('adaptiveEndDate') || ''
const currentStep = 2
const [drafts, setDrafts] = useState<EntryDraft[]>([])
const [loading, setLoading] = useState(false)
const [committing, setCommitting] = useState(false)
const [accountingJudgmentPolicy, setAccountingJudgmentPolicy] = useState<AccountingJudgmentPolicy>('compliant_default')
const blockedDrafts = drafts.filter(isDraftBlocked)
const partialDrafts = drafts.filter(isPartialEvidenceDraft)
const hasBlockedDraft = blockedDrafts.length > 0
const hasPartialDraft = partialDrafts.length > 0

useEffect(() => {
if (!jobId) return
setLoading(true)
api.generateEntries(
  jobId, 
  periodMode === 'fixed' ? (periodId || undefined) : undefined, 
  accountingJudgmentPolicy,
  adaptiveStartDate || undefined,
  adaptiveEndDate || undefined
)
.then(setDrafts)
.catch((error) => {
const detail = error instanceof Error ? error.message : String(error)
  message.error(`生成草稿失败：${detail}`)
      })
      .finally(() => setLoading(false))
  }, [jobId, periodId, accountingJudgmentPolicy, periodMode, adaptiveStartDate, adaptiveEndDate])

  const handleCommit = async () => {
    if (!jobId || hasBlockedDraft) return
    setCommitting(true)
    try {
      const result = await api.commitEntries(jobId, periodId || undefined, drafts)
      message.success(`已保存 ${result.count} 条待复核凭证草稿`)
      const nextParams = new URLSearchParams()
      nextParams.set('inputMode', inputMode)
      nextParams.set('jobId', String(jobId))
      if (periodId) nextParams.set('periodId', String(periodId))
      navigate(`${stepPath(4)}?${nextParams.toString()}`)
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error)
      message.error(`保存草稿失败：${detail}`)
    } finally {
      setCommitting(false)
    }
  }

  const prevParams = new URLSearchParams()
  prevParams.set('inputMode', inputMode)
  if (jobId) prevParams.set('jobId', String(jobId))
  if (periodId) prevParams.set('periodId', String(periodId))
  if (sourceTypes.length > 0) prevParams.set('sourceTypes', sourceTypes.join(','))
  if (parseSummary) prevParams.set('parseSummary', parseSummary)
  const prevQuery = prevParams.toString()

  const continueSupplementEvidence = () => {
    navigate(prevQuery ? `${stepPath(2)}?${prevQuery}` : stepPath(2))
  }

  const switchToManualEntry = async () => {
    if (!jobId || !periodId) return
    const firstBlockedDraft = blockedDrafts[0]
    const draftMetadata = firstBlockedDraft?.metadata || {}
    try {
      await api.logAiDraftManualSwitch(jobId, {
        period_id: periodId,
        reason: String(draftMetadata.missing_reason || '证据不足以达成真实性、准确性、截止性、充分性审计目的，转人工补充分录。'),
        recognized_evidence: getRecordArray(draftMetadata.current_recognized_evidence),
        manual_fields: ['account_code', 'account_name', 'summary', 'counterparty', 'debit_amount', 'credit_amount'],
        draft_metadata: draftMetadata,
      })
      const manualParams = new URLSearchParams()
      manualParams.set('inputMode', 'manual_entry')
      manualParams.set('jobId', String(jobId))
      manualParams.set('periodId', String(periodId))
      navigate(`${stepPath(2)}?${manualParams.toString()}`)
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error)
      message.error(`记录 AI 转人工日志失败：${detail}`)
    }
  }

  const columns: ColumnsType<EntryDraft> = [
    { title: '凭证号', dataIndex: 'voucher_no', key: 'voucher_no' },
    { title: '行号', dataIndex: 'entry_line_no', key: 'entry_line_no' },
    { title: '日期', dataIndex: 'voucher_date', key: 'voucher_date' },
    {
      title: '会计期间',
      key: 'period_code',
      render: (_, record) => {
        const metadata = record.metadata || {}
        const status = metadata.period_detection_status
        const periodCode = String(metadata.period_code || '-')
        if (status === 'matched') return <Tag color="green">{periodCode}</Tag>
        if (status === 'missing_period') return <Tag color="orange">未维护 {periodCode}</Tag>
        if (status === 'invalid_date') return <Tag color="red">日期异常</Tag>
        return <Tag>{periodCode}</Tag>
      }
    },
    { title: '科目代码', dataIndex: 'account_code', key: 'account_code', render: (v) => v || '-' },
    { title: '科目', dataIndex: 'account_name', key: 'account_name', render: (v) => v || '-' },
    { title: '摘要', dataIndex: 'summary', key: 'summary' },
    {
      title: '借方',
      dataIndex: 'debit_amount',
      key: 'debit_amount',
      render: (val: number) => (val > 0 ? `¥${Number(val).toLocaleString()}` : '-')
    },
    {
      title: '贷方',
      dataIndex: 'credit_amount',
      key: 'credit_amount',
      render: (val: number) => (val > 0 ? `¥${Number(val).toLocaleString()}` : '-')
    },
    { title: '对方单位', dataIndex: 'counterparty', key: 'counterparty', render: (v) => v || '-' },
    {
      title: '证据状态',
      key: 'evidence_status',
      render: (_, record) => {
        const metadata = record.metadata || {}
        if (isDraftBlocked(record)) return <Tag color="red">资料不足</Tag>
        if (metadata.evidence_status === 'partial') return <Tag color="orange">暂存-待收款确认</Tag>
        if (metadata.evidence_status === 'sufficient') return <Tag color="green">资料充分</Tag>
        return <Tag>未判断</Tag>
      }
    },
    {
      title: '标签',
      dataIndex: 'tags',
      key: 'tags',
      render: (tags: EntryDraft['tags']) =>
        tags && tags.length > 0
          ? tags.map((t, i) => <Tag key={i} color="blue">{t.tag_type}: {t.tag_value}</Tag>)
          : '-'
    },
  ]

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      <Steps
        current={currentStep}
        items={[
          { title: '选择模式' },
          { title: '导入资料' },
          { title: '生成草稿' },
          { title: '复核调整' },
          { title: '确认入账与导出' }
        ]}
        style={{ marginBottom: '32px' }}
      />

      <FlowNav prev={stepPath(2)} onNext={handleCommit} nextDisabled={!jobId || drafts.length === 0 || hasBlockedDraft || committing} style={{ marginBottom: '16px' }} />

      {!jobId && (
        <Alert
          title="缺少导入任务"
          description="请从导入资料步骤重新进入；如仅缺少会计期间，系统会根据已识别分录日期自动匹配各分录期间。"
          type="warning"
          showIcon
          style={{ marginBottom: '16px' }}
        />
      )}

      {periodId === 0 && jobId > 0 && (
        <Alert
          title="已启用按分录日期自动识别会计期间"
          description="当前链接未指定单一会计期间。系统会按每条分录的凭证日期匹配对应期间；未维护的月份会在表格中标记为“未维护期间”，请先补建会计期间后再正式复核入账。"
          type="info"
          showIcon
          style={{ marginBottom: '16px' }}
        />
      )}

      <Space style={{ marginBottom: '16px', width: '100%', justifyContent: 'space-between' }}>
        <Title level={4} style={{ margin: 0 }}>AI 生成的待复核凭证草稿</Title>
        <Tag color="blue">共 {drafts.length} 条</Tag>
      </Space>

      <Card size="small" style={{ marginBottom: '16px' }} title="会计判断原则（请确认后生成）">
        <Radio.Group
          value={accountingJudgmentPolicy}
          onChange={(event) => setAccountingJudgmentPolicy(event.target.value)}
        >
          <Space direction="vertical">
            {ACCOUNTING_JUDGMENT_OPTIONS.map((option) => (
              <Radio key={option.value} value={option.value}>
                <Space direction="vertical" size={0}>
                  <span>{option.label}</span>
                  <span style={{ color: '#666', fontSize: 12 }}>{option.hint}</span>
                </Space>
              </Radio>
            ))}
          </Space>
        </Radio.Group>
      </Card>

      {(sourceTypes.length > 0 || parseSummary) && (
        <Alert
          title="Step2 原始资料解析上下文"
          description={
            <Space direction="vertical" size={4}>
              {sourceTypes.length > 0 && <div><strong>用户选择资料类型：</strong>{sourceTypes.join('、')}</div>}
              {parseSummary && <div><strong>解析摘要：</strong>{parseSummary}</div>}
            </Space>
          }
          type="info"
          showIcon
          style={{ marginBottom: '16px' }}
        />
      )}

      {hasPartialDraft && !hasBlockedDraft && (
        <Alert
          title="发票已按权责发生制暂存，收款尚未确认"
          description={
            <Space direction="vertical" size="small">
              <div>系统已生成应收与收入草案；补充银行流水后可再生成收款核销分录，现金流量表按收款环节归集。</div>
              <Button size="small" onClick={continueSupplementEvidence}>补充银行流水/回单</Button>
            </Space>
          }
          type="info"
          showIcon
          style={{ marginBottom: '16px' }}
        />
      )}

      {hasBlockedDraft && (
        <Alert
          title="原始资料不足，AI 草稿已暂存但不能保存进入复核"
          description={
            <Space direction="vertical" size="small">
              {blockedDrafts.map((draft, index) => {
                const metadata = draft.metadata || {}
                const missingEvidence = getStringArray(metadata.missing_evidence)
                const suggestedActions = getStringArray(metadata.suggested_actions)
                return (
                  <div key={`${draft.voucher_no}-${draft.entry_line_no}-${index}`}>
                    <div><strong>草稿：</strong>{draft.voucher_no} 第 {draft.entry_line_no} 行</div>
                    <div><strong>缺失资料：</strong>{missingEvidence.length > 0 ? missingEvidence.join('、') : '未明确'}</div>
                    <div><strong>缺失原因：</strong>{String(metadata.missing_reason || '原始资料不足，不能确认业务事实。')}</div>
                    <div><strong>建议动作：</strong>{suggestedActions.length > 0 ? suggestedActions.join('；') : '请补充原始资料或改为人工录入'}</div>
                  </div>
                )
              })}
              <Space>
                <Button size="small" type="primary" onClick={continueSupplementEvidence}>继续补充资料</Button>
                <Button size="small" onClick={switchToManualEntry}>切换人工录入补充分录</Button>
              </Space>
            </Space>
          }
          type="warning"
          showIcon
          style={{ marginBottom: '16px' }}
        />
      )}

      <Card>
        <Table
          columns={columns}
          dataSource={drafts}
          rowKey={(r, idx) => `${r.voucher_no}-${r.entry_line_no}-${idx}`}
          loading={loading}
          pagination={{
            defaultPageSize: 100,
            showSizeChanger: true,
            pageSizeOptions: ['50', '100', '200', '500'],
            showTotal: (total, range) => `第 ${range[0]}-${range[1]} 条 / 共 ${total} 条`,
          }}
          scroll={{ x: 1400, y: 560 }}
          size="small"
        />
        <div style={{ marginTop: '16px', color: '#666', fontSize: '12px' }}>
          <strong>说明：</strong>AI 生成的是待复核凭证草稿，请先检查科目、摘要、借贷金额与对方单位，再保存草稿并进入复核；正式确认入账在复核完成后的确认入账与导出步骤进行。凭证字按"银/收/付/工/转/记"规则生成；未指定单一会计期间时，系统按分录凭证日期识别对应期间。
        </div>
      </Card>

      <div style={{ marginTop: '24px', display: 'flex', gap: '12px' }}>
        <Button onClick={() => navigate(prevQuery ? `${stepPath(2)}?${prevQuery}` : stepPath(2))}>
          上一步
        </Button>
        <Button
          type="primary"
          loading={committing}
          onClick={handleCommit}
          disabled={!jobId || drafts.length === 0 || hasBlockedDraft}
        >
          保存草稿并进入复核
        </Button>
      </div>
    </div>
  )
}
