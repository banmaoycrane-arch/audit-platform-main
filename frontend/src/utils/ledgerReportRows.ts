import Decimal from 'decimal.js'
import type { TrialBalanceRow } from '../api/client'
import { l1AccountKey } from './balanceSheetTreemap'
import { parseDecimal } from '../money'

export function rowHasBalance(row: TrialBalanceRow): boolean {
  // 金额是否为零的判断使用 Decimal，避免浮点比较误差
  return (
    !parseDecimal(row.opening_debit || 0).isZero() ||
    !parseDecimal(row.opening_credit || 0).isZero() ||
    !parseDecimal(row.period_debit || 0).isZero() ||
    !parseDecimal(row.period_credit || 0).isZero() ||
    !parseDecimal(row.ytd_debit || 0).isZero() ||
    !parseDecimal(row.ytd_credit || 0).isZero() ||
    !parseDecimal(row.closing_debit || 0).isZero() ||
    !parseDecimal(row.closing_credit || 0).isZero()
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
      // 金额字段汇总使用 Decimal 累加，避免总账汇总金额与明细账产生尾差
      const sum = (field: keyof TrialBalanceRow) =>
        bucket.reduce<Decimal>(
          (total, row) => total.plus(parseDecimal(row[field] || 0)),
          new Decimal(0),
        ).toNumber()
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
        ytd_debit: sum('ytd_debit'),
        ytd_credit: sum('ytd_credit'),
        closing_debit: sum('closing_debit'),
        closing_credit: sum('closing_credit'),
        isGroup: bucket.length > 1 || key !== bucket[0]?.account_code,
        children: bucket.sort((a, b) => a.account_code.localeCompare(b.account_code, 'zh-CN')),
      }
    })
}
