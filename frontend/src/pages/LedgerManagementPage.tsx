import { useEffect, useState } from 'react'
import { Button, Card, Col, DatePicker, Form, Input, message, Modal, Row, Select, Space, Table, Tag, Typography, Empty, Dropdown, Badge } from 'antd'
import dayjs from 'dayjs'
import { useNavigate } from 'react-router-dom'
import { BookOutlined, PlusOutlined, SafetyOutlined, MoreOutlined, FolderOpenOutlined, EditOutlined, ExclamationCircleOutlined, DeleteOutlined, ReloadOutlined } from '@ant-design/icons'
import { api } from '../api/client'
import type { Ledger, LedgerAuth, Project, Team } from '../api/client'
import { useAuthStore } from '../stores/authStore'

const { Title, Paragraph, Text } = Typography

type AccountingEntityOption = {
  id: number
  entity_name: string
  entity_code?: string | null
  ledger_id?: number | null
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

async function requestWithToken<T>(path: string, options?: RequestInit): Promise<T> {
  const token = localStorage.getItem('token')
  const headers: Record<string, string> = {
    ...(options?.headers as Record<string, string> || {}),
  }
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers })
  if (!response.ok) {
    throw new Error(await response.text())
  }
  return response.json()
}

const ledgerStatusColorMap: Record<string, string> = {
  draft: 'default',
  active: 'success',
  suspended: 'warning',
  archived: 'error',
  deleted: 'red',
}

const ledgerStatusLabelMap: Record<string, string> = {
  draft: '草稿',
  active: '活跃',
  suspended: '暂停',
  archived: '归档',
  deleted: '删除',
}

const ledgerStatusBorderMap: Record<string, string> = {
  draft: '#d9d9d9',
  active: '#52c41a',
  suspended: '#faad14',
  archived: '#ff4d4f',
  deleted: '#ff4d4f',
}

const ledgerRoleLabelMap: Record<string, string> = {
  admin: '管理员',
  accountant: '会计',
  auditor: '审计',
  viewer: '只读查看',
}

const lifecycleActionMap: Record<string, { label: string; nextStatus: string; danger?: boolean }> = {
  activate: { label: '激活', nextStatus: 'active' },
  suspend: { label: '暂停', nextStatus: 'suspended' },
  archive: { label: '归档', nextStatus: 'archived', danger: true },
  restore: { label: '恢复', nextStatus: 'active' },
}

function getAvailableActions(status: string) {
  switch (status) {
    case 'draft':
      return ['activate']
    case 'active':
      return ['suspend', 'archive']
    case 'suspended':
      return ['activate', 'archive']
    case 'archived':
      return ['restore']
    default:
      return []
  }
}

// 状态筛选
const statusFilters = [
  { key: 'all', label: '全部' },
  { key: 'active', label: '活跃' },
  { key: 'suspended', label: '暂停' },
  { key: 'archived', label: '归档' },
  { key: 'deleted', label: '已删除' },
]

