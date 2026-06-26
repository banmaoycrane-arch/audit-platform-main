const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

export type ImportJob = {
  id: number
  organization_id: number
  ledger_id?: number | null
  status: string
  source_type: string
  file_count: number
  entry_count: number
  error_message: string | null
  audit_scope_type?: 'all' | 'by_account' | 'by_period' | null
  audit_period_id?: number | null
  audit_account_codes?: string[] | null
  project_id?: number | null
  created_at: string
}

export type AuditScopePayload = {
  audit_scope_type: 'all' | 'by_account' | 'by_period'
  audit_period_id?: number | null
  audit_account_codes?: string[] | null
  project_id?: number | null
}

export type AccountingEntry = {
  id: number
  import_job_id: number
  voucher_no: string | null
  voucher_date: string | null
  summary: string | null
  account_code: string | null
  account_name: string | null
  debit_amount: number
  credit_amount: number
  counterparty: string | null
  normalized_text: string
  entry_line_no: number
  review_status: string
  created_at: string
}

export type ChronologicalEntryFilters = {
  ledger_id: number
  period_id?: number
  date_from?: string
  date_to?: string
  account_code?: string
  account_name?: string
  summary?: string
  voucher_word?: string
  voucher_no?: string
  amount_min?: number
  amount_max?: number
  limit?: number
  offset?: number
}

export type ChronologicalEntryListResponse = {
  items: AccountingEntry[]
  total: number
  limit: number
  offset: number
}

export type VoucherCard = {
  voucher_no: string | null
  voucher_date: string | null
  voucher_word: string | null
  line_count: number
  debit_total: number
  credit_total: number
  summary_preview: string | null
  lines: AccountingEntry[]
}

export type VoucherQueryFilters = {
  ledger_id: number
  period_id?: number
  date_from?: string
  date_to?: string
  month?: string
  filter_mode?: 'line' | 'voucher'
  account_code?: string
  account_name?: string
  summary?: string
  voucher_word?: string
  voucher_no?: string
  debit_min?: number
  debit_max?: number
  credit_min?: number
  credit_max?: number
  total_min?: number
  total_max?: number
  limit?: number
  offset?: number
}

export type VoucherQueryResponse = {
  items: VoucherCard[]
  total: number
  limit: number
  offset: number
}

export type AuditRisk = {
  id: number
  import_job_id: number
  risk_type: string
  risk_level: string
  title: string
  description: string
  status: string
  confidence: number
  created_at: string
}

export type RiskDetail = AuditRisk & {
  evidence: Array<{
    id: number
    evidence_type: string
    source_id: number
    source_text: string
    similarity_score: number | null
    reason: string
  }>
}

export type DayBookReport = {
  total_vouchers: number
  total_entries: number
  skip_count: number
  unbalanced_count: number
  completeness_score: number
  missing_voucher_nos: string[]
  unbalanced_vouchers: Array<{
    voucher_no: string
    debit_total: string
    credit_total: string
    difference: string
    entry_count: number
  }>
}

export type ParseDiagnostics = {
  template_name?: string | null
  matched_fields?: Record<string, string>
  unmatched_headers?: string[]
  total_rows?: number
  success_rows?: number
  expected_columns?: string[]
  guidance?: string
}

export type AuditFinding = {
  id: string
  db_id?: number
  finding_type: string
  severity: 'high' | 'medium' | 'low'
  business_type: string
  related_entries: string[]
  related_files: string[]
  finding_title: string
  finding_description: string
  audit_procedure: string
  audit_conclusion: string
  risk_statement: string
  recommendation: string
  metadata: Record<string, unknown>
  status?: string
}

export type AuditTestReport = {
  test_date: string
  period: string
  scope: string
  audit_scope?: AuditScopePayload & {
    audit_period_code?: string
    audit_period_start?: string
    audit_period_end?: string
  }
  total_transactions: number
  tested_transactions: number
  forward_test: Record<string, any>
  reverse_test: Record<string, any>
  completeness_result: Record<string, any>
  accuracy_result: Record<string, any>
  cutoff_result: Record<string, any>
  classification_result: Record<string, any>
  findings: AuditFinding[]
  summary: {
    total_findings: number
    high_severity: number
    medium_severity: number
    low_severity: number
    by_type: Record<string, number>
  }
}

export type AccountingPeriod = {
  id: number
  organization_id: number
  period_code: string
  period_type: string
  start_date: string
  end_date: string
  status: string
}

export type SourceFileParseFeedback = {
  document_type?: string
  document_type_label?: string
  confidence?: number
  summary?: string
  voucher_date?: string | null
  amount?: number | null
  counterparty?: string | null
  error_message?: string | null
}

export type DraftArchiveContext = {
  project_id?: number | null
  project_name?: string | null
  ledger_id?: number | null
  period_code?: string | null
  archive_category?: string | null
  archive_folder?: string | null
  archive_path?: string | null
  module_key?: string | null
  module_keys?: string[]
  document_type?: string | null
  document_type_label?: string | null
  counterparty?: string | null
  status?: string | null
  archived_at?: string | null
}

export type SourceFileRead = {
  id: number
  organization_id?: number
  import_job_id?: number
  ledger_id?: number | null
  counterparty_id?: number | null
  counterparty_name?: string | null
  filename: string
  file_type: string
  notes?: string | null
  upload_status: string
  text_extract_status: string
  parse_status: string
  recognized_document_type: string
  parse_feedback?: SourceFileParseFeedback | null
  parse_summary?: string | null
  raw_text_preview: string | null
  archive_path?: string | null
  archive_category?: string | null
  archive_folder?: string | null
  project_id?: number | null
  project_name?: string | null
  period_code?: string | null
  archive_context?: DraftArchiveContext | null
  customer_context?: {
    counterparty_id: number | null
    counterparty_name: string | null
    match_source: string | null
    confidence_note: string | null
  }
  created_at: string
}

