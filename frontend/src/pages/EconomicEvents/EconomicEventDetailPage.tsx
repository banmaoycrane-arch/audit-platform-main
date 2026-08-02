import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  Button,
  Card,
  Descriptions,
  Form,
  Input,
  List,
  Modal,
  Space,
  Tabs,
  Tag,
  Timeline,
  Typography,
  message,
} from 'antd'
import {
  ArrowLeftOutlined,
  PaperClipOutlined,
  ReloadOutlined,
  LinkOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import {
  api,
  type EconomicEventDetail,
  type EconomicEventEntryLink,
  type EconomicEventFileLink,
  type EconomicEventSimilarItem,
  type EconomicEventStep,
} from '../../api/client'
import { useAuthStore } from '../../stores/authStore'
import {
  EVENT_STATUS_LABEL,
  EVENT_STATUS_COLOR,
  EVENT_TYPE_LABEL,
  EVENT_TRANSITIONS,
  EVENT_TERMINAL_STATUSES,
} from './eventConstants'

const { Title, Paragraph, Text } = Typography
const { TextArea } = Input

export function EconomicEventDetailPage() {
  const navigate = useNavigate()
  const params = useParams<{ eventId: string }>()
  const eventId = Number(params.eventId)
  const { currentLedgerId } = useAuthStore()
  const [event, setEvent] = useState<EconomicEventDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [similarEvents, setSimilarEvents] = useState<EconomicEventSimilarItem[]>([])
  const [similarMessage, setSimilarMessage] = useState<string | null>(null)
  const [similarLoading, setSimilarLoading] = useState(false)
  const [transitionModal, setTransitionModal] = useState<{ to: string } | null>(null)
  const [transitionReason, setTransitionReason] = useState('')
  const [entryModalVisible, setEntryModalVisible] = useState(false)
  const [fileModalVisible, setFileModalVisible] = useState(false)
  const [entryForm] = Form.useForm()
  const [fileForm] = Form.useForm()

  const loadSimilar = () => {
    if (!currentLedgerId || !eventId) return
    setSimilarLoading(true)
    api
      .listSimilarEconomicEvents(currentLedgerId, eventId, 5)
      .then((result) => {
        setSimilarEvents(result.results || [])
        setSimilarMessage(result.message || null)
      })
      .catch(() => {
        setSimilarEvents([])
        setSimilarMessage('相似事件推荐暂不可用')
      })
      .finally(() => setSimilarLoading(false))
  }

  const loadEvent = () => {
    if (!currentLedgerId || !eventId) return
    setLoading(true)
    api
      .getEconomicEvent(currentLedgerId, eventId)
      .then((data) => {
        setEvent(data)
        loadSimilar()
      })
      .catch((error: Error) => message.error(error.message || '加载事件详情失败'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadEvent()
  }, [currentLedgerId, eventId])

  const handleTransition = async () => {
    if (!currentLedgerId || !eventId || !transitionModal) return
    try {
      await api.transitionEconomicEvent(currentLedgerId, eventId, {
        to_status: transitionModal.to,
        reason: transitionReason || null,
      })
      message.success(`状态已推进到：${EVENT_STATUS_LABEL[transitionModal.to] || transitionModal.to}`)
      setTransitionModal(null)
      setTransitionReason('')
      loadEvent()
    } catch (error: any) {
      message.error(error.message || '状态推进失败')
    }
  }

  const handleAttachEntry = async () => {
    if (!currentLedgerId || !eventId) return
    try {
      const values = await entryForm.validateFields()
      await api.attachEconomicEventEntry(currentLedgerId, eventId, {
        accounting_entry_id: Number(values.accounting_entry_id),
        relation_type: values.relation_type || 'primary',
      })
      message.success('分录已关联')
      setEntryModalVisible(false)
      entryForm.resetFields()
      loadEvent()
    } catch (error: any) {
      if (error.errorFields) return
      message.error(error.message || '关联分录失败')
    }
  }

  const handleAttachFile = async () => {
    if (!currentLedgerId || !eventId) return
    try {
      const values = await fileForm.validateFields()
      await api.attachEconomicEventFile(currentLedgerId, eventId, {
        source_file_id: Number(values.source_file_id),
        relation_type: values.relation_type || 'evidence',
      })
      message.success('证据文件已关联')
      setFileModalVisible(false)
      fileForm.resetFields()
      loadEvent()
    } catch (error: any) {
      if (error.errorFields) return
      message.error(error.message || '关联文件失败')
    }
  }

  const renderStepColor = (step: EconomicEventStep): string => {
    if (step.step_code === 'transition') {
      if (step.to_status === 'cancelled' || step.to_status === 'failed') return 'red'
      if (step.to_status === 'posted' || step.to_status === 'closed') return 'green'
      return 'blue'
    }
    return 'gray'
  }

  const renderStepsTimeline = () => {
    if (!event || event.steps.length === 0) {
      return <Typography.Text type="secondary">暂无步骤记录</Typography.Text>
    }
    return (
      <Timeline
        items={event.steps.map((step) => ({
          color: renderStepColor(step),
          children: (
            <div>
              <Space wrap>
                <Text strong>#{step.sequence}</Text>
                <Text>{step.step_name}</Text>
                {step.from_status && step.to_status && (
                  <Tag color="blue">
                    {EVENT_STATUS_LABEL[step.from_status] || step.from_status}
                    {' → '}
                    {EVENT_STATUS_LABEL[step.to_status] || step.to_status}
                  </Tag>
                )}
                <Tag>{step.actor_type}</Tag>
                {step.model_name && <Tag color="purple">{step.model_name}</Tag>}
              </Space>
              {step.result_summary && (
                <Paragraph type="secondary" style={{ marginTop: 4, marginBottom: 0 }}>
                  {step.result_summary}
                </Paragraph>
              )}
              <Text type="secondary" style={{ fontSize: 12 }}>
                {step.api_name ? `${step.api_name} · ` : ''}
                {step.created_at ? dayjs(step.created_at).format('YYYY-MM-DD HH:mm:ss') : ''}
                {step.actor_user_id ? ` · 操作人ID=${step.actor_user_id}` : ''}
              </Text>
            </div>
          ),
        }))}
      />
    )
  }

  const renderEntriesTab = () => (
    <div>
      <div style={{ marginBottom: 12, textAlign: 'right' }}>
        <Button
          icon={<LinkOutlined />}
          onClick={() => setEntryModalVisible(true)}
          disabled={!event || EVENT_TERMINAL_STATUSES.has(event.status)}
        >
          关联分录
        </Button>
      </div>
      <List
        itemLayout="horizontal"
        dataSource={event?.entries || []}
        locale={{ emptyText: '暂未关联分录' }}
        renderItem={(item: EconomicEventEntryLink) => (
          <List.Item>
            <List.Item.Meta
              title={<Text>分录 #{item.accounting_entry_id}</Text>}
              description={
                <Space>
                  <Tag>{item.relation_type}</Tag>
                  {item.created_at && (
                    <Text type="secondary">{dayjs(item.created_at).format('YYYY-MM-DD HH:mm')}</Text>
                  )}
                </Space>
              }
            />
          </List.Item>
        )}
      />
    </div>
  )

  const renderFilesTab = () => (
    <div>
      <div style={{ marginBottom: 12, textAlign: 'right' }}>
        <Button
          icon={<PaperClipOutlined />}
          onClick={() => setFileModalVisible(true)}
          disabled={!event || EVENT_TERMINAL_STATUSES.has(event.status)}
        >
          关联证据
        </Button>
      </div>
      <List
        itemLayout="horizontal"
        dataSource={event?.files || []}
        locale={{ emptyText: '暂未关联证据文件' }}
        renderItem={(item: EconomicEventFileLink) => (
          <List.Item>
            <List.Item.Meta
              title={<Text>文件 #{item.source_file_id}</Text>}
              description={
                <Space>
                  <Tag>{item.relation_type}</Tag>
                  {item.created_at && (
                    <Text type="secondary">{dayjs(item.created_at).format('YYYY-MM-DD HH:mm')}</Text>
                  )}
                </Space>
              }
            />
          </List.Item>
        )}
      />
    </div>
  )

  const renderSimilarTab = () => (
    <div>
      <Space style={{ marginBottom: 12 }}>
        <Button loading={similarLoading} onClick={loadSimilar}>
          刷新相似推荐
        </Button>
        <Text type="secondary">基于本账簿事件叙述的向量推荐（仅供参考）</Text>
      </Space>
      {similarMessage && (
        <Paragraph type="secondary" style={{ marginBottom: 8 }}>
          {similarMessage}
        </Paragraph>
      )}
      <List
        loading={similarLoading}
        itemLayout="horizontal"
        dataSource={similarEvents}
        locale={{ emptyText: '暂无相似历史事件' }}
        renderItem={(item: EconomicEventSimilarItem) => (
          <List.Item
            actions={[
              <Button
                key="open"
                type="link"
                onClick={() => navigate(`/ledger/events/${item.event_id}`)}
              >
                打开
              </Button>,
            ]}
          >
            <List.Item.Meta
              title={
                <Space wrap>
                  <Text strong>{item.event_no}</Text>
                  <Text>{item.title}</Text>
                  <Tag color={EVENT_STATUS_COLOR[item.status] || 'default'}>
                    {EVENT_STATUS_LABEL[item.status] || item.status}
                  </Tag>
                </Space>
              }
              description={
                <Space direction="vertical" size={0}>
                  <Text type="secondary">
                    {EVENT_TYPE_LABEL[item.event_type] || item.event_type}
                    {item.score != null ? ` · 相似度 ${(item.score * 100).toFixed(1)}%` : ''}
                  </Text>
                  {item.summary && <Text type="secondary">{item.summary}</Text>}
                </Space>
              }
            />
          </List.Item>
        )}
      />
    </div>
  )

  const tabItems = [
    { key: 'steps', label: '状态时间轴', children: renderStepsTimeline() },
    { key: 'entries', label: `关联分录 (${event?.entries.length || 0})`, children: renderEntriesTab() },
    { key: 'files', label: `证据文件 (${event?.files.length || 0})`, children: renderFilesTab() },
    { key: 'similar', label: `相似事件 (${similarEvents.length})`, children: renderSimilarTab() },
  ]

  if (!eventId) {
    return (
      <Card>
        <Typography.Text type="danger">事件 ID 无效，请从列表重新进入。</Typography.Text>
      </Card>
    )
  }

  if (!currentLedgerId) {
    return (
      <Card>
        <Typography.Text type="warning">请先选择账簿。</Typography.Text>
      </Card>
    )
  }

  if (!event) {
    return (
      <Card loading={loading}>
        <Typography.Text type="secondary">事件不存在或加载中。</Typography.Text>
      </Card>
    )
  }

  const allowedNext = EVENT_TRANSITIONS[event.status] || []

  return (
    <div>
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/ledger/events')} type="link">
          返回事件列表
        </Button>

        <Card
          title={
            <Space wrap>
              <Title level={4} style={{ margin: 0 }}>{event.title}</Title>
              <Tag color={EVENT_STATUS_COLOR[event.status] || 'default'}>
                {EVENT_STATUS_LABEL[event.status] || event.status}
              </Tag>
              <Tag>{EVENT_TYPE_LABEL[event.event_type] || event.event_type}</Tag>
            </Space>
          }
          extra={
            <Button icon={<ReloadOutlined />} onClick={loadEvent} loading={loading}>
              刷新
            </Button>
          }
        >
          <Descriptions column={2} bordered size="small">
            <Descriptions.Item label="事件编号">{event.event_no}</Descriptions.Item>
            <Descriptions.Item label="来源">
              <Tag>{event.source}</Tag>
              {event.source_id ? ` #${event.source_id}` : ''}
            </Descriptions.Item>
            <Descriptions.Item label="业务发生日">
              {event.occurred_on ? dayjs(event.occurred_on).format('YYYY-MM-DD') : '-'}
            </Descriptions.Item>
            <Descriptions.Item label="金额合计">
              {event.display_amount
                ? `${Number(event.display_amount).toLocaleString('zh-CN', { minimumFractionDigits: 2 })} ${event.currency}`
                : '-（未关联分录）'}
            </Descriptions.Item>
            <Descriptions.Item label="分录数">{event.entry_count}</Descriptions.Item>
            <Descriptions.Item label="证据数">{event.file_count}</Descriptions.Item>
            <Descriptions.Item label="创建人">用户 #{event.created_by ?? '-'}</Descriptions.Item>
            <Descriptions.Item label="负责人">
              {event.assignee_user_id ? `用户 #${event.assignee_user_id}` : '未指派'}
            </Descriptions.Item>
            <Descriptions.Item label="创建时间">
              {event.created_at ? dayjs(event.created_at).format('YYYY-MM-DD HH:mm') : '-'}
            </Descriptions.Item>
            <Descriptions.Item label="关闭时间">
              {event.closed_at ? dayjs(event.closed_at).format('YYYY-MM-DD HH:mm') : '-'}
            </Descriptions.Item>
            {event.summary && (
              <Descriptions.Item label="事件叙述" span={2}>{event.summary}</Descriptions.Item>
            )}
          </Descriptions>

          <Space style={{ marginTop: 16 }} wrap>
            {allowedNext.map((to) => {
              const isNegative = to === 'cancelled' || to === 'failed'
              const isPositive = to === 'posted' || to === 'closed' || to === 'pending_post'
              return (
                <Button
                  key={to}
                  type={isPositive ? 'primary' : 'default'}
                  danger={isNegative}
                  icon={isPositive ? <CheckCircleOutlined /> : isNegative ? <CloseCircleOutlined /> : undefined}
                  onClick={() => {
                    setTransitionModal({ to })
                    setTransitionReason('')
                  }}
                >
                  推进到「{EVENT_STATUS_LABEL[to] || to}」
                </Button>
              )
            })}
            {allowedNext.length === 0 && (
              <Typography.Text type="secondary">当前为终态，不可再推进。</Typography.Text>
            )}
          </Space>
        </Card>

        <Card>
          <Tabs defaultActiveKey="steps" items={tabItems} />
        </Card>
      </Space>

      <Modal
        title={`状态推进：${EVENT_STATUS_LABEL[event.status]} → ${EVENT_STATUS_LABEL[transitionModal?.to || ''] || ''}`}
        open={!!transitionModal}
        onOk={handleTransition}
        onCancel={() => {
          setTransitionModal(null)
          setTransitionReason('')
        }}
        okText="确认推进"
        cancelText="取消"
      >
        <Form.Item label="备注原因" labelCol={{ span: 4 }} wrapperCol={{ span: 20 }}>
          <TextArea
            rows={3}
            value={transitionReason}
            onChange={(e) => setTransitionReason(e.target.value)}
            placeholder="推进原因（可选，会记入步骤日志）"
            maxLength={300}
            showCount
          />
        </Form.Item>
      </Modal>

      <Modal
        title="关联分录"
        open={entryModalVisible}
        onOk={handleAttachEntry}
        onCancel={() => {
          setEntryModalVisible(false)
          entryForm.resetFields()
        }}
        okText="关联"
        cancelText="取消"
        destroyOnClose
      >
        <Form form={entryForm} layout="vertical" initialValues={{ relation_type: 'primary' }}>
          <Form.Item
            name="accounting_entry_id"
            label="分录 ID"
            rules={[{ required: true, message: '请输入分录 ID' }]}
          >
            <Input type="number" placeholder="输入要关联的分录 ID" />
          </Form.Item>
          <Form.Item name="relation_type" label="关系类型">
            <Input placeholder="primary / secondary / ..." />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="关联证据文件"
        open={fileModalVisible}
        onOk={handleAttachFile}
        onCancel={() => {
          setFileModalVisible(false)
          fileForm.resetFields()
        }}
        okText="关联"
        cancelText="取消"
        destroyOnClose
      >
        <Form form={fileForm} layout="vertical" initialValues={{ relation_type: 'evidence' }}>
          <Form.Item
            name="source_file_id"
            label="源文件 ID"
            rules={[{ required: true, message: '请输入源文件 ID' }]}
          >
            <Input type="number" placeholder="输入要关联的源文件 ID" />
          </Form.Item>
          <Form.Item name="relation_type" label="关系类型">
            <Input placeholder="evidence / attachment / ..." />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
