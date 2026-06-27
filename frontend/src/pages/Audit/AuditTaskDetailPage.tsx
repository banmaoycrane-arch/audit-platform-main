import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  Avatar,
  Button,
  Card,
  Descriptions,
  Form,
  Input,
  List,
  Modal,
  Select,
  Space,
  Tabs,
  Tag,
  Typography,
  message,
} from 'antd'
import {
  CheckCircleOutlined,
  DeleteOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  UserOutlined,
} from '@ant-design/icons'
import {
  api,
  type AuditComment,
  type AuditReviewRequest,
  type AuditTask,
  type AuditWorkBranch,
  type TeamMember,
} from '../../api/client'
import { useAuthStore } from '../../stores/authStore'

const { Title, Paragraph, Text } = Typography
const { TextArea } = Input

const TASK_STATUS_COLOR: Record<string, string> = {
  open: 'default',
  todo: 'processing',
  in_progress: 'blue',
  review: 'gold',
  closed: 'success',
  rejected: 'error',
}

const TASK_STATUS_LABEL: Record<string, string> = {
  open: '开放',
  todo: '待办',
  in_progress: '进行中',
  review: '复核中',
  closed: '已关闭',
  rejected: '已拒绝',
}

const TASK_TYPE_LABEL: Record<string, string> = {
  risk_assessment: '风险评估',
  control_test: '控制测试',
  substantive: '实质性程序',
  review: '复核',
  other: '其他',
}

const TASK_TYPE_COLOR: Record<string, string> = {
  risk_assessment: 'red',
  control_test: 'blue',
  substantive: 'green',
  review: 'purple',
  other: 'default',
}

const TASK_PRIORITY_COLOR: Record<string, string> = {
  high: 'red',
  normal: 'orange',
  low: 'green',
}

const TASK_PRIORITY_LABEL: Record<string, string> = {
  high: '高',
  normal: '中',
  low: '低',
}

const BRANCH_STATUS_COLOR: Record<string, string> = {
  active: 'processing',
  review_pending: 'gold',
  merged: 'success',
  archived: 'default',
  abandoned: 'error',
}

const BRANCH_STATUS_LABEL: Record<string, string> = {
  active: '进行中',
  review_pending: '待复核',
  merged: '已合并',
  archived: '已归档',
  abandoned: '已废弃',
}

const REVIEW_STATUS_COLOR: Record<string, string> = {
  draft: 'default',
  review: 'processing',
  changes_requested: 'warning',
  approved: 'success',
  merged: 'success',
  closed: 'default',
}

const REVIEW_STATUS_LABEL: Record<string, string> = {
  draft: '草稿',
  review: '复核中',
  changes_requested: '需修改',
  approved: '已通过',
  merged: '已合并',
  closed: '已关闭',
}

interface AuditTaskDetailPageProps {
  taskId?: number
}