export type ModuleRegisterItem = {
  id?: number
  module_key?: string
  ledger_id?: number | null
  counterparty_id?: number | null
  counterparty_name?: string | null
  contract_no?: string | null
  contract_name?: string | null
  contract_type?: string | null
  contract_amount?: number | null
  execution_status?: string | null
  execution_status_label?: string | null
  sign_date?: string | null
  invoice_no?: string | null
  invoice_date?: string | null
  buyer_name?: string | null
  seller_name?: string | null
  total_amount?: number | null
  transaction_date?: string | null
  transaction_type?: string | null
  amount?: number | null
  summary?: string | null
  balance_type?: string | null
  balance_type_label?: string | null
  document_count?: number | null
  created_at?: string | null
}

export type ModuleRegisterListResponse = {
  module_key: string
  module_label: string
  module_path: string
  ledger_id: number
  count: number
  items: ModuleRegisterItem[]
}

export type ModuleRegisterSummary = {
  ledger_id: number
  modules: Record<string, { module_key: string; module_label: string; module_path: string; count: number }>
}

export type ImportPeriodSuggestion = {
  detected_month: string | null
  suggested_period: AccountingPeriodSuggestion | null
  matched_period: (AccountingPeriod & { id: number }) | null
  reason: string
}

export type AccountingPeriodSuggestion = {
  period_code: string
  period_type: string
  start_date: string
  end_date: string
}

export type AccountingPeriodRecommendation = {
  matched_period: AccountingPeriod | null
  suggested_period: AccountingPeriodSuggestion | null
  reason: string
}

export type Counterparty = {
  id: number
  name: string
  role: string
  unified_credit_no: string | null
  is_related_party: boolean
  default_entity_id: number | null
  is_active: boolean
}

export type CoaIndustryTemplate = {
  code: string
  name: string
  description: string
}

export type CoaTemplateAccount = {
  code: string
  name: string
  parent_code: string | null
  level: number
  category: string
  direction: string
  is_terminal: boolean
  import_status?: 'new' | 'skipped' | 'conflict'
}

export type CoaTemplatePreview = CoaIndustryTemplate & {
  accounts: CoaTemplateAccount[]
  summary: {
    new: number
    skipped: number
    conflicts: number
  }
}

export type ChartOfAccount = {
  code: string
  name: string
  parent_code: string | null
  level: number
  category: string
  direction: string
  account_category?: string | null
  account_subcategory?: string | null
  equity_subcategory?: string | null
  include_in_dividend_base?: boolean | null
  is_terminal: boolean
  status: string
  is_system: boolean
}

export type EntryDraft = {
  source_entry_id?: number
  source_file_id?: number
  voucher_no: string
  voucher_date: string
  account_code: string | null
  account_name: string | null
  summary: string
  debit_amount: number
  credit_amount: number
  counterparty: string | null
  entry_line_no: number
  metadata: Record<string, unknown>
  tags: Array<{ tag_type: string; tag_value: string; confidence?: number }>
}

export type ManualEntriesCommitResult = {
  count: number
  entry_ids: number[]
  job_id: number
}

export type AiDraftManualSwitchLogPayload = {
  period_id: number
  reason?: string
  recognized_evidence: Array<Record<string, unknown>>
  manual_fields: string[]
  draft_metadata: Record<string, unknown>
}

export type AiDraftManualSwitchLogResult = {
  log_id: number
  action: string
  logged: boolean
}

export type Project = {
  id: number
  name: string
  team_id?: number
  type?: string
  description?: string | null
  status: 'active' | 'completed' | 'paused' | 'draft' | 'cancelled'
  start_date: string | null
  end_date: string | null
  manager?: string | null
  manager_id?: number | null
  budget?: number | null
  created_at: string | null
  updated_at: string | null
}

export type EntityCreatePayload = {
  entity_name: string
  entity_code?: string | null
  ledger_id?: number | null
  entity_type?: string
  entity_category?: string
  is_accounting_entity?: boolean
  is_tax_entity?: boolean
  is_legal_entity?: boolean
  is_management_entity?: boolean
}

export type AuthContext = {
  user: { id: number; username: string | null; phone: string | null; email: string | null; has_password?: boolean }
  teams: Team[]
  ledgers: Ledger[]
  projects: Project[]
  current_ledger_id: number | null
  missing_bindings: string[]
  requires_onboarding: boolean
  next_action: 'create_team' | 'select_or_create_ledger' | 'select_or_create_project' | 'confirm_accounting_entity' | 'workspace'
  temporary_status: 'onboarding_pending' | 'ready'
  historical_candidates: Array<Record<string, unknown>>
  mock_boundaries: {
    sms_code: 'development_mock' | string
    terms: 'placeholder' | string
    privacy: 'placeholder' | string
    onboarding_data: 'real_api' | string
  }
}

export type BindingRequest = {
  id: number
  requester_user_id: number
  requester_name: string | null
  requester_phone: string | null
  team_id: number
  team_name: string | null
  ledger_id: number | null
  ledger_name: string | null
  project_id: number | null
  project_name: string | null
  requested_role: 'viewer' | 'accountant' | 'admin'
  status: 'pending' | 'approved' | 'rejected'
  reason: string | null
  reviewer_user_id: number | null
  review_comment: string | null
  created_at: string | null
  reviewed_at: string | null
}

export type BindingOptions = {
  teams: Array<{ id: number; name: string }>
  ledgers: Array<{ id: number; name: string }>
  projects: Array<{ id: number; name: string }>
}

export type OpeningBalance = {
  id: number
  organization_id: number
  ledger_id?: number | null
  period_id: number
  account_code: string
  debit_balance: number
  credit_balance: number
  currency: string
  notes: string | null
}

export type TrialBalance = {
  debit_total: number
  credit_total: number
  is_balanced: boolean
  diff: number
  count: number
}

export type TrialBalanceRow = {
  account_code: string
  account_name: string
  category: string
  direction: string
  opening_debit: number
  opening_credit: number
  period_debit: number
  period_credit: number
  closing_debit: number
  closing_credit: number
}

export type TrialBalanceReport = {
  rows: TrialBalanceRow[]
  totals: {
    opening_debit: number
    opening_credit: number
    period_debit: number
    period_credit: number
    closing_debit: number
    closing_credit: number
  }
  is_balanced: boolean
}

export type BalanceSheetReport = {
  assets: TrialBalanceRow[]
  liabilities: TrialBalanceRow[]
  equity: TrialBalanceRow[]
  assets_total: number
  liabilities_total: number
  equity_total: number
  is_balanced: boolean
}

