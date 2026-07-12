/**
 * 财务总账导航分类 — 对齐 bookkeeping-v1 文档主线与常见总账软件模块划分。
 *
 * 业务顺序（L6 路径 A）：
 * 凭证入账 → 期末处理（损益结转/结账）→ 财务报表编制与导出 → 账簿查询核对
 */
export type LedgerNavItem = {
  key: string
  label: string
  path: string
  description?: string
  /** 文档 F 编号，便于验收对照 */
  docRef?: string
}

export type LedgerNavGroup = {
  key: string
  label: string
  items: LedgerNavItem[]
}

export const LEDGER_WORKFLOW_PHASES = [
  {
    key: 'voucher',
    title: '凭证处理',
    summary: '序时簿导入、复核、确认入账与过账',
    docStep: 'A3–A9',
  },
  {
    key: 'period-close',
    title: '期末处理',
    summary: '损益结转、结账与期间状态管理',
    docStep: 'A10',
    path: '/accounting-periods',
  },
  {
    key: 'reports',
    title: '财务报表',
    summary: '科目余额表、资产负债表、利润表、现金流量表编制与导出',
    docStep: 'A11',
    path: '/reports',
  },
  {
    key: 'ledger-books',
    title: '账簿查询',
    summary: '总账、明细账与凭证查询勾稽',
    docStep: 'A11 延伸',
  },
] as const

/** 侧栏与子模块入口 — 单一真值源 */
export const LEDGER_NAV_GROUPS: LedgerNavGroup[] = [
  {
    key: 'ledger-setup',
    label: '基础设置',
    items: [
      { key: 'dimensions', label: '核算结构', path: '/ledger/dimensions', docRef: 'F2' },
      { key: 'books', label: '账簿管理', path: '/ledger/books', docRef: 'F1' },
    ],
  },
  {
    key: 'ledger-vouchers',
    label: '凭证处理',
    items: [
      { key: 'import', label: '序时簿导入', path: '/ledger/vouchers/step/1', docRef: 'F4' },
      { key: 'create', label: '手工录入凭证', path: '/ledger/vouchers/create', docRef: 'F10' },
      { key: 'entries', label: '凭证查询', path: '/ledger/entries', docRef: 'F10' },
      { key: 'import-jobs', label: '导入任务管理', path: '/ledger/import-jobs' },
    ],
  },
  {
    key: 'ledger-query',
    label: '账簿查询',
    items: [
      { key: 'general-ledger', label: '总账', path: '/ledger/general-ledger', docRef: 'F9' },
      { key: 'subsidiary-ledger', label: '明细账', path: '/ledger/subsidiary-ledger', docRef: 'F9' },
    ],
  },
  {
    key: 'period-close',
    label: '期末处理',
    items: [
      {
        key: 'accounting-periods',
        label: '损益结转与结账',
        path: '/accounting-periods',
        description: '创建期间、损益结转、结账/反结账、结转校验',
        docRef: 'F7',
      },
    ],
  },
  {
    key: 'financial-reports',
    label: '财务报表',
    items: [
      { key: 'reports-hub', label: '报表编制中心', path: '/reports', docRef: 'F8' },
      { key: 'trial-balance', label: '科目余额表', path: '/reports/trial-balance', docRef: 'F8' },
      { key: 'balance-sheet', label: '资产负债表', path: '/reports/balance-sheet', docRef: 'F8' },
      { key: 'income-statement', label: '利润表', path: '/reports/income-statement', docRef: 'F8' },
      { key: 'cash-flow-statement', label: '现金流量表', path: '/reports/cash-flow-statement', docRef: 'F8' },
    ],
  },
]

/** 工作台快捷入口（扁平列表） */
export const LEDGER_WORKSPACE_FUNCTIONS: Array<{
  key: string
  label: string
  path: string
  group: string
}> = [
  { key: 'import', label: '序时簿导入', path: '/ledger/vouchers/step/1', group: '凭证处理' },
  { key: 'entries', label: '凭证查询', path: '/ledger/entries', group: '凭证处理' },
  { key: 'periods', label: '损益结转与结账', path: '/accounting-periods', group: '期末处理' },
  { key: 'reports', label: '报表编制中心', path: '/reports', group: '财务报表' },
  { key: 'dimensions', label: '核算结构', path: '/ledger/dimensions', group: '基础设置' },
  { key: 'general-ledger', label: '总账', path: '/ledger/general-ledger', group: '账簿查询' },
  { key: 'subsidiary-ledger', label: '明细账', path: '/ledger/subsidiary-ledger', group: '账簿查询' },
  { key: 'trial-balance', label: '科目余额表', path: '/reports/trial-balance', group: '财务报表' },
  { key: 'balance-sheet', label: '资产负债表', path: '/reports/balance-sheet', group: '财务报表' },
  { key: 'income-statement', label: '利润表', path: '/reports/income-statement', group: '财务报表' },
  { key: 'cash-flow-statement', label: '现金流量表', path: '/reports/cash-flow-statement', group: '财务报表' },
]

export function reportPathWithPeriod(path: string, periodId?: number | null): string {
  if (!periodId) return path
  const sep = path.includes('?') ? '&' : '?'
  return `${path}${sep}period_id=${periodId}`
}
