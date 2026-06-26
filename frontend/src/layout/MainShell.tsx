import { Layout, Menu, Typography, Space, Input } from 'antd'
import { Outlet, useNavigate, useLocation, Link } from 'react-router-dom'
import {
  HomeOutlined,
  FileTextOutlined,
  AppstoreOutlined,
  AuditOutlined,
  TeamOutlined,
  BookOutlined,
  WarningOutlined,
  WalletOutlined,
  PieChartOutlined,
  RobotOutlined,
  BankOutlined,
  ExperimentOutlined,
  ShopOutlined,
  DatabaseOutlined,
  ApartmentOutlined,
  UserOutlined,
  InboxOutlined,
  SettingOutlined,
  ReconciliationOutlined,
  CarOutlined,
} from '@ant-design/icons'
import { LedgerSelector } from '../components/LedgerSelector'

const { Header, Sider, Content } = Layout
const { Title } = Typography

const navItems = [
  { key: '/workspace', icon: <HomeOutlined />, label: <Link to="/workspace">工作台</Link> },
  { key: '/agent', icon: <RobotOutlined />, label: <Link to="/agent">Agent 助手</Link> },
  {
    key: 'ledger',
    icon: <BookOutlined />,
    label: '财务总账',
    children: [
      { key: '/ledger/workspace', icon: <HomeOutlined />, label: <Link to="/ledger/workspace">工作台</Link> },
      { key: '/ledger/files', icon: <FileTextOutlined />, label: <Link to="/ledger/files">账套文件</Link> },
      {
        key: 'ledger-vouchers',
        icon: <FileTextOutlined />,
        label: '凭证管理',
        children: [
          { key: '/ledger/vouchers/step/1', label: <Link to="/ledger/vouchers/step/1">Step 1 选择原始资料类型</Link> },
          { key: '/ledger/vouchers/step/2', label: <Link to="/ledger/vouchers/step/2">Step 2 导入原始凭证</Link> },
          { key: '/ledger/vouchers/step/3', label: <Link to="/ledger/vouchers/step/3">Step 3 AI 生成会计分录</Link> },
          { key: '/ledger/vouchers/step/4', label: <Link to="/ledger/vouchers/step/4">Step 4 复核会计分录</Link> },
          { key: '/ledger/vouchers/step/5', label: <Link to="/ledger/vouchers/step/5">Step 5 确认导出</Link> },
          { key: '/ledger/entries', label: <Link to="/ledger/entries">凭证查询</Link> },
        ],
      },
      { key: '/ledger/books', label: <Link to="/ledger/books">账簿管理</Link> },
      { key: '/ledger/general-ledger', label: <Link to="/ledger/general-ledger">总账</Link> },
      { key: '/ledger/subsidiary-ledger', label: <Link to="/ledger/subsidiary-ledger">明细账</Link> },
      { key: '/reports/trial-balance', icon: <PieChartOutlined />, label: <Link to="/reports/trial-balance">科目余额表</Link> },
      { key: '/reports/trial-balance-statement', label: <Link to="/reports/trial-balance">试算平衡表</Link> },
    ],
  },
  {
    key: 'audit-system',
    icon: <AuditOutlined />,
    label: '审计系统',
    children: [
      { key: '/audit/workspace', icon: <HomeOutlined />, label: <Link to="/audit/workspace">工作台</Link> },
      { key: '/audit/step/1', label: <Link to="/audit/step/1">Step 1 选择范围</Link> },
      { key: '/audit/step/2', label: <Link to="/audit/step/2">Step 2 导入证据</Link> },
      { key: '/audit/step/3', label: <Link to="/audit/step/3">Step 3 导入序时簿</Link> },
      { key: '/audit/step/4', label: <Link to="/audit/step/4">Step 4 执行测试</Link> },
      { key: '/audit/bank-reconciliation', icon: <ReconciliationOutlined />, label: <Link to="/audit/bank-reconciliation">银行调节表草稿</Link> },
      { key: '/audit/confirmations', label: <Link to="/audit/confirmations">往来函证控制表</Link> },
      { key: '/audit/step/5', label: <Link to="/audit/step/5">Step 5 复核发现</Link> },
      { key: '/audit/step/6', label: <Link to="/audit/step/6">Step 6 导出报告</Link> },
    ],
  },
  {
    key: 'bank-module',
    icon: <BankOutlined />,
    label: '银行模块',
    children: [
      { key: '/bank/workspace', icon: <HomeOutlined />, label: <Link to="/bank/workspace">工作台</Link> },
      { key: '/bank/accounts', label: <Link to="/bank/accounts">银行账户</Link> },
      { key: '/bank/third-party-accounts', label: <Link to="/bank/third-party-accounts">三方支付账户</Link> },
      { key: '/bank/aggregate-accounts', label: <Link to="/bank/aggregate-accounts">聚合账户</Link> },
      { key: '/bank/journal', label: <Link to="/bank/journal">日记账</Link> },
      { key: '/bank/settings', icon: <SettingOutlined />, label: <Link to="/bank/settings">账户设置</Link> },
      { key: '/bank/reconciliation', icon: <ReconciliationOutlined />, label: <Link to="/bank/reconciliation">自动对账</Link> },
    ],
  },
  {
    key: 'tax-module',
    icon: <ExperimentOutlined />,
    label: '税务模块',
    children: [
      { key: '/tax/workspace', icon: <HomeOutlined />, label: <Link to="/tax/workspace">工作台</Link> },
      { key: '/tax/invoices', label: <Link to="/tax/invoices">发票管理</Link> },
      { key: '/tax/assistant', icon: <RobotOutlined />, label: <Link to="/tax/assistant">涉税助手</Link> },
    ],
  },
  {
    key: 'fixed-assets-module',
    icon: <CarOutlined />,
    label: '固定资产模块',
    children: [
      { key: '/fixed-assets/workspace', icon: <HomeOutlined />, label: <Link to="/fixed-assets/workspace">工作台</Link> },
      { key: '/fixed-assets/cards', label: <Link to="/fixed-assets/cards">资产卡片（预留）</Link> },
      { key: '/fixed-assets/depreciation', label: <Link to="/fixed-assets/depreciation">折旧计提（预留）</Link> },
    ],
  },
  {
    key: 'inventory-module',
    icon: <ShopOutlined />,
    label: '进销存模块',
    children: [
      { key: '/inventory/workspace', icon: <HomeOutlined />, label: <Link to="/inventory/workspace">工作台</Link> },
      { key: '/inventory/purchase-in', label: <Link to="/inventory/purchase-in">采购入库（预留）</Link> },
      { key: '/inventory/stock-flow', label: <Link to="/inventory/stock-flow">库存流水（预留）</Link> },
    ],
  },
  {
    key: 'basic',
    icon: <DatabaseOutlined />,
    label: '基础资料',
    children: [
      { key: '/basic/workspace', icon: <HomeOutlined />, label: <Link to="/basic/workspace">工作台</Link> },
      { key: '/basic/coa', icon: <BookOutlined />, label: <Link to="/basic/coa">会计科目</Link> },
      { key: '/basic/org-units', icon: <ApartmentOutlined />, label: <Link to="/basic/org-units">企业组织架构</Link> },
      { key: '/basic/personnel', icon: <UserOutlined />, label: <Link to="/basic/personnel">员工/协作人员</Link> },
      { key: '/basic/counterparties', icon: <TeamOutlined />, label: <Link to="/basic/counterparties">往来单位</Link> },
      { key: '/basic/opening-balances', icon: <WalletOutlined />, label: <Link to="/basic/opening-balances">期初数据</Link> },
      { key: '/basic/materials', icon: <InboxOutlined />, label: <Link to="/basic/materials">SKU/物料</Link> },
      { key: '/basic/warehouses', icon: <ShopOutlined />, label: <Link to="/basic/warehouses">仓库</Link> },
    ],
  },
  {
    key: 'management',
    icon: <SettingOutlined />,
    label: '管理中心',
    children: [
      { key: '/team-management', icon: <TeamOutlined />, label: <Link to="/team-management">团队管理</Link> },
      { key: '/ledger-management', icon: <BookOutlined />, label: <Link to="/ledger-management">账套管理</Link> },
      { key: '/ledger/files', icon: <FileTextOutlined />, label: <Link to="/ledger/files">账套文件</Link> },
      { key: '/projects', icon: <AppstoreOutlined />, label: <Link to="/projects">项目管理</Link> },
    ],
  },
  {
    key: 'custom-module',
    icon: <AppstoreOutlined />,
    label: '自定义模块（客户可扩展）',
    children: [
      { key: 'custom-ledger-entries', icon: <FileTextOutlined />, label: <Link to="/ledger/entries">凭证查询</Link> },
      { key: '/risks', icon: <WarningOutlined />, label: <Link to="/risks">专项风险列表入口</Link> },
      { key: 'custom-workspace', icon: <HomeOutlined />, label: <Link to="/workspace">客户自定义工作台入口</Link> },
    ],
  }
]

