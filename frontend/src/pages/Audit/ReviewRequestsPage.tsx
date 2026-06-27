import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
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
import { PlusOutlined, ReloadOutlined, PullRequestOutlined } from '@ant-design/icons'
import { api, type AuditReviewRequest, type Project } from '../../api/client'
import { useAuthStore } from '../../stores/authStore'

const { Title, Paragraph } = Typography

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

const MY_FILTER_OPTIONS = [
  { value: 'all', label: '全部' },
  { value: 'pending_my_review', label: '待我复核' },
  { value: 'submitted_by_me', label: '我提交的' },
]

export function ReviewRequestsPage() {
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const [projects, setProjects] = useState<Project[]>([])
  const [projectId, setProjectId] = useState<number | null>(null)
  const [reviewRequests, setReviewRequests] = useState<AuditReviewRequest[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [statusFilter, setStatusFilter] = useState<string | undefined>()
  const [myFilter, setMyFilter] = useState<string>('all')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(15)
  const [modalVisible, setModalVisible] = useState(false)
  const [createForm] = Form.useForm()

  const loadProjects = () => {
    api.listProjects().then((rows) => {
      setProjects(rows)
      if (!projectId && rows.length > 0) setProjectId(rows[0].id)
    })
  }

  const loadReviewRequests = () => {
    setLoading(true)
    const filters: Parameters<typeof api.listAuditReviewRequests>[0] = {
      page,
      page_size: pageSize,
    }
    if (projectId != null) filters.project_id = projectId
    if (statusFilter) filters.status = statusFilter
    if (myFilter === 'submitted_by_me' && user?.id != null) {
      filters.created_by = user.id
    }
    if (myFilter === 'pending_my_review' && user?.id != null) {
      filters.reviewer_id = user.id
    }
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
    loadProjects()
  }, [])

  useEffect(() => {
    setPage(1)
  }, [projectId, statusFilter, myFilter])

  useEffect(() => {
    if (projectId != null) {
      loadReviewRequests()
    }
  }, [projectId, statusFilter, myFilter, page, pageSize])

  const handleTableChange = (pagination: { current: number; pageSize: number }) => {
    setPage(pagination.current)
    setPageSize(pagination.pageSize)
  }

  const handleViewDetail = (record: AuditReviewRequest) => {
    navigate(`/audit/review-requests/${record.id}`)
  }

  const handleCreate = async () => {
    try {
      await createForm.validateFields()
      message.success('新建复核请求功能将从任务详情页提供')
      setModalVisible(false)
      createForm.resetFields()
    } catch {
    }
  }

  const columns = [
    {
      title: '请求编号',
      dataIndex: 'pr_no',
      key: 'pr_no',
      width: 120,
    },
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (value: string) => (
        <Tag color={STATUS_COLOR[value] || 'default'}>
          {STATUS_LABEL[value] || value}
        </Tag>
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
      render: (value: number) => `#${value}`,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (value: string) => new Date(value).toLocaleString('zh-CN'),
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_: unknown, row: AuditReviewRequest) => (
        <Button size="small" type="link" onClick={() => handleViewDetail(row)}>
          查看详情
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
              <PullRequestOutlined /> 复核请求
            </Title>
            <Paragraph type="secondary" style={{ marginBottom: 0 }}>
              多级复核工作流，支持草稿、复核中、需修改、已通过、已合并等状态流转。
            </Paragraph>
          </div>
          <Space>
            <Button icon={<ReloadOutlined />} onClick={loadReviewRequests} loading={loading}>
              刷新
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalVisible(true)}>
              新建复核请求
            </Button>
          </Space>
        </div>

        <Card size="small">
          <Space wrap style={{ width: '100%' }}>
            <span>项目：</span>
            <Select
              style={{ width: 220 }}
              value={projectId || undefined}
              onChange={setProjectId}
              options={projects.map((item) => ({ value: item.id, label: item.name }))}
              placeholder="选择项目"
            />
            <span style={{ marginLeft: 16 }}>状态：</span>
            <Select
              style={{ width: 140 }}
              value={statusFilter}
              onChange={setStatusFilter}
              allowClear
              placeholder="全部状态"
              options={Object.entries(STATUS_LABEL).map(([value, label]) => ({ value, label }))}
            />
            <span style={{ marginLeft: 16 }}>我的筛选：</span>
            <Select
              style={{ width: 140 }}
              value={myFilter}
              onChange={setMyFilter}
              options={MY_FILTER_OPTIONS}
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
              showTotal: (total) => `共 ${total} 条`,
            }}
            onChange={handleTableChange}
            locale={{ emptyText: '暂无复核请求' }}
          />
        </Card>
      </Space>

      <Modal
        title="新建复核请求"
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        footer={null}
        destroyOnClose
      >
        <Form form={createForm} layout="vertical" onFinish={handleCreate}>
          <Form.Item
            name="title"
            label="标题"
            rules={[{ required: true, message: '请输入标题' }]}
          >
            <Input placeholder="请输入复核请求标题" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={3} placeholder="请输入描述（可选）" />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">
                创建
              </Button>
              <Button onClick={() => setModalVisible(false)}>取消</Button>
            </Space>
            <Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 0 }}>
              MVP 版本：完整的新建功能将从任务详情页提供，支持关联任务和分支。
            </Paragraph>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
