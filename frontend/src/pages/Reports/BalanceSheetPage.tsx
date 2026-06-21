import { useEffect, useState } from 'react'
import { Card, Table, Typography, Alert, Row, Col, Statistic, message } from 'antd'
import { api, type BalanceSheetReport, type TrialBalanceRow } from '../../api/client'
import { PeriodSelector } from '../../components/PeriodSelector'

const { Title } = Typography

export function BalanceSheetPage() {
  const [filter, setFilter] = useState<{ organizationId: number | null; periodId: number | null }>({
    organizationId: null,
    periodId: null,
  })
  const [report, setReport] = useState<BalanceSheetReport | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!filter.organizationId || !filter.periodId) return
    setLoading(true)
    api.getBalanceSheetReport(filter.organizationId, filter.periodId)
      .then(setReport)
      .catch((err) => message.error(`加载失败：${err instanceof Error ? err.message : String(err)}`))
      .finally(() => setLoading(false))
  }, [filter])

  const columns = [
    { title: '代码', dataIndex: 'account_code', key: 'account_code', width: 100 },
    { title: '科目', dataIndex: 'account_name', key: 'account_name' },
    {
      title: '期末借',
      dataIndex: 'closing_debit',
      key: 'closing_debit',
      render: (v: number) => v.toLocaleString(),
    },
    {
      title: '期末贷',
      dataIndex: 'closing_credit',
      key: 'closing_credit',
      render: (v: number) => v.toLocaleString(),
    },
  ]

  return (
    <div>
      <Title level={3}>资产负债表</Title>
      <Card style={{ marginBottom: 16 }}>
        <PeriodSelector value={filter} onChange={setFilter} />
      </Card>

      {report && (
        <>
          {report.is_balanced ? (
            <Alert
              type="success"
              title={`资产 = 负债 + 权益（恒等式平衡）`}
              showIcon
              style={{ marginBottom: 16 }}
            />
          ) : (
            <Alert
              type="error"
              title="资产负债恒等式不平衡"
              description={
                <>
                  <div>资产 {report.assets_total.toLocaleString()} ≠ 负债 {report.liabilities_total.toLocaleString()} + 权益 {report.equity_total.toLocaleString()}</div>
                  <div style={{ marginTop: 8, color: '#cf1322' }}>
                    可能原因：本期损益尚未结转。请前往「会计期间」执行损益结转。
                  </div>
                </>
              }
              showIcon
              style={{ marginBottom: 16 }}
            />
          )}

          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col span={8}>
              <Card><Statistic title="资产合计" value={report.assets_total} prefix="¥" /></Card>
            </Col>
            <Col span={8}>
              <Card><Statistic title="负债合计" value={report.liabilities_total} prefix="¥" /></Card>
            </Col>
            <Col span={8}>
              <Card><Statistic title="所有者权益合计" value={report.equity_total} prefix="¥" /></Card>
            </Col>
          </Row>

          <Card title="资产" style={{ marginBottom: 12 }}>
            <Table<TrialBalanceRow> rowKey="account_code" dataSource={report.assets} columns={columns} pagination={false} size="small" loading={loading} />
          </Card>
          <Card title="负债" style={{ marginBottom: 12 }}>
            <Table<TrialBalanceRow> rowKey="account_code" dataSource={report.liabilities} columns={columns} pagination={false} size="small" />
          </Card>
          <Card title="所有者权益">
            <Table<TrialBalanceRow> rowKey="account_code" dataSource={report.equity} columns={columns} pagination={false} size="small" />
          </Card>
        </>
      )}
    </div>
  )
}
