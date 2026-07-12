import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Alert, Button, Card, List, Select, Space, Tag, Typography, Input, message } from 'antd'
import { SendOutlined } from '@ant-design/icons'
import { api, type AgentAssistResponse } from '../api/client'
import { useAuthStore } from '../stores/authStore'

const { Title, Paragraph, Text } = Typography
const { TextArea } = Input

type ChatMessage = {
  role: 'user' | 'assistant'
  content: string
  result?: AgentAssistResponse
}

type AgentModelConfig = {
  provider: string
  model_name: string | null
  api_key_configured: boolean
  remote_model_configured: boolean
  local_lightweight_model_enabled: boolean
  fallback_to_rules_enabled: boolean
  active_mode: string
  config_source?: string
  is_ollama?: boolean
  agent_mode?: string
}

type AgentCaseTemplate = {
  template_name: string
  scenario: string
  allowed_agent_roles: string[]
  execution_steps: Array<{
    step_no: number
    name: string
    agent_role: string
    can_execute: boolean
    output_status: string
    approval_required: boolean
    allowed_tools: string[]
  }>
  workpaper_policy: string
  audit_draft_policy: string
  api_tool_policy: string
  deliverable_rule: {
    display_name: string
    deliverable_policy: string
    allowed_deliverables: string[]
  }
  audit_trace_required: boolean
  immutable_trace_required: boolean
}

type AgentOrchestrationPlan = {
  primary_agent_role: string
  supporting_agent_roles: string[]
  file_access_policy: string
  human_confirmation_required_for: string[]
  audit_trace_required: boolean
  coordination_steps: Array<{
    step_no: number
    agent_role: string
    task: string
    can_execute: boolean
    approval_required: boolean
    audit_trace_required: boolean
    allowed_tools: string[]
  }>
}

type AgentApproval = {
  id: number
  tool_name: string
  agent_role: string
  risk_level: string
  status: string
  approval_reason: string
  confirmation_comment: string | null
  created_at: string | null
  confirmed_at: string | null
}

type AgentDraftExecutionResult = {
  approval_id: number
  tool_name: string
  agent_role: string
  execution_status: string
  output_type: string
  result: {
    title: string
    notice: string
    review_required: boolean
    formal_delivery_allowed: boolean
  }
}

type AgentDraftReview = {
  id: number
  approval_id: number
  tool_name: string
  agent_role: string
  draft_output_type: string
  review_status: string
  review_comment: string | null
  reviewed_by_user_id: number | null
  returned_for_rework: boolean
  allow_formal_delivery_design: boolean
  created_at: string | null
  reviewed_at: string | null
}

const intentLabels: Record<string, string> = {
  accounting_import: '记账导入',
  audit_workflow: '审计流程',
  report_export: '报告导出',
  basic_data: '基础资料',
  period_close: '期间结账',
  general_help: '通用帮助'
}

const riskColors: Record<string, string> = {
  low: 'green',
  medium: 'orange',
  high: 'red'
}

const riskLabels: Record<string, string> = {
  low: '低风险',
  medium: '中风险',
  high: '高风险'
}

const caseScenarioOptions = [
  { label: '企业内控', value: 'internal_control' },
  { label: '财务尽调', value: 'financial_due_diligence' }
]

const orchestrationTaskOptions = [
  { label: '收集材料并编制底稿', value: '以尽调审计任务为案例，收集材料并编制底稿' },
  { label: '导入凭证并识别业务循环', value: '导入凭证并利用向量库识别业务循环' },
  { label: '生成审计初稿并进入人工确认', value: '生成审计初稿并进入人工确认' }
]

const draftExecutableTools = new Set([
  'draft_audit_workpaper',
  'review_workpaper_quality',
  'generate_audit_draft',
  'generate_issue_classification_draft',
  'generate_final_deliverable_draft'
])

