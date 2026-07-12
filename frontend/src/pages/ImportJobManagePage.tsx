import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Col,
  Modal,
  Popconfirm,
  Row,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import {
  ClearOutlined,
  DeleteOutlined,
  ReloadOutlined,
  WarningOutlined,
} from '@ant-design/icons'
import { Link } from 'react-router-dom'

import { api, type ImportJobCleanupRow } from '../api/client'
import { useAuthStore } from '../stores/authStore'
import { readLedgerImportResume, clearLedgerImportResume, isResumableImportJob } from '../utils/importJobContext'

const { Paragraph, Title, Text } = Typography

const STATUS_COLOR: Record<string, string> = {
  created: 'default',
  queued: 'processing',
  processing: 'processing',
  draft: 'gold',
  preview: 'blue',
  failed: 'error',
  cancelled: 'default',
  completed: 'success',
}

function formatCreatedAt(value: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

export function ImportJobManagePage() {
  const { currentLedgerId } = useAuthStore()
  const [loading, setLoading] = useState(false)
  const [purging, setPurging] = useState(false)
  const [summary, setSummary] = useState<Awaited<
    ReturnType<typeof api.getImportJobCleanupSummary>
  > | null>(null)
  const [selectedRowKeys, setSelectedRowKeys] = useState<number[]>([])
  const [resumeKeepIds, setResumeKeepIds] = useState<number[]>([])

  const resumeJobId = useMemo(
    () => (currentLedgerId ? readLedgerImportResume(currentLedgerId)?.jobId : undefined),
    [currentLedgerId],
  )

  useEffect(() => {
    if (!resumeJobId || !currentLedgerId) {
      setResumeKeepIds([])
      return
    }
    let cancelled = false
    void api
      .getImportJob(resumeJobId)
      .then((job) => {
        if (cancelled) return
        if (isResumableImportJob(job)) {
          setResumeKeepIds([resumeJobId])
          return
        }
        clearLedgerImportResume(currentLedgerId)
        setResumeKeepIds([])
      })
      .catch(() => {
        if (!cancelled) {
          clearLedgerImportResume(currentLedgerId)
          setResumeKeepIds([])
        }
      })
    return () => {
      cancelled = true
    }
  }, [resumeJobId, currentLedgerId])

  const defaultKeepIds = resumeKeepIds

  const loadSummary = useCallback(async () => {
    if (!currentLedgerId) {
      setSummary(null)
      return
    }
    setLoading(true)
    try {
      const data = await api.getImportJobCleanupSummary(currentLedgerId)
      setSummary(data)
      setSelectedRowKeys((prev) => prev.filter((id) => data.jobs.some((job) => job.id === id)))
    } catch (err) {
      message.error(err instanceof Error ? err.message : '加载导入任务失败')
      setSummary(null)
    } finally {
      setLoading(false)
    }
  }, [currentLedgerId])

  useEffect(() => {
    void loadSummary()
  }, [loadSummary])

  const runCleanup = async (options: {
    job_ids?: number[]
    stuck_only?: boolean
    statuses?: string[]
  }) => {
    if (!currentLedgerId) return
    setPurging(true)
    try {
      const result = await api.cleanupImportJobs({
        ledger_id: currentLedgerId,
        keep_job_ids: defaultKeepIds,
        delete_files: true,
        ...options,
      })
      if (result.purged_count > 0) {
        message.success(`已清理 ${result.purged_count} 个导入任务`)
      } else {
        message.info('没有可清理的任务')
      }
      if (result.skipped_count > 0) {
        message.warning(`${result.skipped_count} 个任务已跳过（含保留中的任务）`)
      }
      setSelectedRowKeys([])
      await loadSummary()
    } catch (err) {
      message.error(err instanceof Error ? err.message : '清理失败')
    } finally {
      setPurging(false)
    }
  }

  const confirmBulk = (title: string, onOk: () => Promise<void>) => {
    Modal.confirm({
      title,
      content: (
        <Paragraph type="secondary" style={{ marginBottom: 0 }}>
          将删除 staging 暂存数据、上传文件及任务记录。
          {defaultKeepIds.length > 0 && (
            <> 任务 #{defaultKeepIds.join('、#')} 在保留列表中，不会被删除。</>
          )}
          已正式入账（completed）或已生成凭证的任务不会被清理。
        </Paragraph>
      ),
      okText: '确认清理',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk,
    })
  }

  const columns = [
    {
      title: '任务 ID',
      dataIndex: 'id',
      width: 90,
      render: (id: number) => <Text strong>#{id}</Text>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 110,
      render: (status: string) => <Tag color={STATUS_COLOR[status] || 'default'}>{status}</Tag>,
    },
    {
      title: '来源',
      dataIndex: 'source_type',
      width: 140,
      ellipsis: true,
    },
    {
      title: '文件数',
      dataIndex: 'file_count',
      width: 80,
    },
    {
      title: '分录数',
      dataIndex: 'entry_count',
      width: 90,
      render: (value: number) => value.toLocaleString(),
    },
    {
      title: 'Staging 行',
      dataIndex: 'staging_rows',
      width: 100,
      render: (value: number) => value.toLocaleString(),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      width: 170,
      render: (value: string | null) => formatCreatedAt(value),
    },
    {
      title: '说明',
      dataIndex: 'stuck_reason',
      ellipsis: true,
      render: (reason: string | null, row: ImportJobCleanupRow) => {
        if (row.stuck) {
          return (
            <Space size={4}>
              <Tag color="warning" icon={<WarningOutlined />}>
                卡死/废弃
              </Tag>
              <Text type="secondary">{reason || '建议清理'}</Text>
            </Space>
          )
        }
        if (!row.cleanable) {
          return <Text type="secondary">已入账或受保护</Text>
        }
        return <Text type="secondary">{reason || '可清理'}</Text>
      },
    },
    {
      title: '操作',
      key: 'actions',
      width: 100,
      fixed: 'right' as const,
      render: (_: unknown, row: ImportJobCleanupRow) =>
        row.cleanable ? (
          <Popconfirm
            title={`删除任务 #${row.id}？`}
            description="将释放 staging 与上传文件空间"
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
            onConfirm={() => runCleanup({ job_ids: [row.id] })}
          >
            <Button type="link" danger size="small" icon={<DeleteOutlined />} loading={purging}>
              删除
            </Button>
          </Popconfirm>
        ) : (
          <Text type="secondary">—</Text>
        ),
    },
  ]

  if (!currentLedgerId) {
    return (
      <div style={{ padding: 24 }}>
        <Alert
          type="warning"
          showIcon
          title="请先在顶部选择账套"
          description="导入任务与账套绑定，选择账套后可查看并清理卡死任务。"
        />
      </div>
    )
  }

  return (
    <div style={{ padding: 24, maxWidth: 1680, margin: '0 auto' }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <div>
          <Title level={3} style={{ marginBottom: 4 }}>
            导入任务清理
          </Title>
          <Paragraph type="secondary" style={{ marginBottom: 0 }}>
            清理卡死、失败或未完成的导入任务，释放 staging 暂存与上传文件占用的空间。
            正在使用的草稿任务会自动保留。
            <Link to="/ledger/vouchers/step/2" style={{ marginLeft: 8 }}>
              返回序时簿导入
            </Link>
          </Paragraph>
        </div>

        {summary && resumeJobId && resumeKeepIds.length === 0 && (
          <Alert
            type="info"
            showIcon
            title={`浏览器中曾记录任务 #${resumeJobId} 的恢复进度`}
            description={
              <Space wrap>
                <span>
                  该任务已结束或不可恢复，不再自动保留。已完成入账的任务受保护，不会被误删。
                </span>
                <Button
                  size="small"
                  onClick={() => {
                    if (currentLedgerId) clearLedgerImportResume(currentLedgerId)
                    message.success('已清除浏览器中的恢复记录')
                  }}
                >
                  清除恢复记录
                </Button>
              </Space>
            }
          />
        )}

        {summary && summary.stuck_count > 0 && (
          <Alert
            type="warning"
            showIcon
            title={`检测到 ${summary.stuck_count} 个卡死/废弃任务`}
            description={`其中约 ${summary.total_staging_rows.toLocaleString()} 行 staging 数据可释放。processing/queued 超过 ${summary.stuck_active_hours} 小时视为卡死。`}
          />
        )}

        <Row gutter={16}>
          <Col xs={12} sm={6}>
            <Card size="small">
              <Statistic title="任务总数" value={summary?.total_jobs ?? 0} loading={loading} />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card size="small">
              <Statistic
                title="可清理"
                value={summary?.cleanable_count ?? 0}
                loading={loading}
                valueStyle={{ color: '#cf1322' }}
              />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card size="small">
              <Statistic
                title="卡死/废弃"
                value={summary?.stuck_count ?? 0}
                loading={loading}
                valueStyle={{ color: '#d48806' }}
              />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card size="small">
              <Statistic
                title="Staging 行数"
                value={summary?.total_staging_rows ?? 0}
                loading={loading}
              />
            </Card>
          </Col>
        </Row>

        <Card
          title="任务列表"
          extra={
            <Space wrap>
              <Button icon={<ReloadOutlined />} onClick={() => void loadSummary()} loading={loading}>
                刷新
              </Button>
              <Button
                icon={<ClearOutlined />}
                loading={purging}
                disabled={!summary?.stuck_count}
                onClick={() =>
                  confirmBulk('清理全部卡死/废弃任务？', () => runCleanup({ stuck_only: true }))
                }
              >
                清理卡死任务
              </Button>
              <Button
                danger
                icon={<DeleteOutlined />}
                loading={purging}
                disabled={selectedRowKeys.length === 0}
                onClick={() =>
                  confirmBulk(`清理选中的 ${selectedRowKeys.length} 个任务？`, () =>
                    runCleanup({ job_ids: selectedRowKeys }),
                  )
                }
              >
                清理选中
              </Button>
              <Button
                danger
                type="primary"
                loading={purging}
                disabled={!summary?.cleanable_count}
                onClick={() =>
                  confirmBulk('清理本账套全部可清理任务？', () =>
                    runCleanup({
                      statuses: summary?.cleanable_statuses,
                    }),
                  )
                }
              >
                清理全部可清理
              </Button>
            </Space>
          }
        >
          <Table<ImportJobCleanupRow>
            rowKey="id"
            loading={loading}
            dataSource={summary?.jobs ?? []}
            columns={columns}
            scroll={{ x: 1100 }}
            pagination={{ pageSize: 20, showSizeChanger: true }}
            rowSelection={{
              selectedRowKeys,
              onChange: (keys) => setSelectedRowKeys(keys as number[]),
              getCheckboxProps: (row) => ({
                disabled: !row.cleanable || defaultKeepIds.includes(row.id),
              }),
            }}
            rowClassName={(row) => (row.stuck ? 'import-job-row-stuck' : '')}
          />
        </Card>
      </Space>
      <style>{`
        .import-job-row-stuck td {
          background: #fffbe6 !important;
        }
      `}</style>
    </div>
  )
}
