import { Card, Upload, Button, Steps, Typography, message, Tag, Space, Modal, Input, List, DatePicker, Table, InputNumber, Alert, Select, Statistic } from 'antd'
import { useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { DeleteOutlined, InboxOutlined, PlusOutlined, RobotOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import dayjs, { type Dayjs } from 'dayjs'
import { api, type AccountingPeriod, type ChartOfAccount, type Counterparty, type DayBookReport, type EntryDraft, type ImportPeriodSuggestion } from '../../api/client'
import { FlowNav } from '../../components/FlowNav'
import { useAuthStore } from '../../stores/authStore'

const { Dragger } = Upload
const { Title, Text } = Typography

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

interface ManualEntryLine {
  key: string
  entry_line_no: number
  summary: string
  account_code: string
  account_name: string
  debit_amount: number
  credit_amount: number
  counterparty: string
  account_source: 'coa' | 'manual'
}

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

const roundAmount = (amount: number) => Math.round(amount * 100) / 100

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

export function Step2AccountingImportSource() {
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const { currentLedgerId } = useAuthStore()
  const inputMode = searchParams.get('inputMode') || 'ai_generated'
  const isManualEntry = inputMode === 'manual_entry'
  const isDayBookImport = inputMode === 'day_book_import'
  const stepPath = (step: number) => location.pathname.startsWith('/ledger/vouchers/step/') ? `/ledger/vouchers/step/${step}` : `/accounting/step/${step}`
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
  ])
  const [manualSubmitting, setManualSubmitting] = useState(false)
  const [dayBookReport, setDayBookReport] = useState<DayBookReport | null>(null)
  const [importPeriodSuggestion, setImportPeriodSuggestion] = useState<ImportPeriodSuggestion | null>(null)
  const [importPeriodReason, setImportPeriodReason] = useState('')
  const [outputPath, setOutputPath] = useState<string>('')
  const [processingUpload, setProcessingUpload] = useState(false)
  const [entryCount, setEntryCount] = useState(0)

  const manualVoucherNo = `${manualVoucherType}-${manualVoucherNumber}`
  const debitTotal = roundAmount(manualRows.reduce((sum, row) => sum + Number(row.debit_amount || 0), 0))
  const creditTotal = roundAmount(manualRows.reduce((sum, row) => sum + Number(row.credit_amount || 0), 0))
  const balanceDiff = roundAmount(debitTotal - creditTotal)
  const isBalanced = debitTotal > 0 && creditTotal > 0 && balanceDiff === 0
  const activeChartOfAccounts = useMemo(
    () => chartOfAccounts.filter(account => account.status === 'active'),
    [chartOfAccounts]
  )

  const accountCodeOptions = activeChartOfAccounts.map(account => ({
    value: account.code,
    label: `${account.code} ${account.name}`,
    account,
  }))

  const accountNameOptions = activeChartOfAccounts.map(account => ({
    value: account.code,
    label: account.name,
    account,
  }))

  const counterpartyOptions = counterparties
    .filter(counterparty => counterparty.is_active)
    .map(counterparty => ({
      value: counterparty.name,
      label: `${counterparty.name}（${counterparty.role}）`,
    }))

  useEffect(() => {
    if (!isManualEntry) return

    const loadManualEntryBaseData = async () => {
      setPeriodsLoading(true)
      setCoaLoading(true)
      setCounterpartiesLoading(true)
      try {
        const [periods, accounts, loadedCounterparties] = await Promise.all([
          api.listAccountingPeriods(),
          api.listChartOfAccounts(),
          api.listCounterparties(),
        ])
        setAccountingPeriods(periods)
        setChartOfAccounts(accounts)
        setCounterparties(loadedCounterparties)

        const selectedPeriod = initialPeriodId
          ? periods.find(period => period.id === initialPeriodId)
          : periods.find(period => ['open', 'reopened'].includes(period.status))

        if (selectedPeriod) {
          applySelectedPeriod(selectedPeriod)
          setPeriodSuggestion('')
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
      } catch (error) {
        const detail = error instanceof Error ? error.message : String(error)
        message.error(`加载人工录入基础资料失败：${detail}`)
      } finally {
        setPeriodsLoading(false)
        setCoaLoading(false)
        setCounterpartiesLoading(false)
      }
    }

    void loadManualEntryBaseData()
  }, [isManualEntry, initialPeriodId])

  const applySelectedPeriod = (period: AccountingPeriod) => {
    setPeriodId(period.id)
    setPeriodCode(period.period_code)
    setPeriodStart(period.start_date)
    setPeriodEnd(period.end_date)
    setManualVoucherDate(prev => isDateInPeriod(prev, period.start_date, period.end_date) ? prev : period.start_date)
  }

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
        applyPeriodSuggestion(suggestion)
      } catch {
        // 任务尚未完成导入时忽略
      }
    })()
  }, [isDayBookImport, currentJobId])

  const applyPeriodSuggestion = (suggestion: ImportPeriodSuggestion | null) => {
    if (!suggestion) return
    setImportPeriodReason(suggestion.reason)
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
      setPeriodEnd(suggestion.suggested_period.end_date)
    }
  }

  const handleDayBookUpload = async (file: File) => {
    setProcessingUpload(true)
    try {
      let jobId = currentJobId
      if (!jobId) {
        const job = await api.createImportJob('临时组织', 'ledger_day_book', currentLedgerId)
        jobId = job.id
        setCurrentJobId(jobId)
        setCurrentOrgId(job.organization_id)
      }

      await api.uploadFile(jobId, file)
      setUploadedFiles(prev => [...prev, { name: file.name, size: file.size, fileType: file.type || 'unknown', jobId, }])

      message.loading({ content: '正在解析序时簿并生成会计凭证...', key: 'daybook-parse' })
      const result = await api.processImportJobSync(jobId)
      const reportSummary = result.report as {
        output_path?: string
        total_entries?: number
        period_suggestion?: ImportPeriodSuggestion
        day_book_report?: DayBookReport
      }

      setOutputPath(reportSummary.output_path || 'direct_entries')
      setEntryCount(reportSummary.total_entries || 0)
      if (reportSummary.period_suggestion) {
        setImportPeriodSuggestion(reportSummary.period_suggestion)
        applyPeriodSuggestion(reportSummary.period_suggestion)
      }
      if (reportSummary.day_book_report) {
        setDayBookReport(reportSummary.day_book_report)
      } else {
        const report = await api.getDayBookReport(jobId)
        setDayBookReport(report)
      }

      message.success({
        content: `序时簿解析完成，已生成 ${reportSummary.total_entries || 0} 条分录`,
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
    try {
      // 确保有导入任务 ID
      let jobId = currentJobId
      if (!jobId) {
        // 创建导入任务
        const job = await api.createImportJob('临时组织', 'ai_generated', currentLedgerId)
        jobId = job.id
        setCurrentJobId(jobId)
        setCurrentOrgId(job.organization_id)
      }

      // 调用 API 上传文件
      const result = await api.uploadFile(jobId, file, selectedTypes)

      const fileInfo: UploadedFile = {
        name: file.name,
        size: file.size,
        fileType: file.type || 'unknown',
        jobId: jobId,
        fileId: result.id,
      }
      setUploadedFiles(prev => [...prev, fileInfo])

      // 上传后自动触发生成（同步处理所有文件）
      message.loading({ content: '正在解析上传文件，请稍候...', key: 'parsing' })
      try {
        const syncResult = await api.processImportJobSync(jobId)
        const reportSummary = syncResult.report as {
          output_path?: string
          total_entries?: number
          register_summary?: Array<{
            filename: string
            register_summary?: string
            module_registrations?: UploadedFile['moduleRegistrations']
            module_label?: string
          }>
        }
        setOutputPath(reportSummary.output_path || 'register_ledger')
        setEntryCount(reportSummary.total_entries || 0)

        const fileRegister = reportSummary.register_summary?.find((item) => item.filename === file.name)
        setUploadedFiles(prev => prev.map((item) => {
          if (item.name !== file.name) return item
          const registerItem = fileRegister as {
            module_registrations?: UploadedFile['moduleRegistrations']
            semantic_tags?: string[]
            risk_hints?: UploadedFile['riskHints']
            semantic_decomposition?: { decomposition_source?: string }
            archive_path?: string
            archive_context?: { archive_category?: string; project_name?: string; archive_path?: string }
          } | undefined
          return {
            ...item,
            registerSummary: registerItem?.module_registrations?.length
              ? registerItem.module_registrations.map((reg) => reg.module_label).join('、')
              : undefined,
            moduleRegistrations: registerItem?.module_registrations,
            semanticTags: registerItem?.semantic_tags,
            riskHints: registerItem?.risk_hints,
            decompositionSource: registerItem?.semantic_decomposition?.decomposition_source,
            archivePath: registerItem?.archive_path || registerItem?.archive_context?.archive_path,
            archiveCategory: registerItem?.archive_context?.archive_category,
            projectName: registerItem?.archive_context?.project_name,
          }
        }))

        message.success({ content: `文件已登记为模块台账底稿：${file.name}`, key: 'parsing' })
        console.debug('Parse report:', syncResult)
      } catch (err) {
        message.warning({ content: `${file.name} 上传成功，但解析失败：${err instanceof Error ? err.message : String(err)}`, key: 'parsing' })
      }
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error)
      message.error(`${file.name} 上传失败：${detail}`)
      console.error('Upload error:', detail, error)
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
      const job = await api.createImportJob('临时组织', sourceType, currentLedgerId)
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
      if (!currentJobId || entryCount === 0) {
        message.warning('请先上传序时簿并完成解析')
        return
      }
      let usePeriodId = periodId
      if (!usePeriodId) {
        if (!currentOrgId || !periodCode || !periodStart || !periodEnd) {
          message.warning('系统未能自动识别会计期间，请确认期间信息后重试')
          return
        }
        try {
          const period = await api.createAccountingPeriod({
            organization_id: currentOrgId,
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
      navigate(`${stepPath(4)}?${nextParams.toString()}`)
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

    let usePeriodId = periodId
    if (!usePeriodId) {
      if (!currentOrgId || !periodCode || !periodStart || !periodEnd) {
        message.warning('请先选择/创建会计期间（输入期间编码与起止日期）')
        return
      }
      try {
        const period = await api.createAccountingPeriod({
          organization_id: currentOrgId,
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

  const addManualRow = () => {
    const maxLineNo = manualRows.reduce((max, row) => Math.max(max, row.entry_line_no), 0)
    setManualRows(prev => [...prev, createManualLine(maxLineNo + 1)])
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
    for (const row of manualRows) {
      if (!row.summary.trim() || !row.account_code.trim() || !row.account_name.trim()) {
        message.warning(`第 ${row.entry_line_no} 行请填写摘要，并从会计科目表选择科目代码和科目名称`)
        return false
      }
      if (Number(row.debit_amount || 0) > 0 && Number(row.credit_amount || 0) > 0) {
        message.warning(`第 ${row.entry_line_no} 行不能同时填写借方和贷方金额，请按会计分录方向只填一边`)
        return false
      }
      if (Number(row.debit_amount || 0) === 0 && Number(row.credit_amount || 0) === 0) {
        message.warning(`第 ${row.entry_line_no} 行借方或贷方至少填写一个金额，金额不能为 0`)
        return false
      }
      if (getCounterpartyHintStatus(row) === 'required_missing') {
        message.warning(`第 ${row.entry_line_no} 行属于往来性质科目，请填写客户、供应商或其他对方单位，便于后续对账和审计追踪`)
        return false
      }
    }
    if (!isBalanced) {
      message.warning('本张凭证借方合计与贷方合计不一致，请调平后再提交')
      return false
    }
    return true
  }

  const submitManualVoucher = async () => {
    if (!validateManualRows()) return
    setManualSubmitting(true)
    try {
      const context = await ensurePeriod('manual_entry')
      const drafts: EntryDraft[] = manualRows.map(row => ({
        voucher_no: manualVoucherNo,
        voucher_date: manualVoucherDate,
        account_code: row.account_code.trim(),
        account_name: row.account_name.trim(),
        summary: row.summary.trim(),
        debit_amount: roundAmount(Number(row.debit_amount || 0)),
        credit_amount: roundAmount(Number(row.credit_amount || 0)),
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
          account_source: row.account_source,
          used_custom_account_entry: usedCustomAccountEntry,
          counterparty_hint_status: getCounterpartyHintStatus(row),
          archive_context: '人工凭证录入：已保存期间、日期、凭证字/号、科目选择来源和往来单位提示状态，metadata 仅用于项目归档与追踪，不改变标准 AccountingEntry 字段落库口径。',
        },
        tags: [],
      }))
      const result = await api.commitManualEntries(context.periodId, drafts)
      message.success(`人工凭证已提交 ${result.count} 条分录`)
      const nextParams = new URLSearchParams()
      nextParams.set('inputMode', inputMode)
      nextParams.set('jobId', String(result.job_id))
      nextParams.set('periodId', String(context.periodId))
      navigate(`${stepPath(4)}?${nextParams.toString()}`)
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error)
      message.error(`提交人工凭证失败：${detail}`)
    } finally {
      setManualSubmitting(false)
    }
  }

  const manualColumns: ColumnsType<ManualEntryLine> = [
    {
      title: '行号',
      dataIndex: 'entry_line_no',
      key: 'entry_line_no',
      width: 90,
      render: (value: number, record) => (
        <InputNumber min={1} precision={0} value={value} onChange={(val) => updateManualRow(record.key, 'entry_line_no', val)} />
      )
    },
    {
      title: '摘要',
      dataIndex: 'summary',
      key: 'summary',
      width: 180,
      render: (value: string, record) => (
        <Input value={value} placeholder="例如：收到货款" onChange={(e) => updateManualRow(record.key, 'summary', e.target.value)} />
      )
    },
    {
      title: '科目代码',
      dataIndex: 'account_code',
      key: 'account_code',
      width: 190,
      render: (value: string, record) => (
        <Select
          showSearch
          value={value || undefined}
          placeholder="选择科目代码"
          loading={coaLoading}
          options={accountCodeOptions}
          optionFilterProp="label"
          onSearch={setAccountSearchKeyword}
          onChange={(accountCode) => selectAccountForRow(record.key, accountCode)}
          notFoundContent={
            <Button type="link" onClick={() => navigateToCoa(accountSearchKeyword)}>
              去会计科目模块新增
            </Button>
          }
          style={{ width: '100%' }}
        />
      )
    },
    {
      title: '科目名称',
      dataIndex: 'account_name',
      key: 'account_name',
      width: 190,
      render: (_value: string, record) => (
        <Select
          showSearch
          value={record.account_code || undefined}
          placeholder="选择科目名称"
          loading={coaLoading}
          options={accountNameOptions}
          optionFilterProp="label"
          onSearch={setAccountSearchKeyword}
          onChange={(accountCode) => selectAccountForRow(record.key, accountCode)}
          notFoundContent={
            <Button type="link" onClick={() => navigateToCoa(accountSearchKeyword)}>
              去会计科目模块新增
            </Button>
          }
          style={{ width: '100%' }}
        />
      )
    },
    {
      title: '借方金额',
      dataIndex: 'debit_amount',
      key: 'debit_amount',
      width: 140,
      render: (value: number, record) => (
        <InputNumber min={0} precision={2} value={value} onChange={(val) => updateManualRow(record.key, 'debit_amount', val)} />
      )
    },
    {
      title: '贷方金额',
      dataIndex: 'credit_amount',
      key: 'credit_amount',
      width: 140,
      render: (value: number, record) => (
        <InputNumber min={0} precision={2} value={value} onChange={(val) => updateManualRow(record.key, 'credit_amount', val)} />
      )
    },
    {
      title: '对方单位',
      dataIndex: 'counterparty',
      key: 'counterparty',
      width: 210,
      render: (value: string, record) => {
        const hintStatus = getCounterpartyHintStatus(record)
        return (
          <Space direction="vertical" size={4} style={{ width: '100%' }}>
            <Select
              showSearch
              allowClear
              value={value || undefined}
              placeholder="选择或输入客户/供应商"
              loading={counterpartiesLoading}
              options={counterpartyOptions}
              optionFilterProp="label"
              onSearch={(keyword) => updateManualRow(record.key, 'counterparty', keyword)}
              onChange={(nextValue) => updateManualRow(record.key, 'counterparty', nextValue || '')}
              onBlur={() => updateManualRow(record.key, 'counterparty', value)}
              style={{ width: '100%' }}
            />
            {hintStatus === 'required_missing' && (
              <Text type="warning" style={{ fontSize: 12 }}>往来科目建议填写对方单位</Text>
            )}
          </Space>
        )
      }
    },
    {
      title: '操作',
      key: 'action',
      width: 80,
      render: (_, record) => (
        <Button danger type="text" icon={<DeleteOutlined />} onClick={() => removeManualRow(record.key)} />
      )
    },
  ]

  if (isManualEntry) {
    return (
      <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
        <Steps
          current={currentStep}
          items={[
            { title: '选择模式' },
            { title: '人工录入' },
            { title: '生成草稿' },
            { title: '复核调整' },
            { title: '确认导出' }
          ]}
          style={{ marginBottom: '32px' }}
        />

        <FlowNav prev={stepPath(1)} next={stepPath(4)} style={{ marginBottom: '16px' }} />

        <Title level={4}>传统人工录入凭证</Title>
        <Text type="secondary">请录入一张标准会计凭证，系统校验分录借贷平衡后形成待复核分录，并进入复核调整步骤。</Text>

        <Card style={{ marginTop: '16px' }}>
          <Title level={5}>1. 凭证基本信息</Title>
          <Space wrap align="start">
            <Space direction="vertical" size={4}>
              <Text>凭证字</Text>
              <Select
                value={manualVoucherType}
                options={VOUCHER_TYPE_OPTIONS}
                onChange={setManualVoucherType}
                style={{ width: 120 }}
              />
            </Space>
            <Space direction="vertical" size={4}>
              <Text>凭证号</Text>
              <Input
                value={manualVoucherNumber}
                onChange={(e) => setManualVoucherNumber(e.target.value)}
                placeholder="001"
                style={{ width: 140 }}
              />
              <Text type="secondary" style={{ fontSize: 12 }}>默认建议：001</Text>
            </Space>
            <Space direction="vertical" size={4}>
              <Text>凭证日期</Text>
              <DatePicker
                value={manualVoucherDate ? dayjs(manualVoucherDate) : null}
                placeholder="凭证日期"
                disabledDate={disableVoucherDate}
                onChange={handleVoucherDateChange}
              />
              {periodStart && periodEnd && (
                <Text type="secondary" style={{ fontSize: 12 }}>日期范围：{periodStart} 至 {periodEnd}</Text>
              )}
            </Space>
            <Space direction="vertical" size={4}>
              <Text>兼容凭证字号</Text>
              <Input value={manualVoucherNo} readOnly style={{ width: 160 }} />
              <Text type="secondary" style={{ fontSize: 12 }}>提交时写入原 voucher_no 字段</Text>
            </Space>
          </Space>
        </Card>

        <Card style={{ marginTop: '16px' }}>
          <Title level={5}>2. 选择会计期间</Title>
          <Space direction="vertical" style={{ width: '100%' }}>
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
              onChange={(value) => value ? handleSelectPeriod(value) : setPeriodId(null)}
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
          </Space>
        </Card>

        <Card style={{ marginTop: '16px' }}>
          <Space style={{ marginBottom: '16px', width: '100%', justifyContent: 'space-between' }}>
            <Title level={5} style={{ margin: 0 }}>3. 分录明细</Title>
            <Space>
              <Button onClick={() => navigateToCoa()}>
                去会计科目模块新增
              </Button>
              <Button type="dashed" icon={<PlusOutlined />} onClick={addManualRow}>新增行</Button>
            </Space>
          </Space>
          <Alert
            title="科目选择说明"
            description="分录科目从会计科目表选择并自动填入代码和名称；科目不存在时，请跳转到会计科目模块新增，正式生效日期由会计科目模块人工确认。"
            type="info"
            showIcon
            style={{ marginBottom: '16px' }}
          />
          <Table
            columns={manualColumns}
            dataSource={manualRows}
            rowKey="key"
            pagination={false}
            size="small"
            scroll={{ x: 1220 }}
          />
          <div style={{ marginTop: '16px', display: 'flex', gap: '16px', alignItems: 'center' }}>
            <Text strong>借方合计：¥{debitTotal.toFixed(2)}</Text>
            <Text strong>贷方合计：¥{creditTotal.toFixed(2)}</Text>
            <Tag color={isBalanced ? 'green' : 'red'}>
              {isBalanced ? '借贷平衡' : `差额：¥${Math.abs(balanceDiff).toFixed(2)}`}
            </Tag>
          </div>
          {!isBalanced && (
            <Alert
              title="借贷未平衡"
              description="一张凭证的分录借方合计必须等于贷方合计，且借贷双方金额均大于 0，平衡后才能提交。"
              type="warning"
              showIcon
              style={{ marginTop: '16px' }}
            />
          )}
        </Card>

        <div style={{ marginTop: '24px', display: 'flex', gap: '12px' }}>
          <Button onClick={() => navigate(`${stepPath(1)}?inputMode=${inputMode}`)}>
            上一步
          </Button>
          <Button
            type="primary"
            loading={manualSubmitting}
            onClick={submitManualVoucher}
            disabled={!isBalanced}
          >
            提交人工凭证，进入复核
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
            { title: '序时簿导入' },
            { title: '生成草稿' },
            { title: '复核调整' },
            { title: '确认导出' }
          ]}
          style={{ marginBottom: '32px' }}
        />

        <FlowNav prev={stepPath(1)} next={stepPath(4)} style={{ marginBottom: '16px' }} />

        <Title level={4}>序时簿导入生成会计凭证</Title>
        <Text type="secondary">
          上传按日期顺序登记的序时簿（Excel/CSV），系统将按凭证号分组生成正式会计分录，并自动识别主要会计月份。
        </Text>

        <Alert
          title="稳定输出路径"
          description="序时簿导入走 direct_entries 路径：解析后直接生成 accounting_entries，跳过 AI 草稿步骤，进入复核调整。"
          type="info"
          showIcon
          style={{ marginTop: '16px' }}
        />

        <Card style={{ marginTop: '16px' }}>
          <Title level={5}>1. 上传序时簿文件</Title>
          <Dragger
            name="daybook"
            multiple={false}
            disabled={processingUpload}
            beforeUpload={handleDayBookUpload}
            accept=".xlsx,.xls,.csv"
            style={{ padding: '32px' }}
          >
            <p className="ant-upload-drag-icon">
              <InboxOutlined />
            </p>
            <p className="ant-upload-text">点击或拖拽序时簿文件到此区域</p>
            <p className="ant-upload-hint">
              请保留凭证号、日期、科目、借贷金额、对方单位等列。系统会按凭证号合并、校验借贷平衡并检测跳号。
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
        </Card>

        {dayBookReport && (
          <Card style={{ marginTop: '16px' }}>
            <Title level={5}>2. 序时簿检测报告</Title>
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
                description="请复核不平衡凭证后再结账，系统已保留全部分录供核对。"
                type="warning"
                showIcon
                style={{ marginTop: '16px' }}
              />
            )}
          </Card>
        )}

        <Card style={{ marginTop: '16px' }}>
          <Title level={5}>{dayBookReport ? '3' : '2'}. 会计期间（自动识别）</Title>
          <Space direction="vertical" style={{ width: '100%' }}>
            {importPeriodReason && <Alert title={importPeriodReason} type="info" showIcon />}
            {importPeriodSuggestion?.detected_month && (
              <Text type="secondary">识别主要月份：{importPeriodSuggestion.detected_month}</Text>
            )}
            <Input
              placeholder="期间编码，如 2026-03"
              value={periodCode}
              onChange={(e) => setPeriodCode(e.target.value)}
              style={{ maxWidth: 240 }}
            />
            <Space>
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
            <Text type="secondary">系统根据序时簿凭证日期自动推荐期间；如无匹配 open 期间，提交时将创建新期间。</Text>
          </Space>
        </Card>

        <div style={{ marginTop: '24px', display: 'flex', gap: '12px' }}>
          <Button onClick={() => navigate(`${stepPath(1)}?inputMode=${inputMode}`)}>
            上一步
          </Button>
          <Button
            type="primary"
            onClick={handleNext}
            disabled={entryCount === 0}
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

      <FlowNav prev={stepPath(1)} next={stepPath(3)} style={{ marginBottom: '16px' }} />

      <Title level={4}>导入原始资料</Title>
        <Text type="secondary">
          当前为 AI 智能生成路径。系统会先对底稿做语义分解（收入/成本/发票/往来/资金等维度），自动登记到一个或多个功能模块台账，并按项目自动归档底稿资料，便于后续在项目中检索管理；不直接写入会计分录。
        </Text>

      {outputPath && (
        <Alert
          title={`当前输出路径：${outputPath}`}
          description={outputPath === 'register_ledger'
            ? '原始资料识别后登记到功能模块台账（非会计分录），下一步结合台账证据生成凭证草稿。'
            : '结构化文件已解析为分录预览，请改用序时簿导入模式生成正式凭证。'}
          type="info"
          showIcon
          style={{ marginTop: '12px' }}
        />
      )}

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
            支持 PDF/图片/Excel/CSV 等。资料将保存为底稿、AI 解析登记到功能模块台账，并自动归档到项目目录；不直接生成会计分录。
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

      <Card style={{ marginTop: '16px' }}>
        <Title level={5}>3. 选择会计期间</Title>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Input
            placeholder="期间编码，如 2026-01"
            value={periodCode}
            onChange={(e) => setPeriodCode(e.target.value)}
            style={{ maxWidth: 240 }}
          />
          <Space>
            <DatePicker
              placeholder="期间开始"
              onChange={(_, dateString) => setPeriodStart(typeof dateString === 'string' ? dateString : '')}
            />
            <DatePicker
              placeholder="期间结束"
              onChange={(_, dateString) => setPeriodEnd(typeof dateString === 'string' ? dateString : '')}
            />
          </Space>
          <Typography.Text type="secondary">
            会计期间是凭证生成和后续复核的基础；未选择期间无法进入下一步。
          </Typography.Text>
        </Space>
      </Card>

      <div style={{ marginTop: '24px', display: 'flex', gap: '12px' }}>
        <Button onClick={() => navigate(`${stepPath(1)}?inputMode=${inputMode}`)}>
          上一步
        </Button>
        <Button
          type="primary"
          onClick={handleNext}
          disabled={uploadedFiles.length === 0}
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
