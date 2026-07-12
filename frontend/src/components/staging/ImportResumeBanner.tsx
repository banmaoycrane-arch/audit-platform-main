import { Alert, Button, Space, Spin } from 'antd'
import { CheckCircleOutlined, HistoryOutlined, PlayCircleOutlined, ClearOutlined } from '@ant-design/icons'
import { Link, useNavigate } from 'react-router-dom'
import { useEffect, useMemo, useState } from 'react'

import { api, type ImportJob } from '../../api/client'
import {
  buildLedgerResumePath,
  clearLedgerImportResume,
  isResumableImportJob,
  isTerminalImportJob,
  readLedgerImportResume,
  step2ReturnPath,
  step4ReturnPath,
  type LedgerImportResume,
} from '../../utils/importJobContext'

type ImportResumeBannerProps = {
  ledgerId: number | null | undefined
  /** 当前 URL 中的 jobId；有值时仅展示其它可恢复任务 */
  currentJobId?: number
  variant: 'step2' | 'step4'
  /** Step2 内恢复时可直接写入 state，避免整页跳转 */
  onResumeJob?: (jobId: number) => void
}

function formatJobLabel(job: ImportJob): string {
  const rows = job.entry_count > 0 ? `${job.entry_count.toLocaleString()} 条分录` : '已上传待解析'
  return `#${job.id} · ${rows} · ${job.status}`
}

function step5Path(jobId: number): string {
  const params = new URLSearchParams({
    jobId: String(jobId),
    inputMode: 'day_book_import',
  })
  return `/ledger/vouchers/step/5?${params.toString()}`
}

