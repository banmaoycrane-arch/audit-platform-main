import { useEffect, useState } from 'react'
import { Select, Space, Typography } from 'antd'
import { api, type AccountingPeriod } from '../api/client'

const { Text } = Typography

type Props = {
  value: { organizationId: number | null; periodId: number | null }
  onChange: (v: { organizationId: number | null; periodId: number | null }) => void
}

export function PeriodSelector({ value, onChange }: Props) {
  const [periods, setPeriods] = useState<AccountingPeriod[]>([])

  useEffect(() => {
    api.listAccountingPeriods()
      .then((data) => {
        setPeriods(data)
        if (!value.periodId && data.length > 0) {
          onChange({ organizationId: data[0].organization_id, periodId: data[0].id })
        }
      })
      .catch(() => setPeriods([]))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <Space>
      <Text>会计期间：</Text>
      <Select
        value={value.periodId ?? undefined}
        style={{ width: 280 }}
        placeholder="请选择期间"
        onChange={(v) => {
          const p = periods.find((x) => x.id === v)
          onChange({ organizationId: p?.organization_id ?? null, periodId: v })
        }}
        options={periods.map((p) => ({
          value: p.id,
          label: `${p.period_code}（${p.start_date} ~ ${p.end_date}）`,
        }))}
      />
    </Space>
  )
}