const selectedKeyAliases: Record<string, string> = {
  '/entries': '/ledger/entries',
  '/fixed-assets': '/fixed-assets/workspace',
  '/inventory': '/inventory/workspace',
}

function getSelectedKey(pathname: string) {
  if (pathname.startsWith('/accounting/step/')) {
    return pathname.replace('/accounting/step/', '/ledger/vouchers/step/')
  }
  if (pathname.startsWith('/fixed-assets/') && pathname !== '/fixed-assets/workspace') {
    return pathname
  }
  if (pathname.startsWith('/inventory/') && pathname !== '/inventory/workspace') {
    return pathname
  }
  if (pathname === '/') {
    return '/workspace'
  }
  return selectedKeyAliases[pathname] || pathname
}

export function MainShell() {
  const navigate = useNavigate()
  const location = useLocation()
  const selectedKey = getSelectedKey(location.pathname)

  const handleMenuClick = (e: { key: string; keyPath: string[] }) => {
    // 点击父菜单时默认导航到对应工作台
    const parentKey = e.keyPath[e.keyPath.length - 1]
    const workspaceMap: Record<string, string> = {
      ledger: '/ledger/workspace',
      'audit-system': '/audit/workspace',
      'bank-module': '/bank/workspace',
      'tax-module': '/tax/workspace',
      'fixed-assets-module': '/fixed-assets/workspace',
      'inventory-module': '/inventory/workspace',
      basic: '/basic/workspace',
    }
    if (e.key === parentKey && workspaceMap[parentKey]) {
      navigate(workspaceMap[parentKey])
    }
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ background: '#001529', padding: '0 16px', display: 'flex', alignItems: 'center', gap: 24 }}>
        <Title level={4} style={{ color: '#fff', margin: 0, cursor: 'pointer' }} onClick={() => navigate('/')}>
          财务向量审计风险识别系统
        </Title>
        <Input.Search
          placeholder="搜索单据 / 凭证 / 风险..."
          allowClear
          style={{ maxWidth: 320, marginLeft: 16 }}
        />
        <div style={{ flex: 1 }} />
        <Space style={{ color: '#fff' }}>
          <LedgerSelector />
          <span style={{ cursor: 'pointer' }} onClick={() => navigate('/')}>首页</span>
        </Space>
      </Header>
      <Layout style={{ height: 'calc(100vh - 64px)' }}>
        <Sider
          width={240}
          theme="light"
          style={{
            height: '100%',
            overflowY: 'auto',
            overflowX: 'hidden',
          }}
        >
          <Menu
            mode="inline"
            selectedKeys={[selectedKey]}
            defaultOpenKeys={[
              'ledger',
              'ledger-vouchers',
              'audit-system',
              'bank-module',
              'tax-module',
              'fixed-assets-module',
              'inventory-module',
              'basic',
              'management',
              'custom-module',
            ]}
            items={navItems}
            style={{ height: '100%', borderRight: 0 }}
            onClick={handleMenuClick}
          />
        </Sider>
        <Layout style={{ padding: '16px', height: '100%', overflowY: 'auto' }}>
          <Content style={{ background: '#fff', padding: '16px', minHeight: 280 }}>
            <Outlet />
          </Content>
        </Layout>
      </Layout>
    </Layout>
  )
}
