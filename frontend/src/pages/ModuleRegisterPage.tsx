import { useEffect, useMemo, useState } from 'react'
import { Alert, Button, Card, Select, Space, Table, Tag, Typography, message } from 'antd'
import { MailOutlined } from '@ant-design/icons'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import type { ModuleRegisterItem, ModuleRegisterListResponse } from '../api/client'
import { useAuthStore } from '../stores/authStore'

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
}

export function ModuleRegisterPage({ fixedModuleKey }: { fixedModuleKey?: string }) {
  const { moduleKey: routeModuleKey = 'contract_register' } = useParams<{ moduleKey: string }>()
  const moduleKey = fixedModuleKey || routeModuleKey
  const [searchParams] = useSearchParams()
  const { currentLedgerId, setCurrentLedger, userLedgers, setUserLedgers } = useAuthStore()
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<ModuleRegisterListResponse | null>(null)
  const [executionStatus, setExecutionStatus] = useState<string | undefined>()

  const ledgerId = Number(searchParams.get('ledger_id') || currentLedgerId || 0) || null
  const title = MODULE_TITLES[moduleKey] || data?.module_label || '模块台账'

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

  const columns = useMemo(() => {
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
          render: (value: number) => value?.toLocaleString('zh-CN', { minimumFractionDigits: 2 }),
        },
        { title: '单据数', dataIndex: 'document_count', key: 'document_count', width: 90 },
      ]
    }

    if (moduleKey === 'bank_cash_flow') {
      return [
        { title: '交易日期', dataIndex: 'transaction_date', key: 'transaction_date', width: 120 },
        { title: '对方', dataIndex: 'counterparty_name', key: 'counterparty_name' },
        { title: '摘要', dataIndex: 'summary', key: 'summary', ellipsis: true },
        {
          title: '金额',
          dataIndex: 'amount',
          key: 'amount',
          render: (value: number) => value?.toLocaleString('zh-CN', { minimumFractionDigits: 2 }),
        },
        { title: '类型', dataIndex: 'transaction_type', key: 'transaction_type', width: 100 },
      ]
    }

    if (moduleKey === 'tax_invoice') {
      return [
        { title: '发票号码', dataIndex: 'invoice_no', key: 'invoice_no' },
        { title: '开票日期', dataIndex: 'invoice_date', key: 'invoice_date', width: 120 },
        { title: '购方', dataIndex: 'buyer_name', key: 'buyer_name', ellipsis: true },
        { title: '销方', dataIndex: 'seller_name', key: 'seller_name', ellipsis: true },
        {
          title: '价税合计',
          dataIndex: 'total_amount',
          key: 'total_amount',
          render: (value: number) => value?.toLocaleString('zh-CN', { minimumFractionDigits: 2 }),
        },
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
      {
        title: '合同金额',
        dataIndex: 'contract_amount',
        key: 'contract_amount',
        render: (value: number) => value?.toLocaleString('zh-CN', { minimumFractionDigits: 2 }),
      },
      { title: '签约日期', dataIndex: 'sign_date', key: 'sign_date', width: 120 },
    ]
  }, [moduleKey])

  return (
    <Card>
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <Title level={4} style={{ margin: 0 }}>{title}</Title>
            <Paragraph type="secondary" style={{ marginBottom: 0 }}>
              按账套查询已持久化的模块台账数据（Phase A）。当前账套：
              {userLedgers.find((item) => item.id === ledgerId)?.name || ledgerId || '未选择'}
            </Paragraph>
          </div>
          {moduleKey === 'counterparty_ledger' && (
            <Link to="/audit/confirmations">
              <Button type="primary" icon={<MailOutlined />}>
                往来函证控制表
              </Button>
            </Link>
          )}
        </div>

        {!ledgerId && (
          <Alert type="warning" showIcon title="尚未选择账套" description="请先在账套管理中选择账套后查看模块台账。" />
        )}

        {['contract_register', 'purchase', 'sales'].includes(moduleKey) && (
          <Select
            allowClear
            placeholder="筛选执行状态"
            style={{ width: 180 }}
            value={executionStatus}
            onChange={setExecutionStatus}
            options={[
              { value: 'pending', label: '待执行' },
              { value: 'executing', label: '执行中' },
              { value: 'completed', label: '已完成' },
              { value: 'not_executed', label: '未执行' },
              { value: 'cancelled', label: '已取消' },
            ]}
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
        />
      </Space>
    </Card>
  )
}
