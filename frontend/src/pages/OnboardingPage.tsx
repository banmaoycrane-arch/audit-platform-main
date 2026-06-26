import { useEffect, useMemo, useState } from 'react'
import { Alert, Button, Card, DatePicker, Divider, Form, Input, List, message, Select, Space, Steps, Tag, Typography } from 'antd'
import dayjs from 'dayjs'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import type { AuthContext, Ledger, Project, Team } from '../api/client'
import { useAuthStore } from '../stores/authStore'

const { Title, Paragraph, Text } = Typography

type BindingKey = 'team' | 'ledger' | 'project' | 'accounting_entity'

const stepDefinitions: Array<{
  key: BindingKey
  title: string
  financialMeaning: string
}> = [
  {
    key: 'team',
    title: '团队',
    financialMeaning: '团队对应实务中的企业财务部、事务所项目组或服务团队，用于限定人员权限和协作范围。',
  },
  {
    key: 'ledger',
    title: '账套',
    financialMeaning: '账套是凭证、科目、期间和报表的归属范围，不同账套之间的财务数据必须隔离。',
  },
  {
    key: 'project',
    title: '项目',
    financialMeaning: '项目用于明确本次核算、审计或税务工作的业务范围，后续证据和底稿应归集到具体项目。',
  },
  {
    key: 'accounting_entity',
    title: '会计主体确认',
    financialMeaning: '会计主体决定“为谁记账、为谁出报表”，未确认前历史资料不能自动并入当前账套。',
  },
]

const bindingLabels: Record<BindingKey, string> = {
  team: '团队',
  ledger: '账套',
  project: '项目',
  accounting_entity: '会计主体',
}

