import { useEffect, useState } from 'react'
import { Alert, Button, Card, Empty, Form, Input, Modal, Select, Space, Statistic, Switch, Table, Tag, Typography, message } from 'antd'

const { Text } = Typography

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

type IndustryTemplate = {
  code: string
  name: string
  description: string
}

type TemplateAccount = {
  code: string
  name: string
  parent_code: string | null
  level: number
  category: string
  direction: string
  is_terminal: boolean
  import_status?: 'new' | 'skipped' | 'conflict'
}

type TemplatePreview = IndustryTemplate & {
  accounts: TemplateAccount[]
  summary: {
    new: number
    skipped: number
    conflicts: number
  }
}

type Account = {
  code: string
  name: string
  parent_code: string | null
  level: number
  category: string
  direction: string
  account_category?: string | null
  account_subcategory?: string | null
  equity_subcategory?: string | null
  include_in_dividend_base?: boolean | null
  is_terminal: boolean
  status: string
  is_system: boolean
}

const CATEGORY_LABEL: Record<string, string> = {
  asset: '资产',
  liability: '负债',
  common: '共同',
  equity: '权益',
  cost: '成本',
  profit: '损益',
}

const ACCOUNT_CATEGORY_OPTIONS = [
  { value: '资产', label: '资产' },
  { value: '负债', label: '负债' },
  { value: '所有者权益', label: '所有者权益' },
]

const ACCOUNT_SUBCATEGORY_OPTIONS: Record<string, Array<{ value: string; label: string }>> = {
  资产: [
    { value: '流动资产', label: '流动资产' },
    { value: '非流动资产', label: '非流动资产' },
  ],
  负债: [
    { value: '流动负债', label: '流动负债' },
    { value: '长期负债', label: '长期负债' },
  ],
}

const EQUITY_SUBCATEGORY_OPTIONS = [
  { value: '注册资本', label: '注册资本' },
  { value: '资本公积', label: '资本公积' },
  { value: '盈余公积', label: '盈余公积' },
  { value: '未分配利润', label: '未分配利润' },
]

const ACCOUNT_CATEGORY_TO_SYSTEM_CATEGORY: Record<string, string> = {
  资产: 'asset',
  负债: 'liability',
  所有者权益: 'equity',
}

function getAccountingGuide(accountCategory?: string, equitySubcategory?: string) {
  if (accountCategory === '资产') {
    return '资产细类按流动性区分：预计一年内变现、出售或耗用的列为流动资产；超过一年或一个正常营业周期才收回或使用的列为非流动资产。'
  }
  if (accountCategory === '负债') {
    return '负债细类按偿还期限区分：预计一年内清偿的列为流动负债；偿还期限超过一年的列为长期负债。'
  }
  if (accountCategory === '所有者权益') {
    if (equitySubcategory === '未分配利润') {
      return '未分配利润通常是可分红口径的起点，可按本企业章程、弥补亏损和利润分配限制设置是否纳入可分红基础。'
    }
    return '所有者权益细分注册资本、资本公积、盈余公积、未分配利润；注册资本、资本公积、盈余公积默认不纳入可分红基础。'
  }
  return '请选择科目大类后，系统会按当前选择提供核算口径辅导。'
}

