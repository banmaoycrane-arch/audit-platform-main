import { Card, Button, Steps, Typography, Space, Progress, message, Alert } from 'antd'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useState } from 'react'
import { SafetyCertificateOutlined, FileSearchOutlined, ClockCircleOutlined, TagOutlined } from '@ant-design/icons'
import { api, type AuditTestReport } from '../../api/client'
import { FlowNav } from '../../components/FlowNav'

const { Title } = Typography

interface TestResult {
  name: string
  key: 'completeness' | 'accuracy' | 'cutoff' | 'classification'
  status: 'pending' | 'running' | 'completed' | 'error'
  progress: number
  findingCount: number
  passed?: boolean
}

const initialTests: TestResult[] = [
  { name: '完整性测试', key: 'completeness', status: 'pending', progress: 0, findingCount: 0 },
  { name: '准确性测试', key: 'accuracy', status: 'pending', progress: 0, findingCount: 0 },
  { name: '截止性测试', key: 'cutoff', status: 'pending', progress: 0, findingCount: 0 },
  { name: '分类测试', key: 'classification', status: 'pending', progress: 0, findingCount: 0 }
]

function getFindingCount(report: AuditTestReport, key: TestResult['key']) {
  const byType = report.summary.by_type || {}
  if (key === 'completeness') {
    return (byType.missing_contract || 0) + (byType.missing_inventory || 0) + (byType.missing_invoice || 0) + (byType.missing_payment || 0)
  }
  if (key === 'accuracy') {
    return byType.mismatch_amount || 0
  }
  if (key === 'cutoff') {
    return byType.timing_anomaly || 0
  }
  if (key === 'classification') {
    return byType.classification_mismatch || 0
  }
  return 0
}

function isPassed(report: AuditTestReport, key: TestResult['key']) {
  if (key === 'completeness') {
    return Boolean(report.completeness_result?.summary?.rate >= 0.95)
  }
  if (key === 'accuracy') {
    return Boolean(report.accuracy_result?.summary?.rate >= 0.95)
  }
  if (key === 'cutoff') {
    return report.cutoff_result?.pass !== false
  }
  return !report.findings.some(f => f.finding_type === 'classification_mismatch')
}

export function Step4RunTests() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const jobId = Number(searchParams.get('jobId') || 0)
  const currentStep = 3
  const [running, setRunning] = useState(false)
  const [tests, setTests] = useState<TestResult[]>(initialTests)
  const [report, setReport] = useState<AuditTestReport | null>(null)

  const applyReport = (nextReport: AuditTestReport) => {
    setReport(nextReport)
    setTests(initialTests.map(test => ({
      ...test,
      status: 'completed',
      progress: 100,
      findingCount: getFindingCount(nextReport, test.key),
      passed: isPassed(nextReport, test.key)
    })))
  }

  const runAllTests = async () => {
    if (!jobId) {
      message.warning('缺少导入任务编号，请从上一步重新进入')
      return
    }

    setRunning(true)
    setTests(initialTests.map(test => ({ ...test, status: 'running', progress: 40 })))
    try {
      const nextReport = await api.runAuditTests(jobId)
      applyReport(nextReport)
      message.success(`审计测试完成，发现 ${nextReport.summary.total_findings} 项异常`)
    } catch (error) {
      setTests(initialTests.map(test => ({ ...test, status: 'error', progress: 0 })))
      message.error('审计测试执行失败')
      console.error('Audit test error:', error)
    } finally {
      setRunning(false)
    }
  }

  const totalFindings = report?.summary.total_findings ?? tests.reduce((sum, t) => sum + t.findingCount, 0)
  const completedCount = tests.filter(t => t.status === 'completed').length

  const getIcon = (index: number) => {
    const icons = [<SafetyCertificateOutlined />, <FileSearchOutlined />, <ClockCircleOutlined />, <TagOutlined />]
    return icons[index]
  }

  const getStatusColor = (status: TestResult['status']) => {
    switch (status) {
      case 'completed': return '#52c41a'
      case 'running': return '#1890ff'
      case 'error': return '#ff4d4f'
      default: return '#d9d9d9'
    }
  }

  return (
    <div style={{ padding: '24px', maxWidth: '800px', margin: '0 auto' }}>
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

      <FlowNav prev="/audit/step/3" next="/audit/step/5" style={{ marginBottom: '16px' }} />

      <Space style={{ marginBottom: '16px', width: '100%', justifyContent: 'space-between' }}>
        <Title level={4} style={{ margin: 0 }}>执行审计测试</Title>
        <Space>
          <span style={{ color: '#666' }}>已完成 {completedCount}/{tests.length}</span>
          <Progress
            percent={Math.round((completedCount / tests.length) * 100)}
            size="small"
            style={{ width: '100px' }}
          />
        </Space>
      </Space>

      {!jobId && (
        <Alert
          title="缺少导入任务编号"
          description="请从导入资料步骤重新进入，否则无法执行真实审计测试。"
          type="warning"
          showIcon
          style={{ marginBottom: '16px' }}
        />
      )}

      <Card style={{ marginBottom: '24px' }}>
        {tests.map((test, index) => (
          <Card
            key={test.name}
            size="small"
            style={{ marginBottom: '12px', borderLeft: `4px solid ${getStatusColor(test.status)}` }}
          >
            <Space style={{ width: '100%', justifyContent: 'space-between' }}>
              <Space>
                {getIcon(index)}
                <span style={{ fontWeight: 500 }}>{test.name}</span>
              </Space>
              <Space>
                {test.status === 'completed' && (
                  <span style={{ color: test.findingCount > 0 ? '#faad14' : '#52c41a' }}>
                    完成 {test.findingCount > 0 ? `, ${test.findingCount}项异常` : ', 无异常'}
                  </span>
                )}
                {test.status === 'running' && <span style={{ color: '#1890ff' }}>执行中...</span>}
                {test.status === 'pending' && <span style={{ color: '#999' }}>待执行</span>}
                {test.status === 'error' && <span style={{ color: '#ff4d4f' }}>执行失败</span>}
              </Space>
            </Space>
            {test.status === 'running' && (
              <Progress percent={test.progress} size="small" style={{ marginTop: '8px' }} />
            )}
          </Card>
        ))}

        <Button
          type="primary"
          size="large"
          onClick={runAllTests}
          loading={running}
          disabled={!jobId}
          style={{ width: '100%', marginTop: '16px' }}
        >
          {running ? '执行中...' : '执行全部测试'}
        </Button>
      </Card>

      {report && (
        <Alert
          title="测试完成"
          description={`共发现 ${totalFindings} 项异常，请点击“下一步”复核审计发现。`}
          type={totalFindings > 0 ? 'info' : 'success'}
          showIcon
          style={{ marginBottom: '16px' }}
        />
      )}

      <div style={{ marginTop: '24px', display: 'flex', gap: '12px' }}>
        <Button onClick={() => navigate(jobId ? `/audit/step/3?jobId=${jobId}` : '/audit/step/3')}>
          上一步
        </Button>
        <Button
          type="primary"
          onClick={() => navigate(`/audit/step/5?jobId=${jobId}`)}
          disabled={completedCount < tests.length || !jobId}
        >
          下一步复核发现
        </Button>
      </div>
    </div>
  )
}
