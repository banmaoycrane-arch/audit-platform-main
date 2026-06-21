import { useEffect, useMemo, useState } from 'react'
import {
  Alert, Button, Card, Col, Empty, Form, Input, List, message, Modal, Progress, Result, Row, Select, Space, Spin, Steps, Tag, Typography, Timeline, Tooltip
} from 'antd'
import {
  SafetyCertificateOutlined, TeamOutlined, BookOutlined, AuditOutlined, CheckCircleOutlined, ClockCircleOutlined,
  LockOutlined, UserAddOutlined, ExclamationCircleOutlined, RocketOutlined, ArrowLeftOutlined, HomeOutlined
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useAuthStore } from '../stores/authStore'
import type { BindingOptions, BindingRequest, Team, TeamMember } from '../api/client'

const { Title, Paragraph, Text } = Typography

/**
 * 访客授权申请引导页面
 * 
 * 功能定位：
 * - 针对未绑定任何团队的访客用户（guest）
 * - 提供清晰的申请授权引导流程
 * - 展示申请进度和审批状态
 * 
 * 与 OnboardingPage 的区别：
 * - OnboardingPage：侧重于创建新实体（创建团队/账套/项目）
 * - OnboardingRequestPage：侧重于申请访问现有实体（申请加入已有团队）
 */
