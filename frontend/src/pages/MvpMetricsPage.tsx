import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Alert,
  Button,
  Card,
  Col,
  Progress,
  Row,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import { fetchMvpKpiSummary, type MvpKpiItem, type MvpKpiSummary } from '../utils/productAnalytics'

const { Title, Paragraph, Text } = Typography

const VERDICT_COLOR: Record<string, string> = {
  通过: 'success',
  未达标: 'error',
  待数据: 'default',
}

function formatPercent(value: number | null): string {
  if (value == null) return '—'
  return `${Math.round(value * 1000) / 10}%`
}

function kpiDisplayValue(kpi: MvpKpiItem): string {
  if (kpi.value == null) return '—'
  if (kpi.key === 'agent_median_rounds') return String(kpi.value)
  return formatPercent(kpi.value)
}

function kpiProgress(kpi: MvpKpiItem): number {
  if (kpi.value == null) return 0
  if (kpi.key === 'agent_median_rounds') {
    return Math.max(0, Math.min(100, ((2 - kpi.value) / 2) * 100))
  }
  return Math.max(0, Math.min(100, (kpi.value / kpi.pass_line) * 100))
}

export function MvpMetricsPage() {
  const [loading, setLoading] = useState(false)
  const [summary, setSummary] = useState<MvpKpiSummary | null>(null)
  const [days, setDays] = useState(14)

  const load = async () => {
    setLoading(true)
    try {
      const data = await fetchMvpKpiSummary(days)
      setSummary(data)
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error)
      message.error(`加载 MVP 指标失败：${detail}`)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [days])

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        <div>
          <Title level={3} style={{ marginBottom: 4 }}>
            MVP 验证看板
          </Title>
          <Paragraph type="secondary" style={{ marginBottom: 0 }}>
            两周 Wizard of Oz 实验 · 采纳率与完成率一眼识别 · 对齐{' '}
            <Text code>ai-four-principles-risk-matrix-mvp-validation.md</Text>
          </Paragraph>
        </div>

        <Alert
          type="info"
          showIcon
          message="如何读这个页面"
          description={
            <ul style={{ margin: '8px 0 0', paddingLeft: 20 }}>
              <li>绿色「通过」= 达到 MVP 线，可继续投入</li>
              <li>红色「未达标」= 暂停扩 AI，先修主线或收窄场景</li>
              <li>灰色「待数据」= 还没产生足够埋点，请走一遍 L6 或 Agent WoO 实验</li>
            </ul>
          }
        />

        <Row gutter={16} align="middle">
          <Col>
            <Button type="primary" icon={<ReloadOutlined />} loading={loading} onClick={() => void load()}>
              刷新
            </Button>
          </Col>
          <Col>
            <Space>
              <Text type="secondary">统计窗口</Text>
              {[7, 14, 30].map((value) => (
                <Button key={value} size="small" type={days === value ? 'primary' : 'default'} onClick={() => setDays(value)}>
                  {value} 天
                </Button>
              ))}
            </Space>
          </Col>
          {summary && (
            <Col flex="auto" style={{ textAlign: 'right' }}>
              <Text type="secondary">
                共 {summary.total_events} 条事件 · 更新于 {new Date(summary.generated_at).toLocaleString()}
              </Text>
            </Col>
          )}
        </Row>

        {summary && (
          <>
            <Row gutter={[16, 16]}>
              {summary.kpis.map((kpi) => (
                <Col xs={24} sm={12} lg={8} key={kpi.key}>
                  <Card size="small">
                    <Space direction="vertical" style={{ width: '100%' }} size={8}>
                      <Row justify="space-between" align="middle">
                        <Text strong>{kpi.label}</Text>
                        <Tag color={VERDICT_COLOR[kpi.verdict] || 'default'}>{kpi.verdict}</Tag>
                      </Row>
                      <Statistic value={kpiDisplayValue(kpi)} />
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        通过线 {kpi.threshold} · 样本 {kpi.samples}
                      </Text>
                      <Progress
                        percent={Math.round(kpiProgress(kpi))}
                        showInfo={false}
                        status={kpi.verdict === '未达标' ? 'exception' : kpi.verdict === '通过' ? 'success' : 'normal'}
                      />
                    </Space>
                  </Card>
                </Col>
              ))}
            </Row>

            <Card title="事件计数" size="small">
              <Row gutter={[8, 8]}>
                {Object.entries(summary.event_counts).map(([name, count]) => (
                  <Col key={name}>
                    <Tag>
                      {name}: {count}
                    </Tag>
                  </Col>
                ))}
                {Object.keys(summary.event_counts).length === 0 && (
                  <Text type="secondary">暂无埋点数据。请完成：导入→Step4 复核→Agent 对话→点击推荐路径。</Text>
                )}
              </Row>
            </Card>

            <Card title="最近 30 条原始事件" size="small">
              <Table
                size="small"
                pagination={{ pageSize: 10 }}
                rowKey="id"
                dataSource={summary.recent_events}
                columns={[
                  { title: '时间', dataIndex: 'created_at', width: 170, render: (v: string) => (v ? new Date(v).toLocaleString() : '—') },
                  { title: '事件', dataIndex: 'event_name', width: 220 },
                  { title: 'job', dataIndex: 'job_id', width: 70, render: (v) => v ?? '—' },
                  {
                    title: '摘要',
                    dataIndex: 'properties',
                    render: (props: Record<string, unknown> | null) => (
                      <Text style={{ fontSize: 12 }} ellipsis>
                        {props ? JSON.stringify(props) : '—'}
                      </Text>
                    ),
                  },
                ]}
              />
            </Card>
          </>
        )}

        <Card size="small" title="实验快捷入口">
          <Space wrap>
            <Link to="/ledger/vouchers/step/1">L6 记账 Step1</Link>
            <Link to="/agent">Agent 助手（WoO）</Link>
            <Link to="/parser-engine/config">解析引擎配置</Link>
          </Space>
        </Card>
      </Space>
    </div>
  )
}
