import { useState } from 'react'
import { Card, Typography, Row, Col, Button, Statistic, Table, Select, Space, Tag } from 'antd'
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

const { Title, Paragraph } = Typography

const functionsList = [
  { key: 'vouchers', icon: <FileTextOutlined />, label: '凭证管理', path: '/ledger/vouchers/step/1' },
  { key: 'books', icon: <BookOutlined />, label: '账簿管理', path: '/ledger/books' },
  { key: 'general-ledger', icon: <BarsOutlined />, label: '总账', path: '/ledger/general-ledger' },
  { key: 'subsidiary-ledger', icon: <BarsOutlined />, label: '明细账', path: '/ledger/subsidiary-ledger' },
  { key: 'trial-balance', icon: <PieChartOutlined />, label: '科目余额表', path: '/reports/trial-balance' },
  { key: 'balance-sheet', icon: <DollarOutlined />, label: '试算平衡表', path: '/reports/balance-sheet' },
]

const pendingVouchersColumns = [
  { title: '凭证号', dataIndex: 'voucher_no', key: 'voucher_no' },
  { title: '日期', dataIndex: 'date', key: 'date' },
  { title: '摘要', dataIndex: 'summary', key: 'summary' },
  { title: '金额', dataIndex: 'amount', key: 'amount' },
  { title: '状态', dataIndex: 'status', key: 'status', render: (s: string) => <Tag color="warning">{s}</Tag> },
]

const pendingVouchersData = [
  { voucher_no: 'PZ-2026-001', date: '2026-06-01', summary: '采购原材料', amount: '¥ 50,000.00', status: '待复核' },
  { voucher_no: 'PZ-2026-002', date: '2026-06-02', summary: '支付工资', amount: '¥ 120,000.00', status: '待过账' },
  { voucher_no: 'PZ-2026-003', date: '2026-06-03', summary: '销售收入', amount: '¥ 200,000.00', status: '待复核' },
]

export function LedgerWorkspace() {
  const location = useLocation()
  const navigate = useNavigate()
  const [period, setPeriod] = useState('2026-06')

  return (
    <div>
      <Title level={4}>财务总账工作台</Title>
      <Paragraph type="secondary">管理凭证、账簿、期间与科目余额</Paragraph>

      {/* 顶部操作栏 */}
      <Card style={{ marginBottom: 16 }}>
        <Row justify="space-between" align="middle">
          <Col>
            <Space>
              <Select value={period} onChange={setPeriod} style={{ width: 160 }}>
                <Select.Option value="2026-06">2026年06月</Select.Option>
                <Select.Option value="2026-05">2026年05月</Select.Option>
                <Select.Option value="2026-Q2">2026年第二季度</Select.Option>
              </Select>
              <Tag icon={<CheckCircleOutlined />} color="success">期间已开启</Tag>
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
        {/* 左侧功能列表 */}
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

        {/* 右侧数据卡片区 */}
        <Col span={18}>
          <Row gutter={[16, 16]}>
            <Col span={8}>
              <Card>
                <Statistic title="待处理凭证" value={3} valueStyle={{ color: '#cf1322' }} />
              </Card>
            </Col>
            <Col span={8}>
              <Card>
                <Statistic title="已开启期间" value={1} valueStyle={{ color: '#3f8600' }} />
              </Card>
            </Col>
            <Col span={8}>
              <Card>
                <Statistic title="科目余额异常" value={0} />
              </Card>
            </Col>
          </Row>

          <Card title="待处理凭证列表" style={{ marginTop: 16 }}>
            <Table
              size="small"
              columns={pendingVouchersColumns}
              dataSource={pendingVouchersData}
              pagination={false}
              rowKey="voucher_no"
            />
          </Card>

          <Card title="期间状态" style={{ marginTop: 16 }}>
            <Space>
              <Tag color="green">2026-06 已开启</Tag>
              <Tag>2026-05 已结账</Tag>
              <Tag>2026-04 已结账</Tag>
            </Space>
          </Card>
        </Col>
      </Row>
    </div>
  )
}
