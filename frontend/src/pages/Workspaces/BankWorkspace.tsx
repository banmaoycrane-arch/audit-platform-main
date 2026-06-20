import { Card, Typography, Row, Col, Button, Statistic, List } from 'antd'
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
          <Row gutter={[16, 16]}>
            <Col span={8}>
              <Card>
                <Statistic title="银行账户数" value={3} />
              </Card>
            </Col>
            <Col span={8}>
              <Card>
                <Statistic title="未对账笔数" value={12} valueStyle={{ color: '#cf1322' }} />
              </Card>
            </Col>
            <Col span={8}>
              <Card>
                <Statistic title="日记账状态" value="正常" valueStyle={{ color: '#3f8600' }} />
              </Card>
            </Col>
          </Row>
          <Card title="账户余额概览" style={{ marginTop: 16 }}>
            <Paragraph type="secondary">暂无余额数据（占位）</Paragraph>
          </Card>
        </Col>
      </Row>
    </div>
  )
}