export function AgentChatPage() {
  const { currentLedgerId } = useAuthStore()
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [controlLoading, setControlLoading] = useState(false)
  const [modelConfig, setModelConfig] = useState<AgentModelConfig | null>(null)
  const [caseTemplate, setCaseTemplate] = useState<AgentCaseTemplate | null>(null)
  const [orchestrationPlan, setOrchestrationPlan] = useState<AgentOrchestrationPlan | null>(null)
  const [caseScenario, setCaseScenario] = useState('internal_control')
  const [orchestrationTask, setOrchestrationTask] = useState(orchestrationTaskOptions[0].value)
  const [approvalRecords, setApprovalRecords] = useState<AgentApproval[]>([])
  const [draftResults, setDraftResults] = useState<Record<number, AgentDraftExecutionResult>>({})
  const [draftReviews, setDraftReviews] = useState<Record<number, AgentDraftReview>>({})
  const [reviewComments, setReviewComments] = useState<Record<number, string>>({})
  const [approvalLoadingKey, setApprovalLoadingKey] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: 'assistant',
      content: '你好，我是对话式 Agent 助手。在已登录且选定账簿的前提下，我可以直接调用后端 API 帮你查科目、证据收件箱、导入任务、内控待办等，无需跳转页面。中高风险操作会列为待确认项，不会自动执行。'
    }
  ])

  const agentRequest = async <T,>(path: string, body?: unknown): Promise<T> => {
    const token = localStorage.getItem('token')
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    }
    if (currentLedgerId) {
      headers['X-Ledger-Id'] = String(currentLedgerId)
    }
    const response = await fetch(`${api.baseUrl}${path}`, {
      method: body ? 'POST' : 'GET',
      headers,
      body: body ? JSON.stringify(body) : undefined,
    })
    if (!response.ok) {
      throw new Error(`请求失败（${response.status}）`)
    }
    return response.json() as Promise<T>
  }

  const loadAgentControls = async (scenario = caseScenario, taskMessage = orchestrationTask) => {
    setControlLoading(true)
    try {
      const [model, template, plan] = await Promise.all([
        agentRequest<AgentModelConfig>('/api/agent/model/config'),
        agentRequest<AgentCaseTemplate>('/api/agent/case-templates/due-diligence', { scenario }),
        agentRequest<AgentOrchestrationPlan>('/api/agent/orchestration/plan', { message: taskMessage })
      ])
      setModelConfig(model)
      setCaseTemplate(template)
      setOrchestrationPlan(plan)
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error)
      message.error(`Agent 控制台加载失败：${detail}`)
    } finally {
      setControlLoading(false)
    }
  }

  useEffect(() => {
    void loadAgentControls()
  }, [])

  const getApprovalToolName = (allowedTools: string[]) => {
    return allowedTools[0] || 'generate_audit_draft'
  }

  const requestApproval = async (step: AgentOrchestrationPlan['coordination_steps'][number]) => {
    const toolName = getApprovalToolName(step.allowed_tools)
    const loadingKey = `request-${step.step_no}`
    setApprovalLoadingKey(loadingKey)
    try {
      const approval = await agentRequest<AgentApproval>('/api/agent/approvals/request', {
        tool_name: toolName,
        agent_role: step.agent_role,
        args: {
          source: 'agent_console',
          scenario: caseScenario,
          task_message: orchestrationTask,
          step_no: step.step_no,
          step_task: step.task
        }
      })
      setApprovalRecords((items) => [approval, ...items])
      message.success(`已生成待确认记录 #${approval.id}`)
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error)
      message.error(`申请确认失败：${detail}`)
    } finally {
      setApprovalLoadingKey(null)
    }
  }

  const confirmApproval = async (approval: AgentApproval) => {
    const loadingKey = `confirm-${approval.id}`
    setApprovalLoadingKey(loadingKey)
    try {
      const confirmed = await agentRequest<AgentApproval>(`/api/agent/approvals/${approval.id}/confirm`, {
        comment: '已在 Agent 控制台人工复核，同意进入后续受控流程。'
      })
      setApprovalRecords((items) => items.map((item) => item.id === confirmed.id ? confirmed : item))
      message.success(`确认记录 #${confirmed.id} 已确认`)
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error)
      message.error(`确认失败：${detail}`)
    } finally {
      setApprovalLoadingKey(null)
    }
  }

  const executeDraft = async (approval: AgentApproval) => {
    const loadingKey = `execute-${approval.id}`
    setApprovalLoadingKey(loadingKey)
    try {
      const result = await agentRequest<AgentDraftExecutionResult>(`/api/agent/approvals/${approval.id}/execute-draft`, {})
      setDraftResults((items) => ({ ...items, [approval.id]: result }))
      message.success(`已生成草稿结果 #${approval.id}`)
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error)
      message.error(`草稿受控执行失败：${detail}`)
    } finally {
      setApprovalLoadingKey(null)
    }
  }

  const createDraftReview = async (approvalId: number) => {
    const loadingKey = `review-create-${approvalId}`
    setApprovalLoadingKey(loadingKey)
    try {
      const review = await agentRequest<AgentDraftReview>(`/api/agent/approvals/${approvalId}/draft-review`, {})
      setDraftReviews((items) => ({ ...items, [approvalId]: review }))
      setReviewComments((items) => ({ ...items, [approvalId]: items[approvalId] || '已人工复核草稿内容。' }))
      message.success(`已创建复核记录 #${review.id}`)
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error)
      message.error(`创建复核记录失败：${detail}`)
    } finally {
      setApprovalLoadingKey(null)
    }
  }

  const submitDraftReview = async (approvalId: number, reviewStatus: 'approved' | 'returned') => {
    const review = draftReviews[approvalId]
    if (!review) return
    const comment = (reviewComments[approvalId] || '').trim()
    if (!comment) {
      message.warning('请先填写复核意见')
      return
    }
    const loadingKey = `review-submit-${approvalId}-${reviewStatus}`
    setApprovalLoadingKey(loadingKey)
    try {
      const submitted = await agentRequest<AgentDraftReview>(`/api/agent/draft-reviews/${review.id}/submit`, {
        review_status: reviewStatus,
        review_comment: comment,
        returned_for_rework: reviewStatus === 'returned',
        allow_formal_delivery_design: reviewStatus === 'approved'
      })
      setDraftReviews((items) => ({ ...items, [approvalId]: submitted }))
      message.success(reviewStatus === 'approved' ? '复核通过，允许进入正式交付设计阶段' : '已退回重做')
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error)
      message.error(`提交复核失败：${detail}`)
    } finally {
      setApprovalLoadingKey(null)
    }
  }

  const send = async () => {
    const text = input.trim()
    if (!text) {
      message.warning('请输入你想完成的财务或审计任务')
      return
    }

    setInput('')
    setLoading(true)
    const nextMessages: ChatMessage[] = [...messages, { role: 'user', content: text }]
    setMessages(nextMessages)
    try {
      const conversationHistory = nextMessages
        .filter((item) => item.role === 'user' || item.role === 'assistant')
        .slice(-8)
        .map((item) => ({ role: item.role, content: item.content }))
      const result = await api.agentAssist(text, {
        conversationHistory,
        ledgerId: currentLedgerId,
      })
      setMessages((items) => [...items, { role: 'assistant', content: result.reply, result }])
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error)
      message.error(`Agent 助手请求失败：${detail}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <Title level={3}>Agent 助手</Title>
      <Paragraph type="secondary">
        通过对话直接调用已鉴权的后端 API 完成查询与准备工作，无需跳转页面。低风险工具自动执行；中高风险仅通知待确认。
        {currentLedgerId ? ` 当前账簿 ID：${currentLedgerId}。` : ' 请先在顶部选择账簿，以便查询账簿相关业务数据。'}
      </Paragraph>

      <Card
        title="Agent 控制台"
        extra={<Button loading={controlLoading} onClick={() => void loadAgentControls()}>刷新状态</Button>}
        style={{ marginBottom: 16 }}
      >
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <Space wrap>
            <Text strong>案例场景：</Text>
            <Select
              style={{ width: 160 }}
              value={caseScenario}
              options={caseScenarioOptions}
              onChange={(value) => {
                setCaseScenario(value)
                void loadAgentControls(value, orchestrationTask)
              }}
            />
            <Text strong>协同任务样例：</Text>
            <Select
              style={{ width: 260 }}
              value={orchestrationTask}
              options={orchestrationTaskOptions}
              onChange={(value) => {
                setOrchestrationTask(value)
                void loadAgentControls(caseScenario, value)
              }}
            />
          </Space>

          {modelConfig && (
            <Card size="small" title="模型配置状态">
              <Space wrap>
                <Tag color={modelConfig.remote_model_configured ? 'green' : 'orange'}>
                  {modelConfig.active_mode}
                </Tag>
                {modelConfig.agent_mode === 'conversational_assist' && <Tag color="blue">对话式助手</Tag>}
                <Text>供应商：{modelConfig.provider}</Text>
                <Text>模型：{modelConfig.model_name || '未配置'}</Text>
                {modelConfig.config_source && <Tag>{modelConfig.config_source === 'parser_engine_db' ? '解析引擎 DB 配置' : '环境变量'}</Tag>}
                {modelConfig.is_ollama && <Tag color="cyan">Ollama 本地</Tag>}
                <Tag color={modelConfig.api_key_configured ? 'green' : 'red'}>
                  API Key {modelConfig.api_key_configured ? '已配置' : '未配置'}
                </Tag>
                {modelConfig.local_lightweight_model_enabled && <Tag color="blue">本地轻量识别启用</Tag>}
                {modelConfig.fallback_to_rules_enabled && <Tag color="orange">不可用时回退规则识别</Tag>}
                <Link to="/parser-engine/config">前往解析引擎配置</Link>
              </Space>
            </Card>
          )}

          {caseTemplate && (
            <Card size="small" title={`${caseTemplate.template_name}：${caseTemplate.deliverable_rule.display_name}`}>
              <Space direction="vertical" style={{ width: '100%' }}>
                <Space wrap>
                  {caseTemplate.allowed_agent_roles.map((role) => <Tag key={role}>{role}</Tag>)}
                  {caseTemplate.audit_trace_required && <Tag color="blue">全流程留痕</Tag>}
                  {caseTemplate.immutable_trace_required && <Tag color="red">不可篡改要求</Tag>}
                </Space>
                <Alert type="info" showIcon title={caseTemplate.workpaper_policy} />
                <Alert type="warning" showIcon title={caseTemplate.audit_draft_policy} />
                <Text type="secondary">{caseTemplate.api_tool_policy}</Text>
                <List
                  size="small"
                  header={<Text strong>场景交付物</Text>}
                  dataSource={caseTemplate.deliverable_rule.allowed_deliverables}
                  renderItem={(item) => <List.Item>{item}</List.Item>}
                />
                <List
                  size="small"
                  header={<Text strong>案例执行步骤</Text>}
                  dataSource={caseTemplate.execution_steps}
                  renderItem={(step) => (
                    <List.Item>
                      <Space direction="vertical" style={{ width: '100%' }}>
                        <Space wrap>
                          <Text strong>{step.step_no}. {step.name}</Text>
                          <Tag>{step.agent_role}</Tag>
                          <Tag color={step.can_execute ? 'green' : 'default'}>{step.can_execute ? '允许执行' : '只规划'}</Tag>
                          <Tag color="blue">{step.output_status}</Tag>
                          {step.approval_required && <Tag color="red">人工确认</Tag>}
                        </Space>
                        <Text type="secondary">工具：{step.allowed_tools.join('、') || '无'}</Text>
                      </Space>
                    </List.Item>
                  )}
                />
              </Space>
            </Card>
          )}

          {orchestrationPlan && (
            <Card size="small" title="多 Agent 协同计划">
              <Space direction="vertical" style={{ width: '100%' }}>
                <Space wrap>
                  <Text strong>主 Agent：</Text><Tag color="purple">{orchestrationPlan.primary_agent_role}</Tag>
                  <Text strong>文件策略：</Text><Tag>{orchestrationPlan.file_access_policy}</Tag>
                  {orchestrationPlan.audit_trace_required && <Tag color="blue">所有步骤留痕</Tag>}
                </Space>
                <Text type="secondary">
                  必须人工确认：{orchestrationPlan.human_confirmation_required_for.join('、')}
                </Text>
                <List
                  size="small"
                  dataSource={orchestrationPlan.coordination_steps}
                  renderItem={(step) => (
                    <List.Item>
                      <Space direction="vertical" style={{ width: '100%' }}>
                        <Space wrap>
                          <Text strong>{step.step_no}. {step.agent_role}</Text>
                          <Tag color={step.can_execute ? 'green' : 'default'}>{step.can_execute ? '可执行' : '不可执行'}</Tag>
                          {step.approval_required && <Tag color="red">需确认</Tag>}
                          {step.audit_trace_required && <Tag color="blue">留痕</Tag>}
                        </Space>
                        <Text>{step.task}</Text>
                        <Text type="secondary">白名单工具：{step.allowed_tools.join('、') || '无'}</Text>
                        {step.approval_required && (
                          <Space wrap>
                            {step.allowed_tools.length > 0 ? (
                              <Button
                                size="small"
                                danger
                                loading={approvalLoadingKey === `request-${step.step_no}`}
                                onClick={() => void requestApproval(step)}
                              >
                                申请确认
                              </Button>
                            ) : (
                              <Tag color="red">需人工线下确认</Tag>
                            )}
                            <Text type="secondary">仅生成确认记录，不执行高风险动作。</Text>
                          </Space>
                        )}
                      </Space>
                    </List.Item>
                  )}
                />
              </Space>
            </Card>
          )}

          <Card size="small" title="人工确认记录">
            {approvalRecords.length === 0 ? (
              <Text type="secondary">暂无确认记录。点击需确认步骤中的“申请确认”后，会在这里展示待确认记录。</Text>
            ) : (
              <List
                size="small"
                dataSource={approvalRecords}
                renderItem={(approval) => (
                  <List.Item>
                    <Space direction="vertical" style={{ width: '100%' }}>
                      <Space wrap>
                        <Text strong>#{approval.id}</Text>
                        <Tag>{approval.agent_role}</Tag>
                        <Tag>{approval.tool_name}</Tag>
                        <Tag color={riskColors[approval.risk_level] || 'default'}>
                          {riskLabels[approval.risk_level] || approval.risk_level}
                        </Tag>
                        <Tag color={approval.status === 'confirmed' ? 'green' : 'orange'}>{approval.status}</Tag>
                      </Space>
                      <Text type="secondary">{approval.approval_reason}</Text>
                      <Text type="secondary">申请时间：{approval.created_at || '-'}</Text>
                      {approval.confirmed_at && <Text type="secondary">确认时间：{approval.confirmed_at}</Text>}
                      {approval.confirmation_comment && <Text type="secondary">确认意见：{approval.confirmation_comment}</Text>}
                      {approval.status === 'pending' && (
                        <Button
                          size="small"
                          type="primary"
                          loading={approvalLoadingKey === `confirm-${approval.id}`}
                          onClick={() => void confirmApproval(approval)}
                        >
                          人工确认
                        </Button>
                      )}
                      {approval.status === 'confirmed' && draftExecutableTools.has(approval.tool_name) && !draftResults[approval.id] && (
                        <Button
                          size="small"
                          type="primary"
                          loading={approvalLoadingKey === `execute-${approval.id}`}
                          onClick={() => void executeDraft(approval)}
                        >
                          生成草稿
                        </Button>
                      )}
                      {approval.status === 'confirmed' && !draftExecutableTools.has(approval.tool_name) && (
                        <Text type="secondary">该工具不属于草稿受控执行范围，仅保留确认记录。</Text>
                      )}
                      {draftResults[approval.id] && (
                        <Alert
                          type="success"
                          showIcon
                          title={`${draftResults[approval.id].result.title}（${draftResults[approval.id].output_type}）`}
                          description={
                            <Space direction="vertical">
                              <Text>{draftResults[approval.id].result.notice}</Text>
                              <Text type="secondary">
                                人工复核：{draftResults[approval.id].result.review_required ? '需要' : '不需要'}；正式交付：{draftResults[approval.id].result.formal_delivery_allowed ? '允许' : '不允许'}
                              </Text>
                            </Space>
                          }
                        />
                      )}
                      {draftResults[approval.id] && !draftReviews[approval.id] && (
                        <Button
                          size="small"
                          loading={approvalLoadingKey === `review-create-${approval.id}`}
                          onClick={() => void createDraftReview(approval.id)}
                        >
                          创建复核记录
                        </Button>
                      )}
                      {draftReviews[approval.id] && (
                        <Card size="small" title="草稿人工复核记录">
                          <Space direction="vertical" style={{ width: '100%' }}>
                            <Space wrap>
                              <Tag color={draftReviews[approval.id].review_status === 'approved' ? 'green' : draftReviews[approval.id].review_status === 'returned' ? 'red' : 'orange'}>
                                {draftReviews[approval.id].review_status}
                              </Tag>
                              {draftReviews[approval.id].returned_for_rework && <Tag color="red">退回重做</Tag>}
                              {draftReviews[approval.id].allow_formal_delivery_design && <Tag color="green">允许进入正式交付设计</Tag>}
                            </Space>
                            <Text type="secondary">复核人：{draftReviews[approval.id].reviewed_by_user_id || '-'}</Text>
                            <Text type="secondary">复核时间：{draftReviews[approval.id].reviewed_at || '-'}</Text>
                            {draftReviews[approval.id].review_comment && <Text>复核意见：{draftReviews[approval.id].review_comment}</Text>}
                            {draftReviews[approval.id].review_status === 'pending' && (
                              <>
                                <TextArea
                                  rows={2}
                                  value={reviewComments[approval.id] || ''}
                                  onChange={(event) => setReviewComments((items) => ({ ...items, [approval.id]: event.target.value }))}
                                  placeholder="请输入人工复核意见"
                                />
                                <Space wrap>
                                  <Button
                                    size="small"
                                    type="primary"
                                    loading={approvalLoadingKey === `review-submit-${approval.id}-approved`}
                                    onClick={() => void submitDraftReview(approval.id, 'approved')}
                                  >
                                    复核通过
                                  </Button>
                                  <Button
                                    size="small"
                                    danger
                                    loading={approvalLoadingKey === `review-submit-${approval.id}-returned`}
                                    onClick={() => void submitDraftReview(approval.id, 'returned')}
                                  >
                                    退回重做
                                  </Button>
                                </Space>
                              </>
                            )}
                          </Space>
                        </Card>
                      )}
                    </Space>
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Space>
      </Card>

      <Card style={{ marginBottom: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <TextArea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onPressEnter={(event) => {
              if (!event.shiftKey) {
                event.preventDefault()
                void send()
              }
            }}
            rows={3}
            placeholder="例如：列出科目表 / 查看证据收件箱 / 有哪些导入任务 / 内控待办有哪些"
          />
          <Button type="primary" icon={<SendOutlined />} loading={loading} onClick={() => void send()}>
            发送
          </Button>
        </Space>
      </Card>

      <List
        dataSource={messages}
        renderItem={(item) => (
          <List.Item>
            <Card
              size="small"
              style={{ width: '100%', background: item.role === 'user' ? '#f6ffed' : '#f5f7fa' }}
              title={item.role === 'user' ? '你' : '助手'}
            >
              <Paragraph>{item.content}</Paragraph>
              {item.result && (
                <Space direction="vertical" style={{ width: '100%' }}>
                  {item.result.intent && (
                    <Space wrap>
                      <Text strong>识别意图：</Text>
                      <Tag color="blue">{intentLabels[item.result.intent] || item.result.intent}</Tag>
                      {typeof item.result.confidence === 'number' && (
                        <Text type="secondary">建议匹配度：{Math.round(item.result.confidence * 100)}%</Text>
                      )}
                      {item.result.source === 'llm' && <Tag color="green">智能助手</Tag>}
                      {item.result.source === 'rules' && <Tag color="orange">规则回退</Tag>}
                    </Space>
                  )}
                  {item.result.model_config && (
                    <Text type="secondary">
                      模型：{item.result.model_config.model_name || '未配置'}
                      {item.result.model_config.is_ollama ? '（Ollama）' : ''}
                      {item.result.model_config.config_source ? ` · 配置来源：${item.result.model_config.config_source}` : ''}
                    </Text>
                  )}
                  {item.result.tool_executions && item.result.tool_executions.length > 0 && (
                    <Card size="small" title="已执行工具">
                      <List
                        size="small"
                        dataSource={item.result.tool_executions}
                        renderItem={(execution) => (
                          <List.Item>
                            <Space direction="vertical" style={{ width: '100%' }}>
                              <Space wrap>
                                <Tag color={execution.status === 'success' ? 'green' : 'red'}>{execution.tool_name}</Tag>
                                <Tag>{execution.status === 'success' ? '成功' : '失败'}</Tag>
                              </Space>
                              {execution.error && <Text type="danger">{execution.error}</Text>}
                              {execution.result && (
                                <pre style={{ margin: 0, maxHeight: 200, overflow: 'auto', fontSize: 12 }}>
                                  {JSON.stringify(execution.result, null, 2)}
                                </pre>
                              )}
                            </Space>
                          </List.Item>
                        )}
                      />
                    </Card>
                  )}
                  {item.result.pending_actions && item.result.pending_actions.length > 0 && (
                    <Alert
                      type="warning"
                      showIcon
                      title="待确认操作（未自动执行）"
                      description={
                        <List
                          size="small"
                          dataSource={item.result.pending_actions}
                          renderItem={(action) => (
                            <List.Item>
                              <Space wrap>
                                <Tag color={riskColors[action.risk_level || 'medium'] || 'orange'}>{action.tool_name}</Tag>
                                <Text type="secondary">{action.reason}</Text>
                              </Space>
                            </List.Item>
                          )}
                        />
                      }
                    />
                  )}
                  {item.result.suggested_path && (
                    <Alert
                      type="info"
                      showIcon
                      title={
                        <Space>
                          <span>建议路径：{item.result.suggested_path}</span>
                          <Link to={item.result.suggested_path}>立即前往</Link>
                        </Space>
                      }
                    />
                  )}
                  {item.result.steps && item.result.steps.length > 0 && (
                    <List
                      size="small"
                      header={<Text strong>步骤建议</Text>}
                      dataSource={item.result.steps}
                      renderItem={(step, index) => <List.Item>{index + 1}. {step}</List.Item>}
                    />
                  )}
                </Space>
              )}
            </Card>
          </List.Item>
        )}
      />
    </div>
  )
}
