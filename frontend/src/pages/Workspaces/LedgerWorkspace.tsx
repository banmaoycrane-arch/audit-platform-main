import { useEffect, useMemo, useState } from 'react'
import { Card, Typography, Row, Col, Button, Statistic, Table, Select, Space, Tag, Empty } from 'antd'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  BookOutlined,
  FileTextOutlined,
  PieChartOutlined,
  BarsOutlined,
  DollarOutlined,
  CheckCircleOutlined,
  PlusOutlined,
  SwapOutlined,
  LockOutlined,
} from '@ant-design/icons'
import { api, type AccountingEntry, type AccountingPeriod } from '../../api/client'
import { useAuthStore } from '../../stores/authStore'

const { Title, Paragraph } = Typography

const functionsList = [
  { key: 'vouchers', icon: <FileTextOutlined />, label: '凭证管理', path: '/ledger/vouchers/step/1' },
  { key: 'books', icon: <BookOutlined />, label: '账簿管理', path: '/ledger/books' },
  { key: 'general-ledger', icon: <BarsOutlined />, label: '总账', path: '/ledger/general-ledger' },
  { key: 'subsidiary-ledger', icon: <BarsOutlined />, label: '明细账', path: '/ledger/subsidiary-ledger' },
  { key: 'trial-balance', icon: <PieChartOutlined />, label: '科目余额表', path: '/reports/trial-balance' },
  { key: 'balance-sheet', icon: <DollarOutlined />, label: '资产负债表', path: '/reports/balance-sheet' },
]

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
}

function groupPendingVouchers(entries: AccountingEntry[]): PendingVoucherRow[] {
  const byVoucher = new Map<string, AccountingEntry[]>()
  for (const entry of entries) {
    if (!entry.voucher_no || entry.review_status === 'verified' || entry.review_status === 'ready') {
      continue
    }
    const list = byVoucher.get(entry.voucher_no) || []
    list.push(entry)
    byVoucher.set(entry.voucher_no, list)
  }
  return Array.from(byVoucher.entries()).map(([voucherNo, lines]) => {
    const amount = lines.reduce((sum, line) => sum + Number(line.debit_amount || 0), 0)
    return {
      key: voucherNo,
      voucher_no: voucherNo,
      date: lines[0]?.voucher_date || '-',
      summary: lines[0]?.summary || '-',
      amount: `¥ ${amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
      status: STATUS_LABEL[lines[0]?.review_status] || lines[0]?.review_status || '待复核',
    }
  })
}

const pendingVouchersColumns = [
  { title: '凭证号', dataIndex: 'voucher_no', key: 'voucher_no' },
  { title: '日期', dataIndex: 'date', key: 'date' },
  { title: '摘要', dataIndex: 'summary', key: 'summary' },
  { title: '金额', dataIndex: 'amount', key: 'amount' },
  { title: '状态', dataIndex: 'status', key: 'status', render: (s: string) => <Tag color="warning">{s}</Tag> },
]

const PERIOD_STATUS_LABEL: Record<string, { color: string; text: string }> = {
  open: { color: 'green', text: '已开启' },
  pl_transferred: { color: 'blue', text: '已结转损益' },
  closed: { color: 'default', text: '已结账' },
  reopened: { color: 'purple', text: '已反结账' },
}

export function LedgerWorkspace() {
  const location = useLocation()
  const navigate = useNavigate()
  const { currentLedgerId } = useAuthStore()
  const [periods, setPeriods] = useState<AccountingPeriod[]>([])
  const [entries, setEntries] = useState<AccountingEntry[]>([])
  const [pendingCount, setPendingCount] = useState(0)
  const [openPeriodCount, setOpenPeriodCount] = useState(0)
  const [selectedPeriodCode, setSelectedPeriodCode] = useState<string>('')
  const [loading, setLoading] = useState(false)

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
      api.listEntries(undefined, currentLedgerId),
      api.getDashboardSummary(currentLedgerId),
    ])
      .then(([periodList, entryList, summary]) => {
        setPeriods(periodList)
        setEntries(entryList)
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

  const pendingVouchersData = useMemo(() => groupPendingVouchers(entries), [entries])
  const selectedPeriod = periods.find((p) => p.period_code === selectedPeriodCode)

  return (
    <div>
      <Title level={4}>财务总账工作台</Title>
      <Paragraph type="secondary">管理凭证、账簿、期间与科目余额</Paragraph>

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
              <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/ledger/vouchers/step/1')}>
                新增凭证
              </Button>
              <Button icon={<SwapOutlined />} onClick={() => navigate('/accounting-periods')}>
                损益结转
              </Button>
              <Button icon={<LockOutlined />} onClick={() => navigate('/accounting-periods')}>
                结账
              </Button>
            </Space>
          </Col>
        </Row>
      </Card>

      <Row gutter={16}>
        <Col span={6}>
          <Card title="功能导航" size="small">
            <Space direction="vertical" style={{ width: '100%' }}>
              {functionsList.map((fn) => (
                <Button
                  key={fn.key}
                  type={location.pathname === fn.path ? 'primary' : 'text'}
                  block
                  icon={fn.icon}
                  onClick={() => navigate(fn.path)}
                >
                  {fn.label}
                </Button>
              ))}
            </Space>
          </Card>
        </Col>

        <Col span={18}>
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
              <Empty description="请先选择账套" />
            ) : (
              <Table
                size="small"
                columns={pendingVouchersColumns}
                dataSource={pendingVouchersData}
                pagination={false}
                rowKey="key"
                locale={{ emptyText: '暂无待处理凭证' }}
              />
            )}
          </Card>

          <Card title="期间状态" style={{ marginTop: 16 }} loading={loading}>
            {periods.length === 0 ? (
              <Empty description="当前账套暂无会计期间" />
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
        </Col>
      </Row>
    </div>
  )
}
