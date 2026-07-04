import { useEffect, useMemo, useState } from 'react'
import { Card, message, Spin } from 'antd'
import { useNavigate, useParams } from 'react-router-dom'
import dayjs, { type Dayjs } from 'dayjs'
import {
  api,
  type AccountingPeriod,
  type ChartOfAccount,
  type Counterparty,
  type VoucherUpdatePayload,
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

export function VoucherEditPage() {
  const { voucherId } = useParams<{ voucherId: string }>()
  const navigate = useNavigate()
  const { currentLedgerId, user } = useAuthStore()
  const [loading, setLoading] = useState(false)
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
  const [rows, setRows] = useState<VoucherEntryLine[]>([])
  const [originalStatus, setOriginalStatus] = useState<string>('')

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

  const parsedVoucherId = Number(voucherId)

  useEffect(() => {
    if (!currentLedgerId || Number.isNaN(parsedVoucherId)) return
    const loadBaseData = async () => {
      setLoading(true)
      setPeriodsLoading(true)
      setCoaLoading(true)
      setCounterpartiesLoading(true)
      try {
        const [periods, accounts, loadedCounterparties, voucherResp] = await Promise.all([
          api.listAccountingPeriods(undefined, currentLedgerId),
          api.listChartOfAccounts(),
          api.listCounterparties(),
          api.getVoucher(parsedVoucherId),
        ])
        setAccountingPeriods(periods)
        setChartOfAccounts(accounts)
        setCounterparties(loadedCounterparties)

        const voucher = voucherResp.data
        setOriginalStatus(voucher.status || '')
        setVoucherType(voucher.voucher_type || '记')
        setVoucherNumber(voucher.voucher_number || '001')
        setVoucherDate(voucher.voucher_date)
        setAttachmentCount(voucher.attachment_count)
        setRemark(voucher.summary || '')
        setPeriodId(voucher.period_id || null)

        const matchedPeriod = voucher.period_id
          ? periods.find(p => p.id === voucher.period_id)
          : undefined
        if (matchedPeriod) {
          setPeriodCode(matchedPeriod.period_code)
          setPeriodStart(matchedPeriod.start_date)
          setPeriodEnd(matchedPeriod.end_date)
        } else if (voucher.voucher_date) {
          setPeriodCode(dayjs(voucher.voucher_date).format('YYYY-MM'))
          setPeriodStart(dayjs(voucher.voucher_date).startOf('month').format('YYYY-MM-DD'))
          setPeriodEnd(dayjs(voucher.voucher_date).endOf('month').format('YYYY-MM-DD'))
        }

        setPeriodSuggestion('')
        setRows(
          voucher.lines.length > 0
            ? voucher.lines.map((line, idx) => ({
                key: `${Date.now()}-${idx}`,
                entry_line_no: line.line_no,
                summary: line.summary || '',
                account_code: line.account_code || '',
                account_name: line.account_name || '',
                debit_amount: parseDecimal(line.debit_amount || 0).toNumber(),
                credit_amount: parseDecimal(line.credit_amount || 0).toNumber(),
                counterparty: line.counterparty || '',
                account_source: 'manual',
              }))
            : [createManualLine(1), createManualLine(2)],
        )
      } catch (error) {
        const detail = error instanceof Error ? error.message : String(error)
        message.error(`加载凭证失败：${detail}`)
        navigate('/ledger/vouchers')
      } finally {
        setLoading(false)
        setPeriodsLoading(false)
        setCoaLoading(false)
        setCounterpartiesLoading(false)
      }
    }
    void loadBaseData()
  }, [currentLedgerId, parsedVoucherId, navigate])

  const handleSelectPeriod = (selectedPeriodId: number) => {
    const period = accountingPeriods.find(p => p.id === selectedPeriodId)
    if (period) {
      setPeriodId(period.id)
      setPeriodCode(period.period_code)
      setPeriodStart(period.start_date)
      setPeriodEnd(period.end_date)
      setVoucherDate(prev => isDateInPeriod(prev, period.start_date, period.end_date) ? prev : period.start_date)
    }
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

  const buildPayload = (): VoucherUpdatePayload | null => {
    if (!currentLedgerId) {
      message.error('请先选择账簿')
      return null
    }
    if (!voucherDate) {
      message.error('请选择凭证日期')
      return null
    }
    if (!isBalanced) {
      message.error('凭证借贷方金额必须平衡且大于 0')
      return null
    }
    const activeLines = activeRows.filter(row =>
      row.account_code.trim() && (parseDecimal(row.debit_amount || 0).gt(0) || parseDecimal(row.credit_amount || 0).gt(0))
    )
    if (activeLines.length < 2) {
      message.error('至少需要两条有效分录')
      return null
    }
    return {
      ledger_id: currentLedgerId,
      period_id: periodId || undefined,
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
    if (Number.isNaN(parsedVoucherId)) return
    const payload = buildPayload()
    if (!payload) return
    setSubmitting(true)
    try {
      await api.updateVoucher(parsedVoucherId, payload)
      message.success('凭证更新成功')
      navigate('/ledger/vouchers')
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error)
      message.error(`更新凭证失败：${detail}`)
    } finally {
      setSubmitting(false)
    }
  }

  const handleSaveAndNew = () => {
    message.info('编辑模式下不支持保存并新增')
  }

  const handleSaveAndCopy = () => {
    message.info('编辑模式下不支持保存并复制')
  }

  const handleClear = () => {
    message.info('编辑模式下不支持清空，可返回列表重新选择')
  }

  if (!currentLedgerId) {
    return (
      <div style={{ padding: 24 }}>
        <Card>请先在顶部切换账簿。</Card>
      </div>
    )
  }

  if (loading) {
    return (
      <div style={{ padding: 24, display: 'flex', justifyContent: 'center' }}>
        <Spin size="large" tip="加载凭证中..." />
      </div>
    )
  }

  const readOnly = originalStatus === 'posted'

  return (
    <div style={{ padding: 24 }}>
      {readOnly && (
        <Card size="small" style={{ marginBottom: 16 }}>
          当前凭证已入账，不支持修改。如需调整，请红冲或反结账后重新录入。
        </Card>
      )}
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
        onSaveAndCopy={handleSaveAndCopy}
        onClear={handleClear}
        onNewVoucher={() => navigate('/ledger/vouchers/create')}
        onOpenVoucherList={() => navigate('/ledger/vouchers')}
      />
    </div>
  )
}
