/** 结构化财务文件类型：凭证管理 vs 审计模块共用定义 */

export type StructuredKind =
  | 'day_book'
  | 'standard_entries'
  | 'trial_balance'
  | 'subsidiary_ledger'
  | 'financial_reports'

export type StructuredImportContext = 'accounting' | 'audit'

export type StructuredKindOption = {
  value: StructuredKind
  label: string
  hint: string
  /** 仅审计系统对应模块可用（财务总账凭证管理中置灰） */
  auditOnly: boolean
  auditModuleHint?: string
}

export const STRUCTURED_KIND_OPTIONS: StructuredKindOption[] = [
  {
    value: 'day_book',
    label: '序时簿 / 日记账',
    hint: '按凭证号、日期排列的分录流水',
    auditOnly: false,
  },
  {
    value: 'standard_entries',
    label: '标准格式分录文件',
    hint: '凭证号、科目、借贷金额等标准列',
    auditOnly: false,
  },
  {
    value: 'trial_balance',
    label: '科目余额表',
    hint: '期初、本期发生、期末余额',
    auditOnly: true,
    auditModuleHint: '请在审计系统 · 审计资料导入（余额表）中使用',
  },
  {
    value: 'subsidiary_ledger',
    label: '明细账',
    hint: '按科目展开的分录明细',
    auditOnly: true,
    auditModuleHint: '请在审计系统 · 审计资料导入（明细账）中使用',
  },
  {
    value: 'financial_reports',
    label: '标准财务报表',
    hint: '资产负债表、利润表等导出表',
    auditOnly: true,
    auditModuleHint: '请在审计系统 · 审计资料导入（财务报表）中使用',
  },
]

export const ACCOUNTING_ALLOWED_STRUCTURED_KINDS: StructuredKind[] = ['day_book', 'standard_entries']

const ALL_KIND_VALUES = new Set(STRUCTURED_KIND_OPTIONS.map((item) => item.value))

export function isStructuredKind(value: string | null | undefined): value is StructuredKind {
  return Boolean(value && ALL_KIND_VALUES.has(value as StructuredKind))
}

export function isStructuredKindAllowed(
  kind: string | null | undefined,
  context: StructuredImportContext,
): kind is StructuredKind {
  if (!isStructuredKind(kind)) return false
  if (context === 'audit') return true
  return ACCOUNTING_ALLOWED_STRUCTURED_KINDS.includes(kind)
}

export function resolveStructuredKind(
  kind: string | null | undefined,
  context: StructuredImportContext,
  fallback: StructuredKind = 'day_book',
): StructuredKind {
  if (isStructuredKindAllowed(kind, context)) return kind
  return fallback
}

export function structuredKindOptionsFor(context: StructuredImportContext): StructuredKindOption[] {
  if (context === 'audit') return STRUCTURED_KIND_OPTIONS
  return STRUCTURED_KIND_OPTIONS
}