export type IncomeStatementReport = {
  revenue: Record<string, number>
  expense: Record<string, number>
  operating_revenue: number
  operating_cost: number
  period_expenses: number
  operating_profit: number
  total_profit: number
  income_tax: number
  net_profit: number
}

export type Team = {
  id: number
  name: string
  type: string
  created_at: string | null
  member_count?: number
  ledger_count?: number
}

export type BankAccount = {
  id: number
  ledger_id: number
  bank_name: string
  account_no: string
  account_name: string
  coa_account_code: string
  opening_balance: number
  current_balance: number
  is_active: boolean
}

export type BankTransaction = {
  id: number
  bank_account_id: number
  ledger_id: number
  transaction_date: string
  direction: 'in' | 'out'
  amount: number
  summary: string | null
  counterparty: string | null
  reconciliation_status: string
  matched_entry_id: number | null
}

export type BankReconcileResult = {
  matched_count: number
  matches: Array<{
    transaction_id: number
    entry_id: number
    amount: number
    transaction_date: string
    voucher_date: string
  }>
  unmatched_transactions: Array<{
    id: number
    transaction_date: string
    amount: number
    direction: string
    summary: string | null
  }>
  unmatched_entries: Array<{
    id: number
    voucher_no: string | null
    voucher_date: string | null
    summary: string | null
    amount: number
    direction: string
  }>
}

export type BankSummary = {
  account_count: number
  unreconciled_count: number
  total_balance: number
}

export type BankReconciliationItem = {
  id: number
  item_type: string
  item_type_label: string
  amount: number
  direction: string | null
  bank_transaction_id: number | null
  entry_id: number | null
  summary: string | null
  note: string | null
}

export type BankReconciliationDraft = {
  id: number
  ledger_id: number
  bank_account_id: number
  bank_name: string | null
  account_no: string | null
  period_end: string
  statement_balance: number
  book_balance: number
  adjusted_statement_balance: number
  adjusted_book_balance: number
  difference: number
  status: string
  created_at: string | null
  items: BankReconciliationItem[]
}

export type CounterpartyConfirmation = {
  id: number
  ledger_id: number
  counterparty_id: number | null
  counterparty_name: string | null
  balance_type: string
  balance_type_label: string
  book_balance: number
  confirmation_amount: number
  reply_amount: number | null
  difference: number | null
  status: string
  sent_at: string | null
  replied_at: string | null
  source_file_id: number | null
  created_at: string | null
}

export type PurchaseMatchCheck = {
  check_key: string
  label: string
  left_amount: number
  right_amount: number
  passed: boolean
}

export type PurchaseMatchException = {
  exception_type: string
  exception_label: string
  message: string
  left_amount?: number
  right_amount?: number
}

export type PurchaseMatchResult = {
  ledger_id: number
  contract: {
    id: number
    contract_no: string | null
    contract_name: string | null
    contract_amount: number
    execution_status: string
    counterparty_name: string | null
  }
  invoices: Array<{
    id: number
    invoice_no: string | null
    invoice_date: string | null
    total_amount: number
    seller_name: string | null
    buyer_name: string | null
  }>
  inventory_documents: Array<{
    id: number
    document_no: string
    document_type: string
    document_date: string | null
    total_amount: number
    counterparty_name: string | null
  }>
  totals: {
    contract_amount: number
    invoice_total: number
    inventory_total: number
  }
  checks: PurchaseMatchCheck[]
  exceptions: PurchaseMatchException[]
  match_status: string
  match_status_label: string
}

export type PurchaseMatchSummary = {
  ledger_id: number
  contract_count: number
  matched_count: number
  incomplete_count: number
  exception_count: number
  exception_items: Array<{
    contract_id: number
    contract_no: string | null
    contract_name: string | null
    match_status: string
    exception_type: string
    exception_label: string
    message: string
  }>
  results: PurchaseMatchResult[]
}

export type WorkpaperVersion = {
  id: number
  workpaper_index_id: number
  source_file_id: number
  filename: string | null
  version_no: string
  status: string
  status_label: string
  prepared_by: number | null
  reviewed_by: number | null
  change_reason: string | null
  supersedes_id: number | null
  created_at: string | null
}

export type WorkpaperIndex = {
  id: number
  ledger_id: number
  project_id: number | null
  parent_id: number | null
  index_no: string
  title: string
  audit_area: string | null
  archive_path: string | null
  source_module_key: string | null
  sort_order: number
  version_count: number
  current_version_no: string | null
  current_status: string | null
  created_at: string | null
  versions: WorkpaperVersion[]
}

export type WorkpaperCatalog = {
  ledger_id: number
  exported_at: string
  index_count: number
  version_count: number
  items: WorkpaperIndex[]
}

export type WorkflowConfig = {
  project_id: number
  granularity: string
  enabled_procedures: string[]
  auto_link_workpaper: boolean
  created_at: string | null
  updated_at: string | null
}

export type AuditProcedureRun = {
  id: number
  project_id: number | null
  ledger_id: number
  procedure_key: string
  procedure_label: string
  status: string
  status_label: string
  title: string
  related_entity_type: string | null
  related_entity_id: number | null
  workpaper_index_id: number | null
  source_file_id: number | null
  recommended_by: string
  notes: string | null
  allowed_next_statuses: string[]
  concluded_at: string | null
  created_at: string | null
  updated_at: string | null
}

export type TeamMember = {
  id: number
  username: string | null
  email: string | null
  phone: string | null
  team_id: number | null
}

export type Ledger = {
  id: number
  name: string
  team_id?: number
  organization_id?: number
  is_default?: boolean
  role?: string
  status: string
  created_at?: string
  accounting_start_date?: string | null
  activated_at?: string | null
  suspended_at?: string | null
  archived_at?: string | null
  deleted_at?: string | null
  lifecycle_reason?: string | null
}

export type LedgerAuth = {
  id: number
  ledger_id: number
  user_id: number
  role: string
  granted_at: string | null
  granted_by?: number | null
}

export type CreateLedgerPayload = {
  name: string
  team_id: number
  accounting_start_date?: string
}

