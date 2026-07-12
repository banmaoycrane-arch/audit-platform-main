/** 导入任务上下文：在维度中心与凭证 Step 之间往返时保留 jobId */

const STORAGE_KEY = 'finance_audit_import_job_context'
const LEDGER_RESUME_PREFIX = 'finance_audit_ledger_import_resume_'

export type ImportJobContext = {
  jobId: number
  /** 进入维度中心前的页面路径（含 query） */
  returnPath: string
  savedAt: number
}

/** 按账套持久化「上次导入进度」，浏览器重启后仍可恢复 */
export type LedgerImportResume = {
  ledgerId: number
  jobId: number
  step: 2 | 3 | 4
  reviewPhase?: 'dimensions' | 'vouchers'
  inputMode?: string
  structuredKind?: string
  periodMappingMode?: string
  savedAt: number
}

/** 可从中断处恢复的导入任务状态 */
export const RESUMABLE_IMPORT_STATUSES = new Set(['preview', 'processing', 'parsed'])

export function isResumableImportJob(job: { status: string; entry_count: number }): boolean {
  return RESUMABLE_IMPORT_STATUSES.has(job.status) && job.entry_count > 0
}

export function isTerminalImportJob(job: { status: string }): boolean {
  return job.status === 'completed' || job.status === 'cancelled'
}

export function clearLedgerImportResume(ledgerId: number): void {
  if (!ledgerId) return
  try {
    localStorage.removeItem(`${LEDGER_RESUME_PREFIX}${ledgerId}`)
  } catch {
    // ignore
  }
}

export function persistImportJobContext(jobId: number, returnPath: string): void {
  if (!jobId) return
  const ctx: ImportJobContext = { jobId, returnPath, savedAt: Date.now() }
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(ctx))
  } catch {
    // ignore quota / private mode
  }
}

export function readImportJobContext(): ImportJobContext | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as ImportJobContext
    if (!parsed?.jobId) return null
    return parsed
  } catch {
    return null
  }
}

export function clearImportJobContext(): void {
  try {
    sessionStorage.removeItem(STORAGE_KEY)
  } catch {
    // ignore
  }
}

export function persistLedgerImportResume(
  payload: Omit<LedgerImportResume, 'savedAt'>,
): void {
  if (!payload.ledgerId || !payload.jobId) return
  const record: LedgerImportResume = { ...payload, savedAt: Date.now() }
  try {
    localStorage.setItem(`${LEDGER_RESUME_PREFIX}${payload.ledgerId}`, JSON.stringify(record))
  } catch {
    // ignore
  }
}

export function readLedgerImportResume(ledgerId: number): LedgerImportResume | null {
  if (!ledgerId) return null
  try {
    const raw = localStorage.getItem(`${LEDGER_RESUME_PREFIX}${ledgerId}`)
    if (!raw) return null
    const parsed = JSON.parse(raw) as LedgerImportResume
    if (!parsed?.jobId) return null
    return parsed
  } catch {
    return null
  }
}

export function buildLedgerResumePath(resume: LedgerImportResume): string {
  const base =
    resume.step === 2
      ? step2ReturnPath(resume.jobId)
      : resume.step === 3
        ? `/ledger/vouchers/step/3?jobId=${resume.jobId}&inputMode=${resume.inputMode || 'day_book_import'}`
        : step4ReturnPath(resume.jobId, resume.reviewPhase || 'vouchers')
  if (resume.periodMappingMode) {
    const url = new URL(base, 'http://local')
    url.searchParams.set('periodMappingMode', resume.periodMappingMode)
    if (resume.structuredKind) {
      url.searchParams.set('structuredKind', resume.structuredKind)
    }
    return `${url.pathname}${url.search}`
  }
  if (resume.structuredKind && resume.step === 2) {
    const url = new URL(base, 'http://local')
    url.searchParams.set('structuredKind', resume.structuredKind)
    return `${url.pathname}${url.search}`
  }
  return base
}

export function step4ReturnPath(
  jobId: number,
  reviewPhase: 'dimensions' | 'vouchers' = 'dimensions',
): string {
  const params = new URLSearchParams({
    jobId: String(jobId),
    reviewPhase,
    inputMode: 'day_book_import',
  })
  return `/ledger/vouchers/step/4?${params.toString()}`
}

export function step2ReturnPath(jobId: number): string {
  const params = new URLSearchParams({
    jobId: String(jobId),
    inputMode: 'day_book_import',
    structuredKind: 'day_book',
  })
  return `/ledger/vouchers/step/2?${params.toString()}`
}

export function dimensionsPath(
  tab: string,
  jobId: number,
  extra?: Record<string, string>,
): string {
  const params = new URLSearchParams({ tab, jobId: String(jobId), ...extra })
  return `/ledger/dimensions?${params.toString()}`
}
