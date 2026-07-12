import { Card, Collapse, Space, Table, Tag, Typography } from 'antd'
import type { ReclassificationSummary } from '../../api/client'
import { formatAmount } from '../../money'

const { Text, Paragraph } = Typography

const RISK_LEVEL_META: Record<string, { color: string; label: string }> = {
  high: { color: 'red', label: '高' },
  medium: { color: 'orange', label: '中' },
  low: { color: 'gold', label: '低' },
}

type ReclassificationWorkbenchPanelProps = {
  summary: ReclassificationSummary
}

export function ReclassificationWorkbenchPanel({ summary }: ReclassificationWorkbenchPanelProps) {
  if (!summary.applied || summary.adjustment_count === 0) {
    return null
  }

  return (
    <Card
      size="small"
      title={`往来重分类列报调整（${summary.adjustment_count} 项）`}
      style={{ marginBottom: 12 }}
    >
      <Paragraph type="secondary" style={{ marginBottom: 12 }}>
        <Text strong>准则要求：</Text>
        {summary.standard_note}
      </Paragraph>

      <Table
        size="small"
        pagination={false}
        rowKey={(row) => `${row.from_account_code}-${row.to_account_code}`}
        dataSource={summary.items}
        columns={[
          {
            title: '原列报科目',
            key: 'from',
            render: (_: unknown, row) => (
              <div>
                <Text code>{row.from_account_code}</Text>
                <div><Text type="secondary">{row.from_account_name || '-'}</Text></div>
              </div>
            ),
          },
          {
            title: '重分类至',
            key: 'to',
            render: (_: unknown, row) => (
              <div>
                <Text code>{row.to_account_code}</Text>
                <div><Text type="secondary">{row.to_account_name || '-'}</Text></div>
              </div>
            ),
          },
          {
            title: '调整金额',
            dataIndex: 'amount',
            key: 'amount',
            align: 'right',
            render: (value: string | number) => formatAmount(Number(value)),
          },
          {
            title: '准则依据',
            key: 'standard',
            width: '34%',
            render: (_: unknown, row) => (
              <Space direction="vertical" size={2}>
                <Text style={{ fontSize: 12 }}>{row.standard_basis || row.reason || '-'}</Text>
                {row.standard_reference && (
                  <Text type="secondary" style={{ fontSize: 11 }}>{row.standard_reference}</Text>
                )}
              </Space>
            ),
          },
        ]}
      />

      {summary.assertion_risk_summary.length > 0 && (
        <Collapse
          style={{ marginTop: 12 }}
          items={[
            {
              key: 'assertion-risks',
              label: `认定层面审计风险提示（${summary.assertion_risk_summary.length} 项）`,
              children: (
                <Space direction="vertical" size={12} style={{ width: '100%' }}>
                  {summary.assertion_risk_summary.map((risk) => {
                    const meta = RISK_LEVEL_META[risk.risk_level] || RISK_LEVEL_META.medium
                    return (
                      <div
                        key={`${risk.assertion}-${risk.risk_level}`}
                        style={{
                          border: '1px solid #f0f0f0',
                          borderRadius: 8,
                          padding: 12,
                          background: '#fafafa',
                        }}
                      >
                        <Space wrap>
                          <Tag color="blue">{risk.assertion}</Tag>
                          <Tag color={meta.color}>风险{meta.label}</Tag>
                          {risk.related_accounts.map((code) => (
                            <Tag key={code}>{code}</Tag>
                          ))}
                        </Space>
                        <Paragraph style={{ margin: '8px 0 0', fontSize: 12 }}>
                          {risk.risk_description}
                        </Paragraph>
                      </div>
                    )
                  })}
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    提示：重分类仅调整列报呈现，不替代明细账核对、函证、期后回款/付款等进一步审计程序。
                  </Text>
                </Space>
              ),
            },
          ]}
        />
      )}
    </Card>
  )
}