export type AgentTaskPlan = {
  task_type: string
  agent_role: string
  risk_level: 'low' | 'medium' | 'high' | string
  required_inputs: string[]
  allowed_tools: string[]
  approval_required: boolean
  approval_reason: string
  execution_source: 'agent_assisted' | 'agent_auto' | string
  user_id: number
  ledger_id: number | null
  audit_trace_required: boolean
  context_notes: string[]
}

export type AgentChatResponse = {
  intent: string
  confidence: number
  reply: string
  suggested_path: string
  steps: string[]
  source?: 'llm' | 'rules'
  model_available?: boolean
  task_plan?: AgentTaskPlan
}

async function getApiErrorMessage(response: Response): Promise<string> {
  const text = await response.text()
  if (!text) {
    return `请求失败（${response.status}）`
  }
  try {
    const data = JSON.parse(text) as { detail?: unknown; message?: unknown }
    if (typeof data.detail === 'string') {
      return data.detail
    }
    if (Array.isArray(data.detail)) {
      return data.detail
        .map((item) => {
          if (item && typeof item === 'object' && 'msg' in item) {
            return String(item.msg)
          }
          return JSON.stringify(item)
        })
        .join('；')
    }
    if (data.detail) {
      return JSON.stringify(data.detail)
    }
    if (typeof data.message === 'string') {
      return data.message
    }
    return text
  } catch {
    return text
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = localStorage.getItem('token')
  const headers: Record<string, string> = {
    ...(options?.headers as Record<string, string> || {}),
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
    })
  } catch (error) {
    throw new Error('后端服务不可用，请确认后端服务已启动后重试')
  }
  if (response.status === 401) {
    // 登录相关接口的 401 不应清除 token 或重定向，直接透传错误给调用方
    const isAuthEndpoint = path.includes('/login') || path.includes('/register') || path.includes('/sms/code')
    if (!isAuthEndpoint) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    const errorMessage = await getApiErrorMessage(response)
    throw new Error(errorMessage)
  }
  if (!response.ok) {
    const errorMessage = await getApiErrorMessage(response)
    throw new Error(errorMessage)
  }
  const data = await response.json()
  return data as T
}

