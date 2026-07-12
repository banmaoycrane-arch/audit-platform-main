import { useEffect, useMemo, useState } from 'react'
import { Card, message } from 'antd'
import { useNavigate } from 'react-router-dom'
import dayjs, { type Dayjs } from 'dayjs'
import {
  api,
  type AccountingPeriod,
  type ChartOfAccount,
  type Counterparty,
  type VoucherCreatePayload,
} from '../api/client'
import { TraditionalVoucherForm, type VoucherEntryLine } from '../components/voucher/TraditionalVoucherForm'
import { useAuthStore } from '../stores/authStore'
import { Money, parseDecimal } from '../money'

const VOUCHER_TYPE_OPTIONS = ['记', '银', '收', '付', '转', '工'].map(value => ({ value, label: value }))
const CURRENT_ACCOUNT_CODES = ['1122', '2203', '2202', '1123', '1221', '2241']
const CURRENT_ACCOUNT_NAMES = ['应收', '预收', '应付', '预付', '其他应收', '其他应付']

const createManualLine = (lineNo: number): VoucherEntryLine => ({
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

const isCurrentAccount = (row: VoucherEntryLine) => {
  const accountCode = row.account_code.trim()
  const accountName = row.account_name.trim()
  return CURRENT_ACCOUNT_CODES.some(code => accountCode === code || accountCode.startsWith(`${code}.`))
    || CURRENT_ACCOUNT_NAMES.some(name => accountName.includes(name))
}

const getCounterpartyHintStatus = (row: VoucherEntryLine) => {
  if (!isCurrentAccount(row)) return 'not_required'
  return row.counterparty.trim() ? 'provided' : 'required_missing'
}

const isDateInPeriod = (date: string, start: string, end: string) => {
  if (!date || !start || !end) return true
  const voucherDate = dayjs(date)
  return !voucherDate.isBefore(dayjs(start), 'day') && !voucherDate.isAfter(dayjs(end), 'day')
}

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

export function VoucherCreatePage() {
  const navigate = useNavigate()
  const { currentLedgerId, user } = useAuthStore()
  const [accountingPeriods, setAccountingPeriods] = useState<AccountingPeriod[]>([])
  const [chartOfAccounts, setChartOfAccounts] = useState<ChartOfAccount[]>([])
  const [counterparties, setCounterparties] = useState<Counterparty[]>([])
  const [periodsLoading, setPeriodsLoading] = useState(false)
  const [coaLoading, setCoaLoading] = useState(false)
  const [counterpartiesLoading, setCounterpartiesLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [periodId, setPeriodId] = useState<number | null>(null)
  const [periodCode, setPeriodCode] = useState<string>('')
  const [periodStart, setPeriodStart] = useState<string>('')
  const [periodEnd, setPeriodEnd] = useState<string>('')
  const [periodSuggestion, setPeriodSuggestion] = useState<string>('')
  const [voucherType, setVoucherType] = useState<string>('记')
  const [voucherNumber, setVoucherNumber] = useState<string>('001')
  const [voucherDate, setVoucherDate] = useState<string>('')
  const [attachmentCount, setAttachmentCount] = useState<number>(0)
  const [remark, setRemark] = useState<string>('')
  const [quickEntry, setQuickEntry] = useState<boolean>(false)
  const [rows, setRows] = useState<VoucherEntryLine[]>([
    createManualLine(1),
    createManualLine(2),
    createManualLine(3),
    createManualLine(4),
    createManualLine(5),
  ])

  const activeRows = useMemo(() => rows.filter(row =>
    row.summary.trim()
    || row.account_code.trim()
    || row.account_name.trim()
    || parseDecimal(row.debit_amount || 0).gt(0)
    || parseDecimal(row.credit_amount || 0).gt(0)
    || row.counterparty.trim()
  ), [rows])

  const debitTotal = Money.sum(activeRows.map(row => Money.cny(row.debit_amount)))
  const creditTotal = Money.sum(activeRows.map(row => Money.cny(row.credit_amount)))
  const balanceDiff = debitTotal.sub(creditTotal)
  const isBalanced = debitTotal.isPositive() && creditTotal.isPositive() && balanceDiff.isZero()

  useEffect(() => {
    if (!currentLedgerId) return
    const loadBaseData = async () => {
      setPeriodsLoading(true)
      setCoaLoading(true)
      setCounterpartiesLoading(true)
      try {
        const [periods, accounts, loadedCounterparties] = await Promise.all([
          api.listAccountingPeriods(undefined, currentLedgerId),
          api.listChartOfAccounts(),
          api.listCounterparties(),
        ])
        setAccountingPeriods(periods)
        setChartOfAccounts(accounts)
        setCounterparties(loadedCounterparties)
        applyDefaultPeriodSelection(periods)
      } catch (error) {
        const detail = error instanceof Error ? error.message : String(error)
        message.error(`加载基础数据失败：${detail}`)
      } finally {
        setPeriodsLoading(false)
        setCoaLoading(false)
        setCounterpartiesLoading(false)
      }
    }
    void loadBaseData()
  }, [currentLedgerId])

  const applySelectedPeriod = (period: AccountingPeriod) => {
    setPeriodId(period.id)
    setPeriodCode(period.period_code)
    setPeriodStart(period.start_date)
    setPeriodEnd(period.end_date)
    setVoucherDate(prev => isDateInPeriod(prev, period.start_date, period.end_date) ? prev : period.start_date)
  }

  const applyDefaultPeriodSelection = (periods: AccountingPeriod[]) => {
    const selectedPeriod = periods.find(period => ['open', 'reopened'].includes(period.status))
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
      setVoucherDate(nextPeriod.start_date)
      setPeriodSuggestion(`当前没有 open/reopened 期间。系统已按上一已结账期间建议下一自然月 ${nextPeriod.period_code}，提交时会先创建该期间。`)
    }
  }

  const handleSelectPeriod = (selectedPeriodId: number) => {
    const period = accountingPeriods.find(p => p.id === selectedPeriodId)
    if (period) applySelectedPeriod(period)
  }

  const handleUpdateRow = (key: string, field: keyof VoucherEntryLine, value: string | number | null) => {
    setRows(prev => prev.map(row => row.key === key ? { ...row, [field]: value ?? '' } : row))
  }

  const handleSelectAccount = (key: string, accountCode: string) => {
    const account = chartOfAccounts.find(a => a.code === accountCode)
    setRows(prev => prev.map(row => {
      if (row.key !== key) return row
      return {
        ...row,
        account_code: accountCode,
        account_name: account?.name || '',
      }
    }))
  }

  const handleAddRow = (afterKey?: string) => {
    setRows(prev => {
      const index = afterKey ? prev.findIndex(row => row.key === afterKey) : prev.length - 1
      const insertIndex = index >= 0 ? index + 1 : prev.length
      const newLineNo = insertIndex + 1
      const newRow = createManualLine(newLineNo)
      const next = [...prev]
      next.splice(insertIndex, 0, newRow)
      return next.map((row, idx) => ({ ...row, entry_line_no: idx + 1 }))
    })
  }

  const handleRemoveRow = (key: string) => {
    setRows(prev => {
      const next = prev.filter(row => row.key !== key)
      return next.map((row, idx) => ({ ...row, entry_line_no: idx + 1 }))
    })
  }

  const handleVoucherDateChange = (date: Dayjs | null) => {
    setVoucherDate(date ? date.format('YYYY-MM-DD') : '')
  }

  const disableVoucherDate = (current: Dayjs) => {
    if (!periodStart || !periodEnd) return false
    return current.isBefore(dayjs(periodStart), 'day') || current.isAfter(dayjs(periodEnd), 'day')
  }

  const buildPayload = (): VoucherCreatePayload | null => {
    if (!currentLedgerId) {
      message.error('请先选择账簿')
      return null
    }
    if (!periodId) {
      message.error('请选择会计期间')
      return null
    }
    const period = accountingPeriods.find(p => p.id === periodId)
    if (!period) {
      message.error('所选期间不存在')
      return null
    }
    const organizationId = period.organization_id
    if (!voucherDate) {
      message.error('请选择凭证日期')
      return null
    }
    if (!isBalanced) {
      message.error('凭证借贷方金额必须平衡且大于 0')
      return null
    }
    const activeLines = activeRows.filter(row => row.account_code.trim() && (parseDecimal(row.debit_amount || 0).gt(0) || parseDecimal(row.credit_amount || 0).gt(0)))
    if (activeLines.length < 2) {
      message.error('至少需要两条有效分录')
      return null
    }
    return {
      ledger_id: currentLedgerId,
      organization_id: organizationId,
      period_id: periodId,
      voucher_type: voucherType,
      voucher_number: voucherNumber,
      voucher_date: voucherDate,
      summary: remark || undefined,
      attachment_count: attachmentCount,
      lines: activeLines.map(row => ({
        line_no: row.entry_line_no,
        summary: row.summary || remark || '',
        account_code: row.account_code,
        account_name: row.account_name || undefined,
        debit_amount: parseDecimal(row.debit_amount || 0).toFixed(2),
        credit_amount: parseDecimal(row.credit_amount || 0).toFixed(2),
        counterparty: row.counterparty || undefined,
      })),
    }
  }

  const handleSave = async () => {
    const payload = buildPayload()
    if (!payload) return
    setSubmitting(true)
    try {
      await api.createVoucher(payload)
      message.success('凭证保存成功')
      navigate('/ledger/entries')
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error)
      message.error(`保存凭证失败：${detail}`)
    } finally {
      setSubmitting(false)
    }
  }

  const handleSaveAndNew = async () => {
    const payload = buildPayload()
    if (!payload) return
    setSubmitting(true)
    try {
      await api.createVoucher(payload)
      message.success('凭证保存成功')
      setVoucherNumber(prev => {
        const num = parseInt(prev, 10)
        return Number.isNaN(num) ? '001' : String(num + 1).padStart(3, '0')
      })
      setRows([
        createManualLine(1),
        createManualLine(2),
        createManualLine(3),
        createManualLine(4),
        createManualLine(5),
      ])
      setRemark('')
      setAttachmentCount(0)
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error)
      message.error(`保存凭证失败：${detail}`)
    } finally {
      setSubmitting(false)
    }
  }

  const handleClear = () => {
    setVoucherType('记')
    setVoucherNumber('001')
    setVoucherDate(periodStart)
    setRemark('')
    setAttachmentCount(0)
    setRows([
      createManualLine(1),
      createManualLine(2),
      createManualLine(3),
      createManualLine(4),
      createManualLine(5),
    ])
  }

  if (!currentLedgerId) {
    return (
      <div style={{ padding: 24 }}>
        <Card>请先在顶部切换账簿。</Card>
      </div>
    )
  }

  return (
    <div style={{ padding: 24 }}>
      <TraditionalVoucherForm
        voucherType={voucherType}
        voucherNumber={voucherNumber}
        voucherDate={voucherDate}
        attachmentCount={attachmentCount}
        remark={remark}
        quickEntry={quickEntry}
        rows={rows}
        debitTotal={debitTotal}
        creditTotal={creditTotal}
        isBalanced={isBalanced}
        balanceDiff={balanceDiff}
        submitting={submitting}
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
        onVoucherTypeChange={setVoucherType}
        onVoucherNumberChange={setVoucherNumber}
        onVoucherDateChange={handleVoucherDateChange}
        onAttachmentCountChange={setAttachmentCount}
        onRemarkChange={setRemark}
        onQuickEntryChange={setQuickEntry}
        onSelectPeriod={handleSelectPeriod}
        onPeriodCodeChange={setPeriodCode}
        onPeriodStartChange={setPeriodStart}
        onPeriodEndChange={setPeriodEnd}
        onUpdateRow={handleUpdateRow}
        onSelectAccount={handleSelectAccount}
        onAddRow={handleAddRow}
        onRemoveRow={handleRemoveRow}
        onNavigateToCoa={() => navigate('/basic/coa')}
        onAccountSearch={() => undefined}
        getCounterpartyHintStatus={getCounterpartyHintStatus}
        disableVoucherDate={disableVoucherDate}
        onSave={handleSave}
        onSaveAndNew={handleSaveAndNew}
        onSaveAndCopy={() => undefined}
        onClear={handleClear}
        onNewVoucher={handleClear}
        onOpenVoucherList={() => navigate('/ledger/entries')}
      />
    </div>
  )
}
