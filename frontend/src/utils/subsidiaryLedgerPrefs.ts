export type SubsidiaryLedgerSubtotalMode = 'none' | 'day' | 'week' | 'month' | 'custom_days'

export type AccountCodeMatchMode = 'exact' | 'prefix'

export type DimensionColumnMode = 'all' | 'selected'

export type DimensionDisplayMode = 'compact' | 'columns'

/** 明细账展示结构：综合 / 仅科目 / 仅维度明细 */
export type SubsidiaryDetailLayoutMode = 'combined' | 'account' | 'tag'

export type SubsidiaryTagFilter = {
  categoryCode: string
  tagValue: string
}

export type TagCategorySelection = {
  categoryCode: string
  includeAll: boolean
  selectedValues: string[]
}

export type SubsidiaryLedgerHabit = {
  id: string
  name: string
  subtotalMode: SubsidiaryLedgerSubtotalMode
  customDays?: number
  accountCodeMatch: AccountCodeMatchMode
  selectedAccountCodes?: string[]
  /** @deprecated 使用 periodIds；读取时由 normalizeHabit 自动迁移 */
  periodId?: number | null
  periodIds?: number[]
  dateFrom?: string
  dateTo?: string
  dimensionColumnMode?: DimensionColumnMode
  dimensionDisplayMode?: DimensionDisplayMode
  detailLayoutMode?: SubsidiaryDetailLayoutMode
  detailTagCategoryCode?: string
  columnWidths?: Record<string, number>
  visibleCategoryCodes?: string[]
  tagFilters?: SubsidiaryTagFilter[]
  tagSelections?: TagCategorySelection[]
  summary?: string
  counterparty?: string
  isDefault?: boolean
}

export type SubsidiaryLedgerPrefs = {
  ledgerId: number
  defaultHabitId?: string
  habits: SubsidiaryLedgerHabit[]
  dimensionColumnMode?: DimensionColumnMode
  dimensionDisplayMode?: DimensionDisplayMode
  detailLayoutMode?: SubsidiaryDetailLayoutMode
  detailTagCategoryCode?: string
  columnWidths?: Record<string, number>
  visibleCategoryCodes?: string[]
  savedAt: number
}

const STORAGE_PREFIX = 'finance_audit_subsidiary_ledger_prefs_'

function storageKey(ledgerId: number): string {
  return `${STORAGE_PREFIX}${ledgerId}`
}

/** 将旧习惯里的单期间 periodId 迁移为 periodIds 数组 */
export function normalizeHabit(habit: SubsidiaryLedgerHabit): SubsidiaryLedgerHabit {
  const periodIds =
    habit.periodIds?.length
      ? [...habit.periodIds]
      : habit.periodId != null
        ? [habit.periodId]
        : []
  return {
    ...habit,
    periodIds,
  }
}

export function normalizePrefs(prefs: SubsidiaryLedgerPrefs): SubsidiaryLedgerPrefs {
  return {
    ...prefs,
    habits: prefs.habits.map(normalizeHabit),
  }
}

export function readSubsidiaryLedgerPrefs(ledgerId: number): SubsidiaryLedgerPrefs | null {
  if (!ledgerId) return null
  try {
    const raw = localStorage.getItem(storageKey(ledgerId))
    if (!raw) return null
    const parsed = JSON.parse(raw) as SubsidiaryLedgerPrefs
    if (!parsed?.ledgerId) return null
    return normalizePrefs(parsed)
  } catch {
    return null
  }
}

export function writeSubsidiaryLedgerPrefs(prefs: SubsidiaryLedgerPrefs): void {
  if (!prefs.ledgerId) return
  try {
    localStorage.setItem(
      storageKey(prefs.ledgerId),
      JSON.stringify({ ...prefs, savedAt: Date.now() }),
    )
  } catch {
    // ignore quota / private mode
  }
}

export function getDefaultHabit(prefs: SubsidiaryLedgerPrefs | null): SubsidiaryLedgerHabit | null {
  if (!prefs?.habits.length) return null
  if (prefs.defaultHabitId) {
    const found = prefs.habits.find((habit) => habit.id === prefs.defaultHabitId)
    if (found) return found
  }
  return prefs.habits.find((habit) => habit.isDefault) ?? prefs.habits[0]
}

export function upsertHabit(
  prefs: SubsidiaryLedgerPrefs,
  habit: SubsidiaryLedgerHabit,
  setDefault = false,
): SubsidiaryLedgerPrefs {
  const habits = prefs.habits.filter((item) => item.id !== habit.id)
  const nextHabit = { ...habit, isDefault: setDefault || habit.isDefault }
  const normalized = setDefault
    ? habits.map((item) => ({ ...item, isDefault: false }))
    : habits
  return {
    ...prefs,
    habits: [...normalized, nextHabit],
    defaultHabitId: setDefault ? nextHabit.id : prefs.defaultHabitId,
    savedAt: Date.now(),
  }
}

export function createEmptyPrefs(ledgerId: number): SubsidiaryLedgerPrefs {
  return {
    ledgerId,
    habits: [],
    savedAt: Date.now(),
  }
}

export function newHabitId(): string {
  return `habit_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
}

export type TagCategoryMeta = { code: string; name: string }

export function flattenTagCategoryMeta(
  nodes: Array<{ code: string; name: string; children?: Array<{ code: string; name: string; children?: unknown[] }> }>,
): TagCategoryMeta[] {
  const rows: TagCategoryMeta[] = []
  const walk = (
    list: Array<{ code: string; name: string; children?: Array<{ code: string; name: string; children?: unknown[] }> }>,
  ) => {
    for (const node of list) {
      rows.push({ code: node.code, name: node.name })
      if (node.children?.length) walk(node.children)
    }
  }
  walk(nodes)
  return rows
}
