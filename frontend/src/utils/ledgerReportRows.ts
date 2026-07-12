import type { TrialBalanceRow } from '../api/client'
import { l1AccountKey } from './balanceSheetTreemap'

export function rowHasBalance(row: TrialBalanceRow): boolean {
  return (
    Number(row.opening_debit || 0) !== 0 ||
    Number(row.opening_credit || 0) !== 0 ||
    Number(row.period_debit || 0) !== 0 ||
    Number(row.period_credit || 0) !== 0 ||
    Number(row.ytd_debit || 0) !== 0 ||
    Number(row.ytd_credit || 0) !== 0 ||
    Number(row.closing_debit || 0) !== 0 ||
    Number(row.closing_credit || 0) !== 0
  )
}

export type GeneralLedgerGroupRow = TrialBalanceRow & {
  isGroup: boolean
  children?: TrialBalanceRow[]
}

export function buildGeneralLedgerGroups(rows: TrialBalanceRow[]): GeneralLedgerGroupRow[] {
  const groups = new Map<string, TrialBalanceRow[]>()
  for (const row of rows) {
    const key = l1AccountKey(row.account_code)
    const bucket = groups.get(key) || []
    bucket.push(row)
    groups.set(key, bucket)
  }

  return Array.from(groups.entries())
    .sort(([a], [b]) => a.localeCompare(b, 'zh-CN'))
    .map(([key, bucket]) => {
      const sum = (field: keyof TrialBalanceRow) =>
        bucket.reduce((total, row) => total + Number(row[field] || 0), 0)
      const head = bucket.find((row) => row.account_code === key) || bucket[0]
      return {
        account_code: key,
        account_name: head.account_name,
        category: head.category,
        direction: head.direction,
        opening_debit: sum('opening_debit'),
        opening_credit: sum('opening_credit'),
        period_debit: sum('period_debit'),
        period_credit: sum('period_credit'),
        closing_debit: sum('closing_debit'),
        closing_credit: sum('closing_credit'),
        isGroup: bucket.length > 1 || key !== bucket[0]?.account_code,
        children: bucket.sort((a, b) => a.account_code.localeCompare(b.account_code, 'zh-CN')),
      }
    })
}
