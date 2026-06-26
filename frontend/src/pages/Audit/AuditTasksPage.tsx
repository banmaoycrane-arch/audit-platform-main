import { useEffect, useState } from 'react'
import {
  Button,
  Card,
  DatePicker,
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
import { PlusOutlined, ReloadOutlined, FileTextOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { api, type AuditTask, type Project } from '../../api/client'
import { useAuthStore } from '../../stores/authStore'

const { Title, Paragraph } = Typography
const { TextArea } = Input

const STATUS_COLOR: Record<string, string> = {
  open: 'default',
  todo: 'processing',
  in_progress: 'blue',
  review: 'gold',
  closed: 'success',
  rejected: 'error',
}

const STATUS_LABEL: Record<string, string> = {
  open: '开放',
  todo: '待办',
  in_progress: '进行中',
  review: '复核中',
  closed: '已关闭',
  rejected: '已拒绝',
}

const PRIORITY_COLOR: Record<string, string> = {
  high: 'red',
  normal: 'default',
  low: 'blue',
}

const PRIORITY_LABEL: Record<string, string> = {
  high: '高',
  normal: '中',
  low: '低',
}

const TASK_TYPE_LABEL: Record<string, string> = {
  risk_assessment: '风险评估',
  control_test: '控制测试',
  substantive: '实质性程序',
  review: '复核',
  other: '其他',
}

const STATUS_OPTIONS = [
  { value: 'open', label: '开放' },
  { value: 'todo', label: '待办' },
  { value: 'in_progress', label: '进行中' },
  { value: 'review', label: '复核中' },
  { value: 'closed', label: '已关闭' },
]

const PRIORITY_OPTIONS = [
  { value: 'high', label: '高' },
  { value: 'normal', label: '中' },
  { value: 'low', label: '低' },
]

const TASK_TYPE_OPTIONS = [
  { value: 'risk_assessment', label: '风险评估' },
  { value: 'control_test', label: '控制测试' },
  { value: 'substantive', label: '实质性程序' },
  { value: 'review', label: '复核' },
  { value: 'other', label: '其他' },
]

export function AuditTasksPage() {
  const { currentLedgerId } = useAuthStore()
  const [projects, setProjects] = useState<Project[]>([])
  const [projectId, setProjectId] = useState<number | null>(null)
  const [projectLedgers, setProjectLedgers] = useState<{ id: number; name: string }[]>([])
  const [tasks, setTasks] = useState<AuditTask[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(15)
  const [loading, setLoading] = useState(false)
  const [statusFilter, setStatusFilter] = useState<string | undefined>()
  const [priorityFilter, setPriorityFilter] = useState<string | undefined>()
  const [taskTypeFilter, setTaskTypeFilter] = useState<string | undefined>()
  const [modalVisible, setModalVisible] = useState(false)
  const [detailVisible, setDetailVisible] = useState(false)
  const [selectedTask, setSelectedTask] = useState<AuditTask | null>(null)
  const [createForm] = Form.useForm()

  const loadProjects = () => {
    api.listProjects().then((rows) => {
      setProjects(rows)
      if (!projectId && rows.length > 0) setProjectId(rows[0].id)
    })
  }

  const loadProjectLedgers = () => {
    if (!projectId) return
    api.listProjectLedgers(projectId).then((rows) => {
      setProjectLedgers(rows)
    })
  }

  const loadTasks = () => {
    if (!projectId) return
    setLoading(true)
    api
      .listAuditTasks(projectId, {
        status: statusFilter,
        task_type: taskTypeFilter,
        page,
        page_size: pageSize,
      })
      .then((res) => {
        setTasks(res.items)
        setTotal(res.total)
      })
      .catch((error: Error) => message.error(error.message || '加载任务列表失败'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadProjects()
  }, [])

  useEffect(() => {
    setPage(1)
    loadProjectLedgers()
  }, [statusFilter, priorityFilter, taskTypeFilter, projectId])

  useEffect(() => {
    loadTasks()
  }, [projectId, page, pageSize, statusFilter, taskTypeFilter])

  const handleCreateTask = async () => {
    if (!projectId) return
    try {
      const values = await createForm.validateFields()
      const payload: any = {
        project_id: projectId,
        ledger_id: values.ledger_id,
        title: values.title,
        description: values.description,
        task_type: values.task_type,
        priority: values.priority,
        assignee_id: values.assignee_id,
        due_date: values.due_date ? values.due_date.format('YYYY-MM-DD') : undefined,
      }
      await api.createAuditTask(payload)
      message.success('任务创建成功')
      setModalVisible(false)
      createForm.resetFields()
      loadTasks()
    } catch (error: any) {
      if (error.errorFields) return
      message.error(error.message || '创建任务失败')
    }
  }

  const handleViewDetail = (task: AuditTask) => {
    setSelectedTask(task)
    setDetailVisible(true)
  }

  const columns = [
    {
      title: '任务编号',
      dataIndex: 'task_no',
      key: 'task_no',
      width: 120,
    },
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true,
    },
    {
      title: '类型',
      dataIndex: 'task_type',
      key: 'task_type',
      width: 100,
      render: (value: string) => <Tag>{TASK_TYPE_LABEL[value] || value}</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (value: string) => (
        <Tag color={STATUS_COLOR[value]}>{STATUS_LABEL[value] || value}</Tag>
      ),
    },
    {
      title: '优先级',
      dataIndex: 'priority',
      key: 'priority',
      width: 90,
      render: (value: string) => (
        <Tag color={PRIORITY_COLOR[value]}>{PRIORITY_LABEL[value] || value}</Tag>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 170,
      render: (value: string) => dayjs(value).format('YYYY-MM-DD HH:mm'),
    },
    {
      title: '截止日期',
      dataIndex: 'due_date',
      key: 'due_date',
      width: 120,
      render: (value: string | null) => (value ? dayjs(value).format('YYYY-MM-DD') : '-'),
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_: unknown, row: AuditTask) => (
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
              <FileTextOutlined /> 审计任务管理
            </Title>
            <Paragraph type="secondary" style={{ marginBottom: 0 }}>
              管理审计项目任务，支持任务创建、状态跟踪和优先级管理。
            </Paragraph>
          </div>
          <Space>
            <Button icon={<ReloadOutlined />} onClick={loadTasks} loading={loading}>
              刷新
            </Button>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => setModalVisible(true)}
              disabled={!projectId}
            >
              新建任务
            </Button>
          </Space>
        </div>

        <Card size="small">
          <Space wrap style={{ marginBottom: 12 }}>
            <span>项目：</span>
            <Select
              style={{ width: 220 }}
              value={projectId || undefined}
              onChange={setProjectId}
              options={projects.map((item) => ({ value: item.id, label: item.name }))}
              placeholder="选择项目"
            />
          </Space>
          <Space wrap>
            <span>状态：</span>
            <Select
              style={{ width: 140 }}
              value={statusFilter}
              onChange={setStatusFilter}
              options={STATUS_OPTIONS}
              placeholder="全部状态"
              allowClear
            />
            <span>优先级：</span>
            <Select
              style={{ width: 120 }}
              value={priorityFilter}
              onChange={setPriorityFilter}
              options={PRIORITY_OPTIONS}
              placeholder="全部优先级"
              allowClear
            />
            <span>任务类型：</span>
            <Select
              style={{ width: 140 }}
              value={taskTypeFilter}
              onChange={setTaskTypeFilter}
              options={TASK_TYPE_OPTIONS}
              placeholder="全部类型"
              allowClear
            />
          </Space>
        </Card>

        <Card title="任务列表">
          <Table
            rowKey="id"
            loading={loading}
            columns={columns}
            dataSource={tasks}
            pagination={{
              current: page,
              pageSize,
              total,
              onChange: (p) => setPage(p),
              showSizeChanger: false,
            }}
            locale={{ emptyText: '暂无任务数据' }}
          />
        </Card>
      </Space>

      <Modal
        title="新建任务"
        open={modalVisible}
        onOk={handleCreateTask}
        onCancel={() => {
          setModalVisible(false)
          createForm.resetFields()
        }}
        okText="创建"
        cancelText="取消"
        destroyOnClose
      >
        <Form form={createForm} layout="vertical">
          <Form.Item
            name="title"
            label="任务标题"
            rules={[{ required: true, message: '请输入任务标题' }]}
          >
            <Input placeholder="请输入任务标题" maxLength={200} />
          </Form.Item>
          <Form.Item
            name="ledger_id"
            label="关联账套"
            rules={[{ required: true, message: '请选择关联账套' }]}
          >
            <Select
              options={projectLedgers.map((item) => ({ value: item.id, label: item.name }))}
              placeholder="请选择账套"
              style={{ width: '100%' }}
            />
          </Form.Item>
          <Form.Item name="description" label="任务描述">
            <TextArea rows={3} placeholder="请输入任务描述" maxLength={1000} />
          </Form.Item>
          <Space wrap style={{ width: '100%' }}>
            <Form.Item name="task_type" label="任务类型" style={{ flex: 1, minWidth: 160 }}>
              <Select options={TASK_TYPE_OPTIONS} placeholder="请选择任务类型" />
            </Form.Item>
            <Form.Item name="priority" label="优先级" style={{ flex: 1, minWidth: 120 }}>
              <Select options={PRIORITY_OPTIONS} placeholder="请选择优先级" />
            </Form.Item>
          </Space>
          <Form.Item name="assignee_id" label="负责人">
            <Input placeholder="请输入负责人 ID" type="number" />
          </Form.Item>
          <Form.Item name="due_date" label="截止日期">
            <DatePicker style={{ width: '100%' }} placeholder="选择截止日期" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="任务详情"
        open={detailVisible}
        onCancel={() => {
          setDetailVisible(false)
          setSelectedTask(null)
        }}
        footer={[
          <Button key="close" onClick={() => setDetailVisible(false)}>
            关闭
          </Button>,
        ]}
        width={600}
      >
        {selectedTask && (
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <div>
              <div style={{ color: '#8c8c8c', marginBottom: 4 }}>任务编号</div>
              <div style={{ fontSize: 16, fontWeight: 500 }}>{selectedTask.task_no}</div>
            </div>
            <div>
              <div style={{ color: '#8c8c8c', marginBottom: 4 }}>标题</div>
              <div>{selectedTask.title}</div>
            </div>
            <Space wrap>
              <div>
                <div style={{ color: '#8c8c8c', marginBottom: 4 }}>类型</div>
                <Tag>{TASK_TYPE_LABEL[selectedTask.task_type] || selectedTask.task_type}</Tag>
              </div>
              <div>
                <div style={{ color: '#8c8c8c', marginBottom: 4 }}>状态</div>
                <Tag color={STATUS_COLOR[selectedTask.status]}>
                  {STATUS_LABEL[selectedTask.status] || selectedTask.status}
                </Tag>
              </div>
              <div>
                <div style={{ color: '#8c8c8c', marginBottom: 4 }}>优先级</div>
                <Tag color={PRIORITY_COLOR[selectedTask.priority]}>
                  {PRIORITY_LABEL[selectedTask.priority] || selectedTask.priority}
                </Tag>
              </div>
            </Space>
            {selectedTask.description && (
              <div>
                <div style={{ color: '#8c8c8c', marginBottom: 4 }}>描述</div>
                <div>{selectedTask.description}</div>
              </div>
            )}
            <Space wrap>
              <div>
                <div style={{ color: '#8c8c8c', marginBottom: 4 }}>创建时间</div>
                <div>{dayjs(selectedTask.created_at).format('YYYY-MM-DD HH:mm')}</div>
              </div>
              {selectedTask.due_date && (
                <div>
                  <div style={{ color: '#8c8c8c', marginBottom: 4 }}>截止日期</div>
                  <div>{dayjs(selectedTask.due_date).format('YYYY-MM-DD')}</div>
                </div>
              )}
            </Space>
          </Space>
        )}
      </Modal>
    </div>
  )
}
