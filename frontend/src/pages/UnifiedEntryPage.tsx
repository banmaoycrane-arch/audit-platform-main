import { Card, Row, Col, Typography, Button, Space, Tag, Statistic } from 'antd'
import { useNavigate } from 'react-router-dom'
import { FileTextOutlined, AuditOutlined, ArrowRightOutlined, DatabaseOutlined, BarChartOutlined, LockOutlined, RocketOutlined } from '@ant-design/icons'
import { api } from '../api/client'
import { useState, useEffect } from 'react'

const { Title, Paragraph, Text } = Typography

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

const MODE_OPTIONS = [
  {
    mode: 'accounting',
    title: '记账模式',
    subtitle: '会计核算与凭证生成',
    icon: '📒',
    description: '从原始资料自动生成会计分录，支持凭证复核与调整，最终导出标准账簿。适用于企业日常记账、财务外包、代理记账等场景。',
    features: ['发票/银行流水/合同智能识别', '自动生成会计分录', '凭证复核与调整', '标准账簿导出'],
    actionLabel: '开始记账',
    route: '/ledger/vouchers/step/1',
    color: 'blue',
    stats: [
      { label: '待复核凭证', icon: FileTextOutlined, key: 'voucher_count' },
    ]
  },
  {
    mode: 'audit',
    title: '审计模式',
    subtitle: '审计风险识别与测试',
    icon: '🔍',
    description: '导入被审计单位分录，执行完整性、准确性、截止性、分类等审计测试，自动生成审计发现报告。适用于会计师事务所审计、企业内部审计等场景。',
    features: ['序时簿导入与检测', '多维度审计测试', '风险识别与标记', '审计发现报告'],
    actionLabel: '开始审计',
    route: '/audit/step/1',
    color: 'purple',
    stats: [
      { label: '待复核风险', icon: LockOutlined, key: 'pending_risks' },
      { label: '最近发现', icon: AuditOutlined, key: 'recent_findings' },
    ]
  }
]

