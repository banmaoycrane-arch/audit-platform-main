import { useEffect, useState } from 'react'
import { Card, Typography, Button, Space, Tag, message, Row, Col, Statistic, Modal, Input, Empty, Dropdown, Form, Select, Alert } from 'antd'
import { useNavigate } from 'react-router-dom'
import {
  PlusOutlined,
  ProjectOutlined,
  ClockCircleOutlined,
  CheckCircleOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  RedoOutlined,
  CloseCircleOutlined,
  MoreOutlined,
  CalendarOutlined,
  UserOutlined,
  DollarOutlined,
} from '@ant-design/icons'
import { api, type Ledger, type Team } from '../api/client'
import { useAuthStore } from '../stores/authStore'

const { Title, Paragraph, Text } = Typography

export type Project = {
  id: number
  name: string
  description?: string | null
  team_id?: number
  type?: string
  status: 'active' | 'completed' | 'paused' | 'draft' | 'cancelled'
  start_date: string | null
  end_date: string | null
  manager?: string | null
  budget?: number | null
  created_at: string | null
  updated_at: string | null
}

const statusMap: Record<string, { color: string; label: string; icon: React.ReactNode }> = {
  active: { color: 'processing', label: '进行中', icon: <ClockCircleOutlined /> },
  completed: { color: 'success', label: '已完成', icon: <CheckCircleOutlined /> },
  paused: { color: 'warning', label: '已暂停', icon: <PauseCircleOutlined /> },
  draft: { color: 'default', label: '草稿', icon: <ProjectOutlined /> },
  cancelled: { color: 'error', label: '已取消', icon: <CloseCircleOutlined /> },
}

const statusBorderMap: Record<string, string> = {
  active: '#1890ff',
  completed: '#52c41a',
  paused: '#faad14',
  draft: '#d9d9d9',
  cancelled: '#ff4d4f',
}

// 状态筛选
const statusFilters = [
  { key: 'all', label: '全部' },
  { key: 'active', label: '进行中' },
  { key: 'completed', label: '已完成' },
  { key: 'paused', label: '已暂停' },
  { key: 'cancelled', label: '已取消' },
]

