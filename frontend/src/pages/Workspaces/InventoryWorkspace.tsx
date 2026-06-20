import { Card, Typography, Row, Col, Button, Statistic, List } from 'antd'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  InboxOutlined,
  ShopOutlined,
  ImportOutlined,
  ExportOutlined,
  SwapOutlined,
  FileSearchOutlined,
  SettingOutlined,
} from '@ant-design/icons'

const { Title, Paragraph } = Typography

const functionsList = [
  { key: 'warehouses', icon: <ShopOutlined />, label: '仓库管理', path: '/basic/warehouses' },
  { key: 'materials', icon: <InboxOutlined />, label: '物料管理', path: '/basic/materials' },
  { key: 'purchase-in', icon: <ImportOutlined />, label: '采购入库', path: '/inventory/purchase-in' },
  { key: 'sale-out', icon: <ExportOutlined />, label: '销售出库', path: '/inventory/sale-out' },
  { key: 'stock-flow', icon: <SwapOutlined />, label: '库存流水', path: '/inventory/stock-flow' },
  { key: 'stock-receipt-ledger', icon: <FileSearchOutlined />, label: '库存收发台账', path: '/inventory/stock-receipt-ledger' },
  { key: 'settings', icon: <SettingOutlined />, label: '库存设置', path: '/inventory/settings' },
]

export function InventoryWorkspace() {
  const location = useLocation()
  const navigate = useNavigate()

  return (
    <div>
      <Title level={4}>进销存工作台</Title>
      <Paragraph type="secondary">管理采购、销售、库存流水与收发台账</Paragraph>

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
                <Statistic title="仓库数" value={3} />
              </Card>
            </Col>
            <Col span={8}>
              <Card>
                <Statistic title="SKU 数" value={156} />
              </Card>
            </Col>
            <Col span={8}>
              <Card>
                <Statistic title="本月收发笔数" value={42} valueStyle={{ color: '#3f8600' }} />
              </Card>
            </Col>
          </Row>
          <Card title="库存概览" style={{ marginTop: 16 }}>
            <Paragraph type="secondary">暂无库存数据（占位）</Paragraph>
          </Card>
        </Col>
      </Row>
    </div>
  )
}
