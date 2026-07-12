const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

export type ProductEventPayload = {
  event_name: string
  session_id?: string
  job_id?: number
  properties?: Record<string, unknown>
}

export type MvpKpiItem = {
  key: string
  label: string
  value: number | null
  threshold: string
  pass_line: number
  verdict: string
  samples: number
}

export type MvpKpiSummary = {
  period_days: number
  ledger_id: number | null
  generated_at: string
  event_counts: Record<string, number>
  total_events: number
  kpis: MvpKpiItem[]
  recent_events: Array<{
    id: number
    event_name: string
    created_at: string | null
    job_id: number | null
    session_id: string | null
    properties: Record<string, unknown> | null
  }>
}

function authHeaders(): HeadersInit {
  const token = localStorage.getItem('token')
  const ledgerId = localStorage.getItem('currentLedgerId')
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers.Authorization = `Bearer ${token}`
  if (ledgerId) headers['X-Ledger-Id'] = ledgerId
  return headers
}

export function createAgentSessionId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  return `sess-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
}

/**  fire-and-forget 产品埋点，失败不打断用户操作 */
export async function trackProductEvent(payload: ProductEventPayload): Promise<void> {
  try {
    await fetch(`${API_BASE}/api/product-events`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(payload),
    })
  } catch {
    // MVP 阶段静默失败
  }
}

export async function fetchMvpKpiSummary(days = 14): Promise<MvpKpiSummary> {
  const response = await fetch(`${API_BASE}/api/product-events/mvp-kpi-summary?days=${days}`, {
    headers: authHeaders(),
  })
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(detail || `KPI 加载失败 (${response.status})`)
  }
  return response.json() as Promise<MvpKpiSummary>
}

const STEP_STARTED_AT: Record<string, number> = {}

export function trackBookkeepingStep(
  step: 'step1_select' | 'step2_import' | 'step3_generate' | 'step4_review' | 'step5_post',
  jobId?: number | null,
): void {
  const key = `${step}:${jobId ?? 'none'}`
  const now = Date.now()
  const prev = STEP_STARTED_AT[key]
  STEP_STARTED_AT[key] = now
  const duration = prev ? Math.round((now - prev) / 1000) : undefined
  void trackProductEvent({
    event_name: 'task_bookkeeping_step_reached',
    job_id: jobId ?? undefined,
    properties: {
      step,
      duration_from_prev_seconds: duration,
    },
  })
}

export function trackSuggestedPathClick(sessionId: string, path: string, secondsSinceSuggest: number): void {
  void trackProductEvent({
    event_name: 'agent_suggested_path_click',
    session_id: sessionId,
    properties: {
      path,
      seconds_since_suggest: secondsSinceSuggest,
    },
  })
}

type DraftLineSnapshot = {
  id: number
  account: string
  summary: string
  debit: number
  credit: number
  counterparty: string
  tags: string[]
}

export function buildDraftLineSnapshots(
  lines: Array<{
    id: number
    resolved_account_code?: string | null
    account_code?: string | null
    resolved_account_name?: string | null
    account_name?: string | null
    summary?: string | null
    debit_amount?: number | null
    credit_amount?: number | null
    counterparty?: string | null
    entry_tags_payload?: Array<{ display_name?: string | null; tag_value?: string | null }> | null
  }>,
): DraftLineSnapshot[] {
  return lines.map((line) => ({
    id: line.id,
    account: `${line.resolved_account_code || line.account_code || ''}|${line.resolved_account_name || line.account_name || ''}`,
    summary: String(line.summary || ''),
    debit: Number(line.debit_amount || 0),
    credit: Number(line.credit_amount || 0),
    counterparty: String(line.counterparty || ''),
    tags: (line.entry_tags_payload || []).map((tag) => String(tag.display_name || tag.tag_value || '')),
  }))
}

export function countDraftFields(snapshots: DraftLineSnapshot[]): number {
  return snapshots.reduce((sum, line) => sum + 5 + line.tags.length, 0)
}

export function diffDraftAdoption(
  initial: DraftLineSnapshot[],
  current: DraftLineSnapshot[],
): { fields_total: number; fields_adopted_unchanged: number; fields_edited: number } {
  const fields_total = countDraftFields(initial)
  if (fields_total === 0) {
    return { fields_total: 0, fields_adopted_unchanged: 0, fields_edited: 0 }
  }
  let unchanged = 0
  const currentById = new Map(current.map((line) => [line.id, line]))
  for (const line of initial) {
    const cur = currentById.get(line.id)
    if (!cur) {
      continue
    }
    if (line.account === cur.account) unchanged += 1
    if (line.summary === cur.summary) unchanged += 1
    if (line.debit === cur.debit) unchanged += 1
    if (line.credit === cur.credit) unchanged += 1
    if (line.counterparty === cur.counterparty) unchanged += 1
    const maxTags = Math.max(line.tags.length, cur.tags.length)
    for (let i = 0; i < maxTags; i += 1) {
      if ((line.tags[i] || '') === (cur.tags[i] || '')) unchanged += 1
    }
  }
  const fields_edited = Math.max(0, fields_total - unchanged)
  return {
    fields_total,
    fields_adopted_unchanged: unchanged,
    fields_edited,
  }
}

export async function trackAiVoucherDraftShown(
  jobId: number,
  voucherId: number | null,
  fieldsTotal: number,
  llmUsed: boolean,
): Promise<void> {
  await trackProductEvent({
    event_name: 'ai_voucher_draft_shown',
    job_id: jobId,
    properties: {
      voucher_id: voucherId,
      fields_total: fieldsTotal,
      llm_used: llmUsed,
    },
  })
}

export async function trackAiVoucherDraftSaved(
  jobId: number,
  voucherId: number | null,
  stats: { fields_total: number; fields_adopted_unchanged: number; fields_edited: number },
  timeToSaveSeconds: number,
): Promise<void> {
  await trackProductEvent({
    event_name: 'ai_voucher_draft_saved',
    job_id: jobId,
    properties: {
      voucher_id: voucherId,
      ...stats,
      time_to_save_seconds: timeToSaveSeconds,
    },
  })
}
