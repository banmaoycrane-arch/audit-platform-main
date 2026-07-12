import {
  Card,
  Table,
  Button,
  Steps,
  Typography,
  Tag,
  Space,
  Alert,
  message,
  Modal,
  Select,
  Input,
  Tabs,
  Radio,
  InputNumber,
  Spin,
  Tooltip,
} from 'antd'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { TablePaginationConfig } from 'antd/es/table'
import type { ColumnsType } from 'antd/es/table'
import { EyeOutlined } from '@ant-design/icons'
import { api } from '../../api/client'
import type { ImportJob } from '../../api/client'
import { FlowNav } from '../../components/FlowNav'
import { Step4DimensionReviewPanel } from '../../components/staging/Step4DimensionReviewPanel'
import {
  StagingVoucherReviewDrawer,
  type PreviewVoucherSummary,
  type Step4ComplianceMode,
} from '../../components/staging/StagingVoucherReviewDrawer'
import { VoucherSignatureStrip } from '../../components/staging/VoucherSignatureStrip'
import { formatAmount } from '../../money'
import { useAuthStore } from '../../stores/authStore'
import { ImportResumeBanner } from '../../components/staging/ImportResumeBanner'
import {
  clearLedgerImportResume,
  persistLedgerImportResume,
  persistImportJobContext,
} from '../../utils/importJobContext'
import { useTrackBookkeepingStep } from '../../hooks/useTrackBookkeepingStep'

const { Title, Text } = Typography

type ReviewStats = {
  total_vouchers: number
  verified_vouchers: number
  partial_vouchers: number
  unbalanced_voucher_nos: string[]
  total_lines: number
  spot_check_vouchers?: number
  compliance_pending_vouchers?: number
  compliance_reviewed_vouchers?: number
}

const EMPTY_REVIEW_STATS: ReviewStats = {
  total_vouchers: 0,
  verified_vouchers: 0,
  partial_vouchers: 0,
  unbalanced_voucher_nos: [],
  total_lines: 0,
  spot_check_vouchers: 0,
  compliance_pending_vouchers: 0,
  compliance_reviewed_vouchers: 0,
}

type ReviewFilter =
  | 'all'
  | 'pending'
  | 'verified'
  | 'unbalanced'
  | 'spot_check'
  | 'compliance_pending'
  | 'compliance_reviewed'

const REVIEW_STATUS_LABEL: Record<string, string> = {
  draft: '待复核',
  verified: '已复核',
  partial: '部分复核',
  ready: '待确认入账',
}

const COMPLIANCE_SEVERITY_COLOR: Record<string, string> = {
  info: 'blue',
  warning: 'orange',
  error: 'red',
}

const COMPLIANCE_MODE_OPTIONS: Array<{ value: Step4ComplianceMode; label: string; hint: string }> = [
  { value: 'skip', label: '不审查合规，只复核入账', hint: '隐藏合规审查，仅人工勾选复核并确认入账。' },
  { value: 'manual_each', label: '逐张手动审查', hint: '在凭证抽屉内对单张凭证点击「合规审查」。' },
  {
    value: 'threshold_badge',
    label: '超阈值提示后手动审查',
    hint: '先按金额阈值标记「建议审查」，再对标记凭证手动触发 LLM 审查。',
  },
  { value: 'threshold_auto', label: '超阈值自动审查', hint: '对超过阈值的凭证自动批量运行 LLM 合规审查。' },
  { value: 'random_sample', label: '随机抽样审查', hint: '按抽样比例随机抽取凭证并自动运行合规审查。' },
]

type ReviewPhase = 'dimensions' | 'vouchers'

const DAY_BOOK_SOURCE_TYPES = new Set(['ledger_day_book', 'audit_day_book'])

