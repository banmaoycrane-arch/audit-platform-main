import { useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Empty,
  Form,
  Input,
  List,
  message,
  Row,
  Select,
  Space,
  Statistic,
  Tabs,
  Tag,
  Timeline,
  Typography,
} from 'antd'
import {
  AuditOutlined,
  BookOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  LockOutlined,
  ProjectOutlined,
  SafetyCertificateOutlined,
  SettingOutlined,
  TeamOutlined,
  CrownOutlined,
  UserAddOutlined,
  UserOutlined,
} from '@ant-design/icons'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api, type BindingOptions, type BindingRequest } from '../api/client'
import { useAuthStore, type User } from '../stores/authStore'

const { Title, Paragraph, Text } = Typography

const BINDING_LABEL: Record<string, string> = {
  team: '团队',
  ledger: '账簿',
  project: '项目',
  accounting_entity: '会计主体',
}

const REQUEST_STATUS: Record<string, { label: string; color: string }> = {
  pending: { label: '待审批', color: 'orange' },
  approved: { label: '已通过', color: 'green' },
  rejected: { label: '已驳回', color: 'red' },
}

export function UserSettingsPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { user, setUser, authContext, userLedgers, currentLedgerId, refreshAuthContext } = useAuthStore()
  const [bindingOptions, setBindingOptions] = useState<BindingOptions>({ teams: [], ledgers: [], projects: [] })
  const [myRequests, setMyRequests] = useState<BindingRequest[]>([])
  const [optionsLoading, setOptionsLoading] = useState(false)
  const [requestSubmitting, setRequestSubmitting] = useState(false)
  const [passwordSaving, setPasswordSaving] = useState(false)
  const [profileSaving, setProfileSaving] = useState(false)
  const [requestForm] = Form.useForm()
  const [passwordForm] = Form.useForm()
  const [profileForm] = Form.useForm()

  const initialTab = searchParams.get('focus') === 'password' ? 'password' : 'binding'
  const currentLedger = userLedgers.find((ledger) => ledger.id === currentLedgerId)
  const isSuperAdmin = Boolean(authContext?.is_super_admin)
  const platformRoleLabel = isSuperAdmin ? '开发者超级管理员' : '普通用户'
  const pendingRequests = useMemo(() => myRequests.filter((request) => request.status === 'pending'), [myRequests])
  const approvedRequests = useMemo(() => myRequests.filter((request) => request.status === 'approved'), [myRequests])

  const loadBindingOptions = async (teamId?: number) => {
    setOptionsLoading(true)
    try {
      setBindingOptions(await api.getBindingOptions(teamId))
    } catch (error) {
      message.error(error instanceof Error ? error.message : '加载可申请对象失败')
    } finally {
      setOptionsLoading(false)
    }
  }

  const loadMyRequests = async () => {
    try {
      setMyRequests(await api.listMyBindingRequests())
    } catch (error) {
      message.error(error instanceof Error ? error.message : '加载我的申请记录失败')
    }
  }

  useEffect(() => {
    void loadBindingOptions()
    void loadMyRequests()
  }, [])

  const handleSubmitRequest = async () => {
    const values = await requestForm.validateFields()
    setRequestSubmitting(true)
    try {
      await api.createBindingRequest({
        team_id: values.team_id,
        ledger_id: values.ledger_id || null,
        project_id: values.project_id || null,
        requested_role: values.requested_role,
        reason: values.reason || null,
      })
      message.success('绑定申请已提交，请等待管理员审批')
      requestForm.resetFields()
      void loadBindingOptions()
      void loadMyRequests()
      void refreshAuthContext()
    } catch (error) {
      message.error(error instanceof Error ? error.message : '提交绑定申请失败')
    } finally {
      setRequestSubmitting(false)
    }
  }

  const handleSetPassword = async (values: { password: string; confirmPassword: string }) => {
    if (values.password !== values.confirmPassword) {
      message.error('两次输入的密码不一致')
      return
    }
    setPasswordSaving(true)
    try {
      await api.setPassword(values.password)
      message.success('登录密码已设置')
      passwordForm.resetFields()
      void refreshAuthContext()
    } catch (error) {
      message.error(error instanceof Error ? error.message : '设置密码失败')
    } finally {
      setPasswordSaving(false)
    }
  }

  const handleUpdateProfile = async (values: { username?: string; phone?: string; email?: string }) => {
    setProfileSaving(true)
    try {
      const updated = await api.updateMe({
        username: values.username?.trim() || undefined,
        phone: values.phone?.trim() || undefined,
        email: values.email?.trim() || undefined,
      })
      message.success('个人资料已更新')
      setUser({
        ...user,
        id: updated.id,
        username: updated.username || '',
        phone: updated.phone || '',
        email: updated.email || '',
      } as User)
      void refreshAuthContext()
    } catch (error) {
      message.error(error instanceof Error ? error.message : '更新个人资料失败')
    } finally {
      setProfileSaving(false)
    }
  }

  return (
    <div style={{ padding: 24 }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <div>
          <Title level={3}>
            <UserOutlined /> 用户设置与绑定申请
          </Title>
          <Paragraph type="secondary">
            这里集中处理个人登录设置、团队/账簿/项目访问申请，以及当前授权状态。遇到任务被中断时，可从这里补齐所需绑定。
          </Paragraph>
        </div>

        {isSuperAdmin && (
          <Alert
            type="warning"
            showIcon
            message="当前账号是开发者超级管理员"
            description="可进入平台级入口，查看平台概览并审批全部团队、账簿、项目绑定申请。"
            action={<Button type="primary" size="small" icon={<CrownOutlined />} onClick={() => navigate('/super-admin')}>进入超级管理员</Button>}
          />
        )}

        {authContext?.missing_bindings?.length ? (
          <Alert
            type="warning"
            showIcon
            message="当前账号仍缺少必要绑定"
            description={(
              <Space wrap>
                {authContext.missing_bindings.map((key) => (
                  <Tag color="orange" key={key}>{BINDING_LABEL[key] || key}</Tag>
                ))}
              </Space>
            )}
            action={<Button size="small" type="primary" onClick={() => requestForm.scrollToField('team_id')}>立即申请</Button>}
          />
        ) : (
          <Alert type="success" showIcon message="当前账号绑定状态正常" description="已具备基础工作台访问条件，可继续进入账簿、项目和审计协作流程。" />
        )}

        <Row gutter={[16, 16]}>
          <Col xs={24} md={6}>
            <Card>
              <Statistic title="已加入团队" value={authContext?.teams.length || 0} prefix={<TeamOutlined />} />
            </Card>
          </Col>
          <Col xs={24} md={6}>
            <Card>
              <Statistic title="可访问账簿" value={userLedgers.length} prefix={<BookOutlined />} />
            </Card>
          </Col>
          <Col xs={24} md={6}>
            <Card>
              <Statistic title="可参与项目" value={authContext?.projects.length || 0} prefix={<ProjectOutlined />} />
            </Card>
          </Col>
          <Col xs={24} md={6}>
            <Card>
              <Statistic title="待审批申请" value={pendingRequests.length} prefix={<ClockCircleOutlined />} />
            </Card>
          </Col>
        </Row>

        <Tabs
          defaultActiveKey={initialTab}
          items={[
            {
              key: 'profile',
              label: '个人状态',
              children: (
                <Row gutter={[16, 16]}>
                  <Col xs={24} lg={12}>
                    <Card title="编辑个人资料">
                      <Form
                        form={profileForm}
                        layout="vertical"
                        onFinish={handleUpdateProfile}
                        initialValues={{
                          username: user?.username || '',
                          phone: user?.phone || '',
                          email: user?.email || '',
                        }}
                      >
                        <Form.Item name="username" label="用户名">
                          <Input placeholder="请输入用户名" maxLength={100} showCount />
                        </Form.Item>
                        <Form.Item
                          name="phone"
                          label="手机号"
                          rules={[{ pattern: /^1[3-9]\d{9}$/, message: '请输入有效的手机号' }]}
                        >
                          <Input placeholder="请输入手机号" maxLength={20} />
                        </Form.Item>
                        <Form.Item
                          name="email"
                          label="邮箱"
                          rules={[{ type: 'email', message: '请输入有效的邮箱地址' }]}
                        >
                          <Input placeholder="请输入邮箱" maxLength={200} />
                        </Form.Item>
                        <Button type="primary" htmlType="submit" loading={profileSaving} icon={<UserOutlined />}>
                          保存资料
                        </Button>
                      </Form>
                    </Card>
                  </Col>
                  <Col xs={24} lg={12}>
                    <Card title="当前授权状态">
                      <Descriptions bordered column={1} size="small">
                        <Descriptions.Item label="平台角色">
                          <Tag color={isSuperAdmin ? 'gold' : 'default'}>{platformRoleLabel}</Tag>
                        </Descriptions.Item>
                        <Descriptions.Item label="当前团队">{authContext?.teams[0]?.name || '未加入团队'}</Descriptions.Item>
                        <Descriptions.Item label="当前账簿">{currentLedger?.name || '未选择账簿'}</Descriptions.Item>
                        <Descriptions.Item label="账簿角色">{authContext?.current_ledger_role || '-'}</Descriptions.Item>
                        <Descriptions.Item label="团队类型">{authContext?.current_team_type || '-'}</Descriptions.Item>
                        <Descriptions.Item label="项目模式">
                          {authContext?.can_use_ledger_without_project ? '可不绑定项目直接使用账簿' : '需要项目与账簿绑定后继续'}
                        </Descriptions.Item>
                        <Descriptions.Item label="下一步建议">{authContext?.next_action || '-'}</Descriptions.Item>
                      </Descriptions>
                      <Space wrap style={{ marginTop: 16 }}>
                        <Button icon={<TeamOutlined />} onClick={() => navigate('/team-management')}>团队管理</Button>
                        <Button icon={<BookOutlined />} onClick={() => navigate('/ledger-management')}>账簿管理</Button>
                        <Button icon={<ProjectOutlined />} onClick={() => navigate('/projects')}>项目管理</Button>
                        <Button icon={<SettingOutlined />} onClick={() => navigate('/scope-settings')}>管理配置</Button>
                        {isSuperAdmin && <Button icon={<CrownOutlined />} type="primary" onClick={() => navigate('/super-admin')}>开发者超级管理员</Button>}
                      </Space>
                    </Card>
                  </Col>
                </Row>
              ),
            },
            {
              key: 'binding',
              label: '绑定申请',
              children: (
                <Row gutter={[16, 16]}>
                  <Col xs={24} lg={14}>
                    <Card title="申请团队 / 账簿 / 项目访问">
                      <Alert
                        type="info"
                        showIcon
                        message="申请不会直接授权"
                        description="提交后由管理员审批；审批通过后，系统会把你与对应团队、账簿、项目建立正式绑定。"
                        style={{ marginBottom: 16 }}
                      />
                      <Form form={requestForm} layout="vertical" initialValues={{ requested_role: 'viewer' }}>
                        <Form.Item name="team_id" label="申请加入团队" rules={[{ required: true, message: '请选择团队' }]}> 
                          <Select
                            showSearch
                            placeholder="请选择团队"
                            optionFilterProp="label"
                            loading={optionsLoading}
                            options={bindingOptions.teams.map((team) => ({ value: team.id, label: team.name }))}
                            onChange={(teamId) => {
                              requestForm.setFieldsValue({ ledger_id: undefined, project_id: undefined })
                              void loadBindingOptions(teamId)
                            }}
                          />
                        </Form.Item>
                        <Form.Item name="ledger_id" label="申请访问账簿">
                          <Select
                            allowClear
                            showSearch
                            placeholder="可选：选择需要访问的账簿"
                            optionFilterProp="label"
                            loading={optionsLoading}
                            options={bindingOptions.ledgers.map((ledger) => ({ value: ledger.id, label: ledger.name }))}
                          />
                        </Form.Item>
                        <Form.Item name="project_id" label="申请参与项目">
                          <Select
                            allowClear
                            showSearch
                            placeholder="可选：选择需要参与的项目"
                            optionFilterProp="label"
                            loading={optionsLoading}
                            options={bindingOptions.projects.map((project) => ({ value: project.id, label: project.name }))}
                          />
                        </Form.Item>
                        <Form.Item name="requested_role" label="申请角色" rules={[{ required: true, message: '请选择角色' }]}> 
                          <Select
                            options={[
                              { value: 'viewer', label: '查看 - 仅查看数据' },
                              { value: 'accountant', label: '记账/编制 - 可录入和修改业务数据' },
                              { value: 'admin', label: '管理 - 完整访问和管理权限' },
                            ]}
                          />
                        </Form.Item>
                        <Form.Item name="reason" label="申请说明">
                          <Input.TextArea rows={3} maxLength={200} showCount placeholder="说明申请原因，例如：我是该审计项目现场人员，需要访问客户账簿和项目底稿。" />
                        </Form.Item>
                        <Button type="primary" icon={<UserAddOutlined />} loading={requestSubmitting} onClick={handleSubmitRequest}>
                          提交绑定申请
                        </Button>
                      </Form>
                    </Card>
                  </Col>
                  <Col xs={24} lg={10}>
                    <Card title="我的申请记录">
                      {myRequests.length === 0 ? (
                        <Empty description="暂无申请记录" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                      ) : (
                        <Timeline
                          items={myRequests.map((request) => {
                            const status = REQUEST_STATUS[request.status] || { label: request.status, color: 'default' }
                            return {
                              color: status.color,
                              children: (
                                <Space direction="vertical" size={2}>
                                  <Text strong>{request.team_name || `团队 #${request.team_id}`}</Text>
                                  <Text type="secondary">账簿：{request.ledger_name || '-'}</Text>
                                  <Text type="secondary">项目：{request.project_name || '-'}</Text>
                                  <Space>
                                    <Tag color={status.color}>{status.label}</Tag>
                                    <Text type="secondary">{request.created_at ? new Date(request.created_at).toLocaleString('zh-CN') : '-'}</Text>
                                  </Space>
                                </Space>
                              ),
                            }
                          })}
                        />
                      )}
                    </Card>
                    {approvedRequests.length > 0 && (
                      <Card title="已通过绑定" style={{ marginTop: 16 }}>
                        <List
                          size="small"
                          dataSource={approvedRequests}
                          renderItem={(request) => (
                            <List.Item>
                              <Space wrap>
                                <CheckCircleOutlined style={{ color: '#52c41a' }} />
                                <Text>{request.team_name || `团队 #${request.team_id}`}</Text>
                                {request.ledger_name && <Tag icon={<BookOutlined />}>{request.ledger_name}</Tag>}
                                {request.project_name && <Tag icon={<AuditOutlined />}>{request.project_name}</Tag>}
                              </Space>
                            </List.Item>
                          )}
                        />
                      </Card>
                    )}
                  </Col>
                </Row>
              ),
            },
            {
              key: 'password',
              label: '登录密码',
              children: (
                <Card title="设置登录密码">
                  <Alert type="info" showIcon message="设置后可使用用户名/手机号 + 密码登录。" style={{ marginBottom: 16 }} />
                  <Form form={passwordForm} layout="vertical" onFinish={handleSetPassword} style={{ maxWidth: 420 }}>
                    <Form.Item name="password" label="新密码" rules={[{ required: true, message: '请输入新密码' }, { min: 6, message: '密码至少需要 6 位' }]}> 
                      <Input.Password prefix={<LockOutlined />} placeholder="请输入新密码" />
                    </Form.Item>
                    <Form.Item name="confirmPassword" label="确认密码" rules={[{ required: true, message: '请再次输入新密码' }]}> 
                      <Input.Password prefix={<LockOutlined />} placeholder="请再次输入新密码" />
                    </Form.Item>
                    <Button type="primary" htmlType="submit" loading={passwordSaving}>保存密码</Button>
                  </Form>
                </Card>
              ),
            },
            {
              key: 'paths',
              label: '配置路径',
              children: (
                <Row gutter={[16, 16]}>
                  <Col xs={24} md={12} lg={6}>
                    <Card title="团队" actions={[<Button type="link" onClick={() => navigate('/team-management')}>进入团队管理</Button>]}>申请加入团队、查看团队成员和审批申请。</Card>
                  </Col>
                  <Col xs={24} md={12} lg={6}>
                    <Card title="账簿" actions={[<Button type="link" onClick={() => navigate('/ledger-management')}>进入账簿管理</Button>]}>申请或管理可访问账簿，确定会计主体核算范围。</Card>
                  </Col>
                  <Col xs={24} md={12} lg={6}>
                    <Card title="项目" actions={[<Button type="link" onClick={() => navigate('/projects')}>进入项目管理</Button>]}>将账簿与审计项目绑定，支撑底稿和任务协作。</Card>
                  </Col>
                  <Col xs={24} md={12} lg={6}>
                    <Card title="配置" actions={[<Button type="link" onClick={() => navigate('/scope-settings')}>进入管理配置</Button>]}>维护团队、账簿、项目和主体策略。</Card>
                  </Col>
                </Row>
              ),
            },
          ]}
        />
      </Space>
    </div>
  )
}