export function ChartOfAccountsPage() {
  const [list, setList] = useState<Account[]>([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const [presetOpen, setPresetOpen] = useState(false)
  const [templates, setTemplates] = useState<IndustryTemplate[]>([])
  const [selectedTemplateCode, setSelectedTemplateCode] = useState<string>()
  const [templatePreview, setTemplatePreview] = useState<TemplatePreview | null>(null)
  const [presetLoading, setPresetLoading] = useState(false)
  const [form] = Form.useForm()
  const accountCategory = Form.useWatch('account_category', form)
  const equitySubcategory = Form.useWatch('equity_subcategory', form)

  const load = async () => {
    setLoading(true)
    try {
      const resp = await fetch(`${API_BASE}/api/coa`)
      const data = await resp.json()
      setList(data)
    } catch (error) {
      message.error('加载科目失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void load() }, [])

  const openPresetModal = async () => {
    setPresetOpen(true)
    setPresetLoading(true)
    try {
      const resp = await fetch(`${API_BASE}/api/coa/industry-templates`)
      setTemplates(await resp.json())
    } catch (error) {
      message.error('加载行业预设失败')
    } finally {
      setPresetLoading(false)
    }
  }

  const handlePreviewTemplate = async (templateCode: string) => {
    setSelectedTemplateCode(templateCode)
    setPresetLoading(true)
    try {
      const resp = await fetch(`${API_BASE}/api/coa/industry-templates/${templateCode}`)
      if (!resp.ok) {
        message.error(`预览失败：${await resp.text()}`)
        return
      }
      setTemplatePreview(await resp.json())
    } finally {
      setPresetLoading(false)
    }
  }

  const handleImportTemplate = async () => {
    if (!selectedTemplateCode) return
    setPresetLoading(true)
    try {
      const resp = await fetch(`${API_BASE}/api/coa/industry-templates/${selectedTemplateCode}/import`, { method: 'POST' })
      if (!resp.ok) {
        message.error(`导入失败：${await resp.text()}`)
        return
      }
      const result = await resp.json()
      message.success(`导入完成：新增 ${result.summary.new} 个，跳过 ${result.summary.skipped} 个，冲突 ${result.summary.conflicts} 个`)
      setPresetOpen(false)
      setTemplatePreview(null)
      setSelectedTemplateCode(undefined)
      await load()
    } finally {
      setPresetLoading(false)
    }
  }

  const openCreateModal = () => {
    form.resetFields()
    setOpen(true)
  }

  const handleCreate = async () => {
    const values = await form.validateFields()
    const payload = {
      ...values,
      category: ACCOUNT_CATEGORY_TO_SYSTEM_CATEGORY[values.account_category],
      include_in_dividend_base:
        values.equity_subcategory === '未分配利润'
          ? values.include_in_dividend_base ?? true
          : values.account_category === '所有者权益'
            ? false
            : null,
    }
    const resp = await fetch(`${API_BASE}/api/coa`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
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

  const handleStatusChange = async (code: string, action: 'disable' | 'archive') => {
    const resp = await fetch(`${API_BASE}/api/coa/${code}/${action}`, { method: 'POST' })
    if (!resp.ok) {
      message.error(await resp.text())
      return
    }
    await load()
  }

  const handleDelete = async (code: string) => {
    const resp = await fetch(`${API_BASE}/api/coa/${code}`, { method: 'DELETE' })
    if (!resp.ok) {
      message.error(await resp.text())
      return
    }
    await load()
  }

  const handleAccountCategoryChange = (value: string) => {
    form.setFieldsValue({
      category: ACCOUNT_CATEGORY_TO_SYSTEM_CATEGORY[value],
      account_subcategory: undefined,
      equity_subcategory: undefined,
      include_in_dividend_base: value === '所有者权益' ? false : undefined,
    })
  }

  const handleEquitySubcategoryChange = (value: string) => {
    form.setFieldsValue({ include_in_dividend_base: value === '未分配利润' })
  }

  const columns = [
    { title: '代码', dataIndex: 'code', key: 'code' },
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '类别', dataIndex: 'category', key: 'category', render: (v: string) => CATEGORY_LABEL[v] || v },
    { title: '科目大类', dataIndex: 'account_category', key: 'account_category', render: (v: string | null) => v || '-' },
    {
      title: '科目细类',
      key: 'account_subcategory',
      render: (_: unknown, row: Account) => row.account_subcategory || row.equity_subcategory || '-',
    },
    {
      title: '可分红基础',
      dataIndex: 'include_in_dividend_base',
      key: 'include_in_dividend_base',
      render: (v: boolean | null) => (v === null || v === undefined ? '-' : v ? '纳入' : '不纳入'),
    },
    { title: '方向', dataIndex: 'direction', key: 'direction', render: (v: string) => (v === 'debit' ? '借' : '贷') },
    { title: '级次', dataIndex: 'level', key: 'level' },
    {
      title: '类型',
      dataIndex: 'is_system',
      key: 'is_system',
      render: (v: boolean) => (v ? <Tag color="blue">系统</Tag> : <Tag>自定义</Tag>),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (v: string) => {
        const map: Record<string, string> = { active: 'green', disabled: 'orange', archived: 'default' }
        return <Tag color={map[v] || 'default'}>{v}</Tag>
      },
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, row: Account) => (
        <Space>
          <Button size="small" onClick={() => handleStatusChange(row.code, 'disable')}>停用</Button>
          <Button size="small" onClick={() => handleStatusChange(row.code, 'archive')}>作废</Button>
          <Button size="small" danger onClick={() => handleDelete(row.code)} disabled={row.is_system}>
            删除
          </Button>
        </Space>
      ),
    },
  ]

  return (
    <Card
      title="会计科目"
      extra={(
        <Space>
          <Button onClick={openPresetModal}>加载行业预设</Button>
          <Button type="primary" onClick={openCreateModal}>新增</Button>
        </Space>
      )}
    >
      {list.length === 0 && !loading ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={
            <Space direction="vertical" size={4}>
              <Text strong>当前企业尚未设计会计科目</Text>
              <Text type="secondary">请围绕本企业实际资产、负债和所有者权益结构建立会计科目。</Text>
            </Space>
          }
        >
          <Button type="primary" onClick={openCreateModal}>开始设计会计科目</Button>
        </Empty>
      ) : (
        <Table rowKey="code" dataSource={list} columns={columns} loading={loading} pagination={{ pageSize: 20 }} size="small" />
      )}
      <Modal
        title="加载行业预设科目"
        open={presetOpen}
        onOk={handleImportTemplate}
        onCancel={() => {
          setPresetOpen(false)
          setTemplatePreview(null)
          setSelectedTemplateCode(undefined)
        }}
        okText="确认导入"
        cancelText="取消"
        confirmLoading={presetLoading}
        okButtonProps={{ disabled: !templatePreview }}
        width={900}
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Alert
            type="info"
            showIcon
            title="行业预设只新增不存在的科目；已有科目会跳过或提示冲突，不会覆盖用户已维护的科目。"
          />
          <Select
            style={{ width: 260 }}
            placeholder="请选择行业模板"
            loading={presetLoading}
            value={selectedTemplateCode}
            onChange={handlePreviewTemplate}
            options={templates.map((item) => ({ value: item.code, label: item.name }))}
          />
          {templatePreview && (
            <>
              <Space>
                <Statistic title="预计新增" value={templatePreview.summary.new} />
                <Statistic title="跳过" value={templatePreview.summary.skipped} />
                <Statistic title="冲突" value={templatePreview.summary.conflicts} />
              </Space>
              <Table
                rowKey="code"
                size="small"
                dataSource={templatePreview.accounts}
                pagination={{ pageSize: 10 }}
                columns={[
                  { title: '代码', dataIndex: 'code', key: 'code' },
                  { title: '名称', dataIndex: 'name', key: 'name' },
                  { title: '类别', dataIndex: 'category', key: 'category', render: (v: string) => CATEGORY_LABEL[v] || v },
                  { title: '方向', dataIndex: 'direction', key: 'direction', render: (v: string) => (v === 'debit' ? '借' : '贷') },
                  { title: '级次', dataIndex: 'level', key: 'level' },
                  {
                    title: '导入判断',
                    dataIndex: 'import_status',
                    key: 'import_status',
                    render: (v: string) => {
                      const label: Record<string, string> = { new: '新增', skipped: '跳过', conflict: '冲突' }
                      const color: Record<string, string> = { new: 'green', skipped: 'default', conflict: 'red' }
                      return <Tag color={color[v]}>{label[v] || v}</Tag>
                    },
                  },
                ]}
              />
            </>
          )}
        </Space>
      </Modal>

      <Modal title="设计会计科目" open={open} onOk={handleCreate} onCancel={() => setOpen(false)} okText="保存">
        <Form form={form} layout="vertical" initialValues={{ include_in_dividend_base: true }}>
          <Form.Item name="code" label="科目代码" rules={[{ required: true, message: '请输入科目代码' }]}>
            <Input placeholder="如 100201" />
          </Form.Item>
          <Form.Item name="name" label="科目名称" rules={[{ required: true, message: '请输入科目名称' }]}>
            <Input placeholder="如 基本户银行存款" />
          </Form.Item>
          <Form.Item name="direction" label="借贷方向" rules={[{ required: true, message: '请选择借贷方向' }]}>
            <Select options={[{ value: 'debit', label: '借方' }, { value: 'credit', label: '贷方' }]} />
          </Form.Item>
          <Form.Item name="parent_code" label="上级科目">
            <Select
              allowClear
              showSearch
              optionFilterProp="label"
              options={list.map((item) => ({ value: item.code, label: `${item.code} ${item.name}` }))}
            />
          </Form.Item>
          <Form.Item name="account_category" label="科目大类" rules={[{ required: true, message: '请选择科目大类' }]}>
            <Select options={ACCOUNT_CATEGORY_OPTIONS} onChange={handleAccountCategoryChange} />
          </Form.Item>
          <Form.Item name="category" hidden>
            <Input />
          </Form.Item>
          {accountCategory !== '所有者权益' && (
            <Form.Item name="account_subcategory" label="科目细类" rules={[{ required: true, message: '请选择科目细类' }]}>
              <Select disabled={!accountCategory} options={ACCOUNT_SUBCATEGORY_OPTIONS[accountCategory] || []} />
            </Form.Item>
          )}
          {accountCategory === '所有者权益' && (
            <Form.Item name="equity_subcategory" label="权益细类" rules={[{ required: true, message: '请选择权益细类' }]}>
              <Select options={EQUITY_SUBCATEGORY_OPTIONS} onChange={handleEquitySubcategoryChange} />
            </Form.Item>
          )}
          {equitySubcategory === '未分配利润' && (
            <Form.Item name="include_in_dividend_base" label="是否纳入可分红基础" valuePropName="checked">
              <Switch checkedChildren="纳入" unCheckedChildren="不纳入" />
            </Form.Item>
          )}
          <Alert type="info" showIcon title={getAccountingGuide(accountCategory, equitySubcategory)} />
        </Form>
      </Modal>
    </Card>
  )
}
