const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

/** 序时簿/分录列表 API 单页最多行数 */
export const ENTRIES_PAGE_MAX_LIMIT = 500

/** 凭证查询页单页最多展示的凭证张数（与后端 VOUCHER_QUERY_PAGE_MAX 一致） */
export const VOUCHER_QUERY_PAGE_MAX = 500

function clampEntriesPageLimit(limit?: number): number {
  if (limit == null) return ENTRIES_PAGE_MAX_LIMIT
  return Math.min(Math.max(limit, 1), ENTRIES_PAGE_MAX_LIMIT)
}

function clampVoucherQueryLimit(limit?: number): number {
  if (limit == null) return 50
  return Math.min(Math.max(limit, 1), VOUCHER_QUERY_PAGE_MAX)
}

export type ComplianceStreamEvent =
  | { type: 'status'; message: string }
  | {
      type: 'models'
      parse_model: string
      reasoning_model: string
      active_model: string
      reasoning_configured: boolean
    }
  | { type: 'vector_done'; count: number }
  | { type: 'thinking'; delta: string; text: string }
  | { type: 'content'; delta: string; text: string }
  | { type: 'voucher_done'; item: Record<string, unknown> }
  | {
      type: 'done'
      reviewed_vouchers: number
      skipped: boolean
      scope?: string
      items: Array<Record<string, unknown>>
    }
  | { type: 'error'; message: string }

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

export type ImportJobCleanupRow = {
  id: number
  status: string
  source_type: string
  file_count: number
  entry_count: number
  staging_rows: number
  error_message: string | null
  created_at: string | null
  ledger_id: number | null
  cleanable: boolean
  stuck: boolean
  stuck_reason: string | null
}

export type ImportJobCleanupSummary = {
  ledger_id: number | null
  total_jobs: number
  by_status: Record<string, number>
  cleanable_count: number
  stuck_count: number
  total_staging_rows: number
  stuck_active_hours: number
  cleanable_statuses: string[]
  jobs: ImportJobCleanupRow[]
  cleanable_jobs: ImportJobCleanupRow[]
  stuck_jobs: ImportJobCleanupRow[]
}

export type ImportJobCleanupResult = {
  purged_count: number
  skipped_count: number
  purged: Array<{
    job_id: number
    purged: boolean
    staging_rows_deleted: number
    related_records_deleted: number
    source_files_deleted: number
  }>
  skipped: Array<{ job_id: number; reason: string }>
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
  ledger_id?: number | null
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
  source_file_id?: number | null
  compliance_hint?: string | null
  compliance_severity?: string
  spot_check_flag?: boolean
  created_at: string
  resolved_account_code: string | null
  resolved_account_name: string | null
  counterparty_id: number | null
  entry_tags_payload?: Array<{
    category_code?: string
    tag_value?: string
    display_name?: string
    source_sub_code?: string | null
    name_standardized?: boolean
  }>
  requires_llm_resolution: boolean
}

export type ChronologicalEntryFilters = {
  ledger_id: number
  period_id?: number
  period_ids?: number[]
  date_from?: string
  date_to?: string
  account_code?: string
  account_codes?: string[]
  account_code_match?: 'exact' | 'prefix' | 'contains'
  account_name?: string
  summary?: string
  voucher_word?: string
  voucher_no?: string
  amount_min?: number
  amount_max?: number
  tag_category_code?: string
  tag_value?: string
  tag_filters?: string
  counterparty?: string
  tag_match_scope?: 'entry' | 'voucher'
  limit?: number
  offset?: number
}

export type ChronologicalEntryListResponse = {
  items: AccountingEntry[]
  total: number
  limit: number
  offset: number
}

export type EntryListResponse = ChronologicalEntryListResponse

export type EntryReviewStats = {
  total: number
  verified: number
  ready: number
  unreviewed: number
  status_counts: Record<string, number>
}

export type VoucherCard = {
  voucher_id?: number
  voucher_no: string | null
  voucher_date: string | null
  voucher_word: string | null
  status?: string
  line_count: number
  debit_total: number
  credit_total: number
  summary_preview: string | null
  lines?: AccountingEntry[]
}

export type VoucherLinesResponse = {
  items: AccountingEntry[]
}

export type VoucherQueryFilters = {
  ledger_id: number
  period_id?: number
  date_from?: string
  date_to?: string
  month?: string
  import_job_id?: number
  review_status?: string
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
  include_lines?: boolean
  limit?: number
  offset?: number
}

export type VoucherQueryResponse = {
  items: VoucherCard[]
  total: number
  limit: number
  offset: number
}

export type VoucherDeleteKey = {
  voucher_no: string | null
  voucher_date: string | null
}

export type VoucherLinePayload = {
  line_no: number
  summary: string
  account_code: string
  account_name?: string
  debit_amount: string
  credit_amount: string
  counterparty?: string
  counterparty_id?: number
}

export type VoucherCreatePayload = {
  ledger_id: number
  organization_id: number
  period_id: number
  voucher_type: string
  voucher_number: string
  voucher_date: string
  summary?: string
  attachment_count?: number
  lines: VoucherLinePayload[]
}

export type VoucherUpdatePayload = Partial<VoucherCreatePayload>

export type VoucherLineItem = {
  entry_id: number
  line_no: number
  summary: string
  account_code: string
  account_name?: string
  debit_amount: string
  credit_amount: string
  counterparty?: string
  counterparty_id?: number
}

export type VoucherResponse = {
  success: boolean
  data: {
    voucher_id: number
    ledger_id: number
    organization_id: number
    period_id?: number
    voucher_no: string
    voucher_type?: string
    voucher_number?: string
    voucher_date: string
    summary?: string
    status: string
    total_debit: string
    total_credit: string
    attachment_count: number
    source_type: string
    created_by: number
    created_by_name?: string
    created_at: string
    updated_at?: string
    posted_at?: string
    posted_by?: number
    lines: VoucherLineItem[]
  }
  message: string
}

export type VoucherBatchDeleteResponse = {
  deleted_vouchers: number
  deleted_entries: number
}

export type AccountingEntryUpdate = Partial<Pick<
  AccountingEntry,
  'voucher_no' | 'voucher_date' | 'summary' | 'account_code' | 'account_name' | 'debit_amount' | 'credit_amount' | 'counterparty'
>>

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
    voucher_date?: string | null
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
  error_rows?: number
  quality_score?: number
  engine?: string
  expected_columns?: string[]
  guidance?: string
}

export type AuditFinding = {
  id: string
  db_id?: number
  job_id?: number
  ledger_id?: number | null
  finding_type: string
  severity: string
  business_type: string
  related_entries: string[] | Array<Record<string, unknown>>
  related_files: string[]
  finding_title: string
  finding_description: string
  audit_procedure: string
  audit_conclusion: string
  risk_statement: string
  recommendation: string
  metadata: Record<string, unknown>
  status?: string
  created_at?: string | null
}

export type WorkbenchItem = {
  id: string
  source: 'internal_control' | 'dimension' | 'risk' | string
  source_label: string
  severity: 'blocking' | 'warning' | 'info' | string
  category: string
  title: string
  description: string
  status: string
  ledger_id?: number | null
  job_id?: number | null
  related_finding_id?: number | null
  related_entry_ids?: number[]
  related_source_file_ids?: number[]
  metadata?: Record<string, unknown>
  suggested_path?: string | null
  suggested_action?: string | null
  created_at?: string | null
}

export type WorkbenchQueueResponse = {
  ledger_id: number
  summary: {
    total: number
    blocking: number
    warning: number
    info: number
    by_source: {
      internal_control: number
      dimension: number
      risk: number
    }
  }
  items: WorkbenchItem[]
}

export type EntrySourceEvidence = {
  entry_id: number
  source_file_id: number | null
  linked: boolean
  evidence_path: string | null
  source_file: {
    id: number
    filename: string
    file_type?: string | null
    ledger_id?: number | null
    parse_status?: string | null
    evidence_lifecycle?: string | null
    ingest_channel?: string | null
    archive_category?: string | null
    period_code?: string | null
    project_id?: number | null
  } | null
}

