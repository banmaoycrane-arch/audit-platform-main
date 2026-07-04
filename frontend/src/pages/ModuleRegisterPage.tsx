import { useEffect, useMemo, useState } from 'react'
import { Alert, Button, Card, Form, Input, InputNumber, Modal, Popconfirm, Select, Space, Table, Tag, Typography, message } from 'antd'
import { DeleteOutlined, EditOutlined, FileDoneOutlined, FolderOutlined, MailOutlined, ShoppingOutlined } from '@ant-design/icons'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import type { ModuleRegisterItem, ModuleRegisterListResponse } from '../api/client'
import { useAuthStore } from '../stores/authStore'
import { formatMoney } from '../money'

const renderMoney = (value: unknown) => formatMoney(value as number)

const { Title, Paragraph, Text } = Typography

const MODULE_TITLES: Record<string, string> = {
  contract_register: '合同台账',
  counterparty_ledger: '往来款项台账',
  bank_cash_flow: '银行资金收支台账',
  tax_invoice: '税务发票台账',
  purchase: '采购业务台账',
  sales: '销售业务台账',
  inventory_receipt: '库存收发台账',
  payroll: '薪酬台账',
}

const EXECUTION_STATUS_COLOR: Record<string, string> = {
  pending: 'default',
  executing: 'processing',
  completed: 'success',
  not_executed: 'warning',
  cancelled: 'error',
  archived: 'default',
}

const EXECUTION_STATUS_OPTIONS = [
  { value: 'pending', label: '待执行' },
  { value: 'executing', label: '执行中' },
  { value: 'completed', label: '已完成' },
  { value: 'not_executed', label: '未执行' },
  { value: 'cancelled', label: '已取消' },
  { value: 'archived', label: '已归档' },
]

const EDITABLE_FIELDS: Record<string, Array<{ name: string; label: string; type?: 'text' | 'number' | 'date' | 'select'; options?: Array<{ value: string; label: string }> }>> = {
  contract_register: [
    { name: 'contract_no', label: '合同编号' },
    { name: 'contract_name', label: '合同名称' },
    { name: 'contract_type', label: '合同类型', type: 'select', options: [{ value: 'purchase', label: '采购' }, { value: 'sales', label: '销售' }, { value: 'service', label: '服务' }, { value: 'framework', label: '框架' }] },
    { name: 'execution_status', label: '执行状态', type: 'select', options: EXECUTION_STATUS_OPTIONS },
    { name: 'contract_amount', label: '合同金额', type: 'number' },
    { name: 'sign_date', label: '签约日期', type: 'date' },
  ],
  purchase: [
    { name: 'contract_no', label: '合同编号' },
    { name: 'contract_name', label: '合同名称' },
    { name: 'execution_status', label: '执行状态', type: 'select', options: EXECUTION_STATUS_OPTIONS },
    { name: 'contract_amount', label: '合同金额', type: 'number' },
    { name: 'sign_date', label: '签约日期', type: 'date' },
  ],
  sales: [
    { name: 'contract_no', label: '合同编号' },
    { name: 'contract_name', label: '合同名称' },
    { name: 'execution_status', label: '执行状态', type: 'select', options: EXECUTION_STATUS_OPTIONS },
    { name: 'contract_amount', label: '合同金额', type: 'number' },
    { name: 'sign_date', label: '签约日期', type: 'date' },
  ],
  tax_invoice: [
    { name: 'invoice_no', label: '发票号码' },
    { name: 'invoice_code', label: '发票代码' },
    { name: 'invoice_type', label: '发票类型' },
    { name: 'invoice_status', label: '发票状态', type: 'select', options: [{ value: 'normal', label: '正常' }, { value: 'canceled', label: '作废' }, { value: 'red', label: '红冲' }, { value: 'archived', label: '已归档' }] },
    { name: 'invoice_date', label: '开票日期', type: 'date' },
    { name: 'buyer_name', label: '购方名称' },
    { name: 'seller_name', label: '销方名称' },
    { name: 'total_amount', label: '价税合计', type: 'number' },
  ],
  bank_cash_flow: [
    { name: 'transaction_no', label: '交易流水号' },
    { name: 'transaction_date', label: '交易日期', type: 'date' },
    { name: 'transaction_type', label: '收支类型', type: 'select', options: [{ value: 'income', label: '收入' }, { value: 'expense', label: '支出' }] },
    { name: 'counterparty_name', label: '对方户名' },
    { name: 'amount', label: '金额', type: 'number' },
    { name: 'balance', label: '余额', type: 'number' },
    { name: 'summary', label: '摘要' },
    { name: 'remark', label: '备注' },
  ],
  inventory_receipt: [
    { name: 'document_no', label: '单据编号' },
    { name: 'document_type', label: '单据类型' },
    { name: 'document_date', label: '单据日期', type: 'date' },
    { name: 'warehouse_name', label: '仓库' },
    { name: 'counterparty_name', label: '往来方' },
    { name: 'total_quantity', label: '总数量', type: 'number' },
    { name: 'total_amount', label: '总金额', type: 'number' },
    { name: 'inspect_result', label: '验收结果' },
  ],
}

