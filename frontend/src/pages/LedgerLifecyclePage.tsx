import { useEffect, useState } from 'react'
import { Card, Typography, Table, Button, Space, Tag, message, Row, Col, Statistic, Modal, Input } from 'antd'
import {
  BookOutlined,
  PlayCircleOutlined,
  PauseCircleOutlined,
  CheckCircleOutlined,
  RedoOutlined,
  CloseCircleOutlined,
  InboxOutlined,
} from '@ant-design/icons'
import { api } from '../api/client'
import type { Ledger } from '../api/client'

const { Title, Paragraph } = Typography

const ledgerStatusColorMap: Record<string, string> = {
  draft: 'default',
  active: 'success',
  suspended: 'warning',
  archived: 'error',
  deleted: 'red',
}

const ledgerStatusLabelMap: Record<string, string> = {
  draft: '草稿',
  active: '活跃',
  suspended: '暂停',
  archived: '归档',
  deleted: '删除',
}

export function LedgerLifecyclePage() {
  const [ledgers, setLedgers] = useState<Ledger[]>([])
  const [loading, setLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState<Record<number, boolean>>({})
  const [reasonModal, setReasonModal] = useState<{
    open: boolean
    ledgerId: number | null
    action: string
    title: string
  }>({ open: false, ledgerId: null, action: '', title: '' })
  const [reason, setReason] = useState('')

  useEffect(() => {
    setLoading(true)
    api
      .listLedgers()
      .then((res) => {
        setLedgers(res)
      })
      .catch(() => {
        message.error('加载账簿列表失败')
      })
      .finally(() => setLoading(false))
  }, [])

  const handleLifecycleAction = async (ledgerId: number, action: string) => {
    const titles: Record<string, string> = {
      activate: '激活账簿',
      suspend: '暂停账簿',
      archive: '归档账簿',
      restore: '恢复账簿',
    }
    setReasonModal({ open: true, ledgerId, action, title: titles[action] || action })
  }

  const confirmAction = async () => {
    if (!reasonModal.ledgerId || !reasonModal.action) return
    setActionLoading((prev) => ({ ...prev, [reasonModal.ledgerId!]: true }))
    try {
      const endpoint = `/api/ledgers/${reasonModal.ledgerId}/${reasonModal.action}`
      const response = await fetch(`${api.baseUrl}${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('token')}`,
        },
        body: JSON.stringify({ reason: reason || undefined }),
      })
      if (!response.ok) {
        throw new Error(await response.text())
      }
      const updated = await response.json()
      setLedgers((prev) =>
        prev.map((l) => (l.id === updated.id ? { ...l, status: updated.status } : l))
      )
      message.success(`${reasonModal.title}成功`)
    } catch (err: any) {
      message.error(`${reasonModal.title}失败：${err.message}`)
    } finally {
      setActionLoading((prev) => ({ ...prev, [reasonModal.ledgerId!]: false }))
      setReasonModal({ open: false, ledgerId: null, action: '', title: '' })
      setReason('')
    }
  }

  const getAvailableActions = (status: string) => {
    switch (status) {
      case 'draft':
        return ['activate']
      case 'active':
        return ['suspend', 'archive']
      case 'suspended':
        return ['activate', 'archive']
      case 'archived':
        return ['restore']
      default:
        return []
    }
  }

  const actionButtonMap: Record<string, { icon: React.ReactNode; label: string; danger?: boolean }> = {
    activate: { icon: <PlayCircleOutlined />, label: '激活' },
    suspend: { icon: <PauseCircleOutlined />, label: '暂停' },
    archive: { icon: <InboxOutlined />, label: '归档' },
    restore: { icon: <RedoOutlined />, label: '恢复' },
  }

  const columns = [
    { title: '账簿名称', dataIndex: 'name', key: 'name' },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (s: string) => {
        const color = ledgerStatusColorMap[s] || 'default'
        const label = ledgerStatusLabelMap[s] || s
        return <Tag color={color}>{label}</Tag>
      },
    },
    { title: '角色', dataIndex: 'role', key: 'role' },
    {
      title: '默认',
      dataIndex: 'is_default',
      key: 'is_default',
      render: (v: boolean) => (v ? <Tag color="blue">默认</Tag> : '-'),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (v: string) => v || '-',
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, record: Ledger) => {
        const actions = getAvailableActions(record.status)
        return (
          <Space size="small">
            {actions.map((action) => {
              const btn = actionButtonMap[action]
              return (
                <Button
                  key={action}
                  type="link"
                  size="small"
                  danger={btn.danger}
                  icon={btn.icon}
                  loading={actionLoading[record.id]}
                  onClick={() => handleLifecycleAction(record.id, action)}
                >
                  {btn.label}
                </Button>
              )
            })}
          </Space>
        )
      },
    },
  ]

  const activeCount = ledgers.filter((l) => l.status === 'active').length
  const suspendedCount = ledgers.filter((l) => l.status === 'suspended').length
  const archivedCount = ledgers.filter((l) => l.status === 'archived').length
  const draftCount = ledgers.filter((l) => l.status === 'draft').length

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Title level={4} style={{ margin: 0 }}>
            <BookOutlined /> 账簿生命周期管理
          </Title>
          <Paragraph type="secondary">管理账簿的生命周期状态：激活、暂停、归档、恢复</Paragraph>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card>
            <Statistic title="活跃账簿" value={activeCount} valueStyle={{ color: '#52c41a' }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="草稿账簿" value={draftCount} valueStyle={{ color: '#8c8c8c' }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="暂停账簿" value={suspendedCount} valueStyle={{ color: '#faad14' }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="归档账簿" value={archivedCount} valueStyle={{ color: '#ff4d4f' }} />
          </Card>
        </Col>
      </Row>

      <Card>
        <Table
          rowKey="id"
          columns={columns}
          dataSource={ledgers}
          loading={loading}
          pagination={{ pageSize: 10 }}
          locale={{ emptyText: '暂无账簿数据' }}
        />
      </Card>

      <Modal
        title={reasonModal.title}
        open={reasonModal.open}
        onOk={confirmAction}
        onCancel={() => {
          setReasonModal({ open: false, ledgerId: null, action: '', title: '' })
          setReason('')
        }}
        okText="确认"
        cancelText="取消"
      >
        <p>请填写操作原因（可选）：</p>
        <Input.TextArea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="例如：年度审计结束，归档账簿..."
          rows={3}
        />
      </Modal>
    </div>
  )
}
