import { Navigate, useSearchParams } from 'react-router-dom'
import { VOUCHER_FLOW_ENTRY } from '../utils/voucherFlowRoutes'

type VoucherFlowStepGuardProps = {
  /** Step3 起需要 URL 中的 jobId */
  step: number
  children: React.ReactNode
}

/** 阻止从书签/历史记录直接跳入 Step3~5，避免缺少 jobId 导致事务不一致。 */
export function VoucherFlowStepGuard({ step, children }: VoucherFlowStepGuardProps) {
  const [searchParams] = useSearchParams()
  const jobId = Number(searchParams.get('jobId') || 0)

  if (step >= 3 && !jobId) {
    return <Navigate to={VOUCHER_FLOW_ENTRY} replace />
  }

  return <>{children}</>
}
