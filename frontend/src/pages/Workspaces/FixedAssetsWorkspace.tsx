import { Card, Typography, Row, Col, Button, Statistic, List } from 'antd'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  ToolOutlined,
  PlusOutlined,
  MinusOutlined,
  RedoOutlined,
  FileSearchOutlined,
  SettingOutlined,
} from '@ant-design/icons'

const { Title, Paragraph } = Typography

const functionsList = [
  { key: 'cards', icon: <ToolOutlined />, label: '资产卡片', path: '/fixed-assets/cards' },
  { key: 'addition', icon: <PlusOutlined />, label: '资产增加', path: '/fixed-assets/addition' },
  { key: 'reduction', icon: <MinusOutlined />, label: '资产减少', path: '/fixed-assets/reduction' },
  { key: 'depreciation', icon: <RedoOutlined />, label: '折旧计提', path: '/fixed-assets/depreciation' },
  { key: 'asset-change-ledger', icon: <FileSearchOutlined />, label: '资产增减台账', path: '/fixed-assets/asset-change-ledger' },
  { key: 'settings', icon: <SettingOutlined />, label: '资产设置', path: '/fixed-assets/settings' },
]

export function FixedAssetsWorkspace() {
  const location = useLocation()
  const navigate = useNavigate()

  return (
    <div>
      <Title level={4}>固定资产工作台</Title>
      <Paragraph type="secondary">管理资产卡片、折旧、处置与增减台账</Paragraph>

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
                <Statistic title="资产卡片数" value={45} />
              </Card>
            </Col>
            <Col span={8}>
              <Card>
                <Statistic title="本月折旧额" value={12800} valueStyle={{ color: '#3f8600' }} />
              </Card>
            </Col>
            <Col span={8}>
              <Card>
                <Statistic title="待处置资产" value={2} valueStyle={{ color: '#cf1322' }} />
              </Card>
            </Col>
          </Row>
          <Card title="资产概览" style={{ marginTop: 16 }}>
            <Paragraph type="secondary">暂无资产数据（占位）</Paragraph>
          </Card>
        </Col>
      </Row>
    </div>
  )
}
