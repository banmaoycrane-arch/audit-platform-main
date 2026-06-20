import { useState } from 'react'
import { Card, Typography, Row, Col, Button, Statistic, Table, Select, Space, Tag, Steps, Progress } from 'antd'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  AuditOutlined,
  FileSearchOutlined,
  ExperimentOutlined,
  WarningOutlined,
  ExportOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons'

const { Title, Paragraph } = Typography

const functionsList = [
  { key: 'projects', icon: <FileSearchOutlined />, label: '审计项目', path: '/audit/step/1' },
  { key: 'tests', icon: <ExperimentOutlined />, label: '测试执行', path: '/audit/step/4' },
  { key: 'findings', icon: <WarningOutlined />, label: '风险发现', path: '/audit/step/5' },
  { key: 'report', icon: <ExportOutlined />, label: '报告导出', path: '/audit/step/6' },
]

const testProgressColumns = [
  { title: '测试名称', dataIndex: 'name', key: 'name' },
  { title: '进度', dataIndex: 'progress', key: 'progress', render: (p: number) => <Progress percent={p} size="small" /> },
  { title: '状态', dataIndex: 'status', key: 'status', render: (s: string) => <Tag color={s === '已完成' ? 'success' : 'warning'}>{s}</Tag> },
]

const testProgressData = [
  { name: '完整性测试', progress: 100, status: '已完成' },
  { name: '准确性测试', progress: 80, status: '进行中' },
  { name: '截止性测试', progress: 40, status: '进行中' },
  { name: '分类测试', progress: 0, status: '待开始' },
]

const riskColumns = [
  { title: '风险标题', dataIndex: 'title', key: 'title' },
  { title: '等级', dataIndex: 'level', key: 'level', render: (l: string) => <Tag color={l === '高' ? 'red' : 'orange'}>{l}</Tag> },
  { title: '状态', dataIndex: 'status', key: 'status', render: (s: string) => <Tag>{s}</Tag> },
]

const riskData = [
  { title: '收入确认截止性异常', level: '高', status: '待复核' },
  { title: '关联方交易未披露', level: '中', status: '待复核' },
]

export function AuditWorkspace() {
  const location = useLocation()
  const navigate = useNavigate()
  const [project, setProject] = useState('2026年报审计')

  return (
    <div>
      <Title level={4}>审计工作台</Title>
      <Paragraph type="secondary">管理审计项目、执行测试、复核风险与导出报告</Paragraph>

      {/* 顶部操作栏 */}
      <Card style={{ marginBottom: 16 }}>
        <Row justify="space-between" align="middle">
          <Col>
            <Space>
              <Select value={project} onChange={setProject} style={{ width: 200 }}>
                <Select.Option value="2026年报审计">2026年报审计</Select.Option>
                <Select.Option value="2026内控审计">2026内控审计</Select.Option>
              </Select>
              <Tag icon={<ClockCircleOutlined />} color="processing">进行中</Tag>
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
        {/* 左侧功能列表 */}
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

        {/* 右侧数据卡片区 */}
        <Col span={18}>
          <Row gutter={[16, 16]}>
            <Col span={8}>
              <Card>
                <Statistic title="活跃项目" value={2} valueStyle={{ color: '#1890ff' }} />
              </Card>
            </Col>
            <Col span={8}>
              <Card>
                <Statistic title="待执行测试" value={2} valueStyle={{ color: '#cf1322' }} />
              </Card>
            </Col>
            <Col span={8}>
              <Card>
                <Statistic title="风险发现" value={2} valueStyle={{ color: '#faad14' }} />
              </Card>
            </Col>
          </Row>

          <Card title="项目进度" style={{ marginTop: 16 }}>
            <Steps
              size="small"
              current={3}
              items={[
                { title: '选择范围', icon: <CheckCircleOutlined /> },
                { title: '导入证据', icon: <CheckCircleOutlined /> },
                { title: '导入序时簿', icon: <CheckCircleOutlined /> },
                { title: '执行测试', icon: <ClockCircleOutlined /> },
                { title: '复核发现', icon: <ClockCircleOutlined /> },
                { title: '导出报告', icon: <ClockCircleOutlined /> },
              ]}
            />
          </Card>

          <Card title="测试统计" style={{ marginTop: 16 }}>
            <Table
              size="small"
              columns={testProgressColumns}
              dataSource={testProgressData}
              pagination={false}
              rowKey="name"
            />
          </Card>

          <Card title="风险清单" style={{ marginTop: 16 }}>
            <Table
              size="small"
              columns={riskColumns}
              dataSource={riskData}
              pagination={false}
              rowKey="title"
            />
          </Card>
        </Col>
      </Row>
    </div>
  )
}