export function LedgerManagementPage() {
  const navigate = useNavigate()
  const { setUserLedgers, setCurrentLedger, refreshAuthContext, currentLedgerId } = useAuthStore()
  const [teams, setTeams] = useState<Team[]>([])
  const [ledgers, setLedgers] = useState<Ledger[]>([])
  const [projects, setProjects] = useState<Project[]>([])
  const [accountingEntities, setAccountingEntities] = useState<AccountingEntityOption[]>([])
  const [auths, setAuths] = useState<LedgerAuth[]>([])
  const [selectedLedgerId, setSelectedLedgerId] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [authLoading, setAuthLoading] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [editOpen, setEditOpen] = useState(false)
  const [editingLedger, setEditingLedger] = useState<Ledger | null>(null)
  const [grantOpen, setGrantOpen] = useState(false)
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [reasonModal, setReasonModal] = useState<{
    open: boolean
    ledgerId: number | null
    action: string
    title: string
  }>({ open: false, ledgerId: null, action: '', title: '' })
  const [reason, setReason] = useState('')
  const [createForm] = Form.useForm()
  const [editForm] = Form.useForm()
  const [grantForm] = Form.useForm()
  const selectedCreateTeamId = Form.useWatch('team_id', createForm)

  const selectedLedger = ledgers.find((ledger) => ledger.id === selectedLedgerId) || null
  const filteredLedgers = statusFilter === 'all'
    ? ledgers.filter((ledger) => ledger.status !== 'deleted')
    : ledgers.filter((ledger) => ledger.status === statusFilter)

  const loadBaseData = () => {
    setLoading(true)
    Promise.all([
      api.listTeams(),
      api.listLedgers(),
      api.listProjects(),
      requestWithToken<AccountingEntityOption[]>('/api/entities?accounting_entity=true'),
    ])
      .then(([teamRes, ledgerRes, projectRes, entityRes]) => {
        setTeams(teamRes)
        setLedgers(ledgerRes)
        setProjects(projectRes)
        setAccountingEntities(entityRes)
        setUserLedgers(ledgerRes)
        if (!selectedLedgerId && ledgerRes.length > 0) {
          setSelectedLedgerId(ledgerRes[0].id)
        }
      })
      .catch(() => message.error('加载账簿管理数据失败'))
      .finally(() => setLoading(false))
  }

  const loadAuths = (ledgerId: number) => {
    setAuthLoading(true)
    api
      .getLedgerAuths(ledgerId)
      .then((res) => setAuths(res))
      .catch(() => message.error('加载账簿授权列表失败'))
      .finally(() => setAuthLoading(false))
  }

  useEffect(() => {
    loadBaseData()
  }, [])

  useEffect(() => {
    if (selectedLedgerId) {
      loadAuths(selectedLedgerId)
    } else {
      setAuths([])
    }
  }, [selectedLedgerId])

  const handleCreateLedger = async () => {
    const values = await createForm.validateFields()
    const selectedEntity = accountingEntities.find((entity) => entity.id === values.existing_entity_id)
    try {
      const ledger = await api.createLedger({
        team_id: values.team_id,
        name: values.name,
        accounting_start_date: values.accounting_start_date
          ? dayjs(values.accounting_start_date).format('YYYY-MM-DD')
          : undefined,
      })
      if (values.project_id) {
        await requestWithToken(`/api/projects/${values.project_id}/ledgers`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ledger_id: ledger.id }),
        })
      }
      await api.createEntity({
        entity_name: selectedEntity?.entity_name || values.entity_name || values.name,
        entity_code: selectedEntity?.entity_code || values.entity_code || null,
        ledger_id: ledger.id,
        entity_type: 'company',
        entity_category: 'parent',
        is_accounting_entity: true,
        is_legal_entity: true,
      })
      message.success(values.project_id ? '账簿、项目关系和会计主体创建成功' : '账簿和会计主体创建成功')
      setCreateOpen(false)
      createForm.resetFields()
      setSelectedLedgerId(ledger.id)
      await api.switchLedger(ledger.id)
      setCurrentLedger(ledger.id)
      await refreshAuthContext()
      loadBaseData()
    } catch (error: any) {
      message.error(error.message || '账簿创建失败')
    }
  }

  const handleExistingEntityChange = (entityId: number | undefined) => {
    const selectedEntity = accountingEntities.find((entity) => entity.id === entityId)
    if (!selectedEntity) return
    createForm.setFieldsValue({
      entity_name: selectedEntity.entity_name,
      entity_code: selectedEntity.entity_code || undefined,
    })
  }

  const handleLifecycleAction = (ledgerId: number, action: string) => {
    const actionConfig = lifecycleActionMap[action]
    setReasonModal({ open: true, ledgerId, action, title: actionConfig?.label || action })
  }

  const confirmLifecycleAction = async () => {
    if (!reasonModal.ledgerId || !reasonModal.action) return
    try {
      const updated = await api.updateLedgerLifecycle(reasonModal.ledgerId, reasonModal.action, reason)
      setLedgers((prev) => prev.map((ledger) => (ledger.id === updated.id ? { ...ledger, ...updated } : ledger)))
      message.success(`${reasonModal.title}账簿成功`)
    } catch (error: any) {
      message.error(`${reasonModal.title}账簿失败：${error.message}`)
    } finally {
      setReasonModal({ open: false, ledgerId: null, action: '', title: '' })
      setReason('')
    }
  }

  const handleGrantAuth = async () => {
    if (!selectedLedgerId) return
    const values = await grantForm.validateFields()
    const identifier = String(values.identifier || '').trim()
    const payload =
      /^1\d{10}$/.test(identifier)
        ? { phone: identifier, role: values.role as string }
        : { username: identifier, role: values.role as string }
    try {
      await api.grantLedgerAuth(selectedLedgerId, payload)
      message.success('账簿授权成功')
      setGrantOpen(false)
      grantForm.resetFields()
      loadAuths(selectedLedgerId)
    } catch (error: any) {
      message.error(error.message || '账簿授权失败')
    }
  }

  const handleRevokeAuth = async (authId: number) => {
    if (!selectedLedgerId) return
    try {
      await api.revokeLedgerAuth(selectedLedgerId, authId)
      message.success('账簿授权已撤销')
      loadAuths(selectedLedgerId)
    } catch (error: any) {
      message.error(error.message || '撤销授权失败')
    }
  }

  const handleEnterLedgerFiles = async (ledgerId: number) => {
    try {
      await api.switchLedger(ledgerId)
      setCurrentLedger(ledgerId)
      navigate('/ledger/files')
    } catch (error: any) {
      message.error(error.message || '切换账簿失败')
    }
  }

  const openEditLedger = (ledger: Ledger) => {
    setEditingLedger(ledger)
    editForm.setFieldsValue({
      name: ledger.name,
      accounting_start_date: ledger.accounting_start_date ? dayjs(ledger.accounting_start_date) : undefined,
    })
    setEditOpen(true)
  }

  const handleUpdateLedger = async () => {
    if (!editingLedger) return
    const values = await editForm.validateFields()
    try {
      const updated = await api.updateLedger(editingLedger.id, {
        name: values.name,
        accounting_start_date: values.accounting_start_date
          ? dayjs(values.accounting_start_date).format('YYYY-MM-DD')
          : undefined,
      })
      message.success('账簿已更新')
      setEditOpen(false)
      setEditingLedger(null)
      editForm.resetFields()
      setLedgers((prev) => prev.map((item) => (item.id === updated.id ? { ...item, ...updated } : item)))
      await refreshAuthContext()
      loadBaseData()
    } catch (error: any) {
      message.error(error.message || '账簿更新失败')
    }
  }

  const handleDeleteLedger = (ledger: Ledger) => {
    Modal.confirm({
      title: `删除账簿「${ledger.name}」？`,
      icon: <ExclamationCircleOutlined />,
      content: '硬删除不可恢复：账簿及其凭证、分录、导入记录等关联数据将被永久清除。仅账簿管理员可执行。',
      okText: '确认删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await api.deleteLedger(ledger.id, '用户在账簿管理中删除')
          message.success('账簿已永久删除')
          if (selectedLedgerId === ledger.id) {
            setSelectedLedgerId(null)
          }
          if (currentLedgerId === ledger.id) {
            setCurrentLedger(null)
          }
          setLedgers((prev) => prev.filter((item) => item.id !== ledger.id))
          await refreshAuthContext()
          loadBaseData()
        } catch (error: any) {
          message.error(error.message || '删除账簿失败')
        }
      },
    })
  }

  const handleInitializeLedger = (ledger: Ledger) => {
    Modal.confirm({
      title: `初始化账簿「${ledger.name}」？`,
      icon: <ExclamationCircleOutlined />,
      content:
        '将永久删除该账簿内全部凭证及分录，使业务数据回到账套创建时的空白状态。科目表、会计期间、授权与账簿设置保持不变。此操作不可撤销。',
      okText: '确认初始化',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          const result = await api.initializeLedger(ledger.id, '用户在账簿管理中初始化')
          const voucherMsg =
            result.deleted_vouchers > 0
              ? `已删除 ${result.deleted_vouchers} 张凭证、${result.deleted_entries} 条分录`
              : '账簿内暂无凭证，已完成初始化'
          message.success(voucherMsg)
          await refreshAuthContext()
        } catch (error: any) {
          message.error(error.message || '初始化账簿失败')
        }
      },
    })
  }

  const filteredProjects = projects.filter((project) => !selectedCreateTeamId || !project.team_id || project.team_id === selectedCreateTeamId)

  // 账簿卡片组件
  const LedgerCard = ({ ledger }: { ledger: Ledger }) => {
    const isSelected = selectedLedgerId === ledger.id
    const borderColor = ledgerStatusBorderMap[ledger.status] || '#d9d9d9'
    const team = teams.find(t => t.id === ledger.team_id)
    const availableActions = getAvailableActions(ledger.status)
    
    const isAdmin = ledger.role === 'admin'
    const canManage = isAdmin && ledger.status !== 'deleted'

    const menuItems = [
      ...availableActions.map(action => ({
        key: action,
        label: lifecycleActionMap[action]?.label || action,
        danger: lifecycleActionMap[action]?.danger,
        onClick: () => handleLifecycleAction(ledger.id, action),
      })),
      ...(canManage
        ? [
            { type: 'divider' as const },
            {
              key: 'edit',
              label: '编辑账簿',
              icon: <EditOutlined />,
              onClick: () => openEditLedger(ledger),
            },
            {
              key: 'initialize',
              label: '初始化账簿',
              icon: <ReloadOutlined />,
              danger: true,
              onClick: () => handleInitializeLedger(ledger),
            },
            {
              key: 'delete',
              label: '删除账簿',
              icon: <DeleteOutlined />,
              danger: true,
              onClick: () => handleDeleteLedger(ledger),
            },
          ]
        : []),
    ]
    
    return (
      <Card
        hoverable
        onClick={() => setSelectedLedgerId(ledger.id)}
        style={{
          cursor: 'pointer',
          border: isSelected ? `2px solid ${borderColor}` : `1px solid ${borderColor}`,
          borderRadius: 8,
          transition: 'all 0.3s',
        }}
        styles={{ body: { padding: 16 } }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
          <Tag color={ledgerStatusColorMap[ledger.status] || 'default'}>
            {ledgerStatusLabelMap[ledger.status] || ledger.status}
          </Tag>
          <Dropdown menu={{ items: menuItems }} trigger={['click']}>
            <Button type="text" icon={<MoreOutlined />} onClick={(e) => e.stopPropagation()} />
          </Dropdown>
        </div>
        
        <Title level={5} style={{ margin: '8px 0' }}>
          {ledger.name}
        </Title>
        
        <div style={{ fontSize: 12, color: '#666', marginBottom: 4 }}>
          <SafetyOutlined style={{ marginRight: 4 }} />
          {team ? team.name : `团队 ${ledger.team_id || ledger.organization_id || '-'}`}
        </div>
        
        {ledger.activated_at && (
          <Text type="secondary" style={{ fontSize: 12 }}>
            激活时间：{new Date(ledger.activated_at).toLocaleDateString()}
          </Text>
        )}
        
        <div style={{ marginTop: 12, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <Button 
            type="primary" 
            ghost 
            size="small" 
            icon={<SafetyOutlined />}
            onClick={(e) => {
              e.stopPropagation()
              setSelectedLedgerId(ledger.id)
            }}
          >
            授权
          </Button>
          {canManage ? (
            <Button
              size="small"
              icon={<EditOutlined />}
              onClick={(e) => {
                e.stopPropagation()
                openEditLedger(ledger)
              }}
            >
              编辑
            </Button>
          ) : null}
          <Button 
            size="small" 
            icon={<FolderOpenOutlined />}
            onClick={(e) => {
              e.stopPropagation()
              handleEnterLedgerFiles(ledger.id)
            }}
            disabled={ledger.status === 'deleted'}
          >
            支持性文件
          </Button>
          {canManage ? (
            <Button
              size="small"
              danger
              icon={<DeleteOutlined />}
              onClick={(e) => {
                e.stopPropagation()
                handleDeleteLedger(ledger)
              }}
            >
              删除
            </Button>
          ) : null}
        </div>
      </Card>
    )
  }

  const authColumns = [
    {
      title: '用户名',
      dataIndex: 'username',
      key: 'username',
      render: (_: string | null | undefined, record: LedgerAuth) => (
        <div>
          <div>{record.username || '—'}</div>
          {record.phone ? (
            <Text type="secondary" style={{ fontSize: 12 }}>
              {record.phone}
            </Text>
          ) : null}
        </div>
      ),
    },
    {
      title: '角色',
      dataIndex: 'role',
      key: 'role',
      render: (value: string) => <Tag color="blue">{ledgerRoleLabelMap[value] || value}</Tag>,
    },
    {
      title: '授权时间',
      dataIndex: 'granted_at',
      key: 'granted_at',
      render: (value: string | null) => value || '-',
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, record: LedgerAuth) => (
        <Button danger type="link" onClick={() => handleRevokeAuth(record.id)}>
          撤销
        </Button>
      ),
    },
  ]

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Title level={4} style={{ margin: 0 }}>
            <BookOutlined /> 账簿管理
          </Title>
          <Paragraph type="secondary">账簿管理是团队、项目、账簿和会计主体的业务范围绑定中心。创建或切换账簿后会同步刷新全局上下文，确保凭证、报表和审计资料落到正确归属。</Paragraph>
        </Col>
        <Col>
          <Space>
            <Button onClick={() => navigate('/scope-settings?tab=ledger')}>管理配置</Button>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => {
                setCreateOpen(true)
                if (teams.length === 1) {
                  createForm.setFieldValue('team_id', teams[0].id)
                }
              }}
            >
              创建账簿
            </Button>
          </Space>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={14}>
          <Card 
            title={<span><BookOutlined /> 账簿列表</span>}
            extra={
              <Space>
                <span style={{ fontSize: 12, color: '#999' }}>共 {filteredLedgers.length} 个账簿</span>
              </Space>
            }
          >
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
            
            {filteredLedgers.length === 0 ? (
              <Empty 
                description={statusFilter === 'all' ? '暂无账簿' : `暂无${statusFilters.find(f => f.key === statusFilter)?.label}的账簿`}
                image={Empty.PRESENTED_IMAGE_SIMPLE}
              >
                <Button type="primary" onClick={() => setCreateOpen(true)}>
                  创建第一个账簿
                </Button>
              </Empty>
            ) : (
              <Row gutter={[12, 12]}>
                {filteredLedgers.map((ledger) => (
                  <Col xs={24} sm={12} md={8} key={ledger.id}>
                    <LedgerCard ledger={ledger} />
                  </Col>
                ))}
              </Row>
            )}
          </Card>
        </Col>
        <Col xs={24} xl={10}>
          <Card
            title={selectedLedger ? <><SafetyOutlined /> {selectedLedger.name} - 授权管理</> : <><SafetyOutlined /> 授权管理</>}
            extra={(
              <Button
                type="primary"
                ghost
                icon={<SafetyOutlined />}
                disabled={!selectedLedgerId}
                onClick={() => setGrantOpen(true)}
              >
                授权用户
              </Button>
            )}
          >
            {!selectedLedgerId ? (
              <Empty description="请先选择一个账簿" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ) : (
              <Table
                rowKey="id"
                columns={authColumns}
                dataSource={auths}
                loading={authLoading}
                pagination={false}
                locale={{ emptyText: '暂无授权记录' }}
              />
            )}
          </Card>
        </Col>
      </Row>

      <Modal
        title="创建账簿"
        open={createOpen}
        onOk={handleCreateLedger}
        onCancel={() => {
          setCreateOpen(false)
          createForm.resetFields()
        }}
        okText="创建"
        cancelText="取消"
      >
        <Paragraph type="secondary">
          按会计建账资料先确认协作团队、工作项目和核算主体；这里不要求审计留痕或底稿复核，只用于明确财务数据归属。
        </Paragraph>
        <Form form={createForm} layout="vertical">
          <Form.Item name="team_id" label="所属团队" rules={[{ required: true, message: '请选择所属团队' }]}>
            <Select
              showSearch
              allowClear
              placeholder={teams.length ? '请选择团队' : '暂无团队，请先在团队管理中创建'}
              optionFilterProp="label"
              notFoundContent="暂无可选团队"
              options={teams.map((team) => ({ value: team.id, label: team.name }))}
            />
          </Form.Item>
          <Form.Item name="project_id" label="所属项目（可选）">
            <Select
              showSearch
              allowClear
              placeholder={filteredProjects.length ? '可选择已有核算/税务/服务项目' : '暂无可选项目，可先不选'}
              optionFilterProp="label"
              notFoundContent="暂无可选项目"
              options={filteredProjects.map((project) => ({
                value: project.id,
                label: `${project.name}（${project.type || project.status}）`,
              }))}
            />
          </Form.Item>
          <Form.Item name="name" label="账簿名称" rules={[{ required: true, message: '请输入账簿名称' }]}>
            <Input placeholder="例如：XX公司2026账簿" />
          </Form.Item>
          <Form.Item
            name="accounting_start_date"
            label="会计时间线起点"
            initialValue={dayjs()}
            tooltip="默认使用创建当天；补建历史账簿时可调整为实际开账月份中的任意日期"
            rules={[{ required: true, message: '请选择会计时间线起点' }]}
          >
            <DatePicker style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="existing_entity_id" label="已有会计主体（可选）">
            <Select
              showSearch
              allowClear
              placeholder={accountingEntities.length ? '可从已有会计主体带入' : '暂无已有主体，请在下方手工填写'}
              optionFilterProp="label"
              notFoundContent="暂无可选会计主体"
              onChange={handleExistingEntityChange}
              options={accountingEntities.map((entity) => ({
                value: entity.id,
                label: entity.entity_code ? `${entity.entity_name}（${entity.entity_code}）` : entity.entity_name,
              }))}
            />
          </Form.Item>
          <Form.Item name="entity_name" label="会计主体名称">
            <Input placeholder="默认使用账簿名称；建议填写真实核算主体名称" />
          </Form.Item>
          <Form.Item name="entity_code" label="统一社会信用代码 / 主体编码">
            <Input placeholder="可选，用于合同、发票、税务资料匹配" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="编辑账簿"
        open={editOpen}
        onOk={handleUpdateLedger}
        onCancel={() => {
          setEditOpen(false)
          setEditingLedger(null)
          editForm.resetFields()
        }}
        okText="保存"
        cancelText="取消"
      >
        <Form form={editForm} layout="vertical">
          <Form.Item name="name" label="账簿名称" rules={[{ required: true, message: '请输入账簿名称' }]}>
            <Input placeholder="账簿名称" />
          </Form.Item>
          <Form.Item
            name="accounting_start_date"
            label="会计时间线起点"
            tooltip="补建历史账簿时可调整；已有期间数据请谨慎修改"
          >
            <DatePicker style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="授权用户访问账簿"
        open={grantOpen}
        onOk={handleGrantAuth}
        onCancel={() => setGrantOpen(false)}
        okText="授权"
        cancelText="取消"
      >
        <Form form={grantForm} layout="vertical" initialValues={{ role: 'viewer' }}>
          <Form.Item
            name="identifier"
            label="用户名或手机号"
            rules={[{ required: true, message: '请输入被授权用户的用户名或手机号' }]}
          >
            <Input placeholder="输入用户名或11位手机号" />
          </Form.Item>
          <Form.Item name="role" label="账簿角色" rules={[{ required: true, message: '请选择账簿角色' }]}>
            <Select
              options={[
                { value: 'admin', label: '管理员' },
                { value: 'accountant', label: '会计' },
                { value: 'auditor', label: '审计' },
                { value: 'viewer', label: '只读查看' },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`${reasonModal.title}账簿`}
        open={reasonModal.open}
        onOk={confirmLifecycleAction}
        onCancel={() => {
          setReasonModal({ open: false, ledgerId: null, action: '', title: '' })
          setReason('')
        }}
        okText="确认"
        cancelText="取消"
      >
        <Paragraph>请填写操作原因（可选），便于后续审计追溯。</Paragraph>
        <Input.TextArea
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          placeholder="例如：客户项目结束，归档账簿"
          rows={3}
        />
      </Modal>
    </div>
  )
}
