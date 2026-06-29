import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, Col, Row, Statistic, Typography } from 'antd'
import { FileTextOutlined, CalendarOutlined, AlertOutlined, AuditOutlined } from '@ant-design/icons'
import { api } from '../api/client'

const { Title, Paragraph } = Typography

type Summary = {
  voucher_count: number
  unposted_periods: number
  pending_risks: number
  recent_findings: number
}

const EMPTY_SUMMARY: Summary = {
  voucher_count: 0,
  unposted_periods: 0,
  pending_risks: 0,
  recent_findings: 0
}

export function HomePage() {
  const navigate = useNavigate()
  const [summary, setSummary] = useState<Summary>(EMPTY_SUMMARY)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    api
      .getDashboardSummary()
      .then((data) => {
        if (!cancelled) setSummary(data)
      })
      .catch((err) => {
        // 接口失败不阻塞首页：保持 0 即可
        console.warn('获取 Dashboard 概览失败', err)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div style={{ padding: '48px', maxWidth: '1100px', margin: '0 auto' }}>
      <Title level={2} style={{ textAlign: 'center', marginBottom: '32px' }}>
        财务向量审计系统
      </Title>

      <Row gutter={16} style={{ marginBottom: '32px' }}>
        <Col xs={12} md={6}>
          <Card loading={loading}>
            <Statistic
              title="凭证数"
              value={summary.voucher_count}
              prefix={<FileTextOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card loading={loading}>
            <Statistic
              title="未结转期间"
              value={summary.unposted_periods}
              prefix={<CalendarOutlined />}
              valueStyle={{ color: summary.unposted_periods > 0 ? '#cf1322' : undefined }}
            />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card loading={loading}>
            <Statistic
              title="待复核风险"
              value={summary.pending_risks}
              prefix={<AlertOutlined />}
              valueStyle={{ color: summary.pending_risks > 0 ? '#fa8c16' : undefined }}
            />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card loading={loading}>
            <Statistic
              title="最近审计发现"
              value={summary.recent_findings}
              prefix={<AuditOutlined />}
            />
          </Card>
        </Col>
      </Row>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
        <Card
          hoverable
          style={{
            textAlign: 'center',
            padding: '32px',
            borderRadius: '16px',
            cursor: 'pointer'
          }}
          onClick={() => navigate('/accounting/step/1')}
        >
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>📒</div>
          <Title level={4}>记账模式</Title>
          <Paragraph type="secondary">
            从原始资料（发票、银行流水、合同等）自动生成会计分录，
            支持凭证复核与调整，最终导出标准账簿。
          </Paragraph>
        </Card>

        <Card
          hoverable
          style={{
            textAlign: 'center',
            padding: '32px',
            borderRadius: '16px',
            cursor: 'pointer'
          }}
          onClick={() => navigate('/audit/step/1')}
        >
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>🔍</div>
          <Title level={4}>审计模式</Title>
          <Paragraph type="secondary">
            导入被审计单位分录，执行完整性、准确性、截止性、
            分类等审计测试，自动生成审计发现报告。
          </Paragraph>
        </Card>
      </div>
    </div>
  )
}
