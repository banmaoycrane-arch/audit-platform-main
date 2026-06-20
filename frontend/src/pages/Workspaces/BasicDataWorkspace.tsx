import { Card, Typography, Row, Col, Button, Statistic, List } from 'antd'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  DatabaseOutlined,
  BookOutlined,
  ApartmentOutlined,
  UserOutlined,
  TeamOutlined,
  InboxOutlined,
  ShopOutlined,
} from '@ant-design/icons'

const { Title, Paragraph } = Typography

const functionsList = [
  { key: 'coa', icon: <BookOutlined />, label: '会计科目', path: '/basic/coa' },
  { key: 'org-units', icon: <ApartmentOutlined />, label: '组织架构', path: '/basic/org-units' },
  { key: 'personnel', icon: <UserOutlined />, label: '员工', path: '/basic/personnel' },
  { key: 'counterparties', icon: <TeamOutlined />, label: '往来单位', path: '/basic/counterparties' },
  { key: 'materials', icon: <InboxOutlined />, label: '物料', path: '/basic/materials' },
  { key: 'warehouses', icon: <ShopOutlined />, label: '仓库', path: '/basic/warehouses' },
]

export function BasicDataWorkspace() {
  const location = useLocation()
  const navigate = useNavigate()

  return (
    <div>
      <Title level={4}>基础资料工作台</Title>
      <Paragraph type="secondary">维护科目、组织架构、往来单位、物料仓库等底层核算对象</Paragraph>

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
                <Statistic title="会计科目数" value={156} />
              </Card>
            </Col>
            <Col span={8}>
              <Card>
                <Statistic title="待完善科目" value={3} valueStyle={{ color: '#cf1322' }} />
              </Card>
            </Col>
            <Col span={8}>
              <Card>
                <Statistic title="往来单位数" value={42} />
              </Card>
            </Col>
          </Row>
          <Card title="资料完整性概览" style={{ marginTop: 16 }}>
            <Paragraph type="secondary">暂无异常数据（占位）</Paragraph>
          </Card>
        </Col>
      </Row>
    </div>
  )
}
