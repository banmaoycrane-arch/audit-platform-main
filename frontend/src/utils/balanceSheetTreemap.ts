import type { TrialBalanceRow } from '../api/client'

export type TreemapLeaf = {
  id: string
  name: string
  accountCode: string
  accountName: string
  /** 用于面积（非负） */
  value: number
  /** 原始净额（可负，抵减项） */
  rawBalance: number
  isLeaf: boolean
  isOther?: boolean
  isContra?: boolean
}

export type TreemapSection = {
  id: string
  name: string
  total: number
  items: TreemapLeaf[]
}

const DEFAULT_MIN_SHARE = 0.005
const L1_PREFIX_LEN = 4
const CHILD_SEGMENT_LEN = 2

/** 科目期末净额：资产/借方 = 借-贷，负债权益/贷方 = 贷-借 */
export function rowNetBalance(row: TrialBalanceRow): number {
  const debit = Number(row.closing_debit || 0)
  const credit = Number(row.closing_credit || 0)
  const category = (row.category || '').toLowerCase()
  const direction = (row.direction || '').toLowerCase()
  if (category === 'asset' || direction === 'debit' || direction === '借') {
    return debit - credit
  }
  return credit - debit
}

export function l1AccountKey(accountCode: string): string {
  const code = accountCode.trim()
  if (code.length <= L1_PREFIX_LEN) return code
  return code.slice(0, L1_PREFIX_LEN)
}

/** 取 prefix 下的直接下级分组键（每段 2 位数字），支持逐级下钻 */
export function immediateChildKey(accountCode: string, prefix: string | null): string {
  const code = accountCode.trim()
  if (!prefix) return l1AccountKey(code)
  const root = prefix.trim()
  if (code === root) return root
  if (!code.startsWith(root)) return code
  const remainder = code.slice(root.length)
  if (!remainder) return code
  if (/^\d+$/.test(remainder)) {
    return root + remainder.slice(0, CHILD_SEGMENT_LEN)
  }
  return code
}

export function rowsUnderPrefix(rows: TrialBalanceRow[], prefix: string | null): TrialBalanceRow[] {
  if (!prefix) return rows
  return rows.filter(
    (row) => row.account_code === prefix || row.account_code.startsWith(prefix),
  )
}

function displayNameForGroup(rows: TrialBalanceRow[], key: string): string {
  const exact = rows.find((row) => row.account_code === key)
  if (exact?.account_name) return `${key} ${exact.account_name}`
  const child = rows.find((row) => row.account_code.startsWith(key))
  if (child?.account_name && child.account_code !== key) {
    return `${key} ${child.account_name.replace(/\d+/g, '').trim() || child.account_name}`
  }
  return key
}

function groupRowsAtLevel(rows: TrialBalanceRow[], prefix: string | null): Map<string, TrialBalanceRow[]> {
  const scoped = rowsUnderPrefix(rows, prefix)
  const groups = new Map<string, TrialBalanceRow[]>()

  if (!prefix) {
    for (const row of scoped) {
      const key = l1AccountKey(row.account_code)
      const bucket = groups.get(key) || []
      bucket.push(row)
      groups.set(key, bucket)
    }
    return groups
  }

  for (const row of scoped) {
    const key = immediateChildKey(row.account_code, prefix)
    const bucket = groups.get(key) || []
    bucket.push(row)
    groups.set(key, bucket)
  }
  return groups
}

export function canDrillDeeper(rows: TrialBalanceRow[], key: string): boolean {
  const scoped = rowsUnderPrefix(rows, key)
  if (scoped.length === 0) return false

  const childKeys = new Set(
    scoped.map((row) => immediateChildKey(row.account_code, key)),
  )
  if (childKeys.size > 1) return true

  const only = scoped[0]
  if (scoped.length === 1 && only && only.account_code.length > key.length) {
    return true
  }

  return scoped.some(
    (row) => row.account_code.length > immediateChildKey(row.account_code, key).length,
  )
}

function mergeSmallItems(
  items: TreemapLeaf[],
  sectionTotal: number,
  minShare: number,
): TreemapLeaf[] {
  if (!sectionTotal || sectionTotal <= 0) return items
  const threshold = sectionTotal * minShare
  const large: TreemapLeaf[] = []
  let otherValue = 0
  let otherRaw = 0
  const otherCodes: string[] = []

  for (const item of items) {
    if (item.value < threshold && !item.isContra) {
      otherValue += item.value
      otherRaw += item.rawBalance
      otherCodes.push(item.accountCode)
    } else {
      large.push(item)
    }
  }

  if (otherValue > 0) {
    large.push({
      id: '__other__',
      name: `其他（${otherCodes.length} 个科目）`,
      accountCode: otherCodes[0] || '__other__',
      accountName: '其他',
      value: otherValue,
      rawBalance: otherRaw,
      isLeaf: false,
      isOther: true,
    })
  }
  return sortTreemapItemsByAccountCode(large)
}

