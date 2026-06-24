import { useEffect, useMemo, useState } from 'react'
import { Card, Typography, Row, Col, Button, Statistic, Table, Select, Space, Tag, Steps, Progress, Empty } from 'antd'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  FileSearchOutlined,
  ExperimentOutlined,
  WarningOutlined,
  ExportOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  ReconciliationOutlined,
  TeamOutlined,
} from '@ant-design/icons'
import { api, type AuditRisk, type Project, type ImportJob, type AuditTestReport } from '../../api/client'
import { useAuthStore } from '../../stores/authStore'

const { Title, Paragraph } = Typography

const functionsList = [
  { key: 'projects', icon: <FileSearchOutlined />, label: '审计项目', path: '/audit/step/1' },
  { key: 'tests', icon: <ExperimentOutlined />, label: '测试执行', path: '/audit/step/4' },
  { key: 'bank-reconciliation', icon: <ReconciliationOutlined />, label: '银行调节表草稿', path: '/audit/bank-reconciliation' },
  { key: 'confirmations', icon: <TeamOutlined />, label: '往来函证控制表', path: '/audit/confirmations' },
  { key: 'findings', icon: <WarningOutlined />, label: '风险发现', path: '/audit/step/5' },
  { key: 'report', icon: <ExportOutlined />, label: '报告导出', path: '/audit/step/6' },
]

const RISK_LEVEL_LABEL: Record<string, string> = {
  high: '高',
  medium: '中',
  low: '低',
}

const RISK_STATUS_LABEL: Record<string, string> = {
  pending_review: '待复核',
  confirmed: '已确认',
  dismissed: '已驳回',
}

function deriveCurrentStep(job: ImportJob | null, report: AuditTestReport | null, riskCount: number): number {
  if (!job) return 0
  if (riskCount > 0) return 4
  if (report && report.total_transactions > 0) return 3
  if (job.entry_count > 0) return 2
  if (job.file_count > 0) return 1
  return 0
}

