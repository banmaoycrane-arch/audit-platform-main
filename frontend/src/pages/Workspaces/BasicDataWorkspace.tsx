import { useEffect, useState } from 'react'
import { Card, Row, Col, Statistic, Empty } from 'antd'
import { useNavigate } from 'react-router-dom'
import {
  BookOutlined,
  ApartmentOutlined,
  UserOutlined,
  TeamOutlined,
  InboxOutlined,
  ShopOutlined,
} from '@ant-design/icons'
import { api } from '../../api/client'
import { useAuthStore } from '../../stores/authStore'
import { WorkspaceShell } from '../../components/WorkspaceShell'

const functionsList = [
  { key: 'coa', icon: <BookOutlined />, label: '会计科目', path: '/ledger/dimensions?tab=coa' },
  { key: 'org-units', icon: <ApartmentOutlined />, label: '组织架构', path: '/basic/org-units' },
  { key: 'personnel', icon: <UserOutlined />, label: '员工', path: '/basic/personnel' },
  { key: 'counterparties', icon: <TeamOutlined />, label: '往来单位', path: '/basic/counterparties' },
  { key: 'materials', icon: <InboxOutlined />, label: '物料', path: '/basic/materials' },
  { key: 'warehouses', icon: <ShopOutlined />, label: '仓库', path: '/basic/warehouses' },
]

export function BasicDataWorkspace() {
  const navigate = useNavigate()
  const { currentLedgerId } = useAuthStore()
  const [accountCount, setAccountCount] = useState(0)
  const [incompleteAccounts, setIncompleteAccounts] = useState(0)
  const [counterpartyCount, setCounterpartyCount] = useState(0)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    Promise.all([
      api.listChartOfAccounts(),
      api.listCounterparties(),
      currentLedgerId ? api.getDashboardSummary(currentLedgerId) : api.getDashboardSummary(),
    ])
      .then(([accounts, counterparties, summary]) => {
        const activeAccounts = accounts.filter((a) => a.status === 'active')
        setAccountCount(activeAccounts.length)
        setIncompleteAccounts(summary.module_status.basic.incomplete_accounts)
        setCounterpartyCount(counterparties.length)
      })
      .catch(() => {
        setAccountCount(0)
        setIncompleteAccounts(0)
        setCounterpartyCount(0)
      })
      .finally(() => setLoading(false))
  }, [currentLedgerId])

  return (
    <WorkspaceShell
      title="基础资料工作台"
      description="维护科目、组织架构、往来单位、物料仓库等底层核算对象"
      functionsList={functionsList}
    >
      <Row gutter={[16, 16]}>
        <Col span={8}>
          <Card loading={loading}>
            <Statistic title="会计科目数" value={accountCount} />
          </Card>
        </Col>
        <Col span={8}>
          <Card loading={loading}>
            <Statistic title="待完善科目" value={incompleteAccounts} valueStyle={{ color: '#cf1322' }} />
          </Card>
        </Col>
        <Col span={8}>
          <Card loading={loading}>
            <Statistic title="往来单位数" value={counterpartyCount} />
          </Card>
        </Col>
      </Row>
      <Card title="资料完整性概览" style={{ marginTop: 16 }} loading={loading}>
        {accountCount === 0 && counterpartyCount === 0 ? (
          <Empty description="暂无基础资料，请从左侧导航维护科目和往来单位" />
        ) : (
          <div style={{ color: '#666' }}>
            当前已维护 {accountCount} 个会计科目、{counterpartyCount} 个往来单位。
            {incompleteAccounts > 0 ? ` 另有 ${incompleteAccounts} 个科目待完善。` : ' 科目资料完整。'}
          </div>
        )}
      </Card>
    </WorkspaceShell>
  )
}