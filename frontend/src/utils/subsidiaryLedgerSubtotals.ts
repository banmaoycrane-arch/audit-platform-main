import dayjs from 'dayjs'

import type { AccountingEntry } from '../api/client'
import type { SubsidiaryLedgerSubtotalMode } from './subsidiaryLedgerPrefs'

export type SubsidiaryLedgerSubtotalRow = {
  rowType: 'subtotal'
  rowKey: string
  periodLabel: string
  debit_amount: number
  credit_amount: number
  entry_count: number
}

export type SubsidiaryLedgerEntryRow = AccountingEntry & {
  rowType: 'entry'
  rowKey: string
  running_balance?: number
}

export type SubsidiaryLedgerDisplayRow = SubsidiaryLedgerEntryRow | SubsidiaryLedgerSubtotalRow

function mondayWeekStart(dateStr: string): dayjs.Dayjs {
  const d = dayjs(dateStr)
  const weekday = d.day()
  const offset = weekday === 0 ? -6 : 1 - weekday
  return d.add(offset, 'day')
}

export function periodKeyForEntry(
  dateStr: string | null | undefined,
  mode: SubsidiaryLedgerSubtotalMode,
  customDays: number,
  anchorDate?: string | null,
): string {
  if (!dateStr || mode === 'none') return ''
  const d = dayjs(dateStr)
  if (mode === 'day') return d.format('YYYY-MM-DD')
  if (mode === 'week') return mondayWeekStart(dateStr).format('YYYY-MM-DD')
  if (mode === 'month') return d.format('YYYY-MM')
  const anchor = anchorDate ? dayjs(anchorDate) : d
  const daysSince = d.diff(anchor, 'day')
  const bucket = Math.floor(daysSince / customDays)
  const start = anchor.add(bucket * customDays, 'day')
  return start.format('YYYY-MM-DD')
}

export function formatPeriodLabel(
  key: string,
  mode: SubsidiaryLedgerSubtotalMode,
  customDays: number,
): string {
  if (!key) return '未分类'
  if (mode === 'day') return `${key} 小计`
  if (mode === 'month') return `${key} 月小计`
  if (mode === 'week') {
    const start = dayjs(key)
    const end = start.add(6, 'day')
    return `${start.format('YYYY-MM-DD')} ~ ${end.format('YYYY-MM-DD')} 周小计`
  }
  if (mode === 'custom_days') {
    const start = dayjs(key)
    const end = start.add(customDays - 1, 'day')
    return `${start.format('YYYY-MM-DD')} ~ ${end.format('YYYY-MM-DD')} 小计`
  }
  return `${key} 小计`
}

export function injectSubsidiarySubtotals(
  entries: AccountingEntry[],
  mode: SubsidiaryLedgerSubtotalMode,
  customDays = 7,
): SubsidiaryLedgerDisplayRow[] {
  if (mode === 'none') {
    return entries.map((entry) => ({
      ...entry,
      rowType: 'entry' as const,
      rowKey: `entry-${entry.id}`,
    }))
  }

  const anchorDate = entries.find((entry) => entry.voucher_date)?.voucher_date ?? null
  const rows: SubsidiaryLedgerDisplayRow[] = []
  let currentKey = ''
  let sumDebit = 0
  let sumCredit = 0
  let count = 0

  const pushSubtotal = (key: string) => {
    if (!key || count === 0) return
    rows.push({
      rowType: 'subtotal',
      rowKey: `subtotal-${key}`,
      periodLabel: formatPeriodLabel(key, mode, customDays),
      debit_amount: sumDebit,
      credit_amount: sumCredit,
      entry_count: count,
    })
  }

  for (const entry of entries) {
    const key = periodKeyForEntry(entry.voucher_date, mode, customDays, anchorDate)
    if (currentKey && key !== currentKey) {
      pushSubtotal(currentKey)
      sumDebit = 0
      sumCredit = 0
      count = 0
    }
    currentKey = key
    sumDebit += Number(entry.debit_amount || 0)
    sumCredit += Number(entry.credit_amount || 0)
    count += 1
    rows.push({
      ...entry,
      rowType: 'entry',
      rowKey: `entry-${entry.id}`,
    })
  }
  pushSubtotal(currentKey)
  return rows
}
