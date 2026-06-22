import { useEffect, useState } from 'react'
import { Card, Typography, Row, Col, Statistic, Descriptions, message } from 'antd'
import { api, type IncomeStatementReport } from '../../api/client'
import { PeriodSelector } from '../../components/PeriodSelector'
import { useAuthStore } from '../../stores/authStore'

const { Title } = Typography

const REVENUE_LABEL: Record<string, string> = {
  main_business_revenue: '主营业务收入',
  other_business_revenue: '其他业务收入',
  investment_income: '投资收益',
  non_operating_income: '营业外收入',
}
const EXPENSE_LABEL: Record<string, string> = {
  main_business_cost: '主营业务成本',
  other_business_cost: '其他业务成本',
  selling_expenses: '销售费用',
  admin_expenses: '管理费用',
  financial_expenses: '财务费用',
  asset_impairment_loss: '资产减值损失',
  non_operating_expense: '营业外支出',
  income_tax_expense: '所得税费用',
}

export function IncomeStatementPage() {
  const { currentLedgerId } = useAuthStore()
  const [filter, setFilter] = useState<{ organizationId: number | null; periodId: number | null }>({
    organizationId: null,
    periodId: null,
  })
  const [report, setReport] = useState<IncomeStatementReport | null>(null)

  useEffect(() => {
    if (!filter.organizationId || !filter.periodId) return
    api.getIncomeStatementReport(filter.organizationId, filter.periodId)
      .then(setReport)
      .catch((err) => message.error(`加载失败：${err instanceof Error ? err.message : String(err)}`))
  }, [filter])

  return (
    <div>
      <Title level={3}>利润表</Title>
      <Card style={{ marginBottom: 16 }}>
        <PeriodSelector ledgerId={currentLedgerId} value={filter} onChange={setFilter} />
      </Card>

      {report && (
        <>
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col span={6}>
              <Card><Statistic title="营业利润" value={report.operating_profit} prefix="¥" /></Card>
            </Col>
            <Col span={6}>
              <Card><Statistic title="利润总额" value={report.total_profit} prefix="¥" /></Card>
            </Col>
            <Col span={6}>
              <Card><Statistic title="所得税费用" value={report.income_tax} prefix="¥" /></Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic
                  title="净利润"
                  value={report.net_profit}
                  prefix="¥"
                  valueStyle={{ color: report.net_profit >= 0 ? '#3f8600' : '#cf1322' }}
                />
              </Card>
            </Col>
          </Row>

          <Card title="收入项目" style={{ marginBottom: 12 }}>
            <Descriptions column={2} bordered size="small">
              {Object.entries(report.revenue).map(([k, v]) => (
                <Descriptions.Item key={k} label={REVENUE_LABEL[k] || k}>
                  ¥{Number(v).toLocaleString()}
                </Descriptions.Item>
              ))}
            </Descriptions>
          </Card>

          <Card title="成本费用项目">
            <Descriptions column={2} bordered size="small">
              {Object.entries(report.expense).map(([k, v]) => (
                <Descriptions.Item key={k} label={EXPENSE_LABEL[k] || k}>
                  ¥{Number(v).toLocaleString()}
                </Descriptions.Item>
              ))}
            </Descriptions>
          </Card>
        </>
      )}
    </div>
  )
}
