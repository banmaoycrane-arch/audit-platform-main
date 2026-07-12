import { useEffect, useMemo, useState } from 'react'
import { Card, Row, Col, Button, Statistic, Table, Select, Space, Tag, Empty, Collapse } from 'antd'
import { useNavigate } from 'react-router-dom'
import {
  BookOutlined,
  FileTextOutlined,
  PieChartOutlined,
  BarsOutlined,
  DollarOutlined,
  CheckCircleOutlined,
  PlusOutlined,
  SwapOutlined,
  CalendarOutlined,
  LineChartOutlined,
  SearchOutlined,
} from '@ant-design/icons'
import { api, type AccountingEntry, type AccountingPeriod } from '../../api/client'
import { useAuthStore } from '../../stores/authStore'
import { WorkspaceShell } from '../../components/WorkspaceShell'
import { BalanceSheetWorkbenchBoard } from '../../components/ledger/BalanceSheetWorkbenchBoard'
import { PendingVoucherContextActions } from '../../components/ledger/LedgerContextActions'
import { LEDGER_WORKSPACE_FUNCTIONS } from '../../utils/ledgerNavTaxonomy'
import { VOUCHER_FLOW_ENTRY } from '../../utils/voucherFlowRoutes'
import { sumDecimals } from '../../money'

const WORKSPACE_ICONS: Record<string, React.ReactNode> = {
  import: <FileTextOutlined />,
  entries: <SearchOutlined />,
  periods: <CalendarOutlined />,
  reports: <PieChartOutlined />,
  dimensions: <BookOutlined />,
  'general-ledger': <BarsOutlined />,
  'subsidiary-ledger': <BarsOutlined />,
  'trial-balance': <PieChartOutlined />,
  'balance-sheet': <DollarOutlined />,
  'income-statement': <LineChartOutlined />,
}

const functionsList = LEDGER_WORKSPACE_FUNCTIONS.map((item) => ({
  key: item.key,
  icon: WORKSPACE_ICONS[item.key] ?? <BookOutlined />,
  label: item.label,
  path: item.path,
}))

const STATUS_LABEL: Record<string, string> = {
  draft: '待复核',
  verified: '已复核',
  ready: '待确认入账',
  pending: '待复核',
}

type PendingVoucherRow = {
  key: string
  voucher_no: string
  date: string
  summary: string
  amount: string
  status: string
  import_job_id?: number
}

function groupPendingVouchers(entries: AccountingEntry[]): PendingVoucherRow[] {
  const byVoucher = new Map<string, AccountingEntry[]>()
  for (const entry of entries) {
    if (!entry.voucher_no) {
      continue
    }
    const list = byVoucher.get(entry.voucher_no) || []
    list.push(entry)
    byVoucher.set(entry.voucher_no, list)
  }
  return Array.from(byVoucher.entries()).map(([voucherNo, lines]) => {
    const amount = sumDecimals(lines.map(line => line.debit_amount || 0))
    return {
      key: voucherNo,
      voucher_no: voucherNo,
      date: lines[0]?.voucher_date || '-',
      summary: lines[0]?.summary || '-',
      amount: `¥ ${amount.toFixed(2)}`,
      status: STATUS_LABEL[lines[0]?.review_status] || lines[0]?.review_status || '待复核',
      import_job_id: lines[0]?.import_job_id,
    }
  })
}

const pendingVouchersColumns = (periodId?: number) => [
  { title: '凭证号', dataIndex: 'voucher_no', key: 'voucher_no' },
  { title: '日期', dataIndex: 'date', key: 'date' },
  { title: '摘要', dataIndex: 'summary', key: 'summary' },
  { title: '金额', dataIndex: 'amount', key: 'amount' },
  { title: '状态', dataIndex: 'status', key: 'status', render: (s: string) => <Tag color="warning">{s}</Tag> },
  {
    title: '操作',
    key: 'actions',
    width: 56,
    render: (_: unknown, row: PendingVoucherRow) => (
      <PendingVoucherContextActions
        voucherNo={row.voucher_no}
        importJobId={row.import_job_id}
        periodId={periodId}
      />
    ),
  },
]

const PERIOD_STATUS_LABEL: Record<string, { color: string; text: string }> = {
  open: { color: 'green', text: '已开启' },
  pl_transferred: { color: 'blue', text: '已结转损益' },
  closed: { color: 'default', text: '已结账' },
  reopened: { color: 'purple', text: '已反结账' },
}

