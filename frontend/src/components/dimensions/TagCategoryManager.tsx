import { useCallback, useEffect, useMemo, useState } from 'react'
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
  Typography,
  message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import {
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
  StopOutlined,
  CheckCircleOutlined,
  InboxOutlined,
} from '@ant-design/icons'
import { Link } from 'react-router-dom'
import { api, type TagCategoryNode } from '../../api/client'

const { Text } = Typography

type FlatCategory = TagCategoryNode & { depth: number }

const STATUS_LABEL: Record<string, string> = {
  active: '启用',
  disabled: '禁用',
  archived: '归档',
}

const STATUS_COLOR: Record<string, string> = {
  active: 'green',
  disabled: 'orange',
  archived: 'default',
}

const VALUE_TYPE_OPTIONS = [
  { value: 'text', label: 'text · 文本' },
  { value: 'entity', label: 'entity · 关联主数据' },
  { value: 'enum', label: 'enum · 枚举' },
  { value: 'number', label: 'number · 数值' },
  { value: 'date', label: 'date · 日期' },
  { value: 'boolean', label: 'boolean · 布尔' },
]

const SOURCE_TABLE_OPTIONS = [
  { value: '', label: '无' },
  { value: 'counterparties', label: 'counterparties · 往来单位' },
  { value: 'bank_accounts', label: 'bank_accounts · 银行账户' },
  { value: 'organization_units', label: 'organization_units · 组织部门' },
]

function flattenCategories(nodes: TagCategoryNode[], depth = 0): FlatCategory[] {
  const rows: FlatCategory[] = []
  for (const node of nodes) {
    rows.push({ ...node, depth })
    if (node.children?.length) {
      rows.push(...flattenCategories(node.children, depth + 1))
    }
  }
  return rows
}

function collectParentOptions(nodes: TagCategoryNode[]): Array<{ value: number; label: string }> {
  const options: Array<{ value: number; label: string }> = []
  const walk = (items: TagCategoryNode[], prefix = '') => {
    for (const item of items) {
      const label = `${prefix}${item.name} (${item.code})`
      options.push({ value: item.id, label })
      if (item.children?.length) walk(item.children, `${label} / `)
    }
  }
  walk(nodes)
  return options
}

type TagCategoryManagerProps = {
  ledgerId: number
  onChanged?: () => void
}