export function OnboardingPage() {
  const navigate = useNavigate()
  const { setCurrentLedger, refreshAuthContext } = useAuthStore()
  const [context, setContext] = useState<AuthContext | null>(null)
  const [currentStep, setCurrentStep] = useState(0)
  const [teams, setTeams] = useState<Team[]>([])
  const [ledgers, setLedgers] = useState<Ledger[]>([])
  const [projects, setProjects] = useState<Project[]>([])
  const [selectedTeamId, setSelectedTeamId] = useState<number | null>(null)
  const [selectedLedgerId, setSelectedLedgerId] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [teamForm] = Form.useForm()
  const [ledgerForm] = Form.useForm()
  const [projectForm] = Form.useForm()
  const [entityForm] = Form.useForm()

  const refreshContext = async () => {
    const nextContext = await api.getAuthContext()
    setContext(nextContext)
    setTeams(nextContext.teams)
    setLedgers(nextContext.ledgers)
    setProjects(nextContext.projects)
    await refreshAuthContext()

    if (nextContext.teams.length > 0 && !selectedTeamId) {
      setSelectedTeamId(nextContext.teams[0].id)
      ledgerForm.setFieldValue('team_id', nextContext.teams[0].id)
      projectForm.setFieldValue('team_id', nextContext.teams[0].id)
    }
    if (nextContext.current_ledger_id) {
      setSelectedLedgerId(nextContext.current_ledger_id)
    } else if (nextContext.ledgers.length > 0) {
      setSelectedLedgerId(nextContext.ledgers[0].id)
    }
    const defaultLedger = nextContext.ledgers.find((ledger) => ledger.id === nextContext.current_ledger_id) || nextContext.ledgers[0]
    if (defaultLedger && !entityForm.getFieldValue('entity_name')) {
      entityForm.setFieldValue('entity_name', defaultLedger.name)
    }

    const firstMissingIndex = stepDefinitions.findIndex((step) =>
      nextContext.missing_bindings.includes(step.key)
    )
    setCurrentStep(firstMissingIndex >= 0 ? firstMissingIndex : stepDefinitions.length - 1)
  }

  useEffect(() => {
    refreshContext().catch(() => {
      message.error('加载首次登录上下文失败，请重新登录后再试')
    })
  }, [])

  const missingBindingKeys = useMemo(
    () => (context?.missing_bindings.filter((item): item is BindingKey => item in bindingLabels) || []),
    [context]
  )

  const currentBindingKey = stepDefinitions[currentStep]?.key
  const isTemporary = context?.temporary_status === 'onboarding_pending'

  const handleCreateTeam = async () => {
    const values = await teamForm.validateFields()
    setLoading(true)
    try {
      const team = await api.createTeam(values)
      setSelectedTeamId(team.id)
      message.success('团队创建成功，请继续确认账套')
      await refreshContext()
    } catch (error: any) {
      message.error(error.message || '团队创建失败')
    } finally {
      setLoading(false)
    }
  }

  const handleSelectExistingTeam = () => {
    if (!selectedTeamId) {
      message.warning('请先选择团队')
      return
    }
    setCurrentStep(1)
  }

  const handleCreateLedger = async () => {
    const values = await ledgerForm.validateFields()
    const teamId = values.team_id || selectedTeamId
    if (!teamId) {
      message.warning('请先创建或选择团队')
      return
    }
    setLoading(true)
    try {
      const ledger = await api.createLedger({
        team_id: teamId,
        name: values.name,
        accounting_start_date: values.accounting_start_date
          ? dayjs(values.accounting_start_date).format('YYYY-MM-DD')
          : undefined,
      })
      await api.switchLedger(ledger.id)
      setSelectedLedgerId(ledger.id)
      message.success('账套创建成功，请继续确认项目')
      await refreshContext()
    } catch (error: any) {
      message.error(error.message || '账套创建失败')
    } finally {
      setLoading(false)
    }
  }

  const handleSelectExistingLedger = async () => {
    if (!selectedLedgerId) {
      message.warning('请先选择账套')
      return
    }
    setLoading(true)
    try {
      await api.switchLedger(selectedLedgerId)
      setCurrentLedger(selectedLedgerId)
      message.success('已切换到账套，请继续确认项目')
      await refreshContext()
    } catch (error: any) {
      message.error(error.message || '账套切换失败')
    } finally {
      setLoading(false)
    }
  }

  const handleCreateProject = async () => {
    const values = await projectForm.validateFields()
    const teamId = values.team_id || selectedTeamId || teams[0]?.id
    if (!teamId) {
      message.warning('请先创建或选择团队')
      return
    }
    setLoading(true)
    try {
      await api.createProject({
        team_id: teamId,
        name: values.name,
        project_type: values.project_type || 'audit',
        status: 'active',
      })
      message.success('项目创建成功，请继续确认会计主体')
      await refreshContext()
    } catch (error: any) {
      message.error(error.message || '项目创建失败')
    } finally {
      setLoading(false)
    }
  }

  const handleUseExistingProject = () => {
    if (projects.length === 0) {
      message.warning('暂无可选项目，请先创建项目')
      return
    }
    setCurrentStep(3)
  }

  const handleConfirmAccountingEntity = async () => {
    const ledgerId = selectedLedgerId || context?.current_ledger_id || ledgers[0]?.id
    if (!ledgerId) {
      message.warning('请先选择或创建账套')
      return
    }
    const values = await entityForm.validateFields()
    setLoading(true)
    try {
      await api.createEntity({
        entity_name: values.entity_name,
        entity_code: values.entity_code || null,
        ledger_id: ledgerId,
        entity_type: 'company',
        entity_category: 'parent',
        is_accounting_entity: true,
        is_legal_entity: values.is_legal_entity ?? true,
        is_tax_entity: values.is_tax_entity ?? false,
        is_management_entity: values.is_management_entity ?? false,
      })
      await refreshContext()
      message.success('会计主体已确认')
      navigate('/workspace', { replace: true })
    } catch (error: any) {
      message.error(error.message || '会计主体确认失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ minHeight: '100vh', background: '#f5f5f5', padding: 40 }}>
      <Card style={{ maxWidth: 920, margin: '0 auto' }}>
        <Title level={3}>首次登录引导</Title>
        <Paragraph type="secondary">
          请把用户、团队、账套、项目和会计主体关系确认清楚。这样后续凭证、报表、审计证据都能落到明确的财务归属范围。
        </Paragraph>

        {isTemporary && (
          <Alert
            type="warning"
            showIcon
            style={{ marginBottom: 16 }}
            title="当前为临时工作状态"
            description="未完成绑定前可以继续准备资料，但历史资料不会自动认领或并入当前账套；涉及正式记账、期间关闭、报表出具等操作应在完成会计主体确认后进行。"
          />
        )}

        <Space wrap style={{ marginBottom: 16 }}>
          <Text strong>缺失绑定项：</Text>
          {missingBindingKeys.length > 0 ? (
            missingBindingKeys.map((key) => <Tag color="orange" key={key}>{bindingLabels[key]}</Tag>)
          ) : (
            <Tag color="green">已完成</Tag>
          )}
          <Text type="secondary">下一步：{context?.next_action || '加载中'}</Text>
        </Space>

        <Steps
          current={currentStep}
          style={{ marginBottom: 24 }}
          items={stepDefinitions.map((step) => ({
            title: step.title,
            description: context?.missing_bindings.includes(step.key) ? '待确认' : '已具备',
          }))}
        />

        <Card size="small" style={{ marginBottom: 16 }}>
          <Text strong>本步骤财务含义：</Text>
          <Paragraph style={{ marginTop: 8, marginBottom: 0 }}>
            {stepDefinitions[currentStep]?.financialMeaning}
          </Paragraph>
        </Card>

        {currentBindingKey === 'team' && (
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            {teams.length > 0 && (
              <Card size="small" title="选择已有团队">
                <Space wrap>
                  <Select
                    style={{ width: 280 }}
                    placeholder="请选择团队"
                    value={selectedTeamId || undefined}
                    onChange={(value) => {
                      setSelectedTeamId(value)
                      ledgerForm.setFieldValue('team_id', value)
                      projectForm.setFieldValue('team_id', value)
                    }}
                    options={teams.map((team) => ({ value: team.id, label: team.name }))}
                  />
                  <Button type="primary" onClick={handleSelectExistingTeam}>使用该团队继续</Button>
                </Space>
              </Card>
            )}
            <Card size="small" title="创建新团队">
              <Form form={teamForm} layout="vertical" initialValues={{ type: 'company' }}>
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
                <Button type="primary" loading={loading} onClick={handleCreateTeam}>
                  创建团队并继续
                </Button>
              </Form>
            </Card>
          </Space>
        )}

        {currentBindingKey === 'ledger' && (
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            {ledgers.length > 0 && (
              <Card size="small" title="选择已有账套">
                <Space wrap>
                  <Select
                    style={{ width: 320 }}
                    placeholder="请选择账套"
                    value={selectedLedgerId || undefined}
                    onChange={setSelectedLedgerId}
                    options={ledgers.map((ledger) => ({ value: ledger.id, label: ledger.name }))}
                  />
                  <Button type="primary" loading={loading} onClick={handleSelectExistingLedger}>使用该账套继续</Button>
                </Space>
              </Card>
            )}
            <Card size="small" title="创建新账套">
              <Form form={ledgerForm} layout="vertical" initialValues={{ team_id: selectedTeamId || undefined, accounting_start_date: dayjs() }}>
                <Form.Item name="team_id" label="所属团队" rules={[{ required: true, message: '请选择所属团队' }]}>
                  <Select
                    placeholder="请选择团队"
                    onChange={setSelectedTeamId}
                    options={teams.map((team) => ({ value: team.id, label: team.name }))}
                  />
                </Form.Item>
                <Form.Item name="name" label="账套名称" rules={[{ required: true, message: '请输入账套名称' }]}>
                  <Input placeholder="例如：XX公司2026账套" />
                </Form.Item>
                <Form.Item
                  name="accounting_start_date"
                  label="会计时间线起点"
                  rules={[{ required: true, message: '请选择会计时间线起点' }]}
                  extra="默认创建当天；补建历史账套时请调整为实际开账日期"
                >
                  <DatePicker style={{ width: '100%' }} />
                </Form.Item>
                <Space>
                  <Button onClick={() => setCurrentStep(0)}>返回团队步骤</Button>
                  <Button type="primary" loading={loading} onClick={handleCreateLedger}>
                    创建账套并继续
                  </Button>
                </Space>
              </Form>
            </Card>
          </Space>
        )}

        {currentBindingKey === 'project' && (
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            {projects.length > 0 && (
              <Card size="small" title="已有项目">
                <List
                  size="small"
                  dataSource={projects}
                  renderItem={(project) => <List.Item>{project.name}（{project.status}）</List.Item>}
                />
                <Button type="primary" style={{ marginTop: 12 }} onClick={handleUseExistingProject}>使用已有项目继续</Button>
              </Card>
            )}
            <Card size="small" title="创建项目">
              <Form form={projectForm} layout="vertical" initialValues={{ team_id: selectedTeamId || teams[0]?.id, project_type: 'audit' }}>
                <Form.Item name="team_id" label="所属团队" rules={[{ required: true, message: '请选择所属团队' }]}>
                  <Select options={teams.map((team) => ({ value: team.id, label: team.name }))} />
                </Form.Item>
                <Form.Item name="name" label="项目名称" rules={[{ required: true, message: '请输入项目名称' }]}>
                  <Input placeholder="例如：XX公司2026年报审计项目" />
                </Form.Item>
                <Form.Item name="project_type" label="项目类型">
                  <Select
                    options={[
                      { value: 'audit', label: '审计项目' },
                      { value: 'accounting', label: '核算项目' },
                      { value: 'tax', label: '税务项目' },
                      { value: 'consulting', label: '咨询项目' },
                    ]}
                  />
                </Form.Item>
                <Space>
                  <Button onClick={() => setCurrentStep(1)}>返回账套步骤</Button>
                  <Button type="primary" loading={loading} onClick={handleCreateProject}>创建项目并继续</Button>
                </Space>
              </Form>
            </Card>
          </Space>
        )}

        {currentBindingKey === 'accounting_entity' && (
          <Card size="small" title="会计主体确认">
            <Alert
              type="info"
              showIcon
              title="请确认当前账套的会计主体"
              description="会计主体是凭证、报表和审计证据的归属对象。确认后系统会把该主体写入当前账套，后续登录不会再重复提示该项缺失。"
            />
            <Divider />
            <Form form={entityForm} layout="vertical" initialValues={{ is_legal_entity: true, is_tax_entity: false, is_management_entity: false }}>
              <Form.Item name="entity_name" label="会计主体名称" rules={[{ required: true, message: '请输入会计主体名称' }]}>
                <Input placeholder="例如：XX有限公司" />
              </Form.Item>
              <Form.Item name="entity_code" label="统一社会信用代码 / 主体编码">
                <Input placeholder="可选，用于后续合同、发票、税务资料匹配" />
              </Form.Item>
              <Space>
                <Button onClick={() => setCurrentStep(2)}>返回项目步骤</Button>
                <Button type="primary" loading={loading} onClick={handleConfirmAccountingEntity}>确认会计主体并进入工作台</Button>
              </Space>
            </Form>
          </Card>
        )}

        <Divider />
        <Card size="small" title="待确认历史资料">
          {context?.historical_candidates.length ? (
            <List
              size="small"
              dataSource={context.historical_candidates}
              renderItem={(item, index) => (
                <List.Item>
                  {typeof item === 'object' && item !== null
                    ? `候选资料 ${index + 1}：请确认是否归属于当前账套`
                    : String(item)}
                </List.Item>
              )}
            />
          ) : (
            <Paragraph type="secondary" style={{ marginBottom: 0 }}>
              暂无可自动匹配的历史资料。即使后续发现候选资料，也必须由用户确认后才能并入当前账套。
            </Paragraph>
          )}
        </Card>
      </Card>
    </div>
  )
}
