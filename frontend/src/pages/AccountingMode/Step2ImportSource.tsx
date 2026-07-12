import { Card, Upload, Button, Steps, Typography, message, Tag, Space, Modal, Input, List, DatePicker, Alert, Select, Statistic, Radio, Table } from 'antd'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { InboxOutlined, PlusOutlined, RobotOutlined } from '@ant-design/icons'
import dayjs, { type Dayjs } from 'dayjs'
import { api, type AccountingPeriod, type ChartOfAccount, type Counterparty, type DayBookReport, type EntryDraft, type ImportPeriodSuggestion, type ParseDiagnostics, type PeriodMappingMode } from '../../api/client'
import { FlowNav } from '../../components/FlowNav'
import { TraditionalVoucherForm, type VoucherEntryLine } from '../../components/voucher/TraditionalVoucherForm'
import { useAuthStore } from '../../stores/authStore'
import { Money, parseDecimal } from '../../money'
import { DocumentParserService } from '../../services/DocumentParserService'
import { ImportResumeBanner } from '../../components/staging/ImportResumeBanner'
import { persistLedgerImportResume } from '../../utils/importJobContext'

const { Dragger } = Upload
const { Title, Text } = Typography

const todayDateString = () => dayjs().format('YYYY-MM-DD')

function getEarliestPeriodStart(periods: AccountingPeriod[]): string | null {
  if (periods.length === 0) return null
  return [...periods].sort((a, b) => dayjs(a.start_date).valueOf() - dayjs(b.start_date).valueOf())[0].start_date
}

function resolveAdaptivePeriodRange(
  adaptiveStartDate: string,
  adaptiveEndDate: string,
  earliestPeriodStart: string | null,
): { startDate: string; endDate: string } {
  return {
    startDate: adaptiveStartDate || earliestPeriodStart || '',
    endDate: adaptiveEndDate || todayDateString(),
  }
}

// 预定义原始资料类型
const SOURCE_DOCUMENT_TYPES = [
  { type: 'invoice', label: '发票', icon: '🧾', description: '增值税发票、普通发票等' },
  { type: 'bank_statement', label: '银行流水', icon: '🏦', description: '银行对账单、回单等' },
  { type: 'contract', label: '合同协议', icon: '📄', description: '采购合同、销售合同等' },
  { type: 'inventory', label: '入库单', icon: '📦', description: '入库单、出库单、领料单' },
  { type: 'receipt', label: '收据凭证', icon: '🧾', description: '收据、报销单等' },
  { type: 'payroll', label: '工资表', icon: '💰', description: '工资表、社保缴纳明细' },
  { type: 'expense', label: '费用单据', icon: '📝', description: '差旅费、业务招待费等' },
  { type: 'other', label: '其他凭证', icon: '📋', description: '自定义原始凭证类型' },
]

import {
  resolveStructuredKind,
  type StructuredKind,
} from '../../constants/structuredImportKinds'
import {
  DEFAULT_STRUCTURED_PARSE_OPTIONS,
  StructuredParseCompatibilityPanel,
  type FormatDetectionResult,
} from '../../components/StructuredParseCompatibilityPanel'
import type { StructuredParseOptions } from '../../constants/structuredParseOptions'

const STRUCTURED_KIND_META: Record<
  StructuredKind,
  { label: string; hint: string; uploadTitle: string; columnHint: string }
> = {
  day_book: {
    label: '序时簿 / 日记账',
    hint: '按凭证号、日期排列的分录流水',
    uploadTitle: '序时簿 / 日记账文件',
    columnHint: '请保留凭证号、日期、科目、借贷金额、对方单位等列。系统会按凭证号合并、校验借贷平衡并检测跳号。',
  },
  standard_entries: {
    label: '标准格式分录文件',
    hint: '凭证号、科目、借贷金额等标准列',
    uploadTitle: '标准分录文件',
    columnHint: '请保留凭证号、分录行号、摘要、科目编码/名称、借方金额、贷方金额等标准列。结构化自适应导入引擎识别表头并校验分录。',
  },
  trial_balance: {
    label: '科目余额表',
    hint: '期初、本期发生、期末余额',
    uploadTitle: '科目余额表',
    columnHint: '请保留科目编码、科目名称、期初余额、本期借方、本期贷方、期末余额等列。结构化自适应导入引擎识别表头并校验勾稽关系。',
  },
  subsidiary_ledger: {
    label: '明细账',
    hint: '按科目展开的分录明细',
    uploadTitle: '明细账文件',
    columnHint: '请保留科目、凭证号、日期、摘要、借方、贷方等列。结构化自适应导入引擎按科目归集并生成分录。',
  },
  financial_reports: {
    label: '标准财务报表',
    hint: '资产负债表、利润表等导出表',
    uploadTitle: '财务报表导出文件',
    columnHint: '支持财务软件导出的资产负债表、利润表等 Excel/CSV。结构化自适应导入引擎识别报表结构并提取勾稽线索。',
  },
}

const VOUCHER_TYPE_OPTIONS = ['记', '银', '收', '付', '转', '工'].map(value => ({ value, label: value }))
const CURRENT_ACCOUNT_CODES = ['1122', '2203', '2202', '1123', '1221', '2241']
const CURRENT_ACCOUNT_NAMES = ['应收', '预收', '应付', '预付', '其他应收', '其他应付']

// 上传的文件信息
interface UploadedFile {
  name: string
  size: number
  fileType: string
  jobId?: number
  fileId?: number
  registerSummary?: string
  moduleRegistrations?: Array<{
    module_key: string
    module_label: string
    module_path: string
    register_count: number
    accounting_dimension?: string | null
    semantic_only?: boolean
    reason?: string
  }>
  semanticTags?: string[]
  riskHints?: Array<{ risk_type: string; severity: string; description: string }>
  decompositionSource?: string
  archivePath?: string
  archiveCategory?: string
  projectName?: string
}

interface ManualEntryLine extends VoucherEntryLine {}

const createManualLine = (lineNo: number): ManualEntryLine => ({
  key: `${Date.now()}-${lineNo}`,
  entry_line_no: lineNo,
  summary: '',
  account_code: '',
  account_name: '',
  debit_amount: 0,
  credit_amount: 0,
  counterparty: '',
  account_source: 'manual',
})

const getNextNaturalMonthPeriod = (closedPeriods: AccountingPeriod[]) => {
  if (closedPeriods.length === 0) return null
  const latestClosed = [...closedPeriods].sort((a, b) => dayjs(b.end_date).valueOf() - dayjs(a.end_date).valueOf())[0]
  const startDate = dayjs(latestClosed.end_date).add(1, 'day').startOf('month')
  const endDate = startDate.endOf('month')
  return {
    period_code: startDate.format('YYYY-MM'),
    start_date: startDate.format('YYYY-MM-DD'),
    end_date: endDate.format('YYYY-MM-DD'),
  }
}

const isDateInPeriod = (date: string, start: string, end: string) => {
  if (!date || !start || !end) return true
  const voucherDate = dayjs(date)
  return !voucherDate.isBefore(dayjs(start), 'day') && !voucherDate.isAfter(dayjs(end), 'day')
}

const isCurrentAccount = (row: ManualEntryLine) => {
  const accountCode = row.account_code.trim()
  const accountName = row.account_name.trim()
  return CURRENT_ACCOUNT_CODES.some(code => accountCode === code || accountCode.startsWith(`${code}.`))
    || CURRENT_ACCOUNT_NAMES.some(name => accountName.includes(name))
}

const getCounterpartyHintStatus = (row: ManualEntryLine) => {
  if (!isCurrentAccount(row)) return 'not_required'
  return row.counterparty.trim() ? 'provided' : 'required_missing'
}

const renderParseGuidance = (
  diagnostics: ParseDiagnostics | null,
  options?: { onSwitchDayBook?: () => void },
) => {
  if (!diagnostics) return null
  return (
    <Alert
      title="未能识别有效分录列，请检查表头分列"
      description={(
        <Space direction="vertical" style={{ width: '100%' }}>
          {diagnostics.guidance && <Text>{diagnostics.guidance}</Text>}
          {diagnostics.template_name && (
            <Text type="secondary">识别模板：{diagnostics.template_name}</Text>
          )}
          {diagnostics.engine && (
            <Text type="secondary">解析引擎：{diagnostics.engine}</Text>
          )}
          {diagnostics.matched_fields && Object.keys(diagnostics.matched_fields).length > 0 && (
            <Text type="secondary">
              已匹配列：{Object.entries(diagnostics.matched_fields).map(([field, header]) => `${field}→${header}`).join('；')}
            </Text>
          )}
          {diagnostics.unmatched_headers && diagnostics.unmatched_headers.length > 0 && (
            <Text type="warning">未识别表头：{diagnostics.unmatched_headers.join('、')}</Text>
          )}
          {diagnostics.expected_columns && (
            <Text type="secondary">建议表头包含：{diagnostics.expected_columns.join('、')}</Text>
          )}
          {options?.onSwitchDayBook && (
            <Button type="primary" onClick={options.onSwitchDayBook}>
              切换到「序时簿导入」模式
            </Button>
          )}
        </Space>
      )}
      type="error"
      showIcon
      style={{ marginTop: '16px' }}
    />
  )
}

type PeriodSelectionMode = 'adaptive' | 'fixed'

