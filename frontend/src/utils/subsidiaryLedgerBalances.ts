import type { SubsidiaryLedgerDisplayRow } from './subsidiaryLedgerSubtotals'

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
  let running = openingBalance
  const withBalance = rows.map((row) => {
    if (row.rowType !== 'entry') {
      return row
    }
    const debit = Number(row.debit_amount || 0)
    const credit = Number(row.credit_amount || 0)
    if (direction === 'credit') {
      running += credit - debit
    } else {
      running += debit - credit
    }
    return {
      ...row,
      running_balance: running,
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
