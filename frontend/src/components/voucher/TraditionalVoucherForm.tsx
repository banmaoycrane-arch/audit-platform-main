import {
  Button,
  DatePicker,
  Input,
  InputNumber,
  Select,
  Space,
  Switch,
  Tag,
  Typography,
  Alert,
} from 'antd'
import {
  CopyOutlined,
  DeleteOutlined,
  FileTextOutlined,
  PlusOutlined,
  PrinterOutlined,
  SaveOutlined,
} from '@ant-design/icons'
import dayjs, { type Dayjs } from 'dayjs'
import type { AccountingPeriod, ChartOfAccount, Counterparty } from '../../api/client'
import { AmountDenominationGrid } from './AmountDenominationGrid'
import { amountToChineseUpper, roundAmount } from './voucherAmountUtils'
import './TraditionalVoucherForm.css'

const { Text } = Typography

export interface VoucherEntryLine {
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

export interface TraditionalVoucherFormProps {
  voucherType: string
  voucherNumber: string
  voucherDate: string
  attachmentCount: number
  remark: string
  quickEntry: boolean
  rows: VoucherEntryLine[]
  debitTotal: number
  creditTotal: number
  isBalanced: boolean
  balanceDiff: number
  submitting: boolean
  periodId: number | null
  periodCode: string
  periodStart: string
  periodEnd: string
  periodSuggestion: string
  accountingPeriods: AccountingPeriod[]
  periodsLoading: boolean
  chartOfAccounts: ChartOfAccount[]
  coaLoading: boolean
  counterparties: Counterparty[]
  counterpartiesLoading: boolean
  preparerName: string
  voucherTypeOptions: Array<{ value: string; label: string }>
  onVoucherTypeChange: (value: string) => void
  onVoucherNumberChange: (value: string) => void
  onVoucherDateChange: (date: Dayjs | null) => void
  onAttachmentCountChange: (value: number) => void
  onRemarkChange: (value: string) => void
  onQuickEntryChange: (value: boolean) => void
  onSelectPeriod: (periodId: number) => void
  onPeriodCodeChange: (value: string) => void
  onPeriodStartChange: (value: string) => void
  onPeriodEndChange: (value: string) => void
  onUpdateRow: (key: string, field: keyof VoucherEntryLine, value: string | number | null) => void
  onSelectAccount: (key: string, accountCode: string) => void
  onAddRow: (afterKey?: string) => void
  onRemoveRow: (key: string) => void
  onNavigateToCoa: (keyword?: string) => void
  onAccountSearch: (keyword: string) => void
  getCounterpartyHintStatus: (row: VoucherEntryLine) => 'not_required' | 'provided' | 'required_missing'
  disableVoucherDate: (current: Dayjs) => boolean
  onSave: () => void
  onSaveAndNew: () => void
  onSaveAndCopy: () => void
  onClear: () => void
  onNewVoucher: () => void
  onOpenVoucherList: () => void
}

export function TraditionalVoucherForm({
  voucherType,
  voucherNumber,
  voucherDate,
  attachmentCount,
  remark,
  quickEntry,
  rows,
  debitTotal,
  creditTotal,
  isBalanced,
  balanceDiff,
  submitting,
  periodId,
  periodCode,
  periodStart,
  periodEnd,
  periodSuggestion,
  accountingPeriods,
  periodsLoading,
  chartOfAccounts,
  coaLoading,
  counterparties,
  counterpartiesLoading,
  preparerName,
  voucherTypeOptions,
  onVoucherTypeChange,
  onVoucherNumberChange,
  onVoucherDateChange,
  onAttachmentCountChange,
  onRemarkChange,
  onQuickEntryChange,
  onSelectPeriod,
  onPeriodCodeChange,
  onPeriodStartChange,
  onPeriodEndChange,
  onUpdateRow,
  onSelectAccount,
  onAddRow,
  onRemoveRow,
  onNavigateToCoa,
  onAccountSearch,
  getCounterpartyHintStatus,
  disableVoucherDate,
  onSave,
  onSaveAndNew,
  onSaveAndCopy,
  onClear,
  onNewVoucher,
  onOpenVoucherList,
}: TraditionalVoucherFormProps) {
  const activeAccounts = chartOfAccounts.filter(account => account.status === 'active')
  const accountOptions = activeAccounts.map(account => ({
    value: account.code,
    label: `${account.code} ${account.name}`,
  }))

  const counterpartyOptions = counterparties
    .filter(counterparty => counterparty.is_active)
    .map(counterparty => ({
      value: counterparty.name,
      label: `${counterparty.name}（${counterparty.role}）`,
    }))

  const amountHeader = (
    <div className="voucher-amount-header">
      {['亿', '千', '百', '十', '万', '千', '百', '十', '元', '角', '分'].map((label, index) => (
        <span key={`${label}-${index}`}>{label}</span>
      ))}
    </div>
  )

  return (
    <div className="voucher-sheet">
      <div className="voucher-toolbar no-print">
        <div className="voucher-toolbar-left">
          <Button onClick={onNewVoucher}>新增</Button>
          <Button icon={<FileTextOutlined />} onClick={onOpenVoucherList}>凭证列表</Button>
          <Button icon={<PrinterOutlined />} onClick={() => window.print()}>打印</Button>
        </div>
        <div className="voucher-toolbar-right">
          <Space size={8}>
            <Text type="secondary">快速录入</Text>
            <Switch checked={quickEntry} onChange={onQuickEntryChange} size="small" />
          </Space>
        </div>
      </div>

      <div className="voucher-header">
        <div className="voucher-title-block">
          <h3 className="voucher-title">记账凭证</h3>
          <span className="voucher-style-tag">记账凭证 | 极简风格</span>
        </div>
        <div className="voucher-meta">
          <div className="voucher-meta-item">
            <Select
              value={voucherType}
              options={voucherTypeOptions}
              onChange={onVoucherTypeChange}
              style={{ width: 72 }}
            />
            <Input
              value={voucherNumber}
              onChange={(event) => onVoucherNumberChange(event.target.value)}
              placeholder="001"
              style={{ width: 88 }}
            />
            <Text>号</Text>
          </div>
          <div className="voucher-meta-item">
            <Text>日期</Text>
            <DatePicker
              value={voucherDate ? dayjs(voucherDate) : null}
              disabledDate={disableVoucherDate}
              onChange={onVoucherDateChange}
            />
          </div>
          <div className="voucher-meta-item">
            <Text>附单据</Text>
            <InputNumber
              min={0}
              precision={0}
              value={attachmentCount}
              onChange={(value) => onAttachmentCountChange(Number(value || 0))}
              style={{ width: 72 }}
            />
            <Text>张</Text>
          </div>
          <div className="voucher-meta-item">
            <Text>备注</Text>
            <Input
              value={remark}
              onChange={(event) => onRemarkChange(event.target.value)}
              placeholder="可选"
              style={{ width: 180 }}
            />
          </div>
        </div>
      </div>

      <div className="voucher-period-bar no-print">
        <Text>会计期间</Text>
        <Select
          allowClear
          showSearch
          placeholder="选择 open/reopened 期间"
          loading={periodsLoading}
          value={periodId || undefined}
          options={accountingPeriods.map(period => ({
            value: period.id,
            label: `${period.period_code}（${period.start_date} 至 ${period.end_date}）`,
          }))}
          onChange={(value) => (value ? onSelectPeriod(value) : undefined)}
          style={{ minWidth: 280 }}
        />
        {periodStart && periodEnd && (
          <Text type="secondary">凭证日期范围：{periodStart} 至 {periodEnd}</Text>
        )}
        {!periodId && (
          <Space wrap>
            <Input
              placeholder="期间编码 2026-02"
              value={periodCode}
              onChange={(event) => onPeriodCodeChange(event.target.value)}
              style={{ width: 140 }}
            />
            <DatePicker
              value={periodStart ? dayjs(periodStart) : null}
              placeholder="期间开始"
              onChange={(date) => onPeriodStartChange(date ? date.format('YYYY-MM-DD') : '')}
            />
            <DatePicker
              value={periodEnd ? dayjs(periodEnd) : null}
              placeholder="期间结束"
              onChange={(date) => onPeriodEndChange(date ? date.format('YYYY-MM-DD') : '')}
            />
          </Space>
        )}
      </div>

      {periodSuggestion && (
        <Alert className="voucher-balance-hint no-print" title={periodSuggestion} type="info" showIcon />
      )}

      <div className="voucher-table-wrap">
        <table className="voucher-table">
          <thead>
            <tr>
              <th className="col-line">行号</th>
              <th className="col-summary">摘要</th>
              <th className="col-account">科目</th>
              <th className="col-amount">
                借方金额
                {amountHeader}
              </th>
              <th className="col-amount">
                贷方金额
                {amountHeader}
              </th>
              <th className="col-actions no-print">操作</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const counterpartyHint = getCounterpartyHintStatus(row)
              return (
                <tr key={row.key}>
                  <td className="voucher-line-no">{row.entry_line_no}</td>
                  <td>
                    <input
                      className="voucher-cell-input"
                      value={row.summary}
                      placeholder="摘要"
                      onChange={(event) => onUpdateRow(row.key, 'summary', event.target.value)}
                    />
                  </td>
                  <td className="voucher-account-cell">
                    <Select
                      showSearch
                      allowClear
                      value={row.account_code || undefined}
                      placeholder="选择科目"
                      loading={coaLoading}
                      options={accountOptions}
                      optionFilterProp="label"
                      onSearch={onAccountSearch}
                      onChange={(accountCode) => accountCode && onSelectAccount(row.key, accountCode)}
                      notFoundContent={(
                        <Button type="link" onClick={() => onNavigateToCoa()}>
                          去会计科目模块新增
                        </Button>
                      )}
                    />
                    {counterpartyHint !== 'not_required' && (
                      <div className="voucher-counterparty-hint">
                        <Select
                          showSearch
                          allowClear
                          size="small"
                          value={row.counterparty || undefined}
                          placeholder="往来科目请填写对方单位"
                          loading={counterpartiesLoading}
                          options={counterpartyOptions}
                          optionFilterProp="label"
                          onSearch={(keyword) => onUpdateRow(row.key, 'counterparty', keyword)}
                          onChange={(value) => onUpdateRow(row.key, 'counterparty', value || '')}
                          style={{ width: '100%' }}
                        />
                      </div>
                    )}
                  </td>
                  <td>
                    <AmountDenominationGrid
                      value={row.debit_amount}
                      quickEntry={quickEntry}
                      inputNamePrefix={`debit-${row.key}`}
                      onChange={(amount) => {
                        onUpdateRow(row.key, 'debit_amount', amount)
                        if (amount > 0) onUpdateRow(row.key, 'credit_amount', 0)
                      }}
                    />
                  </td>
                  <td>
                    <AmountDenominationGrid
                      value={row.credit_amount}
                      quickEntry={quickEntry}
                      inputNamePrefix={`credit-${row.key}`}
                      onChange={(amount) => {
                        onUpdateRow(row.key, 'credit_amount', amount)
                        if (amount > 0) onUpdateRow(row.key, 'debit_amount', 0)
                      }}
                    />
                  </td>
                  <td className="no-print">
                    <div className="voucher-row-actions">
                      <Button
                        type="text"
                        size="small"
                        icon={<PlusOutlined />}
                        onClick={() => onAddRow(row.key)}
                      />
                      <Button
                        type="text"
                        size="small"
                        danger
                        icon={<DeleteOutlined />}
                        onClick={() => onRemoveRow(row.key)}
                      />
                    </div>
                  </td>
                </tr>
              )
            })}
            <tr className="voucher-total-row">
              <td colSpan={3}>
                <div className="voucher-total-label">合计</div>
                <div className="voucher-total-chinese">
                  {amountToChineseUpper(Math.max(debitTotal, creditTotal))}
                </div>
              </td>
              <td>
                <AmountDenominationGrid
                  value={debitTotal}
                  readOnly
                  inputNamePrefix="debit-total"
                />
              </td>
              <td>
                <AmountDenominationGrid
                  value={creditTotal}
                  readOnly
                  inputNamePrefix="credit-total"
                />
              </td>
              <td className="no-print" />
            </tr>
          </tbody>
        </table>
      </div>

      {!isBalanced && (debitTotal > 0 || creditTotal > 0) && (
        <Alert
          className="voucher-balance-hint no-print"
          title="借贷未平衡"
          description={`借方合计 ¥${debitTotal.toFixed(2)}，贷方合计 ¥${creditTotal.toFixed(2)}，差额 ¥${Math.abs(balanceDiff).toFixed(2)}`}
          type="warning"
          showIcon
        />
      )}

      <div className="voucher-footer">
        <div className="voucher-signatures">
          <span>制单人：{preparerName || '—'}</span>
          <span>审核人：—</span>
          {isBalanced && debitTotal > 0 && (
            <Tag color="green">借贷平衡</Tag>
          )}
        </div>
        <div className="voucher-actions no-print">
          <Button
            type="primary"
            icon={<SaveOutlined />}
            loading={submitting}
            disabled={!isBalanced}
            onClick={onSaveAndNew}
          >
            保存并新增
          </Button>
          <Button
            icon={<CopyOutlined />}
            loading={submitting}
            disabled={!isBalanced}
            onClick={onSaveAndCopy}
          >
            保存并复制
          </Button>
          <Button
            type="primary"
            ghost
            loading={submitting}
            disabled={!isBalanced}
            onClick={onSave}
          >
            保存
          </Button>
          <Button onClick={onClear}>清空</Button>
        </div>
      </div>
    </div>
  )
}
