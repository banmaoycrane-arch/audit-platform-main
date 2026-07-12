import { useEffect, useState } from 'react'
import { Layout, Menu, Typography, Space, Input, Badge, Button, Drawer, List, Tag, message } from 'antd'
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
  DashboardOutlined,
  CheckSquareOutlined,
  BellOutlined,
  CrownOutlined,
} from '@ant-design/icons'
import { LedgerSelector } from '../components/LedgerSelector'
import { RouteTabs } from '../components/RouteTabs'
import { voucherFlowNavKey } from '../utils/voucherFlowRoutes'
import { LEDGER_NAV_GROUPS } from '../utils/ledgerNavTaxonomy'
import { api, type AuditNotification } from '../api/client'
import { useAuthStore } from '../stores/authStore'

const { Header, Sider, Content } = Layout
const { Title } = Typography

function buildNavItems(isSuperAdmin: boolean) {
  const ledgerNavChildren = [
    { key: '/ledger/workspace', icon: <HomeOutlined />, label: <Link to="/ledger/workspace">工作台</Link> },
    { key: '/ledger/files', icon: <FileTextOutlined />, label: <Link to="/ledger/files">证据云空间</Link> },
    ...LEDGER_NAV_GROUPS.map((group) => ({
      key: `ledger-group-${group.key}`,
      label: group.label,
      children: group.items.map((item) => ({
        key: item.path,
        label: <Link to={item.path}>{item.label}</Link>,
      })),
    })),
    { key: '/ledger/control-defects', label: <Link to="/ledger/control-defects">内控待办</Link> },
  ]

  return [
  { key: '/workspace', icon: <HomeOutlined />, label: <Link to="/workspace">工作台</Link> },
  { key: '/agent', icon: <RobotOutlined />, label: <Link to="/agent">Agent 助手</Link> },
  { key: '/mvp-metrics', icon: <RobotOutlined />, label: <Link to="/mvp-metrics">MVP 验证看板</Link> },
  {
    key: 'ledger',
    icon: <BookOutlined />,
    label: '财务总账',
    children: ledgerNavChildren,
  },
  {
    key: 'audit-system',
    icon: <AuditOutlined />,
    label: '审计系统',
    children: [
      { key: '/audit/workspace', icon: <HomeOutlined />, label: <Link to="/audit/workspace">工作台</Link> },
      { key: '/audit/dashboard', icon: <DashboardOutlined />, label: <Link to="/audit/dashboard">审计协作台</Link> },
      { key: '/audit/tasks', icon: <CheckSquareOutlined />, label: <Link to="/audit/tasks">任务管理</Link> },
      { key: '/audit/review-requests', icon: <AuditOutlined />, label: <Link to="/audit/review-requests">复核请求</Link> },
      { key: '/audit/step/1', label: <Link to="/audit/step/1">Step 1 选择范围</Link> },
      { key: '/audit/step/2', label: <Link to="/audit/step/2">Step 2 导入证据</Link> },
      { key: '/audit/step/3', label: <Link to="/audit/step/3">Step 3 导入序时簿</Link> },
      { key: '/audit/step/4', label: <Link to="/audit/step/4">Step 4 执行测试</Link> },
      { key: '/audit/bank-reconciliation', icon: <ReconciliationOutlined />, label: <Link to="/audit/bank-reconciliation">银行调节表草稿</Link> },
      { key: '/audit/confirmations', label: <Link to="/audit/confirmations">往来函证控制表</Link> },
      { key: '/audit/workpapers', label: <Link to="/audit/workpapers">审计工作底稿</Link> },
      { key: '/audit/workflow', label: <Link to="/audit/workflow">审计工作流</Link> },
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
      { key: '/basic/coa', icon: <BookOutlined />, label: <Link to="/ledger/dimensions?tab=coa">会计科目</Link> },
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
      { key: '/ledger-management', icon: <BookOutlined />, label: <Link to="/ledger-management">账簿管理</Link> },
      { key: '/scope-settings', icon: <SettingOutlined />, label: <Link to="/scope-settings">管理配置</Link> },
      { key: '/parser-engine', icon: <ExperimentOutlined />, label: <Link to="/parser-engine">解析引擎管理</Link> },
      { key: '/parser-engine/config', icon: <SettingOutlined />, label: <Link to="/parser-engine/config">解析引擎配置</Link> },
      { key: '/ledger/files', icon: <FileTextOutlined />, label: <Link to="/ledger/files">证据云空间</Link> },
      { key: '/projects', icon: <AppstoreOutlined />, label: <Link to="/projects">项目管理</Link> },
      ...(isSuperAdmin ? [{ key: '/super-admin', icon: <CrownOutlined />, label: <Link to="/super-admin">开发者超级管理员</Link> }] : []),
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
}

const selectedKeyAliases: Record<string, string> = {
  '/entries': '/ledger/entries',
  '/ledger/vouchers': '/ledger/entries',
  '/basic/coa': '/ledger/dimensions',
  '/fixed-assets': '/fixed-assets/workspace',
  '/inventory': '/inventory/workspace',
}

const NOTIFICATION_EVENT_LABEL: Record<string, string> = {
  task_assigned: '任务分配',
  review_submitted: '提交复核',
  review_approved: '复核通过',
  review_changes_requested: '退回修改',
  review_merged: '合并归档',
  comment_mentioned: '评论提及',
  workpaper_marker_mentioned: '底稿标记',
}

function getNotificationTargetPath(notification: AuditNotification) {
  if (notification.target_type === 'task') return `/audit/tasks/${notification.target_id}`
  if (notification.target_type === 'review_request') return `/audit/review-requests/${notification.target_id}`
  if (notification.target_type === 'workpaper_version') return `/audit/workpapers?version_id=${notification.target_id}`
  return '/audit/dashboard'
}

function getNotificationTargetLabel(notification: AuditNotification) {
  if (notification.target_type === 'task') return `任务 #${notification.target_id}`
  if (notification.target_type === 'review_request') return `复核请求 #${notification.target_id}`
  if (notification.target_type === 'workpaper_version') return `底稿版本 #${notification.target_id}`
  return `${notification.target_type} #${notification.target_id}`
}

function getSelectedKey(pathname: string) {
  const flowKey = voucherFlowNavKey(pathname)
  if (flowKey) return flowKey
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
  const { authContext } = useAuthStore()
  const navItems = buildNavItems(Boolean(authContext?.is_super_admin))
  const selectedKey = getSelectedKey(location.pathname)
  const [notificationOpen, setNotificationOpen] = useState(false)
  const [notifications, setNotifications] = useState<AuditNotification[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [notificationLoading, setNotificationLoading] = useState(false)
  const [openKeys, setOpenKeys] = useState<string[]>([])

  const loadNotifications = () => {
    setNotificationLoading(true)
    api
      .listAuditNotifications({ limit: 30 })
      .then((response) => {
        setNotifications(response.items)
        setUnreadCount(response.unread_count)
      })
      .catch(() => {})
      .finally(() => setNotificationLoading(false))
  }

  useEffect(() => {
    loadNotifications()
  }, [])

  const handleOpenNotifications = () => {
    setNotificationOpen(true)
    loadNotifications()
  }

  const handleReadNotification = async (notification: AuditNotification) => {
    try {
      if (!notification.is_read) {
        await api.markAuditNotificationRead(notification.id)
      }
      setNotificationOpen(false)
      navigate(getNotificationTargetPath(notification))
      loadNotifications()
    } catch (error: any) {
      message.error(error.message || '通知处理失败')
    }
  }

  const handleReadAllNotifications = async () => {
    try {
      await api.markAllAuditNotificationsRead()
      loadNotifications()
      message.success('审计通知已全部标记为已读')
    } catch (error: any) {
      message.error(error.message || '标记失败')
    }
  }

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
          <Button type="text" style={{ color: '#fff' }} onClick={handleOpenNotifications}>
            <Badge count={unreadCount} size="small">
              <BellOutlined style={{ color: '#fff', fontSize: 18 }} />
            </Badge>
            <span style={{ marginLeft: 8 }}>审计通知</span>
          </Button>
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
            openKeys={openKeys}
            onOpenChange={setOpenKeys}
            items={navItems}
            style={{ height: '100%', borderRight: 0 }}
            onClick={handleMenuClick}
          />
        </Sider>
        <Layout style={{ height: '100%', overflow: 'hidden', background: '#f5f7fb' }}>
          <RouteTabs />
          <Content
            style={{
              background: '#fff',
              margin: 16,
              padding: 16,
              minHeight: 280,
              overflow: 'auto',
              borderRadius: 8,
              boxShadow: '0 1px 3px rgba(15, 23, 42, 0.08)',
            }}
          >
            <Outlet />
          </Content>
        </Layout>
      </Layout>
      <Drawer
        title="审计协作通知"
        open={notificationOpen}
        onClose={() => setNotificationOpen(false)}
        width={420}
        extra={
          <Button size="small" onClick={handleReadAllNotifications} disabled={unreadCount === 0}>
            全部已读
          </Button>
        }
      >
        <List
          loading={notificationLoading}
          dataSource={notifications}
          locale={{ emptyText: '暂无审计通知' }}
          renderItem={(item) => (
            <List.Item onClick={() => handleReadNotification(item)} style={{ cursor: 'pointer' }}>
              <List.Item.Meta
                title={
                  <Space>
                    {!item.is_read && <Badge status="processing" />}
                    <span>{item.title}</span>
                    <Tag>{NOTIFICATION_EVENT_LABEL[item.event_type] || item.event_type}</Tag>
                  </Space>
                }
                description={
                  <Space direction="vertical" size={2}>
                    {item.content && <span>{item.content}</span>}
                    <span>点击后进入：{getNotificationTargetLabel(item)}</span>
                    <span>{item.created_at ? new Date(item.created_at).toLocaleString('zh-CN') : '-'}</span>
                  </Space>
                }
              />
            </List.Item>
          )}
        />
      </Drawer>
    </Layout>
  )
}
