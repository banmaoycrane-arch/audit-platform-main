import { useEffect, useState } from 'react'
import { Button, Card, Col, Form, Input, message, Modal, Row, Select, Space, Tag, Typography, Empty, Alert } from 'antd'
import { PlusOutlined, TeamOutlined, UserAddOutlined, MoreOutlined, UserOutlined, BookOutlined, SettingOutlined, ArrowRightOutlined } from '@ant-design/icons'
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

export function TeamManagementPage() {
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

  const teamColumns = [
    { title: '团队名称', dataIndex: 'name', key: 'name' },
    {
      title: '团队类型',
      dataIndex: 'type',
      key: 'type',
      render: (value: string) => <Tag color="blue">{teamTypeLabelMap[value] || value}</Tag>,
    },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at', render: (value: string | null) => value || '-' },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, record: Team) => (
        <Button type="link" onClick={() => setSelectedTeamId(record.id)}>
          查看成员
        </Button>
      ),
    },
  ]

  // 团队卡片组件
  const TeamCard = ({ team, selected, onSelect }: { team: Team; selected: boolean; onSelect: () => void }) => {
    const isSelected = selectedTeamId === team.id
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
        extra={
          <Button
            type="text"
            icon={<MoreOutlined />}
            onClick={(e) => {
              e.stopPropagation()
              setSelectedTeamId(team.id)
            }}
          />
        }
      >
        <div style={{ marginBottom: 12 }}>
          <Tag color={teamTypeColorMap[team.type] || 'blue'} style={{ marginRight: 8 }}>
            {teamTypeLabelMap[team.type] || team.type}
          </Tag>
        </div>
        <Title level={5} style={{ margin: '8px 0' }}>
          {team.name}
        </Title>
        <Text type="secondary" style={{ fontSize: 12 }}>
          创建时间：{team.created_at ? new Date(team.created_at).toLocaleDateString() : '-'}
        </Text>
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

  return (
    <div>
      {isGuest && authContext && (
        <Alert
          message="您当前是访客身份"
          description={
            <div>
              <Text type="secondary">
                您尚未绑定团队，无法查看或管理团队数据。您可以：
              </Text>
              <div style={{ marginTop: 8 }}>
                <Space direction="vertical">
                  <Text type="secondary">
                    <ArrowRightOutlined style={{ marginRight: 8 }} />
                    <Button type="link" onClick={() => setRequestOpen(true)}>申请加入已有团队</Button>
                    <Text> - 向管理员申请加入现有团队，获得数据访问权限</Text>
                  </Text>
                  <Text type="secondary">
                    <ArrowRightOutlined style={{ marginRight: 8 }} />
                    <Button type="link" onClick={() => setCreateOpen(true)}>创建新团队</Button>
                    <Text> - 自己创建团队，成为团队管理员</Text>
                  </Text>
                </Space>
              </div>
              <div style={{ marginTop: 8 }}>
                <Text type="secondary">
                  缺少绑定项：
                  {authContext.missing_bindings.map((key) => {
                    const label = {
                      team: '团队',
                      ledger: '账套',
                      project: '项目',
                      accounting_entity: '会计主体',
                    }[key] || key
                    return <Tag color="orange" key={key}>{label}</Tag>
                  })}
                </Text>
              </div>
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
            <Button onClick={() => setRequestOpen(true)}>
              申请绑定鉴权
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
                      selected={selectedTeamId === team.id}
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
        title="申请绑定鉴权"
        open={requestOpen}
        onOk={handleCreateBindingRequest}
        onCancel={() => setRequestOpen(false)}
        okText="提交申请"
        cancelText="取消"
      >
        <Form form={requestForm} layout="vertical" initialValues={{ requested_role: 'viewer' }}>
          <Paragraph type="secondary">
            提交申请不会立即看到隔离数据，需管理员审批通过后才会写入团队、账套和项目授权关系。
          </Paragraph>
          <Form.Item name="team_id" label="申请加入团队" rules={[{ required: true, message: '请选择团队' }]}>
            <Select
              showSearch
              optionFilterProp="label"
              options={bindingOptions.teams.map((team) => ({ value: team.id, label: team.name }))}
              onChange={(teamId) => {
                requestForm.setFieldsValue({ ledger_id: undefined, project_id: undefined })
                loadBindingOptions(teamId)
              }}
            />
          </Form.Item>
          <Form.Item name="ledger_id" label="申请访问账套（可选）">
            <Select
              allowClear
              showSearch
              optionFilterProp="label"
              options={bindingOptions.ledgers.map((ledger) => ({ value: ledger.id, label: ledger.name }))}
            />
          </Form.Item>
          <Form.Item name="project_id" label="申请关联项目（可选）">
            <Select
              allowClear
              showSearch
              optionFilterProp="label"
              options={bindingOptions.projects.map((project) => ({ value: project.id, label: project.name }))}
            />
          </Form.Item>
          <Form.Item name="requested_role" label="申请角色" rules={[{ required: true, message: '请选择申请角色' }]}>
            <Select
              options={[
                { value: 'viewer', label: '查看' },
                { value: 'accountant', label: '记账' },
                { value: 'admin', label: '管理' },
              ]}
            />
          </Form.Item>
          <Form.Item name="reason" label="申请说明">
            <Input.TextArea rows={3} placeholder="例如：我是本项目记账人员，需要访问该账套处理本期凭证。" />
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
