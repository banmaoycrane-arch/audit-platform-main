import { useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { trackBookkeepingStep } from './productAnalytics'

export type BookkeepingStepId =
  | 'step1_select'
  | 'step2_import'
  | 'step3_generate'
  | 'step4_review'
  | 'step5_post'

export function useTrackBookkeepingStep(step: BookkeepingStepId, jobIdOverride?: number | null): void {
  const [searchParams] = useSearchParams()
  const jobFromUrl = Number(searchParams.get('jobId') || 0)
  const jobId = jobIdOverride ?? (jobFromUrl > 0 ? jobFromUrl : undefined)

  useEffect(() => {
    trackBookkeepingStep(step, jobId)
  }, [step, jobId])
}
