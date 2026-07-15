import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Tabs } from 'antd'
import type { TabsProps } from 'antd'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'

interface RouteTab {
  key: string
  path: string
  title: string
  closable: boolean
  ledgerBound: boolean
}

const HOME_TAB: RouteTab = {
  key: '/workspace',
  path: '/workspace',
  title: '首页',
  closable: false,
  ledgerBound: false,
}

const EXACT_ROUTE_TITLES: Record<string, string> = {
  '/': '首页',
  '/workspace': '首页',
  '/agent': 'Agent 助手（实验）',
  '/ledger/workspace': '财务工作台',
  '/ledger/files': '证据云空间',
  '/ledger/entries': '凭证查询',
  '/ledger/books': '账簿管理',
  '/ledger/dimensions': '核算结构（科目+维度）',
  '/ledger/control-defects': '内控待办',
  '/ledger/general-ledger': '总账',
  '/ledger/subsidiary-ledger': '明细账',
  '/reports/trial-balance': '科目余额表',
  '/reports': '报表编制中心',
  '/reports/balance-sheet': '资产负债表',
  '/reports/income-statement': '利润表',
  '/reports/cash-flow-statement': '现金流量表',
  '/accounting-periods': '损益结转与结账',
  '/audit/workspace': '审计工作台',
  '/audit/dashboard': '审计协作台',
  '/audit/tasks': '审计任务',
  '/audit/review-requests': '复核请求',
  '/audit/bank-reconciliation': '银行调节表草稿',
  '/audit/confirmations': '往来函证控制表',
  '/audit/workpapers': '审计工作底稿',
  '/audit/workflow': '审计工作流',
  '/bank/workspace': '银行工作台（未开发）',
  '/bank/accounts': '银行账户',
  '/bank/third-party-accounts': '三方支付账户',
  '/bank/aggregate-accounts': '聚合账户',
  '/bank/journal': '银行日记账',
  '/bank/settings': '账户设置',
  '/bank/reconciliation': '自动对账',
  '/tax/connections': '税局直连（可选增值）',
  '/tax/workspace': '税务增值（可选）',
  '/tax/invoices': '发票文件管理',
  '/tax/assistant': '涉税助手',
  '/fixed-assets/workspace': '固定资产工作台（未开发）',
  '/fixed-assets/cards': '资产卡片',
  '/fixed-assets/depreciation': '折旧计提',
  '/inventory/workspace': '进销存工作台（未开发）',
  '/inventory/purchase-in': '采购入库',
  '/inventory/stock-flow': '库存流水',
  '/basic/workspace': '基础资料工作台',
  '/basic/coa': '会计科目',
  '/basic/org-units': '企业组织架构',
  '/basic/personnel': '员工/协作人员',
  '/basic/counterparties': '往来单位',
  '/basic/opening-balances': '期初数据',
  '/basic/materials': 'SKU/物料',
  '/basic/warehouses': '仓库',
  '/team-management': '团队管理',
  '/ledger-management': '账簿管理',
  '/scope-settings': '管理配置',
  '/parser-engine': '解析引擎管理',
  '/parser-engine/config': '解析引擎配置',
  '/projects': '项目管理',
  '/risks': '专项风险列表',
}

const MODULE_REGISTER_TITLES: Record<string, string> = {
  contract_register: '合同台账',
  counterparty_ledger: '往来款项台账',
  bank_cash_flow: '银行资金收支台账',
  tax_invoice: '发票台账',
  purchase: '采购业务台账',
  sales: '销售业务台账',
  inventory_receipt: '库存入库台账',
  payroll: '薪酬台账',
}

const MANAGEMENT_PATH_PREFIXES = [
  '/workspace',
  '/agent',
  '/team-management',
  '/ledger-management',
  '/scope-settings',
  '/parser-engine',
  '/projects',
]

function shouldSkipPath(pathname: string) {
  return pathname.startsWith('/login')
    || pathname.startsWith('/register')
    || pathname.startsWith('/onboarding')
}

function normalizePathname(pathname: string) {
  if (pathname === '/') return '/workspace'
  if (pathname === '/entries' || pathname === '/ledger/vouchers') return '/ledger/entries'
  return pathname
}

function shouldKeepSearch(pathname: string, search: string) {
  if (!search) return false
  if (pathname.startsWith('/ledger/vouchers/step/') && search.includes('jobId=')) return true
  if (pathname === '/ledger/dimensions' && search.includes('jobId=')) return true
  if (pathname === '/ledger/control-defects' && search.includes('jobId=')) return true
  if (pathname === '/audit/workpapers' && search.includes('version_id=')) return true
  return false
}

function getTabKey(pathname: string, search: string) {
  const normalizedPathname = normalizePathname(pathname)
  if (shouldKeepSearch(normalizedPathname, search)) {
    return `${normalizedPathname}${search}`
  }
  return normalizedPathname
}

function getTabPath(pathname: string, search: string) {
  const normalizedPathname = normalizePathname(pathname)
  if (shouldKeepSearch(normalizedPathname, search)) {
    return `${normalizedPathname}${search}`
  }
  return normalizedPathname
}

function formatFallbackTitle(pathname: string) {
  const lastSegment = pathname.split('/').filter(Boolean).pop()
  if (!lastSegment) return '页面'
  return decodeURIComponent(lastSegment).replace(/[-_]/g, ' ')
}