export function UnifiedEntryPage() {
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
        console.warn('获取 Dashboard 概览失败', err)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const handleModeSelect = (route: string) => {
    navigate(route)
  }

  return (
    <div style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto' }}>
      <div style={{ textAlign: 'center', marginBottom: '32px' }}>
        <Title level={2} style={{ marginBottom: '8px' }}>
          财务向量审计系统
        </Title>
        <Paragraph type="secondary">
          统一入口 - 选择您要执行的业务模式
        </Paragraph>
      </div>

      <Row gutter={16} style={{ marginBottom: '32px' }}>
        <Col xs={12} sm={6}>
          <Card loading={loading} hoverable>
            <Statistic
              title="凭证数"
              value={summary.voucher_count}
              prefix={<FileTextOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card loading={loading} hoverable>
            <Statistic
              title="未结转期间"
              value={summary.unposted_periods}
              prefix={<DatabaseOutlined />}
              valueStyle={{ color: summary.unposted_periods > 0 ? '#cf1322' : undefined }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card loading={loading} hoverable>
            <Statistic
              title="待复核风险"
              value={summary.pending_risks}
              prefix={<LockOutlined />}
              valueStyle={{ color: summary.pending_risks > 0 ? '#fa8c16' : undefined }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card loading={loading} hoverable>
            <Statistic
              title="最近审计发现"
              value={summary.recent_findings}
              prefix={<AuditOutlined />}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={24}>
        {MODE_OPTIONS.map((option) => (
          <Col xs={24} lg={12} key={option.mode}>
            <Card
              hoverable
              style={{
                height: '100%',
                padding: '32px',
                borderRadius: '16px',
                borderWidth: '2px',
                borderColor: option.color === 'blue' ? '#1890ff' : '#722ed1',
                transition: 'all 0.3s ease',
              }}
              bodyStyle={{ padding: 0 }}
            >
              <div style={{ padding: '0 24px 24px' }}>
                <div style={{ display: 'flex', alignItems: 'center', marginBottom: '16px' }}>
                  <span style={{ fontSize: '48px', marginRight: '16px' }}>{option.icon}</span>
                  <div>
                    <Title level={3} style={{ marginBottom: '4px' }}>
                      {option.title}
                    </Title>
                    <Text type="secondary">{option.subtitle}</Text>
                  </div>
                </div>

                <Paragraph type="secondary" style={{ marginBottom: '20px' }}>
                  {option.description}
                </Paragraph>

                <div style={{ marginBottom: '20px' }}>
                  <Text strong style={{ display: 'block', marginBottom: '8px' }}>功能特性</Text>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                    {option.features.map((feature, index) => (
                      <Tag key={index} color={option.color === 'blue' ? 'blue' : 'purple'}>
                        {feature}
                      </Tag>
                    ))}
                  </div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Space>
                    {option.stats.map((stat) => (
                      <div key={stat.key} style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: '20px', fontWeight: 'bold', color: option.color === 'blue' ? '#1890ff' : '#722ed1' }}>
                          {summary[stat.key as keyof Summary]}
                        </div>
                        <div style={{ fontSize: '12px', color: '#666' }}>{stat.label}</div>
                      </div>
                    ))}
                  </Space>
                  <Button
                    type={option.color === 'blue' ? 'primary' : 'default'}
                    size="large"
                    onClick={() => handleModeSelect(option.route)}
                    style={{
                      borderColor: option.color === 'blue' ? undefined : '#722ed1',
                      color: option.color === 'blue' ? undefined : '#722ed1',
                    }}
                  >
                    {option.actionLabel}
                    <ArrowRightOutlined />
                  </Button>
                </div>
              </div>
            </Card>
          </Col>
        ))}
      </Row>

      <Card style={{ marginTop: '32px', borderRadius: '16px' }}>
        <Title level={5} style={{ marginBottom: '16px' }}>
          <RocketOutlined style={{ marginRight: '8px' }} />
          快速导航
        </Title>
        <Row gutter={16}>
          <Col xs={8} sm={4}>
            <Button block onClick={() => navigate('/ledger/entries')}>
              <FileTextOutlined style={{ marginRight: '8px' }} />
              凭证查询
            </Button>
          </Col>
          <Col xs={8} sm={4}>
            <Button block onClick={() => navigate('/reports/trial-balance')}>
              <BarChartOutlined style={{ marginRight: '8px' }} />
              报表中心
            </Button>
          </Col>
          <Col xs={8} sm={4}>
            <Button block onClick={() => navigate('/basic/coa')}>
              <DatabaseOutlined style={{ marginRight: '8px' }} />
              基础资料
            </Button>
          </Col>
          <Col xs={8} sm={4}>
            <Button block onClick={() => navigate('/bank/workspace')}>
              <DatabaseOutlined style={{ marginRight: '8px' }} />
              银行对账
            </Button>
          </Col>
          <Col xs={8} sm={4}>
            <Button block onClick={() => navigate('/audit/dashboard')}>
              <AuditOutlined style={{ marginRight: '8px' }} />
              审计工作台
            </Button>
          </Col>
          <Col xs={8} sm={4}>
            <Button block onClick={() => navigate('/risks')}>
              <LockOutlined style={{ marginRight: '8px' }} />
              风险中心
            </Button>
          </Col>
        </Row>
      </Card>

      <Card style={{ marginTop: '16px', borderRadius: '16px', background: '#f6ffed' }}>
        <Space direction="vertical" size={8}>
          <div style={{ display: 'flex', alignItems: 'center' }}>
            <RocketOutlined style={{ color: '#52c41a', marginRight: '8px' }} />
            <Text strong>使用提示</Text>
          </div>
          <Text type="secondary">
            记账模式适用于企业日常财务核算，从原始凭证生成会计分录；审计模式适用于审计人员对被审计单位财务数据进行风险识别和测试。
            两种模式共享统一的解析引擎，确保数据处理的一致性和准确性。
          </Text>
        </Space>
      </Card>
    </div>
  )
}
