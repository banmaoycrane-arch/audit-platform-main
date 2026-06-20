import { Card, Typography, Row, Col, Button, Statistic, List } from 'antd'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  ExperimentOutlined,
  FileTextOutlined,
  RobotOutlined,
  PieChartOutlined,
  FileSearchOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons'

const { Title, Paragraph } = Typography

const functionsList = [
  { key: 'invoices', icon: <FileTextOutlined />, label: '发票管理', path: '/tax/invoices' },
  { key: 'invoice-issuance-ledger', icon: <FileSearchOutlined />, label: '发票开具台账', path: '/tax/invoice-issuance-ledger' },
  { key: 'certification-deduction-ledger', icon: <CheckCircleOutlined />, label: '认证抵扣台账', path: '/tax/certification-deduction-ledger' },
  { key: 'assistant', icon: <RobotOutlined />, label: '涉税助手', path: '/tax/assistant' },
  { key: 'reports', icon: <PieChartOutlined />, label: '税务报表', path: '/tax/assistant' },
]

export function TaxWorkspace() {
  const location = useLocation()
  const navigate = useNavigate()

  return (
    <div>
      <Title level={4}>税务工作台</Title>
      <Paragraph type="secondary">管理发票、涉税助手与税务知识库</Paragraph>

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
                <Statistic title="待处理发票" value={8} valueStyle={{ color: '#cf1322' }} />
              </Card>
            </Col>
            <Col span={8}>
              <Card>
                <Statistic title="涉税风险" value={0} />
              </Card>
            </Col>
            <Col span={8}>
              <Card>
                <Statistic title="本月已认证" value={24} valueStyle={{ color: '#3f8600' }} />
              </Card>
            </Col>
          </Row>
          <Card title="发票状态概览" style={{ marginTop: 16 }}>
            <Paragraph type="secondary">暂无发票数据（占位）</Paragraph>
          </Card>
        </Col>
      </Row>
    </div>
  )
}
