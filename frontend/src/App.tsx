import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { ConfigProvider, Spin } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { AuthProvider, useAuthStore } from './stores/authStore'
import { HomePage } from './pages/HomePage'
import { LoginPage } from './pages/Auth/LoginPage'
import { RegisterPage } from './pages/Auth/RegisterPage'
import { ForgotPasswordPage } from './pages/Auth/ForgotPasswordPage'
import { MainShell } from './layout/MainShell'
import { WorkspacePage } from './pages/WorkspacePage'
import { LedgerWorkspace } from './pages/Workspaces/LedgerWorkspace'
import { AuditWorkspace } from './pages/Workspaces/AuditWorkspace'
import { BankWorkspace } from './pages/Workspaces/BankWorkspace'
import { TaxWorkspace } from './pages/Workspaces/TaxWorkspace'
import { BasicDataWorkspace } from './pages/Workspaces/BasicDataWorkspace'
import { EntriesPageRoute } from './pages/EntriesPageRoute'
import { RisksPageRoute } from './pages/RisksPageRoute'
import { AccountingPeriodsPage } from './pages/AccountingPeriodsPage'
import { ChartOfAccountsPage } from './pages/BasicData/ChartOfAccountsPage'
import { CounterpartiesPage } from './pages/BasicData/CounterpartiesPage'
import { OpeningBalancesPage } from './pages/BasicData/OpeningBalancesPage'
import { OrganizationUnitsPage } from './pages/BasicData/OrganizationUnitsPage'
import { PersonnelPage } from './pages/BasicData/PersonnelPage'
import { TrialBalancePage } from './pages/Reports/TrialBalancePage'
import { BalanceSheetPage } from './pages/Reports/BalanceSheetPage'
import { IncomeStatementPage } from './pages/Reports/IncomeStatementPage'
import { AgentChatPage } from './pages/AgentChatPage'
import { ModuleRegisterPage } from './pages/ModuleRegisterPage'
import { PlaceholderModulePage } from './pages/PlaceholderModulePage'
import { Step1AccountingSelectType } from './pages/AccountingMode/Step1SelectType'
import { Step2AccountingImportSource } from './pages/AccountingMode/Step2ImportSource'
import { Step3GenerateEntries } from './pages/AccountingMode/Step3GenerateEntries'
import { Step4ReviewEntries } from './pages/AccountingMode/Step4ReviewEntries'
import { Step5Export } from './pages/AccountingMode/Step5Export'
import { FixedAssetsWorkspace } from './pages/Workspaces/FixedAssetsWorkspace'
import { InventoryWorkspace } from './pages/Workspaces/InventoryWorkspace'
import { LedgerLifecyclePage } from './pages/LedgerLifecyclePage'
import { LedgerManagementPage } from './pages/LedgerManagementPage'
import { LedgerFilesPage } from './pages/LedgerFilesPage'
import { OnboardingPage } from './pages/OnboardingPage'
import { OnboardingRequestPage } from './pages/OnboardingRequestPage'
import { ProjectsPage } from './pages/ProjectsPage'
import { TeamManagementPage } from './pages/TeamManagementPage'
import { Step1SelectScope } from './pages/AuditMode/Step1SelectScope'
import { Step2AuditImportSource } from './pages/AuditMode/Step2ImportSource'
import { Step3ImportEntries } from './pages/AuditMode/Step3ImportEntries'
import { Step4RunTests } from './pages/AuditMode/Step4RunTests'
import { Step5ReviewFindings } from './pages/AuditMode/Step5ReviewFindings'
import { Step6ExportReport } from './pages/AuditMode/Step6ExportReport'
import { BankAccountsPage } from './pages/Bank/BankAccountsPage'
import { BankReconciliationPage } from './pages/Bank/BankReconciliationPage'
import { ConfirmationsPage } from './pages/Audit/ConfirmationsPage'
import { PurchaseMatchPage } from './pages/Audit/PurchaseMatchPage'

function AuthGuard({ children }: { children: React.ReactNode }) {
  const { isLoggedIn } = useAuthStore()
  const location = useLocation()
  const hasToken = localStorage.getItem('token')
  if (!isLoggedIn && !hasToken) {
    return <Navigate to="/login" replace state={{ from: location }} />
  }
  return <>{children}</>
}

function LoggedInRedirect({ children }: { children: React.ReactNode }) {
  const { isLoggedIn } = useAuthStore()
  const hasToken = localStorage.getItem('token')
  if (isLoggedIn || hasToken) {
    return <Navigate to="/workspace" replace />
  }
  return <>{children}</>
}

