import {
  Alert,
  Button,
  Checkbox,
  Card,
  Col,
  Input,
  Modal,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api, type AuditFinding, type MasterSyncResult, type WorkbenchItem } from '../api/client'
import { describeMasterSync } from '../components/dimensions/masterSyncUtils'
import { useAuthStore } from '../stores/authStore'

function ControlDefectDisplayNameEditor({
  initialValue,
  onSave,
}: {
  initialValue: string
  onSave: (displayName: string, syncToMaster: boolean) => Promise<{
    resolved_findings?: number
    master_sync?: MasterSyncResult | null
  }>
}) {
  const [value, setValue] = useState(initialValue)
  const [syncToMaster, setSyncToMaster] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    setValue(initialValue)
  }, [initialValue])

  const handleSave = async () => {
    const next = value.trim()
    if (!next) {
      message.warning('规范全称不能为空')
      return
    }
    setSaving(true)
    try {
      const result = await onSave(next, syncToMaster)
      const syncMsg = describeMasterSync(result.master_sync)
      if (result.resolved_findings && result.resolved_findings > 0) {
        message.success(
          syncMsg
            ? `已保存并自动关闭 ${result.resolved_findings} 条提醒；${syncMsg}`
            : `已保存并自动关闭 ${result.resolved_findings} 条提醒`,
        )
      } else if (syncMsg) {
        message.success(`已保存规范全称；${syncMsg}`)
      } else {
        message.success('已保存规范全称')
      }
    } catch (error) {
      message.error(error instanceof Error ? error.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Space direction="vertical" size={4} style={{ width: '100%' }}>
      <Space.Compact style={{ width: '100%' }}>
        <Input
          size="small"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="输入银行规范全称"
          onPressEnter={() => void handleSave()}
        />
        <Button type="primary" size="small" loading={saving} onClick={() => void handleSave()}>
          保存
        </Button>
      </Space.Compact>
      <Checkbox checked={syncToMaster} onChange={(e) => setSyncToMaster(e.target.checked)}>
        同步到主数据
      </Checkbox>
    </Space>
  )
}

const { Title, Text, Paragraph } = Typography

type ReviewStatus = 'pending' | 'confirmed' | 'false_positive' | 'resolved'

const STATUS_LABEL: Record<string, string> = {
  pending: '待处理',
  confirmed: '已确认',
  false_positive: '误报',
  resolved: '已解决',
}

const STATUS_COLOR: Record<string, string> = {
  pending: 'orange',
  confirmed: 'red',
  false_positive: 'default',
  resolved: 'green',
}

const DEFECT_LABEL: Record<string, string> = {
  bank_name_not_standardized: '银行户名未规范',
}

const SOURCE_LABEL: Record<string, string> = {
  internal_control: '内控规则',
  dimension: '维度待办',
  risk: '风险提醒',
}

const SOURCE_COLOR: Record<string, string> = {
  internal_control: 'purple',
  dimension: 'blue',
  risk: 'red',
}

const SEVERITY_LABEL: Record<string, string> = {
  blocking: '阻塞',
  warning: '警告',
  info: '提示',
}

const SEVERITY_COLOR: Record<string, string> = {
  blocking: 'red',
  warning: 'orange',
  info: 'default',
}

export function ControlDefectsPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { currentLedgerId } = useAuthStore()
  const jobIdParam = Number(searchParams.get('jobId') || 0)
  const statusFilter = searchParams.get('status') || 'pending'
  const sourceFilter = searchParams.get('source') || 'all'

  const [workbenchItems, setWorkbenchItems] = useState<WorkbenchItem[]>([])
  const [summary, setSummary] = useState({
    total: 0,
    blocking: 0,
    warning: 0,
    info: 0,
    by_source: { internal_control: 0, dimension: 0, risk: 0 },
  })
  const [findings, setFindings] = useState<AuditFinding[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [currentFinding, setCurrentFinding] = useState<AuditFinding | null>(null)
  const [reviewAction, setReviewAction] = useState<ReviewStatus>('resolved')
  const [reviewComment, setReviewComment] = useState('')

  const loadWorkbench = async () => {
    if (!currentLedgerId) {
      setWorkbenchItems([])
      setFindings([])
      return
    }
    setLoading(true)
    try {
      const [queue, icFindings] = await Promise.all([
        api.listWorkbenchItems({
          ledgerId: currentLedgerId,
          status: statusFilter === 'all' ? 'all' : statusFilter,
          source: sourceFilter === 'all' ? undefined : sourceFilter,
          jobId: jobIdParam || undefined,
        }),
        api.searchAuditFindings({
          ledgerId: currentLedgerId,
          jobId: jobIdParam || undefined,
          findingType: 'internal_control',
          status: statusFilter === 'all' ? undefined : statusFilter,
        }),
      ])
      setWorkbenchItems(queue.items)
      setSummary(queue.summary)
      setFindings(icFindings)
    } catch (error) {
      message.error('加载工作台待办失败')
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadWorkbench()
  }, [currentLedgerId, jobIdParam, statusFilter, sourceFilter])

  const openReviewModal = (finding: AuditFinding) => {
    setCurrentFinding(finding)
    setReviewAction((finding.status as ReviewStatus) || 'resolved')
    setReviewComment('')
    setModalOpen(true)
  }

  const openReviewByWorkbenchItem = (item: WorkbenchItem) => {
    if (!item.related_finding_id) return
    const finding = findings.find((row) => row.db_id === item.related_finding_id)
    if (finding) openReviewModal(finding)
  }

  const workbenchColumns: ColumnsType<WorkbenchItem> = [
    {
      title: '来源',
      dataIndex: 'source',
      width: 100,
      render: (source: string) => (
        <Tag color={SOURCE_COLOR[source] || 'default'}>{SOURCE_LABEL[source] || source}</Tag>
      ),
    },
    {
      title: '严重度',
      dataIndex: 'severity',
      width: 80,
      render: (severity: string) => (
        <Tag color={SEVERITY_COLOR[severity] || 'default'}>{SEVERITY_LABEL[severity] || severity}</Tag>
      ),
    },
    {
      title: '待办标题',
      dataIndex: 'title',
      ellipsis: true,
    },
    {
      title: '任务',
      dataIndex: 'job_id',
      width: 80,
      render: (jobId?: number) =>
        jobId ? <Link to={`/ledger/vouchers/step/4?jobId=${jobId}`}>#{jobId}</Link> : '-',
    },
    {
      title: '建议操作',
      key: 'action',
      width: 220,
      render: (_, row) => (
        <Space wrap>
          {row.suggested_path && (
            <Link to={row.suggested_path}>{row.suggested_action || '前往处理'}</Link>
          )}
          {row.source === 'internal_control' && row.related_finding_id && (
            <Button type="link" size="small" onClick={() => openReviewByWorkbenchItem(row)}>
              复核
            </Button>
          )}
        </Space>
      ),
    },
  ]

  const internalControlColumns: ColumnsType<AuditFinding> = [
    {
      title: '状态',
      dataIndex: 'status',
      width: 88,
      render: (status: string) => (
        <Tag color={STATUS_COLOR[status] || 'default'}>{STATUS_LABEL[status] || status}</Tag>
      ),
    },
    {
      title: '来源段',
      key: 'bank_sub',
      width: 88,
      render: (_, row) => String(row.metadata?.source_sub_code || '-'),
    },
    {
      title: '规范全称',
      key: 'display_name_edit',
      width: 280,
      render: (_, row) => {
        const meta = row.metadata || {}
        const jobId = row.job_id
        const accountCode = String(meta.account_code || '1002')
        const categoryCode = String(meta.category_code || 'bank_account')
        const tagValue = String(meta.tag_value || meta.display_name || '')
        if (!jobId || !tagValue) return '-'
        return (
          <ControlDefectDisplayNameEditor
            initialValue={String(meta.display_name || tagValue)}
            onSave={async (displayName, syncToMaster) => {
              const result = await api.updateDimensionDisplayName(jobId, {
                account_code: accountCode,
                category_code: categoryCode,
                tag_value: tagValue,
                display_name: displayName,
                source_sub_code: meta.source_sub_code ? String(meta.source_sub_code) : undefined,
                name_standardized: true,
                sync_to_master: syncToMaster,
              })
              await loadWorkbench()
              return result
            }}
          />
        )
      },
    },
    {
      title: '缺陷类型',
      key: 'defect',
      width: 140,
      render: (_, row) => {
        const code = String(row.metadata?.control_defect || '')
        return DEFECT_LABEL[code] || code || row.business_type || '-'
      },
    },
    {
      title: '导入任务',
      dataIndex: 'job_id',
      width: 88,
      render: (jobId?: number) =>
        jobId ? (
          <Link to={`/ledger/vouchers/step/4?jobId=${jobId}`}>#{jobId}</Link>
        ) : (
          '-'
        ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      width: 168,
      render: (v?: string | null) => (v ? new Date(v).toLocaleString() : '-'),
    },
    {
      title: '操作',
      key: 'actions',
      width: 100,
      render: (_, row) => (
        <Button type="link" size="small" onClick={() => openReviewModal(row)}>
          复核
        </Button>
      ),
    },
  ]

  const handleReview = async () => {
    if (!currentFinding?.db_id) {
      message.error('该记录无法复核')
      return
    }
    try {
      const updated = await api.reviewAuditFinding(currentFinding.db_id, reviewAction, reviewComment)
      setFindings((prev) => prev.map((item) => (item.db_id === updated.db_id ? updated : item)))
      await loadWorkbench()
      message.success('复核已留痕')
      setModalOpen(false)
    } catch (error) {
      message.error(error instanceof Error ? error.message : '复核失败')
    }
  }

  const showInternalControlDetail = sourceFilter === 'internal_control'

  return (
    <div style={{ padding: 24 }}>
      <Title level={3} style={{ marginTop: 0 }}>
        内控待办工作台
      </Title>
      <Paragraph type="secondary">
        合并内控规则、维度待办与风险提醒的统一清单。系统仅通知、不强制阻止过账或关账。
      </Paragraph>

      {!currentLedgerId && (
        <Alert type="warning" showIcon style={{ marginBottom: 16 }} title="请先在顶部选择账簿" />
      )}

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col xs={12} sm={6}><Card size="small"><Statistic title="待办总数" value={summary.total} /></Card></Col>
        <Col xs={12} sm={6}><Card size="small"><Statistic title="内控" value={summary.by_source.internal_control} /></Card></Col>
        <Col xs={12} sm={6}><Card size="small"><Statistic title="维度" value={summary.by_source.dimension} /></Card></Col>
        <Col xs={12} sm={6}><Card size="small"><Statistic title="风险" value={summary.by_source.risk} /></Card></Col>
      </Row>

      <Card style={{ marginBottom: 16 }}>
        <Space wrap style={{ marginBottom: 16 }}>
          <span>来源</span>
          <Select
            style={{ width: 140 }}
            value={sourceFilter}
            onChange={(value) => {
              const next = new URLSearchParams(searchParams)
              next.set('source', value)
              setSearchParams(next)
            }}
            options={[
              { value: 'all', label: '全部来源' },
              { value: 'internal_control', label: '内控规则' },
              { value: 'dimension', label: '维度待办' },
              { value: 'risk', label: '风险提醒' },
            ]}
          />
          <span>状态</span>
          <Select
            style={{ width: 140 }}
            value={statusFilter}
            onChange={(value) => {
              const next = new URLSearchParams(searchParams)
              next.set('status', value)
              setSearchParams(next)
            }}
            options={[
              { value: 'pending', label: '待处理' },
              { value: 'resolved', label: '已解决' },
              { value: 'all', label: '全部' },
            ]}
          />
          <span>任务 ID</span>
          <Input
            style={{ width: 120 }}
            placeholder="可选"
            value={jobIdParam || ''}
            onChange={(e) => {
              const next = new URLSearchParams(searchParams)
              const raw = e.target.value.trim()
              if (raw) next.set('jobId', raw)
              else next.delete('jobId')
              setSearchParams(next)
            }}
          />
          <Button onClick={() => void loadWorkbench()}>刷新</Button>
          <Button type="link" onClick={() => navigate('/ledger/dimensions')}>账簿维度管理</Button>
          <Button type="link" onClick={() => navigate('/risks')}>风险列表</Button>
        </Space>

        <Table
          rowKey="id"
          loading={loading}
          columns={workbenchColumns}
          dataSource={workbenchItems}
          pagination={{ pageSize: 20, showSizeChanger: true }}
          expandable={{
            expandedRowRender: (row) => (
              <div style={{ maxWidth: 960 }}>
                <Paragraph style={{ marginBottom: 8 }}>{row.description || '-'}</Paragraph>
                {row.metadata && Object.keys(row.metadata).length > 0 && (
                  <pre style={{ margin: 0, fontSize: 12, maxHeight: 160, overflow: 'auto' }}>
                    {JSON.stringify(row.metadata, null, 2)}
                  </pre>
                )}
              </div>
            ),
          }}
        />
      </Card>

      {showInternalControlDetail && (
        <Card title="内控缺陷明细（可编辑规范全称）">
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
            title="处理建议"
            description={
              <div>
                <div>1. 在 Step4「维度注册表」或凭证抽屉中编辑规范全称；</div>
                <div>2. 对照「账簿维度管理」中的开户清单核对；</div>
                <div>3. 确认无误后复核关闭。</div>
              </div>
            }
          />
          <Table
            rowKey={(row) => String(row.db_id || row.id)}
            loading={loading}
            columns={internalControlColumns}
            dataSource={findings}
            pagination={{ pageSize: 10 }}
            expandable={{
              expandedRowRender: (row) => (
                <div style={{ maxWidth: 960 }}>
                  <Text strong>说明：</Text>
                  <Paragraph style={{ marginBottom: 8 }}>{row.finding_description || '-'}</Paragraph>
                  <Text strong>建议：</Text>
                  <Paragraph style={{ marginBottom: 0 }}>{row.recommendation || '-'}</Paragraph>
                </div>
              ),
            }}
          />
        </Card>
      )}

      <Modal
        title="复核内控缺陷"
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={() => void handleReview()}
        okText="提交复核"
      >
        {currentFinding && (
          <div>
            <Paragraph>
              <Text strong>{currentFinding.finding_title}</Text>
            </Paragraph>
            <Paragraph type="secondary">{currentFinding.finding_description}</Paragraph>
            <div style={{ marginBottom: 12 }}>
              <div style={{ marginBottom: 4 }}>复核结论</div>
              <Select
                style={{ width: '100%' }}
                value={reviewAction}
                onChange={setReviewAction}
                options={[
                  { value: 'resolved', label: '已解决' },
                  { value: 'confirmed', label: '确认缺陷' },
                  { value: 'false_positive', label: '误报' },
                  { value: 'pending', label: '退回待处理' },
                ]}
              />
            </div>
            <div>
              <div style={{ marginBottom: 4 }}>备注</div>
              <Input.TextArea rows={3} value={reviewComment} onChange={(e) => setReviewComment(e.target.value)} />
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