export const api = {
  baseUrl: API_BASE,
  health: () => request<{ status: string }>('/health'),
  loginPassword: (username: string, password: string) =>
    request<{ access_token: string; token_type: string }>('/api/auth/login/password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    }),
  loginSms: (phone: string, code: string) =>
    request<{ access_token: string; token_type: string }>('/api/auth/login/sms', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phone, code })
    }),
  registerUser: (payload: {
    username?: string
    phone?: string
    password: string
    agreed_terms: boolean
    agreed_privacy: boolean
  }) =>
    request<{ access_token: string; token_type: string }>('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }),
  setPassword: (password: string) =>
    request<{ status: string; message: string }>('/api/auth/password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password })
    }),
  getSmsCode: (phone: string) =>
    request<{ code?: string; sms_code?: string; message?: string }>('/api/auth/sms/code', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phone })
    }),
  getMe: () =>
    request<{ id: number; username: string | null; phone: string | null; email: string | null; is_active: boolean }>('/api/auth/me'),
  getAuthContext: () => request<AuthContext>('/api/auth/context'),
  createTeam: (payload: { name: string; type: string }) =>
    request<Team>('/api/teams', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }),
  listTeams: () => request<Team[]>('/api/teams'),
  getTeamMembers: (teamId: number) => request<TeamMember[]>(`/api/teams/${teamId}/members`),
  addTeamMember: (teamId: number, payload: {
    user_id?: number
    username?: string
    phone?: string
    role?: string
  }) =>
    request<TeamMember>(`/api/teams/${teamId}/members`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }),
  getBindingOptions: (teamId?: number) =>
    request<BindingOptions>(teamId ? `/api/binding-requests/options?team_id=${teamId}` : '/api/binding-requests/options'),
  createBindingRequest: (payload: {
    team_id: number
    ledger_id?: number | null
    project_id?: number | null
    requested_role: 'viewer' | 'accountant' | 'admin'
    reason?: string | null
  }) =>
    request<BindingRequest>('/api/binding-requests', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }),
  listMyBindingRequests: () => request<BindingRequest[]>('/api/binding-requests?scope=mine'),
  listReviewableBindingRequests: () => request<BindingRequest[]>('/api/binding-requests?scope=reviewable'),
  approveBindingRequest: (requestId: number, reviewComment?: string | null) =>
    request<BindingRequest>(`/api/binding-requests/${requestId}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ review_comment: reviewComment || null })
    }),
  rejectBindingRequest: (requestId: number, reviewComment?: string | null) =>
    request<BindingRequest>(`/api/binding-requests/${requestId}/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ review_comment: reviewComment || null })
    }),
  agentChat: (message: string) =>
    request<AgentChatResponse>('/api/agent/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message })
    }),
  createImportJob: (
    organizationName: string,
    sourceType?: string,
    ledgerId?: number | null,
    auditScope?: AuditScopePayload,
  ) =>
    request<ImportJob>('/api/import-jobs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        organization_name: organizationName,
        source_type: sourceType || 'voucher_import',
        ledger_id: ledgerId || undefined,
        audit_scope_type: auditScope?.audit_scope_type,
        audit_period_id: auditScope?.audit_period_id ?? undefined,
        audit_account_codes: auditScope?.audit_account_codes,
        project_id: auditScope?.project_id ?? undefined,
      })
    }),
  updateImportJobAuditScope: (jobId: number, auditScope: AuditScopePayload) =>
    request<ImportJob>(`/api/import-jobs/${jobId}/audit-scope`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(auditScope),
    }),
  listImportJobs: (ledgerId?: number) => {
    const params = new URLSearchParams()
    if (ledgerId) params.set('ledger_id', String(ledgerId))
    const query = params.toString()
    return request<ImportJob[]>(`/api/import-jobs${query ? `?${query}` : ''}`)
  },
  getImportJob: (jobId: number) => request<ImportJob>(`/api/import-jobs/${jobId}`),
  uploadFile: (jobId: number, file: File, documentTypeHints?: string[]) => {
    const form = new FormData()
    form.append('file', file)
    if (documentTypeHints && documentTypeHints.length > 0) {
      form.append('document_type_hints', documentTypeHints.join(','))
    }
    return request<SourceFileRead>(`/api/import-jobs/${jobId}/files`, { method: 'POST', body: form })
  },
  parseUploadedFile: (jobId: number, fileId: number) =>
    request<SourceFileRead>(`/api/import-jobs/${jobId}/files/${fileId}/parse`, { method: 'POST' }),
  listImportFiles: (jobId: number) => request<SourceFileRead[]>(`/api/import-jobs/${jobId}/files`),
  processImportJob: (jobId: number) => request<ImportJob>(`/api/import-jobs/${jobId}/process`, { method: 'POST' }),
  processImportJobSync: (jobId: number) =>
    request<{ job: ImportJob; report: Record<string, unknown> }>(
      `/api/import-jobs/${jobId}/process/sync`,
      { method: 'POST' }
    ),
  getImportReport: (jobId: number) => request<any>(`/api/import-jobs/${jobId}/report`),
  getDayBookReport: (jobId: number) => request<DayBookReport>(`/api/import-jobs/${jobId}/day-book-report`),
  getImportPeriodSuggestion: (jobId: number) => request<ImportPeriodSuggestion>(`/api/import-jobs/${jobId}/period-suggestion`),
  listEntries: (jobId?: number, ledgerId?: number) => {
    const params = new URLSearchParams()
    if (jobId) params.set('import_job_id', String(jobId))
    if (!jobId && ledgerId) params.set('ledger_id', String(ledgerId))
    const query = params.toString()
    return request<AccountingEntry[]>(`/api/entries${query ? `?${query}` : ''}`)
  },
  listChronologicalEntries: (filters: ChronologicalEntryFilters) => {
    const params = new URLSearchParams()
    params.set('ledger_id', String(filters.ledger_id))
    if (filters.period_id != null) params.set('period_id', String(filters.period_id))
    if (filters.date_from) params.set('date_from', filters.date_from)
    if (filters.date_to) params.set('date_to', filters.date_to)
    if (filters.account_code) params.set('account_code', filters.account_code)
    if (filters.account_name) params.set('account_name', filters.account_name)
    if (filters.summary) params.set('summary', filters.summary)
    if (filters.voucher_word) params.set('voucher_word', filters.voucher_word)
    if (filters.voucher_no) params.set('voucher_no', filters.voucher_no)
    if (filters.amount_min != null) params.set('amount_min', String(filters.amount_min))
    if (filters.amount_max != null) params.set('amount_max', String(filters.amount_max))
    if (filters.limit != null) params.set('limit', String(filters.limit))
    if (filters.offset != null) params.set('offset', String(filters.offset))
    return request<ChronologicalEntryListResponse>(`/api/entries/chronological?${params.toString()}`)
  },
  queryVouchers: (filters: VoucherQueryFilters) => {
    const params = new URLSearchParams()
    params.set('ledger_id', String(filters.ledger_id))
    if (filters.period_id != null) params.set('period_id', String(filters.period_id))
    if (filters.date_from) params.set('date_from', filters.date_from)
    if (filters.date_to) params.set('date_to', filters.date_to)
    if (filters.month) params.set('month', filters.month)
    if (filters.filter_mode) params.set('filter_mode', filters.filter_mode)
    if (filters.account_code) params.set('account_code', filters.account_code)
    if (filters.account_name) params.set('account_name', filters.account_name)
    if (filters.summary) params.set('summary', filters.summary)
    if (filters.voucher_word) params.set('voucher_word', filters.voucher_word)
    if (filters.voucher_no) params.set('voucher_no', filters.voucher_no)
    if (filters.debit_min != null) params.set('debit_min', String(filters.debit_min))
    if (filters.debit_max != null) params.set('debit_max', String(filters.debit_max))
    if (filters.credit_min != null) params.set('credit_min', String(filters.credit_min))
    if (filters.credit_max != null) params.set('credit_max', String(filters.credit_max))
    if (filters.total_min != null) params.set('total_min', String(filters.total_min))
    if (filters.total_max != null) params.set('total_max', String(filters.total_max))
    if (filters.limit != null) params.set('limit', String(filters.limit))
    if (filters.offset != null) params.set('offset', String(filters.offset))
    return request<VoucherQueryResponse>(`/api/entries/vouchers?${params.toString()}`)
  },
  reviewEntry: (entryId: number, reviewStatus: string) =>
    request<AccountingEntry>(`/api/entries/${entryId}/review`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ review_status: reviewStatus }),
    }),
  batchReviewEntries: (entryIds: number[], reviewStatus: string) =>
    request<{ updated: number }>('/api/entries/batch-review', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ entry_ids: entryIds, review_status: reviewStatus }),
    }),
  listRisks: (jobId?: number, ledgerId?: number) => {
    const params = new URLSearchParams()
    if (jobId) params.set('import_job_id', String(jobId))
    if (!jobId && ledgerId) params.set('ledger_id', String(ledgerId))
    const query = params.toString()
    return request<AuditRisk[]>(`/api/risks${query ? `?${query}` : ''}`)
  },
  getRisk: (riskId: number) => request<RiskDetail>(`/api/risks/${riskId}`),
  reviewRisk: (riskId: number, action: string, comment?: string) =>
    request<AuditRisk>(`/api/risks/${riskId}/review`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, comment })
    }),
  similarSearch: (entryId: number) => request<{ results: unknown[]; message?: string }>(`/api/entries/${entryId}/similar-search`, { method: 'POST' }),
  bindFileLedger: (fileId: number, ledgerId: number | null) =>
    request<SourceFileRead>(`/api/files/${fileId}/bind-ledger`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ledger_id: ledgerId })
    }),
  runAuditTests: (jobId: number) => request<AuditTestReport>(`/api/audit-tests/${jobId}/run`, { method: 'POST' }),
  getAuditTestReport: (jobId: number) => request<AuditTestReport>(`/api/audit-tests/${jobId}/report`),
  getAuditFindings: (jobId: number) => request<AuditFinding[]>(`/api/audit-tests/${jobId}/findings`),
  reviewAuditFinding: (findingDbId: number, action: string, comment?: string) =>
    request<AuditFinding>(`/api/audit-tests/findings/${findingDbId}/review`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, comment })
    }),
  exportImportJob: async (jobId: number, format: 'xlsx' | 'csv' | 'json'): Promise<Blob> => {
    const response = await fetch(`${API_BASE}/api/import-jobs/${jobId}/export?format=${format}`)
    if (!response.ok) {
      throw new Error(await response.text())
    }
    return response.blob()
  },
  postImportJobEntries: (jobId: number) =>
    request<{ job_id: number; posted: number; total: number; posted_at: string }>(
      `/api/import-jobs/${jobId}/post`,
      { method: 'POST' }
    ),
  exportAuditReport: async (jobId: number, format: 'xlsx' | 'json'): Promise<Blob> => {
    const response = await fetch(`${API_BASE}/api/audit-tests/${jobId}/export?format=${format}`)
    if (!response.ok) {
      throw new Error(await response.text())
    }
    return response.blob()
  },
  listAccountingPeriods: (organizationId?: number, ledgerId?: number) => {
    const params = new URLSearchParams()
    if (organizationId) params.set('organization_id', String(organizationId))
    if (ledgerId) params.set('ledger_id', String(ledgerId))
    const query = params.toString()
    return request<AccountingPeriod[]>(`/api/accounting-periods${query ? `?${query}` : ''}`)
  },
  recommendAccountingPeriod: (targetDate?: string, organizationId?: number, periodType?: string) => {
    const params = new URLSearchParams()
    if (targetDate) params.set('target_date', targetDate)
    if (organizationId) params.set('organization_id', String(organizationId))
    if (periodType) params.set('period_type', periodType)
    const query = params.toString()
    return request<AccountingPeriodRecommendation>(`/api/accounting-periods/recommendation${query ? `?${query}` : ''}`)
  },
  listChartOfAccounts: () => request<ChartOfAccount[]>('/api/coa'),
  listCoaIndustryTemplates: () => request<CoaIndustryTemplate[]>('/api/coa/industry-templates'),
  previewCoaIndustryTemplate: (templateCode: string) =>
    request<CoaTemplatePreview>(`/api/coa/industry-templates/${templateCode}`),
  importCoaIndustryTemplate: (templateCode: string) =>
    request<{ template: CoaIndustryTemplate; summary: CoaTemplatePreview['summary']; created_accounts: CoaTemplateAccount[] }>(
      `/api/coa/industry-templates/${templateCode}/import`,
      { method: 'POST' }
    ),
  listCounterparties: () => request<Counterparty[]>('/api/counterparties'),
  listLedgerFiles: (filters?: {
    ledger_id?: number | null
    project_id?: number | null
    counterparty_id?: number | null
    file_type?: string
    parse_status?: string
    archive_category?: string
  }) => {
    const params = new URLSearchParams()
    if (filters?.ledger_id) params.set('ledger_id', String(filters.ledger_id))
    if (filters?.project_id) params.set('project_id', String(filters.project_id))
    if (filters?.counterparty_id) params.set('counterparty_id', String(filters.counterparty_id))
    if (filters?.file_type) params.set('file_type', filters.file_type)
    if (filters?.parse_status) params.set('parse_status', filters.parse_status)
    if (filters?.archive_category) params.set('archive_category', filters.archive_category)
    const query = params.toString()
    return request<SourceFileRead[]>(`/api/files${query ? `?${query}` : ''}`)
  },
  listProjectFiles: (projectId: number, filters?: { ledger_id?: number; archive_category?: string }) => {
    const params = new URLSearchParams()
    if (filters?.ledger_id) params.set('ledger_id', String(filters.ledger_id))
    if (filters?.archive_category) params.set('archive_category', filters.archive_category)
    const query = params.toString()
    return request<SourceFileRead[]>(`/api/projects/${projectId}/files${query ? `?${query}` : ''}`)
  },
  listModuleRegisters: (
    moduleKey: string,
    filters: { ledger_id: number; execution_status?: string; contract_type?: string; limit?: number },
  ) => {
    const params = new URLSearchParams({ ledger_id: String(filters.ledger_id) })
    if (filters.execution_status) params.set('execution_status', filters.execution_status)
    if (filters.contract_type) params.set('contract_type', filters.contract_type)
    if (filters.limit) params.set('limit', String(filters.limit))
    return request<ModuleRegisterListResponse>(`/api/module-registers/${moduleKey}?${params.toString()}`)
  },
  getModuleRegisterSummary: (ledgerId: number) =>
    request<ModuleRegisterSummary>(`/api/module-registers/summary?ledger_id=${ledgerId}`),
  bindFileCounterparty: (fileId: number, counterpartyId: number | null) =>
    request<SourceFileRead>(`/api/files/${fileId}/bind-counterparty`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ counterparty_id: counterpartyId }),
    }),
  updateFile: (fileId: number, payload: { filename?: string; file_type?: string; notes?: string }) =>
    request<SourceFileRead>(`/api/files/${fileId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  deleteFile: (fileId: number) =>
    request<{ deleted: number; message: string }>(`/api/files/${fileId}`, { method: 'DELETE' }),
  createAccountingPeriod: (payload: {
    organization_id?: number
    ledger_id?: number
    period_code: string
    start_date: string
    end_date: string
    period_type?: string
  }) =>
    request<AccountingPeriod>('/api/accounting-periods', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }),
  generateEntries: (
    jobId: number,
    periodId: number,
    accountingJudgmentPolicy: 'compliant_default' | 'revenue_first' | 'counterparty_first' = 'compliant_default',
  ) =>
    request<EntryDraft[]>(`/api/import-jobs/${jobId}/generate-entries`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        period_id: periodId,
        accounting_judgment_policy: accountingJudgmentPolicy,
      }),
    }),
  commitEntries: (jobId: number, periodId: number, drafts: EntryDraft[]) =>
    request<{ count: number; entry_ids: number[]; job_id: number }>(`/api/import-jobs/${jobId}/commit-entries`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ period_id: periodId, drafts })
    }),
  logAiDraftManualSwitch: (jobId: number, payload: AiDraftManualSwitchLogPayload) =>
    request<AiDraftManualSwitchLogResult>(`/api/import-jobs/${jobId}/ai-draft/manual-switch-log`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }),
  commitManualEntries: (periodId: number, drafts: EntryDraft[], organizationName?: string) =>
    request<ManualEntriesCommitResult>('/api/import-jobs/manual-entries', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        period_id: periodId,
        drafts,
        organization_name: organizationName || '临时组织'
      })
    }),
  listOpeningBalances: (organizationId: number, periodId: number, ledgerId?: number) => {
    const params = new URLSearchParams({
      organization_id: String(organizationId),
      period_id: String(periodId),
    })
    if (ledgerId) params.set('ledger_id', String(ledgerId))
    return request<OpeningBalance[]>(`/api/opening-balances?${params.toString()}`)
  },
  upsertOpeningBalance: (payload: {
    organization_id: number
    period_id: number
    ledger_id?: number
    account_code: string
    debit_balance?: number
    credit_balance?: number
    currency?: string
    notes?: string | null
  }) =>
    request<OpeningBalance>('/api/opening-balances', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }),
  bulkUpsertOpeningBalances: (organizationId: number, periodId: number, items: Array<{
    account_code: string
    debit_balance?: number
    credit_balance?: number
    currency?: string
    notes?: string | null
  }>, ledgerId?: number) =>
    request<OpeningBalance[]>('/api/opening-balances/bulk', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        organization_id: organizationId,
        period_id: periodId,
        ledger_id: ledgerId,
        items,
      })
    }),
  deleteOpeningBalance: (id: number) =>
    request<{ deleted: number }>(`/api/opening-balances/${id}`, { method: 'DELETE' }),
  getOpeningTrialBalance: (organizationId: number, periodId: number, ledgerId?: number) => {
    const params = new URLSearchParams({
      organization_id: String(organizationId),
      period_id: String(periodId),
    })
    if (ledgerId) params.set('ledger_id', String(ledgerId))
    return request<TrialBalance>(`/api/opening-balances/trial-balance?${params.toString()}`)
  },
  getTrialBalanceReport: (organizationId: number, periodId: number) =>
    request<TrialBalanceReport>(`/api/reports/trial-balance?organization_id=${organizationId}&period_id=${periodId}`),
  getBalanceSheetReport: (organizationId: number, periodId: number) =>
    request<BalanceSheetReport>(`/api/reports/balance-sheet?organization_id=${organizationId}&period_id=${periodId}`),
  getIncomeStatementReport: (organizationId: number, periodId: number) =>
    request<IncomeStatementReport>(`/api/reports/income-statement?organization_id=${organizationId}&period_id=${periodId}`),
  plTransfer: (periodId: number) =>
    request<{ period_id: number; voucher_no: string; lines: number; net_profit: number; status: string }>(
      `/api/accounting-periods/${periodId}/pl-transfer`,
      { method: 'POST' }
    ),
  plTransferReverse: (periodId: number) =>
    request<{ period_id: number; voucher_no: string; deleted_lines: number; status: string }>(
      `/api/accounting-periods/${periodId}/pl-transfer/reverse`,
      { method: 'POST' }
    ),
  closePeriod: (periodId: number) =>
    request<AccountingPeriod>(
      `/api/accounting-periods/${periodId}/close`,
      { method: 'POST' }
    ),
  reopenPeriod: (periodId: number) =>
    request<AccountingPeriod>(
      `/api/accounting-periods/${periodId}/reopen`,
      { method: 'POST' }
    ),
  getDashboardSummary: (ledgerId?: number) => {
    const headers = ledgerId ? { 'X-Ledger-Id': String(ledgerId) } : undefined
    return request<{
      user: {
        id: number
        username: string
        team: { id: number; name: string } | null
      }
      voucher_count: number
      unclosed_periods: number
      unaudited_periods: number
      pending_risks: number
      recent_findings: number
      unposted_periods: number
      notifications: number
      module_status: {
        ledger: { pending_vouchers: number; unclosed_periods: number }
        audit: { active_projects: number; pending_tests: number }
        bank: { unreconciled: number }
        tax: { pending_invoices: number }
        basic: { incomplete_accounts: number }
      }
    }>('/api/dashboard/summary', { headers })
  },
  listProjects: () => request<Project[]>('/api/projects'),
  createProject: (payload: {
    team_id: number
    name: string
    project_type?: string
    status?: string
    start_date?: string | null
    end_date?: string | null
    manager_id?: number | null
  }) =>
    request<Project>('/api/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }),
  getProject: (id: number) => request<Project>(`/api/projects/${id}`),
  updateProject: (id: number, payload: Partial<Project>) =>
    request<Project>(`/api/projects/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }),
  deleteProject: (id: number) =>
    request<{ deleted: number }>(`/api/projects/${id}`, { method: 'DELETE' }),

  listBankAccounts: (ledgerId: number) =>
    request<BankAccount[]>('/api/bank/accounts', { headers: { 'X-Ledger-Id': String(ledgerId) } }),
  createBankAccount: (ledgerId: number, payload: {
    bank_name: string
    account_no: string
    account_name: string
    coa_account_code?: string
    opening_balance?: number
  }) =>
    request<BankAccount>('/api/bank/accounts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Ledger-Id': String(ledgerId) },
      body: JSON.stringify(payload),
    }),
  listBankTransactions: (ledgerId: number, status?: string) =>
    request<BankTransaction[]>(`/api/bank/transactions${status ? `?status=${status}` : ''}`, {
      headers: { 'X-Ledger-Id': String(ledgerId) },
    }),
  createBankTransaction: (ledgerId: number, payload: {
    bank_account_id: number
    transaction_date: string
    direction: 'in' | 'out'
    amount: number
    summary?: string
    counterparty?: string
  }) =>
    request<BankTransaction>('/api/bank/transactions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Ledger-Id': String(ledgerId) },
      body: JSON.stringify(payload),
    }),
  getBankSummary: (ledgerId: number) =>
    request<BankSummary>('/api/bank/summary', { headers: { 'X-Ledger-Id': String(ledgerId) } }),
  autoReconcile: (ledgerId: number) =>
    request<BankReconcileResult>('/api/bank/reconcile/auto', {
      method: 'POST',
      headers: { 'X-Ledger-Id': String(ledgerId) },
    }),
  listBankReconciliations: (ledgerId: number) =>
    request<BankReconciliationDraft[]>('/api/bank/reconciliations', {
      headers: { 'X-Ledger-Id': String(ledgerId) },
    }),
  createBankReconciliationDraft: (
    ledgerId: number,
    payload: { bank_account_id: number; period_end: string; statement_balance?: number },
  ) =>
    request<BankReconciliationDraft>('/api/bank/reconciliations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Ledger-Id': String(ledgerId) },
      body: JSON.stringify(payload),
    }),
  getBankReconciliation: (ledgerId: number, reconciliationId: number) =>
    request<BankReconciliationDraft>(`/api/bank/reconciliations/${reconciliationId}`, {
      headers: { 'X-Ledger-Id': String(ledgerId) },
    }),

  listConfirmations: (ledgerId: number) =>
    request<CounterpartyConfirmation[]>('/api/confirmations', {
      headers: { 'X-Ledger-Id': String(ledgerId) },
    }),
  generateConfirmations: (
    ledgerId: number,
    payload: { counterparty_ids?: number[]; balance_types?: string[] },
  ) =>
    request<CounterpartyConfirmation[]>('/api/confirmations/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Ledger-Id': String(ledgerId) },
      body: JSON.stringify(payload),
    }),
  updateConfirmation: (
    ledgerId: number,
    confirmationId: number,
    payload: { status?: string; confirmation_amount?: number; reply_amount?: number; source_file_id?: number },
  ) =>
    request<CounterpartyConfirmation>(`/api/confirmations/${confirmationId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', 'X-Ledger-Id': String(ledgerId) },
      body: JSON.stringify(payload),
    }),
  recordConfirmationReply: (
    ledgerId: number,
    confirmationId: number,
    payload: { reply_amount: number; source_file_id?: number },
  ) =>
    request<CounterpartyConfirmation>(`/api/confirmations/${confirmationId}/reply`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Ledger-Id': String(ledgerId) },
      body: JSON.stringify(payload),
    }),

  listPurchaseMatches: (ledgerId: number, contractId?: number) =>
    request<PurchaseMatchResult[]>(
      `/api/audit/purchase-match${contractId ? `?contract_id=${contractId}` : ''}`,
      { headers: { 'X-Ledger-Id': String(ledgerId) } },
    ),
  getPurchaseMatchSummary: (ledgerId: number) =>
    request<PurchaseMatchSummary>('/api/audit/purchase-match/summary', {
      headers: { 'X-Ledger-Id': String(ledgerId) },
    }),

  listWorkpaperIndexes: (ledgerId: number, projectId?: number) =>
    request<WorkpaperIndex[]>(
      `/api/workpapers/index${projectId ? `?project_id=${projectId}` : ''}`,
      { headers: { 'X-Ledger-Id': String(ledgerId) } },
    ),
  getWorkpaperIndex: (ledgerId: number, indexId: number) =>
    request<WorkpaperIndex>(`/api/workpapers/index/${indexId}`, {
      headers: { 'X-Ledger-Id': String(ledgerId) },
    }),
  syncWorkpapersFromArchive: (ledgerId: number) =>
    request<WorkpaperIndex[]>('/api/workpapers/sync-from-archive', {
      method: 'POST',
      headers: { 'X-Ledger-Id': String(ledgerId) },
    }),
  exportWorkpaperCatalog: (ledgerId: number) =>
    request<WorkpaperCatalog>('/api/workpapers/export', {
      headers: { 'X-Ledger-Id': String(ledgerId) },
    }),

  getWorkflowConfig: (projectId: number) =>
    request<WorkflowConfig>(`/api/audit/workflow/config?project_id=${projectId}`),
  updateWorkflowConfig: (
    projectId: number,
    payload: { granularity?: string; enabled_procedures?: string[]; auto_link_workpaper?: boolean },
  ) =>
    request<WorkflowConfig>(`/api/audit/workflow/config?project_id=${projectId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  listAuditProcedureRuns: (ledgerId: number, projectId?: number, status?: string) =>
    request<AuditProcedureRun[]>(
      `/api/audit/workflow/runs?${[
        projectId ? `project_id=${projectId}` : '',
        status ? `status=${status}` : '',
      ].filter(Boolean).join('&')}`,
      { headers: { 'X-Ledger-Id': String(ledgerId) } },
    ),
  advanceAuditProcedureRun: (
    ledgerId: number,
    runId: number,
    payload: { action?: string; target_status?: string; notes?: string },
  ) =>
    request<AuditProcedureRun>(`/api/audit/workflow/runs/${runId}/advance`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Ledger-Id': String(ledgerId) },
      body: JSON.stringify(payload),
    }),

  createEntity: (payload: EntityCreatePayload) =>
    request<{ id: number; entity_name: string; ledger_id?: number | null; is_accounting_entity: boolean }>('/api/entities', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  // Ledger APIs
  createLedger: (payload: CreateLedgerPayload) =>
    request<Ledger>('/api/ledgers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  listLedgers: () => request<Ledger[]>('/api/ledgers'),
  switchLedger: (ledgerId: number) =>
    request<{ ledger_id: number; message: string }>(`/api/ledgers/${ledgerId}/switch`, { method: 'POST' }),
  getLedgerAuths: (ledgerId: number) =>
    request<LedgerAuth[]>(`/api/ledgers/${ledgerId}/auths`),
  grantLedgerAuth: (ledgerId: number, payload: { user_id: number; role: string }) =>
    request<{ message: string; user_id: number; ledger_id: number; role: string }>(`/api/ledgers/${ledgerId}/auth`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  revokeLedgerAuth: (ledgerId: number, authId: number) =>
    request<{ message: string; auth_id: number; user_id: number; ledger_id: number }>(
      `/api/ledgers/${ledgerId}/auths/${authId}`,
      { method: 'DELETE' }
    ),
  updateLedgerLifecycle: (ledgerId: number, action: string, reason?: string) =>
    request<Ledger>(`/api/ledgers/${ledgerId}/${action}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason: reason || undefined }),
    }),
}