function LedgerDataGuard({ children }: { children: React.ReactNode }) {
  const { userLedgers, authContext, authContextReady } = useAuthStore()
  if (!authContextReady) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}>
        <Spin size="large" tip="正在加载账套信息..." />
      </div>
    )
  }
  if (userLedgers.length === 0) {
    if (authContext?.missing_bindings?.includes('team')) {
      return <Navigate to="/onboarding-request" replace />
    }
    return <Navigate to="/onboarding" replace />
  }
  return <>{children}</>
}

function AppRoutes() {
  return (
    <Routes>
      {/* 根路由：已登录展示团队大盘，未登录跳转登录 */}
      <Route path="/" element={<AuthGuard><MainShell /></AuthGuard>}>
        <Route index element={<WorkspacePage />} />
      </Route>

      {/* 公开路由 */}
      <Route path="/home" element={<HomePage />} />
      <Route path="/login" element={<LoggedInRedirect><LoginPage /></LoggedInRedirect>} />
      <Route path="/register" element={<LoggedInRedirect><RegisterPage /></LoggedInRedirect>} />
      <Route path="/forgot-password" element={<LoggedInRedirect><ForgotPasswordPage /></LoggedInRedirect>} />

      {/* 引导式向导（保留旧路径） */}
      <Route path="/accounting" element={<Navigate to="/accounting/step/1" replace />} />
      <Route path="/audit" element={<Navigate to="/audit/step/1" replace />} />

      {/* SAAS Shell + 嵌套子路由（受保护） */}
      <Route element={<AuthGuard><MainShell /></AuthGuard>}>
        <Route path="/onboarding" element={<OnboardingPage />} />
        <Route path="/onboarding-request" element={<OnboardingRequestPage />} />
        <Route path="/workspace" element={<WorkspacePage />} />
        <Route path="/team-management" element={<TeamManagementPage />} />
        <Route path="/ledger-management" element={<LedgerManagementPage />} />
        <Route path="/ledger/files" element={<LedgerDataGuard><LedgerFilesPage /></LedgerDataGuard>} />
        <Route path="/ledger/workspace" element={<LedgerDataGuard><LedgerWorkspace /></LedgerDataGuard>} />
        <Route path="/audit/workspace" element={<LedgerDataGuard><AuditWorkspace /></LedgerDataGuard>} />
        <Route path="/bank/workspace" element={<LedgerDataGuard><BankWorkspace /></LedgerDataGuard>} />
        <Route path="/tax/workspace" element={<LedgerDataGuard><TaxWorkspace /></LedgerDataGuard>} />
        <Route path="/basic/workspace" element={<LedgerDataGuard><BasicDataWorkspace /></LedgerDataGuard>} />
        <Route path="/inventory/workspace" element={<LedgerDataGuard><InventoryWorkspace /></LedgerDataGuard>} />
        <Route path="/fixed-assets/workspace" element={<LedgerDataGuard><FixedAssetsWorkspace /></LedgerDataGuard>} />
        <Route path="/projects" element={<ProjectsPage />} />
        <Route path="/ledger/lifecycle" element={<LedgerLifecyclePage />} />
        <Route path="/accounting/step/1" element={<LedgerDataGuard><Step1AccountingSelectType /></LedgerDataGuard>} />
        <Route path="/accounting/step/2" element={<LedgerDataGuard><Step2AccountingImportSource /></LedgerDataGuard>} />
        <Route path="/accounting/step/3" element={<LedgerDataGuard><Step3GenerateEntries /></LedgerDataGuard>} />
        <Route path="/accounting/step/4" element={<LedgerDataGuard><Step4ReviewEntries /></LedgerDataGuard>} />
        <Route path="/accounting/step/5" element={<LedgerDataGuard><Step5Export /></LedgerDataGuard>} />
        <Route path="/ledger/vouchers/step/1" element={<LedgerDataGuard><Step1AccountingSelectType /></LedgerDataGuard>} />
        <Route path="/ledger/vouchers/step/2" element={<LedgerDataGuard><Step2AccountingImportSource /></LedgerDataGuard>} />
        <Route path="/ledger/vouchers/step/3" element={<LedgerDataGuard><Step3GenerateEntries /></LedgerDataGuard>} />
        <Route path="/ledger/vouchers/step/4" element={<LedgerDataGuard><Step4ReviewEntries /></LedgerDataGuard>} />
        <Route path="/ledger/vouchers/step/5" element={<LedgerDataGuard><Step5Export /></LedgerDataGuard>} />
        <Route path="/audit/step/1" element={<LedgerDataGuard><Step1SelectScope /></LedgerDataGuard>} />
        <Route path="/audit/step/2" element={<LedgerDataGuard><Step2AuditImportSource /></LedgerDataGuard>} />
        <Route path="/audit/step/3" element={<LedgerDataGuard><Step3ImportEntries /></LedgerDataGuard>} />
        <Route path="/audit/step/4" element={<LedgerDataGuard><Step4RunTests /></LedgerDataGuard>} />
        <Route path="/audit/step/5" element={<LedgerDataGuard><Step5ReviewFindings /></LedgerDataGuard>} />
        <Route path="/audit/step/6" element={<LedgerDataGuard><Step6ExportReport /></LedgerDataGuard>} />
        <Route path="/audit/contracts" element={<LedgerDataGuard><ModuleRegisterPage fixedModuleKey="contract_register" /></LedgerDataGuard>} />
        <Route path="/audit/confirmations" element={<LedgerDataGuard><ConfirmationsPage /></LedgerDataGuard>} />
        <Route path="/audit/purchase-match" element={<LedgerDataGuard><PurchaseMatchPage /></LedgerDataGuard>} />
        <Route path="/basic/receivable-payable" element={<LedgerDataGuard><ModuleRegisterPage fixedModuleKey="counterparty_ledger" /></LedgerDataGuard>} />
        <Route path="/bank/cash-flow-ledger" element={<LedgerDataGuard><ModuleRegisterPage fixedModuleKey="bank_cash_flow" /></LedgerDataGuard>} />
        <Route path="/registers/:moduleKey" element={<LedgerDataGuard><ModuleRegisterPage /></LedgerDataGuard>} />
        <Route path="/agent" element={<AgentChatPage />} />
        <Route path="/entries" element={<LedgerDataGuard><EntriesPageRoute /></LedgerDataGuard>} />
        <Route path="/ledger/entries" element={<LedgerDataGuard><EntriesPageRoute /></LedgerDataGuard>} />
        <Route
          path="/ledger/books"
          element={(
            <PlaceholderModulePage
              title="账簿管理"
              description="账簿管理用于按会计期间汇总凭证，形成总账、明细账和辅助账，后续将与结账、反结账、审计抽样联动。"
              items={['按期间生成账簿', '凭证过账与反过账', '账簿导出与审计留痕']}
            />
          )}
        />
        <Route
          path="/ledger/general-ledger"
          element={(
            <PlaceholderModulePage
              title="总账"
              description="总账按会计科目汇总借贷发生额和余额，是试算平衡、财务报表和审计分析的核心数据来源。"
              items={['科目期初余额', '本期借贷发生额', '期末余额与报表取数']}
            />
          )}
        />
        <Route
          path="/ledger/subsidiary-ledger"
          element={(
            <PlaceholderModulePage
              title="明细账"
              description="明细账展示每个科目的分录流水，便于追查凭证、往来单位、银行流水和业务单据之间的勾稽关系。"
              items={['按科目查看流水', '按往来单位筛选', '追溯凭证与附件']}
            />
          )}
        />
        <Route path="/risks" element={<RisksPageRoute />} />
        <Route path="/periods" element={<AccountingPeriodsPage />} />
        <Route path="/accounting-periods" element={<AccountingPeriodsPage />} />
        <Route path="/basic/coa" element={<ChartOfAccountsPage />} />
        <Route path="/basic/org-units" element={<OrganizationUnitsPage />} />
        <Route path="/basic/personnel" element={<PersonnelPage />} />
        <Route path="/basic/counterparties" element={<CounterpartiesPage />} />
        <Route path="/basic/opening-balances" element={<OpeningBalancesPage />} />
        <Route
          path="/basic/materials"
          element={(
            <PlaceholderModulePage
              title="SKU/物料"
              description="SKU/物料资料用于统一商品、成品、半成品和原材料口径，后续服务成本核算、存货盘点和收入成本匹配。"
              items={['SKU 编码与名称', '商品/成品/半成品/原材料分类', '计量单位与成本属性']}
            />
          )}
        />
        <Route
          path="/basic/warehouses"
          element={(
            <PlaceholderModulePage
              title="仓库"
              description="仓库资料用于管理总仓、中转仓、门店仓和虚拟仓，后续与存货流水、盘点和进销存模块关联。"
              items={['总仓', '中转仓', '门店仓', '虚拟仓']}
            />
          )}
        />
        <Route path="/bank/accounts" element={<LedgerDataGuard><BankAccountsPage /></LedgerDataGuard>} />
        <Route path="/bank/reconciliation" element={<LedgerDataGuard><BankReconciliationPage /></LedgerDataGuard>} />
        <Route
          path="/bank/third-party-accounts"
          element={(
            <PlaceholderModulePage
              title="三方支付账户"
              description="三方支付账户用于管理支付宝、微信支付等平台资金，便于识别平台待结算款和银行入账之间的时间差。"
              items={['平台账户', '结算周期', '手续费与到账差异']}
            />
          )}
        />
        <Route
          path="/bank/aggregate-accounts"
          element={(
            <PlaceholderModulePage
              title="聚合账户"
              description="聚合账户用于归集多个银行或三方支付账户视图，支持集团资金管理和账户余额监控。"
              items={['账户分组', '资金归集', '集团视角余额监控']}
            />
          )}
        />
        <Route
          path="/bank/journal"
          element={(
            <PlaceholderModulePage
              title="日记账"
              description="银行日记账记录账户逐笔收支，是银行流水、凭证和余额调节表之间的桥梁。"
              items={['银行流水导入', '收支方向识别', '生成或匹配总账凭证']}
            />
          )}
        />
        <Route
          path="/bank/settings"
          element={(
            <PlaceholderModulePage
              title="账户设置"
              description="账户设置用于维护银行账户、三方支付账户与总账科目、组织主体、权限范围之间的对应关系。"
              items={['科目映射', '组织归属', '对账规则']}
            />
          )}
        />
        <Route
          path="/tax/invoices"
          element={(
            <LedgerDataGuard>
              <ModuleRegisterPage fixedModuleKey="tax_invoice" />
            </LedgerDataGuard>
          )}
        />
        <Route
          path="/tax/invoice-issuance-ledger"
          element={(
            <PlaceholderModulePage
              title="发票开具台账"
              description="发票开具台账用于汇总销项发票开具记录，跟踪开票金额、税率和对应收入确认情况。"
              items={['销项发票汇总', '开票金额统计', '收入勾稽']}
            />
          )}
        />
        <Route
          path="/tax/certification-deduction-ledger"
          element={(
            <PlaceholderModulePage
              title="认证抵扣台账"
              description="认证抵扣台账用于管理进项发票认证、抵扣状态和可抵扣税额，辅助增值税申报。"
              items={['进项认证状态', '可抵扣税额', '申报勾稽']}
            />
          )}
        />
        <Route
          path="/tax/assistant"
          element={(
            <PlaceholderModulePage
              title="涉税助手"
              description="涉税助手用于解释常见涉税问题、提示税务风险，并辅助发票与凭证匹配。当前为预留入口，后续接入正式税务规则和知识资料。"
              items={['涉税问题说明', '税务风险提示', '发票与凭证匹配']}
            />
          )}
        />
        <Route path="/fixed-assets" element={<LedgerDataGuard><FixedAssetsWorkspace /></LedgerDataGuard>} />
        <Route
          path="/fixed-assets/cards"
          element={(
            <PlaceholderModulePage
              title="资产卡片"
              description="资产卡片用于记录固定资产原值、累计折旧、使用部门和状态，是折旧计提、资产处置和盘点的基础。"
              items={['资产编码与名称', '原值与折旧年限', '使用部门与存放地点']}
            />
          )}
        />
        <Route
          path="/fixed-assets/depreciation"
          element={(
            <PlaceholderModulePage
              title="折旧计提"
              description="折旧计提用于按会计政策计算本期折旧额，并为后续生成总账折旧凭证预留接口。"
              items={['折旧政策', '本期折旧测算', '折旧凭证联动']}
            />
          )}
        />
        <Route path="/inventory" element={<InventoryWorkspace />} />
        <Route
          path="/inventory/purchase-in"
          element={(
            <LedgerDataGuard>
              <ModuleRegisterPage fixedModuleKey="purchase" />
            </LedgerDataGuard>
          )}
        />
        <Route
          path="/inventory/stock-flow"
          element={(
            <PlaceholderModulePage
              title="库存流水"
              description="库存流水用于记录存货收发存明细，是成本结转、盘点差异和存货审计的重要依据。"
              items={['采购入库流水', '销售出库流水', '盘点与调拨流水']}
            />
          )}
        />
        <Route path="/reports/trial-balance" element={<LedgerDataGuard><TrialBalancePage /></LedgerDataGuard>} />
        <Route path="/reports/balance-sheet" element={<LedgerDataGuard><BalanceSheetPage /></LedgerDataGuard>} />
        <Route path="/reports/income-statement" element={<LedgerDataGuard><IncomeStatementPage /></LedgerDataGuard>} />
      </Route>
    </Routes>
  )
}

function App() {
  return (
    <ConfigProvider locale={zhCN}>
      <AuthProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </AuthProvider>
    </ConfigProvider>
  )
}

export default App
