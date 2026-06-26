import { useEffect, useState } from 'react'
import {
  Card,
  Col,
  Row,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
  Button,
  message,
} from 'antd'
import {
  ClockCircleOutlined,
  PlayCircleOutlined,
  SearchOutlined,
  CheckCircleOutlined,
  ReloadOutlined,
} from '@ant-design/icons'
import {
  api,
  type AuditDashboardStats,
  type AuditTask,
  type AuditReviewRequest,
} from '../../api/client'
import { useAuthStore } from '../../stores/authStore'

const { Title, Paragraph } = Typography

const TASK_STATUS_COLOR: Record<string, string> = {
  todo: 'default',
  in_progress: 'processing',
  review: 'blue',
  done: 'success',
  closed: 'default',
}

const TASK_STATUS_LABEL: Record<string, string> = {
  todo: '待办',
  in_progress: '进行中',
  review: '复核中',
  done: '已完成',
  closed: '已关闭',
}

const TASK_PRIORITY_COLOR: Record<string, string> = {
  high: 'error',
  medium: 'warning',
  low: 'default',
}

const TASK_PRIORITY_LABEL: Record<string, string> = {
  high: '高',
  medium: '中',
  low: '低',
}

const REVIEW_STATUS_COLOR: Record<string, string> = {
  draft: 'default',
  review: 'processing',
  approved: 'success',
  rejected: 'error',
  merged: 'purple',
  closed: 'default',
}

const REVIEW_STATUS_LABEL: Record<string, string> = {
  draft: '草稿',
  review: '复核中',
  approved: '已通过',
  rejected: '已退回',
  merged: '已归档',
  closed: '已关闭',
}

export function AuditDashboardPage() {
  const { currentLedgerId } = useAuthStore()
  const [stats, setStats] = useState<AuditDashboardStats | null>(null)
  const [todoTasks, setTodoTasks] = useState<AuditTask[]>([])
  const [pendingReviews, setPendingReviews] = useState<AuditReviewRequest[]>([])
  const [loading, setLoading] = useState(false)

  const loadDashboard = () => {
    if (!currentLedgerId) return
    setLoading(true)
    Promise.all([
      api.getAuditDashboardStats(),
      api.getMyTodoTasks(),
      api.getMyPendingReviewList(),
    ])
      .then(([statsData, tasks, reviews]) => {
        setStats(statsData)
        setTodoTasks(tasks)
        setPendingReviews(reviews)
      })
      .catch((error: Error) => message.error(error.message || '加载工作台数据失败'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadDashboard()
  }, [currentLedgerId])

  const taskColumns = [
    { title: '任务编号', dataIndex: 'task_no', key: 'task_no', width: 120 },
    { title: '标题', dataIndex: 'title', key: 'title', ellipsis: true },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (value: string) => (
        <Tag color={TASK_STATUS_COLOR[value] || 'default'}>
          {TASK_STATUS_LABEL[value] || value}
        </Tag>
      ),
    },
    {
      title: '优先级',
      dataIndex: 'priority',
      key: 'priority',
      width: 80,
      render: (value: string) => (
        <Tag color={TASK_PRIORITY_COLOR[value] || 'default'}>
          {TASK_PRIORITY_LABEL[value] || value}
        </Tag>
      ),
    },
    {
      title: '截止日期',
      dataIndex: 'due_date',
      key: 'due_date',
      width: 120,
      render: (value: string | null) => value || '-',
    },
    {
      title: '操作',
      key: 'action',
      width: 80,
      render: () => (
        <Button type="link" size="small" icon={<SearchOutlined />}>
          查看
        </Button>
      ),
    },
  ]

  const reviewColumns = [
    { title: '编号', dataIndex: 'pr_no', key: 'pr_no', width: 120 },
    { title: '标题', dataIndex: 'title', key: 'title', ellipsis: true },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (value: string) => (
        <Tag color={REVIEW_STATUS_COLOR[value] || 'default'}>
          {REVIEW_STATUS_LABEL[value] || value}
        </Tag>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
    },
    {
      title: '操作',
      key: 'action',
      width: 80,
      render: () => (
        <Button type="link" size="small" icon={<SearchOutlined />}>
          查看
        </Button>
      ),
    },
  ]

  return (
    <div>
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <Title level={4} style={{ margin: 0 }}>
              审计工作台
            </Title>
            <Paragraph type="secondary" style={{ marginBottom: 0 }}>
              查看待办任务、复核请求和今日完成情况
            </Paragraph>
          </div>
          <Button
            icon={<ReloadOutlined />}
            onClick={loadDashboard}
            loading={loading}
            disabled={!currentLedgerId}
          >
            刷新
          </Button>
        </div>

        <Row gutter={16}>
          <Col xs={12} sm={12} md={6}>
            <Card loading={loading}>
              <Statistic
                title="待办任务"
                value={stats?.todo_tasks_count || 0}
                prefix={<ClockCircleOutlined style={{ color: '#faad14' }} />}
                valueStyle={{ color: '#faad14' }}
              />
            </Card>
          </Col>
          <Col xs={12} sm={12} md={6}>
            <Card loading={loading}>
              <Statistic
                title="进行中任务"
                value={stats?.in_progress_tasks_count || 0}
                prefix={<PlayCircleOutlined style={{ color: '#1890ff' }} />}
                valueStyle={{ color: '#1890ff' }}
              />
            </Card>
          </Col>
          <Col xs={12} sm={12} md={6}>
            <Card loading={loading}>
              <Statistic
                title="待我复核"
                value={stats?.pending_my_review_count || 0}
                prefix={<SearchOutlined style={{ color: '#722ed1' }} />}
                valueStyle={{ color: '#722ed1' }}
              />
            </Card>
          </Col>
          <Col xs={12} sm={12} md={6}>
            <Card loading={loading}>
              <Statistic
                title="今日完成"
                value={stats?.closed_today_count || 0}
                prefix={<CheckCircleOutlined style={{ color: '#52c41a' }} />}
                valueStyle={{ color: '#52c41a' }}
              />
            </Card>
          </Col>
        </Row>

        <Card title="我的待办任务" size="small">
          <Table
            rowKey="id"
            loading={loading}
            columns={taskColumns}
            dataSource={todoTasks}
            pagination={{ pageSize: 10 }}
            locale={{ emptyText: '暂无待办任务' }}
            size="small"
          />
        </Card>

        <Card title="待我复核的请求" size="small">
          <Table
            rowKey="id"
            loading={loading}
            columns={reviewColumns}
            dataSource={pendingReviews}
            pagination={{ pageSize: 10 }}
            locale={{ emptyText: '暂无待复核的请求' }}
            size="small"
          />
        </Card>
      </Space>
    </div>
  )
}
