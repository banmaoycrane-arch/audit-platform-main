/** Tag 分类编码约定（与 backend/app/config/tag_category_constants.py 对齐） */

/** 货币资金(1001/1002)专用，勿与 1122 往来(customer) 混淆 */
export const BANK_ACCOUNT_CATEGORY_CODE = 'bank_account'

/** 旧编码，与 bank_account 等价 */
export const LEGACY_BANK_ACCOUNT_CATEGORY_CODES = new Set(['account_detail', BANK_ACCOUNT_CATEGORY_CODE])

export const CATEGORY_DISPLAY_HINT: Record<string, string> = {
  bank_account: '银行账户 · 仅货币资金 1001/1002',
  account_detail: '（旧）同 bank_account，建议迁移编码',
  customer: '客户 · 1122 应收/2203 预收 · 实体主数据（名称/角色/信用代码/关联方）',
  supplier: '供应商 · 2202 应付/1123 预付 · 实体主数据',
  counterparty_object: '往来对象 · 1221/2241 等 · 实体主数据',
  product: '产品 · 商品/存货/产品型收入',
  service: '服务 · 劳务/服务型收入',
}

export function normalizeCategoryCode(code: string): string {
  return code === 'account_detail' ? BANK_ACCOUNT_CATEGORY_CODE : code
}

export function isBankAccountCategory(code: string): boolean {
  return LEGACY_BANK_ACCOUNT_CATEGORY_CODES.has(code)
}

export function categoryDisplayLabel(code: string, name?: string): string {
  const hint = CATEGORY_DISPLAY_HINT[code]
  if (hint) return hint
  return name ? `${name} (${code})` : code
}
