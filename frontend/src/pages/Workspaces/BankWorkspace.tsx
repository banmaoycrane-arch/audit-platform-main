import { useEffect, useState } from 'react'
import { Card, Typography, Row, Col, Button, Statistic, List, Spin } from 'antd'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  BankOutlined,
  CreditCardOutlined,
  WalletOutlined,
  BookOutlined,
  SettingOutlined,
  ReconciliationOutlined,
  AccountBookOutlined,
  TransactionOutlined,
  FileSearchOutlined,
} from '@ant-design/icons'
import { api } from '../../api/client'
import { useAuthStore } from '../../stores/authStore'

const { Title, Paragraph } = Typography

const functionsList = [
  { key: 'accounts', icon: <AccountBookOutlined />, label: '银行账户', path: '/bank/accounts' },
  { key: 'third-party', icon: <CreditCardOutlined />, label: '三方支付', path: '/bank/third-party-accounts' },
  { key: 'aggregate', icon: <WalletOutlined />, label: '聚合账户', path: '/bank/aggregate-accounts' },
  { key: 'journal', icon: <BookOutlined />, label: '日记账', path: '/bank/journal' },
  { key: 'reconciliation', icon: <ReconciliationOutlined />, label: '自动对账', path: '/bank/reconciliation' },
  { key: 'cash-flow-ledger', icon: <TransactionOutlined />, label: '资金收支台账', path: '/bank/cash-flow-ledger' },
  { key: 'bank-reconciliation-ledger', icon: <FileSearchOutlined />, label: '银行对账台账', path: '/bank/bank-reconciliation-ledger' },
  { key: 'settings', icon: <SettingOutlined />, label: '账户设置', path: '/bank/settings' },
]

export function BankWorkspace() {
  const location = useLocation()
  const navigate = useNavigate()
  const { currentLedgerId } = useAuthStore()
  const [summary, setSummary] = useState<{ account_count: number; unreconciled_count: number; total_balance: number } | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!currentLedgerId) {
      setSummary(null)
      return
    }
    setLoading(true)
    api
      .getBankSummary(currentLedgerId)
      .then(setSummary)
      .catch(() => setSummary({ account_count: 0, unreconciled_count: 0, total_balance: 0 }))
      .finally(() => setLoading(false))
  }, [currentLedgerId])

  return (
    <div>
      <Title level={4}>银行工作台</Title>
      <Paragraph type="secondary">管理银行账户、三方支付、日记账与自动对账</Paragraph>

      <Row gutter={16}>
        <Col span={6}>
          <Card title="功能导航" size="small">
            <List
              dataSource={functionsList}
              renderItem={(item) => (
                <List.Item>
                  <Button
                    type={location.pathname === item.path ? 'primary' : 'text'}
                    block
                    icon={item.icon}
                    onClick={() => navigate(item.path)}
                  >
                    {item.label}
                  </Button>
                </List.Item>
              )}
            />
          </Card>
        </Col>
        <Col span={18}>
          <Spin spinning={loading}>
            <Row gutter={[16, 16]}>
              <Col span={8}>
                <Card>
                  <Statistic title="银行账户数" value={summary?.account_count ?? 0} prefix={<BankOutlined />} />
                </Card>
              </Col>
              <Col span={8}>
                <Card>
                  <Statistic
                    title="未对账笔数"
                    value={summary?.unreconciled_count ?? 0}
                    valueStyle={{ color: (summary?.unreconciled_count ?? 0) > 0 ? '#cf1322' : undefined }}
                  />
                </Card>
              </Col>
              <Col span={8}>
                <Card>
                  <Statistic
                    title="账户余额合计"
                    value={summary?.total_balance ?? 0}
                    precision={2}
                    prefix="¥"
                    valueStyle={{ color: '#3f8600' }}
                  />
                </Card>
              </Col>
            </Row>
            <Card title="快捷操作" style={{ marginTop: 16 }}>
              <Button type="primary" onClick={() => navigate('/bank/accounts')} style={{ marginRight: 8 }}>
                管理银行账户
              </Button>
              <Button onClick={() => navigate('/bank/reconciliation')}>进入自动对账</Button>
            </Card>
          </Spin>
        </Col>
      </Row>
    </div>
  )
}
