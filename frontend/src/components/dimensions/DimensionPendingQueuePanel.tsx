import { useCallback, useEffect, useMemo, useState } from 'react'
import { Alert, Button, Card, Col, Modal, Row, Select, Space, Statistic, Table, Tag, Typography, message } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { Link } from 'react-router-dom'
import { ReloadOutlined, ThunderboltOutlined } from '@ant-design/icons'
import { api, type DimensionPendingQueueResponse } from '../../api/client'
import {
  QUEUE_TYPE_HINT,
  buildPendingAlertDescription,
  buildPendingAlertTitle,
} from './dimensionReminderCopy'
import { DimensionPendingDisplayNameEditor } from './DimensionPendingDisplayNameEditor'
import { canEditDimensionPendingRow, submitDimensionDisplayName } from './dimensionPendingSave'

const { Text } = Typography

const QUEUE_TYPE_LABEL: Record<string, string> = {
  non_standardized: '待补全称',
  missing_in_master: '主数据里没有',
  requires_llm: '待识别',
  unknown_category: '分类未登记',
  internal_control: '内控提醒',
  mapped: '映射留痕',
}

const QUEUE_TYPE_COLOR: Record<string, string> = {
  non_standardized: 'orange',
  missing_in_master: 'red',
  requires_llm: 'purple',
  unknown_category: 'magenta',
  internal_control: 'blue',
  mapped: 'cyan',
}

const PRIORITY_COLOR: Record<string, string> = {
  high: 'red',
  medium: 'orange',
  low: 'default',
}

type DimensionPendingQueuePanelProps = {
  jobId: number
  onChanged?: () => void
}

