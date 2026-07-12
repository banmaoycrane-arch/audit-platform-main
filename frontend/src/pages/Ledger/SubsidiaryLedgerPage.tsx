import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Col,
  DatePicker,
  Drawer,
  Empty,
  Input,
  InputNumber,
  Modal,
  Pagination,
  Row,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import {
  ColumnWidthOutlined,
  DownloadOutlined,
  ReloadOutlined,
  SaveOutlined,
  SearchOutlined,
  StarOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import { Link, useLocation } from 'react-router-dom'

import {
  api,
  type AccountingEntry,
  type AccountingPeriod,
  type ChartOfAccount,
  type EntryTag,
  type EntryTagAggregate,
  type TagCategoryNode,
} from '../../api/client'
import { EntryTagsCompactCell } from '../../components/ledger/EntryTagsCompactCell'
import { ResizableTableHeaderCell } from '../../components/ledger/ResizableTableHeader'
import { SubsidiaryLedgerTagNavigator } from '../../components/ledger/SubsidiaryLedgerTagNavigator'
import { useAuthStore } from '../../stores/authStore'
import { formatAmount } from '../../money'
import {
  attachRunningBalances,
  isOpeningRow,
  type SubsidiaryLedgerRow,
} from '../../utils/subsidiaryLedgerBalances'
import {
  buildTagDetailRows,
  isTagSectionRow,
  type SubsidiaryTagDetailRow,
} from '../../utils/subsidiaryLedgerDetailLayout'
import {
  COLUMN_WIDTH_LABELS,
  DEFAULT_DIMENSION_COLUMN_WIDTH,
  clampColumnWidth,
  dimensionColumnKey,
  mergeColumnWidths,
  resolveColumnWidth,
  sumColumnWidths,
  type SubsidiaryLedgerColumnWidths,
} from '../../utils/subsidiaryLedgerColumnWidths'
import {
  createEmptyPrefs,
  flattenTagCategoryMeta,
  getDefaultHabit,
  newHabitId,
  normalizeHabit,
  readSubsidiaryLedgerPrefs,
  upsertHabit,
  writeSubsidiaryLedgerPrefs,
  type AccountCodeMatchMode,
  type DimensionColumnMode,
  type DimensionDisplayMode,
  type SubsidiaryDetailLayoutMode,
  type SubsidiaryLedgerHabit,
  type SubsidiaryLedgerSubtotalMode,
  type TagCategoryMeta,
} from '../../utils/subsidiaryLedgerPrefs'
import {
  expandAccountRange,
  formatAccountCodesLabel,
  mergeUniqueCodes,
  migrateLegacyTagFilters,
  parseAccountSpec,
  removeTagFromSelection,
  selectionsToArray,
  serializeTagSelections,
  tagValueKey,
  type TagCategorySelection,
} from '../../utils/subsidiaryLedgerSelections'
import { injectSubsidiarySubtotals } from '../../utils/subsidiaryLedgerSubtotals'

const { Title, Paragraph, Text } = Typography
const { RangePicker } = DatePicker

type AppliedQuery = {
  accountCodes: string[]
  periodIds?: number[]
  dateFrom?: string
  dateTo?: string
  summary?: string
  counterparty?: string
  tagSelections: TagCategorySelection[]
}

type SubsidiaryLedgerLocationState = {
  accountCodes?: string[]
  periodIds?: number[]
  autoSearch?: boolean
}

const SUBTOTAL_OPTIONS: Array<{ value: SubsidiaryLedgerSubtotalMode; label: string }> = [
  { value: 'none', label: '无小计' },
  { value: 'day', label: '按日小计' },
  { value: 'week', label: '按周小计' },
  { value: 'month', label: '按月小计' },
  { value: 'custom_days', label: '自定义周期小计' },
]

/** 科目明细账：按汇总科目查询，始终含本级及全部下级明细科目分录 */
const SUBSIDIARY_ACCOUNT_MATCH: AccountCodeMatchMode = 'prefix'

const DIMENSION_DISPLAY_MODE_OPTIONS: Array<{ value: DimensionDisplayMode; label: string }> = [
  { value: 'compact', label: '紧凑标签列（一屏可见）' },
  { value: 'columns', label: '按维度分列（宽屏）' },
]

const DIMENSION_COLUMN_MODE_OPTIONS: Array<{ value: DimensionColumnMode; label: string }> = [
  { value: 'all', label: '显示全部维度列' },
  { value: 'selected', label: '仅显示指定维度列' },
]

const DETAIL_LAYOUT_OPTIONS: Array<{ value: SubsidiaryDetailLayoutMode; label: string }> = [
  { value: 'combined', label: '综合（科目汇总 + 维度明细）' },
  { value: 'account', label: '仅科目汇总' },
  { value: 'tag', label: '仅维度明细' },
]

const PAGE_SIZE = 50
const SUBTOTAL_FETCH_LIMIT = 2000
const LAYOUT_FETCH_LIMIT = 3000
const API_PAGE_LIMIT = 500
const TAG_BATCH_SIZE = 200

function flattenTagCategories(nodes: TagCategoryNode[]) {
  return flattenTagCategoryMeta(nodes).map((item) => ({
    value: item.code,
    label: `${item.name} (${item.code})`,
  }))
}

function tagTextForCategory(tags: EntryTag[], categoryCode: string): string {
  const tag = tags.find((item) => item.category_code === categoryCode)
  if (!tag) return '-'
  return tag.display_name || tag.tag_value || '-'
}

async function loadEntryTagsBatched(
  ledgerId: number,
  entryIds: number[],
): Promise<Record<number, EntryTag[]>> {
  const grouped: Record<number, EntryTag[]> = {}
  const uniqueIds = [...new Set(entryIds)]
  for (let offset = 0; offset < uniqueIds.length; offset += TAG_BATCH_SIZE) {
    const chunk = uniqueIds.slice(offset, offset + TAG_BATCH_SIZE)
    if (!chunk.length) continue
    const tags = await api.batchListEntryTags({ entry_ids: chunk, ledger_id: ledgerId })
    for (const tag of tags) {
      grouped[tag.entry_id] = grouped[tag.entry_id] || []
      grouped[tag.entry_id].push(tag)
    }
  }
  return grouped
}

async function fetchChronologicalAll(
  baseFilters: Parameters<typeof api.listChronologicalEntries>[0],
  maxRows: number,
): Promise<{ items: AccountingEntry[]; total: number; truncated: boolean }> {
  const first = await api.listChronologicalEntries({
    ...baseFilters,
    limit: API_PAGE_LIMIT,
    offset: 0,
  })
  const items = [...first.items]
  let offset = API_PAGE_LIMIT
  while (items.length < first.total && items.length < maxRows && offset < first.total) {
    const next = await api.listChronologicalEntries({
      ...baseFilters,
      limit: API_PAGE_LIMIT,
      offset,
    })
    items.push(...next.items)
    offset += API_PAGE_LIMIT
  }
  return {
    items: items.slice(0, maxRows),
    total: first.total,
    truncated: first.total > maxRows,
  }
}

export function SubsidiaryLedgerPage() {
  const { currentLedgerId } = useAuthStore()
  const location = useLocation()
  const navStateConsumedRef = useRef(false)
  const [entries, setEntries] = useState<AccountingEntry[]>([])
  const [entryTagsById, setEntryTagsById] = useState<Record<number, EntryTag[]>>({})
  const [accounts, setAccounts] = useState<ChartOfAccount[]>([])
  const [ledgerAccountCodes, setLedgerAccountCodes] = useState<
    Array<{ account_code: string; account_name: string | null; entry_count: number }>
  >([])
  const [tagCategories, setTagCategories] = useState<TagCategoryNode[]>([])
  const [tagValueOptionsByCode, setTagValueOptionsByCode] = useState<Record<string, EntryTagAggregate[]>>({})
  const [draftAccountCodes, setDraftAccountCodes] = useState<string[]>([])
  const [draftAccountRangeFrom, setDraftAccountRangeFrom] = useState<string | undefined>()
  const [draftAccountRangeTo, setDraftAccountRangeTo] = useState<string | undefined>()
  const [draftAccountSpec, setDraftAccountSpec] = useState('')
  const [accountingPeriods, setAccountingPeriods] = useState<AccountingPeriod[]>([])
  const [draftPeriodIds, setDraftPeriodIds] = useState<number[]>([])
  const [draftDateRange, setDraftDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(null)
  const [draftSummary, setDraftSummary] = useState('')
  const [draftCounterparty, setDraftCounterparty] = useState('')
  const [draftTagSelections, setDraftTagSelections] = useState<Record<string, TagCategorySelection>>({})
  const [activeTagCategoryCode, setActiveTagCategoryCode] = useState<string | undefined>()
  const [appliedQuery, setAppliedQuery] = useState<AppliedQuery | null>(null)
  const [dimensionColumnMode, setDimensionColumnMode] = useState<DimensionColumnMode>('all')
  const [dimensionDisplayMode, setDimensionDisplayMode] = useState<DimensionDisplayMode>('compact')
  const [detailLayoutMode, setDetailLayoutMode] = useState<SubsidiaryDetailLayoutMode>('account')
  const [detailTagCategoryCode, setDetailTagCategoryCode] = useState<string | undefined>()
  const [columnWidths, setColumnWidths] = useState<SubsidiaryLedgerColumnWidths>(() =>
    mergeColumnWidths(undefined),
  )
  const [columnWidthModalOpen, setColumnWidthModalOpen] = useState(false)
  const [layoutEntries, setLayoutEntries] = useState<AccountingEntry[]>([])
  const [layoutTruncated, setLayoutTruncated] = useState(false)
  const [visibleCategoryCodes, setVisibleCategoryCodes] = useState<string[]>([])
  const [subtotalMode, setSubtotalMode] = useState<SubsidiaryLedgerSubtotalMode>('none')
  const [customDays, setCustomDays] = useState(7)
  const [openingBalance, setOpeningBalance] = useState(0)
  const [balanceDirection, setBalanceDirection] = useState<'debit' | 'credit'>('debit')
  const [habits, setHabits] = useState<SubsidiaryLedgerHabit[]>([])
  const [selectedHabitId, setSelectedHabitId] = useState<string | undefined>()
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [prefsLoaded, setPrefsLoaded] = useState(false)
  const [saveHabitModalOpen, setSaveHabitModalOpen] = useState(false)
  const [saveHabitAsDefault, setSaveHabitAsDefault] = useState(false)
  const [habitNameDraft, setHabitNameDraft] = useState('')
  const [voucherDrawerOpen, setVoucherDrawerOpen] = useState(false)
  const [voucherDrawerLoading, setVoucherDrawerLoading] = useState(false)
  const [activeVoucher, setActiveVoucher] = useState<{ voucherNo: string | null; voucherDate: string | null } | null>(null)
  const [voucherLines, setVoucherLines] = useState<AccountingEntry[]>([])

  const allCategoryMeta = useMemo(() => flattenTagCategoryMeta(tagCategories), [tagCategories])
  const tagCategoryOptions = useMemo(() => flattenTagCategories(tagCategories), [tagCategories])
  const orderedAccountCodes = useMemo(() => {
    const coaCodes = accounts.map((account) => account.code)
    const ledgerCodes = ledgerAccountCodes.map((row) => row.account_code)
    return [...new Set([...coaCodes, ...ledgerCodes])].sort((a, b) => a.localeCompare(b, 'zh-CN'))
  }, [accounts, ledgerAccountCodes])

  const effectiveDraftAccountCodes = useMemo(() => {
    const fromSpec = draftAccountSpec.trim()
      ? parseAccountSpec(draftAccountSpec, orderedAccountCodes)
      : []
    return mergeUniqueCodes(draftAccountCodes, fromSpec)
  }, [draftAccountCodes, draftAccountSpec, orderedAccountCodes])


  useEffect(() => {
    api.listChartOfAccounts().then(setAccounts).catch(() => setAccounts([]))
  }, [])

  useEffect(() => {
    if (!currentLedgerId) {
      setTagCategories([])
      setHabits([])
      setPrefsLoaded(false)
      setAppliedQuery(null)
      navStateConsumedRef.current = false
      return
    }
    void api
      .listTagCategories(currentLedgerId, { status: 'active' })
      .then(setTagCategories)
      .catch(() => setTagCategories([]))
    void api
      .listLedgerAccountCodes(currentLedgerId)
      .then(setLedgerAccountCodes)
      .catch(() => setLedgerAccountCodes([]))
    void api
      .listAccountingPeriods(undefined, currentLedgerId)
      .then(setAccountingPeriods)
      .catch(() => setAccountingPeriods([]))

    const prefs = readSubsidiaryLedgerPrefs(currentLedgerId) ?? createEmptyPrefs(currentLedgerId)
    setHabits(prefs.habits)
    const defaultHabit = getDefaultHabit(prefs)
    if (defaultHabit) {
      setSelectedHabitId(defaultHabit.id)
      setSubtotalMode(defaultHabit.subtotalMode)
      setCustomDays(defaultHabit.customDays ?? 7)
      setDimensionColumnMode(defaultHabit.dimensionColumnMode ?? prefs.dimensionColumnMode ?? 'all')
      setDimensionDisplayMode(
        defaultHabit.dimensionDisplayMode ?? prefs.dimensionDisplayMode ?? 'compact',
      )
      setDetailLayoutMode(defaultHabit.detailLayoutMode ?? prefs.detailLayoutMode ?? 'account')
      setColumnWidths(mergeColumnWidths(defaultHabit.columnWidths ?? prefs.columnWidths))
      setVisibleCategoryCodes(defaultHabit.visibleCategoryCodes ?? prefs.visibleCategoryCodes ?? [])
      setDraftSummary(defaultHabit.summary ?? '')
      setDraftCounterparty(defaultHabit.counterparty ?? '')
      setDraftTagSelections({})
      setDraftPeriodIds([])
      setDraftDateRange(null)
      setDetailTagCategoryCode(undefined)
      setActiveTagCategoryCode(undefined)
      if (defaultHabit.selectedAccountCodes?.length) {
        setDraftAccountCodes(defaultHabit.selectedAccountCodes)
      }
    } else {
      setDimensionColumnMode(prefs.dimensionColumnMode ?? 'all')
      setDimensionDisplayMode(prefs.dimensionDisplayMode ?? 'compact')
      setDetailLayoutMode(prefs.detailLayoutMode ?? 'account')
      setColumnWidths(mergeColumnWidths(prefs.columnWidths))
      setVisibleCategoryCodes(prefs.visibleCategoryCodes ?? [])
      setDetailTagCategoryCode(undefined)
      setActiveTagCategoryCode(undefined)
    }
    setPrefsLoaded(true)
  }, [currentLedgerId])

  useEffect(() => {
    if (!prefsLoaded || !currentLedgerId || navStateConsumedRef.current) return
    const navState = location.state as SubsidiaryLedgerLocationState | null
    if (!navState?.accountCodes?.length) return

    navStateConsumedRef.current = true
    setDraftAccountCodes(navState.accountCodes)
    setDraftAccountSpec('')
    setDraftAccountRangeFrom(undefined)
    setDraftAccountRangeTo(undefined)
    setDraftPeriodIds(navState.periodIds ?? [])
    setDraftDateRange(null)
    setDraftTagSelections({})
    setActiveTagCategoryCode(undefined)

    if (navState.autoSearch) {
      setPage(1)
      setAppliedQuery({
        accountCodes: navState.accountCodes,
        periodIds: navState.periodIds?.length ? navState.periodIds : undefined,
        tagSelections: [],
      })
    }
  }, [prefsLoaded, currentLedgerId, location.state])

  useEffect(() => {
    if (!allCategoryMeta.length) return
    if (dimensionColumnMode === 'all') {
      setVisibleCategoryCodes(allCategoryMeta.map((item) => item.code))
      return
    }
    setVisibleCategoryCodes((prev) => {
      if (prev.length) {
        return prev.filter((code) => allCategoryMeta.some((item) => item.code === code))
      }
      return allCategoryMeta.map((item) => item.code)
    })
  }, [allCategoryMeta, dimensionColumnMode])

  const periodOptions = useMemo(
    () =>
      accountingPeriods.map((period) => ({
        value: period.id,
        label: `${period.period_code}（${period.start_date} ~ ${period.end_date}）`,
      })),
    [accountingPeriods],
  )

  useEffect(() => {
    if (!currentLedgerId) return
    writeSubsidiaryLedgerPrefs({
      ledgerId: currentLedgerId,
      habits,
      defaultHabitId: habits.find((item) => item.isDefault)?.id,
      dimensionColumnMode,
      dimensionDisplayMode,
      detailLayoutMode,
      detailTagCategoryCode,
      columnWidths,
      visibleCategoryCodes,
      savedAt: Date.now(),
    })
  }, [
    currentLedgerId,
    dimensionColumnMode,
    dimensionDisplayMode,
    detailLayoutMode,
    detailTagCategoryCode,
    columnWidths,
    visibleCategoryCodes,
    habits,
  ])

  const setColumnWidth = useCallback((key: string, width: number) => {
    setColumnWidths((prev) => ({
      ...prev,
      [key]: clampColumnWidth(width),
    }))
  }, [])

  const resetColumnWidths = useCallback(() => {
    setColumnWidths(mergeColumnWidths(undefined))
    message.success('已恢复默认列宽')
  }, [])

  const loadTagValuesForCategory = useCallback(
    async (categoryCode: string) => {
      if (!currentLedgerId || !categoryCode) return
      const values = await api.aggregateEntryTagsScoped(currentLedgerId, categoryCode, {
        account_codes: effectiveDraftAccountCodes,
        account_code_match: SUBSIDIARY_ACCOUNT_MATCH,
        include_voucher_lines: true,
        limit: 500,
      })
      setTagValueOptionsByCode((prev) => ({ ...prev, [categoryCode]: values }))
    },
    [currentLedgerId, effectiveDraftAccountCodes],
  )

  useEffect(() => {
    if (!activeTagCategoryCode || !effectiveDraftAccountCodes.length) return
    void loadTagValuesForCategory(activeTagCategoryCode)
  }, [activeTagCategoryCode, effectiveDraftAccountCodes, loadTagValuesForCategory])

  const visibleCategories = useMemo(() => {
    if (dimensionColumnMode === 'all') return allCategoryMeta
    return allCategoryMeta.filter((item) => visibleCategoryCodes.includes(item.code))
  }, [allCategoryMeta, dimensionColumnMode, visibleCategoryCodes])

  const buildApiFilters = useCallback(
    (query: AppliedQuery, mode: 'paginated' | 'subtotal' | 'full') => {
      const tagFiltersJson = serializeTagSelections(query.tagSelections)
      const limit =
        mode === 'paginated' ? PAGE_SIZE : mode === 'subtotal' ? SUBTOTAL_FETCH_LIMIT : API_PAGE_LIMIT
      const offset = mode === 'paginated' ? (page - 1) * PAGE_SIZE : 0
      return {
        ledger_id: currentLedgerId!,
        account_codes: query.accountCodes,
        account_code_match: SUBSIDIARY_ACCOUNT_MATCH,
        period_ids: query.periodIds,
        date_from: query.dateFrom,
        date_to: query.dateTo,
        summary: query.summary?.trim() || undefined,
        counterparty: query.counterparty?.trim() || undefined,
        tag_filters: tagFiltersJson,
        tag_match_scope: 'voucher',
        limit,
        offset,
      }
    },
    [currentLedgerId, page],
  )

  const loadEntries = useCallback(async () => {
    if (!currentLedgerId || !appliedQuery?.accountCodes.length) {
      setEntries([])
      setLayoutEntries([])
      setEntryTagsById({})
      setTotal(0)
      setOpeningBalance(0)
      setLayoutTruncated(false)
      return
    }
    setLoading(true)
    try {
      const useSubtotal = subtotalMode !== 'none'
      const needLayoutData = detailLayoutMode !== 'account'
      const openingFilters = buildApiFilters(appliedQuery, useSubtotal ? 'subtotal' : 'paginated')

      let resp: { items: AccountingEntry[]; total: number; truncated: boolean }
      if (useSubtotal) {
        const data = await api.listChronologicalEntries(buildApiFilters(appliedQuery, 'subtotal'))
        resp = { items: data.items, total: data.total, truncated: false }
      } else if (detailLayoutMode === 'tag') {
        const full = await fetchChronologicalAll(buildApiFilters(appliedQuery, 'full'), LAYOUT_FETCH_LIMIT)
        resp = { items: full.items, total: full.total, truncated: full.truncated }
      } else {
        const data = await api.listChronologicalEntries(buildApiFilters(appliedQuery, 'paginated'))
        resp = { items: data.items, total: data.total, truncated: false }
      }

      setEntries(resp.items)
      setTotal(resp.total)

      try {
        const opening = await api.getSubsidiaryOpeningBalance({
          ledger_id: currentLedgerId,
          account_codes: appliedQuery.accountCodes,
          account_code_match: SUBSIDIARY_ACCOUNT_MATCH,
          period_ids: appliedQuery.periodIds,
          date_from: appliedQuery.dateFrom,
          summary: appliedQuery.summary,
          counterparty: appliedQuery.counterparty,
          tag_filters: openingFilters.tag_filters,
        })
        setOpeningBalance(opening.opening_balance)
        setBalanceDirection(opening.direction)
      } catch (openingError) {
        setOpeningBalance(0)
        setBalanceDirection('debit')
        message.warning(
          `期初余额加载失败：${openingError instanceof Error ? openingError.message : String(openingError)}，分录列表仍可用`,
        )
      }

      let layoutData: AccountingEntry[] = []
      let truncated = detailLayoutMode === 'tag' ? resp.truncated : false
      if (needLayoutData) {
        if (useSubtotal || detailLayoutMode === 'tag') {
          layoutData = resp.items
        } else {
          const full = await fetchChronologicalAll(buildApiFilters(appliedQuery, 'full'), LAYOUT_FETCH_LIMIT)
          layoutData = full.items
          truncated = full.truncated
        }
      }
      setLayoutEntries(layoutData)
      setLayoutTruncated(truncated)

      const tagEntryIds = [
        ...new Set([
          ...resp.items.map((item) => item.id),
          ...layoutData.map((item) => item.id),
        ]),
      ]
      if (tagEntryIds.length > 0) {
        try {
          const grouped = await loadEntryTagsBatched(currentLedgerId, tagEntryIds)
          setEntryTagsById(grouped)
        } catch (tagError) {
          setEntryTagsById({})
          message.warning(
            `维度标签加载失败：${tagError instanceof Error ? tagError.message : String(tagError)}，分录列表仍可用`,
          )
        }
      } else {
        setEntryTagsById({})
      }
      if (useSubtotal && resp.total > SUBTOTAL_FETCH_LIMIT) {
        message.warning(`共 ${resp.total} 条分录，小计模式仅展示前 ${SUBTOTAL_FETCH_LIMIT} 条`)
      }
      if (truncated) {
        message.warning(`维度明细仅展示前 ${LAYOUT_FETCH_LIMIT} 条，完整数据请导出 Excel`)
      }
    } catch (error) {
      message.error(`加载明细账失败：${error instanceof Error ? error.message : String(error)}`)
      setEntries([])
      setLayoutEntries([])
      setEntryTagsById({})
      setTotal(0)
      setOpeningBalance(0)
      setLayoutTruncated(false)
    } finally {
      setLoading(false)
    }
  }, [
    currentLedgerId,
    appliedQuery,
    subtotalMode,
    buildApiFilters,
    detailLayoutMode,
  ])

  useEffect(() => {
    if (!prefsLoaded) return
    void loadEntries()
  }, [loadEntries, prefsLoaded])

  useEffect(() => {
    setPage(1)
    setAppliedQuery(null)
    setTagValueOptionsByCode({})
  }, [draftAccountCodes, draftAccountSpec])

  const displayRows = useMemo(() => {
    const base = injectSubsidiarySubtotals(entries, subtotalMode, customDays)
    return attachRunningBalances(base, openingBalance, balanceDirection)
  }, [entries, subtotalMode, customDays, openingBalance, balanceDirection])

  const detailCategoryMeta = useMemo(
    () => allCategoryMeta.find((item) => item.code === detailTagCategoryCode),
    [allCategoryMeta, detailTagCategoryCode],
  )

  const tagDetailRows = useMemo((): SubsidiaryTagDetailRow[] => {
    if (detailLayoutMode === 'account' || !detailTagCategoryCode) return []
    const source = layoutEntries.length ? layoutEntries : entries
    return buildTagDetailRows(
      source,
      entryTagsById,
      detailTagCategoryCode,
      detailCategoryMeta?.name || detailTagCategoryCode,
      subtotalMode,
      customDays,
      balanceDirection,
    )
  }, [
    detailLayoutMode,
    detailTagCategoryCode,
    layoutEntries,
    entries,
    entryTagsById,
    detailCategoryMeta,
    subtotalMode,
    customDays,
    balanceDirection,
  ])

  const accountOptions = useMemo(() => {
    const coaCodes = new Set(accounts.map((account) => account.code))
    const exactCountByCode = Object.fromEntries(
      ledgerAccountCodes.map((row) => [row.account_code, row.entry_count]),
    )

    const prefixCountFor = (code: string) =>
      ledgerAccountCodes
        .filter((row) => row.account_code === code || row.account_code.startsWith(code))
        .reduce((sum, row) => sum + row.entry_count, 0)

    const options = accounts.map((account) => {
      const exact = exactCountByCode[account.code] || 0
      const prefixTotal = prefixCountFor(account.code)
      let countLabel = ''
      if (prefixTotal > 0) {
        countLabel =
          exact > 0 ? `（${prefixTotal} 条）` : `（含明细 ${prefixTotal} 条）`
      }
      return {
        value: account.code,
        label: `${account.code} ${account.name}${countLabel}`,
      }
    })

    for (const row of ledgerAccountCodes) {
      if (!coaCodes.has(row.account_code)) {
        options.push({
          value: row.account_code,
          label: `${row.account_code} ${row.account_name || ''}（${row.entry_count} 条）`,
        })
      }
    }

    return options.sort((a, b) => a.value.localeCompare(b.value, 'zh-CN'))
  }, [accounts, ledgerAccountCodes])

  const handleAccountMultiChange = (codes: string[]) => {
    setDraftAccountCodes(codes)
  }

  const addAccountRange = () => {
    if (!draftAccountRangeFrom || !draftAccountRangeTo) {
      message.warning('请选择科目范围的起止')
      return
    }
    const codes = expandAccountRange(draftAccountRangeFrom, draftAccountRangeTo, orderedAccountCodes)
    setDraftAccountCodes((prev) => mergeUniqueCodes(prev, codes))
    setDraftAccountRangeFrom(undefined)
    setDraftAccountRangeTo(undefined)
    message.success(`已添加 ${codes.length} 个科目`)
  }

  const clearAccountSelection = () => {
    setDraftAccountCodes([])
    setDraftAccountSpec('')
    setDraftAccountRangeFrom(undefined)
    setDraftAccountRangeTo(undefined)
  }

  const habitOptions = useMemo(
    () =>
      habits.map((habit) => ({
        value: habit.id,
        label: `${habit.name}${habit.isDefault ? '（默认）' : ''}`,
      })),
    [habits],
  )

  const applySearch = () => {
    if (!currentLedgerId) {
      message.warning('请先选择账簿')
      return
    }
    if (!effectiveDraftAccountCodes.length) {
      message.warning('请先选择科目')
      return
    }
    const hasDateRange = Boolean(draftDateRange?.[0] && draftDateRange?.[1])
    const explicitTagSelections = selectionsToArray(draftTagSelections).filter(
      (item) => !item.includeAll && item.selectedValues.length > 0,
    )
    setPage(1)
    setAppliedQuery({
      accountCodes: effectiveDraftAccountCodes,
      periodIds: !hasDateRange && draftPeriodIds.length ? draftPeriodIds : undefined,
      dateFrom: hasDateRange ? draftDateRange![0].format('YYYY-MM-DD') : undefined,
      dateTo: hasDateRange ? draftDateRange![1].format('YYYY-MM-DD') : undefined,
      summary: draftSummary,
      counterparty: draftCounterparty,
      tagSelections: explicitTagSelections,
    })
  }

  const resetFilters = () => {
    setDraftPeriodIds([])
    setDraftDateRange(null)
    setDraftSummary('')
    setDraftCounterparty('')
    setDraftTagSelections({})
    setActiveTagCategoryCode(undefined)
    setDetailTagCategoryCode(undefined)
    clearAccountSelection()
    setPage(1)
    setAppliedQuery(null)
  }

  const applyHabit = (habitId: string) => {
    const raw = habits.find((item) => item.id === habitId)
    if (!raw) return
    const habit = normalizeHabit(raw)
    setSelectedHabitId(habitId)
    setSubtotalMode(habit.subtotalMode)
    setCustomDays(habit.customDays ?? 7)
    setDimensionColumnMode(habit.dimensionColumnMode ?? 'all')
    setDimensionDisplayMode(habit.dimensionDisplayMode ?? 'compact')
    setDetailLayoutMode(habit.detailLayoutMode ?? 'account')
    setDetailTagCategoryCode(habit.detailTagCategoryCode)
    setActiveTagCategoryCode(undefined)
    setColumnWidths(mergeColumnWidths(habit.columnWidths))
    setVisibleCategoryCodes(habit.visibleCategoryCodes ?? allCategoryMeta.map((item) => item.code))
    setDraftPeriodIds(habit.periodIds ?? [])
    setDraftDateRange(
      habit.dateFrom && habit.dateTo ? [dayjs(habit.dateFrom), dayjs(habit.dateTo)] : null,
    )
    setDraftSummary(habit.summary ?? '')
    setDraftCounterparty(habit.counterparty ?? '')
    setDraftAccountSpec('')
    setDraftAccountCodes(habit.selectedAccountCodes ?? [])
    setDraftTagSelections(
      habit.tagSelections?.length
        ? Object.fromEntries(habit.tagSelections.map((item) => [item.categoryCode, item]))
        : habit.tagFilters?.length
          ? Object.fromEntries(
              migrateLegacyTagFilters(habit.tagFilters).map((item) => [item.categoryCode, item]),
            )
          : {},
    )
  }

  const persistHabits = (nextHabits: SubsidiaryLedgerHabit[], defaultHabitId?: string) => {
    if (!currentLedgerId) return
    setHabits(nextHabits)
    writeSubsidiaryLedgerPrefs({
      ledgerId: currentLedgerId,
      habits: nextHabits,
      defaultHabitId,
      dimensionColumnMode,
      dimensionDisplayMode,
      detailLayoutMode,
      detailTagCategoryCode,
      columnWidths,
      visibleCategoryCodes,
      savedAt: Date.now(),
    })
  }

  const confirmSaveHabit = () => {
    if (!currentLedgerId) return
    const name = habitNameDraft.trim() || `习惯 ${habits.length + 1}`
    const habit: SubsidiaryLedgerHabit = {
      id: newHabitId(),
      name,
      subtotalMode,
      customDays,
      accountCodeMatch: SUBSIDIARY_ACCOUNT_MATCH,
      periodIds: draftPeriodIds.length ? draftPeriodIds : undefined,
      dateFrom: draftDateRange?.[0]?.format('YYYY-MM-DD'),
      dateTo: draftDateRange?.[1]?.format('YYYY-MM-DD'),
      dimensionColumnMode,
      dimensionDisplayMode,
      detailLayoutMode,
      detailTagCategoryCode,
      columnWidths,
      visibleCategoryCodes,
      selectedAccountCodes: effectiveDraftAccountCodes,
      tagSelections: selectionsToArray(draftTagSelections),
      summary: draftSummary,
      counterparty: draftCounterparty,
      isDefault: saveHabitAsDefault,
    }
    const prefs = readSubsidiaryLedgerPrefs(currentLedgerId) ?? createEmptyPrefs(currentLedgerId)
    const next = upsertHabit(prefs, habit, saveHabitAsDefault)
    persistHabits(next.habits, next.defaultHabitId)
    setSelectedHabitId(habit.id)
    setSaveHabitModalOpen(false)
    message.success(saveHabitAsDefault ? '已保存并设为默认习惯' : '已保存查看习惯')
  }

  const openVoucherDrawer = async (voucherNo: string | null, voucherDate: string | null) => {
    if (!currentLedgerId || !voucherNo) return
    setActiveVoucher({ voucherNo, voucherDate })
    setVoucherDrawerOpen(true)
    setVoucherDrawerLoading(true)
    try {
      const resp = await api.getVoucherLines(currentLedgerId, voucherNo, voucherDate)
      setVoucherLines(resp.items)
    } catch (error) {
      message.error(error instanceof Error ? error.message : '加载凭证详情失败')
      setVoucherLines([])
    } finally {
      setVoucherDrawerLoading(false)
    }
  }

  const handleExport = async () => {
    if (!currentLedgerId || !appliedQuery?.accountCodes.length) {
      message.warning('请先选择科目并查询')
      return
    }
    setExporting(true)
    try {
      const filters = buildApiFilters(appliedQuery, 'subtotal')
      const blob = await api.exportSubsidiaryLedger({
        ledger_id: currentLedgerId,
        account_codes: appliedQuery.accountCodes,
        account_code_match: SUBSIDIARY_ACCOUNT_MATCH,
        period_ids: appliedQuery.periodIds,
        date_from: appliedQuery.dateFrom,
        date_to: appliedQuery.dateTo,
        summary: appliedQuery.summary,
        counterparty: appliedQuery.counterparty,
        tag_filters: filters.tag_filters,
        category_codes: visibleCategories.map((item) => item.code).join(','),
      })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `subsidiary_${appliedQuery.accountCodes.slice(0, 3).join('_')}.xlsx`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)
      message.success('明细账已导出')
    } catch (error) {
      message.error(error instanceof Error ? error.message : '导出失败')
    } finally {
      setExporting(false)
    }
  }

  const visibleColumnDefs = useMemo(() => {
    const defs: Array<{ key: string; label: string }> = [
      { key: 'voucher_date', label: COLUMN_WIDTH_LABELS.voucher_date },
      { key: 'voucher_no', label: COLUMN_WIDTH_LABELS.voucher_no },
      { key: 'summary', label: COLUMN_WIDTH_LABELS.summary },
      { key: 'account_code', label: COLUMN_WIDTH_LABELS.account_code },
      { key: 'account_name', label: COLUMN_WIDTH_LABELS.account_name },
    ]
    if (dimensionDisplayMode === 'compact') {
      defs.push({ key: 'dimensions', label: COLUMN_WIDTH_LABELS.dimensions })
    } else {
      visibleCategories.forEach((category) => {
        defs.push({ key: dimensionColumnKey(category.code), label: category.name })
      })
    }
    defs.push(
      { key: 'debit_amount', label: COLUMN_WIDTH_LABELS.debit_amount },
      { key: 'credit_amount', label: COLUMN_WIDTH_LABELS.credit_amount },
      { key: 'running_balance', label: COLUMN_WIDTH_LABELS.running_balance },
    )
    if (dimensionDisplayMode !== 'compact') {
      defs.push({ key: 'counterparty', label: COLUMN_WIDTH_LABELS.counterparty })
    }
    return defs
  }, [dimensionDisplayMode, visibleCategories])

  const tableScrollX = useMemo(
    () => sumColumnWidths(columnWidths, visibleColumnDefs.map((item) => item.key)),
    [columnWidths, visibleColumnDefs],
  )

  const tableComponents = useMemo(
    () => ({
      header: {
        cell: ResizableTableHeaderCell,
      },
    }),
    [],
  )

  const withResizableWidth = useCallback(
    <T extends SubsidiaryLedgerRow | SubsidiaryTagDetailRow>(
      column: ColumnsType<T>[number],
      key: string,
      fallback?: number,
    ): ColumnsType<T>[number] => {
      const width = resolveColumnWidth(columnWidths, key, fallback)
      return {
        ...column,
        width,
        onHeaderCell: () => ({
          width,
          onResize: (nextWidth: number) => setColumnWidth(key, nextWidth),
        }),
      }
    },
    [columnWidths, setColumnWidth],
  )

  const buildDimensionColumns = (categories: TagCategoryMeta[]): ColumnsType<SubsidiaryLedgerRow> =>
    categories.map((category) => {
      const key = dimensionColumnKey(category.code)
      return withResizableWidth(
        {
          title: category.name,
          key,
          ellipsis: true,
          render: (_: unknown, row) =>
            row.rowType === 'entry' ? tagTextForCategory(entryTagsById[row.id] || [], category.code) : '',
        },
        key,
        DEFAULT_DIMENSION_COLUMN_WIDTH,
      )
    })

  const dimensionColumns: ColumnsType<SubsidiaryLedgerRow> =
    dimensionDisplayMode === 'compact'
      ? [
          withResizableWidth(
            {
              title: '维度标签',
              key: 'dimensions',
              render: (_: unknown, row) =>
                row.rowType === 'entry' ? (
                  <EntryTagsCompactCell
                    tags={entryTagsById[row.id] || []}
                    visibleCategories={visibleCategories}
                  />
                ) : (
                  ''
                ),
            },
            'dimensions',
          ),
        ]
      : buildDimensionColumns(visibleCategories)

  const columns: ColumnsType<SubsidiaryLedgerRow> = [
    withResizableWidth(
      {
        title: '日期',
        key: 'voucher_date',
        fixed: 'left',
        render: (_, row) => (row.rowType === 'entry' ? row.voucher_date || '-' : ''),
      },
      'voucher_date',
    ),
    withResizableWidth(
      {
        title: '凭证字号',
        key: 'voucher_no',
        render: (_, row) =>
          row.rowType === 'entry' && row.voucher_no ? (
            <Button type="link" size="small" style={{ padding: 0 }} onClick={() => openVoucherDrawer(row.voucher_no, row.voucher_date)}>
              {row.voucher_no}
            </Button>
          ) : (
            ''
          ),
      },
      'voucher_no',
    ),
    withResizableWidth(
      {
        title: '摘要',
        key: 'summary',
        ellipsis: true,
        render: (_, row) => {
          if (isOpeningRow(row)) {
            return <Text strong>{row.openingLabel}</Text>
          }
          if (isTagSectionRow(row)) {
            return (
              <Text strong style={{ color: '#722ed1' }}>
                {row.sectionLabel}（{row.entry_count} 条）
              </Text>
            )
          }
          if (row.rowType === 'subtotal') {
            return (
              <Text strong style={{ color: '#1677ff' }}>
                {row.periodLabel}
              </Text>
            )
          }
          return row.summary || '-'
        },
      },
      'summary',
    ),
    withResizableWidth(
      {
        title: '科目编码',
        key: 'account_code',
        render: (_, row) => {
          if (isTagSectionRow(row)) return ''
          return row.rowType === 'entry'
            ? row.account_code || '-'
            : ''
        },
      },
      'account_code',
    ),
    withResizableWidth(
      {
        title: '科目名称',
        key: 'account_name',
        ellipsis: true,
        render: (_, row) => (row.rowType === 'entry' ? row.account_name || '-' : ''),
      },
      'account_name',
    ),
    ...dimensionColumns,
    withResizableWidth(
      {
        title: '借方金额',
        key: 'debit_amount',
        align: 'right',
        render: (_, row) =>
          row.rowType === 'entry' || row.rowType === 'subtotal' ? (
            <Text strong={row.rowType === 'subtotal'}>{formatAmount(row.debit_amount)}</Text>
          ) : (
            ''
          ),
      },
      'debit_amount',
    ),
    withResizableWidth(
      {
        title: '贷方金额',
        key: 'credit_amount',
        align: 'right',
        render: (_, row) =>
          row.rowType === 'entry' || row.rowType === 'subtotal' ? (
            <Text strong={row.rowType === 'subtotal'}>{formatAmount(row.credit_amount)}</Text>
          ) : (
            ''
          ),
      },
      'credit_amount',
    ),
    withResizableWidth(
      {
        title: '方向',
        key: 'balance_direction',
        width: 56,
        align: 'center',
        render: (_, row) => {
          if (!isOpeningRow(row) && row.rowType !== 'entry') return ''
          const value = isOpeningRow(row) ? row.running_balance : row.running_balance ?? 0
          if (!value) return '平'
          return value > 0 ? '借' : '贷'
        },
      },
      'balance_direction',
    ),
    withResizableWidth(
      {
        title: '余额',
        key: 'running_balance',
        align: 'right',
        render: (_, row) => {
          if (isOpeningRow(row) || row.rowType === 'entry') {
            const value = isOpeningRow(row) ? row.running_balance : row.running_balance ?? 0
            return <Text strong={isOpeningRow(row)}>{formatAmount(value)}</Text>
          }
          return ''
        },
      },
      'running_balance',
    ),
    ...(dimensionDisplayMode === 'compact'
      ? []
      : [
          withResizableWidth(
            {
              title: '往来单位',
              key: 'counterparty',
              ellipsis: true,
              render: (_: unknown, row: SubsidiaryLedgerRow) =>
                row.rowType === 'entry' ? row.counterparty || '-' : '',
            },
            'counterparty',
          ),
        ]),
  ]

  const activeTagValues = activeTagCategoryCode
    ? tagValueOptionsByCode[activeTagCategoryCode] || []
    : []

  const activeTagSelectedValues = useMemo(() => {
    if (!activeTagCategoryCode) return []
    const selection = draftTagSelections[activeTagCategoryCode]
    if (!selection) return []
    return selection.selectedValues
  }, [activeTagCategoryCode, draftTagSelections])

  const handleTagMultiChange = (values: string[]) => {
    if (!activeTagCategoryCode) return
    const allKeys = activeTagValues.map(tagValueKey)
    if (!values.length) {
      setDraftTagSelections((prev) => {
        const next = { ...prev }
        delete next[activeTagCategoryCode]
        return next
      })
      return
    }
    const includeAll = allKeys.length > 0 && values.length === allKeys.length
    setDraftTagSelections((prev) => ({
      ...prev,
      [activeTagCategoryCode]: {
        categoryCode: activeTagCategoryCode,
        includeAll,
        selectedValues: values,
      },
    }))
  }

  const appliedAccountLabel = appliedQuery
    ? formatAccountCodesLabel(appliedQuery.accountCodes)
    : formatAccountCodesLabel(effectiveDraftAccountCodes)

  const hasActiveTagFilter = Boolean(
    appliedQuery?.tagSelections.some((item) => item.selectedValues.length > 0),
  )

  const emptyHint =
    total === 0 && appliedQuery?.accountCodes.length
      ? appliedQuery.periodIds?.length || appliedQuery.dateFrom || hasActiveTagFilter
        ? '当前筛选条件下无分录。可尝试点击「清除筛选」去掉期间/维度条件后再查。'
        : '所选科目及下级明细暂无分录，或科目编码与账簿数据不一致。'
      : undefined

  return (
    <div>
      <Title level={3}>明细账</Title>
      <Paragraph type="secondary">
        筛选条件需点击「查询」后生效；表格展示选项（小计、列布局等）修改后会即时刷新，不影响查询范围。
      </Paragraph>

      <Row gutter={16}>
        <Col xs={24} xl={18}>
      <Card title="筛选条件（影响查询结果）" style={{ marginBottom: 16 }}>
        <Row gutter={[16, 16]}>
          <Col xs={24} md={12}>
            <Text type="secondary" style={{ display: 'block', marginBottom: 4 }}>科目（可多选，必填）</Text>
            <Select
              mode="multiple"
              allowClear
              showSearch
              value={draftAccountCodes}
              style={{ width: '100%' }}
              placeholder="选择科目，如 1001、1002"
              options={accountOptions}
              onChange={handleAccountMultiChange}
              optionFilterProp="label"
              maxTagCount="responsive"
            />
          </Col>
          <Col xs={24} md={12}>
            <Text type="secondary" style={{ display: 'block', marginBottom: 4 }}>科目范围（从…到…）</Text>
            <Space.Compact style={{ width: '100%' }}>
              <Select
                allowClear
                showSearch
                style={{ width: '40%' }}
                placeholder="起始科目"
                value={draftAccountRangeFrom}
                options={accountOptions}
                onChange={setDraftAccountRangeFrom}
                optionFilterProp="label"
              />
              <Select
                allowClear
                showSearch
                style={{ width: '40%' }}
                placeholder="结束科目"
                value={draftAccountRangeTo}
                options={accountOptions}
                onChange={setDraftAccountRangeTo}
                optionFilterProp="label"
              />
              <Button style={{ width: '20%' }} onClick={addAccountRange}>
                添加范围
              </Button>
            </Space.Compact>
          </Col>
          <Col xs={24}>
            <Text type="secondary" style={{ display: 'block', marginBottom: 4 }}>
              科目规格（如 1001,1002,1004~1008）
            </Text>
            <Input
              value={draftAccountSpec}
              placeholder="逗号分隔单个科目，~ 表示连续范围"
              onChange={(e) => setDraftAccountSpec(e.target.value)}
            />
            {effectiveDraftAccountCodes.length > 0 && (
              <div style={{ marginTop: 8 }}>
                <Text type="secondary">已选 {effectiveDraftAccountCodes.length} 个科目：</Text>
                <Space wrap size={[4, 4]} style={{ marginTop: 4 }}>
                  {effectiveDraftAccountCodes.map((code) => (
                    <Tag
                      key={code}
                      closable
                      onClose={() => handleAccountMultiChange(draftAccountCodes.filter((item) => item !== code))}
                    >
                      {code}
                    </Tag>
                  ))}
                </Space>
              </div>
            )}
          </Col>
          <Col xs={24} md={8}>
            <Text type="secondary" style={{ display: 'block', marginBottom: 4 }}>科目范围说明</Text>
            <Text>自动含本级及全部下级明细科目（如 1002 含 100201、100202）</Text>
          </Col>
          <Col xs={24} md={8}>
            <Text type="secondary" style={{ display: 'block', marginBottom: 4 }}>会计期间（可选，可多选）</Text>
            <Select
              mode="multiple"
              allowClear
              showSearch
              disabled={Boolean(draftDateRange?.[0] && draftDateRange?.[1])}
              style={{ width: '100%' }}
              placeholder="不限定期间（默认全部）"
              value={draftPeriodIds}
              options={periodOptions}
              onChange={setDraftPeriodIds}
              optionFilterProp="label"
              maxTagCount="responsive"
            />
          </Col>
          <Col xs={24} md={12}>
            <Text type="secondary" style={{ display: 'block', marginBottom: 4 }}>日期范围（可选，与期间二选一）</Text>
            <RangePicker
              style={{ width: '100%' }}
              value={draftDateRange}
              disabled={draftPeriodIds.length > 0}
              onChange={(v) => setDraftDateRange(v as [dayjs.Dayjs, dayjs.Dayjs] | null)}
            />
          </Col>
          <Col xs={24} md={6}>
            <Text type="secondary" style={{ display: 'block', marginBottom: 4 }}>摘要关键字</Text>
            <Input value={draftSummary} placeholder="模糊匹配摘要" onChange={(e) => setDraftSummary(e.target.value)} />
          </Col>
          <Col xs={24} md={6}>
            <Text type="secondary" style={{ display: 'block', marginBottom: 4 }}>往来单位</Text>
            <Input value={draftCounterparty} placeholder="模糊匹配往来单位" onChange={(e) => setDraftCounterparty(e.target.value)} />
          </Col>
          <Col xs={24}>
            <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
              维度 tag 筛选（默认不限定；勾选后纳入查询，已选 tag 之间为 OR，按整凭证匹配，含对方科目行上的 tag）
            </Text>
            <Row gutter={[16, 8]}>
              <Col xs={24} md={8}>
                <Select
                  allowClear
                  showSearch
                  style={{ width: '100%' }}
                  placeholder="不限定维度（默认）"
                  value={activeTagCategoryCode}
                  options={tagCategoryOptions}
                  onChange={(value) => {
                    setActiveTagCategoryCode(value)
                    if (!value) {
                      setDraftTagSelections({})
                      return
                    }
                    void loadTagValuesForCategory(value)
                  }}
                  optionFilterProp="label"
                />
              </Col>
              <Col xs={24} md={16}>
                <Select
                  mode="multiple"
                  allowClear
                  showSearch
                  style={{ width: '100%' }}
                  placeholder="选择要保留的 tag（未选则不限制）"
                  disabled={!activeTagCategoryCode}
                  value={activeTagSelectedValues}
                  options={activeTagValues.map((item) => ({
                    value: tagValueKey(item),
                    label: `${item.display_name || item.tag_value} (${item.count})`,
                  }))}
                  onChange={handleTagMultiChange}
                  optionFilterProp="label"
                  maxTagCount="responsive"
                />
              </Col>
            </Row>
            {Object.entries(draftTagSelections)
              .filter(([, selection]) => !selection.includeAll && selection.selectedValues.length > 0)
              .map(([categoryCode, selection]) => {
                const meta = allCategoryMeta.find((item) => item.code === categoryCode)
                return (
                  <div key={categoryCode} style={{ marginTop: 8 }}>
                    <Text type="secondary">{meta?.name || categoryCode} 已限定：</Text>
                    <Space wrap size={[4, 4]} style={{ marginTop: 4 }}>
                      {selection.selectedValues.map((value) => (
                        <Tag
                          key={`${categoryCode}-${value}`}
                          closable
                          onClose={() =>
                            setDraftTagSelections((prev) =>
                              removeTagFromSelection(
                                prev,
                                categoryCode,
                                value,
                                (tagValueOptionsByCode[categoryCode] || []).map(tagValueKey),
                              ),
                            )
                          }
                        >
                          {value}
                        </Tag>
                      ))}
                    </Space>
                  </div>
                )
              })}
          </Col>
        </Row>
        <Space wrap style={{ marginTop: 16 }}>
          <Button type="primary" icon={<SearchOutlined />} onClick={applySearch}>
            查询
          </Button>
          <Button icon={<ReloadOutlined />} onClick={resetFilters}>
            清除筛选
          </Button>
          <Button icon={<DownloadOutlined />} loading={exporting} disabled={!effectiveDraftAccountCodes.length} onClick={() => void handleExport()}>
            导出 Excel
          </Button>
          <Select
            allowClear
            value={selectedHabitId}
            style={{ width: 200 }}
            placeholder="加载习惯"
            options={habitOptions}
            onChange={(value) => value && applyHabit(value)}
          />
          <Button icon={<SaveOutlined />} onClick={() => { setSaveHabitAsDefault(false); setHabitNameDraft(`习惯 ${habits.length + 1}`); setSaveHabitModalOpen(true) }}>
            保存习惯
          </Button>
          <Button type="primary" icon={<StarOutlined />} onClick={() => { setSaveHabitAsDefault(true); setHabitNameDraft(`习惯 ${habits.length + 1}`); setSaveHabitModalOpen(true) }}>
            保存为默认
          </Button>
        </Space>
      </Card>
        </Col>
        <Col xs={24} xl={6}>
          <SubsidiaryLedgerTagNavigator
            ledgerId={currentLedgerId}
            accountCodes={effectiveDraftAccountCodes}
            accountCodeMatch={SUBSIDIARY_ACCOUNT_MATCH}
            categoryOptions={tagCategoryOptions}
            categoryCode={activeTagCategoryCode}
            tagSelections={draftTagSelections}
            includeVoucherLines
            onCategoryChange={(code) => {
              setActiveTagCategoryCode(code)
              if (!code) {
                setDraftTagSelections({})
                return
              }
              void loadTagValuesForCategory(code)
            }}
            onTagSelectionsChange={setDraftTagSelections}
          />
        </Col>
      </Row>

      <Card title="表格展示（不影响查询结果，改后即时刷新）" style={{ marginBottom: 16 }}>
        <Row gutter={[16, 16]}>
          <Col xs={24} md={6}>
            <Text type="secondary" style={{ display: 'block', marginBottom: 4 }}>明细展示结构</Text>
            <Select
              value={detailLayoutMode}
              style={{ width: '100%' }}
              options={DETAIL_LAYOUT_OPTIONS}
              onChange={setDetailLayoutMode}
            />
          </Col>
          <Col xs={24} md={6}>
            <Text type="secondary" style={{ display: 'block', marginBottom: 4 }}>明细分组维度</Text>
            <Select
              allowClear
              disabled={detailLayoutMode === 'account'}
              value={detailTagCategoryCode}
              style={{ width: '100%' }}
              placeholder={detailLayoutMode === 'account' ? '仅科目汇总时无需选择' : '选择分组维度'}
              options={tagCategoryOptions}
              onChange={setDetailTagCategoryCode}
              optionFilterProp="label"
            />
          </Col>
          <Col xs={24} md={6}>
            <Text type="secondary" style={{ display: 'block', marginBottom: 4 }}>维度列展示方式</Text>
            <Select
              value={dimensionDisplayMode}
              style={{ width: '100%' }}
              options={DIMENSION_DISPLAY_MODE_OPTIONS}
              onChange={setDimensionDisplayMode}
            />
          </Col>
          <Col xs={24} md={6}>
            <Text type="secondary" style={{ display: 'block', marginBottom: 4 }}>维度列范围</Text>
            <Select value={dimensionColumnMode} style={{ width: '100%' }} options={DIMENSION_COLUMN_MODE_OPTIONS} onChange={setDimensionColumnMode} />
          </Col>
          <Col xs={24} md={8}>
            <Text type="secondary" style={{ display: 'block', marginBottom: 4 }}>指定维度列</Text>
            <Select
              mode="multiple"
              allowClear
              disabled={dimensionColumnMode === 'all'}
              value={visibleCategoryCodes}
              style={{ width: '100%' }}
              placeholder={dimensionColumnMode === 'all' ? '当前显示全部维度列' : '选择要显示的维度列'}
              options={tagCategoryOptions}
              onChange={setVisibleCategoryCodes}
              optionFilterProp="label"
              maxTagCount="responsive"
            />
          </Col>
          <Col xs={24} md={4}>
            <Text type="secondary" style={{ display: 'block', marginBottom: 4 }}>小计方式</Text>
            <Select value={subtotalMode} style={{ width: '100%' }} options={SUBTOTAL_OPTIONS} onChange={setSubtotalMode} />
          </Col>
          {subtotalMode === 'custom_days' && (
            <Col xs={24} md={4}>
              <Text type="secondary" style={{ display: 'block', marginBottom: 4 }}>自定义天数</Text>
              <InputNumber min={1} max={365} style={{ width: '100%' }} value={customDays} onChange={(v) => setCustomDays(v ?? 7)} />
            </Col>
          )}
        </Row>
        <Space wrap style={{ marginTop: 12 }}>
          <Button icon={<ColumnWidthOutlined />} onClick={() => setColumnWidthModalOpen(true)}>
            列宽设置
          </Button>
        </Space>
      </Card>
      {!effectiveDraftAccountCodes.length ? (
        <Card title="明细账列表">
          <Empty description="请选择科目后点击「查询」查看明细账" />
        </Card>
      ) : !appliedQuery ? (
        <Card title="明细账列表">
          <Empty description={`已选择 ${appliedAccountLabel}，请点击「查询」加载明细账`} />
        </Card>
      ) : (
        <>
          {emptyHint && <Alert type="info" showIcon message={emptyHint} style={{ marginBottom: 12 }} />}

          {detailLayoutMode !== 'tag' && (
            <Card
              title="科目汇总"
              style={{ marginBottom: detailLayoutMode === 'combined' ? 16 : 0 }}
              extra={
                <Text type="secondary">
                  科目 {appliedAccountLabel} · 方向 {balanceDirection === 'debit' ? '借方' : '贷方'} · 期初 {formatAmount(openingBalance)}
                </Text>
              }
            >
              <Table<SubsidiaryLedgerRow>
                rowKey="rowKey"
                loading={loading}
                dataSource={displayRows}
                columns={columns}
                components={tableComponents}
                size="small"
                pagination={false}
                scroll={{ x: tableScrollX }}
                rowClassName={(row) => {
                  if (isOpeningRow(row)) return 'subsidiary-ledger-opening-row'
                  if (row.rowType === 'subtotal') return 'subsidiary-ledger-subtotal-row'
                  return ''
                }}
              />
              {subtotalMode === 'none' && detailLayoutMode !== 'tag' && (
                <div style={{ marginTop: 16, textAlign: 'right' }}>
                  <Pagination
                    current={page}
                    pageSize={PAGE_SIZE}
                    total={total}
                    showSizeChanger={false}
                    showTotal={(t) => `共 ${t} 条分录`}
                    onChange={setPage}
                  />
                </div>
              )}
            </Card>
          )}

          {detailLayoutMode !== 'account' && detailTagCategoryCode && (
            <Card
              title={`按「${detailCategoryMeta?.name || detailTagCategoryCode}」明细`}
              extra={
                layoutTruncated ? (
                  <Text type="warning">仅展示前 {LAYOUT_FETCH_LIMIT} 条</Text>
                ) : (
                  <Text type="secondary">科目 {appliedAccountLabel} + 维度分组</Text>
                )
              }
            >
              <Table<SubsidiaryTagDetailRow>
                rowKey="rowKey"
                loading={loading}
                dataSource={tagDetailRows}
                columns={columns as ColumnsType<SubsidiaryTagDetailRow>}
                components={tableComponents}
                size="small"
                pagination={false}
                scroll={{ x: tableScrollX }}
                rowClassName={(row) => {
                  if (isTagSectionRow(row)) return 'subsidiary-ledger-tag-section-row'
                  if (row.rowType === 'subtotal') return 'subsidiary-ledger-subtotal-row'
                  return ''
                }}
              />
            </Card>
          )}
        </>
      )}

      <Drawer
        title={activeVoucher ? `凭证 ${activeVoucher.voucherNo}` : '凭证详情'}
        open={voucherDrawerOpen}
        width={720}
        onClose={() => setVoucherDrawerOpen(false)}
        extra={
          activeVoucher?.voucherNo ? (
            <Link to={`/ledger/entries?voucher_no=${encodeURIComponent(activeVoucher.voucherNo)}`}>在凭证查询中打开</Link>
          ) : null
        }
      >
        <Table<AccountingEntry>
          rowKey="id"
          loading={voucherDrawerLoading}
          dataSource={voucherLines}
          size="small"
          pagination={false}
          columns={[
            { title: '行号', dataIndex: 'entry_line_no', width: 60 },
            { title: '科目', dataIndex: 'account_code', width: 90 },
            { title: '摘要', dataIndex: 'summary' },
            { title: '借方', dataIndex: 'debit_amount', width: 100, render: (v: number) => formatAmount(v) },
            { title: '贷方', dataIndex: 'credit_amount', width: 100, render: (v: number) => formatAmount(v) },
          ]}
        />
      </Drawer>

      <Modal
        title="列宽设置"
        open={columnWidthModalOpen}
        onCancel={() => setColumnWidthModalOpen(false)}
        onOk={() => {
          setColumnWidthModalOpen(false)
          message.success('列宽已保存，下次打开将自动应用')
        }}
        okText="完成"
        cancelText="取消"
        width={520}
      >
        <Paragraph type="secondary" style={{ marginBottom: 12 }}>
          可直接拖动表头右侧调整列宽；也可在此精确设置。列宽会随当前账簿自动保存，保存为「查看习惯」时一并记住。
        </Paragraph>
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          {visibleColumnDefs.map((item) => (
            <Row key={item.key} gutter={12} align="middle">
              <Col span={10}>
                <Text>{item.label}</Text>
              </Col>
              <Col span={14}>
                <InputNumber
                  min={60}
                  max={480}
                  step={10}
                  style={{ width: '100%' }}
                  value={resolveColumnWidth(columnWidths, item.key)}
                  onChange={(value) => value != null && setColumnWidth(item.key, value)}
                />
              </Col>
            </Row>
          ))}
          <Button onClick={resetColumnWidths}>恢复默认列宽</Button>
        </Space>
      </Modal>

      <Modal
        title={saveHabitAsDefault ? '保存为默认习惯' : '保存当前习惯'}
        open={saveHabitModalOpen}
        onOk={confirmSaveHabit}
        onCancel={() => setSaveHabitModalOpen(false)}
        okText="保存"
        cancelText="取消"
      >
        <Input value={habitNameDraft} onChange={(e) => setHabitNameDraft(e.target.value)} placeholder="习惯名称" />
      </Modal>

      <style>{`
        .subsidiary-ledger-subtotal-row td { background: #f0f7ff !important; }
        .subsidiary-ledger-opening-row td { background: #fffbe6 !important; font-weight: 600; }
        .subsidiary-ledger-tag-section-row td { background: #f9f0ff !important; font-weight: 600; }
      `}</style>
    </div>
  )
}
