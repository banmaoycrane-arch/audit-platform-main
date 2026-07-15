import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Form,
  Input,
  Modal,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Timeline,
  Typography,
  message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import {
  ApiOutlined,
  PlusOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
  SwapOutlined,
} from '@ant-design/icons'
import { WorkspaceShell } from '../../components/WorkspaceShell'
import { Link } from 'react-router-dom'
import {
  api,
  type TaxEgressBinding,
  type TaxEgressCityPool,
  type TaxEgressNode,
  type TaxEgressPoolsResponse,
  type TaxRotationEvent,
} from '../../api/client'
import { useAuthStore } from '../../stores/authStore'

const { Paragraph, Text } = Typography

const NODE_STATUS: Record<string, { color: string; label: string }> = {
  active: { color: 'green', label: '可用' },
  warming: { color: 'blue', label: '预热' },
  cooling: { color: 'orange', label: '冷却' },
  blocked: { color: 'red', label: '封禁' },
}

const SESSION_STATE: Record<string, { color: string; label: string }> = {
  idle: { color: 'default', label: '未登录' },
  need_qr: { color: 'gold', label: '待扫码' },
  active: { color: 'green', label: '会话有效' },
  expired: { color: 'red', label: '已过期' },
}

const functionsList = [
  { key: 'workspace', icon: <ApiOutlined />, label: '税务工作台', path: '/tax/workspace' },
  { key: 'bookkeeping', icon: <ApiOutlined />, label: '记账导入（主线）', path: '/ledger/vouchers/step/1' },
]