function getEditableFields(moduleKey: string) {
  return EDITABLE_FIELDS[moduleKey] || []
}



function pickInitialValues(moduleKey: string, row: ModuleRegisterItem) {
  const values: Record<string, unknown> = {}
  getEditableFields(moduleKey).forEach((field) => {
    values[field.name] = (row as Record<string, unknown>)[field.name]
  })
  return values
}

export function ModuleRegisterPage({ fixedModuleKey }: { fixedModuleKey?: string }) {
  const { moduleKey: routeModuleKey = 'contract_register' } = useParams<{ moduleKey: string }>()
  const moduleKey = fixedModuleKey || routeModuleKey
  const [searchParams] = useSearchParams()
  const { currentLedgerId, setCurrentLedger, userLedgers, setUserLedgers } = useAuthStore()
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<ModuleRegisterListResponse | null>(null)
  const [executionStatus, setExecutionStatus] = useState<string | undefined>()
  const [editingRow, setEditingRow] = useState<ModuleRegisterItem | null>(null)
  const [correctingRow, setCorrectingRow] = useState<ModuleRegisterItem | null>(null)
  const [form] = Form.useForm()
  const [correctForm] = Form.useForm()

  const ledgerId = Number(searchParams.get('ledger_id') || currentLedgerId || 0) || null
  const title = MODULE_TITLES[moduleKey] || data?.module_label || '模块台账'
  const editableFields = getEditableFields(moduleKey)
  const supportsRowOperations = editableFields.length > 0

  const ensureLedger = async () => {
    if (ledgerId) return ledgerId
    const ledgers = await api.listLedgers()
    setUserLedgers(ledgers)
    if (!ledgers.length) return null
    await api.switchLedger(ledgers[0].id)
    setCurrentLedger(ledgers[0].id)
    return ledgers[0].id
  }

  const loadData = async () => {
    setLoading(true)
    try {
      const activeLedgerId = await ensureLedger()
      if (!activeLedgerId) {
        setData(null)
        return
      }
      const response = await api.listModuleRegisters(moduleKey, {
        ledger_id: activeLedgerId,
        execution_status: executionStatus,
      })
      setData(response)
    } catch (error: any) {
      message.error(error.message || '加载模块台账失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadData()
  }, [moduleKey, ledgerId, executionStatus])

  const openEditModal = (row: ModuleRegisterItem) => {
    if (!supportsRowOperations) {
      message.info('该台账为汇总视图，暂不支持直接编辑，请回到来源单据处理。')
      return
    }
    setEditingRow(row)
    form.setFieldsValue(pickInitialValues(moduleKey, row))
  }

  const openCorrectModal = (row: ModuleRegisterItem) => {
    if (!supportsRowOperations) {
      message.info('该台账为汇总视图，暂不支持直接更正，请回到来源单据处理。')
      return
    }
    setCorrectingRow(row)
    correctForm.setFieldsValue({ ...pickInitialValues(moduleKey, row), correction_reason: '' })
  }

  const handleEditSubmit = async () => {
    if (!editingRow?.id) return
    const values = await form.validateFields()
    await api.updateModuleRegisterRow(moduleKey, editingRow.id, values)
    message.success('台账行已编辑')
    setEditingRow(null)
    await loadData()
  }

  const handleCorrectSubmit = async () => {
    if (!correctingRow?.id) return
    const values = await correctForm.validateFields()
    const { correction_reason, ...fields } = values
    await api.correctModuleRegisterRow(moduleKey, correctingRow.id, fields, correction_reason)
    message.success('台账行已更正并记录原因')
    setCorrectingRow(null)
    await loadData()
  }

  const handleArchive = async (row: ModuleRegisterItem) => {
    if (!row.id) return
    if (!supportsRowOperations) {
      message.info('该台账为汇总视图，暂不支持直接归档，请回到来源单据处理。')
      return
    }
    await api.archiveModuleRegisterRow(moduleKey, row.id, '用户在台账页面归档')
    message.success('台账行已归档')
    await loadData()
  }

  const handleDelete = async (row: ModuleRegisterItem) => {
    if (!row.id) return
    if (!supportsRowOperations) {
      message.info('该台账为汇总视图，不能直接删除汇总行。')
      return
    }
    await api.deleteModuleRegisterRow(moduleKey, row.id)
    message.success('台账行已删除')
    await loadData()
  }

  const renderEditFormItems = (currentModuleKey: string) => getEditableFields(currentModuleKey).map((field) => {
    if (field.type === 'number') {
      return (
        <Form.Item key={field.name} name={field.name} label={field.label}>
          <InputNumber style={{ width: '100%' }} precision={2} />
        </Form.Item>
      )
    }
    if (field.type === 'select') {
      return (
        <Form.Item key={field.name} name={field.name} label={field.label}>
          <Select allowClear options={field.options || []} />
        </Form.Item>
      )
    }
    if (field.type === 'date') {
      return (
        <Form.Item key={field.name} name={field.name} label={field.label}>
          <Input placeholder="YYYY-MM-DD" />
        </Form.Item>
      )
    }
    return (
      <Form.Item key={field.name} name={field.name} label={field.label}>
        <Input />
      </Form.Item>
    )
  })

  const baseColumns = useMemo(() => {
    if (moduleKey === 'counterparty_ledger') {
      return [
        { title: '往来单位', dataIndex: 'counterparty_name', key: 'counterparty_name' },
        {
          title: '余额方向',
          dataIndex: 'balance_type_label',
          key: 'balance_type_label',
          render: (value: string) => <Tag>{value}</Tag>,
        },
        {
          title: '合计金额',
          dataIndex: 'total_amount',
          key: 'total_amount',
          render: renderMoney,
        },
        { title: '单据数', dataIndex: 'document_count', key: 'document_count', width: 90 },
      ]
    }

    if (moduleKey === 'bank_cash_flow') {
      return [
        { title: '交易日期', dataIndex: 'transaction_date', key: 'transaction_date', width: 120 },
        { title: '对方', dataIndex: 'counterparty_name', key: 'counterparty_name' },
        { title: '摘要', dataIndex: 'summary', key: 'summary', ellipsis: true },
        { title: '金额', dataIndex: 'amount', key: 'amount', render: renderMoney },
        { title: '类型', dataIndex: 'transaction_type', key: 'transaction_type', width: 100 },
      ]
    }

    if (moduleKey === 'tax_invoice') {
      return [
        { title: '发票号码', dataIndex: 'invoice_no', key: 'invoice_no' },
        { title: '开票日期', dataIndex: 'invoice_date', key: 'invoice_date', width: 120 },
        { title: '购方', dataIndex: 'buyer_name', key: 'buyer_name', ellipsis: true },
        { title: '销方', dataIndex: 'seller_name', key: 'seller_name', ellipsis: true },
        { title: '价税合计', dataIndex: 'total_amount', key: 'total_amount', render: renderMoney },
      ]
    }

    if (moduleKey === 'inventory_receipt') {
      return [
        { title: '单据编号', dataIndex: 'document_no', key: 'document_no' },
        { title: '单据类型', dataIndex: 'document_type', key: 'document_type', width: 120 },
        { title: '单据日期', dataIndex: 'document_date', key: 'document_date', width: 120 },
        { title: '往来方', dataIndex: 'counterparty_name', key: 'counterparty_name', ellipsis: true },
        { title: '总金额', dataIndex: 'total_amount', key: 'total_amount', render: renderMoney },
      ]
    }

    return [
      { title: '合同编号', dataIndex: 'contract_no', key: 'contract_no' },
      { title: '合同名称', dataIndex: 'contract_name', key: 'contract_name', ellipsis: true },
      { title: '类型', dataIndex: 'contract_type', key: 'contract_type', width: 100 },
      {
        title: '执行状态',
        dataIndex: 'execution_status',
        key: 'execution_status',
        width: 110,
        render: (_: string, row: ModuleRegisterItem) => (
          <Tag color={EXECUTION_STATUS_COLOR[row.execution_status || 'pending'] || 'default'}>
            {row.execution_status_label || row.execution_status}
          </Tag>
        ),
      },
      { title: '合同金额', dataIndex: 'contract_amount', key: 'contract_amount', render: renderMoney },
      { title: '签约日期', dataIndex: 'sign_date', key: 'sign_date', width: 120 },
    ]
  }, [moduleKey])

  const columns = useMemo(() => ([
    ...baseColumns,
    {
      title: '操作',
      key: 'actions',
      width: 260,
      fixed: 'right' as const,
      render: (_: unknown, row: ModuleRegisterItem) => (
        <Space size="small" wrap>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEditModal(row)} disabled={!supportsRowOperations}>编辑</Button>
          <Button size="small" icon={<FileDoneOutlined />} onClick={() => openCorrectModal(row)} disabled={!supportsRowOperations}>更正</Button>
          <Button size="small" icon={<FolderOutlined />} onClick={() => handleArchive(row)} disabled={!supportsRowOperations}>归档</Button>
          <Popconfirm
            title="确认删除这行台账数据？"
            description="删除会移除该台账记录，不会自动冲销或生成会计凭证。"
            okText="确认删除"
            cancelText="取消"
            onConfirm={() => handleDelete(row)}
            disabled={!supportsRowOperations}
          >
            <Button size="small" danger icon={<DeleteOutlined />} disabled={!supportsRowOperations}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]), [baseColumns, supportsRowOperations])

  return (
    <Card>
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <Title level={4} style={{ margin: 0 }}>{title}</Title>
            <Paragraph type="secondary" style={{ marginBottom: 0 }}>
              按账簿查询已持久化的模块台账数据（Phase A）。当前账簿：
              {userLedgers.find((item) => item.id === ledgerId)?.name || ledgerId || '未选择'}
            </Paragraph>
          </div>
          {moduleKey === 'counterparty_ledger' && (
            <Link to="/audit/confirmations">
              <Button type="primary" icon={<MailOutlined />}>往来函证控制表</Button>
            </Link>
          )}
          {moduleKey === 'purchase' && (
            <Link to="/audit/purchase-match">
              <Button type="primary" icon={<ShoppingOutlined />}>采购三单匹配</Button>
            </Link>
          )}
        </div>

        {!ledgerId && (
          <Alert type="warning" showIcon title="尚未选择账簿" description="请先在账簿管理中选择账簿后查看模块台账。" />
        )}

        {!supportsRowOperations && (
          <Alert type="info" showIcon message="该页面是汇总台账视图" description="汇总行由来源单据自动汇总生成，不能直接编辑、删除、归档。请进入对应来源单据台账处理。" />
        )}

        {['contract_register', 'purchase', 'sales'].includes(moduleKey) && (
          <Select
            allowClear
            placeholder="筛选执行状态"
            style={{ width: 180 }}
            value={executionStatus}
            onChange={setExecutionStatus}
            options={EXECUTION_STATUS_OPTIONS}
          />
        )}

        <Text type="secondary">共 {data?.count ?? 0} 条记录</Text>

        <Table
          rowKey={(row) => String(row.id || `${row.counterparty_name}-${row.balance_type}`)}
          loading={loading}
          dataSource={data?.items || []}
          columns={columns}
          size="small"
          pagination={{ pageSize: 20 }}
          scroll={{ x: 1100 }}
        />
      </Space>

      <Modal
        title="编辑台账行"
        open={!!editingRow}
        onCancel={() => setEditingRow(null)}
        onOk={handleEditSubmit}
        okText="保存编辑"
        cancelText="取消"
        destroyOnClose
      >
        <Alert type="warning" showIcon message="编辑会直接修改当前台账记录，请确认不是需要保留痕迹的正式更正。" style={{ marginBottom: 16 }} />
        <Form form={form} layout="vertical">
          {renderEditFormItems(moduleKey)}
        </Form>
      </Modal>

      <Modal
        title="更正台账行"
        open={!!correctingRow}
        onCancel={() => setCorrectingRow(null)}
        onOk={handleCorrectSubmit}
        okText="保存更正"
        cancelText="取消"
        destroyOnClose
      >
        <Alert type="info" showIcon message="更正要求填写原因。当前实现会记录更正原因；不会自动生成凭证或冲销分录。" style={{ marginBottom: 16 }} />
        <Form form={correctForm} layout="vertical">
          {renderEditFormItems(moduleKey)}
          <Form.Item name="correction_reason" label="更正原因" rules={[{ required: true, message: '请输入更正原因' }]}>
            <Input.TextArea rows={3} placeholder="例如：OCR识别金额错误，经人工核对合同原文后更正" />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  )
}
