import Decimal from 'decimal.js'
import type { SubsidiaryLedgerDisplayRow } from './subsidiaryLedgerSubtotals'
import { parseDecimal } from '../money'

export type SubsidiaryOpeningRow = {
  rowType: 'opening'
  rowKey: 'opening'
  openingLabel: string
  running_balance: number
}

export type SubsidiaryLedgerRow = SubsidiaryLedgerDisplayRow | SubsidiaryOpeningRow

export function isOpeningRow(row: SubsidiaryLedgerRow): row is SubsidiaryOpeningRow {
  return row.rowType === 'opening'
}

export function attachRunningBalances(
  rows: SubsidiaryLedgerDisplayRow[],
  openingBalance: number,
  direction: 'debit' | 'credit',
): SubsidiaryLedgerRow[] {
  // 余额用 Decimal 维护，避免逐笔借贷相减导致的浮点漂移
  let running = parseDecimal(openingBalance)
  const withBalance = rows.map((row) => {
    if (row.rowType !== 'entry') {
      return row
    }
    const debit = parseDecimal(row.debit_amount || 0)
    const credit = parseDecimal(row.credit_amount || 0)
    if (direction === 'credit') {
      running = running.plus(credit).minus(debit)
    } else {
      running = running.plus(debit).minus(credit)
    }
    return {
      ...row,
      running_balance: running.toNumber(),
    }
  })
  return [
    {
      rowType: 'opening',
      rowKey: 'opening',
      openingLabel: '期初余额',
      running_balance: openingBalance,
    },
    ...withBalance,
  ]
}