export function ProjectsPage() {
  const navigate = useNavigate()
  const { refreshAuthContext } = useAuthStore()
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState<Record<number, boolean>>({})
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [reasonModal, setReasonModal] = useState<{
    open: boolean
    projectId: number | null
    action: string
    title: string
  }>({ open: false, projectId: null, action: '', title: '' })
  const [reason, setReason] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const [editOpen, setEditOpen] = useState(false)
  const [editingProject, setEditingProject] = useState<Project | null>(null)
  const [teams, setTeams] = useState<Team[]>([])
  const [ledgers, setLedgers] = useState<Ledger[]>([])
  const [projectLedgerMap, setProjectLedgerMap] = useState<Record<number, number[]>>({})
  const [createForm] = Form.useForm()
  const [editForm] = Form.useForm()

  const filteredProjects = statusFilter === 'all' ? projects : projects.filter(p => p.status === statusFilter)

  useEffect(() => {
    setLoading(true)
    Promise.all([api.listProjects(), api.listTeams(), api.listLedgers()])
      .then(async ([projectRes, teamRes, ledgerRes]) => {
        const ledgerPairs = await Promise.all(
          projectRes.map(async (project) => [project.id, (await api.listProjectLedgers(project.id)).map((ledger) => ledger.id)] as const)
        )
        const ledgerMap = Object.fromEntries(ledgerPairs)
        setProjects(projectRes)
        setTeams(teamRes)
        setLedgers(ledgerRes)
        setProjectLedgerMap(ledgerMap)
      })
      .catch(() => {
        message.error('加载项目列表失败')
      })
      .finally(() => setLoading(false))
  }, [])

  const handleCreateProject = async () => {
    const values = await createForm.validateFields()
    try {
      const selectedLedgerIds = values.ledger_ids || []
      const created = await api.createProject({
        team_id: values.team_id,
        name: values.name,
        project_type: values.project_type,
        status: 'active',
        start_date: values.start_date || null,
        end_date: values.end_date || null,
      })
      await Promise.all(selectedLedgerIds.map((ledgerId: number) => api.associateProjectLedger(created.id, ledgerId)))
      setProjects((prev) => [created, ...prev])
      setProjectLedgerMap((prev) => ({ ...prev, [created.id]: selectedLedgerIds }))
      await refreshAuthContext()
      message.success(selectedLedgerIds.length ? '项目创建并绑定账簿成功' : '项目创建成功')
      setCreateOpen(false)
      createForm.resetFields()
    } catch (error: any) {
      message.error(error.message || '项目创建失败')
    }
  }

  const openEditProject = (project: Project) => {
    setEditingProject(project)
    editForm.setFieldsValue({
      team_id: project.team_id,
      name: project.name,
      project_type: project.type || 'audit',
      status: project.status,
      start_date: project.start_date || undefined,
      end_date: project.end_date || undefined,
      ledger_ids: projectLedgerMap[project.id] || [],
    })
    setEditOpen(true)
  }

  const syncProjectLedgers = async (projectId: number, nextLedgerIds: number[]) => {
    const previousLedgerIds = projectLedgerMap[projectId] || []
    const toAdd = nextLedgerIds.filter((id) => !previousLedgerIds.includes(id))
    const toRemove = previousLedgerIds.filter((id) => !nextLedgerIds.includes(id))
    await Promise.all([
      ...toAdd.map((ledgerId) => api.associateProjectLedger(projectId, ledgerId)),
      ...toRemove.map((ledgerId) => api.removeProjectLedger(projectId, ledgerId)),
    ])
    setProjectLedgerMap((prev) => ({ ...prev, [projectId]: nextLedgerIds }))
  }

  const handleUpdateProject = async () => {
    if (!editingProject) return
    const values = await editForm.validateFields()
    try {
      const selectedLedgerIds = values.ledger_ids || []
      const updated = await api.updateProject(editingProject.id, {
        team_id: values.team_id,
        name: values.name,
        project_type: values.project_type,
        status: values.status,
        start_date: values.start_date || null,
        end_date: values.end_date || null,
      })
      await syncProjectLedgers(editingProject.id, selectedLedgerIds)
      setProjects((prev) => prev.map((project) => project.id === updated.id ? updated : project))
      await refreshAuthContext()
      message.success('项目已更新')
      setEditOpen(false)
      setEditingProject(null)
      editForm.resetFields()
    } catch (error: any) {
      message.error(error.message || '项目更新失败')
    }
  }

  const handleLifecycleAction = async (projectId: number, action: string) => {
    const titles: Record<string, string> = {
      start: '启动项目',
      pause: '暂停项目',
      complete: '完成项目',
      reopen: '重新打开项目',
      cancel: '取消项目',
    }
    setReasonModal({ open: true, projectId, action, title: titles[action] || action })
  }

  const confirmAction = async () => {
    if (!reasonModal.projectId || !reasonModal.action) return
    setActionLoading((prev) => ({ ...prev, [reasonModal.projectId!]: true }))
    try {
      const endpoint = `/api/projects/${reasonModal.projectId}/${reasonModal.action}`
      const response = await fetch(`${api.baseUrl}${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('token')}`,
        },
        body: JSON.stringify({ reason: reason || undefined }),
      })
      if (!response.ok) {
        throw new Error(await response.text())
      }
      const updated = await response.json()
      setProjects((prev) =>
        prev.map((p) => (p.id === updated.id ? { ...p, status: updated.status, updated_at: updated.updated_at } : p))
      )
      message.success(`${reasonModal.title}成功`)
    } catch (err: any) {
      message.error(`${reasonModal.title}失败：${err.message}`)
    } finally {
      setActionLoading((prev) => ({ ...prev, [reasonModal.projectId!]: false }))
      setReasonModal({ open: false, projectId: null, action: '', title: '' })
      setReason('')
    }
  }

  const getAvailableActions = (status: string) => {
    switch (status) {
      case 'draft':
        return ['start', 'cancel']
      case 'active':
        return ['pause', 'complete', 'cancel']
      case 'paused':
        return ['start', 'complete', 'cancel']
      case 'completed':
        return ['reopen']
      case 'cancelled':
        return ['reopen']
      default:
        return []
    }
  }

  const actionButtonMap: Record<string, { icon: React.ReactNode; label: string; danger?: boolean }> = {
    start: { icon: <PlayCircleOutlined />, label: '启动' },
    pause: { icon: <PauseCircleOutlined />, label: '暂停' },
    complete: { icon: <CheckCircleOutlined />, label: '完成' },
    reopen: { icon: <RedoOutlined />, label: '重新打开' },
    cancel: { icon: <CloseCircleOutlined />, label: '取消', danger: true },
  }

  // 项目卡片组件
  const ProjectCard = ({ project }: { project: Project }) => {
    const borderColor = statusBorderMap[project.status] || '#d9d9d9'
    const statusConfig = statusMap[project.status] || statusMap.draft
    const actions = getAvailableActions(project.status)
    const teamName = teams.find((team) => team.id === project.team_id)?.name
    const linkedLedgers = ledgers.filter((ledger) => (projectLedgerMap[project.id] || []).includes(ledger.id))
    
    const menuItems = [
      { key: 'view', label: '查看项目', onClick: () => openEditProject(project) },
      { key: 'edit', label: '编辑项目', onClick: () => openEditProject(project) },
      ...actions.map(action => ({
        key: action,
        label: actionButtonMap[action]?.label || action,
        danger: actionButtonMap[action]?.danger,
        onClick: () => handleLifecycleAction(project.id, action),
      })),
    ]
    
    return (
      <Card
        hoverable
        style={{
          border: `1px solid ${borderColor}`,
          borderRadius: 8,
          transition: 'all 0.3s',
        }}
        styles={{ body: { padding: 16 } }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
          <Tag color={statusConfig.color} icon={statusConfig.icon}>
            {statusConfig.label}
          </Tag>
          <Dropdown menu={{ items: menuItems }} trigger={['click']}>
            <Button type="text" icon={<MoreOutlined />} />
          </Dropdown>
        </div>
        
        <Title level={5} style={{ margin: '8px 0' }}>
          {project.name}
        </Title>
        
        {project.description && (
          <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>
            {project.description}
          </Text>
        )}
        
        <div style={{ fontSize: 12, color: '#666', display: 'flex', flexDirection: 'column', gap: 4 }}>
          {teamName && (
            <div>
              <ProjectOutlined style={{ marginRight: 4 }} />
              {teamName}
            </div>
          )}
          {project.manager && (
            <div>
              <UserOutlined style={{ marginRight: 4 }} />
              {project.manager}
            </div>
          )}
          <div>
            <ProjectOutlined style={{ marginRight: 4 }} />
            绑定账簿：{linkedLedgers.length ? linkedLedgers.map((ledger) => ledger.name).join('、') : '未绑定'}
          </div>
          {project.budget != null && (
            <div>
              <DollarOutlined style={{ marginRight: 4 }} />
              ¥ {project.budget!.toLocaleString()}
            </div>
          )}
          {(project.start_date || project.end_date) && (
            <div>
              <CalendarOutlined style={{ marginRight: 4 }} />
              {project.start_date || '-'} 至 {project.end_date || '-'}
            </div>
          )}
        </div>
      </Card>
    )
  }

  const activeCount = projects.filter((p) => p.status === 'active').length
  const completedCount = projects.filter((p) => p.status === 'completed').length
  const pausedCount = projects.filter((p) => p.status === 'paused').length
  const cancelledCount = projects.filter((p) => p.status === 'cancelled').length

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Title level={4} style={{ margin: 0 }}>
            <ProjectOutlined /> 项目管理
          </Title>
          <Paragraph type="secondary">管理核算项目、审计项目与业务项目</Paragraph>
        </Col>
        <Col>
          <Space>
            <Button onClick={() => navigate('/scope-settings?tab=project')}>管理配置</Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
              新增项目
            </Button>
          </Space>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card>
            <Statistic title="进行中项目" value={activeCount} valueStyle={{ color: '#1890ff' }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="已完成项目" value={completedCount} valueStyle={{ color: '#52c41a' }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="已暂停项目" value={pausedCount} valueStyle={{ color: '#faad14' }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="已取消项目" value={cancelledCount} valueStyle={{ color: '#ff4d4f' }} />
          </Card>
        </Col>
      </Row>

      <Card>
        {/* 状态筛选标签栏 */}
        <Space style={{ marginBottom: 16 }}>
          {statusFilters.map(filter => (
            <Tag
              key={filter.key}
              color={statusFilter === filter.key ? 'blue' : 'default'}
              style={{ cursor: 'pointer' }}
              onClick={() => setStatusFilter(filter.key)}
            >
              {filter.label}
            </Tag>
          ))}
        </Space>
        
        {filteredProjects.length === 0 ? (
          <Empty 
            description={statusFilter === 'all' ? '暂无项目' : `暂无${statusFilters.find(f => f.key === statusFilter)?.label}的项目`}
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          >
            <Button type="primary" onClick={() => setCreateOpen(true)}>
              创建第一个项目
            </Button>
          </Empty>
        ) : (
          <Row gutter={[12, 12]}>
            {filteredProjects.map((project) => (
              <Col xs={24} sm={12} md={8} lg={6} key={project.id}>
                <ProjectCard project={project} />
              </Col>
            ))}
          </Row>
        )}
      </Card>

      <Modal
        title="新增项目"
        open={createOpen}
        onOk={handleCreateProject}
        onCancel={() => setCreateOpen(false)}
        okText="创建"
        cancelText="取消"
      >
        <Form form={createForm} layout="vertical" initialValues={{ project_type: 'audit', ledger_ids: [] }}>
          <Form.Item name="team_id" label="所属团队" rules={[{ required: true, message: '请选择团队' }]}>
            <Select
              options={teams.map((team) => ({ value: team.id, label: team.name }))}
              placeholder={teams.length ? '请选择团队' : '请先在团队管理中创建团队'}
            />
          </Form.Item>
          <Form.Item name="name" label="项目名称" rules={[{ required: true, message: '请输入项目名称' }]}>
            <Input placeholder="例如：XX公司2026年度审计" />
          </Form.Item>
          <Form.Item name="project_type" label="项目类型">
            <Select
              options={[
                { value: 'audit', label: '审计项目' },
                { value: 'accounting', label: '核算项目' },
                { value: 'tax', label: '税务项目' },
              ]}
            />
          </Form.Item>
          <Form.Item name="ledger_ids" label="绑定账簿">
            <Select
              mode="multiple"
              allowClear
              placeholder={ledgers.length ? '请选择项目要绑定的账簿' : '暂无可绑定账簿'}
              options={ledgers.map((ledger) => ({ value: ledger.id, label: ledger.name }))}
            />
          </Form.Item>
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
            message="项目绑定账簿后，审计工作台和解析资料会按项目范围归集。"
          />
          <Form.Item name="start_date" label="开始日期">
            <Input placeholder="2026-01-01" />
          </Form.Item>
          <Form.Item name="end_date" label="结束日期">
            <Input placeholder="2026-12-31" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={editingProject ? `编辑项目：${editingProject.name}` : '编辑项目'}
        open={editOpen}
        onOk={handleUpdateProject}
        onCancel={() => {
          setEditOpen(false)
          setEditingProject(null)
          editForm.resetFields()
        }}
        okText="保存"
        cancelText="取消"
      >
        <Form form={editForm} layout="vertical">
          <Form.Item name="team_id" label="所属团队" rules={[{ required: true, message: '请选择团队' }]}> 
            <Select
              options={teams.map((team) => ({ value: team.id, label: team.name }))}
              placeholder={teams.length ? '请选择团队' : '请先在团队管理中创建团队'}
            />
          </Form.Item>
          <Form.Item name="name" label="项目名称" rules={[{ required: true, message: '请输入项目名称' }]}> 
            <Input placeholder="例如：XX公司2026年度审计" />
          </Form.Item>
          <Form.Item name="project_type" label="项目类型">
            <Select
              options={[
                { value: 'audit', label: '审计项目' },
                { value: 'accounting', label: '核算项目' },
                { value: 'tax', label: '税务项目' },
              ]}
            />
          </Form.Item>
          <Form.Item name="status" label="项目状态">
            <Select
              options={[
                { value: 'active', label: '进行中' },
                { value: 'draft', label: '草稿' },
                { value: 'paused', label: '已暂停' },
                { value: 'completed', label: '已完成' },
                { value: 'cancelled', label: '已取消' },
              ]}
            />
          </Form.Item>
          <Form.Item name="ledger_ids" label="绑定账簿">
            <Select
              mode="multiple"
              allowClear
              placeholder={ledgers.length ? '请选择项目要绑定的账簿' : '暂无可绑定账簿'}
              options={ledgers.map((ledger) => ({ value: ledger.id, label: ledger.name }))}
            />
          </Form.Item>
          <Alert
            type="warning"
            showIcon
            style={{ marginBottom: 16 }}
            message="调整项目账簿绑定会影响审计工作台下拉清单和后续资料归集范围。"
          />
          <Form.Item name="start_date" label="开始日期">
            <Input placeholder="2026-01-01" />
          </Form.Item>
          <Form.Item name="end_date" label="结束日期">
            <Input placeholder="2026-12-31" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={reasonModal.title}
        open={reasonModal.open}
        onOk={confirmAction}
        onCancel={() => {
          setReasonModal({ open: false, projectId: null, action: '', title: '' })
          setReason('')
        }}
        okText="确认"
        cancelText="取消"
      >
        <p>请填写操作原因（可选）：</p>
        <Input.TextArea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="例如：客户要求暂停审计工作..."
          rows={3}
        />
      </Modal>
    </div>
  )
}
