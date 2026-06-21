import { useEffect, useState } from 'react'
import { Card, Typography, Statistic, Row, Col, Button, Badge, Avatar, Drawer, List, Alert, Space, Dropdown, Empty, Modal, Form, Input, message, Tag } from 'antd'
import {
  BookOutlined,
  AuditOutlined,
  BankOutlined,
  ExperimentOutlined,
  DatabaseOutlined,
  BellOutlined,
  UserOutlined,
  LogoutOutlined,
  FileTextOutlined,
  PieChartOutlined,
  WarningOutlined,
  WalletOutlined,
  InboxOutlined,
  ShopOutlined,
  TeamOutlined,
  ApartmentOutlined,
  ProjectOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useAuthStore } from '../stores/authStore'
import { LedgerSelector } from '../components/LedgerSelector'

const { Title, Paragraph, Text } = Typography

interface DashboardData {
  user: {
    id: number
    username: string
    team: { id: number; name: string } | null
  }
  voucher_count: number
  unclosed_periods: number
  unaudited_periods: number
  pending_risks: number
  notifications: number
  module_status: {
    ledger: { pending_vouchers: number; unclosed_periods: number }
    audit: { active_projects: number; pending_tests: number }
    bank: { unreconciled: number }
    tax: { pending_invoices: number }
    basic: { incomplete_accounts: number }
  }
}

const modules = [
  {
    key: 'ledger',
    title: '财务总账',
    icon: <BookOutlined style={{ fontSize: 32, color: '#1890ff' }} />,
    path: '/ledger/workspace',
    stats: (d: DashboardData) => [
      { label: '待处理凭证', value: d.module_status.ledger.pending_vouchers },
      { label: '未结账期间', value: d.module_status.ledger.unclosed_periods },
    ],
  },
  {
    key: 'audit',
    title: '审计系统',
    icon: <AuditOutlined style={{ fontSize: 32, color: '#52c41a' }} />,
    path: '/audit/workspace',
    stats: (d: DashboardData) => [
      { label: '活跃项目', value: d.module_status.audit.active_projects },
      { label: '待执行测试', value: d.module_status.audit.pending_tests },
    ],
  },
  {
    key: 'bank',
    title: '银行模块',
    icon: <BankOutlined style={{ fontSize: 32, color: '#faad14' }} />,
    path: '/bank/workspace',
    stats: (d: DashboardData) => [
      { label: '未对账笔数', value: d.module_status.bank.unreconciled },
    ],
  },
  {
    key: 'tax',
    title: '税务模块',
    icon: <ExperimentOutlined style={{ fontSize: 32, color: '#eb2f96' }} />,
    path: '/tax/workspace',
    stats: (d: DashboardData) => [
      { label: '待处理发票', value: d.module_status.tax.pending_invoices },
    ],
  },
  {
    key: 'basic',
    title: '基础资料',
    icon: <DatabaseOutlined style={{ fontSize: 32, color: '#13c2c2' }} />,
    path: '/basic/workspace',
    stats: (d: DashboardData) => [
      { label: '待完善科目', value: d.module_status.basic.incomplete_accounts },
    ],
  },
  {
    key: 'projects',
    title: '项目管理',
    icon: <ProjectOutlined style={{ fontSize: 32, color: '#722ed1' }} />,
    path: '/projects',
    stats: () => [
      { label: '进行中项目', value: 0 },
      { label: '已完成项目', value: 0 },
    ],
  },
]

