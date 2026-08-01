import { useEffect, useMemo, useState } from 'react'
import { Alert, Button, Card, Collapse, Form, Input, InputNumber, Modal, Popconfirm, Select, Space, Table, Tag, Typography, message } from 'antd'
import { DeleteOutlined, EditOutlined, FileDoneOutlined, FolderOutlined, MailOutlined, ShoppingOutlined, EyeOutlined, WarningOutlined, InfoCircleOutlined, CheckCircleOutlined, ClockCircleOutlined } from '@ant-design/icons'
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
  const [viewingAnalysisRow, setViewingAnalysisRow] = useState<ModuleRegisterItem | null>(null)
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

  const openAnalysisModal = (row: ModuleRegisterItem) => {
    if (!row.deep_analysis) {
      message.info('该合同暂无深度分析结果')
      return
    }
    setViewingAnalysisRow(row)
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
      width: 340,
      fixed: 'right' as const,
      render: (_: unknown, row: ModuleRegisterItem) => (
        <Space size="small" wrap>
          <Button size="small" icon={<EyeOutlined />} onClick={() => openAnalysisModal(row)} disabled={!row.deep_analysis}>深度分析</Button>
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

      <Modal
        title={`合同深度分析 - ${viewingAnalysisRow?.contract_name || ''}`}
        open={!!viewingAnalysisRow?.deep_analysis}
        onCancel={() => setViewingAnalysisRow(null)}
        footer={null}
        width={900}
        destroyOnClose
      >
        {viewingAnalysisRow?.deep_analysis && (
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              {viewingAnalysisRow.deep_analysis.overall_risk_level === 'critical' && (
                <Tag color="red" icon={<WarningOutlined />}>严重风险</Tag>
              )}
              {viewingAnalysisRow.deep_analysis.overall_risk_level === 'high' && (
                <Tag color="orange" icon={<WarningOutlined />}>高风险</Tag>
              )}
              {viewingAnalysisRow.deep_analysis.overall_risk_level === 'medium' && (
                <Tag color="gold" icon={<ClockCircleOutlined />}>中风险</Tag>
              )}
              {viewingAnalysisRow.deep_analysis.overall_risk_level === 'low' && (
                <Tag color="green" icon={<CheckCircleOutlined />}>低风险</Tag>
              )}
              {viewingAnalysisRow.deep_analysis.overall_risk_level === 'info' && (
                <Tag color="blue" icon={<InfoCircleOutlined />}>信息提示</Tag>
              )}
              <Tag>风险评分: {viewingAnalysisRow.deep_analysis.risk_score}</Tag>
              <Tag>分析时间: {viewingAnalysisRow.deep_analysis.analysis_time}</Tag>
            </div>

            <Paragraph strong>{viewingAnalysisRow.deep_analysis.analysis_summary}</Paragraph>

            <Collapse defaultActiveKey={['summary', 'contradictions', 'missing', 'non_standard', 'ambiguous', 'accounting']}>
              {viewingAnalysisRow.deep_analysis.all_risk_items?.length > 0 && (
                <Collapse.Panel header={`风险项汇总 (${viewingAnalysisRow.deep_analysis.all_risk_items.length})`} key="summary">
                  <Space direction="vertical" size="small" style={{ width: '100%' }}>
                    {viewingAnalysisRow.deep_analysis.all_risk_items.map((item, index) => (
                      <Card key={index} size="small" style={{ borderLeft: '4px solid ' + 
                        (item.risk_level === 'critical' ? '#ff4d4f' :
                         item.risk_level === 'high' ? '#fa8c16' :
                         item.risk_level === 'medium' ? '#faad14' : '#52c41a') }}>
                        <Space direction="vertical" size="small" style={{ width: '100%' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <Text strong>{item.title}</Text>
                            <Tag color={item.risk_level === 'critical' ? 'red' :
                                        item.risk_level === 'high' ? 'orange' :
                                        item.risk_level === 'medium' ? 'gold' : 'green'}>
                              {item.risk_level === 'critical' ? '严重' :
                               item.risk_level === 'high' ? '高' :
                               item.risk_level === 'medium' ? '中' : '低'}
                            </Tag>
                          </div>
                          <Text type="secondary">{item.description}</Text>
                          {item.accounting_impact && (
                            <Paragraph style={{ margin: 0 }}>
                              <Text strong>会计影响：</Text>{item.accounting_impact}
                            </Paragraph>
                          )}
                          {item.recommendation && (
                            <Paragraph style={{ margin: 0 }}>
                              <Text strong>建议：</Text>{item.recommendation}
                            </Paragraph>
                          )}
                        </Space>
                      </Card>
                    ))}
                  </Space>
                </Collapse.Panel>
              )}

              {viewingAnalysisRow.deep_analysis.contradictions?.length > 0 && (
                <Collapse.Panel header={`条款矛盾 (${viewingAnalysisRow.deep_analysis.contradictions.length})`} key="contradictions">
                  <Space direction="vertical" size="small" style={{ width: '100%' }}>
                    {viewingAnalysisRow.deep_analysis.contradictions.map((item, index) => (
                      <Card key={index} size="small" type="inner">
                        <Alert type="error" message={`矛盾类型：${item.contradiction_type}`} showIcon />
                        <Paragraph style={{ margin: '8px 0' }}>
                          <Text strong>条款A：</Text>{item.clause_a}
                        </Paragraph>
                        <Paragraph style={{ margin: '8px 0' }}>
                          <Text strong>条款B：</Text>{item.clause_b}
                        </Paragraph>
                        <Paragraph style={{ margin: 0 }}>
                          <Text strong>矛盾描述：</Text>{item.description}
                        </Paragraph>
                      </Card>
                    ))}
                  </Space>
                </Collapse.Panel>
              )}

              {viewingAnalysisRow.deep_analysis.missing_elements?.length > 0 && (
                <Collapse.Panel header={`缺失要素 (${viewingAnalysisRow.deep_analysis.missing_elements.length})`} key="missing">
                  <Space direction="vertical" size="small" style={{ width: '100%' }}>
                    {viewingAnalysisRow.deep_analysis.missing_elements.map((item, index) => (
                      <Card key={index} size="small" type="inner">
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Text strong>{item.element_name}</Text>
                          <Tag color={item.importance === '高' ? 'red' : item.importance === '中' ? 'orange' : 'blue'}>
                            {item.importance}
                          </Tag>
                        </div>
                        <Paragraph style={{ margin: '8px 0' }}>{item.description}</Paragraph>
                        <Paragraph style={{ margin: 0 }}>
                          <Text strong>建议：</Text>{item.suggested_action}
                        </Paragraph>
                      </Card>
                    ))}
                  </Space>
                </Collapse.Panel>
              )}

              {viewingAnalysisRow.deep_analysis.non_standard_clauses?.length > 0 && (
                <Collapse.Panel header={`非标条款 (${viewingAnalysisRow.deep_analysis.non_standard_clauses.length})`} key="non_standard">
                  <Space direction="vertical" size="small" style={{ width: '100%' }}>
                    {viewingAnalysisRow.deep_analysis.non_standard_clauses.map((item, index) => (
                      <Card key={index} size="small" type="inner">
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Text strong>{item.clause_type}</Text>
                          <Tag color={item.risk_level === 'critical' ? 'red' :
                                      item.risk_level === 'high' ? 'orange' :
                                      item.risk_level === 'medium' ? 'gold' : 'green'}>
                            {item.risk_level === 'critical' ? '严重' :
                             item.risk_level === 'high' ? '高' :
                             item.risk_level === 'medium' ? '中' : '低'}
                          </Tag>
                        </div>
                        <Paragraph style={{ margin: '8px 0' }}>{item.clause_text}</Paragraph>
                        <Paragraph style={{ margin: '8px 0' }}>
                          <Text strong>偏离标准：</Text>{item.deviation_from_standard}
                        </Paragraph>
                        <Paragraph style={{ margin: 0 }}>
                          <Text strong>会计处理：</Text>{item.accounting_treatment}
                        </Paragraph>
                      </Card>
                    ))}
                  </Space>
                </Collapse.Panel>
              )}

              {viewingAnalysisRow.deep_analysis.ambiguous_expressions?.length > 0 && (
                <Collapse.Panel header={`模糊表述 (${viewingAnalysisRow.deep_analysis.ambiguous_expressions.length})`} key="ambiguous">
                  <Space direction="vertical" size="small" style={{ width: '100%' }}>
                    {viewingAnalysisRow.deep_analysis.ambiguous_expressions.map((item, index) => (
                      <Card key={index} size="small" type="inner">
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Text strong>{item.ambiguity_type}</Text>
                        </div>
                        <Paragraph style={{ margin: '8px 0' }}>
                          <Text strong>模糊表述：</Text>{item.expression}
                        </Paragraph>
                        <Paragraph style={{ margin: '8px 0' }}>
                          <Text strong>可能解读：</Text>{item.possible_interpretations.join('；')}
                        </Paragraph>
                        <Paragraph style={{ margin: 0 }}>
                          <Text strong>建议澄清：</Text>{item.recommended_clarification}
                        </Paragraph>
                      </Card>
                    ))}
                  </Space>
                </Collapse.Panel>
              )}

              <Collapse.Panel header="会计处理提示" key="accounting">
                <Space direction="vertical" size="small" style={{ width: '100%' }}>
                  <Card size="small" type="inner">
                    <Text strong>会计处理要点：</Text>
                    <Paragraph>{viewingAnalysisRow.deep_analysis.accounting_notes}</Paragraph>
                  </Card>
                  <Card size="small" type="inner">
                    <Text strong>收入确认考虑：</Text>
                    <Paragraph>{viewingAnalysisRow.deep_analysis.revenue_recognition_considerations}</Paragraph>
                  </Card>
                  <Card size="small" type="inner">
                    <Text strong>预计负债要求：</Text>
                    <Paragraph>{viewingAnalysisRow.deep_analysis.provision_requirements}</Paragraph>
                  </Card>
                </Space>
              </Collapse.Panel>
            </Collapse>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <Tag>分析条款数：{viewingAnalysisRow.deep_analysis.total_clauses_analyzed}</Tag>
              <Tag color="orange">发现风险条款：{viewingAnalysisRow.deep_analysis.risk_clauses_found}</Tag>
            </div>
          </Space>
        )}
      </Modal>
    </Card>
  )
}
