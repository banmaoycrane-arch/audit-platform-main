import type { AuthContext } from '../api/client'

/** 登录后根据绑定状态决定首屏跳转路径 */
export function resolvePostLoginPath(context: AuthContext): string {
  if (!context.requires_onboarding && context.missing_bindings.length === 0) {
    return '/workspace'
  }
  if (context.missing_bindings.includes('team') && context.temporary_status === 'onboarding_pending') {
    return '/onboarding-request'
  }
  return '/onboarding'
}

/** 审计/记账步骤间保留 jobId 等查询参数 */
export function withJobQuery(path: string, jobId?: number | null, extra?: Record<string, string | number | null | undefined>) {
  const params = new URLSearchParams()
  if (jobId) params.set('jobId', String(jobId))
  if (extra) {
    Object.entries(extra).forEach(([key, value]) => {
      if (value !== null && value !== undefined && value !== '') {
        params.set(key, String(value))
      }
    })
  }
  const qs = params.toString()
  return qs ? `${path}?${qs}` : path
}