export function DimensionPendingQueuePanel({ jobId, onChanged }: DimensionPendingQueuePanelProps) {
  const [data, setData] = useState<DimensionPendingQueueResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [llmResolving, setLlmResolving] = useState(false)
  const [typeFilter, setTypeFilter] = useState<string>('all')
  const [confirmingKey, setConfirmingKey] = useState<string | null>(null)

  const rowActionKey = (row: DimensionPendingQueueResponse['items'][number], index: number) =>
    `${row.queue_type}-${row.tag_value || ''}-${row.account_code || ''}-${index}`

  const handleQuickConfirm = async (row: DimensionPendingQueueResponse['items'][number], index: number) => {
    const key = rowActionKey(row, index)
    setConfirmingKey(key)
    try {
      await submitDimensionDisplayName(
        jobId,
        row,
        row.display_name || row.tag_value || '',
        false,
      )
      await refreshQueueAndNotify()
    } catch {
      // submitDimensionDisplayName 已提示
    } finally {
      setConfirmingKey(null)
    }
  }

  const loadQueue = useCallback(async () => {
    setLoading(true)
    try {
      const result = await api.getDimensionPendingQueue(jobId)
      setData(result)
    } catch (error) {
      console.error('加载待处理队列失败', error)
    } finally {
      setLoading(false)
    }
  }, [jobId])

  useEffect(() => {
    void loadQueue()
  }, [loadQueue])

  const refreshQueueAndNotify = useCallback(async () => {
    await loadQueue()
    onChanged?.()
  }, [loadQueue, onChanged])

  const handleBatchLlmResolve = () => {
    const llmCount = data?.summary.requires_llm || 0
    if (!llmCount) return
    Modal.confirm({
      title: '批量 LLM 识别维度',
      content: `将对本批 ${llmCount} 条待识别分录调用 LLM 从摘要补全维度，结果写入 staging（确认入账前可复核）。需已配置解析引擎 AI 模型。`,
      okText: '开始识别',
      onOk: async () => {
        setLlmResolving(true)
        try {
          const result = await api.resolveStagingLlmTags(jobId, { batch_size: 20 })
          if (result.error_messages?.length) {
            message.warning(result.error_messages.join('；'))
          }
          if (result.resolved_rows > 0) {
            message.success(`已处理 ${result.resolved_rows} 条分录，识别 ${result.success_count} 个维度标签`)
          } else if (!result.error_messages?.length) {
            message.info('LLM 未返回可写入的维度标签')
          }
          await refreshQueueAndNotify()
        } catch (error) {
          message.error(error instanceof Error ? error.message : 'LLM 识别失败')
        } finally {
          setLlmResolving(false)
        }
      },
    })
  }

  const filteredItems = useMemo(() => {
    if (!data) return []
    if (typeFilter === 'all') return data.items
    return data.items.filter((item) => item.queue_type === typeFilter)
  }, [data, typeFilter])

  const columns: ColumnsType<DimensionPendingQueueResponse['items'][number]> = [
    {
      title: '类型',
      dataIndex: 'queue_type',
      width: 130,
      render: (value: string) => (
        <Tag color={QUEUE_TYPE_COLOR[value] || 'default'}>{QUEUE_TYPE_LABEL[value] || value}</Tag>
      ),
    },
    {
      title: '优先级',
      dataIndex: 'priority',
      width: 80,
      render: (value: string) => <Tag color={PRIORITY_COLOR[value] || 'default'}>{value}</Tag>,
    },
    {
      title: '科目',
      dataIndex: 'account_code',
      width: 72,
      render: (value) => value || '-',
    },
    {
      title: '分类',
      dataIndex: 'category_code',
      width: 110,
      render: (value) => value || '-',
    },
    {
      title: '导入原名',
      key: 'original_name',
      width: 160,
      ellipsis: true,
      render: (_, row) => {
        if (row.queue_type === 'mapped') {
          return row.original_display_name || row.tag_value || '-'
        }
        if (row.queue_type === 'non_standardized') {
          return row.tag_value || '-'
        }
        return row.tag_value || '-'
      },
    },
    {
      title: '映射值 / 规范全称',
      key: 'mapped_name',
      width: 220,
      render: (_, row) => {
        if (row.queue_type === 'mapped' || row.queue_type === 'non_standardized') {
          if (!row.account_code || !row.category_code || !row.tag_value) {
            return row.display_name || row.tag_value || '-'
          }
          return (
            <DimensionPendingDisplayNameEditor
              jobId={jobId}
              row={row}
              onSaved={() => void refreshQueueAndNotify()}
            />
          )
        }
        const parts = [row.source_sub_code, row.display_name || row.tag_value].filter(Boolean)
        return parts.join(' · ') || row.summary || '-'
      },
    },
    {
      title: '说明',
      dataIndex: 'message',
      ellipsis: true,
      render: (value: string, row) => {
        if (row.queue_type === 'mapped' && row.mapped_at) {
          const mappedAt = row.mapped_at.slice(0, 19).replace('T', ' ')
          return `${QUEUE_TYPE_HINT.mapped}（${mappedAt}）`
        }
        if (value && row.queue_type === 'non_standardized') {
          return value
        }
        return QUEUE_TYPE_HINT[row.queue_type] || value || '-'
      },
    },
    {
      title: '操作',
      key: 'actions',
      width: 200,
      render: (_, row, index) => (
        <Space size={4} wrap>
          {row.queue_type === 'non_standardized' && canEditDimensionPendingRow(row) && (
            <Button
              type="link"
              size="small"
              loading={confirmingKey === rowActionKey(row, index)}
              onClick={() => void handleQuickConfirm(row, index)}
            >
              确认无误
            </Button>
          )}
          {row.queue_type === 'non_standardized' &&
            ['customer', 'supplier', 'counterparty_object', 'bank_account'].includes(row.category_code || '') && (
              <Link to={`/ledger/dimensions?tab=master-values&category=${row.category_code}&jobId=${jobId}`}>
                主数据
              </Link>
            )}
          {row.queue_type === 'missing_in_master' && row.category_code && (
            <Link to={`/ledger/dimensions?tab=master-values&category=${row.category_code}&jobId=${jobId}`}>
              维护主数据
            </Link>
          )}
          {row.queue_type === 'unknown_category' && (
            <Link to={`/ledger/dimensions?tab=categories&jobId=${jobId}`}>维度分类</Link>
          )}
          <Link to={`/ledger/vouchers/step/4?jobId=${jobId}&reviewPhase=dimensions&inputMode=day_book_import`}>Step4 复核</Link>
          {row.finding_id && (
            <Link to={`/ledger/control-defects?jobId=${jobId}&status=pending`}>内控待办</Link>
          )}
        </Space>
      ),
    },
  ]

  if (!data) {
    return (
      <Card loading={loading}>
        <Alert type="info" showIcon message="正在加载待处理队列…" />
      </Card>
    )
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={16}>
      <Row gutter={16}>
        <Col span={4}>
          <Card size="small">
            <Statistic title="合计待办" value={data.summary.total} />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic title="还是简称" value={data.summary.non_standardized} valueStyle={{ color: '#fa8c16' }} />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic title="主数据缺" value={data.summary.missing_in_master} valueStyle={{ color: '#cf1322' }} />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic title="待识别" value={data.summary.requires_llm} valueStyle={{ color: '#722ed1' }} />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic title="分类未建" value={data.summary.unknown_category} />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={6} lg={4}>
          <Card size="small">
            <Statistic title="内控提醒" value={data.summary.internal_control} />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={6} lg={4}>
          <Card size="small">
            <Statistic title="映射留痕" value={data.summary.mapped ?? 0} valueStyle={{ color: '#08979c' }} />
          </Card>
        </Col>
      </Row>

      {data.summary.total === 0 && (data.summary.mapped ?? 0) === 0 ? (
        <Alert type="success" showIcon message="都对齐了，没有待办" description="可以回到 Step4 继续审凭证或确认入账。" />
      ) : data.summary.total === 0 && (data.summary.mapped ?? 0) > 0 ? (
        <Alert
          type="info"
          showIcon
          message="待办已处理完，仍有映射留痕可查阅"
          description={buildPendingAlertDescription(data.summary)}
        />
      ) : (
        <Alert
          type="warning"
          showIcon
          message={buildPendingAlertTitle(data.summary)}
          description={
            <>
              {buildPendingAlertDescription(data.summary)}
              {data.summary.non_standardized > 0 && (
                <div style={{ marginTop: 8 }}>
                  <strong>「待补全称」怎么处理：</strong>
                  在表格「映射值 / 规范全称」列点 <strong>确认</strong>，或在「操作」列点{' '}
                  <strong>确认无误</strong>（名称已正确时不必改名）。需改名则先改映射值再点确认；可勾选「同步到主数据」。
                  处理完点右上角「刷新」；也可继续 Step4，待办为建议项不挡入账。
                </div>
              )}
            </>
          }
        />
      )}

      <Card
        size="small"
        title="待处理明细"
        extra={
          <Space>
            {(data?.summary.requires_llm || 0) > 0 && (
              <Button
                type="primary"
                icon={<ThunderboltOutlined />}
                loading={llmResolving}
                onClick={handleBatchLlmResolve}
              >
                批量 LLM 识别 ({data?.summary.requires_llm})
              </Button>
            )}
            <Select
              value={typeFilter}
              onChange={setTypeFilter}
              style={{ width: 160 }}
              options={[
                { value: 'all', label: '全部类型' },
                ...Object.entries(QUEUE_TYPE_LABEL).map(([value, label]) => ({ value, label })),
              ]}
            />
            <Button icon={<ReloadOutlined />} onClick={() => void loadQueue()} loading={loading}>
              刷新
            </Button>
          </Space>
        }
      >
        <Table
          size="small"
          rowKey={(row, index) =>
            `${row.queue_type}-${row.staging_id || ''}-${row.finding_id || ''}-${row.tag_value || ''}-${index}`
          }
          loading={loading}
          dataSource={filteredItems}
          columns={columns}
          pagination={{ pageSize: 20, showSizeChanger: true }}
        />
        <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
          「待补全称」：在「映射值」列编辑后点 <strong>确认</strong>，或「操作」列点 <strong>确认无误</strong>。
          「映射留痕」记录导入原名与人工映射值，不影响入账门禁。
          「批量 LLM 识别」在确认入账前写入 staging 维度。
        </Text>
      </Card>
    </Space>
  )
}