export function OnboardingRequestPage() {
  const navigate = useNavigate()
  const { authContext, refreshAuthContext } = useAuthStore()
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [bindingOptions, setBindingOptions] = useState<BindingOptions>({ teams: [], ledgers: [], projects: [] })
  const [myRequests, setMyRequests] = useState<BindingRequest[]>([])
  const [optionsLoading, setOptionsLoading] = useState(false)
  const [requestModalOpen, setRequestModalOpen] = useState(false)
  const [createTeamModalOpen, setCreateTeamModalOpen] = useState(false)
  const [requestForm] = Form.useForm()
  const [createTeamForm] = Form.useForm()

  const isGuest = authContext?.temporary_status === 'onboarding_pending' && authContext.missing_bindings.includes('team')

  // 加载可申请的选项
  const loadBindingOptions = async (teamId?: number) => {
    setOptionsLoading(true)
    try {
      const options = await api.getBindingOptions(teamId)
      setBindingOptions(options)
    } catch {
      message.error('加载可申请对象失败')
    } finally {
      setOptionsLoading(false)
    }
  }

  // 加载我的申请记录
  const loadMyRequests = async () => {
    try {
      const requests = await api.listMyBindingRequests()
      setMyRequests(requests)
    } catch {
      message.error('加载申请记录失败')
    }
  }

  useEffect(() => {
    if (isGuest) {
      loadBindingOptions()
      loadMyRequests()
    }
  }, [isGuest])

  // 计算当前进度
  const progressInfo = useMemo(() => {
    if (!authContext) return { current: 0, total: 3, percent: 0 }
    const { missing_bindings } = authContext
    let current = 0
    if (missing_bindings.includes('team')) current = 0
    else if (missing_bindings.includes('ledger')) current = 1
    else if (missing_bindings.includes('project')) current = 2
    else if (missing_bindings.includes('accounting_entity')) current = 3
    else current = 4

    return {
      current,
      total: 4,
      percent: Math.round((current / 4) * 100)
    }
  }, [authContext])

  // 待审批申请数量
  const pendingCount = useMemo(() => myRequests.filter(r => r.status === 'pending').length, [myRequests])

  // 已通过的申请数量
  const approvedCount = useMemo(() => myRequests.filter(r => r.status === 'approved').length, [myRequests])

  // 提交申请
  const handleSubmitRequest = async () => {
    const values = await requestForm.validateFields()
    setSubmitting(true)
    try {
      await api.createBindingRequest({
        team_id: values.team_id,
        ledger_id: values.ledger_id || null,
        project_id: values.project_id || null,
        requested_role: values.requested_role,
        reason: values.reason || null,
      })
      message.success('申请已提交，请等待管理员审批')
      setRequestModalOpen(false)
      requestForm.resetFields()
      loadMyRequests()
      refreshAuthContext()
    } catch (error: any) {
      message.error(error.message || '提交申请失败')
    } finally {
      setSubmitting(false)
    }
  }

  // 创建团队
  const handleCreateTeam = async () => {
    const values = await createTeamForm.validateFields()
    setSubmitting(true)
    try {
      await api.createTeam(values)
      message.success('团队创建成功！您现在可以继续申请授权了。')
      setCreateTeamModalOpen(false)
      createTeamForm.resetFields()
      loadBindingOptions()
      refreshAuthContext()
    } catch (error: any) {
      message.error(error.message || '创建团队失败')
    } finally {
      setSubmitting(false)
    }
  }

  // 跳转到工作台
  const handleGoToWorkspace = () => {
    navigate('/workspace')
  }

  // 如果不是访客，直接跳转
  if (!isGuest || !authContext) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f5f5f5' }}>
        <Result
          status="success"
          icon={<CheckCircleOutlined style={{ color: '#52c41a' }} />}
          title="您已完成授权"
          subTitle="已成功绑定团队、账套和项目，可以正常使用系统功能。"
          extra={[
            <Button type="primary" icon={<HomeOutlined />} onClick={handleGoToWorkspace} key="workspace">
              进入工作台
            </Button>,
            <Button icon={<TeamOutlined />} onClick={() => navigate('/team-management')} key="team">
              团队管理
            </Button>,
          ]}
        />
      </div>
    )
  }

  return (
    <div style={{ minHeight: '100vh', background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', padding: '40px 20px' }}>
      <div style={{ maxWidth: 900, margin: '0 auto' }}>
        {/* 顶部标题 */}
        <Card style={{ marginBottom: 24, borderRadius: 16 }}>
          <Row gutter={[24, 16]} align="middle">
            <Col flex="none">
              <div style={{
                width: 64, height: 64, borderRadius: '50%',
                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                display: 'flex', alignItems: 'center', justifyContent: 'center'
              }}>
                <SafetyCertificateOutlined style={{ fontSize: 32, color: '#fff' }} />
              </div>
            </Col>
            <Col flex="auto">
              <Title level={3} style={{ margin: 0 }}>访客授权申请</Title>
              <Paragraph type="secondary" style={{ margin: '8px 0 0' }}>
                您需要完成团队、账套、项目和会计主体的授权绑定，方可正常使用系统功能。
              </Paragraph>
            </Col>
            <Col flex="none">
              <Progress type="circle" percent={progressInfo.percent} size={64} />
            </Col>
          </Row>
        </Card>

        {/* 进度条 */}
        <Card style={{ marginBottom: 24, borderRadius: 16 }}>
          <Steps
            current={progressInfo.current}
            size="small"
            items={[
              { title: '申请团队', icon: <TeamOutlined /> },
              { title: '申请账套', icon: <BookOutlined /> },
              { title: '申请项目', icon: <AuditOutlined /> },
              { title: '确认主体', icon: <SafetyCertificateOutlined /> },
            ]}
          />
        </Card>

        {/* 缺少绑定项提示 */}
        {authContext.missing_bindings.length > 0 && (
          <Alert
            type="warning"
            showIcon
            icon={<ExclamationCircleOutlined />}
            title="缺少以下授权项"
            description={
              <Space wrap style={{ marginTop: 8 }}>
                {authContext.missing_bindings.map((key) => {
                  const icons: Record<string, React.ReactNode> = {
                    team: <TeamOutlined />,
                    ledger: <BookOutlined />,
                    project: <AuditOutlined />,
                    accounting_entity: <SafetyCertificateOutlined />,
                  }
                  const labels: Record<string, string> = {
                    team: '团队',
                    ledger: '账套',
                    project: '项目',
                    accounting_entity: '会计主体',
                  }
                  return (
                    <Tag key={key} icon={icons[key]} color="orange" style={{ marginBottom: 4 }}>
                      {labels[key] || key}
                    </Tag>
                  )
                })}
              </Space>
            }
            style={{ marginBottom: 24, borderRadius: 16 }}
          />
        )}

        <Row gutter={[16, 16]}>
          {/* 左侧：操作区 */}
          <Col xs={24} lg={14}>
            <Card title="申请授权" style={{ borderRadius: 16, marginBottom: 16 }}>
              <Paragraph type="secondary" style={{ marginBottom: 16 }}>
                选择您需要加入的团队（必选），以及需要访问的账套和项目（可选）。管理员审批通过后，系统将自动写入相应的访问权限。
              </Paragraph>
              <Space direction="vertical" style={{ width: '100%' }} size="middle">
                <Card size="small" style={{ background: '#fafafa' }}>
                  <Row gutter={[12, 12]} align="middle">
                    <Col xs={24} sm={8}>
                      <div style={{ textAlign: 'center', padding: '12px 0' }}>
                        <TeamOutlined style={{ fontSize: 32, color: '#1890ff', marginBottom: 8 }} />
                        <div style={{ fontWeight: 500 }}>申请加入团队</div>
                        <Text type="secondary" style={{ fontSize: 12 }}>必选项</Text>
                      </div>
                    </Col>
                    <Col xs={24} sm={8}>
                      <div style={{ textAlign: 'center', padding: '12px 0' }}>
                        <BookOutlined style={{ fontSize: 32, color: '#52c41a', marginBottom: 8 }} />
                        <div style={{ fontWeight: 500 }}>申请账套</div>
                        <Text type="secondary" style={{ fontSize: 12 }}>可选项</Text>
                      </div>
                    </Col>
                    <Col xs={24} sm={8}>
                      <div style={{ textAlign: 'center', padding: '12px 0' }}>
                        <AuditOutlined style={{ fontSize: 32, color: '#faad14', marginBottom: 8 }} />
                        <div style={{ fontWeight: 500 }}>申请项目</div>
                        <Text type="secondary" style={{ fontSize: 12 }}>可选项</Text>
                      </div>
                    </Col>
                  </Row>
                </Card>

                <Button
                  type="primary"
                  size="large"
                  icon={<UserAddOutlined />}
                  onClick={() => setRequestModalOpen(true)}
                  block
                >
                  申请加入团队
                </Button>

                <div style={{ textAlign: 'center' }}>
                  <Text type="secondary">或者</Text>
                </div>

                <Button
                  size="large"
                  icon={<RocketOutlined />}
                  onClick={() => setCreateTeamModalOpen(true)}
                  block
                >
                  创建新团队
                </Button>
              </Space>
            </Card>

            {/* 申请说明 */}
            <Card size="small" style={{ borderRadius: 16 }}>
              <Title level={5}>授权说明</Title>
              <ul style={{ margin: 0, paddingLeft: 20, color: '#666' }}>
                <li><Text>选择团队是必选项，申请后将成为该团队的成员</Text></li>
                <li><Text>账套和项目为可选项，可同时申请或稍后单独申请</Text></li>
                <li><Text>审批通过后会自动写入对应的访问权限</Text></li>
                <li><Text>审批结果会通过申请记录展示，请关注审批状态</Text></li>
              </ul>
            </Card>
          </Col>

          {/* 右侧：申请记录 */}
          <Col xs={24} lg={10}>
            <Card title="我的申请记录" style={{ borderRadius: 16, marginBottom: 16 }}>
              {pendingCount > 0 && (
                <Alert
                  type="info"
                  showIcon
                  icon={<ClockCircleOutlined />}
                  title={`您有 ${pendingCount} 个申请等待审批`}
                  style={{ marginBottom: 16 }}
                />
              )}

              {myRequests.length === 0 ? (
                <Empty description="暂无申请记录" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              ) : (
                <Timeline
                  items={myRequests.map((request) => {
                    const statusConfig: Record<string, { color: string; icon: React.ReactNode }> = {
                      pending: { color: 'orange', icon: <ClockCircleOutlined /> },
                      approved: { color: 'green', icon: <CheckCircleOutlined /> },
                      rejected: { color: 'red', icon: <ExclamationCircleOutlined /> },
                    }
                    const config = statusConfig[request.status] || { color: 'gray', icon: null }

                    return {
                      color: config.color,
                      icon: config.icon,
                      children: (
                        <div>
                          <Text strong>{request.team_name || `团队 #${request.team_id}`}</Text>
                          {request.ledger_name && (
                            <div><Text type="secondary">账套：{request.ledger_name}</Text></div>
                          )}
                          {request.project_name && (
                            <div><Text type="secondary">项目：{request.project_name}</Text></div>
                          )}
                          <div style={{ marginTop: 4 }}>
                            <Tag color={config.color}>
                              {request.status === 'pending' ? '待审批' : request.status === 'approved' ? '已通过' : '已驳回'}
                            </Tag>
                            <Text type="secondary" style={{ fontSize: 12 }}>
                              {request.created_at ? new Date(request.created_at).toLocaleString() : ''}
                            </Text>
                          </div>
                        </div>
                      ),
                    }
                  })}
                />
              )}
            </Card>

            {/* 已完成绑定 */}
            {approvedCount > 0 && (
              <Card size="small" style={{ borderRadius: 16 }}>
                <Title level={5}><CheckCircleOutlined style={{ color: '#52c41a' }} /> 已完成的绑定</Title>
                <List
                  size="small"
                  dataSource={myRequests.filter(r => r.status === 'approved')}
                  renderItem={(request) => (
                    <List.Item>
                      <Space>
                        <TeamOutlined />
                        <Text>{request.team_name}</Text>
                        {request.ledger_name && <><BookOutlined /><Text>{request.ledger_name}</Text></>}
                      </Space>
                    </List.Item>
                  )}
                />
              </Card>
            )}
          </Col>
        </Row>

        {/* 底部操作 */}
        <Card style={{ marginTop: 24, borderRadius: 16, textAlign: 'center' }}>
          <Space size="large">
            <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)}>
              返回上页
            </Button>
            <Button type="primary" icon={<HomeOutlined />} onClick={handleGoToWorkspace}>
              进入工作台（受限模式）
            </Button>
          </Space>
          <Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 0 }}>
            受限模式下可以继续准备资料，但涉及正式记账、期间关闭、报表出具等操作需要完成授权。
          </Paragraph>
        </Card>
      </div>

      {/* 申请授权 Modal */}
      <Modal
        title={
          <Space>
            <SafetyCertificateOutlined style={{ color: '#1890ff' }} />
            <span>申请授权（团队 / 账套 / 项目）</span>
          </Space>
        }
        open={requestModalOpen}
        onOk={handleSubmitRequest}
        onCancel={() => setRequestModalOpen(false)}
        okText="提交申请"
        cancelText="取消"
        confirmLoading={submitting}
        width={520}
      >
        <Form form={requestForm} layout="vertical" initialValues={{ requested_role: 'viewer' }}>
          <Alert
            type="info"
            showIcon
            title="授权说明"
            description={
              <ul style={{ margin: '8px 0', paddingLeft: 20 }}>
                <li>选择团队是必选项，申请后将成为该团队的成员</li>
                <li>账套和项目为可选项，可同时申请或稍后单独申请</li>
                <li>审批通过后会自动写入对应的访问权限</li>
              </ul>
            }
            style={{ marginBottom: 16 }}
          />

          <Form.Item
            name="team_id"
            label={<Space>申请加入团队 <Text type="danger">*</Text></Space>}
            rules={[{ required: true, message: '请选择要申请的团队' }]}
          >
            <Select
              showSearch
              placeholder="请选择团队"
              optionFilterProp="label"
              loading={optionsLoading}
              options={bindingOptions.teams.map((team) => ({ value: team.id, label: team.name }))}
              onChange={(teamId) => {
                requestForm.setFieldsValue({ ledger_id: undefined, project_id: undefined })
                loadBindingOptions(teamId)
              }}
            />
          </Form.Item>

          <Form.Item
            name="ledger_id"
            label="申请访问账套"
            tooltip="选择后将获得该账套的访问权限"
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
            label="申请关联项目"
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
            label={<Space>申请角色 <Text type="danger">*</Text></Space>}
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

      {/* 创建团队 Modal */}
      <Modal
        title={
          <Space>
            <TeamOutlined style={{ color: '#52c41a' }} />
            <span>创建新团队</span>
          </Space>
        }
        open={createTeamModalOpen}
        onOk={handleCreateTeam}
        onCancel={() => setCreateTeamModalOpen(false)}
        okText="创建"
        cancelText="取消"
        confirmLoading={submitting}
      >
        <Form form={createTeamForm} layout="vertical" initialValues={{ type: 'company' }}>
          <Alert
            type="info"
            showIcon
            title="创建团队后将自动成为管理员"
            description="创建团队后，您可以继续申请授权或直接创建账套和项目。"
            style={{ marginBottom: 16 }}
          />
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
    </div>
  )
}
