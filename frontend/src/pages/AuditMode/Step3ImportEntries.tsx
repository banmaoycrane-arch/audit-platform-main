import { Card, Upload, Button, Steps, Typography, message, Table, Space, Tag, Alert, Tabs, Statistic, List, Row, Col } from 'antd'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { InboxOutlined, EyeOutlined, ReloadOutlined, CheckCircleOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { api, type AccountingEntry, type DayBookReport, type EntryTag, type Counterparty, type LlmResolutionStatistics } from '../../api/client'
import { FlowNav } from '../../components/FlowNav'
import { withJobQuery } from '../../utils/navigation'
import { useAuthStore } from '../../stores/authStore'
import { formatAmount } from '../../money'
import { TagList, TagCategoryLegend } from '../../components/import/TagList'
import { ImportResultDetail } from '../../components/import/ImportResultDetail'

const { Dragger } = Upload
const { Title } = Typography

type ImportKind = 'voucher' | 'audit_day_book'

export function Step3ImportEntries() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { currentLedgerId, authContext } = useAuthStore()
  const canUseLedgerWithoutProject = Boolean(authContext?.can_use_ledger_without_project)
  const urlJobId = Number(searchParams.get('jobId') || 0)
  const currentStep = 2
  const [entries, setEntries] = useState<AccountingEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [activeKind, setActiveKind] = useState<ImportKind>('voucher')
  const [dayBookReport, setDayBookReport] = useState<DayBookReport | null>(null)
  const [reportLoading, setReportLoading] = useState(false)
  const [jobId, setJobId] = useState<number>(urlJobId)
  const [jobSourceType, setJobSourceType] = useState<string | null>(null)
  const [jobProjectId, setJobProjectId] = useState<number | null>(null)

  const [entryTags, setEntryTags] = useState<Map<number, EntryTag[]>>(new Map())
  const [counterparties, setCounterparties] = useState<Map<number, Counterparty>>(new Map())
  const [selectedEntry, setSelectedEntry] = useState<AccountingEntry | null>(null)
  const [llmStats, setLlmStats] = useState<LlmResolutionStatistics | null>(null)
  const [llmProcessing, setLlmProcessing] = useState(false)

  const fetchEntryTags = async () => {
    if (!entries.length) return
    try {
      const entryIds = entries.map((entry) => entry.id)
      const tags = await api.batchListEntryTags({
        entry_ids: entryIds,
        ledger_id: currentLedgerId ?? undefined,
      })
      const tagsMap = new Map<number, EntryTag[]>()
      tags.forEach((tag) => {
        const existing = tagsMap.get(tag.entry_id) || []
        existing.push(tag)
        tagsMap.set(tag.entry_id, existing)
      })
      setEntryTags(tagsMap)
    } catch (error) {
      console.error('批量获取标签失败', error)
    }
  }

  const fetchCounterparties = async () => {
    const uniqueIds = entries
      .filter((e) => e.counterparty_id)
      .map((e) => e.counterparty_id as number)
    if (uniqueIds.length === 0) {
      setCounterparties(new Map())
      return
    }
    try {
      const items = await api.batchGetCounterparties(uniqueIds)
      const cpMap = new Map<number, Counterparty>()
      items.forEach((cp) => cpMap.set(cp.id, cp))
      setCounterparties(cpMap)
    } catch (error) {
      console.error('批量获取往来单位失败', error)
    }
  }

  const fetchLlmStats = async () => {
    try {
      const stats = await api.llmGetStatistics(currentLedgerId ?? undefined)
      setLlmStats(stats)
    } catch {
      // ignore
    }
  }

  const handleBatchLlmResolve = async () => {
    setLlmProcessing(true)
    try {
      const result = await api.llmBatchResolve({
        ledger_id: currentLedgerId ?? undefined,
        batch_size: 50,
      })
      message.success(`LLM解析完成：成功 ${result.success_count} 条，失败 ${result.failed_count} 条`)
      await refreshEntries()
      await fetchEntryTags()
      await fetchLlmStats()
    } catch (error) {
      console.error('LLM批量解析失败', error)
      message.error('LLM批量解析失败')
    } finally {
      setLlmProcessing(false)
    }
  }

  const refreshEntries = async () => {
    if (!jobId) return
    setLoading(true)
    try {
      const result = await api.listEntries(jobId)
      setEntries(result.items)
    } catch (error) {
      console.error('获取分录失败', error)
      message.error('获取分录失败')
    } finally {
      setLoading(false)
    }
  }

  const fetchDayBookReport = async () => {
    if (!jobId) return
    setReportLoading(true)
    try {
      const report = await api.getDayBookReport(jobId)
      setDayBookReport(report)
    } catch (error) {
      console.error('获取序时簿检测报告失败', error)
    } finally {
      setReportLoading(false)
    }
  }

  useEffect(() => {
    if (urlJobId) {
      setJobId(urlJobId)
    }
  }, [urlJobId])

  useEffect(() => {
    if (!jobId) {
      setJobSourceType(null)
      setJobProjectId(null)
      return
    }
    api.getImportJob(jobId)
      .then((job) => {
        setJobSourceType(job.source_type)
        setJobProjectId(job.project_id ?? null)
      })
      .catch(() => {
        setJobSourceType(null)
        setJobProjectId(null)
      })
  }, [jobId])

  useEffect(() => {
    refreshEntries()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId])

  useEffect(() => {
    if (entries.length > 0) {
      fetchEntryTags()
      fetchCounterparties()
      fetchLlmStats()
    }
  }, [entries])

  const handleUpload = async (file: File, kind: ImportKind) => {
    let currentJobId = jobId
    if (kind === 'audit_day_book' && jobSourceType !== 'audit_day_book') {
      currentJobId = 0
    }
    if (!currentJobId) {
      if (kind === 'audit_day_book') {
        try {
          if (!jobProjectId && !canUseLedgerWithoutProject) {
            message.warning('未关联项目时请注意资料不可外泄，本次资料将暂按账簿归集。')
          }
          const job = await api.createImportJob('审计项目', 'audit_day_book', currentLedgerId, {
            audit_scope_type: 'all',
            audit_period_id: null,
            audit_account_codes: null,
            project_id: jobProjectId ?? null,
          })
          currentJobId = job.id
          setJobId(currentJobId)
          setJobSourceType(job.source_type)
          setEntries([])
          setDayBookReport(null)
          setEntryTags(new Map())
        } catch (error) {
          console.error('创建导入任务失败', error)
          message.error('创建导入任务失败')
          return
        }
      } else {
        message.warning('请先从上一步导入审计资料，再上传凭证分录')
        return
      }
    }
    setUploading(true)
    try {
      const sourceFile = await api.uploadFile(currentJobId, file)
      const kindLabel = kind === 'audit_day_book' ? '序时簿' : '凭证'
      message.success(`${file.name}（${kindLabel}）上传成功，开始结构化自适应导入（场景 A）`)
      await api.parseSourceFileWithEngine(currentJobId, sourceFile.id)
      message.success('结构化自适应导入完成')
      await refreshEntries()
      if (kind === 'audit_day_book') {
        await fetchDayBookReport()
      }
    } catch (error) {
      console.error('导入分录失败', error)
      message.error(`${file.name} 导入或解析失败`)
    } finally {
      setUploading(false)
    }
  }

  const columns: ColumnsType<AccountingEntry> = [
    {
      title: '凭证号',
      dataIndex: 'voucher_no',
      key: 'voucher_no',
      render: (val: string | null) => val || '-',
      responsive: ['lg'],
    },
    {
      title: '行号',
      dataIndex: 'entry_line_no',
      key: 'entry_line_no',
      responsive: ['lg'],
    },
    {
      title: '日期',
      dataIndex: 'voucher_date',
      key: 'voucher_date',
      render: (val: string | null) => val || '-',
      responsive: ['lg'],
    },
    {
      title: '原始科目',
      key: 'original_account',
      render: (_: unknown, record: AccountingEntry) => {
        const code = record.account_code || '-'
        const name = record.account_name || '-'
        return (
          <div>
            <div style={{ fontWeight: 500 }}>{code}</div>
            <div style={{ fontSize: 12, color: '#999' }}>{name}</div>
          </div>
        )
      },
    },
    {
      title: '解析后科目',
      key: 'resolved_account',
      render: (_: unknown, record: AccountingEntry) => {
        const code = record.resolved_account_code || '-'
        const name = record.resolved_account_name || '-'
        const hasChanged = (record.account_code !== record.resolved_account_code) || (record.account_name !== record.resolved_account_name)
        return (
          <div>
            <div style={{ fontWeight: 500, color: hasChanged ? '#1890ff' : undefined }}>{code}</div>
            <div style={{ fontSize: 12, color: hasChanged ? '#1890ff' : '#999' }}>{name}</div>
            {hasChanged && <Tag color="orange">已解析</Tag>}
          </div>
        )
      },
    },
    {
      title: '摘要',
      dataIndex: 'summary',
      key: 'summary',
      render: (val: string | null) => val || '-',
      responsive: ['lg'],
    },
    {
      title: '辅助核算',
      key: 'tags',
      render: (_: unknown, record: AccountingEntry) => {
        const tags = entryTags.get(record.id) || []
        if (tags.length === 0) {
          return <span style={{ color: '#999' }}>-</span>
        }
        return (
          <Space wrap size="small">
            {tags.slice(0, 3).map((tag) => (
              <Tag key={tag.id} color={getTagColor(tag.category_code)}>
                {tag.display_name}
              </Tag>
            ))}
            {tags.length > 3 && <Tag color="default">+{tags.length - 3}</Tag>}
          </Space>
        )
      },
    },
    {
      title: '往来单位',
      dataIndex: 'counterparty',
      key: 'counterparty',
      render: (val: string | null, record: AccountingEntry) => {
        const cp = record.counterparty_id ? counterparties.get(record.counterparty_id) : null
        if (cp) {
          return (
            <span>
              <Tag color="green">{cp.name}</Tag>
              <span style={{ marginLeft: 4, fontSize: 12, color: '#999' }}>已关联</span>
            </span>
          )
        }
        return val || '-'
      },
      responsive: ['lg'],
    },
    {
      title: '借方金额',
      dataIndex: 'debit_amount',
      key: 'debit_amount',
      render: (val: number) => (val > 0 ? formatAmount(val) : '-'),
      responsive: ['md'],
    },
    {
      title: '贷方金额',
      dataIndex: 'credit_amount',
      key: 'credit_amount',
      render: (val: number) => (val > 0 ? formatAmount(val) : '-'),
      responsive: ['md'],
    },
    {
      title: '状态',
      key: 'status',
      render: (_: unknown, record: AccountingEntry) => (
        <Space size="small">
          {record.requires_llm_resolution && (
            <Tag color="orange">待LLM解析</Tag>
          )}
          {record.review_status !== 'draft' && (
            <Tag color={record.review_status === 'verified' ? 'green' : 'blue'}>
              {record.review_status}
            </Tag>
          )}
        </Space>
      ),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, record: AccountingEntry) => (
        <Button
          size="small"
          icon={<EyeOutlined />}
          onClick={() => setSelectedEntry(record)}
        >
          详情
        </Button>
      ),
    },
  ]

  const getTagColor = (categoryCode: string) => {
    const colors: Record<string, string> = {
      customer: 'blue',
      supplier: 'green',
      product: 'purple',
      department: 'orange',
      project: 'pink',
      region: 'cyan',
      expense_type: 'gold',
      cost_element: 'geekblue',
    }
    return colors[categoryCode] || 'default'
  }

  const renderDragger = (kind: ImportKind) => {
    const isDayBook = kind === 'audit_day_book'
    return (
      <Dragger
        name="files"
        multiple={false}
        disabled={uploading}
        beforeUpload={(file) => {
          handleUpload(file, kind)
          return false
        }}
        accept=".xlsx,.xls,.csv"
        style={{ padding: '40px' }}
      >
        <p className="ant-upload-drag-icon">
          <InboxOutlined />
        </p>
        <p className="ant-upload-text">
          {isDayBook ? '点击或拖拽文件上传被审计单位序时簿' : '点击或拖拽文件上传被审计单位凭证'}
        </p>
        <p className="ant-upload-hint">
          {isDayBook
            ? '序时簿：按日期顺序、连续登记的全部凭证流水。请保留凭证号、日期、借贷金额、对方单位等列，用于完整性 / 截止性 / 跳号检测。'
            : '支持 Excel 或 CSV 格式，包含凭证号、日期、科目、金额等信息。'}
        </p>
      </Dragger>
    )
  }

  const renderDayBookReport = () => {
    if (!dayBookReport) return null
    const hasIssues = dayBookReport.skip_count > 0 || dayBookReport.unbalanced_count > 0 || dayBookReport.missing_voucher_nos.length > 0
    return (
      <Card
        title="序时簿检测报告"
        loading={reportLoading}
        style={{ marginTop: '24px' }}
      >
        <Space size="large" wrap>
          <Statistic title="凭证总数" value={dayBookReport.total_vouchers} />
          <Statistic title="跳号数量" value={dayBookReport.skip_count} valueStyle={{ color: dayBookReport.skip_count > 0 ? '#cf1322' : undefined }} />
          <Statistic title="不平衡凭证数量" value={dayBookReport.unbalanced_count} valueStyle={{ color: dayBookReport.unbalanced_count > 0 ? '#cf1322' : undefined }} />
          <Statistic title="完整性评分" value={dayBookReport.completeness_score} suffix="%" valueStyle={{ color: dayBookReport.completeness_score < 100 ? '#cf1322' : '#3f8600' }} />
        </Space>

        {hasIssues && (
          <Alert
            title="检测到序时簿异常"
            type="warning"
            showIcon
            style={{ marginTop: '16px' }}
          />
        )}

        {dayBookReport.missing_voucher_nos.length > 0 && (
          <div style={{ marginTop: '16px' }}>
            <Title level={5} style={{ marginBottom: '8px' }}>缺失凭证号列表</Title>
            <List
              size="small"
              bordered
              dataSource={dayBookReport.missing_voucher_nos}
              renderItem={(item) => (
                <List.Item>
                  <Tag color="red">{item}</Tag>
                </List.Item>
              )}
            />
          </div>
        )}

        {dayBookReport.unbalanced_vouchers.length > 0 && (
          <div style={{ marginTop: '16px' }}>
            <Title level={5} style={{ marginBottom: '8px' }}>不平衡凭证列表</Title>
            <List
              size="small"
              bordered
              dataSource={dayBookReport.unbalanced_vouchers}
              renderItem={(item) => (
                <List.Item>
                  <Space wrap>
                    <Tag color="red">{item.voucher_no}</Tag>
                    <span>借方合计：{item.debit_total}</span>
                    <span>贷方合计：{item.credit_total}</span>
                    <span>差额：{item.difference}</span>
                  </Space>
                </List.Item>
              )}
            />
          </div>
        )}
      </Card>
    )
  }

  const renderLlmStats = () => {
    if (!llmStats) return null
    return (
      <Card
        title="LLM辅助解析统计"
        style={{ marginTop: '24px' }}
      >
        <Space size="large" wrap>
          <Statistic
            title="待LLM解析"
            value={llmStats.pending_llm_resolution}
            prefix={<ReloadOutlined style={{ color: '#faad14' }} />}
            valueStyle={{ color: '#faad14' }}
          />
          <Statistic
            title="待审批标签"
            value={llmStats.pending_review}
            valueStyle={{ color: '#fa8c16' }}
          />
          <Statistic
            title="已审批标签"
            value={llmStats.reviewed}
            prefix={<CheckCircleOutlined style={{ color: '#52c41a' }} />}
            valueStyle={{ color: '#52c41a' }}
          />
        </Space>

        {llmStats.pending_llm_resolution > 0 && (
          <Button
            type="primary"
            loading={llmProcessing}
            onClick={handleBatchLlmResolve}
            style={{ marginTop: '16px' }}
          >
            批量调用LLM解析辅助核算维度
          </Button>
        )}
      </Card>
    )
  }

  return (
    <div style={{ padding: '24px', maxWidth: '100%', margin: '0 auto' }}>
      <Steps
        current={currentStep}
        items={[
          { title: '选择范围' },
          { title: '导入资料' },
          { title: '导入分录' },
          { title: '执行测试' },
          { title: '复核发现' },
          { title: '导出报告' }
        ]}
        style={{ marginBottom: '32px' }}
      />

      <FlowNav
        prev={withJobQuery('/audit/step/2', jobId)}
        next={withJobQuery('/audit/step/4', jobId)}
        nextDisabled={!jobId || entries.length === 0}
        style={{ marginBottom: '16px' }}
      />

      <Space style={{ marginBottom: '16px', width: '100%', justifyContent: 'space-between' }}>
        <Title level={4} style={{ margin: 0 }}>导入被审计单位分录</Title>
        <Tag color="blue">共 {entries.length} 条</Tag>
      </Space>

      {!jobId && (
        <Alert
          title="尚未找到导入资料"
          description="请从导入资料步骤重新进入；如本次要直接导入序时簿，可在序时簿导入页签上传文件，系统会自动创建序时簿任务。"
          type="warning"
          showIcon
          style={{ marginBottom: '16px' }}
        />
      )}

      {activeKind === 'audit_day_book' && jobId > 0 && jobSourceType !== 'audit_day_book' && (
        <Alert
          title="序时簿将作为单独的审计资料处理"
          description="当前已有任务不是序时簿任务。上传序时簿时，系统会自动新建序时簿任务，用于跳号、完整性和借贷平衡检测。"
          type="info"
          showIcon
          style={{ marginBottom: '16px' }}
        />
      )}

      <Card style={{ marginBottom: '24px' }}>
        <Tabs
          activeKey={activeKind}
          onChange={(key) => setActiveKind(key as ImportKind)}
          items={[
            {
              key: 'voucher',
              label: '凭证导入',
              children: renderDragger('voucher')
            },
            {
              key: 'audit_day_book',
              label: '序时簿导入',
              children: renderDragger('audit_day_book')
            }
          ]}
        />
      </Card>

      <Row gutter={16}>
        <Col xs={24} lg={16}>
          <Card title="已导入的分录" loading={loading}>
            <Table
              columns={columns}
              dataSource={entries}
              rowKey="id"
              pagination={{ pageSize: 10, showSizeChanger: true, showTotal: (total) => `共 ${total} 条` }}
              size="small"
              locale={{ emptyText: jobId ? '暂无分录，请上传被审计单位凭证或序时簿' : '请先上传或选择审计资料' }}
            />
          </Card>

          {activeKind === 'audit_day_book' && dayBookReport && renderDayBookReport()}
        </Col>

        <Col xs={24} lg={8}>
          <TagCategoryLegend />
          {renderLlmStats()}
        </Col>
      </Row>

      <div style={{ marginTop: '24px', display: 'flex', gap: '12px' }}>
        <Button onClick={() => navigate(jobId ? `/audit/step/2?jobId=${jobId}` : '/audit/step/2')}>
          上一步
        </Button>
        <Button
          type="primary"
          onClick={() => navigate(jobId ? `/audit/step/4?jobId=${jobId}` : '/audit/step/4')}
          disabled={!jobId || entries.length === 0}
        >
          下一步执行测试
        </Button>
      </div>

      {selectedEntry && (
        <ImportResultDetail
          entry={selectedEntry}
          tags={entryTags.get(selectedEntry.id) || []}
          counterparty={selectedEntry.counterparty_id ? counterparties.get(selectedEntry.counterparty_id) : undefined}
          onClose={() => setSelectedEntry(null)}
        />
      )}
    </div>
  )
}
