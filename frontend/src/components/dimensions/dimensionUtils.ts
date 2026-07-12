import type { TagCategoryNode } from '../../api/client'

import {

  BANK_ACCOUNT_CATEGORY_CODE,

  isBankAccountCategory,

  normalizeCategoryCode,

} from './tagCategoryConstants'



export {

  BANK_ACCOUNT_CATEGORY_CODE,

  CATEGORY_DISPLAY_HINT,

  categoryDisplayLabel,

  isBankAccountCategory,

  normalizeCategoryCode,

} from './tagCategoryConstants'



export function flattenTagCategories(nodes: TagCategoryNode[]): TagCategoryNode[] {

  const rows: TagCategoryNode[] = []

  for (const node of nodes) {

    rows.push(node)

    if (node.children?.length) {

      rows.push(...flattenTagCategories(node.children))

    }

  }

  return rows

}



const COUNTERPARTY_ROLE_BY_CODE: Record<string, string | undefined> = {

  customer: 'customer',

  supplier: 'supplier',

}



export type DimensionValueSource = 'bank_accounts' | 'counterparties' | 'aggregate'



/**

 * 系统内置「共享 Tag」分类：替代原 ERP 辅助核算项，值存 EntryTag，

 * 各子模块（费用分析、资产、项目成本等）共用同一套语义，避免按模块各建一张表。

 */

export const SHARED_TAG_CATEGORY_CODES = new Set([

  'fixed_asset_class',

  'fixed_asset_item',

  'cip_category',

  'cip_project',

  'loan_channel',

  'expense_type',

  'department',

  'project',

  'region',

  'product',

  'service',

  'cost_element',

  'tax_type',

])



/** @deprecated 使用 SHARED_TAG_CATEGORY_CODES */

export const VECTOR_ANALYSIS_CATEGORY_CODES = SHARED_TAG_CATEGORY_CODES



const COUNTERPARTY_CATEGORY_CODES = new Set(['customer', 'supplier', 'counterparty_object'])



/**

 * 维度值在主数据页的收集/维护粒度（与 tag-vs-account-hierarchy.md §7.1 对齐）

 *

 * - bank_account / counterparty：实体档案，走独立主数据表

 * - shared_tag：共享语义 Tag，存 EntryTag；可补规范名、可叠加自定义 Tag，不要求独立档案表

 */

export type MasterDataCollectionKind = 'bank_account' | 'counterparty' | 'shared_tag'



export function isMonetaryFundAccount(accountCode?: string | null): boolean {

  const root = (accountCode || '').trim().split('.')[0]

  return root === '1001' || root === '1002'

}



export function isSharedTagCategory(categoryCode: string): boolean {

  return SHARED_TAG_CATEGORY_CODES.has(categoryCode)

}



/**

 * 按维度实例（分类 + 入账科目）决定主数据页应如何展示与维护。

 */

export function resolveMasterDataCollectionKind(item: {

  category_code: string

  account_code?: string | null

}): MasterDataCollectionKind {

  const categoryCode = item.category_code

  if (COUNTERPARTY_CATEGORY_CODES.has(categoryCode)) {

    return 'counterparty'

  }

  if (isBankAccountCategory(categoryCode)) {

    return isMonetaryFundAccount(item.account_code) ? 'bank_account' : 'shared_tag'

  }

  if (SHARED_TAG_CATEGORY_CODES.has(categoryCode)) {

    return 'shared_tag'

  }

  return 'shared_tag'

}



export function masterDataCollectionLabel(kind: MasterDataCollectionKind): string {

  switch (kind) {

    case 'bank_account':

      return '银行账户档案'

    case 'counterparty':

      return '往来单位档案'

    case 'shared_tag':

      return '共享 Tag（辅助核算语义）'

    default:

      return '共享 Tag'

  }

}



/** entity 型走主数据表；shared Tag 走 EntryTag，不要求独立档案字段 */

export function isEntityMasterDataCategory(categoryCode: string, valueType?: string | null): boolean {

  if (COUNTERPARTY_CATEGORY_CODES.has(categoryCode)) return true

  if (isBankAccountCategory(categoryCode)) return true

  return valueType === 'entity'

}



export function resolveDimensionValueSource(category: TagCategoryNode): {

  source: DimensionValueSource

  counterpartyRole?: string

} {

  if (category.source_table === 'bank_accounts' || isBankAccountCategory(category.code)) {

    return { source: 'bank_accounts' }

  }

  if (category.source_table === 'counterparties' || category.code in COUNTERPARTY_ROLE_BY_CODE) {

    return {

      source: 'counterparties',

      counterpartyRole: COUNTERPARTY_ROLE_BY_CODE[category.code],

    }

  }

  if (category.code === 'counterparty_object') {

    return { source: 'counterparties' }

  }

  if (category.value_type === 'entity') {

    return { source: 'counterparties' }

  }

  return { source: 'aggregate' }

}



/** 共享 Tag 是否已在分录侧规范命名（或已沉淀到聚合列表） */

export function isSharedTagValueReady(

  row: { display_name?: string | null; tag_value?: string | null; name_standardized?: boolean },

  knownValues: Set<string>,

): boolean {

  if (row.name_standardized) return true

  const label = (row.display_name || row.tag_value || '').trim()

  return Boolean(label && knownValues.has(label))

}