/** 按科目代码升序排列，「其他」合并组置末，便于对照传统资产负债表阅读习惯 */
export function sortTreemapItemsByAccountCode(items: TreemapLeaf[]): TreemapLeaf[] {
  return [...items].sort((a, b) => {
    if (a.isOther && !b.isOther) return 1
    if (!a.isOther && b.isOther) return -1
    return a.accountCode.localeCompare(b.accountCode, 'zh-CN', { numeric: true })
  })
}

export function buildTreemapSection(
  rows: TrialBalanceRow[],
  sectionName: string,
  options?: {
    drillPrefix?: string | null
    minShare?: number
    allRows?: TrialBalanceRow[]
  },
): TreemapSection {
  const minShare = options?.minShare ?? DEFAULT_MIN_SHARE
  const drillPrefix = options?.drillPrefix ?? null
  const allRows = options?.allRows ?? rows
  const groups = groupRowsAtLevel(rows, drillPrefix)

  const items: TreemapLeaf[] = []
  for (const [key, bucket] of groups.entries()) {
    const rawBalance = bucket.reduce((sum, row) => sum + rowNetBalance(row), 0)
    const value = Math.abs(rawBalance)
    const isContra = rawBalance < 0
    const drillable = canDrillDeeper(allRows, key)
    items.push({
      id: key,
      name: displayNameForGroup(bucket, key),
      accountCode: key,
      accountName: bucket.find((r) => r.account_code === key)?.account_name || bucket[0]?.account_name || key,
      value: value > 0 ? value : 0.01,
      rawBalance,
      isLeaf: !drillable,
      isContra,
    })
  }

  const activeItems = items.filter((item) => item.value > 0 || item.isContra)
  const total = activeItems.reduce((sum, item) => sum + (item.isContra ? 0 : item.value), 0)

  return {
    id: sectionName,
    name: sectionName,
    total,
    items: mergeSmallItems(activeItems, total, minShare),
  }
}

export function buildLiabilityEquitySection(
  liabilities: TrialBalanceRow[],
  equity: TrialBalanceRow[],
  options?: {
    drillPrefix?: string | null
    drillSide?: 'liabilities' | 'equity' | null
    minShare?: number
  },
): TreemapSection {
  const drillPrefix = options?.drillPrefix ?? null
  const drillSide = options?.drillSide ?? null

  if (drillSide === 'liabilities') {
    return buildTreemapSection(liabilities, '负债', {
      drillPrefix,
      minShare: options?.minShare,
      allRows: liabilities,
    })
  }
  if (drillSide === 'equity') {
    return buildTreemapSection(equity, '所有者权益', {
      drillPrefix,
      minShare: options?.minShare,
      allRows: equity,
    })
  }

  const liabilitySection = buildTreemapSection(liabilities, '负债', { allRows: liabilities })
  const equitySection = buildTreemapSection(equity, '所有者权益', { allRows: equity })

  return {
    id: 'liability_equity',
    name: '负债与权益',
    total: liabilitySection.total + equitySection.total,
    items: [
      ...liabilitySection.items.map((item) => ({
        ...item,
        id: `liab:${item.id}`,
        name: item.isOther ? item.name : `负债 · ${item.name}`,
      })),
      ...equitySection.items.map((item) => ({
        ...item,
        id: `eq:${item.id}`,
        name: item.isOther ? item.name : `权益 · ${item.name}`,
      })),
    ],
  }
}

export function toEchartsTreemapData(section: TreemapSection) {
  return section.items.map((item) => ({
    name: item.name,
    value: item.value,
    id: item.id,
    accountCode: item.accountCode,
    rawBalance: item.rawBalance,
    isLeaf: item.isLeaf,
    isOther: item.isOther,
    isContra: item.isContra,
  }))
}

export function formatScaleMarks(total: number): string[] {
  if (total <= 0) return ['0']
  return [0, 0.25, 0.5, 0.75, 1].map((ratio) => {
    const amount = total * ratio
    if (amount >= 100000000) return `${(amount / 100000000).toFixed(1)}亿`
    if (amount >= 10000) return `${(amount / 10000).toFixed(1)}万`
    return amount.toFixed(0)
  })
}