export function TagCategoryManager({ ledgerId, onChanged }: TagCategoryManagerProps) {
  const [categories, setCategories] = useState<TagCategoryNode[]>([])
  const [loading, setLoading] = useState(false)
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'disabled' | 'archived'>('all')
  const [createOpen, setCreateOpen] = useState(false)
  const [editOpen, setEditOpen] = useState(false)
  const [editing, setEditing] = useState<FlatCategory | null>(null)
  const [createForm] = Form.useForm()
  const [editForm] = Form.useForm()

  const fetchCategories = useCallback(
    async (statusOverride?: typeof statusFilter) => {
      const effectiveStatus = statusOverride ?? statusFilter
      setLoading(true)
      try {
        const data = await api.listTagCategories(ledgerId, { status: effectiveStatus })
        setCategories(data)
      } catch (error) {
        message.error(error instanceof Error ? error.message : '加载维度分类失败')
      } finally {
        setLoading(false)
      }
    },
    [ledgerId, statusFilter],
  )

  useEffect(() => {
    void fetchCategories()
  }, [fetchCategories])

  const flatRows = useMemo(() => flattenCategories(categories), [categories])
  const parentOptions = useMemo(() => collectParentOptions(categories), [categories])

  const notifyChanged = (statusOverride?: typeof statusFilter) => {
    void fetchCategories(statusOverride)
    onChanged?.()
  }

  const handleCreate = async () => {
    try {
      const values = await createForm.validateFields()
      await api.createTagCategory(ledgerId, {
        ...values,
        parent_id: values.parent_id ?? null,
        source_table: values.source_table || undefined,
      })
      message.success('维度分类已创建')
      setCreateOpen(false)
      createForm.resetFields()
      const nextFilter =
        statusFilter !== 'all' && statusFilter !== 'active' ? 'active' : statusFilter
      if (nextFilter !== statusFilter) {
        setStatusFilter(nextFilter)
      }
      await fetchCategories(nextFilter)
      onChanged?.()
    } catch (error) {
      if (error && typeof error === 'object' && 'errorFields' in error) {
        return
      }
      message.error(error instanceof Error ? error.message : '创建维度分类失败')
    }
  }

  const openEdit = (row: FlatCategory) => {
    setEditing(row)
    editForm.setFieldsValue({
      name: row.name,
      description: row.description || '',
      value_type: row.value_type,
      source_table: row.source_table || '',
      is_mandatory: row.is_mandatory,
      sort_order: row.sort_order ?? 0,
      status: row.status || 'active',
    })
    setEditOpen(true)
  }

  const handleUpdate = async () => {
    if (!editing) return
    const values = await editForm.validateFields()
    await api.updateTagCategory(editing.id, {
      ...values,
      source_table: values.source_table || '',
    })
    message.success('维度分类已更新')
    setEditOpen(false)
    setEditing(null)
    notifyChanged()
  }

  const handleDelete = (row: FlatCategory) => {
    if (row.is_system) {
      message.warning('系统内置分类不可删除，请改为禁用或归档')
      return
    }
    Modal.confirm({
      title: `删除维度分类「${row.name}」？`,
      content: '仅当无子分类且未被引用时可删除。建议优先使用禁用或归档。',
      okType: 'danger',
      onOk: async () => {
        try {
          await api.deleteTagCategory(row.id)
          message.success('已删除')
          notifyChanged()
        } catch (error) {
          message.error(error instanceof Error ? error.message : '删除失败')
        }
      },
    })
  }

  const handleQuickStatus = async (row: FlatCategory, status: string) => {
    try {
      await api.updateTagCategory(row.id, { status })
      message.success(`已设为${STATUS_LABEL[status] || status}`)
      notifyChanged()
    } catch (error) {
      message.error(error instanceof Error ? error.message : '更新状态失败')
    }
  }

  const columns: ColumnsType<FlatCategory> = [
    {
      title: '编码',
      dataIndex: 'code',
      width: 160,
      render: (code: string, row) => (
        <span style={{ paddingLeft: row.depth * 16 }}>
          <Text code>{code}</Text>
        </span>
      ),
    },
    { title: '名称', dataIndex: 'name', ellipsis: true },
    { title: '值类型', dataIndex: 'value_type', width: 88 },
    {
      title: '主数据表',
      dataIndex: 'source_table',
      width: 120,
      render: (v?: string | null) => v || '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 80,
      render: (status: string) => <Tag color={STATUS_COLOR[status] || 'default'}>{STATUS_LABEL[status] || status}</Tag>,
    },
    {
      title: '标记',
      key: 'flags',
      width: 100,
      render: (_, row) => (
        <Space size={4}>
          {row.is_system && <Tag color="blue">系统</Tag>}
          {row.is_mandatory && <Tag color="orange">必填</Tag>}
        </Space>
      ),
    },
    { title: '排序', dataIndex: 'sort_order', width: 64 },
    {
      title: '操作',
      key: 'actions',
      width: 220,
      render: (_, row) => (
        <Space size={4} wrap>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => openEdit(row)}>
            编辑
          </Button>
          {row.status !== 'active' && (
            <Button
              type="link"
              size="small"
              icon={<CheckCircleOutlined />}
              onClick={() => void handleQuickStatus(row, 'active')}
            >
              启用
            </Button>
          )}
          {row.status === 'active' && (
            <Button
              type="link"
              size="small"
              icon={<StopOutlined />}
              onClick={() => void handleQuickStatus(row, 'disabled')}
            >
              禁用
            </Button>
          )}
          {row.status !== 'archived' && (
            <Button
              type="link"
              size="small"
              icon={<InboxOutlined />}
              onClick={() => void handleQuickStatus(row, 'archived')}
            >
              归档
            </Button>
          )}
          <Button
            type="link"
            size="small"
            danger
            icon={<DeleteOutlined />}
            disabled={row.is_system}
            onClick={() => handleDelete(row)}
          >
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
        message="维度分类是 Tag 体系的「字典」"
        description={
          <div>
            <div>解析映射中的 category_code 须与本表一致；序时簿导入时会自动创建系统分类。</div>
            <div style={{ marginTop: 4 }}>
              本表展示的是<strong>分类字典</strong>（如 expense_type、tax_type），展开后不会出现具体维度值。
              费用类型、税费类型等具体取值请在
              <Link to="/ledger/dimensions?tab=master-values"> 维度值主数据 </Link>
              中查看与维护。
            </div>
            <div style={{ marginTop: 4 }}>
              <strong>编码约定：</strong>
              <code>bank_account</code> 仅货币资金(1001/1002)；
              <code>customer</code>/<code>supplier</code> 用于 1122/2202 等往来；
              勿再用易混淆的 <code>account_detail</code>。
              <code>product</code> 与 <code>service</code> 区分商品与服务型收入。
            </div>
            <div style={{ marginTop: 4 }}>
              可点击「新建分类」添加企业<strong>自定义 Tag</strong>（snake_case 编码）。
              同一分录可挂多个 Tag（如 6602 同时有 expense_type + department + 自定义 business_line），
              解析映射 / 外部映射配好规则后即可做口径切换，无需为每个模块单独建表。
            </div>
            <div style={{ marginTop: 4 }}>
              银行存款户名等管理维度请用
              <Link to="/ledger/dimensions?tab=parse-mapping"> 解析映射 </Link>
              + 开户清单，勿在
              <Link to="/ledger/dimensions?tab=coa"> 科目表 </Link>
              大量建下级户名科目。
            </div>
          </div>
        }
      />

      <Space wrap style={{ marginBottom: 16 }}>
        <span>状态筛选</span>
        <Select
          style={{ width: 120 }}
          value={statusFilter}
          onChange={setStatusFilter}
          options={[
            { value: 'all', label: '全部' },
            { value: 'active', label: '启用' },
            { value: 'disabled', label: '禁用' },
            { value: 'archived', label: '归档' },
          ]}
        />
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
          新建分类
        </Button>
      </Space>

      <Table
        rowKey="id"
        size="small"
        loading={loading}
        columns={columns}
        dataSource={flatRows}
        pagination={{ pageSize: 20, showSizeChanger: true }}
        locale={{ emptyText: '暂无维度分类，可手动新建或先导入序时簿自动创建' }}
      />

      <Modal
        title="新建维度分类"
        open={createOpen}
        destroyOnClose
        onOk={() => void handleCreate()}
        onCancel={() => setCreateOpen(false)}
        okText="保存"
      >
        <Form form={createForm} layout="vertical" initialValues={{ value_type: 'text', sort_order: 0, is_mandatory: false }}>
          <Form.Item name="code" label="编码" rules={[{ required: true, message: '请输入 snake_case 编码' }]}>
            <Input placeholder="如 product_line" />
          </Form.Item>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="如 产品线" />
          </Form.Item>
          <Form.Item name="description" label="说明">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="parent_id" label="父分类">
            <Select allowClear placeholder="无（顶级）" options={parentOptions} />
          </Form.Item>
          <Form.Item name="value_type" label="值类型">
            <Select options={VALUE_TYPE_OPTIONS} />
          </Form.Item>
          <Form.Item name="source_table" label="主数据来源表">
            <Select options={SOURCE_TABLE_OPTIONS} />
          </Form.Item>
          <Form.Item name="is_mandatory" label="是否必填" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name="sort_order" label="排序号">
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={editing ? `编辑 · ${editing.code}` : '编辑维度分类'}
        open={editOpen}
        onOk={() => void handleUpdate()}
        onCancel={() => {
          setEditOpen(false)
          setEditing(null)
        }}
        okText="保存"
      >
        <Form form={editForm} layout="vertical">
          <Form.Item label="编码">
            <Input value={editing?.code} disabled />
          </Form.Item>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="description" label="说明">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="value_type" label="值类型">
            <Select options={VALUE_TYPE_OPTIONS} />
          </Form.Item>
          <Form.Item name="source_table" label="主数据来源表">
            <Select options={SOURCE_TABLE_OPTIONS} />
          </Form.Item>
          <Form.Item name="is_mandatory" label="是否必填" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name="sort_order" label="排序号">
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="status" label="状态">
            <Select
              options={[
                { value: 'active', label: '启用' },
                { value: 'disabled', label: '禁用' },
                { value: 'archived', label: '归档' },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
