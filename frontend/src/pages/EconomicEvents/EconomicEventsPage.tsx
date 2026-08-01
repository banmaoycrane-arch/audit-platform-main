import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Button,
  Card,
  DatePicker,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import { PlusOutlined, ReloadOutlined, ThunderboltOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import {
  api,
  type EconomicEvent,
} from '../../api/client'
import { useAuthStore } from '../../stores/authStore'
import {
  EVENT_STATUS_LABEL,
  EVENT_STATUS_COLOR,
  EVENT_TYPE_LABEL,
  EVENT_TYPE_OPTIONS,
  EVENT_STATUS_OPTIONS,
} from './eventConstants'

const { Title, Paragraph, Text } = Typography
const { TextArea } = Input

const PAGE_SIZE = 20

export function EconomicEventsPage() {
  const navigate = useNavigate()
  const { currentLedgerId } = useAuthStore()
  const [events, setEvents] = useState<EconomicEvent[]>([])
  const [loading, setLoading] = useState(false)
  const [statusFilter, setStatusFilter] = useState<string | undefined>()
  const [typeFilter, setTypeFilter] = useState<string | undefined>()
  const [keyword, setKeyword] = useState('')
  const [modalVisible, setModalVisible] = useState(false)
  const [createForm] = Form.useForm()

  const loadEvents = () => {
    if (!currentLedgerId) return
    setLoading(true)
    api
      .listEconomicEvents(currentLedgerId, {
        status: statusFilter,
        event_type: typeFilter,
        keyword: keyword || undefined,
        offset: 0,
        limit: 200,
      })
      .then((rows) => setEvents(rows))
      .catch((error: Error) => message.error(error.message || '加载事件列表失败'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadEvents()
  }, [currentLedgerId, statusFilter, typeFilter, keyword])

  const handleCreate = async () => {
    if (!currentLedgerId) return
    try {
      const values = await createForm.validateFields()
      await api.createEconomicEvent(currentLedgerId, {
        title: values.title,
        event_type: values.event_type || 'manual',
        occurred_on: values.occurred_on ? values.occurred_on.format('YYYY-MM-DD') : null,
        summary: values.summary || null,
      })
      message.success('事件工单已创建')
      setModalVisible(false)
      createForm.resetFields()
      loadEvents()
    } catch (error: any) {
      if (error.errorFields) return
      message.error(error.message || '创建失败')
    }
  }

  const columns = [
    {
      title: '事件编号',
      dataIndex: 'event_no',
      key: 'event_no',
      width: 180,
      render: (value: string) => <Text strong>{value}</Text>,
    },
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true,
    },
    {
      title: '类型',
      dataIndex: 'event_type',
      key: 'event_type',
      width: 120,
      render: (value: string) => <Tag>{EVENT_TYPE_LABEL[value] || value}</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 110,
      render: (value: string) => (
        <Tag color={EVENT_STATUS_COLOR[value] || 'default'}>
          {EVENT_STATUS_LABEL[value] || value}
        </Tag>
      ),
    },
    {
      title: '金额合计',
      dataIndex: 'display_amount',
      key: 'display_amount',
      width: 140,
      align: 'right' as const,
      render: (value: string | null, row: EconomicEvent) =>
        value ? `${Number(value).toLocaleString('zh-CN', { minimumFractionDigits: 2 })} ${row.currency}` : '-',
    },
    {
      title: '分录/证据',
      key: 'counts',
      width: 100,
      align: 'center' as const,
      render: (_: unknown, row: EconomicEvent) => `${row.entry_count} / ${row.file_count}`,
    },
    {
      title: '发生日',
      dataIndex: 'occurred_on',
      key: 'occurred_on',
      width: 120,
      render: (value: string | null) => (value ? dayjs(value).format('YYYY-MM-DD') : '-'),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (value: string | null) => (value ? dayjs(value).format('YYYY-MM-DD HH:mm') : '-'),
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_: unknown, row: EconomicEvent) => (
        <Button size="small" type="link" onClick={() => navigate(`/ledger/events/${row.id}`)}>
          查看详情
        </Button>
      ),
    },
  ]

  if (!currentLedgerId) {
    return (
      <Card>
        <Typography.Text type="warning">
          请先选择账簿后再查看经济事件工单。
        </Typography.Text>
      </Card>
    )
  }

  return (
    <div>
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <Title level={4} style={{ margin: 0 }}>
              <ThunderboltOutlined /> 经济事件工单
            </Title>
            <Paragraph type="secondary" style={{ marginBottom: 0 }}>
              以「事件」聚合分录与证据，按状态机推进：草稿 → 归集 → 复核 → 入账 → 关闭。
            </Paragraph>
          </div>
          <Space>
            <Button icon={<ReloadOutlined />} onClick={loadEvents} loading={loading}>
              刷新
            </Button>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => setModalVisible(true)}
            >
              新建事件
            </Button>
          </Space>
        </div>

        <Card size="small">
          <Space wrap>
            <span>状态：</span>
            <Select
              style={{ width: 140 }}
              value={statusFilter}
              onChange={setStatusFilter}
              options={EVENT_STATUS_OPTIONS}
              placeholder="全部状态"
              allowClear
            />
            <span>类型：</span>
            <Select
              style={{ width: 150 }}
              value={typeFilter}
              onChange={setTypeFilter}
              options={EVENT_TYPE_OPTIONS}
              placeholder="全部类型"
              allowClear
            />
            <span>关键词：</span>
            <Input.Search
              style={{ width: 220 }}
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              onSearch={loadEvents}
              placeholder="搜索事件标题"
              allowClear
            />
          </Space>
        </Card>

        <Card title="事件列表">
          <Table
            rowKey="id"
            loading={loading}
            columns={columns}
            dataSource={events}
            pagination={{ pageSize: PAGE_SIZE, showSizeChanger: false }}
            locale={{ emptyText: '暂无事件工单' }}
          />
        </Card>
      </Space>

      <Modal
        title="新建经济事件"
        open={modalVisible}
        onOk={handleCreate}
        onCancel={() => {
          setModalVisible(false)
          createForm.resetFields()
        }}
        okText="创建"
        cancelText="取消"
        destroyOnClose
      >
        <Form form={createForm} layout="vertical" initialValues={{ event_type: 'manual' }}>
          <Form.Item
            name="title"
            label="事件标题"
            rules={[{ required: true, message: '请输入事件标题' }]}
          >
            <Input placeholder="例如：8 月工资发放" maxLength={300} />
          </Form.Item>
          <Form.Item name="event_type" label="事件类型">
            <Select options={EVENT_TYPE_OPTIONS} placeholder="请选择类型" />
          </Form.Item>
          <Form.Item name="occurred_on" label="业务发生日">
            <DatePicker style={{ width: '100%' }} placeholder="选择发生日" />
          </Form.Item>
          <Form.Item name="summary" label="事件叙述">
            <TextArea rows={3} placeholder="可检索的事件摘要（供后续向量检索）" maxLength={500} showCount />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