export function TaxConnectionPage() {
  const { currentLedgerId } = useAuthStore()
  const [cityCode, setCityCode] = useState('330100')
  const [cityPool, setCityPool] = useState<TaxEgressCityPool | null>(null)
  const [poolConfig, setPoolConfig] = useState<TaxEgressPoolsResponse['config'] | null>(null)
  const [bindings, setBindings] = useState<TaxEgressBinding[]>([])
  const [events, setEvents] = useState<TaxRotationEvent[]>([])
  const [cityOptions, setCityOptions] = useState<Array<{ value: string; label: string }>>([])
  const [loading, setLoading] = useState(false)
  const [rotateModal, setRotateModal] = useState<TaxEgressBinding | null>(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [createForm] = Form.useForm()

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [pools, bindingRes, eventRes] = await Promise.all([
        api.getTaxEgressPools(cityCode),
        api.listTaxEgressBindings(cityCode, currentLedgerId),
        api.listTaxRotationEvents(20),
      ])
      setPoolConfig(pools.config)
      setCityOptions(pools.cities.map((c) => ({ value: c.city_code, label: c.city_name })))
      setCityPool(pools.cities.find((c) => c.city_code === cityCode) ?? pools.cities[0] ?? null)
      if (!pools.cities.find((c) => c.city_code === cityCode) && pools.cities[0]) {
        setCityCode(pools.cities[0].city_code)
      }
      setBindings(bindingRes.items)
      setEvents(eventRes.items)
    } catch (error) {
      message.error(error instanceof Error ? error.message : '加载税务连接失败')
    } finally {
      setLoading(false)
    }
  }, [cityCode, currentLedgerId])

  useEffect(() => {
    void loadData()
  }, [loadData])

  const poolStats = useMemo(() => {
    if (!cityPool) return { active: 0, total: 0, slots: 0 }
    return {
      active: cityPool.stats.active_nodes,
      total: cityPool.stats.total_nodes,
      slots: cityPool.stats.remaining_slots,
    }
  }, [cityPool])

  const bindingColumns: ColumnsType<TaxEgressBinding> = [
    { title: '纳税主体', dataIndex: 'taxpayer_name', key: 'name' },
    { title: '税号', dataIndex: 'taxpayer_id', key: 'tid', width: 200 },
    {
      title: '绑定出口 IP',
      key: 'ip',
      render: (_, row) => (
        <Space direction="vertical" size={0}>
          <Text code>{row.egress_ip || '—'}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>节点 {row.node_key || row.node_id}</Text>
        </Space>
      ),
    },
    {
      title: '7 日轮换',
      dataIndex: 'rotate_count_7d',
      key: 'rot',
      width: 90,
      render: (v: number) => <Tag color={v >= (poolConfig?.max_rotate_per_taxpayer_7d ?? 2) ? 'red' : 'default'}>{v} 次</Tag>,
    },
    {
      title: '会话',
      key: 'session',
      render: (_, row) => {
        const s = SESSION_STATE[row.session_state] || { color: 'default', label: row.session_state }
        return <Tag color={s.color}>{s.label}</Tag>
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 220,
      render: (_, row) => (
        <Space>
          <Button
            size="small"
            type="primary"
            loading={loading}
            onClick={() => void handleStartSession(row.id)}
          >
            登录税局
          </Button>
          <Button size="small" icon={<SwapOutlined />} onClick={() => setRotateModal(row)}>
            轮换 IP
          </Button>
        </Space>
      ),
    },
  ]

  const poolColumns: ColumnsType<TaxEgressNode> = [
    { title: '出口 IP', dataIndex: 'egress_ip', key: 'ip', render: (v) => <Text code>{v}</Text> },
    { title: '线路', dataIndex: 'provider', key: 'provider' },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (s: string) => {
        const meta = NODE_STATUS[s] || { color: 'default', label: s }
        return <Tag color={meta.color}>{meta.label}</Tag>
      },
    },
    { title: '负载', key: 'load', render: (_, row) => `${row.load} / ${row.max_tenants}` },
    {
      title: '健康分',
      dataIndex: 'health_score',
      key: 'health',
      render: (v: number) => `${Math.round(v * 100)}%`,
    },
  ]

  const handleStartSession = async (bindingId: number) => {
    try {
      const result = await api.startTaxEgressSession(bindingId)
      message.info(result.message)
      await loadData()
    } catch (error) {
      message.error(error instanceof Error ? error.message : '发起会话失败')
    }
  }

  const handleRotate = async () => {
    if (!rotateModal) return
    try {
      await api.rotateTaxEgressBinding(rotateModal.id, '管理员手动轮换')
      message.success('IP 已轮换，需重新扫码登录')
      setRotateModal(null)
      await loadData()
    } catch (error) {
      message.error(error instanceof Error ? error.message : '轮换失败')
    }
  }

  const handleCreateBinding = async () => {
    try {
      const values = await createForm.validateFields()
      await api.createTaxEgressBinding(
        {
          taxpayer_id: values.taxpayer_id,
          taxpayer_name: values.taxpayer_name,
          city_code: values.city_code || cityCode,
        },
        currentLedgerId,
      )
      message.success('纳税主体已绑定城市出口 IP')
      setCreateOpen(false)
      createForm.resetFields()
      await loadData()
    } catch (error) {
      if (error instanceof Error) message.error(error.message)
    }
  }

  return (
    <WorkspaceShell
      title="税局直连（代开票/取票）"
      description="可选增值：仅当客户明确要求代操作电子税务局时启用。记账请使用财务总账文件导入，无需开通本功能。"
      functionsList={functionsList}
    >
      <Alert
        type="info"
        showIcon
        title="可选增值，记账无需开通"
        description={(
          <span>
            代账「只做记账、客户只给文件」请走
            <Link to="/ledger/vouchers/step/1"> 序时簿导入 </Link>
            。本页用于未来「按城市绑 IP + Worker 扫码登录税局」；当前 Phase 1 仅管理池与绑定，未接真实税局。
          </span>
        )}
        style={{ marginBottom: 16 }}
      />

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col xs={24} md={8}>
          <Card>
            <Statistic title="城市池可用节点" value={poolStats.active} suffix={`/ ${poolStats.total}`} />
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card>
            <Statistic title="剩余绑定槽位" value={poolStats.slots} />
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card>
            <Statistic title="轮换策略" value="粘性 + 故障转移" />
          </Card>
        </Col>
      </Row>

      <Card
        title="城市 IP 池"
        loading={loading}
        extra={(
          <Space>
            <Select style={{ width: 160 }} value={cityCode} onChange={setCityCode} options={cityOptions} />
            <Button icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>新增绑定</Button>
            <Button icon={<ReloadOutlined />} onClick={() => void loadData()}>刷新</Button>
          </Space>
        )}
        style={{ marginBottom: 16 }}
      >
        <Table
          rowKey="id"
          size="small"
          pagination={false}
          columns={poolColumns}
          dataSource={cityPool?.nodes ?? []}
        />
        <Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 0 }}>
          <SafetyCertificateOutlined /> 策略 <Text code>sticky_with_failover</Text>
          {poolConfig ? ` · 冷却 ${poolConfig.cooling_hours}h · 7日轮换上限 ${poolConfig.max_rotate_per_taxpayer_7d} 次` : null}
        </Paragraph>
      </Card>

      <Card title="纳税主体绑定" loading={loading} style={{ marginBottom: 16 }}>
        <Table rowKey="id" size="small" columns={bindingColumns} dataSource={bindings} pagination={false} />
      </Card>

      <Row gutter={16}>
        <Col xs={24} lg={14}>
          <Card title="轮换策略说明">
            <Descriptions column={1} size="small" bordered>
              <Descriptions.Item label="默认模式">sticky_with_failover</Descriptions.Item>
              <Descriptions.Item label="种子数据">TAX_EGRESS_SEED_ENABLED=true 时自动创建演示城市池</Descriptions.Item>
              <Descriptions.Item label="生产真实 IP">关闭种子后通过管理接口或 SQL 写入 tax_egress_nodes</Descriptions.Item>
              <Descriptions.Item label="Worker">tax_egress_nodes.worker_host 指向地区 Worker 地址</Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title="最近轮换事件" loading={loading}>
            <Timeline
              items={events.map((e) => ({
                color: e.trigger.includes('health') || e.trigger.includes('T1') ? 'orange' : 'blue',
                children: (
                  <div>
                    <Text strong>{e.time}</Text>
                    <br />
                    <Text type="secondary">{e.taxpayer_id}</Text>
                    <br />
                    <Text>{e.old_ip} → <Text code>{e.new_ip}</Text></Text>
                    <br />
                    <Tag>{e.trigger}</Tag>
                    {e.detail && <div style={{ fontSize: 12, color: '#666' }}>{e.detail}</div>}
                  </div>
                ),
              }))}
            />
          </Card>
        </Col>
      </Row>

      <Modal title="新增纳税主体绑定" open={createOpen} onCancel={() => setCreateOpen(false)} onOk={() => void handleCreateBinding()}>
        <Form form={createForm} layout="vertical" initialValues={{ city_code: cityCode }}>
          <Form.Item name="taxpayer_name" label="企业名称" rules={[{ required: true }]}>
            <Input placeholder="杭州示例科技有限公司" />
          </Form.Item>
          <Form.Item name="taxpayer_id" label="统一社会信用代码/税号" rules={[{ required: true, min: 15 }]}>
            <Input placeholder="91330100MA2XXXX001" />
          </Form.Item>
          <Form.Item name="city_code" label="主管税务机关城市" rules={[{ required: true }]}>
            <Select options={cityOptions} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal title="手动轮换出口 IP" open={Boolean(rotateModal)} onCancel={() => setRotateModal(null)} onOk={() => void handleRotate()} okText="确认轮换">
        {rotateModal && (
          <Space direction="vertical">
            <Text>主体：{rotateModal.taxpayer_name}</Text>
            <Text>当前 IP：<Text code>{rotateModal.egress_ip}</Text></Text>
            <Alert type="warning" showIcon message="轮换后需重新扫码登录税局" />
          </Space>
        )}
      </Modal>
    </WorkspaceShell>
  )
}