export function LedgerWorkspace() {
  const navigate = useNavigate()
  const { currentLedgerId } = useAuthStore()
  const [periods, setPeriods] = useState<AccountingPeriod[]>([])
  const [entries, setEntries] = useState<AccountingEntry[]>([])
  const [pendingCount, setPendingCount] = useState(0)
  const [openPeriodCount, setOpenPeriodCount] = useState(0)
  const [selectedPeriodCode, setSelectedPeriodCode] = useState<string>('')
  const [loading, setLoading] = useState(false)

  const selectedPeriod = periods.find((p) => p.period_code === selectedPeriodCode)

  const loadEntries = () => {
    if (!currentLedgerId) return
    setLoading(true)
    let dateFrom: string | undefined
    let dateTo: string | undefined
    if (selectedPeriod) {
      dateFrom = selectedPeriod.start_date
      dateTo = selectedPeriod.end_date
    }
    api.listEntries(undefined, currentLedgerId, 'draft', dateFrom, dateTo, 50, 0)
      .then((result) => setEntries(result.items))
      .catch(() => setEntries([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    if (!currentLedgerId) {
      setPeriods([])
      setEntries([])
      setPendingCount(0)
      setOpenPeriodCount(0)
      return
    }
    setLoading(true)
    Promise.all([
      api.listAccountingPeriods(undefined, currentLedgerId),
      api.getDashboardSummary(currentLedgerId),
    ])
      .then(([periodList, summary]) => {
        setPeriods(periodList)
        setPendingCount(summary.module_status.ledger.pending_vouchers)
        setOpenPeriodCount(summary.module_status.ledger.unclosed_periods)
        if (periodList.length > 0) {
          const openPeriod = periodList.find((p) => p.status === 'open') || periodList[0]
          setSelectedPeriodCode(openPeriod.period_code)
        } else {
          setSelectedPeriodCode('')
        }
      })
      .catch(() => {
        setPeriods([])
        setEntries([])
        setPendingCount(0)
        setOpenPeriodCount(0)
      })
      .finally(() => setLoading(false))
  }, [currentLedgerId])

  useEffect(() => {
    loadEntries()
  }, [selectedPeriodCode, currentLedgerId])

  const pendingVouchersData = useMemo(() => groupPendingVouchers(entries), [entries])

  return (
    <WorkspaceShell
      title="财务总账工作台"
      description="管理凭证、账簿、期间与科目余额"
      functionsList={functionsList}
    >
      <BalanceSheetWorkbenchBoard ledgerId={currentLedgerId} />

      <Collapse
        style={{ marginTop: 8 }}
        items={[
          {
            key: 'workspace-secondary',
            label: `待办与快捷操作 (${pendingCount})`,
            children: (
              <>
                <Card style={{ marginBottom: 16 }} loading={loading}>
                  <Row justify="space-between" align="middle">
                    <Col>
                      <Space>
                        <Select
                          value={selectedPeriodCode || undefined}
                          onChange={setSelectedPeriodCode}
                          style={{ width: 160 }}
                          placeholder="选择期间"
                          options={periods.map((p) => ({ value: p.period_code, label: p.period_code }))}
                        />
                        {selectedPeriod && (
                          <Tag icon={<CheckCircleOutlined />} color={selectedPeriod.status === 'open' ? 'success' : 'default'}>
                            {PERIOD_STATUS_LABEL[selectedPeriod.status]?.text || selectedPeriod.status}
                          </Tag>
                        )}
                      </Space>
                    </Col>
                    <Col>
                      <Space>
                        <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate(VOUCHER_FLOW_ENTRY)}>
                          序时簿导入
                        </Button>
                        <Button icon={<SwapOutlined />} onClick={() => navigate('/accounting-periods')}>
                          损益结转与结账
                        </Button>
                        <Button icon={<PieChartOutlined />} onClick={() => navigate('/reports')}>
                          报表编制中心
                        </Button>
                      </Space>
                    </Col>
                  </Row>
                </Card>

                <Row gutter={[16, 16]}>
                  <Col span={8}>
                    <Card loading={loading}>
                      <Statistic title="待处理凭证" value={pendingCount} valueStyle={{ color: '#cf1322' }} />
                    </Card>
                  </Col>
                  <Col span={8}>
                    <Card loading={loading}>
                      <Statistic title="已开启期间" value={openPeriodCount} valueStyle={{ color: '#3f8600' }} />
                    </Card>
                  </Col>
                  <Col span={8}>
                    <Card loading={loading}>
                      <Statistic title="科目余额异常" value={0} />
                    </Card>
                  </Col>
                </Row>

                <Card title="待处理凭证列表" style={{ marginTop: 16 }} loading={loading}>
                  {!currentLedgerId ? (
                    <Empty description="请先选择账簿" />
                  ) : (
                    <Table
                      size="small"
                      columns={pendingVouchersColumns(selectedPeriod?.id)}
                      dataSource={pendingVouchersData}
                      pagination={false}
                      rowKey="key"
                      locale={{ emptyText: '暂无待处理凭证' }}
                    />
                  )}
                </Card>

                <Card title="期间状态" style={{ marginTop: 16 }} loading={loading}>
                  {periods.length === 0 ? (
                    <Empty description="当前账簿暂无会计期间" />
                  ) : (
                    <Space wrap>
                      {periods.map((period) => {
                        const meta = PERIOD_STATUS_LABEL[period.status] || { color: 'default', text: period.status }
                        return (
                          <Tag key={period.id} color={meta.color}>
                            {period.period_code} {meta.text}
                          </Tag>
                        )
                      })}
                    </Space>
                  )}
                </Card>
              </>
            ),
          },
        ]}
      />
    </WorkspaceShell>
  )
}