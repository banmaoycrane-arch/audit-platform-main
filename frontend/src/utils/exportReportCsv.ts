import type { BalanceSheetReport, IncomeStatementReport, TrialBalanceReport } from '../api/client'

const CATEGORY_LABEL: Record<string, string> = {
  asset: '资产',
  liability: '负债',
  common: '共同',
  equity: '所有者权益',
  cost: '成本',
  profit: '损益',
}

function escapeCsvCell(value: string | number): string {
  const text = String(value ?? '')
  if (/[",\n\r]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`
  }
  return text
}

export function downloadCsv(filename: string, rows: Array<Array<string | number>>): void {
  const lines = rows.map((row) => row.map(escapeCsvCell).join(','))
  const blob = new Blob(['\uFEFF' + lines.join('\r\n')], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename.endsWith('.csv') ? filename : `${filename}.csv`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

function periodSlug(report: { period_code?: string; as_of_date?: string }, fallback: string): string {
  return report.period_code || report.as_of_date || fallback
}

function parseAmount(value: string | number | undefined): number {
  if (value === undefined || value === null || value === '') return 0
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

function reportHeaderRows(report: { ledger_name?: string; period_code?: string; as_of_date?: string }, title: string): string[][] {
  return [
    [title],
    [`编制单位：${report.ledger_name || '—'}`],
    [`会计期间：${report.period_code || '—'}${report.as_of_date ? `（截止 ${report.as_of_date}）` : ''}`],
    ['币种：人民币', '金额单位：元'],
    [],
  ]
}

export function exportTrialBalanceCsv(report: TrialBalanceReport): void {
  const slug = periodSlug(report, 'report')
  const rows = [
    ...reportHeaderRows(report, '科目余额表'),
    [
      '科目编码', '科目名称', '科目类别',
      '期初借方余额', '期初贷方余额', '本期借方发生额', '本期贷方发生额',
      '本年借方累计', '本年贷方累计', '期末借方余额', '期末贷方余额',
    ],
    ...report.rows.map((row) => [
      row.account_code,
      row.account_name,
      CATEGORY_LABEL[row.category] || row.category,
      row.opening_debit,
      row.opening_credit,
      row.period_debit,
      row.period_credit,
      row.ytd_debit,
      row.ytd_credit,
      row.closing_debit,
      row.closing_credit,
    ]),
    [
      '合计', '', '',
      report.totals.opening_debit,
      report.totals.opening_credit,
      report.totals.period_debit,
      report.totals.period_credit,
      report.totals.ytd_debit,
      report.totals.ytd_credit,
      report.totals.closing_debit,
      report.totals.closing_credit,
    ],
  ]
  downloadCsv(`科目余额表_${slug}.csv`, rows)
}

function classicHeaderRows(
  report: { ledger_name?: string; period_code?: string; as_of_date?: string },
  kind: 'balance_sheet' | 'income_statement' | 'cash_flow',
  title: string,
): string[][] {
  const ledger = report.ledger_name || '—'
  const asOf = report.as_of_date || '—'
  const period = report.period_code || ''
  const year = period.slice(0, 4) || asOf.slice(0, 4) || '—'
  if (kind === 'balance_sheet') {
    return [[title], [`编制单位：${ledger}`, `编制日期：${asOf}`, '单位：元'], []]
  }
  if (kind === 'income_statement') {
    return [[title], [`编制单位：${ledger}`, `填表日期：${asOf}`, '单位：元'], []]
  }
  return [[title], [`编制单位：${ledger}`, `${year}年`, '单位：元'], []]
}

function classicFooterRows(): string[][] {
  return [[], ['制表人：____________', '负责人：____________', '复核：____________']]
}

export function exportBalanceSheetCsv(report: BalanceSheetReport): void {
  const slug = periodSlug(report, 'report')
  const paired = report.classic_dual_column?.paired_rows || []
  const body: Array<Array<string | number>> = paired.length
    ? paired.map((row) => [
        row.asset_label,
        parseAmount(row.asset_opening as string | number | undefined),
        parseAmount(row.asset_closing as string | number | undefined),
        row.liability_label,
        parseAmount(row.liability_opening as string | number | undefined),
        parseAmount(row.liability_closing as string | number | undefined),
      ])
    : (report.statement_lines || []).map((line) => [
        line.label,
        parseAmount(line.opening_balance),
        parseAmount(line.closing_balance),
        '',
        '',
        '',
      ])
  downloadCsv(`资产负债表_${slug}.csv`, [
    ...classicHeaderRows(report, 'balance_sheet', '资产负债表'),
    ['资产', '年初数', '年末数', '负债及所有者权益', '年初数', '年末数'],
    ...body,
    ...classicFooterRows(),
  ])
}

const REVENUE_LABEL: Record<string, string> = {
  main_business_revenue: '一、营业收入',
  other_business_revenue: '其他业务收入',
  investment_income: '投资收益',
  non_operating_income: '营业外收入',
}

const EXPENSE_LABEL: Record<string, string> = {
  main_business_cost: '减：营业成本',
  other_business_cost: '其他业务成本',
  selling_expenses: '销售费用',
  admin_expenses: '管理费用',
  financial_expenses: '财务费用',
  asset_impairment_loss: '资产减值损失',
  non_operating_expense: '营业外支出',
}

export function exportIncomeStatementCsv(report: IncomeStatementReport, periodCode: string): void {
  const lines = report.statement_lines || []
  const body: Array<Array<string | number>> = lines.length
    ? lines.map((line) => [
        line.label,
        line.line_no,
        parseAmount(line.month_amount ?? line.current_amount),
        parseAmount(line.year_to_date_amount ?? line.ytd_amount),
      ])
    : (() => {
        const rows: Array<Array<string | number>> = []
        let line = 0
        for (const [key, value] of Object.entries(report.revenue)) {
          line += 1
          rows.push([line, REVENUE_LABEL[key] || key, value, report.ytd_revenue?.[key] ?? ''])
        }
        for (const [key, value] of Object.entries(report.expense)) {
          line += 1
          rows.push([line, EXPENSE_LABEL[key] || key, value, report.ytd_expense?.[key] ?? ''])
        }
        for (const [label, current, ytd] of [
          ['营业利润', report.operating_profit, report.ytd_operating_profit],
          ['利润总额', report.total_profit, report.ytd_total_profit],
          ['减：所得税费用', report.income_tax, report.ytd_income_tax],
          ['净利润', report.net_profit, report.ytd_net_profit],
        ] as const) {
          line += 1
          rows.push([line, label, current ?? '', ytd ?? ''])
        }
        return rows
      })()
  downloadCsv(`损益表_${periodCode || 'report'}.csv`, [
    ...classicHeaderRows(report, 'income_statement', '损益表'),
    ['财务项目', '行次', '本月数', '本年累计数'],
    ...body,
    ...classicFooterRows(),
  ])
}
