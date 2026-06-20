import { Card, Table, Button, Steps, Typography, Tag, Space, Modal, Input, Select, Rate, message, Alert } from 'antd'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { ExclamationCircleOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { api, type AuditFinding } from '../../api/client'
import { FlowNav } from '../../components/FlowNav'

const { Title, Text } = Typography

type ReviewStatus = 'pending' | 'confirmed' | 'false_positive' | 'resolved'

type Finding = AuditFinding & {
  reviewStatus: ReviewStatus
}

const statusLabels: Record<ReviewStatus, string> = {
  pending: '待复核',
  confirmed: '已确认',
  false_positive: '误报',
  resolved: '已解决'
}

export function Step5ReviewFindings() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const jobId = Number(searchParams.get('jobId') || 0)
  const [findings, setFindings] = useState<Finding[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const [modalVisible, setModalVisible] = useState(false)
  const [currentFinding, setCurrentFinding] = useState<Finding | null>(null)
  const [reviewComment, setReviewComment] = useState('')
  const [reviewAction, setReviewAction] = useState<ReviewStatus>('confirmed')
  const currentStep = 4

  useEffect(() => {
    if (!jobId) return
    setLoading(true)
    api.getAuditFindings(jobId)
      .then(data => {
        setFindings(data.map(item => ({
          ...item,
          reviewStatus: ((item.status as ReviewStatus) || 'pending')
        })))
      })
      .catch(error => {
        message.error('获取审计发现失败，请先执行审计测试')
        console.error('Get audit findings error:', error)
      })
      .finally(() => setLoading(false))
  }, [jobId])

  const openReviewModal = (finding: Finding) => {
    setCurrentFinding(finding)
    setReviewComment('')
    setReviewAction(finding.reviewStatus === 'pending' ? 'confirmed' : finding.reviewStatus)
    setModalVisible(true)
  }

  const persistReview = async (finding: Finding, action: ReviewStatus, comment?: string) => {
    if (!finding.db_id) {
      throw new Error('该审计发现尚未持久化，无法复核')
    }
    return api.reviewAuditFinding(finding.db_id, action, comment)
  }

  const handleReview = async () => {
    if (!currentFinding) return
    try {
      await persistReview(currentFinding, reviewAction, reviewComment)
      setFindings(findings.map(f =>
        f.id === currentFinding.id
          ? { ...f, reviewStatus: reviewAction, status: reviewAction }
          : f
      ))
      message.success('复核已留痕')
    } catch (error) {
      console.error('复核失败', error)
      message.error('复核失败')
    } finally {
      setModalVisible(false)
      setReviewComment('')
    }
  }

  const batchUpdate = async (action: ReviewStatus) => {
    const targets = findings.filter(f => selectedRowKeys.includes(f.id))
    if (targets.length === 0) return
    try {
      await Promise.all(targets.map(f => persistReview(f, action)))
      setFindings(findings.map(f =>
        selectedRowKeys.includes(f.id)
          ? { ...f, reviewStatus: action, status: action }
          : f
      ))
      setSelectedRowKeys([])
      message.success(`已批量${action === 'confirmed' ? '确认' : '标记为误报'}`)
    } catch (error) {
      console.error('批量复核失败', error)
      message.error('批量复核失败')
    }
  }

  const batchConfirm = () => {
    void batchUpdate('confirmed')
  }

  const batchFalsePositive = () => {
    void batchUpdate('false_positive')
  }

  const rowSelection = {
    selectedRowKeys,
    onChange: (keys: React.Key[]) => setSelectedRowKeys(keys)
  }

  const columns: ColumnsType<Finding> = [
    {
      title: '风险级别',
      dataIndex: 'severity',
      key: 'severity',
      render: (val: string) => {
        const colors: Record<string, string> = { high: 'red', medium: 'orange', low: 'green' }
        return <Tag color={colors[val]}>{val.toUpperCase()}</Tag>
      }
    },
    {
      title: '风险类型',
      dataIndex: 'finding_type',
      key: 'finding_type'
    },
    {
      title: '标题',
      dataIndex: 'finding_title',
      key: 'finding_title',
      render: (val: string, record: Finding) => (
        <a onClick={() => openReviewModal(record)}>{val}</a>
      )
    },
    {
      title: '业务类型',
      dataIndex: 'business_type',
      key: 'business_type'
    },
    {
      title: '关联文件',
      dataIndex: 'related_files',
      key: 'related_files',
      render: (files: string[]) => files.length ? files.join('、') : '-'
    },
    {
      title: '判断强度',
      key: 'confidence',
      render: () => <Rate disabled defaultValue={4} allowHalf style={{ fontSize: '12px' }} />
    },
    {
      title: '状态',
      dataIndex: 'reviewStatus',
      key: 'reviewStatus',
      render: (val: ReviewStatus) => {
        const colors: Record<ReviewStatus, string> = {
          pending: 'default',
          confirmed: 'blue',
          false_positive: 'gray',
          resolved: 'green'
        }
        return <Tag color={colors[val]}>{statusLabels[val]}</Tag>
      }
    }
  ]

  const pendingCount = findings.filter(f => f.reviewStatus === 'pending').length

  return (
    <div style={{ padding: '24px', maxWidth: '1100px', margin: '0 auto' }}>
      <Steps
        current={currentStep}
        items={[
          { title: '选择范围' },
          { title: '导入资料' },
          { title: '导入分录' },
          { title: '执行测试' },
          { title: '复核发现' },
          { title: '导出报告' }
        ]}
        style={{ marginBottom: '32px' }}
      />

      <FlowNav prev="/audit/step/4" next="/audit/step/6" style={{ marginBottom: '16px' }} />

      <Space style={{ marginBottom: '16px', width: '100%', justifyContent: 'space-between' }}>
        <Title level={4} style={{ margin: 0 }}>审计发现复核</Title>
        <Space>
          <Tag color={pendingCount > 0 ? 'orange' : 'green'}>
            待复核 {pendingCount}/{findings.length}
          </Tag>
        </Space>
      </Space>

      {!jobId && (
        <Alert
          message="尚未找到可复核的审计测试结果"
          description="请先执行审计测试，再进入审计发现复核。"
          type="warning"
          showIcon
          style={{ marginBottom: '16px' }}
        />
      )}

      <Card>
        <div style={{ marginBottom: '16px', display: 'flex', gap: '12px', alignItems: 'center' }}>
          <Button
            type="primary"
            onClick={batchConfirm}
            disabled={selectedRowKeys.length === 0}
          >
            批量确认 ({selectedRowKeys.length})
          </Button>
          <Button
            onClick={batchFalsePositive}
            disabled={selectedRowKeys.length === 0}
          >
            标记为误报
          </Button>
        </div>

        <Table
          rowSelection={rowSelection}
          columns={columns}
          dataSource={findings}
          rowKey="id"
          pagination={{ pageSize: 10 }}
          size="small"
          loading={loading}
          locale={{ emptyText: jobId ? '暂无需要复核的审计发现' : '请先完成审计测试，再进入复核发现步骤' }}
        />
      </Card>

      <Modal
        title={
          <Space>
            <ExclamationCircleOutlined style={{ color: '#faad14' }} />
            复核审计发现
          </Space>
        }
        open={modalVisible}
        onOk={handleReview}
        onCancel={() => setModalVisible(false)}
        width={700}
      >
        {currentFinding && (
          <div>
            <Card size="small" style={{ marginBottom: '16px' }}>
              <Space direction="vertical" style={{ width: '100%' }}>
                <Space>
                  <Tag color={
                    currentFinding.severity === 'high' ? 'red' :
                    currentFinding.severity === 'medium' ? 'orange' : 'green'
                  }>
                    {currentFinding.severity.toUpperCase()}
                  </Tag>
                  <Tag>{currentFinding.finding_type}</Tag>
                  <Text type="secondary">业务类型: {currentFinding.business_type}</Text>
                </Space>
                <Text strong>{currentFinding.finding_title}</Text>
                <Text type="secondary">{currentFinding.finding_description}</Text>
                <Text>审计程序: {currentFinding.audit_procedure}</Text>
                <Text>审计结论: {currentFinding.audit_conclusion}</Text>
                <Text type="danger">风险表述: {currentFinding.risk_statement}</Text>
                <Text>建议措施: {currentFinding.recommendation}</Text>
              </Space>
            </Card>

            <Space direction="vertical" style={{ width: '100%' }}>
              <div>
                <label style={{ display: 'block', marginBottom: '8px' }}>处理动作</label>
                <Select value={reviewAction} onChange={setReviewAction} style={{ width: '100%' }}>
                  <Select.Option value="confirmed">确认问题 - 纳入审计报告</Select.Option>
                  <Select.Option value="false_positive">标记为误报 - 不纳入报告</Select.Option>
                  <Select.Option value="resolved">已解决 - 需要跟踪处理</Select.Option>
                </Select>
              </div>
              <div>
                <label style={{ display: 'block', marginBottom: '8px' }}>复核意见</label>
                <Input.TextArea
                  rows={4}
                  value={reviewComment}
                  onChange={e => setReviewComment(e.target.value)}
                  placeholder="请输入复核意见..."
                />
              </div>
            </Space>
          </div>
        )}
      </Modal>

      <div style={{ marginTop: '24px', display: 'flex', gap: '12px' }}>
        <Button onClick={() => navigate(jobId ? `/audit/step/4?jobId=${jobId}` : '/audit/step/4')}>
          上一步
        </Button>
        <Button
          type="primary"
          onClick={() => navigate(jobId ? `/audit/step/6?jobId=${jobId}` : '/audit/step/6')}
          disabled={pendingCount > 0}
        >
          下一步导出报告
        </Button>
      </div>
    </div>
  )
}
