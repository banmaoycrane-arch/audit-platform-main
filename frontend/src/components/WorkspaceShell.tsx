import { Card, Typography, Row, Col, Button, Space, Tag } from 'antd'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  BookOutlined,
  FileSearchOutlined,
  BankOutlined,
  PieChartOutlined,
  InboxOutlined,
  ShoppingOutlined,
  SafetyOutlined,
  TagOutlined,
} from '@ant-design/icons'

const { Title, Paragraph } = Typography

export interface WorkspaceFunctionItem {
  key: string
  icon: React.ReactNode
  label: string
  path: string
}

export interface WorkspaceShellProps {
  title: string
  description: string
  functionsList: WorkspaceFunctionItem[]
  children: React.ReactNode
}

const workspaceTabs = [
  { key: 'ledger', label: '财务总账', path: '/ledger/workspace', icon: <BookOutlined /> },
  { key: 'audit', label: '审计', path: '/audit/workspace', icon: <FileSearchOutlined /> },
  { key: 'bank', label: '银行', path: '/bank/workspace', icon: <BankOutlined /> },
  { key: 'tax', label: '税务', path: '/tax/workspace', icon: <PieChartOutlined /> },
  { key: 'basic', label: '基础资料', path: '/basic/workspace', icon: <InboxOutlined /> },
  { key: 'inventory', label: '存货', path: '/inventory/workspace', icon: <ShoppingOutlined /> },
  { key: 'fixed-assets', label: '固定资产', path: '/fixed-assets/workspace', icon: <SafetyOutlined /> },
  { key: 'document-tags', label: '文档标签', path: '/document-tags', icon: <TagOutlined /> },
]

export function WorkspaceShell({ title, description, functionsList, children }: WorkspaceShellProps) {
  const location = useLocation()
  const navigate = useNavigate()

  return (
    <div>
      <Title level={4}>{title}</Title>
      <Paragraph type="secondary">{description}</Paragraph>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={24}>
          <Space wrap size="small">
            {workspaceTabs.map((tab) => (
              <Tag
                key={tab.key}
                color={location.pathname.startsWith(tab.path) ? 'blue' : 'default'}
                icon={tab.icon}
                style={{
                  cursor: 'pointer',
                  padding: '4px 12px',
                  fontSize: '13px',
                  opacity: location.pathname.startsWith(tab.path) ? 1 : 0.7,
                }}
                onClick={() => navigate(tab.path)}
              >
                {tab.label}
              </Tag>
            ))}
          </Space>
        </Col>
      </Row>

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
          {children}
        </Col>
      </Row>
    </div>
  )
}