function getRouteTitle(pathname: string) {
  const normalizedPathname = normalizePathname(pathname)
  const exactTitle = EXACT_ROUTE_TITLES[normalizedPathname]
  if (exactTitle) return exactTitle

  const voucherStepMatch = normalizedPathname.match(/^\/ledger\/vouchers\/step\/(\d+)/)
  if (voucherStepMatch) return `凭证 Step ${voucherStepMatch[1]}`

  const accountingStepMatch = normalizedPathname.match(/^\/accounting\/step\/(\d+)/)
  if (accountingStepMatch) return `凭证 Step ${accountingStepMatch[1]}`

  const auditStepMatch = normalizedPathname.match(/^\/audit\/step\/(\d+)/)
  if (auditStepMatch) return `审计 Step ${auditStepMatch[1]}`

  if (/^\/audit\/tasks\/[^/]+/.test(normalizedPathname)) return '审计任务详情'
  if (/^\/audit\/review-requests\/[^/]+/.test(normalizedPathname)) return '复核请求详情'
  if (/^\/ledger\/vouchers\/draft\/[^/]+/.test(normalizedPathname)) return '凭证草稿'

  const registerMatch = normalizedPathname.match(/^\/registers\/([^/]+)/)
  if (registerMatch) {
    return MODULE_REGISTER_TITLES[registerMatch[1]] || '模块台账'
  }

  return formatFallbackTitle(normalizedPathname)
}

function isLedgerBoundPath(pathname: string) {
  const normalizedPathname = normalizePathname(pathname)
  if (MANAGEMENT_PATH_PREFIXES.some((prefix) => normalizedPathname === prefix || normalizedPathname.startsWith(`${prefix}/`))) {
    return false
  }
  return true
}

function createRouteTab(pathname: string, search: string): RouteTab {
  const normalizedPathname = normalizePathname(pathname)
  const key = getTabKey(normalizedPathname, search)
  return {
    key,
    path: getTabPath(normalizedPathname, search),
    title: getRouteTitle(normalizedPathname),
    closable: key !== HOME_TAB.key,
    ledgerBound: isLedgerBoundPath(normalizedPathname),
  }
}

function ensureHomeTab(tabs: RouteTab[]) {
  if (tabs.some((tab) => tab.key === HOME_TAB.key)) return tabs
  return [HOME_TAB, ...tabs]
}

export function RouteTabs() {
  const location = useLocation()
  const navigate = useNavigate()
  const { currentLedgerId } = useAuthStore()
  const previousLedgerIdRef = useRef(currentLedgerId)
  const [openTabs, setOpenTabs] = useState<RouteTab[]>([HOME_TAB])

  const activeKey = useMemo(
    () => getTabKey(location.pathname, location.search),
    [location.pathname, location.search],
  )

  useEffect(() => {
    if (shouldSkipPath(location.pathname)) return
    const currentTab = createRouteTab(location.pathname, location.search)
    setOpenTabs((previousTabs) => {
      const safeTabs = ensureHomeTab(previousTabs)
      const existingIndex = safeTabs.findIndex((tab) => tab.key === currentTab.key)
      if (existingIndex >= 0) {
        const nextTabs = [...safeTabs]
        nextTabs[existingIndex] = currentTab
        return nextTabs
      }
      return [...safeTabs, currentTab]
    })
  }, [location.pathname, location.search])

  useEffect(() => {
    if (previousLedgerIdRef.current === currentLedgerId) return
    previousLedgerIdRef.current = currentLedgerId

    setOpenTabs((previousTabs) => ensureHomeTab(previousTabs.filter((tab) => !tab.ledgerBound)))

    if (isLedgerBoundPath(location.pathname)) {
      navigate('/workspace', { replace: true })
    }
  }, [currentLedgerId, location.pathname, navigate])

  const closeTab = useCallback((targetKey: string) => {
    if (targetKey === HOME_TAB.key) return

    const targetIndex = openTabs.findIndex((tab) => tab.key === targetKey)
    if (targetIndex < 0) return

    const nextTabs = ensureHomeTab(openTabs.filter((tab) => tab.key !== targetKey))
    setOpenTabs(nextTabs)

    if (activeKey === targetKey) {
      const nextActiveTab = nextTabs[targetIndex] || nextTabs[targetIndex - 1] || HOME_TAB
      navigate(nextActiveTab.path)
    }
  }, [activeKey, navigate, openTabs])

  const handleEdit: TabsProps['onEdit'] = (targetKey, action) => {
    if (action === 'remove' && typeof targetKey === 'string') {
      closeTab(targetKey)
    }
  }

  const items = openTabs.map((tab) => ({
    key: tab.key,
    label: tab.title,
    closable: tab.closable,
  }))

  return (
    <div
      style={{
        background: '#f5f7fb',
        borderBottom: '1px solid #e5e7eb',
        padding: '8px 16px 0',
      }}
    >
      <Tabs
        type="editable-card"
        hideAdd
        size="small"
        activeKey={activeKey}
        items={items}
        onChange={(key) => {
          const targetTab = openTabs.find((tab) => tab.key === key)
          if (targetTab) navigate(targetTab.path)
        }}
        onEdit={handleEdit}
        tabBarStyle={{ marginBottom: 0 }}
      />
    </div>
  )
}