export function Step4ReviewEntries() {
  useTrackBookkeepingStep('step4_review')
  useTrackBookkeepingStep('step4_review')
  const navigate = useNavigate()
  const location = useLocation()
  const stepPath = (step: number) =>
    location.pathname.startsWith('/ledger/vouchers/step/')
      ? `/ledger/vouchers/step/${step}`
      : `/accounting/step/${step}`
  const [searchParams, setSearchParams] = useSearchParams()
  const { currentLedgerId } = useAuthStore()
  const jobId = Number(searchParams.get('jobId') || 0)
  const inputMode = searchParams.get('inputMode') || ''
  const isDayBookImport = inputMode === 'day_book_import'
  const reviewPhase: ReviewPhase =
    searchParams.get('reviewPhase') === 'vouchers' ? 'vouchers' : 'dimensions'
  const currentStep = 3

  const [vouchers, setVouchers] = useState<PreviewVoucherSummary[]>([])
  const [voucherTotal, setVoucherTotal] = useState(0)
  const [reviewStats, setReviewStats] = useState<ReviewStats>(EMPTY_REVIEW_STATS)
  const [reviewFilter, setReviewFilter] = useState<ReviewFilter>('pending')
  const [searchText, setSearchText] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [loading, setLoading] = useState(false)
  const [batchLoading, setBatchLoading] = useState(false)
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const [batchStatus, setBatchStatus] = useState('verified')
  const [confirmed, setConfirmed] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [activeVoucher, setActiveVoucher] = useState<PreviewVoucherSummary | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [complianceMode, setComplianceMode] = useState<Step4ComplianceMode>('manual_each')
  const [amountThreshold, setAmountThreshold] = useState(100000)
  const [sampleRate, setSampleRate] = useState(0.1)
  const [complianceRunning, setComplianceRunning] = useState(false)
  const [vouchersBootstrapping, setVouchersBootstrapping] = useState(false)
  const [importJob, setImportJob] = useState<ImportJob | null>(null)
  const voucherLoadSeq = useRef(0)

  const setReviewPhase = (phase: ReviewPhase) => {
    const next = new URLSearchParams(searchParams)
    next.set('reviewPhase', phase)
    if (isDayBookImport) {
      next.set('inputMode', 'day_book_import')
    }
    setSearchParams(next)
  }

  const applyReviewStats = (stats?: ReviewStats) => {
    if (stats) {
      setReviewStats(stats)
      return
    }
    setReviewStats(EMPTY_REVIEW_STATS)
  }

  const loadVouchers = async (nextPage = page, nextPageSize = pageSize, filter = reviewFilter) => {
    if (!jobId) return
    const seq = ++voucherLoadSeq.current
    setLoading(true)
    if (nextPage === 1) {
      setVouchersBootstrapping(true)
    }
    try {
      const result = await api.listPreviewVouchers(jobId, {
        reviewFilter: filter,
        search: searchText.trim() || undefined,
        limit: nextPageSize,
        offset: (nextPage - 1) * nextPageSize,
      })
      if (seq !== voucherLoadSeq.current) return
      setVouchers(result.items)
      setVoucherTotal(result.total)
      applyReviewStats(result.review_stats)
    } catch (error) {
      if (seq !== voucherLoadSeq.current) return
      console.error('获取凭证列表失败', error)
      message.error('获取凭证列表失败')
    } finally {
      if (seq === voucherLoadSeq.current) {
        setLoading(false)
        setVouchersBootstrapping(false)
      }
    }
  }

  useEffect(() => {
    if (reviewPhase !== 'vouchers') return
    void loadVouchers(1, pageSize, reviewFilter)
    setPage(1)
  }, [jobId, reviewFilter, reviewPhase])

  const refreshAllSilent = async (nextPage = page, nextPageSize = pageSize, filter = reviewFilter) => {
    if (!jobId) return
    const seq = ++voucherLoadSeq.current
    try {
      const result = await api.listPreviewVouchers(jobId, {
        reviewFilter: filter,
        search: searchText.trim() || undefined,
        limit: nextPageSize,
        offset: (nextPage - 1) * nextPageSize,
      })
      if (seq !== voucherLoadSeq.current) return
      setVouchers(result.items)
      setVoucherTotal(result.total)
      applyReviewStats(result.review_stats)
    } catch (error) {
      if (seq !== voucherLoadSeq.current) return
      console.error('刷新凭证列表失败', error)
    }
  }

  const handleVoucherReviewStatusChanged = useCallback(
    (groupKey: string, reviewStatus: string) => {
      setActiveVoucher((prev) =>
        prev && prev.group_key === groupKey ? { ...prev, review_status: reviewStatus } : prev,
      )
      if (reviewFilter === 'pending' && reviewStatus === 'verified') {
        setVouchers((prev) => prev.filter((item) => item.group_key !== groupKey))
        setVoucherTotal((total) => Math.max(0, total - 1))
        setSelectedRowKeys((keys) => keys.filter((key) => key !== groupKey))
      } else if (reviewFilter === 'verified' && reviewStatus === 'draft') {
        setVouchers((prev) => prev.filter((item) => item.group_key !== groupKey))
        setVoucherTotal((total) => Math.max(0, total - 1))
      } else {
        setVouchers((prev) =>
          prev.map((item) =>
            item.group_key === groupKey ? { ...item, review_status: reviewStatus } : item,
          ),
        )
      }
      void api
        .getPreviewVoucherReviewStats(jobId)
        .then((stats) => applyReviewStats(stats))
        .catch(() => undefined)
    },
    [jobId, reviewFilter],
  )

  const refreshAll = async () => {
    await loadVouchers(page, pageSize, reviewFilter)
  }

  useEffect(() => {
    if (!jobId || searchParams.get('inputMode')) return
    void api.getImportJob(jobId).then((job) => {
      if (!DAY_BOOK_SOURCE_TYPES.has(job.source_type)) return
      const next = new URLSearchParams(searchParams)
      next.set('inputMode', 'day_book_import')
      setSearchParams(next, { replace: true })
    }).catch(() => undefined)
  }, [jobId, searchParams, setSearchParams])

  useEffect(() => {
    if (!isDayBookImport || !jobId || searchParams.get('reviewPhase')) return
    const next = new URLSearchParams(searchParams)
    next.set('reviewPhase', 'dimensions')
    next.set('inputMode', 'day_book_import')
    setSearchParams(next, { replace: true })
  }, [isDayBookImport, jobId, searchParams, setSearchParams])

  useEffect(() => {
    if (complianceMode === 'skip' && (
      reviewFilter === 'spot_check'
      || reviewFilter === 'compliance_pending'
      || reviewFilter === 'compliance_reviewed'
    )) {
      setReviewFilter('pending')
      setPage(1)
      void loadVouchers(1, pageSize, 'pending')
    }
  }, [complianceMode])

  useEffect(() => {
    if (!jobId) {
      setImportJob(null)
      return
    }
    void api
      .getImportJob(jobId)
      .then((job) => {
        setImportJob(job)
        if (job.status === 'completed' && currentLedgerId) {
          clearLedgerImportResume(currentLedgerId)
        }
      })
      .catch(() => setImportJob(null))
  }, [jobId, currentLedgerId])

  useEffect(() => {
    if (!jobId || !currentLedgerId || importJob?.status === 'completed') return
    persistImportJobContext(jobId, `${location.pathname}${location.search}`)
    persistLedgerImportResume({
      ledgerId: currentLedgerId,
      jobId,
      step: 4,
      reviewPhase,
      inputMode: isDayBookImport ? 'day_book_import' : inputMode || undefined,
      structuredKind: searchParams.get('structuredKind') || undefined,
      periodMappingMode: searchParams.get('periodMappingMode') || undefined,
    })
  }, [
    jobId,
    currentLedgerId,
    reviewPhase,
    isDayBookImport,
    inputMode,
    location.pathname,
    location.search,
    searchParams,
    importJob?.status,
  ])

  const showDimensionPhase = isDayBookImport
  const activePhase: ReviewPhase = showDimensionPhase ? reviewPhase : 'vouchers'

  useEffect(() => {
    if (!jobId || activePhase !== 'dimensions') return
    void api
      .getPreviewVoucherReviewStats(jobId)
      .then((stats) => applyReviewStats(stats))
      .catch(() => undefined)
  }, [jobId, activePhase])

  const openVoucherDrawer = (voucher: PreviewVoucherSummary) => {
    setActiveVoucher(voucher)
    setDrawerOpen(true)
  }

  const handleTableChange = (pagination: TablePaginationConfig) => {
    const nextPage = pagination.current || 1
    const nextPageSize = pagination.pageSize || pageSize
    setPage(nextPage)
    setPageSize(nextPageSize)
    setSelectedRowKeys([])
    void loadVouchers(nextPage, nextPageSize, reviewFilter)
  }

  const batchVerify = async () => {
    const anchorIds = selectedRowKeys
      .map((key) => vouchers.find((item) => item.group_key === key)?.anchor_entry_id)
      .filter((id): id is number => Boolean(id))
    if (anchorIds.length === 0 || !jobId) return
    setBatchLoading(true)
    try {
      const result = await api.batchReviewPreviewEntries(jobId, anchorIds, batchStatus)
      await refreshAll()
      setSelectedRowKeys([])
      message.success(`已批量更新 ${result.updated_vouchers} 张凭证`)
    } catch (error) {
      message.error(error instanceof Error ? error.message : '批量复核失败')
    } finally {
      setBatchLoading(false)
    }
  }

  const handleMarkThreshold = async () => {
    if (!jobId) return
    setComplianceRunning(true)
    try {
      const result = await api.complianceSpotCheck(jobId, amountThreshold)
      message.success(`已标记 ${result.flagged_count} 条超阈值分录，涉及 ${result.flagged_voucher_nos.length} 张凭证`)
      setReviewFilter('compliance_pending')
      setPage(1)
      setSelectedRowKeys([])
      await loadVouchers(1, pageSize, 'compliance_pending')
    } catch (error) {
      message.error(error instanceof Error ? error.message : '超阈值标记失败')
    } finally {
      setComplianceRunning(false)
    }
  }

  const handleThresholdAutoReview = async () => {
    if (!jobId) return
    setComplianceRunning(true)
    try {
      const mark = await api.complianceSpotCheck(jobId, amountThreshold)
      const review = await api.complianceReview(jobId, 'spot', { useLlm: true })
      message.success(
        `超阈值标记 ${mark.flagged_count} 条，已完成 ${review.reviewed_vouchers} 张凭证合规审查`,
      )
      await refreshAll()
    } catch (error) {
      message.error(error instanceof Error ? error.message : '超阈值合规审查失败')
    } finally {
      setComplianceRunning(false)
    }
  }

  const handleRandomSampleReview = async () => {
    if (!jobId) return
    setComplianceRunning(true)
    try {
      const mark = await api.complianceRandomSample(jobId, { sampleRate })
      const review = await api.complianceReview(jobId, 'random', { useLlm: true })
      message.success(
        `随机抽取 ${mark.sampled_vouchers} 张凭证，已完成 ${review.reviewed_vouchers} 张合规审查`,
      )
      await refreshAll()
    } catch (error) {
      message.error(error instanceof Error ? error.message : '随机抽样合规审查失败')
    } finally {
      setComplianceRunning(false)
    }
  }

  const selectedModeHint = COMPLIANCE_MODE_OPTIONS.find((item) => item.value === complianceMode)?.hint

  const reviewTabItems = useMemo(() => {
    const items = [
      {
        key: 'pending',
        label: `待复核 (${Math.max(reviewStats.total_vouchers - reviewStats.verified_vouchers, 0)})`,
      },
      { key: 'verified', label: `已复核 (${reviewStats.verified_vouchers})` },
      {
        key: 'unbalanced',
        label: `借贷不平衡 (${reviewStats.unbalanced_voucher_nos.length})`,
      },
    ]
    if (complianceMode !== 'skip') {
      items.push(
        {
          key: 'compliance_pending',
          label: `待合规审查 (${reviewStats.compliance_pending_vouchers ?? 0})`,
        },
        {
          key: 'spot_check',
          label: `建议审查 (${reviewStats.spot_check_vouchers ?? 0})`,
        },
        {
          key: 'compliance_reviewed',
          label: `已合规审查 (${reviewStats.compliance_reviewed_vouchers ?? 0})`,
        },
      )
    }
    items.push({ key: 'all', label: `全部 (${reviewStats.total_vouchers})` })
    return items
  }, [complianceMode, reviewStats])

  const reviewAll = () => {
    if (!jobId) return
    Modal.confirm({
      title: '确认全量更新复核状态？',
      content: `将把当前任务全部 ${reviewStats.total_vouchers} 张凭证标记为「${REVIEW_STATUS_LABEL[batchStatus] || batchStatus}」。`,
      okText: '确认更新全部',
      cancelText: '取消',
      onOk: async () => {
        setLoading(true)
        try {
          const result = await api.reviewAllPreviewEntries(jobId, batchStatus)
          await refreshAll()
          setSelectedRowKeys([])
          message.success(`已全量更新 ${result.updated_vouchers} 张凭证`)
        } catch (error) {
          message.error(error instanceof Error ? error.message : '全量复核失败')
        } finally {
          setLoading(false)
        }
      },
    })
  }

  const columns: ColumnsType<PreviewVoucherSummary> = [
    {
      title: '凭证号',
      dataIndex: 'voucher_no',
      key: 'voucher_no',
      width: 120,
      fixed: 'left',
      render: (val: string | null) => val || '-',
    },
    {
      title: '日期',
      dataIndex: 'voucher_date',
      key: 'voucher_date',
      width: 112,
      render: (val: string | null) => val || '-',
    },
    {
      title: '摘要预览',
      dataIndex: 'summary_preview',
      key: 'summary_preview',
      width: 200,
      ellipsis: { showTitle: false },
      render: (val: string | null) => (
        <Tooltip title={val || undefined}>
          <span>{val || '-'}</span>
        </Tooltip>
      ),
    },
    {
      title: '行数',
      dataIndex: 'line_count',
      key: 'line_count',
      width: 64,
      align: 'center',
    },
    {
      title: '借方合计',
      dataIndex: 'debit_total',
      key: 'debit_total',
      width: 128,
      align: 'right',
      render: (val: number) => formatAmount(val),
    },
    {
      title: '贷方合计',
      dataIndex: 'credit_total',
      key: 'credit_total',
      width: 128,
      align: 'right',
      render: (val: number) => formatAmount(val),
    },
    {
      title: '平衡',
      key: 'is_balanced',
      width: 72,
      align: 'center',
      render: (_: unknown, record) =>
        record.is_balanced ? <Tag color="green">是</Tag> : <Tag color="red">否</Tag>,
    },
    {
      title: '签章',
      key: 'signature',
      width: 220,
      render: (_: unknown, record) => (
        <VoucherSignatureStrip
          compact
          signature={{
            source_preparer_name: record.source_preparer_name,
            cross_reviewed_by_name: record.cross_reviewed_by_name,
            cross_reviewed_at: record.cross_reviewed_at,
          }}
        />
      ),
    },
    {
      title: '复核状态',
      dataIndex: 'review_status',
      key: 'review_status',
      width: 96,
      render: (status: string) => (
        <Tag color={status === 'verified' ? 'green' : status === 'partial' ? 'orange' : 'default'}>
          {REVIEW_STATUS_LABEL[status] || status}
        </Tag>
      ),
    },
    {
      title: '合规状态',
      key: 'compliance',
      width: 240,
      render: (_: unknown, record) => (
        <Space size={4} direction="vertical" style={{ width: '100%' }}>
          {record.spot_check_flag && complianceMode !== 'skip' && (
            <Tag color="orange">建议审查</Tag>
          )}
          {record.compliance_hint ? (
            <Tooltip title={record.compliance_hint}>
              <Tag
                color={COMPLIANCE_SEVERITY_COLOR[record.compliance_severity] || 'default'}
                style={{ maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
              >
                {record.compliance_hint}
              </Tag>
            </Tooltip>
          ) : (
            !record.spot_check_flag && <Text type="secondary">未审查</Text>
          )}
        </Space>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 108,
      fixed: 'right',
      render: (_: unknown, record) => (
        <Button type="link" icon={<EyeOutlined />} onClick={() => openVoucherDrawer(record)}>
          查看复核
        </Button>
      ),
    },
  ]

  const allVerified =
    reviewStats.total_vouchers > 0 &&
    reviewStats.verified_vouchers === reviewStats.total_vouchers &&
    reviewStats.partial_vouchers === 0 &&
    reviewStats.unbalanced_voucher_nos.length === 0

  const goPrev = () => {
    if (activePhase === 'vouchers' && showDimensionPhase) {
      setReviewPhase('dimensions')
      return
    }
    const params = new URLSearchParams(searchParams)
    params.delete('reviewPhase')
    const qs = params.toString()
    navigate(qs ? `${stepPath(2)}?${qs}` : stepPath(2))
  }

  const goNext = () => {
    if (!jobId) return
    if (activePhase === 'dimensions') {
      setReviewPhase('vouchers')
      return
    }
    if (!allVerified) {
      message.warning('请先完成全部凭证复核（可使用「全量标记全部凭证」）')
      return
    }
    const params = new URLSearchParams(searchParams)
    params.delete('reviewPhase')
    navigate(`${stepPath(5)}?${params.toString()}`)
  }

  const handleConfirmImport = async () => {
    if (!jobId) return
    setConfirming(true)
    try {
      const result = await api.confirmImport(jobId)
      setConfirmed(true)
      if (currentLedgerId) clearLedgerImportResume(currentLedgerId)
      message.success(`已确认入账 ${result.entries_created} 条分录（未审核），请前往凭证查询页审核`)
    } catch (error) {
      message.error(error instanceof Error ? error.message : '确认入账失败')
    } finally {
      setConfirming(false)
    }
  }

  const handleCancelImport = async () => {
    if (!jobId) return
    Modal.confirm({
      title: '取消导入？',
      content: '将丢弃当前草稿分录，返回上传步骤。',
      onOk: async () => {
        await api.cancelImport(jobId)
        navigate(stepPath(2))
      },
    })
  }

  const vouchersNextBlocked =
    activePhase === 'vouchers' && (reviewStats.total_vouchers === 0 || !allVerified)

  const vouchersNextHint =
    reviewStats.total_vouchers === 0
      ? '尚未生成可复核凭证'
      : !allVerified
        ? `尚有 ${reviewStats.total_vouchers - reviewStats.verified_vouchers} 张凭证未复核；大批量可先点「全量标记全部凭证」`
        : ''

  const renderNextButton = (label: string) => {
    const button = (
      <Button
        type="primary"
        onClick={goNext}
        disabled={!jobId || vouchersNextBlocked}
        loading={activePhase === 'vouchers' && vouchersBootstrapping}
      >
        {label}
      </Button>
    )
    if (!vouchersNextBlocked) return button
    return (
      <Tooltip title={activePhase === 'vouchers' ? vouchersNextHint : undefined}>
        <span>{button}</span>
      </Tooltip>
    )
  }

  return (
    <div style={{ padding: '24px 32px', width: '100%', maxWidth: '1680px', margin: '0 auto', boxSizing: 'border-box' }}>
      <Steps
        current={currentStep}
        items={[
          { title: '选择类型' },
          { title: '导入资料' },
          { title: '生成草稿' },
          { title: '复核调整' },
          { title: '确认入账与导出' },
        ]}
        style={{ marginBottom: '32px' }}
      />

      <FlowNav
        prev={stepPath(2)}
        onNext={goNext}
        nextLabel={activePhase === 'dimensions' ? '进入凭证复核' : '进入确认入账与导出'}
        nextDisabled={
          !jobId ||
          importJob?.status === 'completed' ||
          (activePhase === 'vouchers' &&
            (reviewStats.total_vouchers === 0 || !allVerified))
        }
        style={{ marginBottom: '16px' }}
      />

      {importJob?.status === 'completed' && (
        <Alert
          type="success"
          showIcon
          style={{ marginBottom: 16 }}
          title={`导入任务 #${importJob.id} 已完成确认入账`}
          description={
            <Space wrap>
              <span>
                共 {importJob.entry_count.toLocaleString()} 条分录已写入正式账簿，staging 草稿已清空，无需再复核。
              </span>
              <Button
                type="primary"
                size="small"
                onClick={() =>
                  navigate(
                    `${stepPath(5)}?jobId=${importJob.id}&inputMode=${isDayBookImport ? 'day_book_import' : inputMode || 'day_book_import'}`,
                  )
                }
              >
                前往 Step5 导出
              </Button>
              <Button size="small" onClick={() => navigate(stepPath(2))}>
                开始新导入
              </Button>
            </Space>
          }
        />
      )}

      {importJob?.status !== 'completed' && (
        <>
      {showDimensionPhase && (
        <Tabs
          activeKey={activePhase}
          onChange={(key) => setReviewPhase(key as ReviewPhase)}
          style={{ marginBottom: 16 }}
          items={[
            { key: 'dimensions', label: '① 维度与映射复核' },
            {
              key: 'vouchers',
              label: `② 凭证复核${
                reviewStats.total_vouchers > 0
                  ? ` (${reviewStats.verified_vouchers}/${reviewStats.total_vouchers})`
                  : ''
              }`,
            },
          ]}
        />
      )}

      {activePhase === 'dimensions' && jobId > 0 && (
        <Step4DimensionReviewPanel jobId={jobId} onContinue={() => setReviewPhase('vouchers')} />
      )}

      {activePhase === 'vouchers' && (
        <Spin spinning={vouchersBootstrapping} tip="正在加载凭证列表，大批量导入可能需要数秒…">
        <>
      <Space style={{ marginBottom: '16px', width: '100%', justifyContent: 'space-between' }}>
        <Title level={4} style={{ margin: 0 }}>
          按凭证复核（草稿入账前）
        </Title>
        <Tag color={allVerified ? 'green' : 'blue'}>
          已复核 {reviewStats.verified_vouchers}/{reviewStats.total_vouchers || 0} 张凭证
          {reviewStats.total_lines > 0 ? ` · ${reviewStats.total_lines} 行` : ''}
        </Tag>
      </Space>

      {reviewStats.total_vouchers >= 500 && !allVerified && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message={`本批共 ${reviewStats.total_vouchers} 张凭证，建议先使用「全量标记全部凭证」再抽样打开几张核对`}
        />
      )}

      {!jobId && <ImportResumeBanner ledgerId={currentLedgerId} variant="step4" />}

      <Card loading={loading} style={{ marginBottom: 16 }}>
        <Title level={5} style={{ marginTop: 0 }}>
          合规审查策略
        </Title>
        <Radio.Group
          value={complianceMode}
          onChange={(event) => setComplianceMode(event.target.value as Step4ComplianceMode)}
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
            gap: 8,
            width: '100%',
          }}
        >
          {COMPLIANCE_MODE_OPTIONS.map((option) => (
            <Radio key={option.value} value={option.value}>
              {option.label}
            </Radio>
          ))}
        </Radio.Group>
        {selectedModeHint && (
          <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
            {selectedModeHint}
          </Text>
        )}
        {(complianceMode === 'threshold_badge' || complianceMode === 'threshold_auto') && (
          <Space wrap style={{ marginTop: 12 }}>
            <span>金额阈值（元）</span>
            <InputNumber min={1} value={amountThreshold} onChange={(v) => setAmountThreshold(v ?? 100000)} />
            {complianceMode === 'threshold_badge' && (
              <Button loading={complianceRunning} onClick={() => void handleMarkThreshold()}>
                标记超阈值凭证
              </Button>
            )}
            {complianceMode === 'threshold_auto' && (
              <Button type="primary" loading={complianceRunning} onClick={() => void handleThresholdAutoReview()}>
                执行超阈值合规审查
              </Button>
            )}
          </Space>
        )}
        {complianceMode === 'random_sample' && (
          <Space wrap style={{ marginTop: 12 }}>
            <span>抽样比例</span>
            <InputNumber
              min={0.01}
              max={1}
              step={0.05}
              value={sampleRate}
              formatter={(v) => `${Math.round(Number(v || 0) * 100)}%`}
              parser={(v) => Number(String(v).replace('%', '')) / 100}
              onChange={(v) => setSampleRate(v ?? 0.1)}
            />
            <Button type="primary" loading={complianceRunning} onClick={() => void handleRandomSampleReview()}>
              执行随机抽样审查
            </Button>
          </Space>
        )}
      </Card>

      <Card loading={loading}>
        <Alert
          title="逐张凭证复核"
          description={
            complianceMode === 'skip'
              ? '请逐张查看分录并勾选复核。制单人来自序时簿解析；勾选复核后系统将记名复核人；Step5 确认入账时记名审核人。'
              : complianceMode === 'manual_each'
                ? '请逐张打开凭证复核，核对签章栏（制单/复核/审核）。需要时在抽屉内点击「合规审查」。'
                : '请先完成合规策略操作，再逐张复核。签章：制单人（序时簿）→ 复核人（本步记名）→ 审核人（Step5 记名）。'
          }
          type="info"
          showIcon
          style={{ marginBottom: '16px' }}
        />

        <Tabs
          activeKey={reviewFilter}
          onChange={(key) => {
            setReviewFilter(key as ReviewFilter)
            setPage(1)
            setSelectedRowKeys([])
            void loadVouchers(1, pageSize, key as ReviewFilter)
          }}
          items={reviewTabItems}
          style={{ marginBottom: 16 }}
          type="card"
        />

        {complianceMode === 'threshold_badge' && (reviewStats.compliance_pending_vouchers ?? 0) > 0 && (
          <Alert
            type="warning"
            showIcon
            style={{ marginBottom: 16 }}
            message={`有 ${reviewStats.compliance_pending_vouchers} 张凭证已标记「建议审查」但尚未 LLM 合规审查`}
            description='请切换到「待合规审查」筛选，逐张打开抽屉点击「审查本张凭证」。'
            action={
              <Button
                size="small"
                type="primary"
                onClick={() => {
                  setReviewFilter('compliance_pending')
                  setPage(1)
                  void loadVouchers(1, pageSize, 'compliance_pending')
                }}
              >
                查看待合规审查
              </Button>
            }
          />
        )}

        <Space wrap style={{ marginBottom: 16, width: '100%' }}>
          <Input.Search
            allowClear
            placeholder="按凭证号/摘要/科目搜索"
            style={{ width: 280 }}
            onSearch={() => void loadVouchers(1, pageSize, reviewFilter)}
            onChange={(event) => setSearchText(event.target.value)}
          />
          {complianceMode !== 'skip' && (
            <Select
              value={reviewFilter}
              style={{ minWidth: 200 }}
              onChange={(value: ReviewFilter) => {
                setReviewFilter(value)
                setPage(1)
                setSelectedRowKeys([])
                void loadVouchers(1, pageSize, value)
              }}
              options={[
                { value: 'pending', label: '待复核' },
                { value: 'verified', label: '已复核' },
                { value: 'unbalanced', label: '借贷不平衡' },
                { value: 'compliance_pending', label: '待合规审查（建议审查未审）' },
                { value: 'spot_check', label: '全部建议审查' },
                { value: 'compliance_reviewed', label: '已合规审查' },
                { value: 'all', label: '全部凭证' },
              ]}
            />
          )}
          <Button type="primary" loading={confirming} disabled={!jobId || !allVerified || confirmed} onClick={() => void handleConfirmImport()}>
            {confirmed ? '已确认入账' : '确认入账'}
          </Button>
          <Button danger onClick={() => void handleCancelImport()} disabled={!jobId || confirmed}>
            取消导入
          </Button>
          <Button type="primary" loading={batchLoading} onClick={() => void batchVerify()} disabled={selectedRowKeys.length === 0}>
            批量标记选中 ({selectedRowKeys.length} 张)
          </Button>
          <Button onClick={reviewAll} disabled={!jobId || reviewStats.total_vouchers === 0}>
            全量标记全部凭证
          </Button>
          <Select value={batchStatus} onChange={setBatchStatus} style={{ width: 150 }}>
            <Select.Option value="draft">待复核</Select.Option>
            <Select.Option value="verified">已复核</Select.Option>
          </Select>
        </Space>

        <Table
          rowSelection={{
            selectedRowKeys,
            onChange: setSelectedRowKeys,
          }}
          columns={columns}
          dataSource={vouchers}
          rowKey="group_key"
          pagination={{
            current: page,
            pageSize,
            total: voucherTotal,
            showSizeChanger: true,
            pageSizeOptions: ['10', '20', '50', '100'],
            showTotal: (total, range) => `第 ${range[0]}-${range[1]} 张 / 共 ${total} 张凭证`,
          }}
          onChange={handleTableChange}
          scroll={{ x: 1480 }}
          size="middle"
          onRow={(record) => ({
            onDoubleClick: () => openVoucherDrawer(record),
          })}
        />
      </Card>

      <StagingVoucherReviewDrawer
        open={drawerOpen}
        jobId={jobId}
        voucher={activeVoucher}
        voucherList={vouchers}
        complianceMode={complianceMode}
        onClose={() => {
          setDrawerOpen(false)
          setActiveVoucher(null)
        }}
        onReviewStatusChanged={handleVoucherReviewStatusChanged}
        onChanged={() => void refreshAllSilent()}
        onNavigate={(next) => setActiveVoucher(next)}
      />
        </>
        </Spin>
      )}

      <div style={{ marginTop: '24px', display: 'flex', gap: '12px' }}>
        <Button onClick={goPrev}>
          {activePhase === 'vouchers' && showDimensionPhase ? '返回维度复核' : '上一步'}
        </Button>
        {renderNextButton(
          activePhase === 'dimensions' ? '进入凭证复核' : '进入确认入账与导出',
        )}
      </div>
        </>
      )}

      {importJob?.status === 'completed' && (
        <div style={{ marginTop: '24px', display: 'flex', gap: '12px' }}>
          <Button onClick={() => navigate(stepPath(2))}>开始新导入</Button>
          <Button
            type="primary"
            onClick={() =>
              navigate(
                `${stepPath(5)}?jobId=${importJob.id}&inputMode=${isDayBookImport ? 'day_book_import' : inputMode || 'day_book_import'}`,
              )
            }
          >
            前往 Step5 导出
          </Button>
        </div>
      )}
    </div>
  )
}
