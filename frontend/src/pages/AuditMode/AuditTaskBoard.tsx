import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
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
import {
  api,
  type AuditTask,
  type AuditTaskCreate,
  type AuditWorkBranch,
  type Project,
  type ProjectTaskAssignee,
} from '../../api/client'
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

export function AuditTaskBoard() {
  const [searchParams] = useSearchParams()
  const projectIdParam = searchParams.get('projectId')
  const projectId = projectIdParam ? Number(projectIdParam) : null
  const { currentLedgerId, userLedgers } = useAuthStore()
  const [tasks, setTasks] = useState<AuditTask[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(15)
  const [loading, setLoading] = useState(false)
  const [statusFilter, setStatusFilter] = useState<string | undefined>()
  const [modalVisible, setModalVisible] = useState(false)
  const [createForm] = Form.useForm()
  const [assignees, setAssignees] = useState<ProjectTaskAssignee[]>([])
  const [projects, setProjects] = useState<Project[]>([])
  const [branchesByTask, setBranchesByTask] = useState<Record<number, AuditWorkBranch[]>>({})
  const [branchLoadingTaskId, setBranchLoadingTaskId] = useState<number | null>(null)
  const [statusUpdatingTaskId, setStatusUpdatingTaskId] = useState<number | null>(null)
  const [createSubmitting, setCreateSubmitting] = useState(false)

  // ledger_id 后端必填：优先当前选中账簿，否则取第一个用户账簿
  const effectiveLedgerId = currentLedgerId ?? userLedgers[0]?.id ?? null

  const loadProjects = () => {
    api.listProjects()
      .then((rows) => setProjects(rows.filter((item) => item.status !== 'cancelled')))
      .catch((error: Error) => message.error(error.message || '加载项目列表失败'))
  }

  const loadAssignees = () => {
    if (!projectId) {
      setAssignees([])
      return
    }
    api.listProjectTaskAssignees(projectId, effectiveLedgerId)
      .then(setAssignees)
      .catch((error: Error) => message.error(error.message || '加载指派人列表失败'))
  }

  const loadTasks = () => {
    if (!projectId) return
    setLoading(true)
    api
      .listAuditTasks(projectId, {
        status: statusFilter,
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
  }, [statusFilter, projectId])

  useEffect(() => {
    loadAssignees()
  }, [projectId, effectiveLedgerId])

  useEffect(() => {
    loadTasks()
  }, [projectId, page, pageSize, statusFilter])

  const loadBranchesForTask = async (taskId: number) => {
    if (branchesByTask[taskId]) return
    setBranchLoadingTaskId(taskId)
    try {
      const branches = await api.getBranchesByTask(taskId)
      setBranchesByTask((prev) => ({ ...prev, [taskId]: branches }))
    } catch (error) {
      const msg = error instanceof Error ? error.message : '加载工作分支失败'
      message.error(msg)
    } finally {
      setBranchLoadingTaskId(null)
    }
  }

  const handleStatusChange = async (taskId: number, status: string) => {
    setStatusUpdatingTaskId(taskId)
    try {
      await api.updateAuditTaskStatus(taskId, status)
      message.success('任务状态已更新')
      loadTasks()
    } catch (error) {
      const msg = error instanceof Error ? error.message : '更新任务状态失败'
      message.error(msg)
    } finally {
      setStatusUpdatingTaskId(null)
    }
  }

  const handleCreateTask = async () => {
    if (!projectId) {
      message.error('缺少项目 ID，无法创建任务')
      return
    }
    if (!effectiveLedgerId) {
      message.error('当前没有可用账簿，无法创建任务')
      return
    }
    try {
      const values = await createForm.validateFields()
      setCreateSubmitting(true)
      const payload: AuditTaskCreate = {
        project_id: projectId,
        ledger_id: effectiveLedgerId,
        title: values.title,
        description: values.description,
        task_type: values.task_type,
        audit_area: values.audit_area,
        priority: values.priority,
        assignee_id: values.assignee_id,
        due_date: values.due_date ? values.due_date.format('YYYY-MM-DD') : undefined,
      }
      await api.createAuditTask(payload)
      message.success('任务创建成功')
      setModalVisible(false)
      createForm.resetFields()
      loadTasks()
    } catch (error) {
      if (error && typeof error === 'object' && 'errorFields' in error) return
      const msg = error instanceof Error ? error.message : '创建任务失败'
      message.error(msg)
    } finally {
      setCreateSubmitting(false)
    }
  }

  const columns = [
    { title: '任务编号', dataIndex: 'task_no', key: 'task_no', width: 130 },
    { title: '标题', dataIndex: 'title', key: 'title', ellipsis: true },
    {
      title: '类型',
      dataIndex: 'task_type',
      key: 'task_type',
      width: 110,
      render: (value: string) => <Tag>{TASK_TYPE_LABEL[value] || value}</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 150,
      render: (value: string, row: AuditTask) => (
        <Select
          size="small"
          style={{ width: 130 }}
          value={value}
          onChange={(next) => handleStatusChange(row.id, next)}
          loading={statusUpdatingTaskId === row.id}
          options={STATUS_OPTIONS}
        />
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
      title: '指派人',
      dataIndex: 'assignee_id',
      key: 'assignee_id',
      width: 110,
      render: (value: number | null) => (value ? `用户 ${value}` : '未分配'),
    },
    {
      title: '截止日期',
      dataIndex: 'due_date',
      key: 'due_date',
      width: 120,
      render: (value: string | null) => (value ? dayjs(value).format('YYYY-MM-DD') : '-'),
    },
  ]

  const expandedRowRender = (row: AuditTask) => {
    const branches = branchesByTask[row.id] || []
    return (
      <Card size="small" title={`工作分支（${branches.length}）`} loading={branchLoadingTaskId === row.id}>
        <Table
          rowKey="id"
          size="small"
          dataSource={branches}
          pagination={false}
          locale={{ emptyText: '暂无工作分支' }}
          columns={[
            { title: '分支名称', dataIndex: 'branch_name', key: 'branch_name' },
            {
              title: '基准分支',
              dataIndex: 'base_branch',
              key: 'base_branch',
              render: (v: string | null) => v || 'main',
            },
            {
              title: '状态',
              dataIndex: 'status',
              key: 'status',
              render: (v: string) => (
                <Tag color={BRANCH_STATUS_COLOR[v] || 'default'}>
                  {BRANCH_STATUS_LABEL[v] || v}
                </Tag>
              ),
            },
            {
              title: '创建时间',
              dataIndex: 'created_at',
              key: 'created_at',
              render: (v: string) => (v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-'),
            },
          ]}
        />
      </Card>
    )
  }

  const projectName = projects.find((item) => item.id === projectId)?.name

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
              <FileTextOutlined /> 审计任务看板
            </Title>
            <Paragraph type="secondary" style={{ marginBottom: 0 }}>
              管理审计任务，支持状态流转与工作分支查看。
              {projectId ? ` 当前项目：${projectName || `#${projectId}`}` : ' 请通过 ?projectId= 指定项目'}
              {effectiveLedgerId ? ` 当前账簿：#${effectiveLedgerId}` : '（未选中账簿）'}
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
              disabled={!projectId || !effectiveLedgerId}
            >
              新建任务
            </Button>
          </Space>
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
              showSizeChanger: true,
              showTotal: (t) => `共 ${t} 条`,
            }}
            onChange={handleTableChange}
            expandable={{
              expandedRowRender,
              onExpand: (expanded, row) => {
                if (expanded) loadBranchesForTask(row.id)
              },
            }}
            locale={{ emptyText: projectId ? '暂无任务数据' : '请通过 URL 携带 projectId 参数指定项目' }}
          />
        </Card>
      </Space>

      <Modal
        title="新建任务"
        open={modalVisible}
        onOk={handleCreateTask}
        confirmLoading={createSubmitting}
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
          <Form.Item name="audit_area" label="审计区域">
            <Input placeholder="例如：收入、存货、资金" maxLength={100} />
          </Form.Item>
          <Form.Item name="assignee_id" label="指派人">
            <Select
              allowClear
              showSearch
              optionFilterProp="label"
              placeholder={assignees.length ? '请选择指派人' : '暂无可指派人员'}
              options={assignees.map((item) => {
                const name = item.username || item.phone || item.email || `用户 ${item.id}`
                const roleText = [item.project_role, ...(item.ledger_roles || [])].filter(Boolean).join(' / ')
                return { value: item.id, label: roleText ? `${name}（${roleText}）` : name }
              })}
            />
          </Form.Item>
          <Form.Item name="due_date" label="截止日期">
            <DatePicker style={{ width: '100%' }} placeholder="选择截止日期" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
