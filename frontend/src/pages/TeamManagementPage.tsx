import { useEffect, useState, useMemo } from 'react'
import {
  Button, Card, Col, Form, Input, message, Modal, Row, Select, Space, Table, Tag, Typography, Empty, Alert, Spin, Steps, Tooltip, Dropdown
} from 'antd'
import {
  PlusOutlined, TeamOutlined, UserAddOutlined, MoreOutlined, UserOutlined, BookOutlined, SettingOutlined,
  ArrowRightOutlined, SafetyCertificateOutlined, LockOutlined, AuditOutlined, CheckCircleOutlined, LoadingOutlined, EditOutlined
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useAuthStore } from '../stores/authStore'
import type { BindingOptions, BindingRequest, Team, TeamMember } from '../api/client'

const { Title, Paragraph, Text } = Typography

const teamTypeLabelMap: Record<string, string> = {
  firm: '会计师事务所/服务团队',
  company: '企业财务团队',
  personal: '个人团队',
}

const teamTypeColorMap: Record<string, string> = {
  firm: 'purple',
  company: 'blue',
  personal: 'green',
}

const requestRoleLabelMap: Record<string, string> = {
  viewer: '查看',
  accountant: '记账',
  admin: '管理',
}

const requestStatusMap: Record<string, { label: string; color: string }> = {
  pending: { label: '待审批', color: 'orange' },
  approved: { label: '已通过', color: 'green' },
  rejected: { label: '已驳回', color: 'red' },
}

  // 缺少绑定项的图标映射
  const missingBindingIconMap: Record<string, React.ReactNode> = {
    team: <TeamOutlined />,
    ledger: <BookOutlined />,
    project: <AuditOutlined />,
    accounting_entity: <SafetyCertificateOutlined />,
  }

  // 缺少绑定项的中文标签
  const missingBindingLabelMap: Record<string, string> = {
    team: '团队',
    ledger: '账套',
    project: '项目',
    accounting_entity: '会计主体',
  }