export type IngestApiExample = {
  ledger_id: number
  ledger_name: string
  endpoint: string
  method: string
  headers: Record<string, string>
  form_fields: Record<string, unknown>
  curl_example: string
  cli_example: string
  notes: string[]
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

export type PlTransferBatchResult = {
  ledger_id: number
  total: number
  succeeded_count: number
  failed_count: number
  skipped_count: number
  stopped_early: boolean
  succeeded: Array<{
    period_id: number
    period_code: string
    status: string
    voucher_no?: string | null
    lines?: number | null
    net_profit?: number | null
  }>
  failed: Array<{
    period_id: number
    period_code: string
    status: string
    error?: string | null
  }>
  skipped: Array<{
    period_id: number
    period_code: string
    status: string
    reason?: string | null
  }>
}

export type AccountingPeriod = {
  id: number
  organization_id: number
  period_code: string
  period_type: string
  start_date: string
  end_date: string
  status: string
  snapshot_status?: string | null
  snapshot_version?: number
  source?: string
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
  object_name?: string | null
  object_names?: string[]
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
  evidence_lifecycle?: 'inbox' | 'archived' | string
  ingest_channel?: string | null
  customer_context?: {
    counterparty_id: number | null
    counterparty_name: string | null
    match_source: string | null
    confidence_note: string | null
  }
  created_at: string
}

export type DocumentTag = {
  id: number
  document_id: number
  document_type: string
  tag: string
  tag_type: string
  vector_id?: string | null
  vector_stored: boolean
  confidence: number
  source: string
  created_at: string
}

export type EntryTag = {
  id: number
  entry_id: number
  ledger_id: number
  category_id: number
  category_code: string
  category_name: string
  tag_name: string
  tag_type: string
  tag_value: string
  display_name: string
  confidence: number
  tag_source: string
  reviewed_by_user: boolean
  created_at: string
}

export type LlmTagSuggestion = {
  id: number
  entry_id: number
  category_id?: number
  category_code: string
  category_name: string
  tag_value: string
  display_name: string
  confidence: number
  tag_source: string
  created_at: string
}

export type LlmResolutionResult = {
  task_id: string
  total_entries: number
  success_count: number
  failed_count: number
  processing_time_ms: number
  error_messages: string[]
  suggested_tags: LlmTagSuggestion[]
}

export type LlmResolutionStatistics = {
  pending_llm_resolution: number
  pending_review: number
  reviewed: number
}

export type AccountTagConfig = {
  version: string
  mandatory_hierarchical_accounts: string[]
  mandatory_hierarchical_keywords: string[]
  account_code_tag_category: Record<string, string>
  account_name_tag_category: Record<string, string>
  auxiliary_keywords: Record<string, string[]>
}

export type SealTextItem = {
  text: string
  x: number
  y: number
  width: number
  height: number
  confidence: number
}

export type ContractSeal = {
  id: number
  contract_id: number
  source_file_id?: number | null
  page_no: number
  bbox: { x1: number; y1: number; x2: number; y2: number }
  seal_image_path?: string | null
  recognized_text?: string | null
  text_items?: SealTextItem[]
  seal_type?: string | null
  confidence: number
  detection_method?: string | null
  created_at: string
  updated_at: string
}

export type ContractSealListResponse = {
  total: number
  page: number
  size: number
  items: ContractSeal[]
}

export type ContractSealExtractResponse = {
  contract_id: number
  extracted_count: number
  seals: ContractSeal[]
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
  detected_months?: string[]
  is_multi_period?: boolean
  suggested_period: AccountingPeriodSuggestion | null
  matched_period: (AccountingPeriod & { id: number }) | null
  reason: string
}

export type PeriodMappingMode = 'preserve_source' | 'unify_target'

export type ApplyImportPeriodMappingPayload = {
  period_mapping_mode: PeriodMappingMode
  period_mode?: 'adaptive' | 'fixed' | null
  period_id?: number | null
  period_start_date?: string | null
  period_end_date?: string | null
}

export type ApplyImportPeriodMappingResult = {
  period_mapping_mode: PeriodMappingMode
  period_mode: string | null
  assigned_voucher_count: number
  total_voucher_count: number
  created_period_codes: string[]
  used_period_codes: string[]
  out_of_range_count: number
  primary_period_id: number | null
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

export type ProjectTaskAssignee = {
  id: number
  username: string | null
  email: string | null
  phone: string | null
  team_id: number | null
  project_role: string | null
  ledger_roles: string[]
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
  user: {
    id: number
    username: string | null
    phone: string | null
    email: string | null
    has_password?: boolean
    platform_role?: 'user' | 'super_admin' | string
    is_super_admin?: boolean
  }
  teams: Team[]
  ledgers: Ledger[]
  projects: Project[]
  current_ledger_id: number | null
  current_ledger_role?: string | null
  current_team_type?: string | null
  can_use_ledger_without_project?: boolean
  platform_role?: 'user' | 'super_admin' | string
  is_super_admin?: boolean
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

export type SuperAdminOverview = {
  user_count: number
  team_count: number
  ledger_count: number
  project_count: number
  pending_binding_request_count: number
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
  ytd_debit: number
  ytd_credit: number
  closing_debit: number
  closing_credit: number
}

export type LedgerReportMeta = {
  period_id?: number
  period_code?: string
  period_status?: string
  period_start_date?: string
  period_end_date?: string
  as_of_date?: string
  balance_source?: 'live' | 'snapshot'
  snapshot_frozen?: boolean
}

export type TrialBalanceReport = LedgerReportMeta & {
  rows: TrialBalanceRow[]
  totals: {
    opening_debit: number
    opening_credit: number
    period_debit: number
    period_credit: number
    ytd_debit: number
    ytd_credit: number
    closing_debit: number
    closing_credit: number
  }
  is_balanced: boolean
}

export type PlTransferHealth = {
  period_id: number
  period_code: string
  period_status: string
  is_balanced: boolean
  has_system_pl_voucher: boolean
  imported_pl_voucher_count: number
  profit_accounts_cleared?: boolean
  ready?: boolean
  mode?: string
  can_close_without_manual_transfer?: boolean
  message?: string
  non_zero_profit_accounts?: Array<{
    account_code: string
    account_name: string
    closing_debit: string
    closing_credit: string
  }>
  imported_pl_vouchers?: Array<{
    voucher_id: number
    voucher_no: string | null
    voucher_date: string
    summary: string | null
    pl_accounts: string[]
  }>
  period_status_consistent: boolean
  warnings: string[]
  fixed?: boolean
}

export type BalanceSheetPresentationMode = 'balance' | 'net_movement'

export type AuditAssertionRisk = {
  assertion: string
  risk_level: 'high' | 'medium' | 'low'
  risk_description: string
  related_accounts?: string[]
}

export type ReclassificationAdjustment = {
  from_account_code: string
  from_account_name?: string
  to_account_code: string
  to_account_name?: string
  amount: string | number
  balance_direction?: string
  reason?: string
  standard_basis?: string
  standard_reference?: string
  audit_assertion_risks?: AuditAssertionRisk[]
  counterparty_semantic_note?: string
}

export type ReclassificationSummary = {
  applied: boolean
  adjustment_count: number
  standard_note: string
  items: Array<{
    from_account_code: string
    from_account_name?: string
    to_account_code: string
    to_account_name?: string
    amount: string | number
    reason?: string
    standard_basis?: string | null
    standard_reference?: string | null
    audit_assertion_risks?: AuditAssertionRisk[]
  }>
  assertion_risk_summary: AuditAssertionRisk[]
}

export type FinancialStatementLine = {
  line_no: number | string
  line_code?: string
  label: string
  section?: string
  group?: string
  is_header?: boolean
  is_subtotal?: boolean
  direction?: string
  opening_balance?: string | number
  closing_balance?: string | number
  current_amount?: string | number
  prior_amount?: string | number
  ytd_amount?: string | number
  month_amount?: string | number
  year_to_date_amount?: string | number
  account_codes?: string[]
  reconciled_with_direct?: boolean
}

export type ClassicDualColumnBalanceSheet = {
  format: string
  paired_rows: Array<{
    row_index: number
    asset_label: string
    asset_opening: string | number
    asset_closing: string | number
    asset_is_section?: boolean
    asset_is_subtotal?: boolean
    liability_label: string
    liability_opening: string | number
    liability_closing: string | number
    liability_is_section?: boolean
    liability_is_subtotal?: boolean
  }>
}

export type BalanceSheetReport = LedgerReportMeta & {
  assets: TrialBalanceRow[]
  liabilities: TrialBalanceRow[]
  equity: TrialBalanceRow[]
  assets_total: number
  liabilities_total: number
  equity_total: number
  is_balanced: boolean
  statement_lines?: FinancialStatementLine[]
  classic_dual_column?: ClassicDualColumnBalanceSheet
  format?: string
  statement_balanced?: boolean
  presentation_mode?: BalanceSheetPresentationMode
  uses_resolved_account_code?: boolean
  unmapped_entry_net?: string | number
  coa_gap_mapping_count?: number
  coa_gap_mappings?: Record<string, string>
  unmapped_codes?: string[]
  pl_transfer_health?: PlTransferHealth
  reclassification_adjustments?: ReclassificationAdjustment[]
  reclassification_summary?: ReclassificationSummary
}

export type IncomeStatementReport = LedgerReportMeta & {
  ledger_name?: string
  revenue: Record<string, number>
  expense: Record<string, number>
  ytd_revenue?: Record<string, number>
  ytd_expense?: Record<string, number>
  statement_lines?: FinancialStatementLine[]
  operating_revenue: number
  operating_cost: number
  period_expenses: number
  operating_profit: number
  total_profit: number
  income_tax: number
  net_profit: number
  ytd_operating_profit?: number
  ytd_total_profit?: number
  ytd_income_tax?: number
  ytd_net_profit?: number
}

export type ReportExportSignature = {
  preparer_name?: string
  reviewer_name?: string
  approver_name?: string
}

export type CashFlowActivityBlock = {
  inflow: string
  outflow: string
  net: string
}

export type CashFlowStatementReport = {
  method?: string
  statement_lines?: FinancialStatementLine[]
  indirect_lines?: FinancialStatementLine[]
  direct_indirect_reconciled?: boolean
  compilation_notes?: string[]
  pattern_flags?: {
    direct_revenue_to_bank?: boolean
    receivable_collection?: boolean
  }
  operating_activities: CashFlowActivityBlock
  investing_activities: CashFlowActivityBlock
  financing_activities: CashFlowActivityBlock
  net_increase_in_cash: string
  period_id?: number
  period_code?: string
  as_of_date?: string
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
  source_sub_code?: string | null
  opening_balance: number
  current_balance: number
  is_active: boolean
}

export type TagCategoryNode = {
  id: number
  code: string
  name: string
  description?: string | null
  level?: number
  value_type: string
  source_table?: string | null
  is_mandatory: boolean
  is_system?: boolean
  status: string
  sort_order: number
  children?: TagCategoryNode[]
}

export type TagMappingRule = {
  id: number
  source_pattern: string
  source_type: string
  target_category_code: string
  target_value: string | null
  priority: number
  is_regex: boolean
  is_active: boolean
  description?: string | null
}

export type EntryTagAggregate = {
  tag_value: string
  count: number
  avg_weight: number
  display_name?: string | null
}

export type MasterSyncResult = {
  synced?: boolean
  reason?: string
  target?: string
  action?: string
  id?: number
  category_code?: string
}

export type DimensionPendingQueueItem = {
  queue_type:
    | 'non_standardized'
    | 'missing_in_master'
    | 'requires_llm'
    | 'unknown_category'
    | 'internal_control'
    | 'mapped'
  priority: 'high' | 'medium' | 'low'
  account_code?: string
  account_name?: string
  category_code?: string
  source_sub_code?: string | null
  tag_value?: string
  display_name?: string
  original_display_name?: string
  mapped_at?: string
  mapped_by_user_id?: number
  line_count?: number
  voucher_count?: number
  staging_id?: number
  voucher_no?: string
  summary?: string
  finding_id?: number
  message: string
}

export type DimensionPendingQueueResponse = {
  job_id: number
  ledger_id: number | null
  summary: {
    total: number
    non_standardized: number
    missing_in_master: number
    requires_llm: number
    unknown_category: number
    internal_control: number
    mapped: number
  }
  items: DimensionPendingQueueItem[]
  registry_warnings: Array<{
    severity: string
    code: string
    account_code?: string
    message: string
  }>
}

export type DimensionRegistryResponse = {
  job_id: number
  ledger_id: number | null
  dimension_count: number
  blocking: boolean
  items: Array<{
    account_code: string
    account_name: string
    category_code: string
    source_sub_code: string | null
    tag_value: string
    display_name: string
    name_standardized: boolean
    line_count: number
    voucher_count: number
  }>
  warnings: Array<{
    severity: string
    code: string
    account_code?: string
    message: string
    coa_sub_codes?: string[]
    used_sub_codes?: string[]
    missing_in_import?: string[]
    items?: Array<{ source_sub_code?: string | null; display_name?: string; tag_value?: string }>
  }>
  layers?: {
    config_coa: Array<{ parent_code: string; account_code: string }>
    config_bank_evidence: Array<{
      bank_name: string
      account_no: string
      account_name: string
      coa_account_code: string
      source_sub_code?: string | null
    }>
    import_used: DimensionRegistryResponse['items']
  }
  comparison?: {
    matched: Array<Record<string, unknown>>
    in_import_not_in_evidence: DimensionRegistryResponse['items']
    in_evidence_not_in_import: Array<{
      source_sub_code?: string | null
      bank_name: string
      account_no: string
    }>
    coa_gaps: Array<{
      account_code: string
      missing_in_import: string[]
      defined_sub_codes: string[]
      used_sub_codes: string[]
    }>
  }
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
  file_name?: string | null
  file_ext?: string | null
  mime_type?: string | null
  storage_path?: string | null
  file_hash?: string | null
  file_size?: number | null
  template_code?: string | null
  sheet_count?: number | null
  workbook_metadata?: { sheets?: string[] } | Record<string, unknown> | null
  generated_from?: string | null
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

export type ScopeSettingsCatalogField = {
  label: string
  type: 'select' | 'boolean' | 'text'
  options?: Array<{ value: string; label: string }>
  depends_on?: Record<string, boolean | string>
}

export type ScopeSettingsCatalog = Record<
  string,
  {
    label: string
    description: string
    fields: Record<string, ScopeSettingsCatalogField>
  }
>

export type LedgerSettingsData = {
  currency_mode: 'single' | 'multi'
  base_currency: string
  balance_direction_rule: 'strict' | 'natural'
  account_code_pattern: '4-2-2-2' | '3-3-2-2'
  allow_custom_subjects: boolean
}

export type TeamSettingsData = {
  allow_multi_team_membership: boolean
  require_binding_approval: boolean
  default_ledger_role: 'admin' | 'accountant' | 'viewer'
  ledger_grant_policy: 'admin_only' | 'manager_can_grant'
  team_roles_enabled: string[]
}

export type ProjectSettingsData = {
  allow_merge: boolean
  allow_virtual_project: boolean
  virtual_project_label: string
  require_manager_on_create: boolean
}

export type AuditTask = {
  id: number
  project_id: number
  ledger_id?: number | null
  task_no: string
  title: string
  description?: string | null
  task_type: string
  audit_area?: string | null
  status: string
  priority: string
  created_by: number
  assignee_id?: number | null
  reviewer_ids?: number[] | null
  related_finding_id?: number | null
  related_procedure_key?: string | null
  parent_task_id?: number | null
  labels?: string[] | null
  due_date?: string | null
  created_at: string
  updated_at: string
  closed_at?: string | null
}

export type AuditTaskCreate = {
  project_id: number
  ledger_id?: number | null
  title: string
  description?: string | null
  task_type?: string
  audit_area?: string | null
  priority?: string
  assignee_id?: number | null
  due_date?: string | null
  related_finding_id?: number | null
  related_procedure_key?: string | null
}

export type AuditTaskUpdate = {
  title?: string
  description?: string | null
  task_type?: string
  audit_area?: string | null
  priority?: string
  status?: string
  assignee_id?: number | null
  due_date?: string | null
}

export type AuditTaskListResponse = {
  items: AuditTask[]
  total: number
  page: number
  page_size: number
}

export type AuditWorkBranch = {
  id: number
  project_id: number
  ledger_id?: number | null
  task_id: number
  branch_name: string
  base_branch?: string | null
  status: string
  created_by: number
  assignee_id?: number | null
  workpaper_index_id?: number | null
  procedure_run_id?: number | null
  latest_version_id?: number | null
  created_at: string
  updated_at: string
  merged_at?: string | null
}

export type AuditWorkBranchCreate = {
  task_id: number
  project_id: number
  ledger_id?: number | null
  branch_name: string
  base_branch?: string
  assignee_id?: number | null
  workpaper_index_id?: number | null
  procedure_run_id?: number | null
}

export type AuditReviewRequest = {
  id: number
  project_id: number
  ledger_id?: number | null
  task_id: number
  branch_id: number
  pr_no: string
  title: string
  description?: string | null
  target_branch: string
  status: string
  current_review_level: number
  created_by: number
  reviewer_level_1_id?: number | null
  reviewer_level_2_id?: number | null
  reviewer_level_3_id?: number | null
  submitted_version_id?: number | null
  approved_version_id?: number | null
  merged_version_id?: number | null
  merged_by?: number | null
  created_at: string
  submitted_at?: string | null
  approved_at?: string | null
  merged_at?: string | null
  closed_at?: string | null
}

export type AuditReviewRequestCreate = {
  task_id: number
  branch_id: number
  project_id: number
  ledger_id?: number | null
  title: string
  description?: string | null
  target_branch?: string
  reviewer_level_1_id?: number | null
  reviewer_level_2_id?: number | null
  reviewer_level_3_id?: number | null
  submitted_version_id?: number | null
}

export type AuditReviewAction = {
  id: number
  review_request_id: number
  review_level: number
  action: string
  comment?: string | null
  reviewer_id: number
  created_at: string
}

export type AuditReviewActionCreate = {
  action: string
  comment?: string | null
  review_level?: number
}

export type AuditReviewSubmit = {
  reviewer_level_1_id?: number | null
}

export type AuditReviewListResponse = {
  items: AuditReviewRequest[]
  total: number
  page: number
  page_size: number
}

export type AuditComment = {
  id: number
  target_type: string
  target_id: number
  content: string
  mention_user_ids?: number[] | null
  marker_type?: string | null
  sheet_name?: string | null
  cell_ref?: string | null
  range_ref?: string | null
  severity?: string | null
  resolved_at?: string | null
  resolved_by?: number | null
  created_by: number
  created_at: string
  updated_at: string
}

export type AuditCommentCreate = {
  target_type: string
  target_id: number
  content: string
  mention_user_ids?: number[] | null
  marker_type?: string | null
  sheet_name?: string | null
  cell_ref?: string | null
  range_ref?: string | null
  severity?: string | null
}

export type AuditNotification = {
  id: number
  recipient_user_id: number
  actor_user_id?: number | null
  event_type: string
  target_type: string
  target_id: number
  title: string
  content?: string | null
  is_read: boolean
  project_id?: number | null
  ledger_id?: number | null
  created_at?: string | null
  read_at?: string | null
}

export type AuditNotificationListResponse = {
  items: AuditNotification[]
  unread_count: number
}

export type AuditDashboardStats = {
  todo_tasks_count: number
  in_progress_tasks_count: number
  review_tasks_count: number
  pending_my_review_count: number
  submitted_by_me_count: number
  closed_today_count: number
}

export type EntityScopeSettingsData = {
  allow_virtual_entity: boolean
  require_tax_registration: boolean
  default_entity_category: 'operating' | 'holding' | 'branch'
  allow_multi_entity_per_ledger: boolean
}

export type ScopeSettingsResponse<T> = {
  scope: string
  settings: T
  created_at: string | null
  updated_at: string | null
  ledger_id?: number
  team_id?: number
  project_id?: number
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
  username?: string | null
  phone?: string | null
  granted_at: string | null
  granted_by?: number | null
}

export type CreateLedgerPayload = {
  name: string
  team_id: number
  accounting_start_date?: string
}

export type UpdateLedgerPayload = {
  name?: string
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

export type AgentToolExecution = {
  tool_name: string
  status: 'success' | 'failed'
  result?: Record<string, unknown>
  error?: string
}

export type TaxEgressNode = {
  id: number
  node_key: string
  egress_ip: string
  provider?: string | null
  worker_host?: string | null
  status: string
  load: number
  max_tenants: number
  health_score: number
  last_health_at?: string | null
}

export type TaxEgressCityPool = {
  city_code: string
  city_name: string
  bureau_province: string
  pool_policy: string
  max_rotate_per_taxpayer_7d: number
  cooling_hours: number
  stats: { active_nodes: number; total_nodes: number; remaining_slots: number }
  nodes: TaxEgressNode[]
}

export type TaxEgressPoolsResponse = {
  pool_policy: string
  config: {
    seed_enabled: boolean
    max_rotate_per_taxpayer_7d: number
    cooling_hours: number
    default_lease_days: number
  }
  cities: TaxEgressCityPool[]
}

export type TaxEgressBinding = {
  id: number
  taxpayer_id: string
  taxpayer_name: string
  ledger_id?: number | null
  city_code: string
  city_name: string
  egress_ip?: string | null
  node_id?: number | null
  node_key?: string | null
  lease_end?: string | null
  rotate_count_7d: number
  binding_status: string
  session_state: string
}

export type TaxRotationEvent = {
  id: number
  time?: string | null
  taxpayer_id: string
  old_ip?: string | null
  new_ip?: string | null
  trigger: string
  detail?: string | null
  created_by?: string
}

export type TaxEgressSessionStart = {
  binding_id: number
  session_state: string
  egress_ip?: string | null
  message: string
}

export type AgentAssistResponse = {
  reply: string
  intent?: string
  confidence?: number
  source?: 'llm' | 'rules' | string
  model?: string | null
  model_config?: {
    provider?: string
    model_name?: string | null
    config_source?: string
    is_ollama?: boolean
    remote_model_configured?: boolean
  }
  ledger_id?: number | null
  tool_executions?: AgentToolExecution[]
  pending_actions?: Array<{ tool_name: string; reason: string; risk_level?: string }>
  suggested_path?: string | null
  steps?: string[]
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

export type EvolutionProposal = {
  id: number
  rule_name: string
  document_type: string
  rule_type: string
  target_field: string
  source: string | null
  source_correction_id: number | null
  source_header: string | null
  evidence_file: string | null
  file_name: string | null
  category: string | null
  shadow_note: string | null
  original_value: unknown
  corrected_value: unknown
  status: string
  created_at: string | null
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
    if (data.detail && typeof data.detail === 'object') {
      const detail = data.detail as { message?: unknown; unreviewed_count?: unknown; sample_entry_ids?: unknown }
      if (typeof detail.message === 'string') {
        const countText = typeof detail.unreviewed_count === 'number' ? `，未复核 ${detail.unreviewed_count} 条` : ''
        const sampleText = Array.isArray(detail.sample_entry_ids) && detail.sample_entry_ids.length > 0
          ? `，样例 entry_ids=${detail.sample_entry_ids.slice(0, 20).join(', ')}`
          : ''
        return `${detail.message}${countText}${sampleText}`
      }
    }
    if (data && typeof data === 'object' && 'error' in data) {
      const gatewayError = (data as { error?: { message?: string; request_id?: string; details?: unknown } }).error
      if (gatewayError?.details && typeof gatewayError.details === 'object') {
        const details = gatewayError.details as { message?: unknown; unreviewed_count?: unknown; sample_entry_ids?: unknown }
        if (typeof details.message === 'string') {
          const countText = typeof details.unreviewed_count === 'number' ? `，未复核 ${details.unreviewed_count} 条` : ''
          const sampleText = Array.isArray(details.sample_entry_ids) && details.sample_entry_ids.length > 0
            ? `，样例 entry_ids=${details.sample_entry_ids.slice(0, 20).join(', ')}`
            : ''
          return `${details.message}${countText}${sampleText}`
        }
      }
      if (gatewayError?.message) {
        return gatewayError.request_id
          ? `${gatewayError.message}（请求编号：${gatewayError.request_id}）`
          : gatewayError.message
      }
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
    'Cache-Control': 'no-cache, no-store, must-revalidate',
    'Pragma': 'no-cache',
    ...(options?.headers as Record<string, string> || {}),
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  const body = options?.body
  const isFormData = body instanceof FormData
  if (
    body
    && typeof body === 'string'
    && !headers['Content-Type']
    && !isFormData
  ) {
    headers['Content-Type'] = 'application/json'
  }
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new Error('请求已取消')
    }
    const detail = error instanceof Error ? error.message : String(error)
    if (/failed to fetch|networkerror|load failed/i.test(detail)) {
      throw new Error('无法连接后端服务，请确认 API 地址正确且服务已启动')
    }
    throw new Error(`网络请求失败：${detail}`)
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
    if (/^请求失败（(500|502|503|504)）$/.test(errorMessage)) {
      throw new Error('无法连接后端服务，请先启动后端（http://127.0.0.1:8000）')
    }
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
    request<{ code?: string; sms_code?: string; verify_code?: string; message?: string }>('/api/auth/sms/code', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phone })
    }),
  getMe: () =>
    request<{ id: number; username: string | null; phone: string | null; email: string | null; is_active: boolean }>('/api/auth/me'),
  updateMe: (payload: { username?: string; phone?: string; email?: string }) =>
    request<{ id: number; username: string | null; phone: string | null; email: string | null; is_active: boolean }>('/api/auth/me', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }),
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
  getSuperAdminOverview: () => request<SuperAdminOverview>('/api/super-admin/overview'),
  listSuperAdminBindingRequests: (status?: 'pending' | 'approved' | 'rejected' | 'all') =>
    request<BindingRequest[]>(`/api/super-admin/binding-requests${status ? `?status=${status}` : ''}`),
  agentChat: (message: string) =>
    request<AgentChatResponse>('/api/agent/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message })
    }),
  agentAssist: (
    message: string,
    options?: {
      conversationHistory?: Array<{ role: string; content: string }>
      autoExecuteTools?: boolean
      ledgerId?: number | null
      sessionId?: string
      roundIndex?: number
    },
  ) => {
    const normalizedLedgerId = typeof options?.ledgerId === 'number' && Number.isInteger(options.ledgerId) && options.ledgerId > 0
      ? options.ledgerId
      : undefined
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (normalizedLedgerId) {
      headers['X-Ledger-Id'] = String(normalizedLedgerId)
    }
    return request<AgentAssistResponse>('/api/agent/assist', {
      method: 'POST',
      headers,
      body: JSON.stringify({
        message,
        conversation_history: options?.conversationHistory,
        auto_execute_tools: options?.autoExecuteTools ?? true,
        session_id: options?.sessionId,
        round_index: options?.roundIndex ?? 1,
      }),
    })
  },
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
  getImportJobCleanupSummary: (ledgerId?: number) => {
    const params = new URLSearchParams()
    if (ledgerId) params.set('ledger_id', String(ledgerId))
    const query = params.toString()
    return request<ImportJobCleanupSummary>(
      `/api/import-jobs/cleanup-summary${query ? `?${query}` : ''}`,
    )
  },
  cleanupImportJobs: (payload: {
    ledger_id?: number
    job_ids?: number[]
    statuses?: string[]
    keep_job_ids?: number[]
    stuck_only?: boolean
    delete_files?: boolean
  }) =>
    request<ImportJobCleanupResult>('/api/import-jobs/cleanup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  getImportJob: (jobId: number) => request<ImportJob>(`/api/import-jobs/${jobId}`),
  uploadFile: (jobId: number, file: File, documentTypeHints?: string[]) => {
    const form = new FormData()
    form.append('file', file)
    if (documentTypeHints && documentTypeHints.length > 0) {
      form.append('document_type_hints', documentTypeHints.join(','))
    }
    return request<SourceFileRead>(`/api/import-jobs/${jobId}/files`, { method: 'POST', body: form })
  },
  detectImportFormat: (
    file: File,
    parseOptions?: { charset?: string; delimiter?: string },
  ) => {
    const form = new FormData()
    form.append('file', file)
    if (parseOptions?.charset) form.append('charset', parseOptions.charset)
    if (parseOptions?.delimiter) form.append('delimiter', parseOptions.delimiter)
    return request<{
      filename?: string
      file_name?: string
      file_extension: string
      is_structured_tabular: boolean
      charset: string | null
      charset_confidence?: number | null
      delimiter?: string | null
      delimiter_label?: string | null
      header_row_index?: number | null
      detected_headers: string[]
      estimated_data_rows: number
      parseable: boolean
      hints: string[]
      company_name?: string | null
      report_period?: string | null
      parse_options?: { charset: string; delimiter: string }
    }>('/api/import-jobs/detect-format', { method: 'POST', body: form })
  },
  updateImportJobParseOptions: (jobId: number, parseOptions: { charset: string; delimiter: string }) =>
    request<ImportJob>(`/api/import-jobs/${jobId}/parse-options`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(parseOptions),
    }),
  parseSourceFileWithEngine: (jobId: number, fileId: number) =>
    request<SourceFileRead>(`/api/import-jobs/${jobId}/files/${fileId}/parse`, { method: 'POST' }),
  parseUploadedFile: (jobId: number, fileId: number) =>
    api.parseSourceFileWithEngine(jobId, fileId),
  listImportFiles: (jobId: number) => request<SourceFileRead[]>(`/api/import-jobs/${jobId}/files`),
  processImportJob: (jobId: number) => request<ImportJob>(`/api/import-jobs/${jobId}/process`, { method: 'POST' }),
  processImportJobSync: (jobId: number) =>
    request<{ job: ImportJob; report: Record<string, unknown> }>(
      `/api/import-jobs/${jobId}/process/sync`,
      { method: 'POST' }
    ),
  listPreviewEntries: (jobId: number, limit = 100, offset = 0) =>
    request<{
      items: Array<{
        id: number
        voucher_no: string | null
        voucher_date: string | null
        summary: string | null
        account_code: string | null
        account_name: string | null
        debit_amount: number
        credit_amount: number
        counterparty: string | null
        entry_line_no: number
        review_status: string
        compliance_hint: string | null
        compliance_severity: string
        spot_check_flag: boolean
      }>
      total: number
      limit: number
      offset: number
      review_stats?: {
        total_vouchers: number
        verified_vouchers: number
        partial_vouchers: number
        unbalanced_voucher_nos: string[]
        total_lines: number
        spot_check_vouchers?: number
        compliance_pending_vouchers?: number
        compliance_reviewed_vouchers?: number
      }
    }>(`/api/import-jobs/${jobId}/preview-entries?limit=${limit}&offset=${offset}`),
  listPreviewVouchers: (
    jobId: number,
    options?: {
      reviewFilter?: 'all' | 'pending' | 'verified' | 'unbalanced' | 'spot_check' | 'compliance_pending' | 'compliance_reviewed'
      search?: string
      limit?: number
      offset?: number
    },
  ) => {
    const params = new URLSearchParams()
    if (options?.reviewFilter) params.set('review_filter', options.reviewFilter)
    if (options?.search) params.set('search', options.search)
    if (options?.limit) params.set('limit', String(options.limit))
    if (options?.offset) params.set('offset', String(options.offset))
    const query = params.toString()
    return request<{
      items: Array<{
        group_key: string
        voucher_no: string | null
        voucher_date: string | null
        voucher_word: string | null
        line_count: number
        debit_total: number
        credit_total: number
        is_balanced: boolean
        review_status: string
        compliance_hint: string | null
        compliance_severity: string
        spot_check_flag?: boolean
        summary_preview: string | null
        anchor_entry_id: number
        source_preparer_name?: string | null
        cross_reviewed_by_user_id?: number | null
        cross_reviewed_by_name?: string | null
        cross_reviewed_at?: string | null
      }>
      total: number
      limit: number
      offset: number
      review_stats?: {
        total_vouchers: number
        verified_vouchers: number
        partial_vouchers: number
        unbalanced_voucher_nos: string[]
        total_lines: number
        spot_check_vouchers?: number
        compliance_pending_vouchers?: number
        compliance_reviewed_vouchers?: number
      }
    }>(`/api/import-jobs/${jobId}/preview-vouchers${query ? `?${query}` : ''}`)
  },
  getPreviewVoucherReviewStats: (jobId: number) =>
    request<{
      total_vouchers: number
      verified_vouchers: number
      partial_vouchers: number
      unbalanced_voucher_nos: string[]
      total_lines: number
    }>(`/api/import-jobs/${jobId}/preview-voucher-stats`),
  getPreviewVoucherLines: (jobId: number, groupKey: string) =>
    request<{
      group_key: string
      signature?: {
        source_preparer_name?: string | null
        cross_reviewed_by_user_id?: number | null
        cross_reviewed_by_name?: string | null
        cross_reviewed_at?: string | null
        approved_by_name?: string | null
        approved_at?: string | null
      }
      items: Array<{
        id: number
        voucher_no: string | null
        voucher_date: string | null
        summary: string | null
        account_code: string | null
        account_name: string | null
        resolved_account_code?: string | null
        resolved_account_name?: string | null
        entry_tags_payload?: Array<{
          category_code?: string
          tag_value?: string
          display_name?: string
          source_sub_code?: string | null
          name_standardized?: boolean
        }>
        debit_amount: number
        credit_amount: number
        counterparty: string | null
        entry_line_no: number
        review_status: string
        compliance_hint: string | null
        compliance_severity: string
        spot_check_flag: boolean
      }>
    }>(`/api/import-jobs/${jobId}/preview-vouchers/${encodeURIComponent(groupKey)}/lines`),
  updatePreviewEntry: (
    jobId: number,
    stagingId: number,
    patch: Partial<{
      summary: string
      account_code: string
      account_name: string
      debit_amount: number
      credit_amount: number
      counterparty: string
      review_status: string
      tag_updates: Array<{ tag_index: number; display_name: string; name_standardized?: boolean }>
      sync_to_master?: boolean
    }>,
  ) =>
    request<{
      id: number
      updated: boolean
      entry?: Record<string, unknown>
      master_sync?: MasterSyncResult[]
    }>(
      `/api/import-jobs/${jobId}/preview-entries/${stagingId}`,
      {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(patch),
      },
    ),
  updateDimensionDisplayName: (
    jobId: number,
    payload: {
      account_code: string
      category_code: string
      tag_value: string
      display_name: string
      source_sub_code?: string | null
      name_standardized?: boolean
      sync_to_master?: boolean
    },
  ) =>
    request<{
      updated_lines: number
      resolved_findings: number
      display_name: string
      master_sync?: MasterSyncResult | null
    }>(
      `/api/import-jobs/${jobId}/dimension-registry/update-display-name`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      },
    ),
  batchReviewPreviewEntries: (jobId: number, entryIds: number[], reviewStatus: string) =>
    request<{ updated_vouchers: number; updated_lines: number }>(
      `/api/import-jobs/${jobId}/preview-entries/review-batch`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ entry_ids: entryIds, review_status: reviewStatus }),
      },
    ),
  reviewAllPreviewEntries: (jobId: number, reviewStatus: string) =>
    request<{ updated_vouchers: number; updated_lines: number }>(
      `/api/import-jobs/${jobId}/preview-entries/review-all`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ review_status: reviewStatus }),
      },
    ),
  confirmImport: (jobId: number) =>
    request<{ job: ImportJob; entries_created: number }>(`/api/import-jobs/${jobId}/confirm`, {
      method: 'POST',
    }),
  cancelImport: (jobId: number) =>
    request<{ job: ImportJob; cancelled: boolean }>(`/api/import-jobs/${jobId}/cancel`, {
      method: 'POST',
    }),
  complianceSpotCheck: (jobId: number, amountThreshold: number) =>
    request<{
      flagged_count: number
      flagged_voucher_nos: string[]
      flagged_group_keys?: string[]
    }>(
      `/api/import-jobs/${jobId}/compliance-spot-check`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ amount_threshold: amountThreshold }),
      },
    ),
  complianceRandomSample: (
    jobId: number,
    options: { sampleRate?: number; sampleCount?: number; seed?: number },
  ) =>
    request<{
      flagged_count: number
      flagged_voucher_nos: string[]
      flagged_group_keys: string[]
      sampled_vouchers: number
    }>(`/api/import-jobs/${jobId}/compliance-random-sample`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sample_rate: options.sampleRate,
        sample_count: options.sampleCount,
        seed: options.seed,
      }),
    }),
  getDimensionRegistry: (jobId: number) =>
    request<DimensionRegistryResponse>(`/api/import-jobs/${jobId}/dimension-registry`),
  getDimensionPendingQueue: (jobId: number) =>
    request<DimensionPendingQueueResponse>(`/api/import-jobs/${jobId}/dimension-pending-queue`),
  complianceReview: (
    jobId: number,
    mode: 'each' | 'spot' | 'random' | 'skip',
    options?: {
      voucherNos?: string[]
      groupKeys?: string[]
      useLlm?: boolean
    },
  ) =>
    request<{
      reviewed_vouchers: number
      skipped: boolean
      scope?: string
      items: Array<{
        group_key?: string
        voucher_no: string | null
        compliance_hint: string | null
        compliance_severity: string
        line_count: number
        engine?: string
        llm_used?: boolean
        llm_error?: string | null
        llm_thinking?: string | null
        compliant?: boolean
        similar_tag_refs?: Array<{
          score: number
          category_code?: string
          tag_value?: string
          display_name?: string
          voucher_no?: string
          summary?: string
        }>
        llm_reasoning?: string | null
        findings?: string[]
        similar_case_notes?: string | null
      }>
    }>(`/api/import-jobs/${jobId}/preview-entries/compliance-review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        mode,
        voucher_nos: options?.voucherNos,
        group_keys: options?.groupKeys,
        use_llm: options?.useLlm ?? true,
      }),
    }),
  complianceReviewStream: async (
    jobId: number,
    mode: 'each' | 'spot' | 'random' | 'skip',
    options: {
      voucherNos?: string[]
      groupKeys?: string[]
      useLlm?: boolean
      onEvent: (event: ComplianceStreamEvent) => void
      signal?: AbortSignal
    },
  ): Promise<{
    reviewed_vouchers: number
    skipped: boolean
    scope?: string
    items: Array<{
      group_key?: string
      voucher_no: string | null
      compliance_hint: string | null
      compliance_severity: string
      line_count: number
      engine?: string
      llm_used?: boolean
      llm_error?: string | null
      llm_thinking?: string | null
      compliant?: boolean
      similar_tag_refs?: Array<{
        score: number
        category_code?: string
        tag_value?: string
        display_name?: string
        voucher_no?: string
        summary?: string
      }>
      llm_reasoning?: string | null
      findings?: string[]
      similar_case_notes?: string | null
    }>
  }> => {
    const token = localStorage.getItem('token')
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
      'Cache-Control': 'no-cache',
    }
    if (token) {
      headers.Authorization = `Bearer ${token}`
    }
    const response = await fetch(`${API_BASE}/api/import-jobs/${jobId}/preview-entries/compliance-review/stream`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        mode,
        voucher_nos: options.voucherNos,
        group_keys: options.groupKeys,
        use_llm: options.useLlm ?? true,
      }),
      signal: options.signal,
    })
    if (response.status === 404 || response.status === 405) {
      options.onEvent({
        type: 'status',
        message: '流式接口不可用，已切换为普通合规审查（请重启后端以启用实时输出）…',
      })
      const fallback = await request<{
        reviewed_vouchers: number
        skipped: boolean
        scope?: string
        items: Array<{
          group_key?: string
          voucher_no: string | null
          compliance_hint: string | null
          compliance_severity: string
          line_count: number
          engine?: string
          llm_used?: boolean
          llm_error?: string | null
          llm_thinking?: string | null
          compliant?: boolean
          similar_tag_refs?: Array<Record<string, unknown>>
          llm_reasoning?: string | null
          findings?: string[]
          similar_case_notes?: string | null
        }>
      }>(`/api/import-jobs/${jobId}/preview-entries/compliance-review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mode,
          voucher_nos: options.voucherNos,
          group_keys: options.groupKeys,
          use_llm: options.useLlm ?? true,
        }),
      })
      options.onEvent({
        type: 'done',
        reviewed_vouchers: fallback.reviewed_vouchers,
        skipped: fallback.skipped ?? false,
        scope: fallback.scope,
        items: fallback.items as Array<Record<string, unknown>>,
      })
      return fallback
    }
    if (!response.ok) {
      const errorMessage = await getApiErrorMessage(response)
      throw new Error(errorMessage)
    }
    if (!response.body) {
      throw new Error('流式响应不可用')
    }
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let finalResult: {
      reviewed_vouchers: number
      skipped: boolean
      scope?: string
      items: Array<Record<string, unknown>>
    } | null = null

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const chunks = buffer.split('\n\n')
      buffer = chunks.pop() || ''
      for (const chunk of chunks) {
        const line = chunk
          .split('\n')
          .map((part) => part.trim())
          .find((part) => part.startsWith('data:'))
        if (!line) continue
        const payload = JSON.parse(line.slice(5).trim()) as ComplianceStreamEvent
        options.onEvent(payload)
        if (payload.type === 'done') {
          finalResult = {
            reviewed_vouchers: payload.reviewed_vouchers,
            skipped: payload.skipped,
            scope: payload.scope,
            items: payload.items,
          }
        }
        if (payload.type === 'error') {
          throw new Error(payload.message || '合规审查失败')
        }
      }
    }
    if (!finalResult) {
      throw new Error('合规审查未返回最终结果')
    }
    return finalResult as {
      reviewed_vouchers: number
      skipped: boolean
      scope?: string
      items: Array<{
        group_key?: string
        voucher_no: string | null
        compliance_hint: string | null
        compliance_severity: string
        line_count: number
        engine?: string
        llm_used?: boolean
        llm_error?: string | null
        llm_thinking?: string | null
        compliant?: boolean
        similar_tag_refs?: Array<{
          score: number
          category_code?: string
          tag_value?: string
          display_name?: string
          voucher_no?: string
          summary?: string
        }>
        llm_reasoning?: string | null
        findings?: string[]
        similar_case_notes?: string | null
      }>
    }
  },
  reviewVoucher: (voucherId: number) =>
    request<{ voucher_id: number; status: string; reviewed: boolean }>(
      `/api/entries/vouchers/${voucherId}/review`,
      { method: 'POST' },
    ),
  reviewVouchersBatch: (voucherIds: number[]) =>
    request<{ reviewed_count: number }>(`/api/entries/vouchers/review-batch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ voucher_ids: voucherIds }),
    }),
  unreviewVoucher: (voucherId: number) =>
    request<{ voucher_id: number; status: string; reviewed: boolean }>(
      `/api/entries/vouchers/${voucherId}/unreview`,
      { method: 'POST' },
    ),
  getImportJobDraft: (jobId: number) =>
    request<{
      job_id: number
      status: string
      error_message: string | null
      draft_data: Record<string, unknown> | null
      source_type: string
      entry_count: number
      file_count: number
      created_at: string | null
    }>(`/api/import-jobs/${jobId}/draft`),
  retryImportJob: (jobId: number) =>
    request<{ job_id: number; status: string; message: string }>(
      `/api/import-jobs/${jobId}/retry`,
      { method: 'POST' }
    ),
  getImportReport: (jobId: number) => request<any>(`/api/import-jobs/${jobId}/report`),
  getDayBookReport: (jobId: number) => request<DayBookReport>(`/api/import-jobs/${jobId}/day-book-report`),
  getImportPeriodSuggestion: (jobId: number) => request<ImportPeriodSuggestion>(`/api/import-jobs/${jobId}/period-suggestion`),
  applyImportPeriodMapping: (jobId: number, payload: ApplyImportPeriodMappingPayload) =>
    request<ApplyImportPeriodMappingResult>(`/api/import-jobs/${jobId}/apply-period-mapping`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  listEntries: (jobId?: number, ledgerId?: number, reviewStatus?: string, dateFrom?: string, dateTo?: string, limit = 100, offset = 0) => {
    const params = new URLSearchParams()
    if (jobId) params.set('import_job_id', String(jobId))
    if (!jobId && ledgerId) params.set('ledger_id', String(ledgerId))
    if (reviewStatus) params.set('review_status', reviewStatus)
    if (dateFrom) params.set('date_from', dateFrom)
    if (dateTo) params.set('date_to', dateTo)
    params.set('limit', String(clampEntriesPageLimit(limit)))
    params.set('offset', String(offset))
    const query = params.toString()
    return request<EntryListResponse>(`/api/entries${query ? `?${query}` : ''}`)
  },
  listChronologicalEntries: (filters: ChronologicalEntryFilters) => {
    const params = new URLSearchParams()
    params.set('ledger_id', String(filters.ledger_id))
    if (filters.period_ids?.length) params.set('period_ids', JSON.stringify(filters.period_ids))
    else if (filters.period_id != null) params.set('period_id', String(filters.period_id))
    if (filters.date_from) params.set('date_from', filters.date_from)
    if (filters.date_to) params.set('date_to', filters.date_to)
    if (filters.account_code) params.set('account_code', filters.account_code)
    if (filters.account_codes?.length) params.set('account_codes', JSON.stringify(filters.account_codes))
    if (filters.account_code_match) params.set('account_code_match', filters.account_code_match)
    if (filters.account_name) params.set('account_name', filters.account_name)
    if (filters.summary) params.set('summary', filters.summary)
    if (filters.voucher_word) params.set('voucher_word', filters.voucher_word)
    if (filters.voucher_no) params.set('voucher_no', filters.voucher_no)
    if (filters.amount_min != null) params.set('amount_min', String(filters.amount_min))
    if (filters.amount_max != null) params.set('amount_max', String(filters.amount_max))
    if (filters.tag_category_code) params.set('tag_category_code', filters.tag_category_code)
    if (filters.tag_value) params.set('tag_value', filters.tag_value)
    if (filters.tag_filters) params.set('tag_filters', filters.tag_filters)
    if (filters.counterparty) params.set('counterparty', filters.counterparty)
    if (filters.tag_match_scope) params.set('tag_match_scope', filters.tag_match_scope)
    if (filters.limit != null) params.set('limit', String(clampEntriesPageLimit(filters.limit)))
    if (filters.offset != null) params.set('offset', String(filters.offset))
    return request<ChronologicalEntryListResponse>(`/api/entries/chronological?${params.toString()}`)
  },
  listLedgerAccountCodes: (ledgerId: number, limit = 500) =>
    request<Array<{ account_code: string; account_name: string | null; entry_count: number }>>(
      `/api/entries/ledger-account-codes?ledger_id=${ledgerId}&limit=${limit}`,
    ),
  getSubsidiaryOpeningBalance: (filters: {
    ledger_id: number
    account_code?: string
    account_codes?: string[]
    account_code_match?: 'exact' | 'prefix' | 'contains'
    organization_id?: number
    period_id?: number
    period_ids?: number[]
    date_from?: string
    summary?: string
    counterparty?: string
    tag_filters?: string
  }) => {
    const params = new URLSearchParams()
    params.set('ledger_id', String(filters.ledger_id))
    if (filters.account_codes?.length) {
      params.set('account_codes', JSON.stringify(filters.account_codes))
    } else if (filters.account_code) {
      params.set('account_code', filters.account_code)
    }
    if (filters.account_code_match) params.set('account_code_match', filters.account_code_match)
    if (filters.organization_id != null) params.set('organization_id', String(filters.organization_id))
    if (filters.period_ids?.length) params.set('period_ids', JSON.stringify(filters.period_ids))
    else if (filters.period_id != null) params.set('period_id', String(filters.period_id))
    if (filters.date_from) params.set('date_from', filters.date_from)
    if (filters.summary) params.set('summary', filters.summary)
    if (filters.counterparty) params.set('counterparty', filters.counterparty)
    if (filters.tag_filters) params.set('tag_filters', filters.tag_filters)
    return request<{ account_code: string; direction: 'debit' | 'credit'; opening_balance: number }>(
      `/api/entries/subsidiary-ledger/opening-balance?${params.toString()}`,
    )
  },
  exportSubsidiaryLedger: async (filters: {
    ledger_id: number
    account_code?: string
    account_codes?: string[]
    account_code_match?: 'exact' | 'prefix' | 'contains'
    organization_id?: number
    period_id?: number
    period_ids?: number[]
    date_from?: string
    date_to?: string
    summary?: string
    counterparty?: string
    tag_filters?: string
    category_codes?: string
  }): Promise<Blob> => {
    const params = new URLSearchParams()
    params.set('ledger_id', String(filters.ledger_id))
    if (filters.account_codes?.length) {
      params.set('account_codes', JSON.stringify(filters.account_codes))
    } else if (filters.account_code) {
      params.set('account_code', filters.account_code)
    }
    if (filters.account_code_match) params.set('account_code_match', filters.account_code_match)
    if (filters.organization_id != null) params.set('organization_id', String(filters.organization_id))
    if (filters.period_ids?.length) params.set('period_ids', JSON.stringify(filters.period_ids))
    else if (filters.period_id != null) params.set('period_id', String(filters.period_id))
    if (filters.date_from) params.set('date_from', filters.date_from)
    if (filters.date_to) params.set('date_to', filters.date_to)
    if (filters.summary) params.set('summary', filters.summary)
    if (filters.counterparty) params.set('counterparty', filters.counterparty)
    if (filters.tag_filters) params.set('tag_filters', filters.tag_filters)
    if (filters.category_codes) params.set('category_codes', filters.category_codes)
    const response = await fetch(`${API_BASE}/api/entries/subsidiary-ledger/export?${params.toString()}`)
    if (!response.ok) {
      throw new Error(await response.text())
    }
    return response.blob()
  },
  queryVouchers: (filters: VoucherQueryFilters) => {
    const params = new URLSearchParams()
    params.set('ledger_id', String(filters.ledger_id))
    if (filters.period_ids?.length) params.set('period_ids', JSON.stringify(filters.period_ids))
    else if (filters.period_id != null) params.set('period_id', String(filters.period_id))
    if (filters.date_from) params.set('date_from', filters.date_from)
    if (filters.date_to) params.set('date_to', filters.date_to)
    if (filters.month) params.set('month', filters.month)
    if (filters.import_job_id != null) params.set('import_job_id', String(filters.import_job_id))
    if (filters.review_status) params.set('review_status', filters.review_status)
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
    if (filters.include_lines != null) params.set('include_lines', String(filters.include_lines))
    if (filters.limit != null) params.set('limit', String(clampVoucherQueryLimit(filters.limit)))
    if (filters.offset != null) params.set('offset', String(filters.offset))
    return request<VoucherQueryResponse>(`/api/entries/vouchers?${params.toString()}`)
  },
  getVoucherLines: (ledgerId: number, voucherNo: string | null, voucherDate: string | null) => {
    const params = new URLSearchParams()
    params.set('ledger_id', String(ledgerId))
    if (voucherNo) params.set('voucher_no', voucherNo)
    if (voucherDate) params.set('voucher_date', voucherDate)
    return request<VoucherLinesResponse>(`/api/entries/vouchers/lines?${params.toString()}`)
  },
  deleteVouchersBatch: (ledgerId: number, vouchers: VoucherDeleteKey[]) =>
    request<VoucherBatchDeleteResponse>('/api/entries/vouchers/batch-delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ledger_id: ledgerId, vouchers }),
    }),

  createVoucher: (payload: VoucherCreatePayload) =>
    request<VoucherResponse>('/api/vouchers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  getVoucher: (voucherId: number) =>
    request<VoucherResponse>(`/api/vouchers/${voucherId}`),

  updateVoucher: (voucherId: number, payload: VoucherUpdatePayload) =>
    request<VoucherResponse>(`/api/vouchers/${voucherId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  deleteVoucher: (voucherId: number) =>
    request<VoucherResponse>(`/api/vouchers/${voucherId}`, {
      method: 'DELETE',
    }),

  verifyVoucher: (voucherId: number) =>
    request<VoucherResponse>(`/api/vouchers/${voucherId}/verify`, {
      method: 'POST',
    }),

  postVoucher: (voucherId: number) =>
    request<VoucherResponse>(`/api/vouchers/${voucherId}/post`, {
      method: 'POST',
    }),
  updateEntry: (entryId: number, payload: AccountingEntryUpdate) =>
    request<AccountingEntry>(`/api/entries/${entryId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
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
  reviewAllJobEntries: (jobId: number, reviewStatus: string) =>
    request<{ updated: number }>(`/api/entries/jobs/${jobId}/review-all`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ review_status: reviewStatus }),
    }),
  getEntryReviewStats: (jobId?: number, ledgerId?: number) => {
    const params = new URLSearchParams()
    if (jobId) params.set('import_job_id', String(jobId))
    if (!jobId && ledgerId) params.set('ledger_id', String(ledgerId))
    const query = params.toString()
    return request<EntryReviewStats>(`/api/entries/review-stats${query ? `?${query}` : ''}`)
  },
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
  searchAuditFindings: (params?: {
    ledgerId?: number
    jobId?: number
    findingType?: string
    status?: string
  }) => {
    const qs = new URLSearchParams()
    if (params?.ledgerId != null) qs.set('ledger_id', String(params.ledgerId))
    if (params?.jobId != null) qs.set('job_id', String(params.jobId))
    if (params?.findingType) qs.set('finding_type', params.findingType)
    if (params?.status) qs.set('status', params.status)
    const query = qs.toString()
    return request<AuditFinding[]>(`/api/audit-tests/findings/search${query ? `?${query}` : ''}`)
  },
  listWorkbenchItems: (params?: {
    ledgerId?: number
    status?: string
    source?: string
    jobId?: number
    limit?: number
  }) => {
    const query = new URLSearchParams()
    if (params?.status) query.set('status', params.status)
    if (params?.source) query.set('source', params.source)
    if (params?.jobId) query.set('job_id', String(params.jobId))
    if (params?.limit) query.set('limit', String(params.limit))
    const headers = params?.ledgerId ? { 'X-Ledger-Id': String(params.ledgerId) } : undefined
    const suffix = query.toString()
    return request<WorkbenchQueueResponse>(`/api/workbench/items${suffix ? `?${suffix}` : ''}`, { headers })
  },
  getEntrySourceEvidence: (entryId: number) =>
    request<EntrySourceEvidence>(`/api/entries/${entryId}/source-evidence`),
  reviewAuditFinding: (findingDbId: number, action: string, comment?: string) =>
    request<AuditFinding>(`/api/audit-tests/findings/${findingDbId}/review`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, comment })
    }),
  exportImportJob: async (
    jobId: number,
    format: 'xlsx' | 'csv' | 'json',
  ): Promise<{ blob: Blob; contentDisposition: string | null }> => {
    const response = await fetch(`${API_BASE}/api/import-jobs/${jobId}/export?format=${format}`)
    if (!response.ok) {
      throw new Error(await response.text())
    }
    return {
      blob: await response.blob(),
      contentDisposition: response.headers.get('Content-Disposition'),
    }
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
    ledger_ids?: number[]
    project_id?: number | null
    counterparty_id?: number | null
    object_name?: string
    file_type?: string
    parse_status?: string
    archive_category?: string
    lifecycle?: 'inbox' | 'archived' | 'all'
  }) => {
    const params = new URLSearchParams()
    if (filters?.ledger_id) params.set('ledger_id', String(filters.ledger_id))
    if (filters?.ledger_ids?.length) params.set('ledger_ids', filters.ledger_ids.join(','))
    if (filters?.project_id) params.set('project_id', String(filters.project_id))
    if (filters?.counterparty_id) params.set('counterparty_id', String(filters.counterparty_id))
    if (filters?.object_name) params.set('object_name', filters.object_name)
    if (filters?.file_type) params.set('file_type', filters.file_type)
    if (filters?.parse_status) params.set('parse_status', filters.parse_status)
    if (filters?.archive_category) params.set('archive_category', filters.archive_category)
    if (filters?.lifecycle) params.set('lifecycle', filters.lifecycle)
    const query = params.toString()
    return request<SourceFileRead[]>(`/api/files${query ? `?${query}` : ''}`)
  },
  ingestEvidenceFile: (ledgerId: number, file: File, fileType?: string) => {
    const form = new FormData()
    form.append('ledger_id', String(ledgerId))
    form.append('file', file)
    if (fileType) form.append('file_type', fileType)
    return request<SourceFileRead>('/api/files/ingest', {
      method: 'POST',
      headers: { 'X-Ingest-Channel': 'web' },
      body: form,
    })
  },
  getIngestApiExample: (ledgerId: number) =>
    request<IngestApiExample>(`/api/files/ingest/example?ledger_id=${ledgerId}`),
  archiveEvidenceFile: (
    fileId: number,
    payload: { project_id: number; period_code: string; archive_category: string; document_folder?: string },
  ) =>
    request<SourceFileRead>(`/api/files/${fileId}/archive`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
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
  updateModuleRegisterRow: (moduleKey: string, rowId: number, fields: Record<string, unknown>) =>
    request<{ status: string; message: string; row_id: number }>(`/api/module-registers/${moduleKey}/${rowId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fields }),
    }),
  correctModuleRegisterRow: (moduleKey: string, rowId: number, fields: Record<string, unknown>, correctionReason: string) =>
    request<{ status: string; message: string; row_id: number }>(`/api/module-registers/${moduleKey}/${rowId}/correct`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fields, correction_reason: correctionReason }),
    }),
  archiveModuleRegisterRow: (moduleKey: string, rowId: number, archiveReason?: string) =>
    request<{ status: string; message: string; row_id: number }>(`/api/module-registers/${moduleKey}/${rowId}/archive`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ archive_reason: archiveReason }),
    }),
  deleteModuleRegisterRow: (moduleKey: string, rowId: number) =>
    request<{ status: string; message: string; row_id: number }>(`/api/module-registers/${moduleKey}/${rowId}`, { method: 'DELETE' }),
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
  batchCreateAccountingPeriods: (payload: {
    organization_id?: number
    ledger_id?: number
    start_date: string
    end_date: string
    period_type?: string
  }) =>
    request<{
      created_count: number
      skipped_count: number
      created_periods: AccountingPeriod[]
      skipped_period_codes: string[]
    }>('/api/accounting-periods/batch-create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }),
  generateEntries: (
    jobId: number,
    periodId?: number | null,
    accountingJudgmentPolicy: 'compliant_default' | 'revenue_first' | 'counterparty_first' = 'compliant_default',
    periodStartDate?: string,
    periodEndDate?: string,
  ) =>
    request<EntryDraft[]>(`/api/import-jobs/${jobId}/generate-entries`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...(periodId ? { period_id: periodId } : {}),
        ...(periodStartDate ? { period_start_date: periodStartDate } : {}),
        ...(periodEndDate ? { period_end_date: periodEndDate } : {}),
        accounting_judgment_policy: accountingJudgmentPolicy,
      }),
    }),
  commitEntries: (jobId: number, periodId: number | null | undefined, drafts: EntryDraft[]) =>
    request<{ count: number; entry_ids: number[]; job_id: number }>(`/api/import-jobs/${jobId}/commit-entries`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...(periodId ? { period_id: periodId } : {}), drafts })
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
  getTrialBalanceReport: (params: {
    ledgerId: number
    periodId: number
    asOfDate?: string
    organizationId?: number
  }) => {
    const query = new URLSearchParams({
      ledger_id: String(params.ledgerId),
      period_id: String(params.periodId),
    })
    if (params.asOfDate) query.set('as_of_date', params.asOfDate)
    if (params.organizationId) query.set('organization_id', String(params.organizationId))
    return request<TrialBalanceReport>(`/api/reports/trial-balance?${query}`)
  },
  getBalanceSheetReport: (params: {
    ledgerId: number
    periodId: number
    asOfDate?: string
    organizationId?: number
    presentationMode?: BalanceSheetPresentationMode
  }) => {
    const query = new URLSearchParams({
      ledger_id: String(params.ledgerId),
      period_id: String(params.periodId),
    })
    if (params.asOfDate) query.set('as_of_date', params.asOfDate)
    if (params.organizationId) query.set('organization_id', String(params.organizationId))
    if (params.presentationMode) query.set('presentation_mode', params.presentationMode)
    return request<BalanceSheetReport>(`/api/reports/balance-sheet?${query}`)
  },
  getBalanceSheetBreakdown: (params: {
    ledgerId: number
    periodId: number
    accountPrefix: string
    category?: 'asset' | 'liability' | 'equity'
    asOfDate?: string
    organizationId?: number
    presentationMode?: BalanceSheetPresentationMode
  }) => {
    const query = new URLSearchParams({
      ledger_id: String(params.ledgerId),
      period_id: String(params.periodId),
      account_prefix: params.accountPrefix,
    })
    if (params.category) query.set('category', params.category)
    if (params.asOfDate) query.set('as_of_date', params.asOfDate)
    if (params.organizationId) query.set('organization_id', String(params.organizationId))
    if (params.presentationMode) query.set('presentation_mode', params.presentationMode)
    return request<{
      account_prefix: string
      category: string
      presentation_mode?: BalanceSheetPresentationMode
      rows: TrialBalanceRow[]
      as_of_date?: string
    }>(`/api/reports/balance-sheet/breakdown?${query}`)
  },
  getIncomeStatementReport: (organizationId: number, periodId: number) =>
    request<IncomeStatementReport>(`/api/reports/income-statement?organization_id=${organizationId}&period_id=${periodId}`),

  getCashFlowStatementReport: (params: {
    ledgerId: number
    periodId: number
    asOfDate?: string
    organizationId?: number
  }) => {
    const query = new URLSearchParams({
      ledger_id: String(params.ledgerId),
      period_id: String(params.periodId),
    })
    if (params.asOfDate) query.set('as_of_date', params.asOfDate)
    if (params.organizationId) query.set('organization_id', String(params.organizationId))
    return request<CashFlowStatementReport>(`/api/reports/cash-flow-statement?${query}`)
  },

  exportTrialBalanceReport: async (
    params: { ledgerId: number; periodId: number; asOfDate?: string; organizationId?: number } & ReportExportSignature,
    format: 'xlsx' | 'csv' | 'pdf' = 'xlsx',
  ): Promise<{ blob: Blob; contentDisposition: string | null }> => {
    const query = new URLSearchParams({
      ledger_id: String(params.ledgerId),
      period_id: String(params.periodId),
      format,
    })
    if (params.asOfDate) query.set('as_of_date', params.asOfDate)
    if (params.organizationId) query.set('organization_id', String(params.organizationId))
    if (params.preparer_name) query.set('preparer_name', params.preparer_name)
    if (params.reviewer_name) query.set('reviewer_name', params.reviewer_name)
    if (params.approver_name) query.set('approver_name', params.approver_name)
    const response = await fetch(`${API_BASE}/api/reports/trial-balance/export?${query}`)
    if (!response.ok) throw new Error(await response.text())
    return { blob: await response.blob(), contentDisposition: response.headers.get('Content-Disposition') }
  },

  exportBalanceSheetReport: async (
    params: {
      ledgerId: number
      periodId: number
      asOfDate?: string
      organizationId?: number
      presentationMode?: BalanceSheetPresentationMode
    } & ReportExportSignature,
    format: 'xlsx' | 'csv' | 'pdf' = 'xlsx',
  ): Promise<{ blob: Blob; contentDisposition: string | null }> => {
    const query = new URLSearchParams({
      ledger_id: String(params.ledgerId),
      period_id: String(params.periodId),
      format,
    })
    if (params.asOfDate) query.set('as_of_date', params.asOfDate)
    if (params.organizationId) query.set('organization_id', String(params.organizationId))
    if (params.presentationMode) query.set('presentation_mode', params.presentationMode)
    if (params.preparer_name) query.set('preparer_name', params.preparer_name)
    if (params.reviewer_name) query.set('reviewer_name', params.reviewer_name)
    if (params.approver_name) query.set('approver_name', params.approver_name)
    const response = await fetch(`${API_BASE}/api/reports/balance-sheet/export?${query}`)
    if (!response.ok) throw new Error(await response.text())
    return { blob: await response.blob(), contentDisposition: response.headers.get('Content-Disposition') }
  },

  exportIncomeStatementReport: async (
    params: { organizationId: number; periodId: number; ledgerId?: number } & ReportExportSignature,
    format: 'xlsx' | 'csv' | 'pdf' = 'xlsx',
  ): Promise<{ blob: Blob; contentDisposition: string | null }> => {
    const query = new URLSearchParams({
      organization_id: String(params.organizationId),
      period_id: String(params.periodId),
      format,
    })
    if (params.ledgerId) query.set('ledger_id', String(params.ledgerId))
    if (params.preparer_name) query.set('preparer_name', params.preparer_name)
    if (params.reviewer_name) query.set('reviewer_name', params.reviewer_name)
    if (params.approver_name) query.set('approver_name', params.approver_name)
    const response = await fetch(`${API_BASE}/api/reports/income-statement/export?${query}`)
    if (!response.ok) throw new Error(await response.text())
    return { blob: await response.blob(), contentDisposition: response.headers.get('Content-Disposition') }
  },

  exportCashFlowStatementReport: async (
    params: { ledgerId: number; periodId: number; asOfDate?: string; organizationId?: number } & ReportExportSignature,
    format: 'xlsx' | 'csv' | 'pdf' = 'xlsx',
  ): Promise<{ blob: Blob; contentDisposition: string | null }> => {
    const query = new URLSearchParams({
      ledger_id: String(params.ledgerId),
      period_id: String(params.periodId),
      format,
    })
    if (params.asOfDate) query.set('as_of_date', params.asOfDate)
    if (params.organizationId) query.set('organization_id', String(params.organizationId))
    if (params.preparer_name) query.set('preparer_name', params.preparer_name)
    if (params.reviewer_name) query.set('reviewer_name', params.reviewer_name)
    if (params.approver_name) query.set('approver_name', params.approver_name)
    const response = await fetch(`${API_BASE}/api/reports/cash-flow-statement/export?${query}`)
    if (!response.ok) throw new Error(await response.text())
    return { blob: await response.blob(), contentDisposition: response.headers.get('Content-Disposition') }
  },

  exportReportsPackage: async (
    params: {
      ledgerId: number
      periodId: number
      asOfDate?: string
      organizationId?: number
      includePdf?: boolean
    } & ReportExportSignature,
  ): Promise<{ blob: Blob; contentDisposition: string | null }> => {
    const query = new URLSearchParams({
      ledger_id: String(params.ledgerId),
      period_id: String(params.periodId),
      include_pdf: String(params.includePdf !== false),
    })
    if (params.asOfDate) query.set('as_of_date', params.asOfDate)
    if (params.organizationId) query.set('organization_id', String(params.organizationId))
    if (params.preparer_name) query.set('preparer_name', params.preparer_name)
    if (params.reviewer_name) query.set('reviewer_name', params.reviewer_name)
    if (params.approver_name) query.set('approver_name', params.approver_name)
    const response = await fetch(`${API_BASE}/api/reports/package/export?${query}`)
    if (!response.ok) throw new Error(await response.text())
    return { blob: await response.blob(), contentDisposition: response.headers.get('Content-Disposition') }
  },

  deliverReportsPackage: (params: {
    ledgerId: number
    periodId: number
    asOfDate?: string
    organizationId?: number
    includePdf?: boolean
    includeSubsidiary?: boolean
  } & ReportExportSignature) => {
    const query = new URLSearchParams({
      ledger_id: String(params.ledgerId),
      period_id: String(params.periodId),
      include_pdf: String(params.includePdf !== false),
      include_subsidiary: String(params.includeSubsidiary !== false),
    })
    if (params.asOfDate) query.set('as_of_date', params.asOfDate)
    if (params.organizationId) query.set('organization_id', String(params.organizationId))
    if (params.preparer_name) query.set('preparer_name', params.preparer_name)
    if (params.reviewer_name) query.set('reviewer_name', params.reviewer_name)
    if (params.approver_name) query.set('approver_name', params.approver_name)
    return request<{
      delivery_root: string
      delivery_folder: string
      manifest_path: string
      zip_path: string
      files: string[]
      ledger_name: string
      period_code: string
    }>(`/api/reports/package/deliver?${query}`, { method: 'POST' })
  },

  plTransfer: (periodId: number) =>
    request<{ period_id: number; voucher_no: string; lines: number; net_profit: number; status: string }>(
      `/api/accounting-periods/${periodId}/pl-transfer`,
      { method: 'POST' }
    ),
  plTransferBatch: (payload: {
    ledgerId: number
    periodIds?: number[]
    fromPeriodId?: number
    toPeriodId?: number
    stopOnError?: boolean
    skipTransferred?: boolean
  }) =>
    request<PlTransferBatchResult>('/api/accounting-periods/batch/pl-transfer', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ledger_id: payload.ledgerId,
        period_ids: payload.periodIds,
        from_period_id: payload.fromPeriodId,
        to_period_id: payload.toPeriodId,
        stop_on_error: payload.stopOnError !== false,
        skip_transferred: payload.skipTransferred !== false,
      }),
    }),
  plTransferReverse: (periodId: number) =>
    request<{ period_id: number; voucher_no: string; deleted_lines: number; status: string }>(
      `/api/accounting-periods/${periodId}/pl-transfer/reverse`,
      { method: 'POST' }
    ),
  reconcilePlTransfer: (periodId: number, autoFix = false) => {
    const query = autoFix ? '?auto_fix=true' : ''
    return request<PlTransferHealth>(
      `/api/accounting-periods/${periodId}/pl-transfer/reconcile${query}`,
      { method: 'POST' }
    )
  },
  autoProvisionCoaGaps: (ledgerId: number, dryRun = false) => {
    const query = new URLSearchParams({ ledger_id: String(ledgerId) })
    if (dryRun) query.set('dry_run', 'true')
    return request<{
      ledger_id: number
      dry_run: boolean
      orphan_code_count: number
      created_count: number
      created: Array<Record<string, unknown>>
      skipped: Array<{ code: string; reason: string }>
    }>(`/api/coa/auto-provision-gaps?${query}`, { method: 'POST' })
  },
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
    const normalizedLedgerId = typeof ledgerId === 'number' && Number.isInteger(ledgerId) && ledgerId > 0
      ? ledgerId
      : undefined
    const headers = normalizedLedgerId ? { 'X-Ledger-Id': String(normalizedLedgerId) } : undefined
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
  listProjectLedgers: (projectId: number) => request<{ id: number; name: string }[]>(`/api/projects/${projectId}/ledgers`),
  listProjectTaskAssignees: (projectId: number, ledgerId?: number | null) => {
    const params = new URLSearchParams()
    if (ledgerId != null) params.set('ledger_id', String(ledgerId))
    const query = params.toString()
    return request<ProjectTaskAssignee[]>(`/api/projects/${projectId}/task-assignees${query ? `?${query}` : ''}`)
  },
  associateProjectLedger: (projectId: number, ledgerId: number) =>
    request<{ id: number; project_id: number; ledger_id: number }>(`/api/projects/${projectId}/ledgers`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ledger_id: ledgerId }),
    }),
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
  updateProject: (id: number, payload: Partial<Project> & { project_type?: string }) =>
    request<Project>(`/api/projects/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }),
  removeProjectLedger: (projectId: number, ledgerId: number) =>
    request<{ deleted: number; project_id: number; ledger_id: number }>(`/api/projects/${projectId}/ledgers/${ledgerId}`, {
      method: 'DELETE',
    }),
  deleteProject: (id: number) =>
    request<{ deleted: number }>(`/api/projects/${id}`, { method: 'DELETE' }),

  listBankAccounts: (ledgerId: number) =>
    request<BankAccount[]>('/api/bank/accounts', { headers: { 'X-Ledger-Id': String(ledgerId) } }),
  bulkImportBankAccounts: (ledgerId: number, records: Array<Record<string, unknown>>) =>
    request<{ created: number; skipped: number; errors: string[] }>('/api/bank/accounts/bulk-import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Ledger-Id': String(ledgerId) },
      body: JSON.stringify({ records }),
    }),
  createBankAccount: (ledgerId: number, payload: {
    bank_name: string
    account_no: string
    account_name: string
    coa_account_code?: string
    source_sub_code?: string | null
    opening_balance?: number
  }) =>
    request<BankAccount>('/api/bank/accounts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Ledger-Id': String(ledgerId) },
      body: JSON.stringify(payload),
    }),
  updateBankAccount: (
    ledgerId: number,
    accountId: number,
    payload: {
      bank_name: string
      account_no: string
      account_name: string
      coa_account_code?: string
      source_sub_code?: string | null
    },
  ) =>
    request<BankAccount>(`/api/bank/accounts/${accountId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', 'X-Ledger-Id': String(ledgerId) },
      body: JSON.stringify(payload),
    }),
  deleteBankAccount: (ledgerId: number, accountId: number) =>
    request<{ status: string }>(`/api/bank/accounts/${accountId}`, {
      method: 'DELETE',
      headers: { 'X-Ledger-Id': String(ledgerId) },
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
  updateLedger: (ledgerId: number, payload: UpdateLedgerPayload) =>
    request<Ledger>(`/api/ledgers/${ledgerId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  deleteLedger: (ledgerId: number, reason?: string) =>
    request<{ deleted: boolean; ledger_id: number }>(`/api/ledgers/${ledgerId}/delete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason }),
    }),
  initializeLedger: (ledgerId: number, reason?: string) =>
    request<{ ledger_id: number; deleted_vouchers: number; deleted_entries: number }>(
      `/api/ledgers/${ledgerId}/initialize`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason }),
      },
    ),
  switchLedger: (ledgerId: number) =>
    request<{ ledger_id: number; message: string }>(`/api/ledgers/${ledgerId}/switch`, { method: 'POST' }),
  getLedgerAuths: (ledgerId: number) =>
    request<LedgerAuth[]>(`/api/ledgers/${ledgerId}/auths`),
  grantLedgerAuth: (
    ledgerId: number,
    payload: { user_id?: number; username?: string; phone?: string; role: string }
  ) =>
    request<{ message: string; user_id: number; username?: string; ledger_id: number; role: string }>(
      `/api/ledgers/${ledgerId}/auth`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      }
    ),
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

  getScopeSettingsCatalog: () => request<ScopeSettingsCatalog>('/api/scope-settings/catalog'),
  getLedgerSettings: (ledgerId: number) =>
    request<ScopeSettingsResponse<LedgerSettingsData>>(`/api/scope-settings/ledger/${ledgerId}`),
  updateLedgerSettings: (ledgerId: number, payload: Partial<LedgerSettingsData>) =>
    request<ScopeSettingsResponse<LedgerSettingsData>>(`/api/scope-settings/ledger/${ledgerId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  getTeamSettings: (teamId: number) =>
    request<ScopeSettingsResponse<TeamSettingsData>>(`/api/scope-settings/team/${teamId}`),
  updateTeamSettings: (teamId: number, payload: Partial<TeamSettingsData>) =>
    request<ScopeSettingsResponse<TeamSettingsData>>(`/api/scope-settings/team/${teamId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  getProjectSettings: (projectId: number) =>
    request<ScopeSettingsResponse<ProjectSettingsData>>(`/api/scope-settings/project/${projectId}`),
  updateProjectSettings: (projectId: number, payload: Partial<ProjectSettingsData>) =>
    request<ScopeSettingsResponse<ProjectSettingsData>>(`/api/scope-settings/project/${projectId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  getEntityScopeSettings: (ledgerId: number) =>
    request<ScopeSettingsResponse<EntityScopeSettingsData>>(`/api/scope-settings/entity/${ledgerId}`),
  updateEntityScopeSettings: (ledgerId: number, payload: Partial<EntityScopeSettingsData>) =>
    request<ScopeSettingsResponse<EntityScopeSettingsData>>(`/api/scope-settings/entity/${ledgerId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  listAuditTasks: (projectId: number, filters?: {
    status?: string
    assignee_id?: number
    task_type?: string
    priority?: string
    page?: number
    page_size?: number
  }) => {
    const params = new URLSearchParams({ project_id: String(projectId) })
    if (filters?.status) params.set('status', filters.status)
    if (filters?.assignee_id != null) params.set('assignee_id', String(filters.assignee_id))
    if (filters?.task_type) params.set('task_type', filters.task_type)
    if (filters?.priority) params.set('priority', filters.priority)
    if (filters?.page != null) params.set('page', String(filters.page))
    if (filters?.page_size != null) params.set('page_size', String(filters.page_size))
    return request<AuditTaskListResponse>(`/api/audit/tasks?${params.toString()}`)
  },
  getAuditTask: (taskId: number) => request<AuditTask>(`/api/audit/tasks/${taskId}`),
  createAuditTask: (payload: AuditTaskCreate) =>
    request<AuditTask>('/api/audit/tasks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  updateAuditTask: (taskId: number, payload: AuditTaskUpdate) =>
    request<AuditTask>(`/api/audit/tasks/${taskId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  assignAuditTask: (taskId: number, assigneeId: number) =>
    request<AuditTask>(`/api/audit/tasks/${taskId}/assign`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ assignee_id: assigneeId }),
    }),
  updateAuditTaskStatus: (taskId: number, status: string, comment?: string | null) =>
    request<AuditTask>(`/api/audit/tasks/${taskId}/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status, comment: comment || undefined }),
    }),
  deleteAuditTask: (taskId: number) =>
    request<{ deleted: boolean }>(`/api/audit/tasks/${taskId}`, { method: 'DELETE' }),

  listAuditBranches: (filters?: {
    project_id?: number
    task_id?: number
    status?: string
    page?: number
    page_size?: number
  }) => {
    const params = new URLSearchParams()
    if (filters?.project_id != null) params.set('project_id', String(filters.project_id))
    if (filters?.task_id != null) params.set('task_id', String(filters.task_id))
    if (filters?.status) params.set('status', filters.status)
    if (filters?.page != null) params.set('page', String(filters.page))
    if (filters?.page_size != null) params.set('page_size', String(filters.page_size))
    const query = params.toString()
    return request<{ items: AuditWorkBranch[]; total: number; page: number; page_size: number }>(
      `/api/audit/branches${query ? `?${query}` : ''}`
    )
  },
  getAuditBranch: (branchId: number) =>
    request<AuditWorkBranch>(`/api/audit/branches/${branchId}`),
  createAuditBranch: (payload: AuditWorkBranchCreate) =>
    request<AuditWorkBranch>('/api/audit/branches', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  updateAuditBranchStatus: (branchId: number, status: string) =>
    request<AuditWorkBranch>(`/api/audit/branches/${branchId}/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    }),
  getBranchesByTask: (taskId: number) =>
    request<AuditWorkBranch[]>(`/api/audit/branches/task/${taskId}`),
  linkBranchVersion: (branchId: number, versionId: number) =>
    request<AuditWorkBranch>(`/api/audit/branches/${branchId}/link-version`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ version_id: versionId }),
    }),
  linkBranchProcedure: (branchId: number, procedureRunId: number) =>
    request<AuditWorkBranch>(`/api/audit/branches/${branchId}/link-procedure`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ procedure_run_id: procedureRunId }),
    }),

  listAuditReviewRequests: (filters?: {
    project_id?: number
    status?: string
    created_by?: number
    reviewer_id?: number
    page?: number
    page_size?: number
  }) => {
    const params = new URLSearchParams()
    if (filters?.project_id != null) params.set('project_id', String(filters.project_id))
    if (filters?.status) params.set('status', filters.status)
    if (filters?.created_by != null) params.set('created_by', String(filters.created_by))
    if (filters?.reviewer_id != null) params.set('reviewer_id', String(filters.reviewer_id))
    if (filters?.page != null) params.set('page', String(filters.page))
    if (filters?.page_size != null) params.set('page_size', String(filters.page_size))
    const query = params.toString()
    return request<AuditReviewListResponse>(
      `/api/audit/review-requests${query ? `?${query}` : ''}`
    )
  },
  getAuditReviewRequest: (reviewId: number) =>
    request<AuditReviewRequest>(`/api/audit/review-requests/${reviewId}`),
  createAuditReviewRequest: (payload: AuditReviewRequestCreate) =>
    request<AuditReviewRequest>('/api/audit/review-requests', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  submitAuditReview: (reviewId: number, reviewerLevel1Id?: number | null) =>
    request<AuditReviewRequest>(`/api/audit/review-requests/${reviewId}/submit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reviewer_level_1_id: reviewerLevel1Id || undefined }),
    }),
  performAuditReview: (reviewId: number, payload: AuditReviewActionCreate) =>
    request<AuditReviewRequest>(`/api/audit/review-requests/${reviewId}/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  mergeAuditReview: (reviewId: number) =>
    request<AuditReviewRequest>(`/api/audit/review-requests/${reviewId}/merge`, {
      method: 'POST',
    }),
  getAuditReviewActions: (reviewId: number) =>
    request<AuditReviewAction[]>(`/api/audit/review-requests/${reviewId}/actions`),
  getMyPendingReviews: (projectId?: number) => {
    const params = new URLSearchParams()
    if (projectId != null) params.set('project_id', String(projectId))
    const query = params.toString()
    return request<AuditReviewRequest[]>(
      `/api/audit/review-requests/pending/mine${query ? `?${query}` : ''}`
    )
  },
  getMySubmittedReviews: (projectId?: number) => {
    const params = new URLSearchParams()
    if (projectId != null) params.set('project_id', String(projectId))
    const query = params.toString()
    return request<AuditReviewRequest[]>(
      `/api/audit/review-requests/submitted/mine${query ? `?${query}` : ''}`
    )
  },

  listAuditComments: (targetType: string, targetId: number) =>
    request<AuditComment[]>(`/api/audit/comments?target_type=${targetType}&target_id=${targetId}`),
  createAuditComment: (payload: AuditCommentCreate) =>
    request<AuditComment>('/api/audit/comments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  deleteAuditComment: (commentId: number) =>
    request<{ deleted: boolean }>(`/api/audit/comments/${commentId}`, { method: 'DELETE' }),

  listAuditNotifications: (filters?: { unread_only?: boolean; limit?: number }) => {
    const params = new URLSearchParams()
    if (filters?.unread_only != null) params.set('unread_only', String(filters.unread_only))
    if (filters?.limit != null) params.set('limit', String(filters.limit))
    const query = params.toString()
    return request<AuditNotificationListResponse>(
      `/api/audit/notifications${query ? `?${query}` : ''}`
    )
  },
  markAuditNotificationRead: (notificationId: number) =>
    request<AuditNotification>(`/api/audit/notifications/${notificationId}/read`, { method: 'POST' }),
  markAllAuditNotificationsRead: () =>
    request<{ status: string; updated_count: number }>('/api/audit/notifications/read-all', { method: 'POST' }),

  getAuditDashboardStats: (projectId?: number) => {
    const params = new URLSearchParams()
    if (projectId != null) params.set('project_id', String(projectId))
    const query = params.toString()
    return request<AuditDashboardStats>(
      `/api/audit/dashboard/stats${query ? `?${query}` : ''}`
    )
  },
  getMyTodoTasks: (projectId?: number) => {
    const params = new URLSearchParams()
    if (projectId != null) params.set('project_id', String(projectId))
    const query = params.toString()
    return request<AuditTask[]>(`/api/audit/dashboard/todo-tasks${query ? `?${query}` : ''}`)
  },
  getMyPendingReviewList: (projectId?: number) => {
    const params = new URLSearchParams()
    if (projectId != null) params.set('project_id', String(projectId))
    const query = params.toString()
    return request<AuditReviewRequest[]>(
      `/api/audit/dashboard/pending-review${query ? `?${query}` : ''}`
    )
  },
  getMySubmittedList: (projectId?: number) => {
    const params = new URLSearchParams()
    if (projectId != null) params.set('project_id', String(projectId))
    const query = params.toString()
    return request<AuditReviewRequest[]>(
      `/api/audit/dashboard/submitted${query ? `?${query}` : ''}`
    )
  },

  // ==========================================================================
  // 解析引擎 API
  // ==========================================================================
  getParserEngineStatus: () =>
    request<{
      status: string
      llm_multi_engine_enabled: boolean
      llm_enable_parallel_parsing: boolean
      llm_max_concurrent_models: number
      llm_preferred_model: string
      llm_comparison_strategy: string
      llm_knowledge_base: string | null
      supported_formats: string[]
      supported_document_types: string[]
    }>('/api/parser-engine/status'),

  listExcelSheets: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<{
      success: boolean
      sheet_count: number
      sheets: Array<{
        name: string
        rows: number
        columns: string[]
        preview: Record<string, unknown>[]
      }>
    }>('/api/parser-engine/list-excel-sheets', { method: 'POST', body: form })
  },

  parseFile: (organizationId: number, file: File, sheetName?: string, options?: RequestInit) => {
    const form = new FormData()
    form.append('organization_id', String(organizationId))
    form.append('file', file)
    if (sheetName) {
      form.append('sheet_name', sheetName)
    }
    return request<{
      file_format: string
      document_type: string
      document_sub_type: string | null
      confidence: number
      engine_type: string
      data: Record<string, unknown>
      raw_text: string | null
      error_message: string | null
      parse_duration_ms: number
      stage_timings?: Record<string, number> | null
      engine_comparison?: Record<string, unknown>
      multi_llm_comparison?: Record<string, unknown>
    }>('/api/parser-engine/parse-file', { ...options, method: 'POST', body: form })
  },

  parseSourceFile: (fileId: number) =>
    request<{
      file_format: string
      document_type: string
      document_sub_type: string | null
      confidence: number
      engine_type: string
      data: Record<string, unknown>
      raw_text: string | null
      error_message: string | null
      parse_duration_ms: number
    }>(`/api/parser-engine/parse-source-file/${fileId}`, { method: 'POST' }),

  getPerformanceStats: () =>
    request<{
      total_parses: number
      successful_parses: number
      failed_parses: number
      success_rate_percent: number
      stage_stats: Record<string, { count: number; avg_ms: number; max_ms: number; min_ms: number }>
      format_stats: Record<string, { count: number; avg_ms: number; max_ms: number; min_ms: number }>
      doctype_stats: Record<string, { count: number; avg_ms: number; max_ms: number; min_ms: number }>
      error_stats: Record<string, number>
    }>('/api/parser-engine/performance-stats'),

  resetPerformanceStats: () =>
    request<{ status: string; message: string }>(
      '/api/parser-engine/performance-stats/reset',
      { method: 'POST' }
    ),

  // ==========================================================================
  // 配置管理 API
  // ==========================================================================
  getParserEngineConfig: () =>
    request<{
      ai_provider: string
      ai_base_url: string
      ai_model: string
      ai_reasoning_model?: string
      ai_api_key: string | null
      ai_local_model_enabled: boolean
      ai_fallback_to_rules: boolean
      llm_max_concurrent_models: number
      llm_memory_limit_mb: number
      llm_preferred_model: string
      llm_fallback_model: string
      llm_timeout_seconds: number
      llm_enable_parallel_parsing: boolean
      llm_parallel_timeout_seconds: number
      llm_result_selection_mode: string
      llm_confidence_threshold_auto: number
      llm_confidence_threshold_user: number
      llm_multi_engine_enabled: boolean
      llm_comparison_mode: string
      llm_comparison_strategy: string
      llm_comparison_engines: string
      llm_engine_weights: string
      llm_agreement_threshold: number
      llm_save_all_results: boolean
    }>('/api/config/parser-engine'),

  saveParserEngineConfig: (config: Record<string, unknown>) =>
    request<{ success: boolean; message: string; config?: Record<string, unknown> }>(
      '/api/config/parser-engine',
      { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(config) }
    ),

  testAIConnection: (params: { ai_base_url: string; ai_model: string; ai_api_key?: string }) =>
    request<{ 
      success: boolean; 
      message: string; 
      model?: string; 
      base_url?: string;
      response_content?: string;
      response_time_ms?: number;
      usage?: { prompt_tokens: number; completion_tokens: number; total_tokens: number }
    }>(
      '/api/config/parser-engine/test-connection',
      { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(params) }
    ),

  getProviderOptions: () =>
    request<{
      providers: Array<{ value: string; label: string; description: string; default_base_url: string; default_model: string; requires_api_key: boolean; has_model_list: boolean }>
      models: Array<{ value: string; label: string; description: string }>
      comparison_modes: Array<{ value: string; label: string }>
      comparison_strategies: Array<{ value: string; label: string }>
      selection_modes: Array<{ value: string; label: string }>
    }>('/api/config/provider-options'),

  getOllamaModels: (baseUrl: string) =>
    request<{
      success: boolean
      message?: string
      models: Array<{ value: string; label: string; description: string }>
      count: number
    }>(`/api/config/ollama-models?base_url=${encodeURIComponent(baseUrl)}`),

  // ==========================================================================
  // 解析结果直通凭证草稿 API (B1/B2)
  // ==========================================================================
  parseToVoucherDrafts: (organizationId: number, file: File, sheetName?: string) => {
    const form = new FormData()
    form.append('organization_id', String(organizationId))
    form.append('file', file)
    if (sheetName) {
      form.append('sheet_name', sheetName)
    }
    return request<{
      success: boolean
      document_type: string
      confidence: number
      drafts: Array<{
        voucher_no: string
        voucher_date: string
        summary: string
        document_type: string
        source_confidence: number
        lines: Array<{
          account_code: string
          account_name: string
          summary: string
          debit_amount: string
          credit_amount: string
          counterparty: string | null
        }>
        validation_errors: string[]
        raw_extracted_data: Record<string, unknown>
      }>
      error_message: string | null
      seal_info?: {
        detected: boolean
        seal_count: number
        seals: Array<{
          bbox: { x1: number; y1: number; x2: number; y2: number }
          seal_image_path?: string | null
          recognized_text?: string | null
          text_items?: Array<{
            text: string
            x: number
            y: number
            width: number
            height: number
            confidence: number
          }>
          seal_type?: string | null
          confidence: number
          detection_method?: string | null
        }>
      } | null
    }>('/api/parser-voucher/parse-to-drafts', { method: 'POST', body: form })
  },

  confirmVoucherDrafts: (ledgerId: number, organizationId: number, drafts: Array<{
    voucher_no: string
    voucher_date: string
    summary: string
    lines: Array<{
      account_code: string
      account_name: string
      summary: string
      debit_amount: string
      credit_amount: string
      counterparty: string | null
    }>
  }>) =>
    request<{
      success: boolean
      created_count: number
      voucher_ids: number[]
      error_message: string | null
    }>('/api/parser-voucher/confirm-drafts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ledger_id: ledgerId,
        organization_id: organizationId,
        drafts,
      }),
    }),

  // ==========================================================================
  // DocumentTag API
  // ==========================================================================
  listDocumentTags: (filters?: {
    document_id?: number
    document_type?: string
    tag_type?: string
    source?: string
    vector_stored?: boolean
    created_from?: string
    created_to?: string
  }) => {
    const params = new URLSearchParams()
    if (filters?.document_id != null) params.set('document_id', String(filters.document_id))
    if (filters?.document_type) params.set('document_type', filters.document_type)
    if (filters?.tag_type) params.set('tag_type', filters.tag_type)
    if (filters?.source) params.set('source', filters.source)
    if (filters?.vector_stored != null) params.set('vector_stored', String(filters.vector_stored))
    if (filters?.created_from) params.set('created_from', filters.created_from)
    if (filters?.created_to) params.set('created_to', filters.created_to)
    const query = params.toString()
    return request<DocumentTag[]>(`/api/document-tags${query ? `?${query}` : ''}`)
  },
  getDocumentTag: (tagId: number) =>
    request<DocumentTag>(`/api/document-tags/${tagId}`),
  createDocumentTag: (payload: {
    document_id: number
    document_type: string
    tag: string
    tag_type: string
    confidence?: number
    source?: string
  }) =>
    request<DocumentTag>('/api/document-tags', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  createDocumentTagsBatch: (payload: {
    document_id: number
    document_type: string
    tags: Array<{ tag: string; tag_type: string; confidence?: number; source?: string }>
  }) =>
    request<DocumentTag[]>('/api/document-tags/batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  updateDocumentTag: (tagId: number, payload: {
    tag?: string
    tag_type?: string
    confidence?: number
    source?: string
  }) =>
    request<DocumentTag>(`/api/document-tags/${tagId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  deleteDocumentTag: (tagId: number) =>
    request<{ success: boolean }>(`/api/document-tags/${tagId}`, { method: 'DELETE' }),
  deleteDocumentTagsByDocument: (documentId: number) =>
    request<{ success: boolean; deleted_count: number }>(`/api/document-tags/document/${documentId}`, { method: 'DELETE' }),
  generateDocumentTags: (payload: {
    document_id: number
    document_type: string
    parsed_data: Record<string, unknown>
    source?: string
  }) =>
    request<DocumentTag[]>('/api/document-tags/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  generateDocumentTagsAI: (payload: {
    document_id: number
    document_type: string
    extracted_text: string
    parsed_data?: Record<string, unknown>
  }) =>
    request<DocumentTag[]>('/api/document-tags/generate/ai', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  generateDocumentTagsHybrid: (payload: {
    document_id: number
    document_type: string
    extracted_text: string
    parsed_data: Record<string, unknown>
    ai_enabled?: boolean
  }) =>
    request<DocumentTag[]>('/api/document-tags/generate/hybrid', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  getDocumentTagStats: (document_type?: string) => {
    const params = new URLSearchParams()
    if (document_type) params.set('document_type', document_type)
    const query = params.toString()
    return request<{
      total_tags: number
      total_documents: number
      by_tag_type: Array<{ tag_type: string; count: number; avg_confidence: number }>
    }>(`/api/document-tags/stats${query ? `?${query}` : ''}`)
  },
  syncDocumentTagVectors: () =>
    request<{ success: boolean; synced_count: number }>('/api/document-tags/sync-vectors', { method: 'POST' }),
  searchDocumentTags: (params: {
    query_text: string
    document_type?: string
    tag_type?: string
    limit?: number
  }) => {
    const searchParams = new URLSearchParams()
    searchParams.set('query_text', params.query_text)
    if (params.document_type) searchParams.set('document_type', params.document_type)
    if (params.tag_type) searchParams.set('tag_type', params.tag_type)
    if (params.limit != null) searchParams.set('limit', String(params.limit))
    return request<Array<{ score: number; metadata: DocumentTag }>>(`/api/document-tags/search?${searchParams.toString()}`)
  },

  batchUpdateDocumentTags: (payload: {
    tag_ids: number[]
    updates: { tag?: string; tag_type?: string; confidence?: number; source?: string }
    operator?: string
    reason?: string
  }) =>
    request<{ success: boolean; updated_count: number }>('/api/document-tags/batch', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  batchDeleteDocumentTags: (payload: { tag_ids: number[]; operator?: string; reason?: string }) =>
    request<{ success: boolean; deleted_count: number }>('/api/document-tags/batch', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  batchAssignDocumentTags: (payload: {
    document_ids: number[]
    document_type: string
    tags: Array<{ tag: string; tag_type: string; confidence?: number; source?: string }>
  }) =>
    request<{ success: boolean; created_count: number }>('/api/document-tags/batch/assign', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  listDocumentTagHistory: (params?: {
    document_tag_id?: number
    document_id?: number
    action?: string
    limit?: number
  }) => {
    const searchParams = new URLSearchParams()
    if (params?.document_tag_id != null) searchParams.set('document_tag_id', String(params.document_tag_id))
    if (params?.document_id != null) searchParams.set('document_id', String(params.document_id))
    if (params?.action) searchParams.set('action', params.action)
    if (params?.limit != null) searchParams.set('limit', String(params.limit))
    const query = searchParams.toString()
    return request<Array<{
      id: number
      document_tag_id: number
      document_id: number
      document_type: string
      action: string
      before_tag: string | null
      before_tag_type: string | null
      before_confidence: number | null
      before_source: string | null
      after_tag: string | null
      after_tag_type: string | null
      after_confidence: number | null
      after_source: string | null
      operator: string | null
      reason: string | null
      created_at: string
    }>>(`/api/document-tags/history${query ? `?${query}` : ''}`)
  },

  extractContractSeals: (contractId: number) =>
    request<ContractSealExtractResponse>(`/api/v1/contracts/${contractId}/seals/extract`, {
      method: 'POST',
    }),

  listContractSeals: (contractId: number, page: number = 1, size: number = 20) =>
    request<ContractSealListResponse>(
      `/api/v1/contracts/${contractId}/seals?page=${page}&size=${size}`
    ),

  getSealDetail: (sealId: number) =>
    request<ContractSeal>(`/api/v1/seals/${sealId}`),

  // ==========================================================================
  // EntryTag API
  // ==========================================================================
  listEntryTags: (entryId?: number, ledgerId?: number) => {
    const params = new URLSearchParams()
    if (entryId) params.set('entry_id', String(entryId))
    if (ledgerId) params.set('ledger_id', String(ledgerId))
    const query = params.toString()
    return request<EntryTag[]>(`/api/entry-tags${query ? `?${query}` : ''}`)
  },

  batchListEntryTags: (payload: {
    entry_ids: number[]
    ledger_id?: number
    category_code?: string
  }) =>
    request<EntryTag[]>('/api/entry-tags/tags/batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  listTagCategories: (ledgerId: number, params?: { status?: 'active' | 'disabled' | 'archived' | 'all' }) => {
    const qs = new URLSearchParams({ ledger_id: String(ledgerId) })
    if (params?.status) qs.set('status', params.status)
    return request<TagCategoryNode[]>(`/api/entry-tags/categories?${qs.toString()}`)
  },

  createTagCategory: (
    ledgerId: number,
    payload: {
      code: string
      name: string
      description?: string
      parent_id?: number | null
      value_type?: string
      source_table?: string
      is_mandatory?: boolean
      sort_order?: number
    },
  ) =>
    request<{ id: number; code: string; name: string }>(
      `/api/entry-tags/categories?ledger_id=${ledgerId}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      },
    ),

  updateTagCategory: (
    categoryId: number,
    payload: Partial<{
      name: string
      description: string
      value_type: string
      source_table: string
      is_mandatory: boolean
      sort_order: number
      status: string
    }>,
  ) =>
    request<{ id: number; code: string; name: string }>(`/api/entry-tags/categories/${categoryId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  deleteTagCategory: (categoryId: number) =>
    request<{ message: string }>(`/api/entry-tags/categories/${categoryId}`, { method: 'DELETE' }),

  aggregateEntryTags: (ledgerId: number, categoryCode: string) =>
    request<EntryTagAggregate[]>(
      `/api/entry-tags/aggregate/${encodeURIComponent(categoryCode)}?ledger_id=${ledgerId}`,
    ),

  aggregateEntryTagsScoped: (
    ledgerId: number,
    categoryCode: string,
    options?: {
      account_codes?: string[]
      account_code_match?: 'exact' | 'prefix' | 'contains'
      q?: string
      limit?: number
      include_voucher_lines?: boolean
    },
  ) => {
    const qs = new URLSearchParams({ ledger_id: String(ledgerId) })
    if (options?.account_codes?.length) qs.set('account_codes', JSON.stringify(options.account_codes))
    if (options?.account_code_match) qs.set('account_code_match', options.account_code_match)
    if (options?.q) qs.set('q', options.q)
    if (options?.limit != null) qs.set('limit', String(options.limit))
    if (options?.include_voucher_lines) qs.set('include_voucher_lines', 'true')
    return request<EntryTagAggregate[]>(
      `/api/entry-tags/aggregate/${encodeURIComponent(categoryCode)}?${qs.toString()}`,
    )
  },

  listTagMappingRules: (ledgerId: number, sourceType?: string) => {
    const qs = new URLSearchParams({ ledger_id: String(ledgerId) })
    if (sourceType) qs.set('source_type', sourceType)
    return request<TagMappingRule[]>(`/api/entry-tags/mapping-rules?${qs.toString()}`)
  },

  createTagMappingRule: (
    ledgerId: number,
    payload: {
      source_pattern: string
      target_category_code: string
      source_type?: string
      target_value?: string | null
      priority?: number
      is_regex?: boolean
      description?: string | null
    },
  ) =>
    request<{ id: number; source_pattern: string }>(
      `/api/entry-tags/mapping-rules?ledger_id=${ledgerId}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      },
    ),

  updateTagMappingRule: (
    ruleId: number,
    payload: Partial<{
      target_value: string | null
      priority: number
      is_active: boolean
      description: string | null
    }>,
  ) =>
    request<{ id: number; source_pattern: string }>(`/api/entry-tags/mapping-rules/${ruleId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  deleteTagMappingRule: (ruleId: number) =>
    request<{ status: string }>(`/api/entry-tags/mapping-rules/${ruleId}`, { method: 'DELETE' }),

  createCounterparty: (payload: {
    name: string
    role?: string
    unified_credit_no?: string | null
    is_related_party?: boolean
  }) =>
    request<Counterparty>('/api/counterparties', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  updateCounterparty: (
    counterpartyId: number,
    payload: {
      name?: string
      role?: string
      unified_credit_no?: string | null
      is_related_party?: boolean
    },
  ) =>
    request<Counterparty>(`/api/counterparties/${counterpartyId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  disableCounterparty: (counterpartyId: number) =>
    request<Counterparty>(`/api/counterparties/${counterpartyId}/disable`, { method: 'POST' }),

  getCounterparty: (counterpartyId: number) =>
    request<Counterparty>(`/api/counterparties/${counterpartyId}`),

  batchGetCounterparties: (ids: number[]) =>
    request<Counterparty[]>('/api/counterparties/batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids }),
    }),

  batchUpdateCounterpartyRole: (payload: { ids: number[]; role: string }) =>
    request<{ updated: number; role: string; items: Counterparty[]; skipped_ids: number[] }>(
      '/api/counterparties/batch-update-role',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      },
    ),

  // ==========================================================================
  // LLM Tag Resolution API
  // ==========================================================================
  llmBatchResolve: (payload: {
    entry_ids?: number[]
    ledger_id?: number
    batch_size?: number
    dry_run?: boolean
  }) =>
    request<LlmResolutionResult>('/api/llm-resolution/batch-resolve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  llmGetPendingSuggestions: (params?: {
    ledger_id?: number
    limit?: number
    offset?: number
  }) => {
    const searchParams = new URLSearchParams()
    if (params?.ledger_id != null) searchParams.set('ledger_id', String(params.ledger_id))
    if (params?.limit != null) searchParams.set('limit', String(params.limit))
    if (params?.offset != null) searchParams.set('offset', String(params.offset))
    const query = searchParams.toString()
    return request<{
      success: boolean
      items: LlmTagSuggestion[]
      total: number
      limit: number
      offset: number
    }>(`/api/llm-resolution/pending-suggestions${query ? `?${query}` : ''}`)
  },

  llmApproveSuggestions: (suggestionIds: number[]) =>
    request<{ success: boolean; message: string; approved_count: number }>('/api/llm-resolution/approve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ suggestion_ids: suggestionIds }),
    }),

  llmRejectSuggestions: (suggestionIds: number[]) =>
    request<{ success: boolean; message: string; rejected_count: number }>('/api/llm-resolution/reject', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ suggestion_ids: suggestionIds }),
    }),

  llmGetStatistics: (ledgerId?: number) => {
    const params = new URLSearchParams()
    if (ledgerId != null) params.set('ledger_id', String(ledgerId))
    const query = params.toString()
    return request<LlmResolutionStatistics>(`/api/llm-resolution/statistics${query ? `?${query}` : ''}`)
  },

  getAccountTagRules: () =>
    request<{ success: boolean; config: AccountTagConfig; message?: string }>('/api/config/account-tag-rules'),

  saveAccountTagRules: (config: AccountTagConfig) =>
    request<{ success: boolean; message?: string }>('/api/config/account-tag-rules', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    }),

  resetAccountTagRules: () =>
    request<{ success: boolean; message?: string; config?: AccountTagConfig }>(
      '/api/config/account-tag-rules/reset',
      {
        method: 'POST',
      },
    ),

  getLedgerAccountTagRules: (ledgerId: number) =>
    request<{
      success: boolean
      config: AccountTagConfig
      has_ledger_override?: boolean
      message?: string
    }>(`/api/config/ledgers/${ledgerId}/account-tag-rules`),

  saveLedgerAccountTagRules: (ledgerId: number, config: AccountTagConfig) =>
    request<{ success: boolean; message?: string; has_ledger_override?: boolean }>(
      `/api/config/ledgers/${ledgerId}/account-tag-rules`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      },
    ),

  resetLedgerAccountTagRules: (ledgerId: number) =>
    request<{ success: boolean; message?: string; config?: AccountTagConfig; has_ledger_override?: boolean }>(
      `/api/config/ledgers/${ledgerId}/account-tag-rules/reset`,
      { method: 'POST' },
    ),

  getLedgerDimensionReadiness: (ledgerId: number) =>
    request<{
      ledger_id: number
      ready_for_structured_import: boolean
      tag_rules_reviewed_at?: string | null
      parse_config_ok?: boolean
      category_count?: number
      prior_structured_import_count?: number
      blockers?: Array<{ code: string; message: string; action_tab?: string }>
      warnings?: Array<{ code: string; message: string; action_tab?: string }>
      vector_scope_note?: string
    }>(`/api/config/ledgers/${ledgerId}/dimension-readiness`),

  acknowledgeLedgerDimensionReadiness: (ledgerId: number) =>
    request<{ success: boolean; ledger_id: number; tag_rules_reviewed_at?: string }>(
      `/api/config/ledgers/${ledgerId}/dimension-readiness/acknowledge`,
      { method: 'POST' },
    ),

  getStagingLlmPending: (jobId: number) =>
    request<{
      job_id: number
      ledger_id: number | null
      total: number
      items: Array<{
        staging_id: number
        voucher_no?: string
        summary?: string
        account_code?: string
        account_name?: string
      }>
    }>(`/api/import-jobs/${jobId}/staging/llm-pending`),

  resolveStagingLlmTags: (
    jobId: number,
    payload?: { staging_ids?: number[]; batch_size?: number; dry_run?: boolean },
  ) =>
    request<{
      task_id: string
      total_rows: number
      success_count: number
      failed_count: number
      resolved_rows: number
      processing_time_ms: number
      error_messages: string[]
      suggested_tags: Array<{
        staging_id: number
        category_code: string
        tag_value: string
        display_name: string
        confidence: number
        validation_passed: boolean
      }>
    }>(`/api/import-jobs/${jobId}/staging/llm-resolve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload || {}),
    }),

  listEvolutionProposals: (params?: { status?: string; limit?: number }) => {
    const searchParams = new URLSearchParams()
    searchParams.set('status', params?.status ?? 'draft')
    searchParams.set('limit', String(params?.limit ?? 200))
    return request<{ items: EvolutionProposal[]; total: number }>(
      `/api/parser-engine/evolution/proposals?${searchParams.toString()}`,
    )
  },

  runEvolutionScan: () =>
    request<{ new_proposals: number; run_id: string }>('/api/parser-engine/evolution/run', {
      method: 'POST',
    }),

  runNightlyRegression: () =>
    request<{ run_id: string; categories: Record<string, unknown> }>(
      '/api/parser-engine/evolution/nightly-regression',
      { method: 'POST' },
    ),

  batchApproveEvolutionProposals: (patchIds: number[], approvedBy = 'ui') =>
    request<{ approved_count: number }>('/api/parser-engine/evolution/proposals/batch-approve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ patch_ids: patchIds, approved_by: approvedBy }),
    }),

  batchRejectEvolutionProposals: (patchIds: number[], reason = '') =>
    request<{ rejected_count: number }>('/api/parser-engine/evolution/proposals/batch-reject', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ patch_ids: patchIds, reason }),
    }),

  getTaxEgressPools: (cityCode?: string) =>
    request<TaxEgressPoolsResponse>(`/api/tax/egress/pools${cityCode ? `?city_code=${encodeURIComponent(cityCode)}` : ''}`),

  listTaxEgressBindings: (cityCode?: string, ledgerId?: number | null) => {
    const params = new URLSearchParams()
    if (cityCode) params.set('city_code', cityCode)
    const headers: Record<string, string> = {}
    if (typeof ledgerId === 'number' && ledgerId > 0) headers['X-Ledger-Id'] = String(ledgerId)
    const qs = params.toString()
    return request<{ items: TaxEgressBinding[] }>(`/api/tax/egress/bindings${qs ? `?${qs}` : ''}`, { headers })
  },

  createTaxEgressBinding: (
    payload: { taxpayer_id: string; taxpayer_name: string; city_code: string },
    ledgerId?: number | null,
  ) => {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (typeof ledgerId === 'number' && ledgerId > 0) headers['X-Ledger-Id'] = String(ledgerId)
    return request<TaxEgressBinding>('/api/tax/egress/bindings', {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
    })
  },

  rotateTaxEgressBinding: (bindingId: number, reason?: string) =>
    request<TaxEgressBinding>(`/api/tax/egress/bindings/${bindingId}/rotate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason: reason || null }),
    }),

  startTaxEgressSession: (bindingId: number) =>
    request<TaxEgressSessionStart>(`/api/tax/egress/bindings/${bindingId}/sessions`, { method: 'POST' }),

  listTaxRotationEvents: (limit = 30) =>
    request<{ items: TaxRotationEvent[] }>(`/api/tax/egress/rotation-events?limit=${limit}`),
}
