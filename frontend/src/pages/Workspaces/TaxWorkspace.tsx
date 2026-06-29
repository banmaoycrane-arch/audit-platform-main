import { Card, Row, Col, Statistic, Empty } from 'antd'
import { useNavigate } from 'react-router-dom'
import {
  ExperimentOutlined,
  FileTextOutlined,
  RobotOutlined,
  PieChartOutlined,
  FileSearchOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons'
import { WorkspaceShell } from '../../components/WorkspaceShell'

const functionsList = [
  { key: 'invoices', icon: <FileTextOutlined />, label: '发票管理', path: '/tax/invoices' },
  { key: 'invoice-issuance-ledger', icon: <FileSearchOutlined />, label: '发票开具台账', path: '/tax/invoice-issuance-ledger' },
  { key: 'certification-deduction-ledger', icon: <CheckCircleOutlined />, label: '认证抵扣台账', path: '/tax/certification-deduction-ledger' },
  { key: 'assistant', icon: <RobotOutlined />, label: '涉税助手', path: '/tax/assistant' },
  { key: 'reports', icon: <PieChartOutlined />, label: '税务报表', path: '/tax/assistant' },
]

export function TaxWorkspace() {
  const navigate = useNavigate()

  return (
    <WorkspaceShell
      title="税务工作台"
      description="管理发票、涉税助手与税务知识库"
      functionsList={functionsList}
    >
      <Row gutter={[16, 16]}>
        <Col span={8}>
          <Card>
            <Statistic title="待处理发票" value={0} />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic title="涉税风险" value={0} />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic title="本月已认证" value={0} />
          </Card>
        </Col>
      </Row>
      <Card title="发票状态概览" style={{ marginTop: 16 }}>
        <Empty description="暂无发票数据，请先通过发票管理导入发票" />
      </Card>
    </WorkspaceShell>
  )
}