export function TeamManagementPage() {
  const navigate = useNavigate()
  const { authContext } = useAuthStore()
  const [teams, setTeams] = useState<Team[]>([])
  const [members, setMembers] = useState<TeamMember[]>([])
  const [selectedTeamId, setSelectedTeamId] = useState<number | null>(null)
  const [bindingOptions, setBindingOptions] = useState<BindingOptions>({ teams: [], ledgers: [], projects: [] })
  const [myRequests, setMyRequests] = useState<BindingRequest[]>([])
  const [reviewableRequests, setReviewableRequests] = useState<BindingRequest[]>([])
  const [loading, setLoading] = useState(false)
  const [membersLoading, setMembersLoading] = useState(false)
  const [requestsLoading, setRequestsLoading] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [addMemberOpen, setAddMemberOpen] = useState(false)
  const [requestOpen, setRequestOpen] = useState(false)
  const [reviewComment, setReviewComment] = useState('')
  const [createForm] = Form.useForm()
  const [memberForm] = Form.useForm()
  const [requestForm] = Form.useForm()

  const selectedTeam = teams.find((team) => team.id === selectedTeamId) || null
  const isGuest = authContext?.temporary_status === 'onboarding_pending' && authContext.missing_bindings.includes('team')

  const loadTeams = () => {
    setLoading(true)
    api
      .listTeams()
      .then((res) => {
        setTeams(res)
        if (!selectedTeamId && res.length > 0) {
          setSelectedTeamId(res[0].id)
        }
      })
      .catch(() => message.error('加载团队列表失败'))
      .finally(() => setLoading(false))
  }

  const loadMembers = (teamId: number) => {
    setMembersLoading(true)
    api
      .getTeamMembers(teamId)
      .then((res) => setMembers(res))
      .catch(() => message.error('加载团队成员失败'))
      .finally(() => setMembersLoading(false))
  }

  const loadBindingRequests = () => {
    setRequestsLoading(true)
    Promise.all([
      api.listMyBindingRequests(),
      api.listReviewableBindingRequests(),
    ])
      .then(([mine, reviewable]) => {
        setMyRequests(mine)
        setReviewableRequests(reviewable)
      })
      .catch(() => message.error('加载绑定申请失败'))
      .finally(() => setRequestsLoading(false))
  }

  const loadBindingOptions = (teamId?: number) => {
    api
      .getBindingOptions(teamId)
      .then((res) => setBindingOptions(res))
      .catch(() => message.error('加载可申请对象失败'))
  }

  useEffect(() => {
    loadTeams()
    loadBindingRequests()
    loadBindingOptions()
  }, [])

  useEffect(() => {
    if (selectedTeamId) {
      loadMembers(selectedTeamId)
    } else {
      setMembers([])
    }
  }, [selectedTeamId])

  const handleCreateTeam = async () => {
    const values = await createForm.validateFields()
    try {
      await api.createTeam(values)
      message.success('团队创建成功')
      setCreateOpen(false)
      createForm.resetFields()
      loadTeams()
    } catch (error: any) {
      message.error(error.message || '团队创建失败')
    }
  }

  const handleAddMember = async () => {
    if (!selectedTeamId) return
    const values = await memberForm.validateFields()
    const payload = {
      user_id: values.user_id ? Number(values.user_id) : undefined,
      username: values.username || undefined,
      phone: values.phone || undefined,
      role: values.role || 'member',
    }
    try {
      await api.addTeamMember(selectedTeamId, payload)
      message.success('成员添加成功')
      setAddMemberOpen(false)
      memberForm.resetFields()
      loadMembers(selectedTeamId)
    } catch (error: any) {
      message.error(error.message || '成员添加失败')
    }
  }

  const handleCreateBindingRequest = async () => {
    const values = await requestForm.validateFields()
    try {
      await api.createBindingRequest({
        team_id: values.team_id,
        ledger_id: values.ledger_id || null,
        project_id: values.project_id || null,
        requested_role: values.requested_role,
        reason: values.reason || null,
      })
      message.success('绑定申请已提交，等待管理员审批')
      setRequestOpen(false)
      requestForm.resetFields()
      loadBindingRequests()
    } catch (error: any) {
      message.error(error.message || '提交绑定申请失败')
    }
  }

  const handleReviewBindingRequest = async (requestId: number, action: 'approve' | 'reject') => {
    try {
      if (action === 'approve') {
        await api.approveBindingRequest(requestId, reviewComment || null)
        message.success('已审批通过，系统已写入授权关系')
      } else {
        await api.rejectBindingRequest(requestId, reviewComment || null)
        message.success('已驳回申请')
      }
      setReviewComment('')
      loadBindingRequests()
    } catch (error: any) {
      message.error(error.message || '处理绑定申请失败')
    }
  }

  const TeamCard = ({ team, onSelect }: { team: Team; onSelect: () => void }) => {
    const isSelected = selectedTeamId === team.id
    const menuItems = [
      { key: 'members', label: '查看成员', icon: <UserOutlined />, onClick: () => setSelectedTeamId(team.id) },
      { key: 'add', label: '添加成员', icon: <UserAddOutlined />, onClick: () => { setSelectedTeamId(team.id); setAddMemberOpen(true) } },
    ]
    return (
      <Card
        hoverable
        onClick={onSelect}
        style={{
          cursor: 'pointer',
          border: isSelected ? '2px solid #1890ff' : '1px solid #f0f0f0',
          borderRadius: 8,
          transition: 'all 0.3s',
        }}
        styles={{ body: { padding: 16 } }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Tag color={teamTypeColorMap[team.type] || 'blue'}>
            {teamTypeLabelMap[team.type] || team.type}
          </Tag>
          <Dropdown menu={{ items: menuItems }} trigger={['click']}>
            <Button type="text" icon={<MoreOutlined />} onClick={(e) => e.stopPropagation()} />
          </Dropdown>
        </div>
        <Title level={5} style={{ margin: '8px 0' }}>
          {team.name}
        </Title>
        <Space size="large" style={{ fontSize: 12, color: '#666' }}>
          <span><UserOutlined /> {team.member_count ?? '-'} 人</span>
          <span><BookOutlined /> {team.ledger_count ?? '-'} 账套</span>
        </Space>
        <div>
          <Text type="secondary" style={{ fontSize: 12 }}>
            创建时间：{team.created_at ? new Date(team.created_at).toLocaleDateString() : '-'}
          </Text>
        </div>
      </Card>
    )
  }

  const memberColumns = [
    { title: '用户ID', dataIndex: 'id', key: 'id' },
    { title: '用户名', dataIndex: 'username', key: 'username', render: (value: string | null) => value || '-' },
    { title: '手机号', dataIndex: 'phone', key: 'phone', render: (value: string | null) => value || '-' },
    { title: '邮箱', dataIndex: 'email', key: 'email', render: (value: string | null) => value || '-' },
  ]

  const bindingRequestColumns = [
    { title: '团队', dataIndex: 'team_name', key: 'team_name', render: (value: string | null) => value || '-' },
    { title: '账套', dataIndex: 'ledger_name', key: 'ledger_name', render: (value: string | null) => value || '-' },
    { title: '项目', dataIndex: 'project_name', key: 'project_name', render: (value: string | null) => value || '-' },
    {
      title: '申请角色',
      dataIndex: 'requested_role',
      key: 'requested_role',
      render: (value: string) => <Tag color="blue">{requestRoleLabelMap[value] || value}</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (value: string) => {
        const statusConfig = requestStatusMap[value] || { label: value, color: 'default' }
        return <Tag color={statusConfig.color}>{statusConfig.label}</Tag>
      },
    },
    { title: '申请说明', dataIndex: 'reason', key: 'reason', render: (value: string | null) => value || '-' },
  ]

  const reviewColumns = [
    { title: '申请人', dataIndex: 'requester_name', key: 'requester_name', render: (value: string | null, record: BindingRequest) => value || record.requester_phone || record.requester_user_id },
    ...bindingRequestColumns,
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, record: BindingRequest) => (
        record.status === 'pending' ? (
          <Space>
            <Button type="link" onClick={() => handleReviewBindingRequest(record.id, 'approve')}>通过</Button>
            <Button type="link" danger onClick={() => handleReviewBindingRequest(record.id, 'reject')}>驳回</Button>
          </Space>
        ) : '-'
      ),
    },
  ]

  // 计算当前申请进度步骤
  const currentStep = useMemo(() => {
    if (!authContext) return 0
    const { missing_bindings } = authContext
    if (missing_bindings.includes('team')) return 0
    if (missing_bindings.includes('ledger')) return 1
    if (missing_bindings.includes('project')) return 2
    if (missing_bindings.includes('accounting_entity')) return 3
    return 4
  }, [authContext])

  return (
    <div>
      {isGuest && authContext && (
        <Alert
          title={
            <Space>
              <LockOutlined />
              <Text strong>您当前是访客身份，需要完成授权才能访问系统数据</Text>
            </Space>
          }
          description={
            <div>
              <Steps
                current={currentStep}
                size="small"
                style={{ marginBottom: 16 }}
                items={[
                  { title: '申请团队', icon: currentStep > 0 ? <CheckCircleOutlined /> : <TeamOutlined /> },
                  { title: '申请账套', icon: currentStep > 1 ? <CheckCircleOutlined /> : currentStep === 1 ? <LoadingOutlined /> : <BookOutlined /> },
                  { title: '申请项目', icon: currentStep > 2 ? <CheckCircleOutlined /> : currentStep === 2 ? <LoadingOutlined /> : <AuditOutlined /> },
                ]}
              />
              <Paragraph type="secondary" style={{ marginBottom: 12 }}>
                请选择以下操作获取访问权限：
              </Paragraph>
              <Row gutter={[12, 8]}>
                <Col xs={24} sm={8}>
                  <Card
                    size="small"
                    hoverable
                    onClick={() => setRequestOpen(true)}
                    style={{ textAlign: 'center', cursor: 'pointer' }}
                    bodyStyle={{ padding: 16 }}
                  >
                    <TeamOutlined style={{ fontSize: 24, color: '#1890ff', marginBottom: 8 }} />
                    <div style={{ fontWeight: 500 }}>申请加入团队</div>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      向管理员申请加入现有团队
                    </Text>
                  </Card>
                </Col>
                <Col xs={24} sm={8}>
                  <Card
                    size="small"
                    hoverable
                    onClick={() => setCreateOpen(true)}
                    style={{ textAlign: 'center', cursor: 'pointer' }}
                    bodyStyle={{ padding: 16 }}
                  >
                    <PlusOutlined style={{ fontSize: 24, color: '#52c41a', marginBottom: 8 }} />
                    <div style={{ fontWeight: 500 }}>创建新团队</div>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      自己创建团队，成为管理员
                    </Text>
                  </Card>
                </Col>
                <Col xs={24} sm={8}>
                  <Card
                    size="small"
                    style={{ textAlign: 'center', background: '#fafafa' }}
                    bodyStyle={{ padding: 16 }}
                  >
                    <SafetyCertificateOutlined style={{ fontSize: 24, color: '#faad14', marginBottom: 8 }} />
                    <div style={{ fontWeight: 500 }}>等待审批</div>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      已有 {myRequests.filter(r => r.status === 'pending').length} 个申请待审批
                    </Text>
                  </Card>
                </Col>
              </Row>
              {authContext.missing_bindings.length > 0 && (
                <div style={{ marginTop: 12 }}>
                  <Text type="secondary">缺少授权项：</Text>
                  <Space wrap style={{ marginTop: 4 }}>
                    {authContext.missing_bindings.map((key) => (
                      <Tag key={key} icon={missingBindingIconMap[key]} color="orange">
                        {missingBindingLabelMap[key] || key}
                      </Tag>
                    ))}
                  </Space>
                </div>
              )}
            </div>
          }
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Title level={4} style={{ margin: 0 }}>
            <TeamOutlined /> 团队管理
          </Title>
          <Paragraph type="secondary">团队用于归集人员、账套和项目，是权限隔离的基础。</Paragraph>
        </Col>
        <Col>
          <Space>
            <Button onClick={() => navigate('/scope-settings?tab=team')}>管理配置</Button>
            <Button icon={<SafetyCertificateOutlined />} onClick={() => setRequestOpen(true)}>
              申请授权
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
              创建团队
            </Button>
          </Space>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card 
            title={<span><TeamOutlined /> 团队列表</span>}
            extra={<span style={{ fontSize: 12, color: '#999' }}>共 {teams.length} 个团队</span>}
          >
            {teams.length === 0 ? (
              <Empty 
                description="暂无团队" 
                image={Empty.PRESENTED_IMAGE_SIMPLE}
              >
                <Button type="primary" onClick={() => setCreateOpen(true)}>
                  创建第一个团队
                </Button>
              </Empty>
            ) : (
              <Row gutter={[12, 12]}>
                {teams.map((team) => (
                  <Col xs={24} sm={12} key={team.id}>
                    <TeamCard
                      team={team}
                      onSelect={() => setSelectedTeamId(team.id)}
                    />
                  </Col>
                ))}
              </Row>
            )}
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card
            title={selectedTeam ? <><UserOutlined /> {selectedTeam.name} - 成员</> : <><UserOutlined /> 团队成员</>}
            extra={(
              <Button
                type="primary"
                ghost
                icon={<UserAddOutlined />}
                disabled={!selectedTeamId}
                onClick={() => setAddMemberOpen(true)}
              >
                添加成员
              </Button>
            )}
          >
            {!selectedTeamId ? (
              <Empty description="请先选择一个团队" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ) : members.length === 0 ? (
              <Empty description="暂无成员" image={Empty.PRESENTED_IMAGE_SIMPLE}>
                <Button type="primary" ghost onClick={() => setAddMemberOpen(true)}>
                  添加成员
                </Button>
              </Empty>
            ) : (
              <Table
                rowKey="id"
                columns={memberColumns}
                dataSource={members}
                loading={membersLoading}
                pagination={false}
                locale={{ emptyText: '暂无成员' }}
              />
            )}
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={12}>
          <Card title="我的绑定申请">
            <Table
              rowKey="id"
              columns={bindingRequestColumns}
              dataSource={myRequests}
              loading={requestsLoading}
              pagination={false}
              locale={{ emptyText: '暂无绑定申请' }}
            />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="待我审批的绑定申请">
            <Input.TextArea
              rows={2}
              value={reviewComment}
              onChange={(event) => setReviewComment(event.target.value)}
              placeholder="审批意见，可选"
              style={{ marginBottom: 12 }}
            />
            <Table
              rowKey="id"
              columns={reviewColumns}
              dataSource={reviewableRequests}
              loading={requestsLoading}
              pagination={false}
              locale={{ emptyText: '暂无待审批申请' }}
            />
          </Card>
        </Col>
      </Row>

      <Modal
        title="创建团队"
        open={createOpen}
        onOk={handleCreateTeam}
        onCancel={() => setCreateOpen(false)}
        okText="创建"
        cancelText="取消"
      >
        <Form form={createForm} layout="vertical" initialValues={{ type: 'company' }}>
          <Form.Item name="name" label="团队名称" rules={[{ required: true, message: '请输入团队名称' }]}>
            <Input placeholder="例如：XX公司财务部" />
          </Form.Item>
          <Form.Item name="type" label="团队类型" rules={[{ required: true, message: '请选择团队类型' }]}>
            <Select
              options={[
                { value: 'company', label: '企业财务团队' },
                { value: 'firm', label: '会计师事务所/服务团队' },
                { value: 'personal', label: '个人团队' },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={
          <Space>
            <SafetyCertificateOutlined />
            <span>申请授权（团队 / 账套 / 项目）</span>
          </Space>
        }
        open={requestOpen}
        onOk={handleCreateBindingRequest}
        onCancel={() => setRequestOpen(false)}
        okText="提交申请"
        cancelText="取消"
        width={560}
      >
        <Form form={requestForm} layout="vertical" initialValues={{ requested_role: 'viewer' }}>
          <Alert
            title="授权说明"
            description={
              <ul style={{ margin: '8px 0', paddingLeft: 20 }}>
                <li>选择团队是必选项，申请后将成为该团队的成员</li>
                <li>账套和项目为可选项，可同时申请或稍后单独申请</li>
                <li>审批通过后会自动写入对应的访问权限</li>
              </ul>
            }
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
          />
          <Form.Item
            name="team_id"
            label={<Space><TeamOutlined /> 申请加入团队 <Text type="danger">*</Text></Space>}
            rules={[{ required: true, message: '请选择要申请的团队' }]}
          >
            <Select
              showSearch
              placeholder="请先选择团队"
              optionFilterProp="label"
              loading={loading}
              options={bindingOptions.teams.map((team) => ({ value: team.id, label: team.name }))}
              onChange={(teamId) => {
                requestForm.setFieldsValue({ ledger_id: undefined, project_id: undefined })
                loadBindingOptions(teamId)
              }}
            />
          </Form.Item>
          <Form.Item
            name="ledger_id"
            label={<Space><BookOutlined /> 申请访问账套</Space>}
            tooltip="选择后获将得该账套的访问权限"
          >
            <Select
              allowClear
              showSearch
              placeholder={bindingOptions.ledgers.length > 0 ? "请选择账套（可选）" : "请先选择团队"}
              optionFilterProp="label"
              disabled={!requestForm.getFieldValue('team_id')}
              options={bindingOptions.ledgers.map((ledger) => ({ value: ledger.id, label: ledger.name }))}
            />
          </Form.Item>
          <Form.Item
            name="project_id"
            label={<Space><AuditOutlined /> 申请关联项目</Space>}
            tooltip="选择后将获得该项目的参与权限"
          >
            <Select
              allowClear
              showSearch
              placeholder={bindingOptions.projects.length > 0 ? "请选择项目（可选）" : "请先选择团队"}
              optionFilterProp="label"
              disabled={!requestForm.getFieldValue('team_id')}
              options={bindingOptions.projects.map((project) => ({ value: project.id, label: project.name }))}
            />
          </Form.Item>
          <Form.Item
            name="requested_role"
            label={<Space><LockOutlined /> 申请角色 <Text type="danger">*</Text></Space>}
            rules={[{ required: true, message: '请选择申请角色' }]}
          >
            <Select
              options={[
                { value: 'viewer', label: '查看 - 仅查看数据，不能修改' },
                { value: 'accountant', label: '记账 - 可录入和修改账务数据' },
                { value: 'admin', label: '管理 - 完整访问和管理权限' },
              ]}
            />
          </Form.Item>
          <Form.Item name="reason" label="申请说明">
            <Input.TextArea
              rows={3}
              placeholder="请简要说明申请原因，例如：我是本项目记账人员，需要访问该账套处理本期凭证。"
              showCount
              maxLength={200}
            />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="添加团队成员"
        open={addMemberOpen}
        onOk={handleAddMember}
        onCancel={() => setAddMemberOpen(false)}
        okText="添加"
        cancelText="取消"
      >
        <Form form={memberForm} layout="vertical" initialValues={{ role: 'member' }}>
          <Paragraph type="secondary">可填写用户ID、用户名或手机号中的任意一项。</Paragraph>
          <Form.Item name="user_id" label="用户ID">
            <Input placeholder="已知用户ID时填写" />
          </Form.Item>
          <Space style={{ width: '100%' }} size="middle">
            <Form.Item name="username" label="用户名" style={{ flex: 1 }}>
              <Input placeholder="用户名" />
            </Form.Item>
            <Form.Item name="phone" label="手机号" style={{ flex: 1 }}>
              <Input placeholder="手机号" />
            </Form.Item>
          </Space>
          <Form.Item name="role" label="团队角色">
            <Select
              options={[
                { value: 'member', label: '普通成员' },
                { value: 'admin', label: '管理员' },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
