import { useEffect, useState } from 'react'
import { Card, Table, Button, Modal, Form, Input, Select, Space, Tag, message } from 'antd'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

type Counterparty = {
  id: number
  name: string
  role: string
  unified_credit_no: string | null
  is_related_party: boolean
  default_entity_id: number | null
  is_active: boolean
}

const ROLE_LABEL: Record<string, string> = {
  customer: '客户',
  supplier: '供应商',
  related_party: '关联方',
  government: '政府/税务',
  individual: '个人',
  internal: '内部',
  other: '其他',
}

export function CounterpartiesPage() {
  const [list, setList] = useState<Counterparty[]>([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const [form] = Form.useForm()

  const load = async () => {
    setLoading(true)
    try {
      const resp = await fetch(`${API_BASE}/api/counterparties`)
      setList(await resp.json())
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void load() }, [])

  const handleCreate = async () => {
    const values = await form.validateFields()
    const resp = await fetch(`${API_BASE}/api/counterparties`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(values),
    })
    if (!resp.ok) {
      message.error(`创建失败：${await resp.text()}`)
      return
    }
    setOpen(false)
    form.resetFields()
    await load()
    message.success('已创建')
  }

  const handleDisable = async (id: number) => {
    await fetch(`${API_BASE}/api/counterparties/${id}/disable`, { method: 'POST' })
    await load()
  }

  return (
    <Card title="对方单位" extra={<Button type="primary" onClick={() => setOpen(true)}>新增</Button>}>
      <Table
        rowKey="id"
        dataSource={list}
        loading={loading}
        size="small"
        pagination={{ pageSize: 20 }}
        columns={[
          { title: 'ID', dataIndex: 'id', key: 'id' },
          { title: '名称', dataIndex: 'name', key: 'name' },
          { title: '角色', dataIndex: 'role', key: 'role', render: (v: string) => ROLE_LABEL[v] || v },
          { title: '统一社会信用代码', dataIndex: 'unified_credit_no', key: 'unified_credit_no', render: (v: string | null) => v || '-' },
          {
            title: '关联方',
            dataIndex: 'is_related_party',
            key: 'is_related_party',
            render: (v: boolean) => (v ? <Tag color="red">是</Tag> : <Tag>否</Tag>),
          },
          {
            title: '状态',
            dataIndex: 'is_active',
            key: 'is_active',
            render: (v: boolean) => (v ? <Tag color="green">启用</Tag> : <Tag color="default">已停用</Tag>),
          },
          {
            title: '操作',
            key: 'action',
            render: (_: unknown, row: Counterparty) => (
              <Space>
                <Button size="small" onClick={() => handleDisable(row.id)} disabled={!row.is_active}>停用</Button>
              </Space>
            ),
          },
        ]}
      />
      <Modal title="新增对方单位" open={open} onOk={handleCreate} onCancel={() => setOpen(false)} okText="创建">
        <Form form={form} layout="vertical" initialValues={{ role: 'customer' }}>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="role" label="角色" rules={[{ required: true }]}>
            <Select options={Object.entries(ROLE_LABEL).map(([k, v]) => ({ value: k, label: v }))} />
          </Form.Item>
          <Form.Item name="unified_credit_no" label="统一社会信用代码">
            <Input />
          </Form.Item>
          <Form.Item name="is_related_party" label="是否关联方" valuePropName="checked">
            <input type="checkbox" />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  )
}
