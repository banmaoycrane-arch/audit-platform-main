import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Alert, Button, Card, Col, Collapse, List, Row, Select, Space, Tag, Typography, Input, message } from 'antd'
import { ReloadOutlined, SendOutlined } from '@ant-design/icons'
import { api, type AgentAssistResponse } from '../api/client'
import { useAuthStore } from '../stores/authStore'
import { createAgentSessionId, trackSuggestedPathClick } from '../utils/productAnalytics'
import './AgentChatPage.css'

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
  const [agentSessionId] = useState(() => createAgentSessionId())
  const [agentRoundIndex, setAgentRoundIndex] = useState(0)
  const [suggestedPathAt, setSuggestedPathAt] = useState<number | null>(null)
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
    const roundIndex = agentRoundIndex + 1
    setAgentRoundIndex(roundIndex)
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
        sessionId: agentSessionId,
        roundIndex,
      })
      if (result.suggested_path) {
        setSuggestedPathAt(Date.now())
      }
      setMessages((items) => [...items, { role: 'assistant', content: result.reply, result }])
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error)
      message.error(`Agent 助手请求失败：${detail}`)
    } finally {
      setLoading(false)
    }
  }

  const lastAssistantResult = useMemo(() => {
    for (let index = messages.length - 1; index >= 0; index -= 1) {
      const item = messages[index]
      if (item.role === 'assistant' && item.result) {
        return item.result
      }
    }
    return null
  }, [messages])

  const renderMessageMeta = (result: AgentAssistResponse) => (
    <Space direction="vertical" style={{ width: '100%', marginTop: 8 }} size="small">
      {result.intent && (
        <Space wrap size={[4, 4]}>
          <Tag color="blue">{intentLabels[result.intent] || result.intent}</Tag>
          {typeof result.confidence === 'number' && (
            <Text type="secondary" style={{ fontSize: 12 }}>
              匹配 {Math.round(result.confidence * 100)}%
            </Text>
          )}
          {result.source === 'llm' && <Tag color="green">智能</Tag>}
          {result.source === 'rules' && <Tag color="orange">规则</Tag>}
        </Space>
      )}
      {result.suggested_path && (
        <Alert
          type="info"
          showIcon
          style={{ padding: '6px 10px' }}
          message={
            <Space size="small" wrap>
              <span>建议：{result.suggested_path}</span>
              <Link
                to={result.suggested_path}
                onClick={() => {
                  const seconds = suggestedPathAt ? Math.round((Date.now() - suggestedPathAt) / 1000) : 0
                  trackSuggestedPathClick(agentSessionId, result.suggested_path!, seconds)
                }}
              >
                前往
              </Link>
            </Space>
          }
        />
      )}
      {result.tool_executions && result.tool_executions.length > 0 && (
        <Collapse
          size="small"
          items={[{
            key: 'tools',
            label: `已执行工具（${result.tool_executions.length}）`,
            children: (
              <List
                size="small"
                dataSource={result.tool_executions}
                renderItem={(execution) => (
                  <List.Item style={{ padding: '4px 0' }}>
                    <Space direction="vertical" style={{ width: '100%' }} size={2}>
                      <Space wrap size={4}>
                        <Tag color={execution.status === 'success' ? 'green' : 'red'}>{execution.tool_name}</Tag>
                      </Space>
                      {execution.error && <Text type="danger" style={{ fontSize: 12 }}>{execution.error}</Text>}
                    </Space>
                  </List.Item>
                )}
              />
            ),
          }]}
        />
      )}
    </Space>
  )

  return (
    <div className="agent-console-page">
      <div className="agent-console-header">
        <Title level={3} style={{ marginBottom: 4 }}>Agent 助手</Title>
        <Paragraph type="secondary" style={{ marginBottom: 0 }}>
          中间对话直接调用后端 API；右侧查看场景、交付物与待办提醒。
          {currentLedgerId ? ` 当前账簿：${currentLedgerId}` : ' 请先选择账簿。'}
          {' '}
          <Link to="/mvp-metrics">MVP 验证看板</Link>
        </Paragraph>
      </div>

      <Row gutter={16} align="stretch">
        <Col xs={24} lg={16} xl={17} className="agent-chat-column">
          <Card
            className="agent-chat-card"
            title="对话"
            extra={
              <Button size="small" loading={loading} disabled={!input.trim()} type="primary" icon={<SendOutlined />} onClick={() => void send()}>
                发送
              </Button>
            }
          >
            <div className="agent-chat-messages">
              {messages.map((item, index) => (
                <div key={`${item.role}-${index}`} className={`agent-chat-message ${item.role}`}>
                  <div className="agent-chat-bubble">
                    <div className="agent-chat-bubble-role">{item.role === 'user' ? '你' : '助手'}</div>
                    <Paragraph style={{ marginBottom: 0 }}>{item.content}</Paragraph>
                    {item.result && renderMessageMeta(item.result)}
                  </div>
                </div>
              ))}
            </div>
            <div className="agent-chat-input-bar">
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
                placeholder="例如：列出科目表 / 查看证据收件箱 / 我还没有团队怎么开始"
              />
            </div>
          </Card>
        </Col>

        <Col xs={24} lg={8} xl={7} className="agent-side-column">
          <Card
            size="small"
            className="agent-side-card"
            title="运行状态"
            extra={
              <Button type="link" size="small" icon={<ReloadOutlined />} loading={controlLoading} onClick={() => void loadAgentControls()}>
                刷新
              </Button>
            }
          >
            {modelConfig ? (
              <Space direction="vertical" size={6} style={{ width: '100%' }}>
                <Space wrap size={[4, 4]}>
                  <Tag color={modelConfig.remote_model_configured ? 'green' : 'orange'}>{modelConfig.active_mode}</Tag>
                  {modelConfig.agent_mode === 'conversational_assist' && <Tag color="blue">对话式</Tag>}
                  {modelConfig.is_ollama && <Tag color="cyan">Ollama</Tag>}
                </Space>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {modelConfig.model_name || '未配置模型'} · {modelConfig.config_source === 'parser_engine_db' ? 'DB' : 'ENV'}
                </Text>
                <Link to="/parser-engine/config" style={{ fontSize: 12 }}>解析引擎配置</Link>
              </Space>
            ) : (
              <Text type="secondary" style={{ fontSize: 12 }}>加载中…</Text>
            )}
          </Card>

          <Card size="small" className="agent-side-card" title="场景与交付物">
            <Space direction="vertical" size={8} style={{ width: '100%' }}>
              <Select
                size="small"
                style={{ width: '100%' }}
                value={caseScenario}
                options={caseScenarioOptions}
                onChange={(value) => {
                  setCaseScenario(value)
                  void loadAgentControls(value, orchestrationTask)
                }}
              />
              <Select
                size="small"
                style={{ width: '100%' }}
                value={orchestrationTask}
                options={orchestrationTaskOptions}
                onChange={(value) => {
                  setOrchestrationTask(value)
                  void loadAgentControls(caseScenario, value)
                }}
              />
              {caseTemplate && (
                <>
                  <Text strong style={{ fontSize: 12 }}>{caseTemplate.deliverable_rule.display_name}</Text>
                  <div>
                    {caseTemplate.deliverable_rule.allowed_deliverables.map((item) => (
                      <Tag key={item} className="agent-deliverable-tag">{item}</Tag>
                    ))}
                  </div>
                </>
              )}
            </Space>
          </Card>

          <Card size="small" className="agent-side-card" title="提醒与待确认">
            {lastAssistantResult?.pending_actions && lastAssistantResult.pending_actions.length > 0 && (
              <div style={{ marginBottom: 10 }}>
                {lastAssistantResult.pending_actions.map((action, index) => (
                  <div key={`pending-${index}`} className="agent-reminder-item">
                    <Tag color={riskColors[action.risk_level || 'medium'] || 'orange'} style={{ marginBottom: 4 }}>
                      {action.tool_name}
                    </Tag>
                    <div style={{ fontSize: 12 }}>{action.reason}</div>
                  </div>
                ))}
              </div>
            )}
            {lastAssistantResult?.suggested_path && (
              <Alert
                type="info"
                showIcon
                style={{ marginBottom: 10, padding: '6px 10px' }}
                message={
                  <Link
                    to={lastAssistantResult.suggested_path}
                    onClick={() => {
                      const seconds = suggestedPathAt ? Math.round((Date.now() - suggestedPathAt) / 1000) : 0
                      trackSuggestedPathClick(agentSessionId, lastAssistantResult.suggested_path!, seconds)
                    }}
                  >
                    前往 {lastAssistantResult.suggested_path}
                  </Link>
                }
              />
            )}
            {approvalRecords.length === 0 ? (
              <Text type="secondary" style={{ fontSize: 12 }}>暂无人工确认记录</Text>
            ) : (
              <List
                className="agent-side-compact-list"
                size="small"
                dataSource={approvalRecords.slice(0, 5)}
                renderItem={(approval) => (
                  <List.Item>
                    <Space direction="vertical" size={2} style={{ width: '100%' }}>
                      <Space wrap size={4}>
                        <Text strong style={{ fontSize: 12 }}>#{approval.id}</Text>
                        <Tag color={approval.status === 'confirmed' ? 'green' : 'orange'}>{approval.status}</Tag>
                      </Space>
                      <Text type="secondary" style={{ fontSize: 11 }}>{approval.tool_name}</Text>
                      {approval.status === 'pending' && (
                        <Button
                          size="small"
                          type="link"
                          style={{ padding: 0, height: 'auto' }}
                          loading={approvalLoadingKey === `confirm-${approval.id}`}
                          onClick={() => void confirmApproval(approval)}
                        >
                          确认
                        </Button>
                      )}
                      {approval.status === 'confirmed' && draftExecutableTools.has(approval.tool_name) && !draftResults[approval.id] && (
                        <Button
                          size="small"
                          type="link"
                          style={{ padding: 0, height: 'auto' }}
                          loading={approvalLoadingKey === `execute-${approval.id}`}
                          onClick={() => void executeDraft(approval)}
                        >
                          生成草稿
                        </Button>
                      )}
                    </Space>
                  </List.Item>
                )}
              />
            )}
          </Card>

          {(orchestrationPlan || caseTemplate) && (
            <Collapse
              size="small"
              items={[
                orchestrationPlan ? {
                  key: 'orchestration',
                  label: `协同步骤（${orchestrationPlan.coordination_steps.length}）`,
                  children: (
                    <List
                      className="agent-side-compact-list"
                      size="small"
                      dataSource={orchestrationPlan.coordination_steps}
                      renderItem={(step) => (
                        <List.Item>
                          <Space direction="vertical" size={2} style={{ width: '100%' }}>
                            <Text style={{ fontSize: 12 }}>{step.step_no}. {step.task}</Text>
                            {step.approval_required && step.allowed_tools.length > 0 && (
                              <Button
                                size="small"
                                danger
                                loading={approvalLoadingKey === `request-${step.step_no}`}
                                onClick={() => void requestApproval(step)}
                              >
                                申请确认
                              </Button>
                            )}
                          </Space>
                        </List.Item>
                      )}
                    />
                  ),
                } : null,
                caseTemplate ? {
                  key: 'policy',
                  label: '场景策略说明',
                  children: (
                    <Space direction="vertical" size={6} style={{ width: '100%' }}>
                      <Text style={{ fontSize: 12 }}>{caseTemplate.workpaper_policy}</Text>
                      <Text type="secondary" style={{ fontSize: 11 }}>{caseTemplate.api_tool_policy}</Text>
                    </Space>
                  ),
                } : null,
              ].filter(Boolean) as { key: string; label: string; children: ReactNode }[]}
            />
          )}

          {approvalRecords.some((item) => draftResults[item.id] || draftReviews[item.id]) && (
            <Collapse
              size="small"
              items={[{
                key: 'drafts',
                label: '草稿与复核',
                children: (
                  <List
                    className="agent-side-compact-list"
                    size="small"
                    dataSource={approvalRecords.filter((item) => draftResults[item.id] || draftReviews[item.id])}
                    renderItem={(approval) => (
                      <List.Item>
                        <Space direction="vertical" size={4} style={{ width: '100%' }}>
                          <Text strong style={{ fontSize: 12 }}>#{approval.id}</Text>
                          {draftResults[approval.id] && (
                            <Text style={{ fontSize: 11 }}>{draftResults[approval.id].result.title}</Text>
                          )}
                          {draftResults[approval.id] && !draftReviews[approval.id] && approval.status === 'confirmed' && (
                            <Button size="small" loading={approvalLoadingKey === `review-create-${approval.id}`} onClick={() => void createDraftReview(approval.id)}>
                              创建复核
                            </Button>
                          )}
                          {draftReviews[approval.id]?.review_status === 'pending' && (
                            <>
                              <TextArea
                                rows={2}
                                size="small"
                                value={reviewComments[approval.id] || ''}
                                onChange={(event) => setReviewComments((items) => ({ ...items, [approval.id]: event.target.value }))}
                              />
                              <Space size={4}>
                                <Button size="small" type="primary" loading={approvalLoadingKey === `review-submit-${approval.id}-approved`} onClick={() => void submitDraftReview(approval.id, 'approved')}>
                                  通过
                                </Button>
                                <Button size="small" danger loading={approvalLoadingKey === `review-submit-${approval.id}-returned`} onClick={() => void submitDraftReview(approval.id, 'returned')}>
                                  退回
                                </Button>
                              </Space>
                            </>
                          )}
                        </Space>
                      </List.Item>
                    )}
                  />
                ),
              }]}
            />
          )}
        </Col>
      </Row>
    </div>
  )
}
