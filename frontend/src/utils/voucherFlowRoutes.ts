/** 凭证导入五步：URL 保留 step/1~5 供程序串联，日常导航只暴露入口。 */
export const VOUCHER_FLOW_ENTRY = '/ledger/vouchers/step/1'

export function voucherFlowStepPath(
  step: number,
  params?: Record<string, string | number | undefined | null>,
): string {
  const search = new URLSearchParams()
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null && value !== '') {
        search.set(key, String(value))
      }
    }
  }
  const qs = search.toString()
  return `/ledger/vouchers/step/${step}${qs ? `?${qs}` : ''}`
}

export function step4ReviewPath(jobId: number, reviewPhase: 'dimensions' | 'vouchers' = 'vouchers') {
  return voucherFlowStepPath(4, {
    jobId,
    reviewPhase,
    inputMode: 'day_book_import',
  })
}

export function step5ExportPath(jobId: number) {
  return voucherFlowStepPath(5, {
    jobId,
    inputMode: 'day_book_import',
  })
}

/** 侧栏高亮：step/2~5 归入同一导入流程入口 */
export function voucherFlowNavKey(pathname: string): string | null {
  if (pathname.startsWith('/ledger/vouchers/step/')) {
    const step = Number(pathname.split('/').pop() || 1)
    return step >= 2 ? VOUCHER_FLOW_ENTRY : pathname
  }
  if (pathname.startsWith('/accounting/step/')) {
    return VOUCHER_FLOW_ENTRY
  }
  return null
}
