import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  Button,
  Card,
  Descriptions,
  Form,
  Input,
  List,
  Modal,
  Space,
  Tag,
  Tabs,
  Typography,
  message,
} from 'antd'
import {
  CheckCircleOutlined,
  DeleteOutlined,
  SyncOutlined,
  SendOutlined,
} from '@ant-design/icons'
import {
  api,
  type AuditReviewRequest,
  type AuditReviewAction,
  type AuditComment,
} from '../../api/client'
import { useAuthStore } from '../../stores/authStore'

const { Title, Paragraph, Text } = Typography
const { TextArea } = Input

const STATUS_COLOR: Record<string, string> = {
  draft: 'default',
  review: 'processing',
  changes_requested: 'warning',
  approved: 'success',
  merged: 'purple',
  closed: 'default',
}

const STATUS_LABEL: Record<string, string> = {
  draft: '草稿',
  review: '复核中',
  changes_requested: '需修改',
  approved: '已通过',
  merged: '已归档',
  closed: '已关闭',
}

const ACTION_LABEL: Record<string, string> = {
  submit: '提交复核',
  approve: '通过',
  request_changes: '退回修改',
  merge: '合并归档',
}

interface ReviewDetailPageProps {
  reviewId?: number
  onBack?: () => void
}

export function ReviewDetailPage({ reviewId, onBack }: ReviewDetailPageProps = {}) {
  const params = useParams<{ reviewId: string }>()
  const effectiveReviewId = reviewId || Number(params.reviewId)
  const { user } = useAuthStore()
  const [review, setReview] = useState<AuditReviewRequest | null>(null)
  const [actions, setActions] = useState<AuditReviewAction[]>([])
  const [comments, setComments] = useState<AuditComment[]>([])
  const [loading, setLoading] = useState(false)
  const [commentText, setCommentText] = useState('')
  const [commentLoading, setCommentLoading] = useState(false)
  const [rejectModalVisible, setRejectModalVisible] = useState(false)
  const [rejectForm] = Form.useForm()
  const [actionLoading, setActionLoading] = useState(false)

  const loadDetail = () => {
    if (!effectiveReviewId) return
    setLoading(true)
    Promise.all([
      api.getAuditReviewRequest(effectiveReviewId),
      api.getAuditReviewActions(effectiveReviewId),
      api.listAuditComments('review_request', effectiveReviewId),
    ])
      .then(([detail, actionList, commentList]) => {
        setReview(detail)
        setActions(actionList)
        setComments(commentList)
      })
      .catch((error: Error) => message.error(error.message || '加载复核详情失败'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadDetail()
  }, [effectiveReviewId])

  const isReviewer = () => {
    if (!review || !user) return false
    const level = review.current_review_level
    if (level === 1) return review.reviewer_level_1_id === user.id
    if (level === 2) return review.reviewer_level_2_id === user.id
    if (level === 3) return review.reviewer_level_3_id === user.id
    return false
  }

  const isCreator = () => {
    if (!review || !user) return false
    return review.created_by === user.id
  }

  const handleSubmit = async () => {
    if (!review) return
    setActionLoading(true)
    try {
      await api.submitAuditReview(review.id)
      message.success('已提交复核')
      loadDetail()
    } catch (error: any) {
      message.error(error.message || '提交失败')
    } finally {
      setActionLoading(false)
    }
  }

  const handleApprove = async () => {
    if (!review) return
    setActionLoading(true)
    try {
      await api.performAuditReview(review.id, { action: 'approve' })
      message.success('复核已通过')
      loadDetail()
    } catch (error: any) {
      message.error(error.message || '操作失败')
    } finally {
      setActionLoading(false)
    }
  }

  const handleReject = async () => {
    if (!review) return
    try {
      const values = await rejectForm.validateFields()
      setActionLoading(true)
      await api.performAuditReview(review.id, {
        action: 'request_changes',
        comment: values.comment,
      })
      message.success('已退回修改')
      setRejectModalVisible(false)
      rejectForm.resetFields()
      loadDetail()
    } catch (error: any) {
      if (error.errorFields) return
      message.error(error.message || '操作失败')
    } finally {
      setActionLoading(false)
    }
  }

  const handleMerge = async () => {
    if (!review) return
    setActionLoading(true)
    try {
      await api.mergeAuditReview(review.id)
      message.success('已合并归档')
      loadDetail()
    } catch (error: any) {
      message.error(error.message || '操作失败')
    } finally {
      setActionLoading(false)
    }
  }

  const handleAddComment = async () => {
    if (!commentText.trim() || !review) return
    setCommentLoading(true)
    try {
      await api.createAuditComment({
      target_type: 'review_request',
      target_id: review.id,
      content: commentText.trim(),
    })
      message.success('评论已发布')
      setCommentText('')
      loadDetail()
    } catch (error: any) {
      message.error(error.message || '评论失败')
    } finally {
      setCommentLoading(false)
    }
  }

  const renderActions = () => (
    <Space wrap>
      {review?.status === 'draft' && isCreator() && (
        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={handleSubmit}
          loading={actionLoading}
        >
          提交复核
        </Button>
      )}
      {review?.status === 'review' && isReviewer() && (
        <>
          <Button
            type="primary"
            icon={<CheckCircleOutlined />}
            onClick={handleApprove}
            loading={actionLoading}
          >
            通过
          </Button>
          <Button
            danger
            icon={<DeleteOutlined />}
            onClick={() => setRejectModalVisible(true)}
            loading={actionLoading}
          >
            退回修改
          </Button>
        </>
      )}
      {review?.status === 'approved' && (
        <Button
          type="primary"
          icon={<SyncOutlined />}
          onClick={handleMerge}
          loading={actionLoading}
        >
          合并归档
        </Button>
      )}
    </Space>
  )

  const tabItems = [
    {
      key: 'actions',
      label: '复核记录',
      children: (
        <List
          dataSource={actions}
          locale={{ emptyText: '暂无复核记录' }}
          renderItem={(item) => (
            <List.Item key={item.id}>
              <List.Item.Meta
                title={
                  <Space>
                    <Text strong>{ACTION_LABEL[item.action] || item.action}</Text>
                    <Tag color={item.action === 'approve' ? 'success' : item.action === 'request_changes' ? 'warning' : 'default'}>
                      第 {item.review_level} 级
                    </Tag>
                  </Space>
                }
                description={
                  <div>
                    <div>复核人 ID: {item.reviewer_id}</div>
                    {item.comment && <div>意见: {item.comment}</div>}
                    <Text type="secondary">{item.created_at}</Text>
                  </div>
                }
              />
            </List.Item>
          )}
        />
      ),
    },
    {
      key: 'comments',
      label: `评论 (${comments.length})`,
      children: (
        <div>
          <List
            dataSource={comments}
            locale={{ emptyText: '暂无评论' }}
            renderItem={(item) => (
              <List.Item key={item.id}>
                <Card size="small" style={{ marginBottom: 8 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                    <Typography.Text strong>{`用户 ${item.created_by}`}</Typography.Text>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      {new Date(item.created_at).toLocaleString('zh-CN')}
                    </Typography.Text>
                  </div>
                  <Typography.Text>{item.content}</Typography.Text>
                </Card>
              </List.Item>
            )}
          />
          <div style={{ marginTop: 16 }}>
            <TextArea
              rows={3}
              placeholder="发表评论..."
              value={commentText}
              onChange={(e) => setCommentText(e.target.value)}
              maxLength={500}
              showCount
            />
            <div style={{ marginTop: 8, textAlign: 'right' }}>
              <Button
                type="primary"
                onClick={handleAddComment}
                loading={commentLoading}
                disabled={!commentText.trim()}
              >
                发表评论
              </Button>
            </div>
          </div>
        </div>
      ),
    },
  ]

  return (
    <div>
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <Title level={4} style={{ margin: 0 }}>
              复核请求详情
            </Title>
            <Paragraph type="secondary" style={{ marginBottom: 0 }}>
              查看复核请求的详细信息、复核记录和评论
            </Paragraph>
          </div>
          {onBack && (
            <Button onClick={onBack}>返回</Button>
          )}
        </div>

        <Card loading={loading}>
          {review && (
            <Space direction="vertical" size="large" style={{ width: '100%' }}>
              <Descriptions bordered column={2} size="small">
                <Descriptions.Item label="编号">{review.pr_no}</Descriptions.Item>
                <Descriptions.Item label="状态">
                  <Tag color={STATUS_COLOR[review.status] || 'default'}>
                    {STATUS_LABEL[review.status] || review.status}
                  </Tag>
                </Descriptions.Item>
                <Descriptions.Item label="标题" span={2}>
                  {review.title}
                </Descriptions.Item>
                <Descriptions.Item label="描述" span={2}>
                  {review.description || '-'}
                </Descriptions.Item>
                <Descriptions.Item label="当前复核级别">
                  第 {review.current_review_level} 级
                </Descriptions.Item>
                <Descriptions.Item label="目标分支">
                  {review.target_branch || '-'}
                </Descriptions.Item>
                <Descriptions.Item label="创建人">
                  用户 {review.created_by}
                </Descriptions.Item>
                <Descriptions.Item label="任务 ID">
                  {review.task_id || '-'}
                </Descriptions.Item>
                <Descriptions.Item label="分支 ID">
                  {review.branch_id || '-'}
                </Descriptions.Item>
                <Descriptions.Item label="提交底稿版本">
                  {review.submitted_version_id || '-'}
                </Descriptions.Item>
                <Descriptions.Item label="通过底稿版本">
                  {review.approved_version_id || '-'}
                </Descriptions.Item>
                <Descriptions.Item label="归档底稿版本">
                  {review.merged_version_id || '-'}
                </Descriptions.Item>
                <Descriptions.Item label="一级复核人">
                  {review.reviewer_level_1_id ? `用户 ${review.reviewer_level_1_id}` : '-'}
                </Descriptions.Item>
                <Descriptions.Item label="二级复核人">
                  {review.reviewer_level_2_id ? `用户 ${review.reviewer_level_2_id}` : '-'}
                </Descriptions.Item>
                <Descriptions.Item label="三级复核人">
                  {review.reviewer_level_3_id ? `用户 ${review.reviewer_level_3_id}` : '-'}
                </Descriptions.Item>
                <Descriptions.Item label="创建时间">
                  {review.created_at}
                </Descriptions.Item>
                <Descriptions.Item label="提交时间">
                  {review.submitted_at || '-'}
                </Descriptions.Item>
                <Descriptions.Item label="通过时间">
                  {review.approved_at || '-'}
                </Descriptions.Item>
                <Descriptions.Item label="归档时间">
                  {review.merged_at || '-'}
                </Descriptions.Item>
              </Descriptions>

              <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                {renderActions()}
              </div>

              <Tabs defaultActiveKey="actions" items={tabItems} />
            </Space>
          )}
        </Card>
      </Space>

      <Modal
        title="退回修改"
        open={rejectModalVisible}
        onOk={handleReject}
        onCancel={() => {
          setRejectModalVisible(false)
          rejectForm.resetFields()
        }}
        confirmLoading={actionLoading}
        okText="确认退回"
        cancelText="取消"
      >
        <Form form={rejectForm} layout="vertical">
          <Form.Item
            name="comment"
            label="退回原因"
            rules={[{ required: true, message: '请输入退回原因' }]}
          >
            <TextArea rows={4} placeholder="请输入退回原因..." maxLength={500} showCount />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
