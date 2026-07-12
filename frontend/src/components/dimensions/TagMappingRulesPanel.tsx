import { useCallback, useEffect, useState } from 'react'
import {
  Alert,
  Button,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { DeleteOutlined, PlusOutlined, ReloadOutlined } from '@ant-design/icons'
import { api, type TagMappingRule } from '../../api/client'

const SOURCE_TYPE_OPTIONS = [
  { value: 'account_code', label: 'account_code · 科目编码' },
  { value: 'summary', label: 'summary · 摘要' },
  { value: 'tag', label: 'tag · 外部标签' },
]

type TagMappingRulesPanelProps = {
  ledgerId: number
  categoryCodes: string[]
}

export function TagMappingRulesPanel({ ledgerId, categoryCodes }: TagMappingRulesPanelProps) {
  const [rules, setRules] = useState<TagMappingRule[]>([])
  const [loading, setLoading] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [createForm] = Form.useForm()

  const loadRules = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.listTagMappingRules(ledgerId)
      setRules(data)
    } catch (error) {
      message.error(error instanceof Error ? error.message : '加载映射规则失败')
    } finally {
      setLoading(false)
    }
  }, [ledgerId])

  useEffect(() => {
    void loadRules()
  }, [loadRules])

  const handleCreate = async () => {
    const values = await createForm.validateFields()
    await api.createTagMappingRule(ledgerId, values)
    message.success('映射规则已创建')
    setCreateOpen(false)
    createForm.resetFields()
    void loadRules()
  }

  const handleToggleActive = async (rule: TagMappingRule) => {
    await api.updateTagMappingRule(rule.id, { is_active: !rule.is_active })
    void loadRules()
  }

  const handleDelete = (rule: TagMappingRule) => {
    Modal.confirm({
      title: '删除映射规则？',
      content: `${rule.source_type}: ${rule.source_pattern} → ${rule.target_category_code}`,
      okType: 'danger',
      onOk: async () => {
        await api.deleteTagMappingRule(rule.id)
        message.success('已删除')
        void loadRules()
      },
    })
  }

  const categoryOptions = categoryCodes.map((code) => ({ value: code, label: code }))

  const columns: ColumnsType<TagMappingRule> = [
    { title: '来源类型', dataIndex: 'source_type', width: 110 },
    { title: '来源模式', dataIndex: 'source_pattern', ellipsis: true },
    {
      title: '目标分类',
      dataIndex: 'target_category_code',
      width: 130,
      render: (v: string) => <Tag color="blue">{v}</Tag>,
    },
    { title: '目标值', dataIndex: 'target_value', ellipsis: true, render: (v) => v || '-' },
    { title: '优先级', dataIndex: 'priority', width: 72 },
    {
      title: '正则',
      dataIndex: 'is_regex',
      width: 56,
      render: (v: boolean) => (v ? '是' : '否'),
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      width: 80,
      render: (active: boolean) => (
        <Tag color={active ? 'green' : 'default'}>{active ? '启用' : '停用'}</Tag>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 140,
      render: (_, row) => (
        <Space size={4}>
          <Button type="link" size="small" onClick={() => void handleToggleActive(row)}>
            {row.is_active ? '停用' : '启用'}
          </Button>
          <Button type="link" size="small" danger icon={<DeleteOutlined />} onClick={() => handleDelete(row)}>
            删除
          </Button>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="外部映射规则（ERP 科目段 / 摘要 / 自由标签 → 内部维度）"
        description="用于将外部财务软件编码或辅助核算项映射到本系统 TagCategory。优先级高的规则先匹配。"
      />

      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
          新建规则
        </Button>
        <Button icon={<ReloadOutlined />} onClick={() => void loadRules()} loading={loading}>
          刷新
        </Button>
      </Space>

      <Table rowKey="id" size="small" loading={loading} columns={columns} dataSource={rules} pagination={{ pageSize: 20 }} />

      <Modal title="新建外部映射规则" open={createOpen} onOk={() => void handleCreate()} onCancel={() => setCreateOpen(false)} okText="保存">
        <Form
          form={createForm}
          layout="vertical"
          initialValues={{ source_type: 'account_code', priority: 10, is_regex: false }}
        >
          <Form.Item name="source_type" label="来源类型" rules={[{ required: true }]}>
            <Select options={SOURCE_TYPE_OPTIONS} />
          </Form.Item>
          <Form.Item name="source_pattern" label="来源模式" rules={[{ required: true }]}>
            <Input placeholder="如 100201 或 招商银行" />
          </Form.Item>
          <Form.Item name="target_category_code" label="目标 Tag 分类" rules={[{ required: true }]}>
            <Select showSearch options={categoryOptions} placeholder="bank_account / customer / service ..." />
          </Form.Item>
          <Form.Item name="target_value" label="目标维度值（可选）">
            <Input placeholder="映射后的 display_name / tag_value" />
          </Form.Item>
          <Form.Item name="priority" label="优先级">
            <InputNumber min={0} max={999} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="is_regex" label="正则匹配" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name="description" label="说明">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