export function ImportResumeBanner({
  ledgerId,
  currentJobId = 0,
  variant,
  onResumeJob,
}: ImportResumeBannerProps) {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [jobs, setJobs] = useState<ImportJob[]>([])
  const [pinnedJob, setPinnedJob] = useState<ImportJob | null>(null)
  const [pinnedLoading, setPinnedLoading] = useState(false)
  const [localResume, setLocalResume] = useState<LedgerImportResume | null>(() =>
    ledgerId ? readLedgerImportResume(ledgerId) : null,
  )

  useEffect(() => {
    setLocalResume(ledgerId ? readLedgerImportResume(ledgerId) : null)
  }, [ledgerId])

  useEffect(() => {
    if (!ledgerId) return
    let cancelled = false
    setLoading(true)
    void api
      .listImportJobs(ledgerId)
      .then((list) => {
        if (cancelled) return
        const resumable = list
          .filter(isResumableImportJob)
          .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
        setJobs(resumable)
      })
      .catch(() => {
        if (!cancelled) setJobs([])
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [ledgerId])

  const pinnedJobId = useMemo(() => {
    if (!localResume?.jobId || !ledgerId) return 0
    if (jobs.some((job) => job.id === localResume.jobId)) return 0
    if (currentJobId === localResume.jobId) return 0
    return localResume.jobId
  }, [localResume, ledgerId, jobs, currentJobId])

  useEffect(() => {
    if (!ledgerId || !pinnedJobId) {
      setPinnedJob(null)
      return
    }
    let cancelled = false
    setPinnedLoading(true)
    void api
      .getImportJob(pinnedJobId)
      .then((job) => {
        if (cancelled) return
        setPinnedJob(job)
        if (isTerminalImportJob(job) || !isResumableImportJob(job)) {
          clearLedgerImportResume(ledgerId)
          setLocalResume(null)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setPinnedJob(null)
          clearLedgerImportResume(ledgerId)
          setLocalResume(null)
        }
      })
      .finally(() => {
        if (!cancelled) setPinnedLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [ledgerId, pinnedJobId])

  const dismissResumeHint = () => {
    if (!ledgerId) return
    clearLedgerImportResume(ledgerId)
    setLocalResume(null)
    setPinnedJob(null)
  }

  const otherJobs = jobs.filter((job) => job.id !== currentJobId)
  const primaryJob =
    (currentJobId ? jobs.find((job) => job.id === currentJobId) : null) ??
    jobs.find((job) => job.id === localResume?.jobId) ??
    jobs[0] ??
    null

  const showMissingJobHint = variant === 'step4' && !currentJobId && !loading && !primaryJob && !pinnedJob && !localResume

  if (!ledgerId) {
    return showMissingJobHint ? (
      <Alert
        type="warning"
        showIcon
        style={{ marginBottom: 16 }}
        title="尚未找到待复核凭证草稿"
        description="请从「生成草稿」步骤保存待复核凭证草稿后再进入本步骤；或先在顶部选择账套。"
      />
    ) : null
  }

  if ((loading || pinnedLoading) && !primaryJob && !pinnedJob && !localResume) {
    return (
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        title="正在检查是否有未完成的导入草稿…"
        description={<Spin size="small" />}
      />
    )
  }

  if (pinnedJob?.status === 'completed') {
    return (
      <Alert
        type="success"
        showIcon
        icon={<CheckCircleOutlined />}
        style={{ marginBottom: 16 }}
        title={`导入任务 #${pinnedJob.id} 已完成`}
        description={
          <Space wrap size="middle" style={{ marginTop: 4 }}>
            <span>
              共 {pinnedJob.entry_count.toLocaleString()} 条分录已确认入账，草稿已清空，无需再复核或重新上传。
            </span>
            <Link to={step5Path(pinnedJob.id)}>
              <Button type="primary" size="small" icon={<PlayCircleOutlined />}>
                前往 Step5 导出
              </Button>
            </Link>
            <Link to={step2ReturnPath(pinnedJob.id)}>
              <Button size="small" icon={<HistoryOutlined />}>
                查看 Step2 导入记录
              </Button>
            </Link>
            <Button size="small" onClick={dismissResumeHint}>
              不再提示
            </Button>
          </Space>
        }
      />
    )
  }

  if (pinnedJob && !isResumableImportJob(pinnedJob)) {
    const isCancelled = pinnedJob.status === 'cancelled' || pinnedJob.status === 'failed'
    return (
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        title={`导入任务 #${pinnedJob.id} 已结束（${pinnedJob.status}）`}
        description={
          <Space wrap size="middle" style={{ marginTop: 4 }}>
            <span>
              {isCancelled
                ? '该任务已取消或失败，浏览器中的恢复记录已清除。'
                : '该任务当前不可恢复，浏览器中的恢复记录已清除。'}
            </span>
            <Link to="/ledger/import-jobs">
              <Button size="small" icon={<ClearOutlined />}>
                管理导入任务
              </Button>
            </Link>
            <Button size="small" onClick={dismissResumeHint}>
              不再提示
            </Button>
          </Space>
        }
      />
    )
  }

  if (!primaryJob && !localResume && !showMissingJobHint) {
    return null
  }

  const saved = localResume
  const targetJobId = primaryJob?.id ?? saved?.jobId
  if (!targetJobId && showMissingJobHint) {
    return (
      <Alert
        type="warning"
        showIcon
        style={{ marginBottom: 16 }}
        title="尚未找到待复核凭证草稿"
        description="本账套暂无 preview 状态的导入任务。若刚重启服务，数据仍在数据库中 — 请从 Step2 进入并选择「继续上次导入」，勿重新上传文件。"
      />
    )
  }

  if (!targetJobId) return null

  const continueStep4 = saved?.step === 4
    ? buildLedgerResumePath(saved)
    : step4ReturnPath(targetJobId, 'vouchers')
  const continueStep2 = saved?.step === 2
    ? buildLedgerResumePath(saved)
    : step2ReturnPath(targetJobId)

  const handleContinueStep2 = () => {
    if (onResumeJob) {
      onResumeJob(targetJobId)
      return
    }
    navigate(continueStep2)
  }

  const title =
    variant === 'step4' && !currentJobId
      ? `检测到未完成导入任务 #${targetJobId} — 草稿已保存在数据库，无需重新上传`
      : variant === 'step2' && !currentJobId
        ? `可继续上次序时簿导入 #${targetJobId}，无需重新解析`
        : `导入任务 #${targetJobId} 的 staging 草稿仍有效`

  const description = (
    <Space wrap size="middle" style={{ marginTop: 4 }}>
      <span>
        {primaryJob
          ? formatJobLabel(primaryJob)
          : saved
            ? `上次停留在 Step${saved.step}${saved.reviewPhase ? `（${saved.reviewPhase === 'vouchers' ? '凭证复核' : '维度复核'}）` : ''}`
            : ''}
        。重启浏览器或服务后可直接从此处继续，不必重新导入文件。
      </span>
      {variant === 'step4' && !currentJobId && (
        <Link to={continueStep4}>
          <Button type="primary" size="small" icon={<PlayCircleOutlined />}>
            继续 Step4 凭证复核
          </Button>
        </Link>
      )}
      {variant === 'step2' && !currentJobId && (
        <Button type="primary" size="small" icon={<PlayCircleOutlined />} onClick={handleContinueStep2}>
          继续 Step2 查看草稿
        </Button>
      )}
      {variant === 'step4' && currentJobId > 0 && (
        <Link to={step2ReturnPath(currentJobId)}>
          <Button size="small" icon={<HistoryOutlined />}>
            查看 Step2 导入结果
          </Button>
        </Link>
      )}
      {otherJobs.length > 0 && (
        <span style={{ color: 'rgba(0,0,0,0.45)' }}>
          另有 {otherJobs.length} 个可恢复任务：
          {otherJobs.slice(0, 3).map((job) => (
            <Link key={job.id} to={step4ReturnPath(job.id, 'vouchers')} style={{ marginLeft: 8 }}>
              #{job.id}
            </Link>
          ))}
        </span>
      )}
      <Link to="/ledger/import-jobs">
        <Button size="small" icon={<ClearOutlined />}>
          清理卡死导入任务
        </Button>
      </Link>
      {saved && (
        <Button size="small" onClick={dismissResumeHint}>
          不再提示
        </Button>
      )}
    </Space>
  )

  return (
    <Alert
      type={variant === 'step4' && !currentJobId ? 'warning' : 'info'}
      showIcon
      style={{ marginBottom: 16 }}
      title={title}
      description={description}
    />
  )
}