const parsePeriodMappingMode = (value: string | null): PeriodMappingMode | null => {
  if (value === 'preserve_source' || value === 'unify_target') return value
  return null
}

const getCurrentCalendarMonthPeriod = () => {
  const start = dayjs().startOf('month')
  const end = dayjs().endOf('month')
  return {
    period_code: start.format('YYYY-MM'),
    start_date: start.format('YYYY-MM-DD'),
    end_date: end.format('YYYY-MM-DD'),
  }
}

export function Step2AccountingImportSource() {
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams, setSearchParams] = useSearchParams()
  const { currentLedgerId, user, authContext } = useAuthStore()
  const currentProjectId = useMemo(() => {
    if (!authContext?.projects?.length || !currentLedgerId) return null
    const currentLedger = authContext.projects.find((p) => p.id === currentLedgerId)
    const teamId = currentLedger?.team_id
    const matched = authContext.projects.find(
      (p) => (teamId ? p.team_id === teamId : true) && p.status === 'active'
    )
    return matched?.id ?? authContext.projects[0]?.id ?? null
  }, [authContext, currentLedgerId])
  const inputMode = searchParams.get('inputMode') || 'ai_generated'
  const structuredKindParam = searchParams.get('structuredKind')
  const structuredKind = resolveStructuredKind(structuredKindParam, 'accounting')
  const structuredMeta = STRUCTURED_KIND_META[structuredKind]
  const isManualEntry = inputMode === 'manual_entry'
  const isAiGenerated = inputMode === 'ai_generated'
  const isDayBookImport = inputMode === 'day_book_import'
  const needsPeriodPicker = isManualEntry || isAiGenerated || isDayBookImport
  const stepPath = (step: number) => location.pathname.startsWith('/ledger/vouchers/step/') ? `/ledger/vouchers/step/${step}` : `/accounting/step/${step}`
  const buildStepQuery = (extra?: Record<string, string>) => {
    const params = new URLSearchParams({ inputMode, ...(extra || {}) })
    if (isDayBookImport) {
      params.set('structuredKind', structuredKind)
    }
    if (periodMappingMode) {
      params.set('periodMappingMode', periodMappingMode)
    }
    return params.toString()
  }
  const currentStep = 1
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([])
  const [selectedTypes, setSelectedTypes] = useState<string[]>([])
  const [customTypeModalVisible, setCustomTypeModalVisible] = useState(false)
  const [customTypeInput, setCustomTypeInput] = useState('')
  const [customTypes, setCustomTypes] = useState<{ type: string; label: string; description: string }[]>([])
  const initialJobId = Number(searchParams.get('jobId') || 0)
  const initialPeriodId = Number(searchParams.get('periodId') || 0)
  const [currentJobId, setCurrentJobId] = useState<number | null>(initialJobId || null)
  const [currentOrgId, setCurrentOrgId] = useState<number | null>(null)
  const [periodId, setPeriodId] = useState<number | null>(initialPeriodId || null)
  const [periodCode, setPeriodCode] = useState<string>('')
  const [periodStart, setPeriodStart] = useState<string>('')
  const [periodEnd, setPeriodEnd] = useState<string>('')
  const [accountingPeriods, setAccountingPeriods] = useState<AccountingPeriod[]>([])
  const [periodsLoading, setPeriodsLoading] = useState(false)
  const [periodSuggestion, setPeriodSuggestion] = useState('')
  const [periodMode, setPeriodMode] = useState<PeriodSelectionMode>(searchParams.get('periodMode') === 'fixed' ? 'fixed' : 'adaptive')
  const [periodMappingMode, setPeriodMappingMode] = useState<PeriodMappingMode>(
    () => parsePeriodMappingMode(searchParams.get('periodMappingMode')) ?? 'unify_target',
  )
  const [adaptiveStartDate, setAdaptiveStartDate] = useState<string>(() => searchParams.get('adaptiveStartDate') || '')
  const [adaptiveEndDate, setAdaptiveEndDate] = useState<string>(() => searchParams.get('adaptiveEndDate') || '')
  const [chartOfAccounts, setChartOfAccounts] = useState<ChartOfAccount[]>([])
  const [coaLoading, setCoaLoading] = useState(false)
  const [counterparties, setCounterparties] = useState<Counterparty[]>([])
  const [counterpartiesLoading, setCounterpartiesLoading] = useState(false)
  const [accountSearchKeyword, setAccountSearchKeyword] = useState('')
  const [usedCustomAccountEntry, setUsedCustomAccountEntry] = useState(false)
  const [manualVoucherDate, setManualVoucherDate] = useState<string>('')
  const [manualVoucherType, setManualVoucherType] = useState<string>('记')
  const [manualVoucherNumber, setManualVoucherNumber] = useState<string>('001')
  const [manualRows, setManualRows] = useState<ManualEntryLine[]>([
    createManualLine(1),
    createManualLine(2),
    createManualLine(3),
    createManualLine(4),
    createManualLine(5),
  ])
  const [manualSubmitting, setManualSubmitting] = useState(false)
  const [manualAttachmentCount, setManualAttachmentCount] = useState(0)
  const [manualRemark, setManualRemark] = useState('')
  const [manualQuickEntry, setManualQuickEntry] = useState(false)
  const [dayBookReport, setDayBookReport] = useState<DayBookReport | null>(null)
  const [importPeriodSuggestion, setImportPeriodSuggestion] = useState<ImportPeriodSuggestion | null>(null)
  const [importPeriodReason, setImportPeriodReason] = useState('')
  const [outputPath, setOutputPath] = useState<string>('')
  const [processingUpload, setProcessingUpload] = useState(false)
  const [entryCount, setEntryCount] = useState(0)
  const [parseGuidance, setParseGuidance] = useState<ParseDiagnostics | null>(null)
  const [parseOptions, setParseOptions] = useState<StructuredParseOptions>(DEFAULT_STRUCTURED_PARSE_OPTIONS)
  const [formatDetecting, setFormatDetecting] = useState(false)
  const [formatDetection, setFormatDetection] = useState<FormatDetectionResult | null>(null)
  const [structuredPreviewCount, setStructuredPreviewCount] = useState(0)
  const [periodMappingApplying, setPeriodMappingApplying] = useState(false)

  const documentParserService = useMemo(
    () => new DocumentParserService({
      messageKey: 'step2-parser',
      navigateToDraftOnError: true,
      navigate,
      onSuccess: (result) => {
        setCurrentJobId(result.jobId)
        setOutputPath(result.outputPath)
        setEntryCount(0)
        setStructuredPreviewCount(0)
        setParseGuidance(null)
        syncQueryToUrl({ jobId: result.jobId })
      },
    }),
    [navigate],
  )

  const manualVoucherNo = `${manualVoucherType}-${manualVoucherNumber}`
  const activeManualRows = useMemo(() => manualRows.filter(row =>
    row.summary.trim()
    || row.account_code.trim()
    || row.account_name.trim()
    || parseDecimal(row.debit_amount || 0).gt(0)
    || parseDecimal(row.credit_amount || 0).gt(0)
    || row.counterparty.trim()
  ), [manualRows])
  const debitTotal = Money.sum(activeManualRows.map(row => Money.cny(row.debit_amount)))
  const creditTotal = Money.sum(activeManualRows.map(row => Money.cny(row.credit_amount)))
  const balanceDiff = debitTotal.sub(creditTotal)
  const isBalanced = debitTotal.isPositive() && creditTotal.isPositive() && balanceDiff.isZero()
  const activeChartOfAccounts = useMemo(
    () => chartOfAccounts.filter(account => account.status === 'active'),
    [chartOfAccounts]
  )

  const syncQueryToUrl = (updates: {
    jobId?: number | null
    periodId?: number | null
    periodMode?: PeriodSelectionMode
    periodMappingMode?: PeriodMappingMode
    adaptiveStartDate?: string
    adaptiveEndDate?: string
  }) => {
    const next = new URLSearchParams(searchParams)
    next.set('inputMode', inputMode)
    if (isDayBookImport) {
      next.set('structuredKind', structuredKind)
    }
    const mode = updates.periodMode ?? periodMode
    next.set('periodMode', mode)
    const mappingMode = updates.periodMappingMode !== undefined ? updates.periodMappingMode : periodMappingMode
    if (mappingMode) {
      next.set('periodMappingMode', mappingMode)
    } else {
      next.delete('periodMappingMode')
    }
    if (updates.jobId !== undefined && updates.jobId) {
      next.set('jobId', String(updates.jobId))
    }
    if (mode === 'adaptive') {
      const earliest = getEarliestPeriodStart(accountingPeriods)
      const start = updates.adaptiveStartDate ?? adaptiveStartDate ?? earliest ?? ''
      const end = updates.adaptiveEndDate ?? adaptiveEndDate ?? todayDateString()
      if (start) next.set('adaptiveStartDate', start)
      if (end) next.set('adaptiveEndDate', end)
      next.delete('periodId')
    } else if (updates.periodId !== undefined && updates.periodId) {
      next.set('periodId', String(updates.periodId))
    }
    setSearchParams(next, { replace: true })
  }

  const applyAdaptiveDefaults = (periods: AccountingPeriod[]) => {
    const earliest = getEarliestPeriodStart(periods)
    if (!adaptiveStartDate && earliest) {
      setAdaptiveStartDate(earliest)
    }
    if (!adaptiveEndDate) {
      setAdaptiveEndDate(todayDateString())
    }
  }

  const applySelectedPeriod = (period: AccountingPeriod) => {
    setPeriodId(period.id)
    setPeriodCode(period.period_code)
    setPeriodStart(period.start_date)
    setPeriodEnd(period.end_date)
    setManualVoucherDate(prev => isDateInPeriod(prev, period.start_date, period.end_date) ? prev : period.start_date)
  }

  const applyCurrentMonthPeriodDefault = (periods: AccountingPeriod[]) => {
    const current = getCurrentCalendarMonthPeriod()
    setPeriodMode('fixed')
    const matchedOpen = periods.find(
      period => period.period_code === current.period_code && ['open', 'reopened'].includes(period.status),
    )
    if (matchedOpen) {
      applySelectedPeriod(matchedOpen)
      setPeriodSuggestion('')
      syncQueryToUrl({ periodId: matchedOpen.id, periodMode: 'fixed' })
      return
    }
    setPeriodId(null)
    setPeriodCode(current.period_code)
    setPeriodStart(current.start_date)
    setPeriodEnd(current.end_date)
    setPeriodSuggestion('当前月份尚无 open/reopened 期间，提交时将自动创建本周期。')
  }

  const applyDefaultPeriodSelection = (periods: AccountingPeriod[]) => {
    if (isDayBookImport) {
      if (periodMappingMode === 'unify_target') {
        applyCurrentMonthPeriodDefault(periods)
      }
      return
    }
    if (periodMode === 'adaptive' && !isManualEntry) {
      applyAdaptiveDefaults(periods)
      return
    }

    const selectedPeriod = initialPeriodId
      ? periods.find(period => period.id === initialPeriodId)
      : periods.find(period => ['open', 'reopened'].includes(period.status))

    if (selectedPeriod) {
      applySelectedPeriod(selectedPeriod)
      setPeriodSuggestion('')
      syncQueryToUrl({ periodId: selectedPeriod.id })
      return
    }

    const nextPeriod = getNextNaturalMonthPeriod(periods.filter(period => period.status === 'closed'))
    if (nextPeriod) {
      setPeriodId(null)
      setPeriodCode(nextPeriod.period_code)
      setPeriodStart(nextPeriod.start_date)
      setPeriodEnd(nextPeriod.end_date)
      setManualVoucherDate(nextPeriod.start_date)
      setPeriodSuggestion(`当前没有 open/reopened 期间。系统已按上一已结账期间建议下一自然月 ${nextPeriod.period_code}，提交时会先创建该期间。`)
    }
  }

  useEffect(() => {
    if (!needsPeriodPicker) return

    const loadStep2BaseData = async () => {
      setPeriodsLoading(true)
      if (isManualEntry) {
        setCoaLoading(true)
        setCounterpartiesLoading(true)
      }
      try {
        if (isManualEntry) {
          const [periods, accounts, loadedCounterparties] = await Promise.all([
            api.listAccountingPeriods(undefined, currentLedgerId || undefined),
            api.listChartOfAccounts(),
            api.listCounterparties(),
          ])
          setAccountingPeriods(periods)
          setChartOfAccounts(accounts)
          setCounterparties(loadedCounterparties)
          applyDefaultPeriodSelection(periods)
        } else {
          const periods = await api.listAccountingPeriods(undefined, currentLedgerId || undefined)
          setAccountingPeriods(periods)
          applyDefaultPeriodSelection(periods)
        }
      } catch (error) {
        const detail = error instanceof Error ? error.message : String(error)
        message.error(`加载会计期间失败：${detail}`)
      } finally {
        setPeriodsLoading(false)
        if (isManualEntry) {
          setCoaLoading(false)
          setCounterpartiesLoading(false)
        }
      }
    }

    void loadStep2BaseData()
  }, [needsPeriodPicker, isManualEntry, initialPeriodId, currentLedgerId])

  useEffect(() => {
    if (!isDayBookImport || !currentJobId) return
    void (async () => {
      try {
        const [report, suggestion] = await Promise.all([
          api.getDayBookReport(currentJobId),
          api.getImportPeriodSuggestion(currentJobId),
        ])
        setDayBookReport(report)
        setImportPeriodSuggestion(suggestion)
        setImportPeriodReason(suggestion.reason)
      } catch {
        // 任务尚未完成导入时忽略
      }
    })()
  }, [isDayBookImport, currentJobId])

  useEffect(() => {
    if (!isDayBookImport || !currentJobId || !currentLedgerId) return
    persistLedgerImportResume({
      ledgerId: currentLedgerId,
      jobId: currentJobId,
      step: 2,
      inputMode: 'day_book_import',
      structuredKind,
      periodMappingMode,
    })
  }, [isDayBookImport, currentJobId, currentLedgerId, structuredKind, periodMappingMode])

  const handleResumeImportJob = (jobId: number) => {
    setCurrentJobId(jobId)
    syncQueryToUrl({ jobId })
    void api.getImportJob(jobId).then((job) => {
      setEntryCount(job.entry_count)
    }).catch(() => undefined)
  }

  const applyPeriodSuggestion = (suggestion: ImportPeriodSuggestion | null) => {
    if (!suggestion) return
    setImportPeriodReason(suggestion.reason)
    const suggestedStart = suggestion.matched_period?.start_date || suggestion.suggested_period?.start_date
    const suggestedEnd = suggestion.matched_period?.end_date || suggestion.suggested_period?.end_date
    if (suggestedStart && !adaptiveStartDate) {
      setAdaptiveStartDate(suggestedStart)
    }
    if (!adaptiveEndDate) {
      setAdaptiveEndDate(todayDateString())
    }
    if (suggestion.matched_period) {
      setPeriodId(suggestion.matched_period.id)
      setPeriodCode(suggestion.matched_period.period_code)
      setPeriodStart(suggestion.matched_period.start_date)
      setPeriodEnd(suggestion.matched_period.end_date)
      return
    }
    if (suggestion.suggested_period) {
      setPeriodId(null)
      setPeriodCode(suggestion.suggested_period.period_code)
      setPeriodStart(suggestion.suggested_period.start_date)
      setPeriodEnd(suggestedEnd || suggestion.suggested_period.end_date)
    }
  }

  const handlePreDetectFormat = async (file: File) => {
    setFormatDetecting(true)
    try {
      const detected = await api.detectImportFormat(file, parseOptions)
      setFormatDetection({
        charset: detected.charset,
        delimiter_label: detected.delimiter_label,
        detected_headers: detected.detected_headers || [],
        estimated_data_rows: detected.estimated_data_rows || 0,
        parseable: detected.parseable ?? false,
        hints: detected.hints || [],
        company_name: detected.company_name,
        report_period: detected.report_period,
      })
      message.success('预检测完成，请确认字符集与表头识别结果')
    } catch (error) {
      message.error(error instanceof Error ? error.message : '文件预检测失败')
    } finally {
      setFormatDetecting(false)
    }
  }

  const handleDayBookUpload = async (file: File) => {
    setProcessingUpload(true)
    setParseGuidance(null)
    try {
      if (currentLedgerId) {
        try {
          const readiness = await api.getLedgerDimensionReadiness(currentLedgerId)
          if (!readiness.ready_for_structured_import) {
            const blocker = readiness.blockers?.[0]
            Modal.confirm({
              title: '请先审阅本账簿维度规则',
              content:
                blocker?.message
                || '不同公司/行业的维度叫法不同。请先在「账簿维度管理」确认解析映射与维度分类，再导入序时簿。',
              okText: '前往维度中心',
              cancelText: '取消',
              onOk: () => {
                const dimParams = new URLSearchParams({
                  tab: blocker?.action_tab || 'parse-mapping',
                })
                if (currentJobId) dimParams.set('jobId', String(currentJobId))
                navigate(`/ledger/dimensions?${dimParams.toString()}`)
              },
            })
            return
          }
        } catch {
          message.warning('无法检查维度就绪状态，将继续尝试导入')
        }
      }

      try {
        const detected = await api.detectImportFormat(file, parseOptions)
        setFormatDetection({
          charset: detected.charset,
          delimiter_label: detected.delimiter_label,
          detected_headers: detected.detected_headers || [],
          estimated_data_rows: detected.estimated_data_rows || 0,
          parseable: detected.parseable ?? false,
          hints: detected.hints || [],
          company_name: detected.company_name,
          report_period: detected.report_period,
        })
      } catch {
        setFormatDetection(null)
      }

      let jobId = currentJobId
      if (!jobId) {
        const job = await api.createImportJob('临时组织', 'ledger_day_book', currentLedgerId, {
        audit_scope_type: 'all',
        audit_period_id: null,
        audit_account_codes: null,
        project_id: currentProjectId,
      })
      jobId = job.id
      setCurrentJobId(jobId)
      setCurrentOrgId(job.organization_id)
      }

      await api.updateImportJobParseOptions(jobId, parseOptions)

      await api.uploadFile(jobId, file)
      setUploadedFiles(prev => [...prev, { name: file.name, size: file.size, fileType: file.type || 'unknown', jobId }])

      message.loading({
        content: `正在规则预识别并解析${structuredMeta.label}，生成会计分录...`,
        key: 'daybook-parse',
      })
      const result = await api.processImportJobSync(jobId)
      const reportSummary = result.report as {
        output_path?: string
        total_entries?: number
        failed_files?: number
        error_message?: string
        period_suggestion?: ImportPeriodSuggestion
        day_book_report?: DayBookReport
        parse_diagnostics?: ParseDiagnostics
        file_results?: Array<{ error_message?: string; error?: string; parse_diagnostics?: ParseDiagnostics }>
        file_summary?: Array<{ error?: string; error_message?: string; parse_diagnostics?: ParseDiagnostics }>
      }

      const fileResults = reportSummary.file_results || reportSummary.file_summary || []
      const diagnostics = reportSummary.parse_diagnostics
        || fileResults.find((item) => item.parse_diagnostics)?.parse_diagnostics
        || null
      const totalEntries = reportSummary.total_entries || 0
      const isPreview = result.job.status === 'preview'
      const failed = (reportSummary.failed_files ?? 0) > 0
        || result.job.status === 'failed'
        || (totalEntries === 0 && !isPreview && !reportSummary.error_message)

      setOutputPath(reportSummary.output_path || 'direct_entries')
      setEntryCount(totalEntries)

      if (failed) {
        setParseGuidance(diagnostics)
        setDayBookReport(null)
        const detail = reportSummary.error_message
          || fileResults.find((item) => item.error_message)?.error_message
          || fileResults.find((item) => item.error)?.error
          || '未解析到有效分录，请检查表头列名'
        message.error({ content: `序时簿解析失败：${detail}`, key: 'daybook-parse' })
        return
      }

      if (reportSummary.period_suggestion) {
        setImportPeriodSuggestion(reportSummary.period_suggestion)
        setImportPeriodReason(reportSummary.period_suggestion.reason)
      }
      if (reportSummary.day_book_report) {
        setDayBookReport(reportSummary.day_book_report)
      } else {
        const report = await api.getDayBookReport(jobId)
        setDayBookReport(report)
      }

      message.success({
        content: `${structuredMeta.label}解析完成，已生成 ${totalEntries} 条草稿分录，请进入复核确认`,
        key: 'daybook-parse',
      })
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error)
      message.error({ content: `序时簿导入失败：${detail}`, key: 'daybook-parse' })
    } finally {
      setProcessingUpload(false)
    }
    return false
  }

  const handleUpload = async (file: File) => {
    // 原始资料：资料解析中心 · 场景 B（识别与台账登记），生成草稿而非直接入账。
    // 后续需人工复核确认，符合 AI 不绕过人工复核的原则。
    const result = await documentParserService.parseDocument(file, {
      jobId: currentJobId,
      ledgerId: currentLedgerId,
      projectId: currentProjectId,
      sourceType: 'ai_generated',
      documentTypeHints: selectedTypes,
    })

    if (result.jobId) {
      setCurrentJobId(result.jobId)
      setCurrentOrgId(null)
      syncQueryToUrl({ jobId: result.jobId })
    }

    // 将解析结果合并到已上传文件列表中展示
    for (const summary of result.parsedFiles) {
      const fileInfo: UploadedFile = {
        name: summary.fileName,
        size: file.size,
        fileType: file.type || 'unknown',
        jobId: result.jobId,
        fileId: summary.fileId,
        registerSummary: summary.registerSummary || undefined,
        semanticTags: summary.semanticTags,
        riskHints: summary.riskHints,
        archivePath: summary.archivePath || undefined,
        archiveCategory: summary.archiveCategory || undefined,
        projectName: summary.projectName || undefined,
      }
      setUploadedFiles(prev => [...prev, fileInfo])
    }

    return false // 阻止默认上传行为
  }

  const handleAddCustomType = () => {
    if (customTypeInput.trim()) {
      const newType = {
        type: `custom_${Date.now()}`,
        label: customTypeInput.trim(),
        description: '用户自定义原始凭证类型',
      }
      setCustomTypes(prev => [...prev, newType])
      setSelectedTypes(prev => [...prev, newType.type])
      setCustomTypeInput('')
      setCustomTypeModalVisible(false)
      message.success(`已添加自定义类型：${newType.label}`)
    }
  }

  const toggleType = (type: string) => {
    setSelectedTypes(prev =>
      prev.includes(type)
        ? prev.filter(t => t !== type)
        : [...prev, type]
    )
  }

  const ensurePeriod = async (sourceType: 'ai_generated' | 'manual_entry') => {
    let jobId = currentJobId
    let orgId = currentOrgId
    if (!jobId) {
      const job = await api.createImportJob('账簿导入', sourceType, currentLedgerId, {
        audit_scope_type: 'all',
        audit_period_id: null,
        audit_account_codes: null,
        project_id: currentProjectId,
      })
      jobId = job.id
      orgId = job.organization_id
      setCurrentJobId(jobId)
      setCurrentOrgId(orgId)
    }

    let usePeriodId = periodId
    if (!usePeriodId) {
      if (!orgId || !periodCode || !periodStart || !periodEnd) {
        throw new Error('请先选择可用会计期间；如没有可用期间，请填写期间编码、开始日期和结束日期后创建')
      }
      const period = await api.createAccountingPeriod({
        organization_id: orgId,
        ledger_id: currentLedgerId || undefined,
        period_code: periodCode,
        start_date: periodStart,
        end_date: periodEnd,
      })
      usePeriodId = period.id
      setPeriodId(usePeriodId)
    }

    return { jobId, periodId: usePeriodId }
  }

  const handleNext = async () => {
    if (isDayBookImport) {
      if (!currentJobId) {
        message.warning('请先上传结构化文件并完成解析')
        return
      }
      setPeriodMappingApplying(true)
      try {
        let navigateParams: Record<string, string> = {
          jobId: String(currentJobId),
          periodMappingMode,
        }

        if (periodMappingMode === 'preserve_source') {
          const result = await api.applyImportPeriodMapping(currentJobId, {
            period_mapping_mode: 'preserve_source',
          })
          message.success(
            `已按凭证日期分配 ${result.assigned_voucher_count} 张凭证到 ${result.used_period_codes.length} 个期间`
            + (result.created_period_codes.length > 0 ? `（新建 ${result.created_period_codes.join('、')}）` : ''),
          )
        } else {
          let usePeriodId = periodId
          if (!usePeriodId) {
            if (!currentOrgId || !periodCode || !periodStart || !periodEnd) {
              message.warning('请从下拉列表选择 open/reopened 会计期间，或确认本周期起止日期后创建')
              return
            }
            const period = await api.createAccountingPeriod({
              organization_id: currentOrgId,
              ledger_id: currentLedgerId || undefined,
              period_code: periodCode,
              start_date: periodStart,
              end_date: periodEnd,
            })
            usePeriodId = period.id
            setPeriodId(usePeriodId)
          }
          const result = await api.applyImportPeriodMapping(currentJobId, {
            period_mapping_mode: 'unify_target',
            period_mode: 'fixed',
            period_id: usePeriodId,
          })
          message.success(`已将 ${result.assigned_voucher_count} 张凭证归入期间 ${result.used_period_codes.join('、') || periodCode}`)
          navigateParams = {
            ...navigateParams,
            periodMode: 'fixed',
            periodId: String(usePeriodId),
          }
        }

        syncQueryToUrl({
          jobId: currentJobId,
          periodMappingMode,
          periodMode: navigateParams.periodMode as PeriodSelectionMode | undefined,
          periodId: navigateParams.periodId ? Number(navigateParams.periodId) : null,
        })
        const step4Params = new URLSearchParams(buildStepQuery(navigateParams))
        step4Params.set('reviewPhase', 'dimensions')
        navigate(`${stepPath(4)}?${step4Params.toString()}`)
      } catch (error) {
        const detail = error instanceof Error ? error.message : String(error)
        message.error(`期间映射失败：${detail}`)
      } finally {
        setPeriodMappingApplying(false)
      }
      return
    }

    if (uploadedFiles.length === 0) {
      message.warning('请先上传文件')
      return
    }
    if (!currentJobId) {
      message.warning('导入任务未创建')
      return
    }

    if (periodMode === 'adaptive') {
      const { startDate, endDate } = resolveAdaptivePeriodRange(
        adaptiveStartDate,
        adaptiveEndDate,
        earliestPeriodStart,
      )
      if (!startDate) {
        message.warning('无法确定自适应期间开始日期，请检查账簿会计期间设置')
        return
      }
      if (dayjs(endDate).isBefore(dayjs(startDate), 'day')) {
        message.warning('结束日期不能早于开始日期')
        return
      }
      setAdaptiveStartDate(startDate)
      setAdaptiveEndDate(endDate)
      const nextParams = new URLSearchParams()
      nextParams.set('inputMode', inputMode)
      nextParams.set('jobId', String(currentJobId))
      nextParams.set('periodMode', 'adaptive')
      nextParams.set('adaptiveStartDate', startDate)
      nextParams.set('adaptiveEndDate', endDate)
      syncQueryToUrl({
        jobId: currentJobId,
        periodMode: 'adaptive',
        adaptiveStartDate: startDate,
        adaptiveEndDate: endDate,
      })
      navigate(`${stepPath(3)}?${nextParams.toString()}`)
      return
    }

    let usePeriodId = periodId
    if (!usePeriodId) {
      if (!currentOrgId || !periodCode || !periodStart || !periodEnd) {
        message.warning('请从下拉列表选择 open/reopened 会计期间，或填写期间编码与起止日期后创建')
        return
      }
      try {
        const period = await api.createAccountingPeriod({
          organization_id: currentOrgId,
          ledger_id: currentLedgerId || undefined,
          period_code: periodCode,
          start_date: periodStart,
          end_date: periodEnd,
        })
        usePeriodId = period.id
        setPeriodId(usePeriodId)
      } catch (error) {
        const detail = error instanceof Error ? error.message : String(error)
        message.error(`创建会计期间失败：${detail}`)
        return
      }
    }
    const nextParams = new URLSearchParams()
    nextParams.set('inputMode', inputMode)
    nextParams.set('jobId', String(currentJobId))
    nextParams.set('periodId', String(usePeriodId))
    nextParams.set('periodMode', 'fixed')
    syncQueryToUrl({ jobId: currentJobId, periodId: usePeriodId, periodMode: 'fixed' })
    navigate(`${stepPath(3)}?${nextParams.toString()}`)
  }

  const updateManualRow = (key: string, field: keyof ManualEntryLine, value: string | number | null) => {
    setManualRows(prev => prev.map(row => {
      if (row.key !== key) return row
      return { ...row, [field]: value ?? (field === 'debit_amount' || field === 'credit_amount' || field === 'entry_line_no' ? 0 : '') }
    }))
  }

  const selectAccountForRow = (key: string, accountCode: string) => {
    const account = activeChartOfAccounts.find(item => item.code === accountCode)
    if (!account) return
    setManualRows(prev => prev.map(row => {
      if (row.key !== key) return row
      return {
        ...row,
        account_code: account.code,
        account_name: account.name,
        account_source: 'coa',
      }
    }))
  }

  const addManualRow = (afterKey?: string) => {
    setManualRows(prev => {
      const maxLineNo = prev.reduce((max, row) => Math.max(max, row.entry_line_no), 0)
      const nextLine = createManualLine(maxLineNo + 1)
      if (!afterKey) return [...prev, nextLine]
      const index = prev.findIndex(row => row.key === afterKey)
      if (index < 0) return [...prev, nextLine]
      const next = [...prev]
      next.splice(index + 1, 0, nextLine)
      return next.map((row, rowIndex) => ({ ...row, entry_line_no: rowIndex + 1 }))
    })
  }

  const resetManualForm = (options?: { keepPeriod?: boolean; incrementVoucherNumber?: boolean }) => {
    const nextNumber = options?.incrementVoucherNumber
      ? String(Number.parseInt(manualVoucherNumber, 10) + 1 || 1).padStart(3, '0')
      : '001'
    setManualVoucherType('记')
    setManualVoucherNumber(nextNumber)
    setManualAttachmentCount(0)
    setManualRemark('')
    setManualRows([
      createManualLine(1),
      createManualLine(2),
      createManualLine(3),
      createManualLine(4),
      createManualLine(5),
    ])
    if (!options?.keepPeriod) {
      setManualVoucherDate(periodStart || '')
    } else if (manualVoucherDate) {
      setManualVoucherDate(manualVoucherDate)
    } else {
      setManualVoucherDate(periodStart || '')
    }
  }

  const clearManualForm = () => {
    resetManualForm({ keepPeriod: true })
    message.info('已清空当前凭证内容')
  }

  const removeManualRow = (key: string) => {
    if (manualRows.length <= 1) {
      message.warning('至少保留一行分录')
      return
    }
    setManualRows(prev => prev.filter(row => row.key !== key))
  }

  const handleSelectPeriod = (selectedPeriodId: number) => {
    const selectedPeriod = accountingPeriods.find(period => period.id === selectedPeriodId)
    if (!selectedPeriod) return
    applySelectedPeriod(selectedPeriod)
    setPeriodSuggestion('')
    syncQueryToUrl({ periodId: selectedPeriod.id, jobId: currentJobId })
  }

  const handleVoucherDateChange = (date: Dayjs | null) => {
    const nextDate = date ? date.format('YYYY-MM-DD') : ''
    setManualVoucherDate(nextDate)
    if (nextDate && periodStart && periodEnd && !isDateInPeriod(nextDate, periodStart, periodEnd)) {
      message.warning('凭证日期不在当前会计期间内，请确认是否选错期间或日期')
    }
  }

  const disableVoucherDate = (current: Dayjs) => {
    if (!periodStart || !periodEnd) return false
    return current.isBefore(dayjs(periodStart), 'day') || current.isAfter(dayjs(periodEnd), 'day')
  }

  const navigateToCoa = (keyword?: string) => {
    const params = new URLSearchParams()
    params.set('from', 'manual-voucher')
    if (manualVoucherDate) params.set('voucherDate', manualVoucherDate)
    if (periodId) params.set('periodId', String(periodId))
    if (periodCode) params.set('periodCode', periodCode)
    if (keyword || accountSearchKeyword) params.set('keyword', keyword || accountSearchKeyword)
    setUsedCustomAccountEntry(true)
    navigate(`/basic/coa?${params.toString()}`)
  }

  const validateManualRows = () => {
    if (!manualVoucherDate || !manualVoucherType.trim() || !manualVoucherNumber.trim()) {
      message.warning('请填写凭证日期、凭证字和凭证号')
      return false
    }
    if (periodStart && periodEnd && !isDateInPeriod(manualVoucherDate, periodStart, periodEnd)) {
      message.warning('凭证日期不在所选会计期间内，请先调整日期或重新选择期间')
      return false
    }
    const activeRows = activeManualRows
    if (activeRows.length === 0) {
      message.warning('请至少录入一行有效分录')
      return false
    }
    for (const row of activeRows) {
      if (!row.summary.trim() || !row.account_code.trim() || !row.account_name.trim()) {
        message.warning(`第 ${row.entry_line_no} 行请填写摘要，并从会计科目表选择科目`)
        return false
      }
      if (parseDecimal(row.debit_amount || 0).gt(0) && parseDecimal(row.credit_amount || 0).gt(0)) {
        message.warning(`第 ${row.entry_line_no} 行不能同时填写借方和贷方金额，请按会计分录方向只填一边`)
        return false
      }
      if (parseDecimal(row.debit_amount || 0).isZero() && parseDecimal(row.credit_amount || 0).isZero()) {
        message.warning(`第 ${row.entry_line_no} 行借方或贷方至少填写一个金额，金额不能为 0`)
        return false
      }
      if (getCounterpartyHintStatus(row) === 'required_missing') {
        message.warning(`第 ${row.entry_line_no} 行属于往来性质科目，请填写客户、供应商或其他对方单位`)
        return false
      }
    }
    if (!isBalanced) {
      message.warning('本张凭证借方合计与贷方合计不一致，请调平后再提交')
      return false
    }
    return true
  }

  const buildManualDrafts = (context: { periodId: number }): EntryDraft[] => activeManualRows.map(row => ({
    voucher_no: manualVoucherNo,
    voucher_date: manualVoucherDate,
    account_code: row.account_code.trim(),
    account_name: row.account_name.trim(),
    summary: row.summary.trim(),
    debit_amount: parseDecimal(row.debit_amount || 0).toNumber(),
    credit_amount: parseDecimal(row.credit_amount || 0).toNumber(),
    counterparty: row.counterparty.trim() || null,
    entry_line_no: row.entry_line_no,
    metadata: {
      source: 'manual_entry',
      inputMode,
      periodId: context.periodId,
      voucherDate: manualVoucherDate,
      voucherType: manualVoucherType,
      voucherNumber: manualVoucherNumber,
      voucher_no_compatible: manualVoucherNo,
      attachmentCount: manualAttachmentCount,
      remark: manualRemark,
      quickEntry: manualQuickEntry,
      account_source: row.account_source,
      used_custom_account_entry: usedCustomAccountEntry,
      counterparty_hint_status: getCounterpartyHintStatus(row),
      archive_context: '传统人工凭证录入：已保存期间、日期、凭证字/号、附单据、备注和科目选择来源，metadata 仅用于项目归档与追踪。',
    },
    tags: [],
  }))

  const submitManualVoucher = async (action: 'save' | 'save_and_new' | 'save_and_copy' = 'save') => {
    if (!validateManualRows()) return
    setManualSubmitting(true)
    try {
      const context = await ensurePeriod('manual_entry')
      const drafts = buildManualDrafts(context)
      const result = await api.commitManualEntries(context.periodId, drafts)
      message.success(`凭证已保存，共 ${result.count} 条分录`)

      if (action === 'save') {
        const nextParams = new URLSearchParams()
        nextParams.set('inputMode', inputMode)
        nextParams.set('jobId', String(result.job_id))
        nextParams.set('periodId', String(context.periodId))
        navigate(`${stepPath(4)}?${nextParams.toString()}`)
        return
      }

      if (action === 'save_and_new') {
        resetManualForm({ keepPeriod: true, incrementVoucherNumber: true })
        return
      }

      const nextVoucherNumber = String(Number.parseInt(manualVoucherNumber, 10) + 1 || 1).padStart(3, '0')
      setManualVoucherNumber(nextVoucherNumber)
      setManualAttachmentCount(0)
      setManualRemark('')
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error)
      message.error(`保存凭证失败：${detail}`)
    } finally {
      setManualSubmitting(false)
    }
  }

  const earliestPeriodStart = useMemo(() => getEarliestPeriodStart(accountingPeriods), [accountingPeriods])

  const effectiveAdaptiveRange = useMemo(
    () => resolveAdaptivePeriodRange(adaptiveStartDate, adaptiveEndDate, earliestPeriodStart),
    [adaptiveStartDate, adaptiveEndDate, earliestPeriodStart],
  )

  const periodSelectionReady = useMemo(() => {
    if (periodMode === 'adaptive') {
      return Boolean(effectiveAdaptiveRange.startDate && effectiveAdaptiveRange.endDate)
    }
    return Boolean(periodId || (periodCode && periodStart && periodEnd))
  }, [periodMode, effectiveAdaptiveRange, periodId, periodCode, periodStart, periodEnd])

  const dayBookImportReady = useMemo(() => {
    if (periodMappingMode === 'preserve_source') return true
    return Boolean(periodId || (periodCode && periodStart && periodEnd))
  }, [periodMappingMode, periodId, periodCode, periodStart, periodEnd])

  const dayBookNextDisabled = !currentJobId || !dayBookImportReady || periodMappingApplying

  const disabledStartDate = (current: Dayjs) => {
    if (!earliestPeriodStart) return false
    return current.isBefore(dayjs(earliestPeriodStart), 'day')
  }

  const disabledEndDate = (current: Dayjs) => {
    const start = effectiveAdaptiveRange.startDate
    if (!start) return false
    return current.isBefore(dayjs(start), 'day')
  }

  const renderPeriodMappingCard = (sectionTitle: string) => (
    <Card style={{ marginTop: '16px' }}>
      <Title level={5}>{sectionTitle}</Title>
      {importPeriodSuggestion?.is_multi_period && importPeriodSuggestion.detected_months && (
        <Alert
          title="检测到多期间凭证"
          description={`文件中的凭证日期跨越 ${importPeriodSuggestion.detected_months.length} 个月份：${importPeriodSuggestion.detected_months.join('、')}。请选择下方期间处理方式。`}
          type="warning"
          showIcon
          style={{ marginBottom: '12px' }}
        />
      )}
      {importPeriodReason && !importPeriodSuggestion?.is_multi_period && (
        <Alert title={importPeriodReason} type="info" showIcon style={{ marginBottom: '12px' }} />
      )}
      <Radio.Group
        value={periodMappingMode}
        onChange={(event) => {
          const nextMode = event.target.value as PeriodMappingMode
          setPeriodMappingMode(nextMode)
          syncQueryToUrl({ periodMappingMode: nextMode, jobId: currentJobId })
          if (nextMode === 'unify_target') {
            applyCurrentMonthPeriodDefault(accountingPeriods)
          }
        }}
        style={{ width: '100%' }}
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <Radio value="unify_target">
            <Space direction="vertical" size={0}>
              <span>导入后统一期间</span>
              <span style={{ color: '#666', fontSize: 12 }}>
                将全部凭证归入单一会计期间，默认本周期（今天所在月），适用于按月分批导入。
              </span>
            </Space>
          </Radio>
          <Radio value="preserve_source">
            <Space direction="vertical" size={0}>
              <span>保留来源期间</span>
              <span style={{ color: '#666', fontSize: 12 }}>
                按序时簿中各凭证的原始日期，自动匹配或创建对应月份期间；一张凭证对应一个期间，适用于跨月序时簿整体导入。
              </span>
            </Space>
          </Radio>
        </Space>
      </Radio.Group>
      {periodMappingMode === 'preserve_source' && (
        <Alert
          title="将按凭证日期自动分配期间"
          description="进入下一步时，系统会根据每张凭证的日期识别所属月份，自动匹配已有期间或创建缺失的月度期间，无需手动选择目标期间。"
          type="info"
          showIcon
          style={{ marginTop: '12px' }}
        />
      )}
      {periodMappingMode === 'unify_target' && (
        <Space direction="vertical" style={{ width: '100%', marginTop: '12px' }}>
          <Alert
            title="目标期间（固定 · 本周期）"
            description="默认选中今天所在自然月；若账簿已有同月 open/reopened 期间则自动匹配。"
            type="info"
            showIcon
          />
          <Select
            allowClear
            showSearch
            placeholder="优先选择 open/reopened 会计期间"
            loading={periodsLoading}
            value={periodId || undefined}
            options={accountingPeriods.map(period => ({
              value: period.id,
              label: `${period.period_code}（${period.start_date} 至 ${period.end_date}，${period.status}）`,
            }))}
            optionFilterProp="label"
            onChange={(value) => (value ? handleSelectPeriod(value) : setPeriodId(null))}
            style={{ maxWidth: 520, width: '100%' }}
          />
          {periodSuggestion && <Alert title={periodSuggestion} type="info" showIcon />}
          <Space wrap>
            <Input
              placeholder="期间编码，如 2026-07"
              value={periodCode}
              onChange={(e) => setPeriodCode(e.target.value)}
              style={{ width: 180 }}
            />
            <DatePicker
              value={periodStart ? dayjs(periodStart) : null}
              placeholder="期间开始"
              onChange={(date) => setPeriodStart(date ? date.format('YYYY-MM-DD') : '')}
            />
            <DatePicker
              value={periodEnd ? dayjs(periodEnd) : null}
              placeholder="期间结束"
              onChange={(date) => setPeriodEnd(date ? date.format('YYYY-MM-DD') : '')}
            />
          </Space>
          <Text type="secondary">确认目标期间后，系统将把本次导入的全部凭证归入该期间。</Text>
        </Space>
      )}
    </Card>
  )

  const renderPeriodSelectionCard = (sectionTitle: string, extraAlert?: ReactNode) => (
    <Card style={{ marginTop: '16px' }}>
      <Title level={5}>{sectionTitle}</Title>
      {extraAlert}
      <Space direction="vertical" style={{ width: '100%' }}>
        <Radio.Group
          value={periodMode}
          onChange={(event) => {
            const nextMode = event.target.value as PeriodSelectionMode
            setPeriodMode(nextMode)
            if (nextMode === 'adaptive') {
              applyAdaptiveDefaults(accountingPeriods)
            }
          }}
          style={{ marginBottom: '8px' }}
        >
          <Space direction="vertical">
            <Radio value="adaptive">
              <Space direction="vertical" size={0}>
                <span>自适应范围（根据识别的凭证日期自动匹配期间）</span>
                <span style={{ color: '#666', fontSize: 12 }}>系统根据凭证日期识别月份范围，自动创建缺失期间，适用于多期间混合导入场景。</span>
              </Space>
            </Radio>
            <Radio value="fixed">
              <Space direction="vertical" size={0}>
                <span>固定期间（事前约定单一会计期间）</span>
                <span style={{ color: '#666', fontSize: 12 }}>只接受指定期间内的凭证，超出期间的凭证将被标记为异常，适用于按月分批导入场景。</span>
              </Space>
            </Radio>
          </Space>
        </Radio.Group>

        {periodMode === 'adaptive' && (
          <Space direction="vertical" style={{ width: '100%' }}>
            <Alert
              title="自适应期间范围设置"
              description={
                <Space direction="vertical" size={4}>
                  <div><strong>上限（最早允许日期）：</strong>{earliestPeriodStart || '未设置'} — 系统自动取账簿最早期间的开始日期，凭证日期不得早于此日期。</div>
                  <div><strong>下限（最晚允许日期）：</strong>由您指定，凭证日期不得晚于此日期。</div>
                </Space>
              }
              type="info"
              showIcon
            />
            <Space wrap>
              <DatePicker
                value={effectiveAdaptiveRange.startDate ? dayjs(effectiveAdaptiveRange.startDate) : null}
                placeholder="期间范围开始（默认账簿最早期间）"
                onChange={(date) => setAdaptiveStartDate(date ? date.format('YYYY-MM-DD') : '')}
                disabledDate={disabledStartDate}
                style={{ width: 200 }}
              />
              <DatePicker
                value={effectiveAdaptiveRange.endDate ? dayjs(effectiveAdaptiveRange.endDate) : null}
                placeholder="期间范围结束（默认今天）"
                onChange={(date) => setAdaptiveEndDate(date ? date.format('YYYY-MM-DD') : '')}
                disabledDate={disabledEndDate}
                style={{ width: 200 }}
              />
            </Space>
            {effectiveAdaptiveRange.startDate && effectiveAdaptiveRange.endDate && (
              <Text type="secondary">
                当前设置：{effectiveAdaptiveRange.startDate} 至 {effectiveAdaptiveRange.endDate}，系统将在此范围内按月份自动创建会计期间。
              </Text>
            )}
          </Space>
        )}

        {periodMode === 'fixed' && (
          <>
            <Select
              allowClear
              showSearch
              placeholder="优先选择 open/reopened 会计期间"
              loading={periodsLoading}
              value={periodId || undefined}
              options={accountingPeriods.map(period => ({
                value: period.id,
                label: `${period.period_code}（${period.start_date} 至 ${period.end_date}，${period.status}）`,
              }))}
              optionFilterProp="label"
              onChange={(value) => (value ? handleSelectPeriod(value) : setPeriodId(null))}
              style={{ maxWidth: 520, width: '100%' }}
            />
            {periodSuggestion && <Alert title={periodSuggestion} type="info" showIcon />}
            <Alert
              title="期间选择说明"
              description="系统会优先使用 open/reopened 期间；如果只有已结账期间，会按上一已结账期间建议下一自然月。下方手工创建入口仅作为没有可用期间时的补充路径。"
              type="info"
              showIcon
            />
            <Space wrap>
              <Input
                placeholder="期间编码，如 2026-01"
                value={periodCode}
                onChange={(e) => setPeriodCode(e.target.value)}
                style={{ width: 180 }}
              />
              <DatePicker
                value={periodStart ? dayjs(periodStart) : null}
                placeholder="期间开始"
                onChange={(date) => setPeriodStart(date ? date.format('YYYY-MM-DD') : '')}
              />
              <DatePicker
                value={periodEnd ? dayjs(periodEnd) : null}
                placeholder="期间结束"
                onChange={(date) => setPeriodEnd(date ? date.format('YYYY-MM-DD') : '')}
              />
            </Space>
            <Text type="secondary">会计期间用于限定凭证日期范围，也是后续复核、报表和导出的基础核算范围。</Text>
          </>
        )}
      </Space>
    </Card>
  )

  if (isManualEntry) {
    return (
      <div style={{ padding: '24px', maxWidth: '1280px', margin: '0 auto' }}>
        <Steps
          current={currentStep}
          items={[
            { title: '选择模式' },
            { title: '人工录入' },
            { title: '生成草稿' },
            { title: '复核调整' },
            { title: '确认导出' }
          ]}
          style={{ marginBottom: '24px' }}
        />

        <FlowNav prev={stepPath(1)} style={{ marginBottom: '16px' }} />

        <Title level={4}>传统人工录入凭证</Title>
        <Text type="secondary" style={{ display: 'block', marginBottom: '16px' }}>
          按纸质记账凭证样式录入：摘要、科目、借方/贷方面额分列。保存后可进入复核调整。
        </Text>

        <TraditionalVoucherForm
          voucherType={manualVoucherType}
          voucherNumber={manualVoucherNumber}
          voucherDate={manualVoucherDate}
          attachmentCount={manualAttachmentCount}
          remark={manualRemark}
          quickEntry={manualQuickEntry}
          rows={manualRows}
          debitTotal={debitTotal}
          creditTotal={creditTotal}
          isBalanced={isBalanced}
          balanceDiff={balanceDiff}
          submitting={manualSubmitting}
          periodId={periodId}
          periodCode={periodCode}
          periodStart={periodStart}
          periodEnd={periodEnd}
          periodSuggestion={periodSuggestion}
          accountingPeriods={accountingPeriods}
          periodsLoading={periodsLoading}
          chartOfAccounts={chartOfAccounts}
          coaLoading={coaLoading}
          counterparties={counterparties}
          counterpartiesLoading={counterpartiesLoading}
          preparerName={user?.username || ''}
          voucherTypeOptions={VOUCHER_TYPE_OPTIONS}
          onVoucherTypeChange={setManualVoucherType}
          onVoucherNumberChange={setManualVoucherNumber}
          onVoucherDateChange={handleVoucherDateChange}
          onAttachmentCountChange={setManualAttachmentCount}
          onRemarkChange={setManualRemark}
          onQuickEntryChange={setManualQuickEntry}
          onSelectPeriod={handleSelectPeriod}
          onPeriodCodeChange={setPeriodCode}
          onPeriodStartChange={setPeriodStart}
          onPeriodEndChange={setPeriodEnd}
          onUpdateRow={updateManualRow}
          onSelectAccount={selectAccountForRow}
          onAddRow={addManualRow}
          onRemoveRow={removeManualRow}
          onNavigateToCoa={navigateToCoa}
          onAccountSearch={setAccountSearchKeyword}
          getCounterpartyHintStatus={getCounterpartyHintStatus}
          disableVoucherDate={disableVoucherDate}
          onSave={() => void submitManualVoucher('save')}
          onSaveAndNew={() => void submitManualVoucher('save_and_new')}
          onSaveAndCopy={() => void submitManualVoucher('save_and_copy')}
          onClear={clearManualForm}
          onNewVoucher={() => resetManualForm({ keepPeriod: true, incrementVoucherNumber: false })}
          onOpenVoucherList={() => navigate('/ledger/entries')}
        />

        <div style={{ marginTop: '16px' }} className="no-print">
          <Button onClick={() => navigate(`${stepPath(1)}?${buildStepQuery()}`)}>
            返回选择模式
          </Button>
        </div>
      </div>
    )
  }

  if (isDayBookImport) {
    return (
      <div style={{ padding: '24px', maxWidth: '1000px', margin: '0 auto' }}>
        <Steps
          current={currentStep}
          items={[
            { title: '选择模式' },
            { title: '导入资料' },
            { title: '生成草稿' },
            { title: '复核调整' },
            { title: '确认导出' }
          ]}
          style={{ marginBottom: '32px' }}
        />

        <FlowNav
          prev={`${stepPath(1)}?${buildStepQuery()}`}
          onNext={handleNext}
          nextDisabled={dayBookNextDisabled}
          style={{ marginBottom: '16px' }}
        />

        {!currentJobId && (
          <ImportResumeBanner
            ledgerId={currentLedgerId}
            variant="step2"
            onResumeJob={handleResumeImportJob}
          />
        )}

        <Title level={4}>导入结构化财务文件 · {structuredMeta.label}</Title>
        <Text type="secondary">
          {structuredMeta.hint}。上传 Excel/CSV 等标准表格：由「结构化自适应导入引擎」（资料解析中心 · 场景 A）识别表头、映射列并校验分录。
        </Text>

        <Alert
          title="结构化自适应导入（场景 A）"
          description={`当前文件类型：${structuredMeta.label}。解析成功后走 direct_entries 路径，直接生成 accounting_entries 并进入复核调整；如需更换类型请返回 Step 1。`}
          type="info"
          showIcon
          style={{ marginTop: '16px' }}
        />

        <Card title="解析兼容性配置" style={{ marginTop: '16px' }}>
          <StructuredParseCompatibilityPanel
            options={parseOptions}
            onChange={setParseOptions}
            formatDetection={formatDetection}
            detecting={formatDetecting}
            onPreDetect={handlePreDetectFormat}
          />
        </Card>

        <Card style={{ marginTop: '16px' }}>
          <Title level={5}>1. 上传{structuredMeta.uploadTitle}</Title>
          <Dragger
            name="daybook"
            multiple={false}
            disabled={processingUpload}
            beforeUpload={handleDayBookUpload}
            accept=".xlsx,.xls,.csv,.tsv"
            style={{ padding: '32px' }}
          >
            <p className="ant-upload-drag-icon">
              <InboxOutlined />
            </p>
            <p className="ant-upload-text">点击或拖拽文件到此区域</p>
            <p className="ant-upload-hint">
              {structuredMeta.columnHint}
              {' '}
              上传前请先在上方确认字符集与分隔符；也可使用「预检测文件」查看识别结果。
            </p>
          </Dragger>

          {uploadedFiles.length > 0 && (
            <List
              header={<Text strong>已上传文件 ({uploadedFiles.length})</Text>}
              dataSource={uploadedFiles}
              renderItem={(file) => (
                <List.Item>
                  <List.Item.Meta title={file.name} description={`${(file.size / 1024).toFixed(1)} KB`} />
                  {outputPath && <Tag color="blue">输出路径：{outputPath}</Tag>}
                  {entryCount > 0 && <Tag color="green">{entryCount} 条分录</Tag>}
                </List.Item>
              )}
              style={{ marginTop: '16px' }}
            />
          )}
          {renderParseGuidance(parseGuidance, {
            onSwitchDayBook: () => navigate(`${stepPath(1)}?${buildStepQuery()}`),
          })}
        </Card>

        {dayBookReport && (
          <Card style={{ marginTop: '16px' }}>
            <Title level={5}>2. 结构化文件检测报告</Title>
            <Space wrap size="large">
              <Statistic title="凭证总数" value={dayBookReport.total_vouchers} />
              <Statistic title="分录行数" value={dayBookReport.total_entries} />
              <Statistic title="跳号数量" value={dayBookReport.skip_count} />
              <Statistic title="不平衡凭证" value={dayBookReport.unbalanced_count} />
              <Statistic title="完整性评分" value={dayBookReport.completeness_score} suffix="/ 100" />
            </Space>
            {dayBookReport.missing_voucher_nos.length > 0 && (
              <Alert
                title="检测到凭证号跳号"
                description={`缺失凭证号：${dayBookReport.missing_voucher_nos.join('、')}`}
                type="warning"
                showIcon
                style={{ marginTop: '16px' }}
              />
            )}
            {dayBookReport.unbalanced_count > 0 && (
              <Alert
                title="存在借贷不平衡凭证"
                description="部分序时簿仅在首行填日期/凭证号。蓝字为同侧正数发生额，红字可在借方或贷方列出现，表示同侧负数冲减；整张凭证仍须借贷相等。贷方列若仅用红色显示正常发生额且摘要无“冲/红字”等字样，仍按正数贷方处理。"
                type="warning"
                showIcon
                style={{ marginTop: '16px' }}
              />
            )}
            {dayBookReport.unbalanced_vouchers.length > 0 && (
              <Table
                style={{ marginTop: 16 }}
                size="small"
                rowKey={(row) => `${row.voucher_no}-${row.voucher_date || ''}-${row.entry_count}`}
                pagination={{ pageSize: 8, hideOnSinglePage: true }}
                dataSource={dayBookReport.unbalanced_vouchers}
                columns={[
                  { title: '凭证号', dataIndex: 'voucher_no', width: 120 },
                  { title: '凭证日期', dataIndex: 'voucher_date', width: 120, render: (v) => v || '-' },
                  { title: '分录行', dataIndex: 'entry_count', width: 80 },
                  { title: '借方合计', dataIndex: 'debit_total', width: 120 },
                  { title: '贷方合计', dataIndex: 'credit_total', width: 120 },
                  { title: '差额', dataIndex: 'difference', width: 100 },
                ]}
              />
            )}
          </Card>
        )}

        {entryCount > 0 && renderPeriodMappingCard(`${dayBookReport ? '3' : '2'}. 会计期间映射`)}

        <div style={{ marginTop: '24px', display: 'flex', gap: '12px' }}>
          <Button onClick={() => navigate(`${stepPath(1)}?${buildStepQuery()}`)}>
            上一步
          </Button>
          <Button
            type="primary"
            onClick={handleNext}
            loading={periodMappingApplying}
            disabled={dayBookNextDisabled}
          >
            进入复核调整 {entryCount > 0 ? `(${entryCount} 条分录)` : ''}
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div style={{ padding: '24px', maxWidth: '900px', margin: '0 auto' }}>
      <Steps
        current={currentStep}
        items={[
          { title: '选择模式' },
          { title: '导入资料' },
          { title: '生成草稿' },
          { title: '复核调整' },
          { title: '确认导出' }
        ]}
        style={{ marginBottom: '32px' }}
      />

      <FlowNav prev={stepPath(1)} onNext={handleNext} nextDisabled={uploadedFiles.length === 0 || !currentJobId || !periodSelectionReady} style={{ marginBottom: '16px' }} />

      <Title level={4}>导入非结构化 · 支持性原始文件</Title>
        <Text type="secondary">
          由「原始资料解析与登记」（资料解析中心 · 场景 B）处理 PDF、图片、扫描件：OCR 与语义识别后登记功能模块台账并归档底稿；不直接写入会计分录，下一步生成待复核凭证草稿。
        </Text>

      {outputPath && (
        <Alert
          title={`当前输出路径：${outputPath}`}
          description={
            outputPath === 'register_ledger'
              ? '原始资料（PDF/图片等）识别后登记到功能模块台账（非会计分录），下一步结合台账证据生成凭证草稿。'
              : outputPath === 'structured_preview'
                ? `已识别结构化表格 ${structuredPreviewCount > 0 ? `（${structuredPreviewCount} 条分录预览）` : ''}。标准 Excel/CSV 财务文件请返回 Step 1 选择「结构化 · 标准化财务文件」。`
                : '结构化文件已解析为分录预览，请返回 Step 1 选择「结构化 · 标准化财务文件」生成正式凭证。'
          }
          type={outputPath === 'structured_preview' ? 'warning' : 'info'}
          showIcon
          style={{ marginTop: '12px' }}
        />
      )}

      {renderParseGuidance(parseGuidance, {
        onSwitchDayBook: () => navigate(`${stepPath(1)}?inputMode=day_book_import&structuredKind=day_book`),
      })}

      <Card style={{ marginTop: '16px' }}>
        <Title level={5}>1. 提供原始资料类型辅助信息</Title>
        <Text type="secondary">原始资料类型作为 AI 识别辅助信息，可多选；系统将据此登记到对应功能模块台账。</Text>

        <div style={{ marginTop: '16px', display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
          {[...SOURCE_DOCUMENT_TYPES.filter(t => t.type !== 'other'), ...customTypes].map((item) => (
            <Tag.CheckableTag
              key={item.type}
              checked={selectedTypes.includes(item.type)}
              onClick={() => toggleType(item.type)}
              style={{
                padding: '8px 16px',
                fontSize: '14px',
                borderRadius: '6px',
              }}
            >
              <Space>
                <span>{'icon' in item && typeof item.icon === 'string' ? item.icon : '📋'}</span>
                <span>{item.label}</span>
              </Space>
            </Tag.CheckableTag>
          ))}
        </div>

        <Button
          type="dashed"
          icon={<PlusOutlined />}
          onClick={() => setCustomTypeModalVisible(true)}
          style={{ marginTop: '16px' }}
        >
          添加自定义凭证类型
        </Button>

        {selectedTypes.length > 0 && (
          <div style={{ marginTop: '16px', padding: '12px', background: '#f6ffed', borderRadius: '6px' }}>
            <Text type="secondary">
              <RobotOutlined style={{ color: '#52c41a', marginRight: '8px' }} />
              已提供 {selectedTypes.length} 个资料类型辅助信息，上传后将优先登记到对应模块台账（发票→税务、流水→银行、合同→往来/采购/销售）
            </Text>
          </div>
        )}
      </Card>

      <Card style={{ marginTop: '16px' }}>
        <Title level={5}>2. 上传原始凭证文件</Title>

        <Dragger
          name="files"
          multiple
          beforeUpload={handleUpload}
          accept=".xlsx,.xls,.csv,.pdf,.jpg,.jpeg,.png,.txt"
          style={{ padding: '40px' }}
        >
          <p className="ant-upload-drag-icon">
            <InboxOutlined />
          </p>
          <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
          <p className="ant-upload-hint">
            支持 PDF/图片（原始资料 AI 识别）或 Excel/CSV（结构化序时簿预览）。
            PDF/图片将登记模块台账；Excel/CSV 会检测列映射并引导切换到序时簿导入模式。
          </p>
        </Dragger>

        {uploadedFiles.length > 0 && (
          <List
            header={<Text strong>已上传文件 ({uploadedFiles.length})</Text>}
            dataSource={uploadedFiles}
            renderItem={(file) => (
              <List.Item>
                <List.Item.Meta
                  title={file.name}
                  description={
                    <Space direction="vertical" size={2}>
                      <Text type="secondary">{(file.size / 1024).toFixed(1)} KB</Text>
                      {file.registerSummary && (
                        <Text type="success">已登记：{file.registerSummary}</Text>
                      )}
                      {file.moduleRegistrations && file.moduleRegistrations.length > 0 && (
                        <Space wrap size={[4, 4]}>
                          {file.moduleRegistrations.map((reg) => (
                            <Tag key={reg.module_key} color={reg.semantic_only ? 'gold' : 'blue'}>
                              {reg.module_label}{reg.semantic_only ? '（语义投影）' : ''}
                            </Tag>
                          ))}
                        </Space>
                      )}
                      {file.decompositionSource && (
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          分解引擎：{file.decompositionSource === 'rules+llm' ? '规则 + AI 语义增强' : '规则基线（稳定）'}
                        </Text>
                      )}
                      {file.semanticTags && file.semanticTags.length > 0 && (
                        <Space wrap size={[4, 4]}>
                          {file.semanticTags.map((tag) => (
                            <Tag key={tag}>{tag}</Tag>
                          ))}
                        </Space>
                      )}
                      {file.riskHints && file.riskHints.length > 0 && (
                        <Alert
                          type="warning"
                          showIcon
                          title={`识别 ${file.riskHints.length} 条风险线索`}
                          description={file.riskHints.map((hint) => hint.description).join('；')}
                        />
                      )}
                      {file.archivePath && (
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          归档路径：{file.archivePath}
                          {file.archiveCategory ? `（${file.archiveCategory}）` : ''}
                        </Text>
                      )}
                    </Space>
                  }
                />
              </List.Item>
            )}
            style={{ marginTop: '16px' }}
          />
        )}
      </Card>

      {renderPeriodSelectionCard('3. 选择会计期间')}

      <div style={{ marginTop: '24px', display: 'flex', gap: '12px' }}>
        <Button onClick={() => navigate(`${stepPath(1)}?inputMode=${inputMode}`)}>
          上一步
        </Button>
        <Button
          type="primary"
          onClick={handleNext}
          disabled={uploadedFiles.length === 0 || !currentJobId || !periodSelectionReady}
        >
          下一步 {uploadedFiles.length > 0 ? `(${uploadedFiles.length} 个文件)` : ''}
        </Button>
      </div>

      <Modal
        title="添加自定义凭证类型"
        open={customTypeModalVisible}
        onOk={handleAddCustomType}
        onCancel={() => {
          setCustomTypeModalVisible(false)
          setCustomTypeInput('')
        }}
        okText="添加"
        cancelText="取消"
      >
        <div style={{ marginBottom: '16px' }}>
          <Text type="secondary">
            如果原始凭证类型不在常见类型中，例如质检单、验收单、结算单等，
            可以在这里添加，系统会作为 AI 识别辅助信息。
          </Text>
        </div>
        <Input
          placeholder="请输入凭证类型名称，如：质检单、验收单、结算单"
          value={customTypeInput}
          onChange={(e) => setCustomTypeInput(e.target.value)}
          onPressEnter={handleAddCustomType}
        />
        <div style={{ marginTop: '8px', color: '#999', fontSize: '12px' }}>
          <Text type="warning">提示：</Text> 请尽量使用规范的凭证名称，便于系统识别。
        </div>
      </Modal>
    </div>
  )
}
