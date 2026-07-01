import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  Button,
  Card,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import { ReloadOutlined, PullRequestOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import {
  api,
  type AuditReviewAction,
  type AuditReviewRequest,
} from '../../api/client'

const { Title, Paragraph } = Typography
const { TextArea } = Input

const STATUS_COLOR: Record<string, string> = {
  draft: 'default',
  review: 'processing',
  changes_requested: 'warning',
  approved: 'success',
  merged: 'success',
  closed: 'default',
}

const STATUS_LABEL: Record<string, string> = {
  draft: '草稿',
  review: '复核中',
  changes_requested: '需修改',
  approved: '已通过',
  merged: '已合并',
  closed: '已关闭',
}

const STATUS_OPTIONS = [
  { value: 'draft', label: '草稿' },
  { value: 'review', label: '复核中' },
  { value: 'changes_requested', label: '需修改' },
  { value: 'approved', label: '已通过' },
  { value: 'merged', label: '已合并' },
  { value: 'closed', label: '已关闭' },
]

const ACTION_LABEL: Record<string, string> = {
  submit: '提交复核',
  approve: '通过',
  request_changes: '要求修改',
  comment: '评论',
  merge: '合并归档',
}

const ACTION_COLOR: Record<string, string> = {
  submit: 'blue',
  approve: 'success',
  request_changes: 'warning',
  comment: 'default',
  merge: 'purple',
}

const REVIEW_ACTION_OPTIONS = [
  { value: 'approve', label: '通过' },
  { value: 'request_changes', label: '要求修改' },
  { value: 'comment', label: '评论' },
]

export function AuditReviewPage() {
  const [searchParams] = useSearchParams()
  const projectIdParam = searchParams.get('projectId')
  const projectId = projectIdParam ? Number(projectIdParam) : null
  const [reviewRequests, setReviewRequests] = useState<AuditReviewRequest[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(15)
  const [loading, setLoading] = useState(false)
  const [statusFilter, setStatusFilter] = useState<string | undefined>()
  const [actionsByReview, setActionsByReview] = useState<Record<number, AuditReviewAction[]>>({})
  const [actionLoadingId, setActionLoadingId] = useState<number | null>(null)
  const [submittingId, setSubmittingId] = useState<number | null>(null)
  const [mergingId, setMergingId] = useState<number | null>(null)
  const [reviewModalVisible, setReviewModalVisible] = useState(false)
  const [reviewForm] = Form.useForm()
  const [currentReviewTarget, setCurrentReviewTarget] = useState<AuditReviewRequest | null>(null)
  const [reviewSubmitting, setReviewSubmitting] = useState(false)

  const loadReviewRequests = () => {
    setLoading(true)
    const filters: Parameters<typeof api.listAuditReviewRequests>[0] = {
      page,
      page_size: pageSize,
    }
    if (projectId != null) filters.project_id = projectId
    if (statusFilter) filters.status = statusFilter
    api
      .listAuditReviewRequests(filters)
      .then((response) => {
        setReviewRequests(response.items)
        setTotal(response.total)
      })
      .catch((error: Error) => message.error(error.message || '加载复核请求失败'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    setPage(1)
  }, [statusFilter, projectId])

  useEffect(() => {
    loadReviewRequests()
  }, [projectId, page, pageSize, statusFilter])

  const invalidateActions = (reviewId: number) => {
    setActionsByReview((prev) => {
      const next = { ...prev }
      delete next[reviewId]
      return next
    })
  }

  const loadActionsForReview = async (reviewId: number) => {
    if (actionsByReview[reviewId]) return
    setActionLoadingId(reviewId)
    try {
      const actions = await api.getAuditReviewActions(reviewId)
      setActionsByReview((prev) => ({ ...prev, [reviewId]: actions }))
    } catch (error) {
      const msg = error instanceof Error ? error.message : '加载复核动作记录失败'
      message.error(msg)
    } finally {
      setActionLoadingId(null)
    }
  }

  const handleSubmit = async (reviewId: number) => {
    setSubmittingId(reviewId)
    try {
      await api.submitAuditReview(reviewId)
      message.success('已提交复核')
      loadReviewRequests()
      invalidateActions(reviewId)
    } catch (error) {
      const msg = error instanceof Error ? error.message : '提交复核失败'
      message.error(msg)
    } finally {
      setSubmittingId(null)
    }
  }

  const handleMerge = async (reviewId: number) => {
    setMergingId(reviewId)
    try {
      await api.mergeAuditReview(reviewId)
      message.success('已合并归档')
      loadReviewRequests()
      invalidateActions(reviewId)
    } catch (error) {
      const msg = error instanceof Error ? error.message : '合并失败'
      message.error(msg)
    } finally {
      setMergingId(null)
    }
  }

  const openReviewModal = (review: AuditReviewRequest) => {
    setCurrentReviewTarget(review)
    reviewForm.resetFields()
    setReviewModalVisible(true)
  }

  const handlePerformReview = async () => {
    if (!currentReviewTarget) return
    try {
      const values = await reviewForm.validateFields()
      setReviewSubmitting(true)
      await api.performAuditReview(currentReviewTarget.id, {
        action: values.action,
        comment: values.comment || undefined,
      })
      message.success('复核意见已提交')
      setReviewModalVisible(false)
      loadReviewRequests()
      invalidateActions(currentReviewTarget.id)
    } catch (error) {
      if (error && typeof error === 'object' && 'errorFields' in error) return
      const msg = error instanceof Error ? error.message : '执行复核失败'
      message.error(msg)
    } finally {
      setReviewSubmitting(false)
    }
  }

  const columns = [
    { title: 'PR 编号', dataIndex: 'pr_no', key: 'pr_no', width: 130 },
    { title: '标题', dataIndex: 'title', key: 'title', ellipsis: true },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 110,
      render: (value: string) => (
        <Tag color={STATUS_COLOR[value] || 'default'}>{STATUS_LABEL[value] || value}</Tag>
      ),
    },
    {
      title: '当前复核级别',
      dataIndex: 'current_review_level',
      key: 'current_review_level',
      width: 120,
      render: (value: number) => `第 ${value} 级`,
    },
    {
      title: '创建人',
      dataIndex: 'created_by',
      key: 'created_by',
      width: 100,
      render: (value: number) => `用户 ${value}`,
    },
    {
      title: '提交时间',
      dataIndex: 'submitted_at',
      key: 'submitted_at',
      width: 170,
      render: (value: string | null) => (value ? dayjs(value).format('YYYY-MM-DD HH:mm') : '-'),
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      render: (_: unknown, row: AuditReviewRequest) => (
        <Space size="small" wrap>
          {row.status === 'draft' && (
            <Button
              size="small"
              type="primary"
              onClick={() => handleSubmit(row.id)}
              loading={submittingId === row.id}
            >
              提交复核
            </Button>
          )}
          {row.status === 'review' && (
            <Button size="small" onClick={() => openReviewModal(row)}>
              执行复核
            </Button>
          )}
          {row.status === 'approved' && (
            <Button
              size="small"
              type="primary"
              onClick={() => handleMerge(row.id)}
              loading={mergingId === row.id}
            >
              合并
            </Button>
          )}
        </Space>
      ),
    },
  ]

  const expandedRowRender = (row: AuditReviewRequest) => {
    const actions = actionsByReview[row.id] || []
    return (
      <Card size="small" title="复核动作记录" loading={actionLoadingId === row.id}>
        <Table
          rowKey="id"
          size="small"
          dataSource={actions}
          pagination={false}
          locale={{ emptyText: '暂无动作记录' }}
          columns={[
            {
              title: '动作',
              dataIndex: 'action',
              key: 'action',
              width: 120,
              render: (v: string) => (
                <Tag color={ACTION_COLOR[v] || 'default'}>{ACTION_LABEL[v] || v}</Tag>
              ),
            },
            {
              title: '复核级别',
              dataIndex: 'review_level',
              key: 'review_level',
              width: 100,
              render: (v: number) => `第 ${v} 级`,
            },
            {
              title: '复核人',
              dataIndex: 'reviewer_id',
              key: 'reviewer_id',
              width: 100,
              render: (v: number) => `用户 ${v}`,
            },
            {
              title: '意见',
              dataIndex: 'comment',
              key: 'comment',
              render: (v: string | null) => v || '-',
            },
            {
              title: '时间',
              dataIndex: 'created_at',
              key: 'created_at',
              width: 170,
              render: (v: string) => (v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-'),
            },
          ]}
        />
      </Card>
    )
  }

  const handleTableChange = (pagination: { current?: number; pageSize?: number }) => {
    setPage(pagination.current || 1)
    setPageSize(pagination.pageSize || 15)
  }

  return (
    <div>
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <Title level={4} style={{ margin: 0 }}>
              <PullRequestOutlined /> 审计复核与合并
            </Title>
            <Paragraph type="secondary" style={{ marginBottom: 0 }}>
              管理复核请求，支持提交复核、执行复核、合并归档与动作记录查看。
              {projectId ? ` 当前项目：#${projectId}` : ' 可通过 ?projectId= 指定项目过滤'}
            </Paragraph>
          </div>
          <Button icon={<ReloadOutlined />} onClick={loadReviewRequests} loading={loading}>
            刷新
          </Button>
        </div>

        <Card size="small">
          <Space wrap>
            <span>状态筛选：</span>
            <Select
              style={{ width: 160 }}
              value={statusFilter}
              onChange={setStatusFilter}
              options={STATUS_OPTIONS}
              placeholder="全部状态"
              allowClear
            />
          </Space>
        </Card>

        <Card title="复核请求列表">
          <Table
            rowKey="id"
            loading={loading}
            columns={columns}
            dataSource={reviewRequests}
            pagination={{
              current: page,
              pageSize,
              total,
              showSizeChanger: true,
              showTotal: (t) => `共 ${t} 条`,
            }}
            onChange={handleTableChange}
            expandable={{
              expandedRowRender,
              onExpand: (expanded, row) => {
                if (expanded) loadActionsForReview(row.id)
              },
            }}
            locale={{ emptyText: '暂无复核请求' }}
          />
        </Card>
      </Space>

      <Modal
        title="执行复核"
        open={reviewModalVisible}
        onOk={handlePerformReview}
        confirmLoading={reviewSubmitting}
        onCancel={() => {
          setReviewModalVisible(false)
          reviewForm.resetFields()
        }}
        okText="提交"
        cancelText="取消"
        destroyOnClose
      >
        {currentReviewTarget && (
          <Paragraph type="secondary" style={{ marginBottom: 12 }}>
            PR：{currentReviewTarget.pr_no} - {currentReviewTarget.title}
          </Paragraph>
        )}
        <Form form={reviewForm} layout="vertical">
          <Form.Item
            name="action"
            label="复核动作"
            rules={[{ required: true, message: '请选择复核动作' }]}
          >
            <Select options={REVIEW_ACTION_OPTIONS} placeholder="请选择复核动作" />
          </Form.Item>
          <Form.Item name="comment" label="复核意见">
            <TextArea rows={4} placeholder="请输入复核意见（可选）" maxLength={500} showCount />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