export function WorkspacePage() {
  const navigate = useNavigate()
  const { user, logout, currentLedgerId, userLedgers, authContext } = useAuthStore()
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(false)
  const [notifyOpen, setNotifyOpen] = useState(false)
  const [passwordOpen, setPasswordOpen] = useState(false)
  const [passwordSaving, setPasswordSaving] = useState(false)
  const [dashboardNotice, setDashboardNotice] = useState<string | null>(null)
  const [passwordForm] = Form.useForm()

  useEffect(() => {
    setLoading(true)
    setDashboardNotice(null)
    api
      .getDashboardSummary(currentLedgerId || undefined)
      .then((res) => {
        setData(res as DashboardData)
      })
      .catch((error) => {
        setData({
          user: {
            id: user?.id || 0,
            username: user?.username || '',
            team: null,
          },
          voucher_count: 0,
          unclosed_periods: 0,
          unaudited_periods: 0,
          pending_risks: 0,
          notifications: 0,
          module_status: {
            ledger: { pending_vouchers: 0, unclosed_periods: 0 },
            audit: { active_projects: 0, pending_tests: 0 },
            bank: { unreconciled: 0 },
            tax: { pending_invoices: 0 },
            basic: { incomplete_accounts: 0 },
          },
        })
        setDashboardNotice(error instanceof Error ? error.message : '暂时无法取得工作台统计数据')
      })
      .finally(() => setLoading(false))
  }, [currentLedgerId, user])

  const displayName = user?.username || data?.user?.username || '用户'
  const teamName = data?.user?.team?.name || '未加入团队'

  const alerts = [
    data && data.unclosed_periods > 0
      ? `本月还有 ${data.unclosed_periods} 个期间未结账，请及时处理。`
      : null,
    data && data.module_status.audit.pending_tests > 0
      ? `审计项目还有 ${data.module_status.audit.pending_tests} 项测试未完成。`
      : null,
  ].filter(Boolean) as string[]

  const handleSetPassword = async (values: { password: string; confirmPassword: string }) => {
    if (values.password !== values.confirmPassword) {
      message.error('两次输入的密码不一致')
      return
    }
    try {
      setPasswordSaving(true)
      const response = await fetch('/api/auth/password', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('token')}`,
        },
        body: JSON.stringify({ password: values.password }),
      })
      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.detail || data.error?.message || '设置密码失败')
      }
      message.success(data.message || '密码已设置')
      passwordForm.resetFields()
      setPasswordOpen(false)
    } catch (error) {
      message.error(error instanceof Error ? error.message : '设置密码失败')
    } finally {
      setPasswordSaving(false)
    }
  }

  const userMenuItems = [
    { key: 'profile', label: <span><UserOutlined /> {displayName}</span> },
    { key: 'team', label: <span><TeamOutlined /> {teamName}</span> },
    { type: 'divider' as const },
    { key: 'team-management', label: <span><TeamOutlined /> 团队管理</span>, onClick: () => navigate('/team-management') },
    { key: 'ledger-management', label: <span><BookOutlined /> 账套管理</span>, onClick: () => navigate('/ledger-management') },
    { key: 'projects', label: <span><ProjectOutlined /> 项目管理</span>, onClick: () => navigate('/projects') },
    { key: 'set-password', label: <span><UserOutlined /> 设置登录密码</span>, onClick: () => setPasswordOpen(true) },
    { type: 'divider' as const },
    { key: 'logout', label: <span><LogoutOutlined /> 退出登录</span>, onClick: logout },
  ]

  // 如果用户无授权账套，则进入访客/待绑定状态：只展示模块入口和公共说明，不展示账套隔离数据。
  const hasNoLedgers = userLedgers.length === 0 && !loading

  return (
    <div>
      {/* 顶部区域 */}
      <Row justify="space-between" align="middle" style={{ marginBottom: 24 }}>
        <Col>
          <Space direction="vertical" size={0}>
            <Title level={3} style={{ margin: 0 }}>
              欢迎回来，{displayName}
            </Title>
            <Text type="secondary">{teamName}</Text>
          </Space>
        </Col>
        <Col>
          <Space size="large">
            <LedgerSelector />
            <Badge count={data?.notifications || 0} size="small">
              <BellOutlined style={{ fontSize: 20, cursor: 'pointer' }} onClick={() => setNotifyOpen(true)} />
            </Badge>
            <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
              <Avatar icon={<UserOutlined />} style={{ cursor: 'pointer' }} />
            </Dropdown>
          </Space>
        </Col>
      </Row>

      {/* 通知 Drawer */}
      <Drawer title="消息通知" placement="right" onClose={() => setNotifyOpen(false)} open={notifyOpen} width={360}>
        <List
          dataSource={[]}
          locale={{ emptyText: '暂无新通知' }}
          renderItem={() => null}
        />
      </Drawer>

      <Modal
        title="设置登录密码"
        open={passwordOpen}
        onCancel={() => setPasswordOpen(false)}
        onOk={() => passwordForm.submit()}
        confirmLoading={passwordSaving}
        okText="保存密码"
        cancelText="取消"
      >
        <Alert
          title="设置后可使用手机号或用户名加密码登录。"
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
        />
        <Form form={passwordForm} layout="vertical" onFinish={handleSetPassword}>
          <Form.Item name="password" label="新密码" rules={[{ required: true, message: '请输入新密码' }, { min: 6, message: '密码至少需要 6 位' }]}> 
            <Input.Password placeholder="请输入新密码" />
          </Form.Item>
          <Form.Item name="confirmPassword" label="确认密码" rules={[{ required: true, message: '请再次输入新密码' }]}> 
            <Input.Password placeholder="请再次输入新密码" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 访客/待绑定提示 */}
      {hasNoLedgers && authContext && (
        <Alert
          title="当前为访客/待绑定状态"
          description={
            <div>
              <Text type="secondary">
                您已经可以登录并查看系统模块和公共说明。由于尚未绑定以下内容，系统不会展示任何账套隔离数据：
              </Text>
              <div style={{ marginTop: 8, marginBottom: 12 }}>
                {authContext.missing_bindings.map((key) => {
                  const label = {
                    team: '团队',
                    ledger: '账套',
                    project: '项目',
                    accounting_entity: '会计主体',
                  }[key] || key
                  return <Tag color="orange" key={key}>{label}</Tag>
                })}
              </div>
              <Text type="secondary">
                请通过以下入口申请绑定鉴权：
              </Text>
            </div>
          }
          type="warning"
          showIcon
          action={(
            <Space>
              <Button size="small" onClick={() => navigate('/team-management')}>团队控制台（申请加入团队）</Button>
              <Button size="small" onClick={() => navigate('/ledger-management')}>账套控制台（申请访问账套）</Button>
              <Button size="small" onClick={() => navigate('/projects')}>项目控制台（申请关联项目）</Button>
            </Space>
          )}
          style={{ marginBottom: 16 }}
        />
      )}

      {dashboardNotice && !hasNoLedgers && (
        <Alert
          title="工作台统计暂不可用"
          description={dashboardNotice}
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      {/* 工作进度提醒 */}
      {alerts.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          {alerts.map((text, idx) => (
            <Alert key={idx} title={text} type="warning" showIcon style={{ marginBottom: 8 }} />
          ))}
        </div>
      )}

      {/* 模块状态卡片 */}
      <Row gutter={[16, 16]}>
        {modules.map((mod) => (
          <Col xs={24} sm={12} lg={8} key={mod.key}>
            <Card
              hoverable
              loading={loading}
              onClick={() => navigate(hasNoLedgers ? '/onboarding' : mod.path)}
              bodyStyle={{ padding: 20 }}
            >
              <Space align="start" size={16}>
                {mod.icon}
                <div style={{ flex: 1 }}>
                  <Title level={5} style={{ margin: 0, marginBottom: 8 }}>{mod.title}</Title>
                  {hasNoLedgers ? (
                    <Empty
                      description="需完成绑定后查看账套数据"
                      image={Empty.PRESENTED_IMAGE_SIMPLE}
                    />
                  ) : (
                    <Row gutter={16}>
                      {data &&
                        mod.stats(data).map((s) => (
                          <Col key={s.label}>
                            <Statistic value={s.value} title={s.label} valueStyle={{ fontSize: 18 }} />
                          </Col>
                        ))}
                    </Row>
                  )}
                  <Button
                    type={hasNoLedgers ? 'default' : 'primary'}
                    size="small"
                    style={{ marginTop: 12 }}
                    onClick={(e) => {
                      e.stopPropagation()
                      navigate(hasNoLedgers ? '/onboarding' : mod.path)
                    }}
                  >
                    {hasNoLedgers ? '申请/完成绑定' : `进入${mod.title}`}
                  </Button>
                </div>
              </Space>
            </Card>
          </Col>
        ))}
      </Row>

      {/* 最近活动区（占位） */}
      <Card title="最近活动" style={{ marginTop: 24 }}>
        <Paragraph type="secondary">暂无最近活动记录</Paragraph>
      </Card>
    </div>
  )
}
