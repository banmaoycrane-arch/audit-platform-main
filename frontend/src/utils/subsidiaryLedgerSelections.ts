import type { SubsidiaryTagFilter } from './subsidiaryLedgerPrefs'

export type TagCategorySelection = {
  categoryCode: string
  includeAll: boolean
  selectedValues: string[]
}

export function expandAccountRange(
  startCode: string,
  endCode: string,
  orderedCodes: string[],
): string[] {
  const startIdx = orderedCodes.indexOf(startCode)
  const endIdx = orderedCodes.indexOf(endCode)
  if (startIdx < 0 && endIdx < 0) {
    return [startCode, endCode].filter(Boolean)
  }
  if (startIdx < 0) return [startCode]
  if (endIdx < 0) return [endCode]
  const [lo, hi] = startIdx <= endIdx ? [startIdx, endIdx] : [endIdx, startIdx]
  return orderedCodes.slice(lo, hi + 1)
}

export function parseAccountSpec(spec: string, orderedCodes: string[]): string[] {
  const result = new Set<string>()
  const parts = spec
    .split(/[,，;\s]+/)
    .map((item) => item.trim())
    .filter(Boolean)
  for (const part of parts) {
    if (part.includes('~')) {
      const [from, to] = part.split('~').map((item) => item.trim())
      if (from && to) {
        expandAccountRange(from, to, orderedCodes).forEach((code) => result.add(code))
      }
    } else {
      result.add(part)
    }
  }
  return [...result]
}

export function mergeUniqueCodes(...groups: string[][]): string[] {
  const codes: string[] = []
  for (const group of groups) {
    for (const code of group) {
      const normalized = String(code).trim()
      if (normalized) codes.push(normalized)
    }
  }
  return [...new Set(codes)]
}

export function formatAccountCodesLabel(codes: string[]): string {
  if (!codes.length) return ''
  if (codes.length <= 3) return codes.join('、')
  return `${codes.slice(0, 3).join('、')} 等 ${codes.length} 个科目`
}

export function serializeTagSelections(
  selections: TagCategorySelection[],
): string | undefined {
  const rows = selections
    .filter((item) => item.categoryCode && !item.includeAll && item.selectedValues.length > 0)
    .map((item) => ({
      category_code: item.categoryCode,
      tag_values: [...new Set(item.selectedValues)],
    }))
  if (!rows.length) return undefined
  return JSON.stringify(rows)
}

export function migrateLegacyTagFilters(filters: SubsidiaryTagFilter[]): TagCategorySelection[] {
  const grouped = new Map<string, string[]>()
  for (const item of filters) {
    if (!item.categoryCode || !item.tagValue) continue
    const bucket = grouped.get(item.categoryCode) ?? []
    bucket.push(item.tagValue)
    grouped.set(item.categoryCode, bucket)
  }
  return [...grouped.entries()].map(([categoryCode, values]) => ({
    categoryCode,
    includeAll: false,
    selectedValues: [...new Set(values)],
  }))
}

export function tagValueKey(tag: { tag_value: string; display_name?: string | null }): string {
  return tag.display_name || tag.tag_value
}

export function isTagValueSelected(
  selection: TagCategorySelection | undefined,
  value: string,
  allValues: string[],
): boolean {
  if (!selection || selection.includeAll) return true
  if (!selection.selectedValues.length) return false
  return selection.selectedValues.includes(value)
}

export function toggleTagValue(
  selection: TagCategorySelection | undefined,
  value: string,
  allValues: string[],
  checked: boolean,
): TagCategorySelection {
  const categoryCode = selection?.categoryCode ?? ''
  const base =
    selection && !selection.includeAll
      ? [...selection.selectedValues]
      : [...allValues]
  const next = checked ? mergeUniqueCodes(base, [value]) : base.filter((item) => item !== value)
  return {
    categoryCode,
    includeAll: false,
    selectedValues: next,
  }
}

export function ensureTagSelection(
  selections: Record<string, TagCategorySelection>,
  categoryCode: string,
  allValues: string[],
): TagCategorySelection {
  const existing = selections[categoryCode]
  if (existing) return existing
  return {
    categoryCode,
    includeAll: true,
    selectedValues: [...allValues],
  }
}

export function addTagToSelection(
  selections: Record<string, TagCategorySelection>,
  categoryCode: string,
  value: string,
  allValues: string[],
): Record<string, TagCategorySelection> {
  const current = ensureTagSelection(selections, categoryCode, allValues)
  const selected = current.includeAll ? [...allValues] : [...current.selectedValues]
  if (!selected.includes(value)) selected.push(value)
  return {
    ...selections,
    [categoryCode]: {
      categoryCode,
      includeAll: false,
      selectedValues: selected,
    },
  }
}

export function removeTagFromSelection(
  selections: Record<string, TagCategorySelection>,
  categoryCode: string,
  value: string,
  allValues: string[],
): Record<string, TagCategorySelection> {
  const current = ensureTagSelection(selections, categoryCode, allValues)
  if (current.includeAll) {
    const nextValues = allValues.filter((item) => item !== value)
    return {
      ...selections,
      [categoryCode]: {
        categoryCode,
        includeAll: nextValues.length === allValues.length,
        selectedValues: nextValues,
      },
    }
  }
  const nextValues = current.selectedValues.filter((item) => item !== value)
  return {
    ...selections,
    [categoryCode]: {
      categoryCode,
      includeAll: nextValues.length === allValues.length,
      selectedValues: nextValues.length === allValues.length ? allValues : nextValues,
    },
  }
}

export function selectionsToArray(
  selections: Record<string, TagCategorySelection>,
): TagCategorySelection[] {
  return Object.values(selections).filter((item) => item.categoryCode)
}