export function AuditWorkspace() {
  const location = useLocation()
  const navigate = useNavigate()
  const { currentLedgerId } = useAuthStore()
  const [projects, setProjects] = useState<Project[]>([])
  const [risks, setRisks] = useState<AuditRisk[]>([])
  const [jobs, setJobs] = useState<ImportJob[]>([])
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null)
  const [testReport, setTestReport] = useState<AuditTestReport | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    Promise.all([
      api.listProjects(),
      currentLedgerId ? api.listRisks(undefined, currentLedgerId) : Promise.resolve([]),
      currentLedgerId ? api.listImportJobs(currentLedgerId) : api.listImportJobs(),
      currentLedgerId ? api.getDashboardSummary(currentLedgerId) : api.getDashboardSummary(),
    ])
      .then(([projectList, riskList, jobList]) => {
        setProjects(projectList)
        setRisks(riskList)
        setJobs(jobList)
        if (projectList.length > 0) {
          setSelectedProjectId(projectList[0].id)
        }
      })
      .catch(() => {
        setProjects([])
        setRisks([])
        setJobs([])
      })
      .finally(() => setLoading(false))
  }, [currentLedgerId])

  const latestJob = jobs[0] || null

  useEffect(() => {
    if (!latestJob) {
      setTestReport(null)
      return
    }
    api.getAuditTestReport(latestJob.id)
      .then(setTestReport)
      .catch(() => setTestReport(null))
  }, [latestJob?.id])

  const activeProjects = projects.filter((p) => p.status === 'active').length
  const pendingTests = testReport
    ? Math.max(testReport.summary.total_findings, testReport.findings.filter((f) => f.status === 'pending_review').length)
    : risks.filter((r) => r.status === 'pending_review').length
  const currentStep = deriveCurrentStep(latestJob, testReport, risks.length)
  const selectedProject = projects.find((p) => p.id === selectedProjectId)

  const testProgressData = useMemo(() => {
    if (!testReport) {
      return [
        { key: 'integrity', name: '完整性测试', progress: latestJob?.entry_count ? 50 : 0, status: latestJob?.entry_count ? '进行中' : '待开始' },
        { key: 'accuracy', name: '准确性测试', progress: risks.length > 0 ? 80 : 0, status: risks.length > 0 ? '进行中' : '待开始' },
      ]
    }
    const items = [
      { key: 'completeness', name: '完整性测试', result: testReport.completeness_result },
      { key: 'accuracy', name: '准确性测试', result: testReport.accuracy_result },
      { key: 'cutoff', name: '截止性测试', result: testReport.cutoff_result },
      { key: 'classification', name: '分类测试', result: testReport.classification_result },
    ]
    return items.map((item) => {
      const passed = Boolean((item.result as { passed?: boolean }).passed)
      const findings = Number((item.result as { findings_count?: number }).findings_count || 0)
      return {
        key: item.key,
        name: item.name,
        progress: passed ? 100 : findings > 0 ? 60 : testReport.tested_transactions > 0 ? 40 : 0,
        status: passed ? '已完成' : testReport.tested_transactions > 0 ? '进行中' : '待开始',
      }
    })
  }, [testReport, latestJob, risks.length])

  const riskData = risks.slice(0, 10).map((risk) => ({
    key: String(risk.id),
    title: risk.title,
    level: RISK_LEVEL_LABEL[risk.risk_level] || risk.risk_level,
    status: RISK_STATUS_LABEL[risk.status] || risk.status,
  }))

  const testProgressColumns = [
    { title: '测试名称', dataIndex: 'name', key: 'name' },
    { title: '进度', dataIndex: 'progress', key: 'progress', render: (p: number) => <Progress percent={p} size="small" /> },
    { title: '状态', dataIndex: 'status', key: 'status', render: (s: string) => <Tag color={s === '已完成' ? 'success' : 'warning'}>{s}</Tag> },
  ]

  const riskColumns = [
    { title: '风险标题', dataIndex: 'title', key: 'title' },
    { title: '等级', dataIndex: 'level', key: 'level', render: (l: string) => <Tag color={l === '高' ? 'red' : 'orange'}>{l}</Tag> },
    { title: '状态', dataIndex: 'status', key: 'status', render: (s: string) => <Tag>{s}</Tag> },
  ]

  return (
    <div>
      <Title level={4}>审计工作台</Title>
      <Paragraph type="secondary">管理审计项目、执行测试、复核风险与导出报告</Paragraph>

      <Card style={{ marginBottom: 16 }} loading={loading}>
        <Row justify="space-between" align="middle">
          <Col>
            <Space>
              <Select
                value={selectedProjectId || undefined}
                onChange={setSelectedProjectId}
                style={{ width: 220 }}
                placeholder="选择审计项目"
                options={projects.map((p) => ({ value: p.id, label: p.name }))}
              />
              {selectedProject && (
                <Tag icon={<ClockCircleOutlined />} color="processing">
                  {selectedProject.status === 'completed' ? '已完成' : '进行中'}
                </Tag>
              )}
            </Space>
          </Col>
          <Col>
            <Space>
              <Button type="primary" icon={<ExperimentOutlined />} onClick={() => navigate('/audit/step/4')}>
                执行测试
              </Button>
              <Button icon={<ExportOutlined />} onClick={() => navigate('/audit/step/6')}>
                导出报告
              </Button>
            </Space>
          </Col>
        </Row>
      </Card>

      <Row gutter={16}>
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

        <Col span={18}>
          <Row gutter={[16, 16]}>
            <Col span={8}>
              <Card loading={loading}>
                <Statistic title="活跃项目" value={activeProjects || projects.length} valueStyle={{ color: '#1890ff' }} />
              </Card>
            </Col>
            <Col span={8}>
              <Card loading={loading}>
                <Statistic title="待执行测试" value={pendingTests} valueStyle={{ color: '#cf1322' }} />
              </Card>
            </Col>
            <Col span={8}>
              <Card loading={loading}>
                <Statistic title="风险发现" value={risks.length} valueStyle={{ color: '#faad14' }} />
              </Card>
            </Col>
          </Row>

          <Card title="项目进度" style={{ marginTop: 16 }} loading={loading}>
            <Steps
              size="small"
              current={currentStep}
              items={[
                { title: '选择范围', icon: currentStep > 0 ? <CheckCircleOutlined /> : <ClockCircleOutlined /> },
                { title: '导入证据', icon: currentStep > 1 ? <CheckCircleOutlined /> : <ClockCircleOutlined /> },
                { title: '导入序时簿', icon: currentStep > 2 ? <CheckCircleOutlined /> : <ClockCircleOutlined /> },
                { title: '执行测试', icon: currentStep > 3 ? <CheckCircleOutlined /> : <ClockCircleOutlined /> },
                { title: '复核发现', icon: currentStep > 4 ? <CheckCircleOutlined /> : <ClockCircleOutlined /> },
                { title: '导出报告', icon: <ClockCircleOutlined /> },
              ]}
            />
          </Card>

          <Card title="测试统计" style={{ marginTop: 16 }} loading={loading}>
            {testProgressData.length === 0 ? (
              <Empty description="暂无测试数据，请先创建审计导入任务" />
            ) : (
              <Table
                size="small"
                columns={testProgressColumns}
                dataSource={testProgressData}
                pagination={false}
                rowKey="key"
              />
            )}
          </Card>

          <Card title="风险清单" style={{ marginTop: 16 }} loading={loading}>
            {riskData.length === 0 ? (
              <Empty description="暂无风险发现" />
            ) : (
              <Table
                size="small"
                columns={riskColumns}
                dataSource={riskData}
                pagination={false}
                rowKey="key"
              />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  )
}
