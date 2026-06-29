import { useEffect, useState } from 'react'
import { Alert, Button, Card, Col, Form, Input, message, Modal, Result, Row, Select, Space, Statistic, Table, Tag, Typography } from 'antd'
import { AuditOutlined, BookOutlined, CheckCircleOutlined, ClockCircleOutlined, ProjectOutlined, TeamOutlined, UserOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { api, type BindingRequest, type SuperAdminOverview } from '../api/client'
import { useAuthStore } from '../stores/authStore'

const { Title, Paragraph } = Typography

const STATUS_MAP: Record<string, { label: string; color: string }> = {
  pending: { label: '待审批', color: 'orange' },
  approved: { label: '已通过', color: 'green' },
  rejected: { label: '已驳回', color: 'red' },
}

const ROLE_MAP: Record<string, string> = {
  viewer: '查看',
  accountant: '记账/编制',
  admin: '管理',
}

export function SuperAdminPage() {
  const navigate = useNavigate()
  const { authContext } = useAuthStore()
  const [overview, setOverview] = useState<SuperAdminOverview | null>(null)
  const [requests, setRequests] = useState<BindingRequest[]>([])
  const [statusFilter, setStatusFilter] = useState<'pending' | 'approved' | 'rejected' | 'all'>('pending')
  const [loading, setLoading] = useState(false)
  const [reviewOpen, setReviewOpen] = useState(false)
  const [reviewAction, setReviewAction] = useState<'approve' | 'reject'>('approve')
  const [selectedRequest, setSelectedRequest] = useState<BindingRequest | null>(null)
  const [reviewForm] = Form.useForm()

  const isSuperAdmin = Boolean(authContext?.is_super_admin)

  const loadData = async (nextStatus = statusFilter) => {
    if (!isSuperAdmin) return
    setLoading(true)
    try {
      const [overviewResponse, requestResponse] = await Promise.all([
        api.getSuperAdminOverview(),
        api.listSuperAdminBindingRequests(nextStatus),
      ])
      setOverview(overviewResponse)
      setRequests(requestResponse)
    } catch (error) {
      message.error(error instanceof Error ? error.message : '加载超级管理员数据失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadData()
  }, [isSuperAdmin])

  const openReview = (record: BindingRequest, action: 'approve' | 'reject') => {
    setSelectedRequest(record)
    setReviewAction(action)
    reviewForm.resetFields()
    setReviewOpen(true)
  }

  const handleReview = async () => {
    if (!selectedRequest) return
    const values = await reviewForm.validateFields()
    try {
      if (reviewAction === 'approve') {
        await api.approveBindingRequest(selectedRequest.id, values.review_comment || null)
        message.success('已审批通过，授权关系已写入')
      } else {
        await api.rejectBindingRequest(selectedRequest.id, values.review_comment || null)
        message.success('已驳回申请')
      }
      setReviewOpen(false)
      setSelectedRequest(null)
      void loadData()
    } catch (error) {
      message.error(error instanceof Error ? error.message : '处理申请失败')
    }
  }

  if (!isSuperAdmin) {
    return (
      <Result
        status="403"
        title="需要开发者超级管理员权限"
        subTitle="当前账号不是平台级开发者超级管理员，不能进入该入口。"
        extra={<Button type="primary" onClick={() => navigate('/workspace')}>返回工作台</Button>}
      />
    )
  }

  const columns = [
    { title: '申请人', dataIndex: 'requester_name', key: 'requester_name', render: (value: string | null) => value || '-' },
    { title: '手机号', dataIndex: 'requester_phone', key: 'requester_phone', render: (value: string | null) => value || '-' },
    { title: '团队', dataIndex: 'team_name', key: 'team_name', render: (value: string | null) => value || '-' },
    { title: '账簿', dataIndex: 'ledger_name', key: 'ledger_name', render: (value: string | null) => value || '-' },
    { title: '项目', dataIndex: 'project_name', key: 'project_name', render: (value: string | null) => value || '-' },
    {
      title: '申请角色',
      dataIndex: 'requested_role',
      key: 'requested_role',
      render: (value: string) => ROLE_MAP[value] || value,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (value: string) => {
        const status = STATUS_MAP[value] || { label: value, color: 'default' }
        return <Tag color={status.color}>{status.label}</Tag>
      },
    },
    { title: '申请原因', dataIndex: 'reason', key: 'reason', ellipsis: true, render: (value: string | null) => value || '-' },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (value: string | null) => (value ? new Date(value).toLocaleString('zh-CN') : '-'),
    },
    {
      title: '操作',
      key: 'action',
      fixed: 'right' as const,
      width: 150,
      render: (_: unknown, record: BindingRequest) => (
        record.status === 'pending' ? (
          <Space>
            <Button size="small" type="link" onClick={() => openReview(record, 'approve')}>通过</Button>
            <Button size="small" danger type="link" onClick={() => openReview(record, 'reject')}>驳回</Button>
          </Space>
        ) : '-'
      ),
    },
  ]

  return (
    <div style={{ padding: 24 }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <div>
          <Title level={3}>
            <AuditOutlined /> 开发者超级管理员
          </Title>
          <Paragraph type="secondary">
            平台级开发者入口，用于系统初始化、授权兜底和全部绑定申请审批。该入口不复用账簿 admin 权限。
          </Paragraph>
        </div>

        <Alert
          type="warning"
          showIcon
          message="超级管理员权限说明"
          description="当前账号可查看平台级概览，并审批任意团队、账簿、项目绑定申请。财务账簿数据访问仍建议通过明确账簿授权和审计留痕执行。"
        />

        <Row gutter={[16, 16]}>
          <Col xs={24} md={8} lg={4}>
            <Card><Statistic title="用户数" value={overview?.user_count || 0} prefix={<UserOutlined />} /></Card>
          </Col>
          <Col xs={24} md={8} lg={5}>
            <Card><Statistic title="团队数" value={overview?.team_count || 0} prefix={<TeamOutlined />} /></Card>
          </Col>
          <Col xs={24} md={8} lg={5}>
            <Card><Statistic title="账簿数" value={overview?.ledger_count || 0} prefix={<BookOutlined />} /></Card>
          </Col>
          <Col xs={24} md={8} lg={5}>
            <Card><Statistic title="项目数" value={overview?.project_count || 0} prefix={<ProjectOutlined />} /></Card>
          </Col>
          <Col xs={24} md={8} lg={5}>
            <Card><Statistic title="待审批申请" value={overview?.pending_binding_request_count || 0} prefix={<ClockCircleOutlined />} /></Card>
          </Col>
        </Row>

        <Card
          title="全部绑定申请"
          extra={(
            <Space>
              <Select
                value={statusFilter}
                style={{ width: 140 }}
                options={[
                  { value: 'pending', label: '待审批' },
                  { value: 'approved', label: '已通过' },
                  { value: 'rejected', label: '已驳回' },
                  { value: 'all', label: '全部' },
                ]}
                onChange={(value) => {
                  setStatusFilter(value)
                  void loadData(value)
                }}
              />
              <Button onClick={() => loadData()} loading={loading}>刷新</Button>
            </Space>
          )}
        >
          <Table
            rowKey="id"
            loading={loading}
            columns={columns}
            dataSource={requests}
            scroll={{ x: 1300 }}
          />
        </Card>
      </Space>

      <Modal
        title={reviewAction === 'approve' ? '审批通过绑定申请' : '驳回绑定申请'}
        open={reviewOpen}
        onCancel={() => setReviewOpen(false)}
        onOk={handleReview}
        okText={reviewAction === 'approve' ? '确认通过' : '确认驳回'}
        okButtonProps={{ danger: reviewAction === 'reject', icon: reviewAction === 'approve' ? <CheckCircleOutlined /> : undefined }}
      >
        <Form form={reviewForm} layout="vertical">
          <Form.Item label="审批意见" name="review_comment">
            <Input.TextArea rows={3} maxLength={200} showCount placeholder="可填写审批意见或驳回原因" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
