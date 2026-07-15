import { Alert, Card, Row, Col, Statistic, Empty, Button, Space, Typography } from 'antd'
import { useNavigate, Link } from 'react-router-dom'
import {
  ApiOutlined,
  BookOutlined,
  FileTextOutlined,
  RobotOutlined,
  PieChartOutlined,
  FileSearchOutlined,
  CheckCircleOutlined,
  RightOutlined,
} from '@ant-design/icons'
import { WorkspaceShell } from '../../components/WorkspaceShell'

const { Paragraph, Text } = Typography

const functionsList = [
  { key: 'bookkeeping', icon: <BookOutlined />, label: '记账导入（主线）', path: '/ledger/vouchers/step/1' },
  { key: 'invoices', icon: <FileTextOutlined />, label: '发票文件管理', path: '/tax/invoices' },
  { key: 'connections', icon: <ApiOutlined />, label: '税局直连（可选）', path: '/tax/connections' },
  { key: 'invoice-issuance-ledger', icon: <FileSearchOutlined />, label: '发票开具台账', path: '/tax/invoice-issuance-ledger' },
  { key: 'certification-deduction-ledger', icon: <CheckCircleOutlined />, label: '认证抵扣台账', path: '/tax/certification-deduction-ledger' },
  { key: 'assistant', icon: <RobotOutlined />, label: '涉税助手', path: '/tax/assistant' },
]

export function TaxWorkspace() {
  const navigate = useNavigate()

  return (
    <WorkspaceShell
      title="税务增值（可选）"
      description="记账请用「财务总账」导入客户文件；本区仅在需要代开票/代取票时启用税局直连。"
      functionsList={functionsList}
    >
      <Alert
        type="success"
        showIcon
        title="近期策略：只做记账、客户只给文件"
        description={(
          <Space direction="vertical" size={4}>
            <Text>
              无需 etax 登录、无需合作商 IP 池。客户发来序时簿/发票/流水 →
              <Link to="/ledger/vouchers/step/1"> Step1 序时簿导入 </Link>
              → 复核入账 → 三大表。
            </Text>
            <Text type="secondary">
              当客户要求「帮我在税局里开票/取票」时，再启用下方「税局直连」；大客户自动化开票请单独立项乐企/航天百旺。
            </Text>
          </Space>
        )}
        style={{ marginBottom: 16 }}
      />

      <Card
        title="记账主线（推荐）"
        style={{ marginBottom: 16 }}
        extra={(
          <Button type="primary" icon={<RightOutlined />} onClick={() => navigate('/ledger/vouchers/step/1')}>
            去序时簿导入
          </Button>
        )}
      >
        <Paragraph style={{ marginBottom: 8 }}>
          代账多客户场景：每家客户一个账簿，每批资料一个导入任务。发票 PDF、OFD、Excel 均可走现有解析与 Step4 凭证草稿流程。
        </Paragraph>
        <Space wrap>
          <Button onClick={() => navigate('/ledger/files')}>证据云空间</Button>
          <Button onClick={() => navigate('/reports')}>财务报表</Button>
        </Space>
      </Card>

      <Row gutter={[16, 16]}>
        <Col span={8}>
          <Card>
            <Statistic title="待处理发票文件" value={0} />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic title="涉税风险（规则）" value={0} />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic title="税局直连绑定" value={0} suffix="家" />
          </Card>
        </Col>
      </Row>

      <Card
        title="税局直连（代开票/取票）— 可选增值"
        style={{ marginTop: 16 }}
        extra={(
          <Button onClick={() => navigate('/tax/connections')}>查看税务连接</Button>
        )}
      >
        <Empty
          description={(
            <span>
              未启用。仅当客户明确要求代操作电子税务局（开票/取票/勾选）时，再配置城市 IP 与 Worker 扫码登录。
              <br />
              <Text type="secondary">记账本身不需要开通此项。</Text>
            </span>
          )}
        />
      </Card>

      <Card title="发票文件概览" style={{ marginTop: 16 }}>
        <Empty description="暂无发票文件。请通过「发票文件管理」或财务总账导入任务上传客户资料" />
      </Card>
    </WorkspaceShell>
  )
}