export function AuditTaskDetailPage({ taskId }: AuditTaskDetailPageProps = {}) {
  const params = useParams<{ taskId: string }>()
  const routeTaskId = Number(params.taskId)
  const effectiveTaskId = taskId || (Number.isFinite(routeTaskId) ? routeTaskId : 0)
  const { user } = useAuthStore()
  const [task, setTask] = useState<AuditTask | null>(null)
  const [loading, setLoading] = useState(false)
  const [branches, setBranches] = useState<AuditWorkBranch[]>([])
  const [reviewRequests, setReviewRequests] = useState<AuditReviewRequest[]>([])
  const [comments, setComments] = useState<AuditComment[]>([])
  const [commentText, setCommentText] = useState('')
  const [submittingComment, setSubmittingComment] = useState(false)
  const [closeModalVisible, setCloseModalVisible] = useState(false)
  const [closeReason, setCloseReason] = useState('')
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([])
  const [assignModalVisible, setAssignModalVisible] = useState(false)
  const [selectedAssignee, setSelectedAssignee] = useState<number | null>(null)

  const currentTaskId = effectiveTaskId

  const loadTask = () => {
    if (!currentTaskId) return
    setLoading(true)
    api
      .getAuditTask(currentTaskId)
      .then(setTask)
      .catch((error: Error) => message.error(error.message || '加载任务详情失败'))
      .finally(() => setLoading(false))
  }

  const loadBranches = () => {
    if (!currentTaskId) return
    api
      .getBranchesByTask(currentTaskId)
      .then(setBranches)
      .catch((error: Error) => message.error(error.message || '加载工作分支失败'))
  }

  const loadReviewRequests = () => {
    if (!task?.project_id) return
    api
      .listAuditReviewRequests({ project_id: task.project_id })
      .then((res) => {
        const filtered = res.items.filter((item) => item.task_id === currentTaskId)
        setReviewRequests(filtered)
      })
      .catch((error: Error) => message.error(error.message || '加载复核请求失败'))
  }

  const loadComments = () => {
    if (!currentTaskId) return
    api
      .listAuditComments('task', currentTaskId)
      .then(setComments)
      .catch((error: Error) => message.error(error.message || '加载评论失败'))
  }

  const loadTeamMembers = () => {
    api
      .listTeams()
      .then((teams) => {
        if (teams.length > 0) {
          return api.getTeamMembers(teams[0].id)
        }
        return []
      })
      .then(setTeamMembers)
      .catch(() => {})
  }

  useEffect(() => {
    loadTask()
    loadBranches()
    loadComments()
    loadTeamMembers()
  }, [currentTaskId])

  useEffect(() => {
    if (task?.project_id) {
      loadReviewRequests()
    }
  }, [task?.project_id])

  const handleAssignToMe = async () => {
    if (!currentTaskId || !user) return
    try {
      await api.assignAuditTask(currentTaskId, user.id)
      message.success('任务已分配给您')
      loadTask()
    } catch (error: any) {
      message.error(error.message || '分配失败')
    }
  }

  const handleAssign = async () => {
    if (!currentTaskId || !selectedAssignee) return
    try {
      await api.assignAuditTask(currentTaskId, selectedAssignee)
      message.success('任务已分配')
      setAssignModalVisible(false)
      setSelectedAssignee(null)
      loadTask()
    } catch (error: any) {
      message.error(error.message || '分配失败')
    }
  }

  const handleStartProgress = async () => {
    if (!currentTaskId) return
    try {
      await api.updateAuditTaskStatus(currentTaskId, 'in_progress')
      message.success('任务已开始处理')
      loadTask()
    } catch (error: any) {
      message.error(error.message || '操作失败')
    }
  }

  const handleSubmitReview = async () => {
    if (!currentTaskId) return
    try {
      await api.updateAuditTaskStatus(currentTaskId, 'review')
      message.success('任务已提交复核')
      loadTask()
    } catch (error: any) {
      message.error(error.message || '操作失败')
    }
  }

  const handleCloseTask = async () => {
    if (!currentTaskId) return
    try {
      await api.updateAuditTaskStatus(currentTaskId, 'closed', closeReason || null)
      message.success('任务已关闭')
      setCloseModalVisible(false)
      setCloseReason('')
      loadTask()
    } catch (error: any) {
      message.error(error.message || '关闭失败')
    }
  }

  const handleSubmitComment = async () => {
    if (!currentTaskId || !commentText.trim()) return
    setSubmittingComment(true)
    try {
      await api.createAuditComment({
        target_type: 'task',
        target_id: currentTaskId,
        content: commentText.trim(),
      })
      message.success('评论已发布')
      setCommentText('')
      loadComments()
    } catch (error: any) {
      message.error(error.message || '评论发布失败')
    } finally {
      setSubmittingComment(false)
    }
  }

  const getMemberName = (userId: number | null | undefined) => {
    if (!userId) return '-'
    const member = teamMembers.find((m) => m.id === userId)
    return member?.username || member?.email || member?.phone || `用户${userId}`
  }

  const renderTaskInfo = () => {
    if (!task) return null
    return (
      <Card
        title={
          <Space>
            <Title level={4} style={{ margin: 0 }}>
              {task.title}
            </Title>
            <Tag color={TASK_STATUS_COLOR[task.status] || 'default'}>
              {TASK_STATUS_LABEL[task.status] || task.status}
            </Tag>
          </Space>
        }
        extra={
          <Button icon={<ReloadOutlined />} onClick={loadTask} loading={loading}>
            刷新
          </Button>
        }
      >
        <Descriptions column={2} bordered size="small">
          <Descriptions.Item label="任务编号">{task.task_no}</Descriptions.Item>
          <Descriptions.Item label="优先级">
            <Tag color={TASK_PRIORITY_COLOR[task.priority] || 'default'}>
              {TASK_PRIORITY_LABEL[task.priority] || task.priority}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="类型">
            <Tag color={TASK_TYPE_COLOR[task.task_type] || 'default'}>
              {TASK_TYPE_LABEL[task.task_type] || task.task_type}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="状态">
            <Tag color={TASK_STATUS_COLOR[task.status] || 'default'}>
              {TASK_STATUS_LABEL[task.status] || task.status}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="描述" span={2}>
            {task.description || '-'}
          </Descriptions.Item>
          <Descriptions.Item label="创建人">{getMemberName(task.created_by)}</Descriptions.Item>
          <Descriptions.Item label="指派人">
            {task.assignee_id ? getMemberName(task.assignee_id) : '未分配'}
          </Descriptions.Item>
          <Descriptions.Item label="创建时间">
            {task.created_at ? new Date(task.created_at).toLocaleString('zh-CN') : '-'}
          </Descriptions.Item>
          <Descriptions.Item label="截止日期">
            {task.due_date ? new Date(task.due_date).toLocaleDateString('zh-CN') : '-'}
          </Descriptions.Item>
        </Descriptions>

        <Space style={{ marginTop: 16 }} wrap>
          {!task.assignee_id && (
            <Button
              type="primary"
              icon={<UserOutlined />}
              onClick={handleAssignToMe}
              disabled={!user}
            >
              分配给我
            </Button>
          )}
          {task.assignee_id && (
            <Button onClick={() => setAssignModalVisible(true)}>重新分配</Button>
          )}
          {task.status === 'todo' && task.assignee_id && (
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={handleStartProgress}
            >
              开始处理
            </Button>
          )}
          {task.status === 'in_progress' && (
            <Button type="primary" onClick={handleSubmitReview}>
              提交复核
            </Button>
          )}
          {task.status !== 'closed' && (
            <Button danger icon={<DeleteOutlined />} onClick={() => setCloseModalVisible(true)}>
              关闭任务
            </Button>
          )}
        </Space>
      </Card>
    )
  }

  const renderBranchesTab = () => (
    <List
      itemLayout="horizontal"
      dataSource={branches}
      locale={{ emptyText: '暂无工作分支' }}
      renderItem={(item) => (
        <List.Item
          actions={[
            <Tag key="status" color={BRANCH_STATUS_COLOR[item.status] || 'default'}>
              {BRANCH_STATUS_LABEL[item.status] || item.status}
            </Tag>,
          ]}
        >
          <List.Item.Meta
            title={item.branch_name}
            description={
              <Space direction="vertical" size={4}>
                <Text type="secondary">基准分支：{item.base_branch || 'main'}</Text>
                <Text type="secondary">
                  创建人：{getMemberName(item.created_by)}
                </Text>
                <Text type="secondary">
                  创建时间：{new Date(item.created_at).toLocaleString('zh-CN')}
                </Text>
              </Space>
            }
          />
        </List.Item>
      )}
    />
  )

  const renderReviewsTab = () => (
    <List
      itemLayout="horizontal"
      dataSource={reviewRequests}
      locale={{ emptyText: '暂无复核请求' }}
      renderItem={(item) => (
        <List.Item
          actions={[
            <Tag key="status" color={REVIEW_STATUS_COLOR[item.status] || 'default'}>
              {REVIEW_STATUS_LABEL[item.status] || item.status}
            </Tag>,
          ]}
        >
          <List.Item.Meta
            title={
              <Space>
                <Text strong>{item.pr_no}</Text>
                <Link to={`/audit/review-requests/${item.id}`}>{item.title}</Link>
              </Space>
            }
            description={
              <Space direction="vertical" size={4}>
                <Text type="secondary">目标分支：{item.target_branch}</Text>
                <Text type="secondary">
                  创建人：{getMemberName(item.created_by)}
                </Text>
                <Text type="secondary">
                  当前复核级别：第{item.current_review_level}级
                </Text>
                <Text type="secondary">
                  创建时间：{new Date(item.created_at).toLocaleString('zh-CN')}
                </Text>
                {item.description && (
                  <Paragraph type="secondary" style={{ marginBottom: 0 }}>
                    {item.description}
                  </Paragraph>
                )}
              </Space>
            }
          />
        </List.Item>
      )}
    />
  )

  const renderCommentsTab = () => (
    <div>
      <List
        className="comment-list"
        header={`${comments.length} 条评论`}
        itemLayout="horizontal"
        dataSource={comments}
        locale={{ emptyText: '暂无评论' }}
        renderItem={(item) => (
          <li key={item.id}>
            <Card size="small" style={{ marginBottom: 8 }}>
              <Space align="start" style={{ width: '100%' }}>
                <Avatar icon={<UserOutlined />} alt={getMemberName(item.created_by)} />
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                    <Typography.Text strong>{getMemberName(item.created_by)}</Typography.Text>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      {new Date(item.created_at).toLocaleString('zh-CN')}
                    </Typography.Text>
                  </div>
                  <Typography.Text>{item.content}</Typography.Text>
                </div>
              </Space>
            </Card>
          </li>
        )}
      />
      <Card size="small" style={{ marginTop: 16 }}>
        <Form.Item>
          <TextArea
            rows={3}
            value={commentText}
            onChange={(e) => setCommentText(e.target.value)}
            placeholder="发表评论..."
            maxLength={500}
            showCount
          />
        </Form.Item>
        <Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
          <Button
            type="primary"
            onClick={handleSubmitComment}
            loading={submittingComment}
            disabled={!commentText.trim()}
            icon={<CheckCircleOutlined />}
          >
            发表评论
          </Button>
        </Form.Item>
      </Card>
    </div>
  )

  const tabItems = [
    { key: 'branches', label: '工作分支', children: renderBranchesTab() },
    { key: 'reviews', label: '复核请求', children: renderReviewsTab() },
    { key: 'comments', label: '评论', children: renderCommentsTab() },
  ]

  if (!currentTaskId) {
    return (
      <Card>
        <Typography.Text type="danger">任务 ID 无效，请从任务列表重新进入。</Typography.Text>
      </Card>
    )
  }

  return (
    <div>
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        {renderTaskInfo()}

        <Card>
          <Tabs defaultActiveKey="branches" items={tabItems} />
        </Card>
      </Space>

      <Modal
        title="关闭任务"
        open={closeModalVisible}
        onOk={handleCloseTask}
        onCancel={() => {
          setCloseModalVisible(false)
          setCloseReason('')
        }}
        okText="确认关闭"
        cancelText="取消"
        okButtonProps={{ danger: true }}
      >
        <Paragraph type="secondary">确定要关闭此任务吗？关闭后将无法重新打开。</Paragraph>
        <Form.Item label="关闭原因" labelCol={{ span: 4 }} wrapperCol={{ span: 20 }}>
          <TextArea
            rows={3}
            value={closeReason}
            onChange={(e) => setCloseReason(e.target.value)}
            placeholder="请输入关闭原因（可选）"
            maxLength={200}
            showCount
          />
        </Form.Item>
      </Modal>

      <Modal
        title="分配任务"
        open={assignModalVisible}
        onOk={handleAssign}
        onCancel={() => {
          setAssignModalVisible(false)
          setSelectedAssignee(null)
        }}
        okText="确认分配"
        cancelText="取消"
      >
        <Form layout="vertical">
          <Form.Item label="选择指派人" required>
            <Select
              value={selectedAssignee || undefined}
              onChange={setSelectedAssignee}
              placeholder="请选择指派人"
              options={teamMembers.map((m) => ({
                value: m.id,
                label: m.username || m.email || m.phone || `用户${m.id}`,
              }))}
              showSearch
              optionFilterProp="label"
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
