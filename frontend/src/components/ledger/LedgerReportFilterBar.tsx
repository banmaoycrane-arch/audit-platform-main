import { useEffect, useMemo, useState } from 'react'
import { Button, Card, DatePicker, Select, Space, Tag, Typography } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import dayjs, { type Dayjs } from 'dayjs'
import { api, type AccountingPeriod } from '../../api/client'

const { Text } = Typography

const PERIOD_STATUS_LABEL: Record<string, { color: string; text: string }> = {
  open: { color: 'green', text: '进行中' },
  pl_transferred: { color: 'blue', text: '已结转损益' },
  closed: { color: 'default', text: '已结账' },
  reopened: { color: 'purple', text: '已反结账' },
}

export type LedgerReportDraft = {
  periodId: number | null
  asOfDate: string | null
}

export type LedgerReportApplied = {
  periodId: number
  asOfDate: string
  period: AccountingPeriod
}

type Props = {
  ledgerId?: number | null
  title?: string
  applied: LedgerReportApplied | null
  onApply: (query: LedgerReportApplied) => void
  autoSearch?: boolean
  /** URL 或上游传入的默认期间 */
  initialPeriodId?: number | null
}

export function LedgerReportFilterBar({
  ledgerId,
  title = '筛选条件（点击查询生效）',
  applied,
  onApply,
  autoSearch = true,
  initialPeriodId,
}: Props) {
  const [periods, setPeriods] = useState<AccountingPeriod[]>([])
  const [draftPeriodId, setDraftPeriodId] = useState<number | null>(null)
  const [draftAsOfDate, setDraftAsOfDate] = useState<Dayjs | null>(dayjs())

  useEffect(() => {
    if (!ledgerId) {
      setPeriods([])
      setDraftPeriodId(null)
      return
    }
    void api
      .listAccountingPeriods(undefined, ledgerId)
      .then((data) => {
        setPeriods(data)
        if (!data.length) {
          setDraftPeriodId(null)
          return
        }
        const preferred =
          applied?.periodId != null
            ? data.find((item) => item.id === applied.periodId)
            : initialPeriodId
              ? data.find((item) => item.id === initialPeriodId)
              : data.find((item) => item.status === 'open') || data[data.length - 1]
        if (preferred) {
          setDraftPeriodId(preferred.id)
          if (preferred.status === 'closed') {
            setDraftAsOfDate(dayjs(preferred.end_date))
          } else if (!applied?.asOfDate) {
            setDraftAsOfDate(dayjs())
          }
        }
      })
      .catch(() => setPeriods([]))
  }, [ledgerId, applied?.periodId, applied?.asOfDate, initialPeriodId])

  const draftPeriod = useMemo(
    () => periods.find((item) => item.id === draftPeriodId) ?? null,
    [periods, draftPeriodId],
  )

  const isClosedPeriod = draftPeriod?.status === 'closed'

  const applySearch = () => {
    if (!draftPeriod) return
    const asOf = isClosedPeriod
      ? draftPeriod.end_date
      : (draftAsOfDate || dayjs()).format('YYYY-MM-DD')
    onApply({
      periodId: draftPeriod.id,
      asOfDate: asOf,
      period: draftPeriod,
    })
  }

  useEffect(() => {
    if (!autoSearch || !ledgerId || !draftPeriod || applied) return
    applySearch()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoSearch, ledgerId, draftPeriod?.id])

  return (
    <Card title={title} size="small" style={{ marginBottom: 16 }}>
      <Space wrap align="center">
        <Text>会计期间</Text>
        <Select
          value={draftPeriodId ?? undefined}
          placeholder="请选择期间"
          style={{ width: 280 }}
          onChange={setDraftPeriodId}
          options={periods.map((period) => ({
            value: period.id,
            label: `${period.period_code}（${period.start_date} ~ ${period.end_date}）`,
          }))}
        />
        {draftPeriod && (
          <Tag color={PERIOD_STATUS_LABEL[draftPeriod.status]?.color || 'default'}>
            {PERIOD_STATUS_LABEL[draftPeriod.status]?.text || draftPeriod.status}
          </Tag>
        )}
        <Text>截止日</Text>
        <DatePicker
          value={draftAsOfDate}
          disabled={isClosedPeriod}
          onChange={(value) => setDraftAsOfDate(value)}
          allowClear={false}
        />
        <Button type="primary" icon={<SearchOutlined />} onClick={applySearch} disabled={!draftPeriod}>
          查询
        </Button>
        {applied && (
          <Tag color={applied.period.status === 'closed' ? 'default' : 'processing'}>
            {applied.period.status === 'closed' ? '结账快照' : '即时余额'} · 截止 {applied.asOfDate}
          </Tag>
        )}
      </Space>
    </Card>
  )
}
