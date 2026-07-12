export type SubsidiaryLedgerColumnKey =
  | 'voucher_date'
  | 'voucher_no'
  | 'summary'
  | 'account_code'
  | 'account_name'
  | 'dimensions'
  | 'debit_amount'
  | 'credit_amount'
  | 'running_balance'
  | 'counterparty'

export type SubsidiaryLedgerColumnWidths = Record<string, number>

export const DEFAULT_SUBSIDIARY_COLUMN_WIDTHS: SubsidiaryLedgerColumnWidths = {
  voucher_date: 110,
  voucher_no: 130,
  summary: 180,
  account_code: 100,
  account_name: 130,
  dimensions: 176,
  debit_amount: 110,
  credit_amount: 110,
  running_balance: 120,
  counterparty: 120,
}

export const DEFAULT_DIMENSION_COLUMN_WIDTH = 120

export const COLUMN_WIDTH_MIN = 60
export const COLUMN_WIDTH_MAX = 480

export const COLUMN_WIDTH_LABELS: Record<SubsidiaryLedgerColumnKey, string> = {
  voucher_date: '日期',
  voucher_no: '凭证号',
  summary: '摘要',
  account_code: '科目编码',
  account_name: '科目名称',
  dimensions: '维度标签',
  debit_amount: '借方金额',
  credit_amount: '贷方金额',
  running_balance: '余额',
  counterparty: '往来单位',
}

export function dimensionColumnKey(categoryCode: string): string {
  return `dim-${categoryCode}`
}

export function resolveColumnWidth(
  widths: SubsidiaryLedgerColumnWidths,
  key: string,
  fallback?: number,
): number {
  const value = widths[key]
  if (typeof value === 'number' && value >= COLUMN_WIDTH_MIN) {
    return Math.min(value, COLUMN_WIDTH_MAX)
  }
  if (typeof fallback === 'number') return fallback
  if (key.startsWith('dim-')) return DEFAULT_DIMENSION_COLUMN_WIDTH
  return DEFAULT_SUBSIDIARY_COLUMN_WIDTHS[key as SubsidiaryLedgerColumnKey] ?? 120
}

export function mergeColumnWidths(
  saved: SubsidiaryLedgerColumnWidths | undefined,
): SubsidiaryLedgerColumnWidths {
  return {
    ...DEFAULT_SUBSIDIARY_COLUMN_WIDTHS,
    ...(saved ?? {}),
  }
}

export function clampColumnWidth(width: number): number {
  return Math.max(COLUMN_WIDTH_MIN, Math.min(COLUMN_WIDTH_MAX, Math.round(width)))
}

export function sumColumnWidths(widths: SubsidiaryLedgerColumnWidths, keys: string[]): number {
  return keys.reduce((sum, key) => sum + resolveColumnWidth(widths, key), 0)
}
