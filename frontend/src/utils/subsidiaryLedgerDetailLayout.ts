import type { AccountingEntry, EntryTag } from '../api/client'
import type { SubsidiaryLedgerSubtotalMode } from './subsidiaryLedgerPrefs'
import {
  injectSubsidiarySubtotals,
  type SubsidiaryLedgerDisplayRow,
} from './subsidiaryLedgerSubtotals'

export type TagSectionRow = {
  rowType: 'tag_section'
  rowKey: string
  sectionLabel: string
  tagValue: string
  entry_count: number
}

export type SubsidiaryTagDetailRow = SubsidiaryLedgerDisplayRow | TagSectionRow

export function isTagSectionRow(row: { rowType?: string }): row is TagSectionRow {
  return row.rowType === 'tag_section'
}

function tagBucketForEntry(
  tags: EntryTag[],
  categoryCode: string,
): { key: string; label: string } {
  const tag = tags.find((item) => item.category_code === categoryCode)
  if (!tag) {
    return { key: '__untagged__', label: '（未标注）' }
  }
  const label = tag.display_name || tag.tag_value || '（未命名）'
  return { key: label, label }
}

export function buildTagDetailRows(
  entries: AccountingEntry[],
  entryTagsById: Record<number, EntryTag[]>,
  categoryCode: string,
  categoryName: string,
  subtotalMode: SubsidiaryLedgerSubtotalMode,
  customDays: number,
  direction: 'debit' | 'credit',
): SubsidiaryTagDetailRow[] {
  const groups = new Map<string, { label: string; entries: AccountingEntry[] }>()
  for (const entry of entries) {
    const bucket = tagBucketForEntry(entryTagsById[entry.id] || [], categoryCode)
    const group = groups.get(bucket.key) ?? { label: bucket.label, entries: [] }
    group.entries.push(entry)
    groups.set(bucket.key, group)
  }

  const sortedKeys = [...groups.keys()].sort((a, b) => {
    if (a === '__untagged__') return 1
    if (b === '__untagged__') return -1
    return a.localeCompare(b, 'zh-CN')
  })

  const rows: SubsidiaryTagDetailRow[] = []
  for (const key of sortedKeys) {
    const group = groups.get(key)!
    rows.push({
      rowType: 'tag_section',
      rowKey: `tag-section-${categoryCode}-${key}`,
      sectionLabel: `${categoryName}：${group.label}`,
      tagValue: key,
      entry_count: group.entries.length,
    })

    let running = 0
    const innerRows = injectSubsidiarySubtotals(group.entries, subtotalMode, customDays)
    for (const row of innerRows) {
      if (row.rowType === 'entry') {
        const debit = Number(row.debit_amount || 0)
        const credit = Number(row.credit_amount || 0)
        running += direction === 'credit' ? credit - debit : debit - credit
        rows.push({ ...row, running_balance: running })
      } else {
        rows.push(row)
      }
    }
  }
  return rows
}

export function suggestDetailTagCategory(
  accountCode: string | undefined,
  categories: Array<{ code: string; name: string }>,
): string | undefined {
  if (!categories.length) return undefined
  const preferredByAccount: Record<string, string> = {
    '1002': 'bank_account',
    '1012': 'bank_account',
    '1122': 'customer',
    '1123': 'customer',
    '2202': 'supplier',
    '2203': 'supplier',
    '1403': 'material',
    '1601': 'fixed_asset_item',
  }
  const preferred = accountCode ? preferredByAccount[accountCode] : undefined
  if (preferred && categories.some((item) => item.code === preferred)) {
    return preferred
  }
  return categories[0]?.code
}
