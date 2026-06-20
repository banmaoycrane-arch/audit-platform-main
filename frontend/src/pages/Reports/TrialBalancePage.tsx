import { useEffect, useState } from 'react'
import { Card, Table, Typography, Alert, message } from 'antd'
import { api, type TrialBalanceReport } from '../../api/client'
import { PeriodSelector } from '../../components/PeriodSelector'

const { Title } = Typography

const CATEGORY_LABEL: Record<string, string> = {
  asset: '资产',
  liability: '负债',
  common: '共同',
  equity: '权益',
  cost: '成本',
  profit: '损益',
}

export function TrialBalancePage() {
  const [filter, setFilter] = useState<{ organizationId: number | null; periodId: number | null }>({
    organizationId: null,
    periodId: null,
  })
  const [report, setReport] = useState<TrialBalanceReport | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!filter.organizationId || !filter.periodId) return
    setLoading(true)
    api.getTrialBalanceReport(filter.organizationId, filter.periodId)
      .then(setReport)
      .catch((err) => message.error(`加载失败：${err instanceof Error ? err.message : String(err)}`))
      .finally(() => setLoading(false))
  }, [filter])

  return (
    <div>
      <Title level={3}>科目余额表</Title>
      <Card style={{ marginBottom: 16 }}>
        <PeriodSelector value={filter} onChange={setFilter} />
      </Card>

      {report && !report.is_balanced && (
        <Alert
          type="error"
          showIcon
          message="期末借贷不平衡"
          description={`借方合计 ¥${report.totals.closing_debit.toLocaleString()}，贷方合计 ¥${report.totals.closing_credit.toLocaleString()}`}
          style={{ marginBottom: 16 }}
        />
      )}

      <Card>
        <Table
          rowKey="account_code"
          dataSource={report?.rows || []}
          loading={loading}
          size="small"
          pagination={{ pageSize: 50 }}
          columns={[
            { title: '代码', dataIndex: 'account_code', key: 'account_code', width: 90 },
            { title: '科目', dataIndex: 'account_name', key: 'account_name' },
            {
              title: '类别',
              dataIndex: 'category',
              key: 'category',
              render: (v: string) => CATEGORY_LABEL[v] || v,
              width: 80,
            },
            { title: '期初借', dataIndex: 'opening_debit', key: 'opening_debit', render: (v: number) => v.toLocaleString() },
            { title: '期初贷', dataIndex: 'opening_credit', key: 'opening_credit', render: (v: number) => v.toLocaleString() },
            { title: '本期借', dataIndex: 'period_debit', key: 'period_debit', render: (v: number) => v.toLocaleString() },
            { title: '本期贷', dataIndex: 'period_credit', key: 'period_credit', render: (v: number) => v.toLocaleString() },
            { title: '期末借', dataIndex: 'closing_debit', key: 'closing_debit', render: (v: number) => v.toLocaleString() },
            { title: '期末贷', dataIndex: 'closing_credit', key: 'closing_credit', render: (v: number) => v.toLocaleString() },
          ]}
          summary={() =>
            report ? (
              <Table.Summary.Row>
                <Table.Summary.Cell index={0} colSpan={3}><strong>合计</strong></Table.Summary.Cell>
                <Table.Summary.Cell index={1}><strong>{report.totals.opening_debit.toLocaleString()}</strong></Table.Summary.Cell>
                <Table.Summary.Cell index={2}><strong>{report.totals.opening_credit.toLocaleString()}</strong></Table.Summary.Cell>
                <Table.Summary.Cell index={3}><strong>{report.totals.period_debit.toLocaleString()}</strong></Table.Summary.Cell>
                <Table.Summary.Cell index={4}><strong>{report.totals.period_credit.toLocaleString()}</strong></Table.Summary.Cell>
                <Table.Summary.Cell index={5}><strong>{report.totals.closing_debit.toLocaleString()}</strong></Table.Summary.Cell>
                <Table.Summary.Cell index={6}><strong>{report.totals.closing_credit.toLocaleString()}</strong></Table.Summary.Cell>
              </Table.Summary.Row>
            ) : null
          }
        />
      </Card>
    </div>
  )
}
