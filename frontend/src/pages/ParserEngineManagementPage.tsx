import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Col,
  Collapse,
  Descriptions,
  Divider,
  Empty,
  InputNumber,
  List,
  Modal,
  Progress,
  Row,
  Select,
  Space,
  Spin,
  Statistic,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import {
  BarChartOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  CodeOutlined,
  DatabaseOutlined,
  ExclamationCircleOutlined,
  FileSearchOutlined,
  FileTextOutlined,
  ReloadOutlined,
  StopOutlined,
  ThunderboltOutlined,
  UploadOutlined,
} from '@ant-design/icons'
import { api, type Project } from '../api/client'
import { useAuthStore } from '../stores/authStore'

const { Title, Text } = Typography

type EngineDiagnosis = {
  consistency_rate?: number
  consistent_fields?: Array<{ field: string; value: unknown }>
  conflict_fields?: Array<{ field: string; rule_value: unknown; llm_value: unknown }>
  rule_only_fields?: Array<{ field: string; rule_value: unknown }>
  llm_only_fields?: Array<{ field: string; llm_value: unknown }>
  review_required?: boolean
  review_reason?: string
  confidence_gap?: number
}

type ParseApiResult = {
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
}

type ParseTaskStatus = 'queued' | 'sheet_pending' | 'parsing' | 'success' | 'failed' | 'cancelled' | 'timeout'

type ParseTask = {
  id: string
  draftId: string
  file: File
  fileName: string
  sheetName?: string
  selectedSheetNames?: string[]
  status: ParseTaskStatus
  progress: number
  stage: string
  pollCount: number
  timeoutSeconds: number
  elapsedMs: number
  startedAt?: number
  finishedAt?: number
  projectId: number | null
  projectName: string | null
  ledgerId: number | null
  ledgerName: string | null
  targetModule: string
  registerPath: string
  result?: ParseApiResult
  errorMessage?: string
  stageTimings: Record<string, number>
}

type ExcelSheetInfo = {
  name: string
  rows: number
  columns: string[]
  preview: Record<string, unknown>[]
}

const DOCUMENT_TYPE_LABELS: Record<string, string> = {
  invoice: '发票',
  bank_statement: '银行流水',
  contract: '合同协议',
  inventory_receipt: '入库单',
  salary_table: '工资表',
  expense_document: '费用单据',
  receipt: '收据凭证',
  accounting_entry: '会计分录',
  general: '通用文档',
  unknown: '未知',
}

const FILE_FORMAT_LABELS: Record<string, string> = {
  pdf_text: 'PDF(可提取文本)',
  pdf_image: 'PDF(图片)',
  excel: 'Excel',
  csv: 'CSV',
  xml: 'XML',
  ofd: 'OFD',
  image: '图片',
  word: 'Word',
  text: '文本',
  unknown: '未知',
}

const MODULE_OPTIONS = [
  { value: 'source_archive', label: '源文件归档', path: '文件中心 / 源文件归档' },
  { value: 'contract_register', label: '合同台账', path: '合同管理 / 合同台账' },
  { value: 'invoice_register', label: '发票台账', path: '发票管理 / 发票台账' },
  { value: 'bank_register', label: '银行流水台账', path: '资金管理 / 银行流水台账' },
  { value: 'inventory_register', label: '进销存台账', path: '进销存 / 单据台账' },
  { value: 'audit_evidence', label: '审计证据库', path: '审计 / 审计证据库' },
]

function getDefaultModule(documentType?: string) {
  if (documentType === 'contract') return 'contract_register'
  if (documentType === 'invoice') return 'invoice_register'
  if (documentType === 'bank_statement') return 'bank_register'
  if (documentType === 'inventory_receipt') return 'inventory_register'
  return 'source_archive'
}

function getModulePath(moduleKey: string) {
  return MODULE_OPTIONS.find((item) => item.value === moduleKey)?.path || '文件中心 / 源文件归档'
}

function getEngineDiagnosis(result?: ParseApiResult): EngineDiagnosis | null {
  const diagnosis = result?.engine_comparison?.diagnosis
  if (!diagnosis || typeof diagnosis !== 'object') return null
  return diagnosis as EngineDiagnosis
}

function formatPercent(value?: number) {
  return `${((value || 0) * 100).toFixed(1)}%`
}

function renderValue(value: unknown) {
  return value === null || value === undefined || value === '' ? '空' : String(value)
}

function buildDraftId(ledgerId: number | null, projectId: number | null, index: number) {
  const timestamp = new Date().toISOString().replace(/[-:TZ.]/g, '').slice(0, 14)
  const ledgerPart = ledgerId ? `L${ledgerId}` : 'LNA'
  const projectPart = projectId ? `P${projectId}` : 'PNA'
  return `DRAFT-${ledgerPart}-${projectPart}-${timestamp}-${String(index + 1).padStart(3, '0')}`
}

function isExcelFile(fileName: string) {
  return /\.(xlsx|xls)$/i.test(fileName)
}

export function ParserEngineManagementPage() {
  const { currentLedgerId, userLedgers, authContext } = useAuthStore()
  const currentLedger = userLedgers.find((ledger) => ledger.id === currentLedgerId) || null
  const defaultProject = authContext?.projects?.[0] as Project | undefined

  const [status, setStatus] = useState<{
    status: string
    llm_multi_engine_enabled: boolean
    llm_enable_parallel_parsing: boolean
    llm_max_concurrent_models: number
    llm_preferred_model: string
    llm_comparison_strategy: string
    supported_formats: string[]
    supported_document_types: string[]
  } | null>(null)

  const [stats, setStats] = useState<{
    total_parses: number
    successful_parses: number
    failed_parses: number
    success_rate_percent: number
    stage_stats: Record<string, { count: number; avg_ms: number; max_ms: number; min_ms: number }>
    format_stats: Record<string, { count: number; avg_ms: number; max_ms: number; min_ms: number }>
    doctype_stats: Record<string, { count: number; avg_ms: number; max_ms: number; min_ms: number }>
    error_stats: Record<string, number>
  } | null>(null)

  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [parseTasks, setParseTasks] = useState<ParseTask[]>([])
  const [selectedTaskIds, setSelectedTaskIds] = useState<string[]>([])
  const [excelSheetsVisible, setExcelSheetsVisible] = useState(false)
  const [excelSheets, setExcelSheets] = useState<ExcelSheetInfo[]>([])
  const [selectedSheetNames, setSelectedSheetNames] = useState<string[]>([])
  const [pendingExcelFile, setPendingExcelFile] = useState<File | null>(null)
  const [pendingExcelQueue, setPendingExcelQueue] = useState<File[]>([])
  const [loadingSheets, setLoadingSheets] = useState(false)
  const [timeoutSeconds, setTimeoutSeconds] = useState(90)
  const [targetModule, setTargetModule] = useState('source_archive')
  const [batchModule, setBatchModule] = useState('source_archive')
  const abortControllerRef = useRef<AbortController | null>(null)
  const pollingTimerRef = useRef<number | null>(null)

  const latestResult = useMemo(() => {
    return [...parseTasks].reverse().find((task) => task.result)?.result
  }, [parseTasks])
  const latestDiagnosis = getEngineDiagnosis(latestResult)

  const runningTask = parseTasks.find((task) => task.status === 'parsing')
  const finishedCount = parseTasks.filter((task) => ['success', 'failed', 'cancelled', 'timeout'].includes(task.status)).length
  const successCount = parseTasks.filter((task) => task.status === 'success').length
  const failedCount = parseTasks.filter((task) => ['failed', 'timeout'].includes(task.status)).length
  const totalCount = parseTasks.length
  const batchProgress = totalCount > 0 ? Math.round((finishedCount / totalCount) * 100) : 0

  useEffect(() => {
    fetchData()
    return () => {
      if (pollingTimerRef.current) window.clearInterval(pollingTimerRef.current)
      abortControllerRef.current?.abort()
    }
  }, [])

  const fetchData = async () => {
    setLoading(true)
    try {
      const [engineStatus, performanceStats] = await Promise.all([
        api.getParserEngineStatus(),
        api.getPerformanceStats(),
      ])
      setStatus(engineStatus)
      setStats(performanceStats)
    } catch (error) {
      console.error('获取解析引擎数据失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const refreshStatsSilently = async () => {
    try {
      setStats(await api.getPerformanceStats())
    } catch (error) {
      console.error('刷新统计失败:', error)
    }
  }

  const handleResetStats = async () => {
    try {
      await api.resetPerformanceStats()
      await fetchData()
    } catch (error) {
      console.error('重置统计数据失败:', error)
    }
  }

  const createTask = (file: File, index: number, sheetName?: string): ParseTask => {
    const projectId = defaultProject?.id ?? null
    const ledgerId = currentLedgerId ?? null
    const fileName = sheetName ? `${file.name} / ${sheetName}` : file.name
    return {
      id: `${file.name}-${sheetName || 'all'}-${Date.now()}-${index}`,
      draftId: buildDraftId(ledgerId, projectId, index),
      file,
      fileName,
      sheetName,
      status: 'queued',
      progress: 0,
      stage: '等待解析',
      pollCount: 0,
      timeoutSeconds,
      elapsedMs: 0,
      projectId,
      projectName: defaultProject?.name ?? null,
      ledgerId,
      ledgerName: currentLedger?.name ?? null,
      targetModule,
      registerPath: getModulePath(targetModule),
      stageTimings: {},
    }
  }

  const updateTask = (taskId: string, patch: Partial<ParseTask>) => {
    setParseTasks((rows) => rows.map((task) => task.id === taskId ? { ...task, ...patch } : task))
  }

  const startPollingUi = (taskId: string, startedAt: number, timeoutSec: number) => {
    if (pollingTimerRef.current) window.clearInterval(pollingTimerRef.current)
    pollingTimerRef.current = window.setInterval(() => {
      const elapsedMs = Date.now() - startedAt
      const progress = Math.min(95, Math.max(8, Math.round((elapsedMs / (timeoutSec * 1000)) * 95)))
      updateTask(taskId, {
        elapsedMs,
        progress,
        pollCount: Math.floor(elapsedMs / 2000),
        stage: elapsedMs < 3000 ? '上传文件并初始化解析' : elapsedMs < 10000 ? '识别格式与提取文本' : '调用规则引擎/LLM引擎解析',
      })
    }, 1000)
  }

  const stopPollingUi = () => {
    if (pollingTimerRef.current) {
      window.clearInterval(pollingTimerRef.current)
      pollingTimerRef.current = null
    }
  }

  const parseOneTask = async (task: ParseTask) => {
    const controller = new AbortController()
    abortControllerRef.current = controller
    const startedAt = Date.now()
    updateTask(task.id, { status: 'parsing', progress: 5, stage: '开始解析', startedAt, elapsedMs: 0, pollCount: 0 })
    startPollingUi(task.id, startedAt, task.timeoutSeconds)

    const timeoutHandle = window.setTimeout(() => {
      controller.abort()
      updateTask(task.id, {
        status: 'timeout',
        progress: 100,
        stage: '解析超时，已中止',
        errorMessage: `超过 ${task.timeoutSeconds} 秒未完成`,
        finishedAt: Date.now(),
      })
    }, task.timeoutSeconds * 1000)

    try {
      const result = await api.parseFile(1, task.file, task.sheetName, { signal: controller.signal }) as ParseApiResult
      window.clearTimeout(timeoutHandle)
      stopPollingUi()
      const moduleKey = getDefaultModule(result.document_type)
      const finishedAt = Date.now()
      updateTask(task.id, {
        status: 'success',
        progress: 100,
        stage: '解析完成',
        elapsedMs: finishedAt - startedAt,
        finishedAt,
        result,
        targetModule: moduleKey,
        registerPath: getModulePath(moduleKey),
        stageTimings: result.stage_timings || { 总耗时: result.parse_duration_ms || (finishedAt - startedAt) },
      })
      await refreshStatsSilently()
    } catch (error) {
      window.clearTimeout(timeoutHandle)
      stopPollingUi()
      const isAbort = error instanceof Error && (error.name === 'AbortError' || error.message.includes('aborted'))
      updateTask(task.id, {
        status: isAbort ? 'cancelled' : 'failed',
        progress: 100,
        stage: isAbort ? '用户已中止解析' : '解析失败',
        elapsedMs: Date.now() - startedAt,
        finishedAt: Date.now(),
        errorMessage: isAbort ? '用户已中止解析' : error instanceof Error ? error.message : String(error),
      })
      if (!isAbort) await refreshStatsSilently()
    } finally {
      abortControllerRef.current = null
    }
  }

  const runTasks = async (tasks: ParseTask[]) => {
    if (tasks.length === 0) return
    setUploading(true)
    setSelectedTaskIds(tasks.map((task) => task.id))
    setParseTasks((rows) => [...tasks, ...rows])
    for (const task of tasks) {
      if (abortControllerRef.current?.signal.aborted) break
      await parseOneTask(task)
    }
    setUploading(false)
    message.success('批量解析任务已结束，请查看解析草稿列表')
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    e.target.value = ''
    if (files.length === 0) return

    const excelFiles = files.filter((file) => isExcelFile(file.name))
    const normalFiles = files.filter((file) => !isExcelFile(file.name))
    const normalTasks = normalFiles.map((file, index) => createTask(file, index))

    if (normalTasks.length > 0) {
      runTasks(normalTasks)
    }

    if (excelFiles.length > 0) {
      setPendingExcelQueue(excelFiles.slice(1))
      await openExcelSheetPicker(excelFiles[0])
    }
  }

  const openExcelSheetPicker = async (file: File) => {
    setPendingExcelFile(file)
    setLoadingSheets(true)
    setExcelSheetsVisible(true)
    try {
      const result = await api.listExcelSheets(file)
      if (result.success && result.sheets.length > 0) {
        setExcelSheets(result.sheets)
        setSelectedSheetNames(result.sheets.map((sheet) => sheet.name))
      } else {
        message.warning('未找到工作表')
      }
    } catch (error) {
      message.error(`获取工作表列表失败: ${error instanceof Error ? error.message : String(error)}`)
      setExcelSheetsVisible(false)
    } finally {
      setLoadingSheets(false)
    }
  }

  const handleParseWithSheets = async () => {
    if (!pendingExcelFile || selectedSheetNames.length === 0) return
    const tasks = selectedSheetNames.map((sheetName, index) => createTask(pendingExcelFile, index, sheetName))
    setExcelSheetsVisible(false)
    setPendingExcelFile(null)
    setExcelSheets([])
    setSelectedSheetNames([])
    runTasks(tasks)

    const [nextExcelFile, ...remaining] = pendingExcelQueue
    setPendingExcelQueue(remaining)
    if (nextExcelFile) {
      await openExcelSheetPicker(nextExcelFile)
    }
  }

  const handleCancelParsing = () => {
    abortControllerRef.current?.abort()
    stopPollingUi()
    setUploading(false)
  }

  const handleBatchAssign = () => {
    if (selectedTaskIds.length === 0) {
      message.warning('请先选择需要批量管理的解析草稿')
      return
    }
    const path = getModulePath(batchModule)
    setParseTasks((rows) => rows.map((task) => selectedTaskIds.includes(task.id)
      ? { ...task, targetModule: batchModule, registerPath: path }
      : task,
    ))
    message.success(`已将 ${selectedTaskIds.length} 个解析草稿分配到：${path}`)
  }

  const StageStatsColumns = [
    { title: '阶段', dataIndex: 'stage', key: 'stage' },
    { title: '调用次数', dataIndex: 'count', key: 'count' },
    { title: '平均耗时(ms)', dataIndex: 'avg_ms', key: 'avg_ms' },
    { title: '最大耗时(ms)', dataIndex: 'max_ms', key: 'max_ms' },
    { title: '最小耗时(ms)', dataIndex: 'min_ms', key: 'min_ms' },
  ]

  const FormatStatsColumns = [
    { title: '文件格式', dataIndex: 'format', key: 'format' },
    { title: '解析次数', dataIndex: 'count', key: 'count' },
    { title: '平均耗时(ms)', dataIndex: 'avg_ms', key: 'avg_ms' },
    { title: '最大耗时(ms)', dataIndex: 'max_ms', key: 'max_ms' },
    { title: '最小耗时(ms)', dataIndex: 'min_ms', key: 'min_ms' },
  ]

  const DoctypeStatsColumns = [
    { title: '文档类型', dataIndex: 'doctype', key: 'doctype' },
    { title: '解析次数', dataIndex: 'count', key: 'count' },
    { title: '平均耗时(ms)', dataIndex: 'avg_ms', key: 'avg_ms' },
    { title: '最大耗时(ms)', dataIndex: 'max_ms', key: 'max_ms' },
    { title: '最小耗时(ms)', dataIndex: 'min_ms', key: 'min_ms' },
  ]

  const taskColumns = [
    {
      title: '解析草稿',
      dataIndex: 'draftId',
      key: 'draftId',
      width: 230,
      render: (_: string, row: ParseTask) => (
        <Space direction="vertical" size={0}>
          <Text strong>{row.draftId}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>{row.fileName}</Text>
        </Space>
      ),
    },
    {
      title: '状态与进度',
      dataIndex: 'status',
      key: 'status',
      width: 210,
      render: (_: string, row: ParseTask) => (
        <Space direction="vertical" style={{ width: '100%' }}>
          <Space>
            <Tag color={row.status === 'success' ? 'green' : row.status === 'failed' || row.status === 'timeout' ? 'red' : row.status === 'parsing' ? 'blue' : 'default'}>
              {row.status === 'queued' ? '排队中' : row.status === 'parsing' ? '解析中' : row.status === 'success' ? '成功' : row.status === 'timeout' ? '超时' : row.status === 'cancelled' ? '已中止' : '失败'}
            </Tag>
            <Text type="secondary">轮询 {row.pollCount} 次</Text>
          </Space>
          <Progress percent={row.progress} size="small" />
          <Text type="secondary" style={{ fontSize: 12 }}>{row.stage}</Text>
        </Space>
      ),
    },
    {
      title: '耗时',
      key: 'duration',
      width: 130,
      render: (_: unknown, row: ParseTask) => (
        <Space direction="vertical" size={0}>
          <Text>{Math.round(row.elapsedMs || row.result?.parse_duration_ms || 0)} ms</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>超时 {row.timeoutSeconds}s</Text>
        </Space>
      ),
    },
    {
      title: '项目/账套',
      key: 'context',
      width: 190,
      render: (_: unknown, row: ParseTask) => (
        <Space direction="vertical" size={0}>
          <Text>{row.projectName || '未选择项目'}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>{row.ledgerName || '未选择账套'}</Text>
        </Space>
      ),
    },
    {
      title: '解析结果',
      key: 'result',
      width: 190,
      render: (_: unknown, row: ParseTask) => row.result ? (
        <Space direction="vertical" size={0}>
          <Text>{DOCUMENT_TYPE_LABELS[row.result.document_type] || row.result.document_type}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>置信度 {(row.result.confidence * 100).toFixed(1)}%</Text>
        </Space>
      ) : <Text type="secondary">{row.errorMessage || '-'}</Text>,
    },
    {
      title: '管理路径',
      key: 'registerPath',
      width: 220,
      render: (_: unknown, row: ParseTask) => (
        <Space direction="vertical" size={0}>
          <Tag color="purple">{MODULE_OPTIONS.find((item) => item.value === row.targetModule)?.label}</Tag>
          <Text type="secondary" style={{ fontSize: 12 }}>{row.registerPath}</Text>
        </Space>
      ),
    },
  ]

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '100px' }}>
        <Spin size="large" tip="正在加载解析引擎状态..." />
      </div>
    )
  }

  return (
    <div>
      <Title level={2}>解析引擎管理</Title>
      <Text type="secondary">统一管理文件解析、批量解析草稿、项目账套归属与台账分配路径</Text>

      <Divider />

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="解析引擎状态"
              value={status?.status === 'running' ? '运行中' : '未运行'}
              prefix={status?.status === 'running' ? <CheckCircleOutlined /> : <ExclamationCircleOutlined />}
              valueStyle={{ color: status?.status === 'running' ? '#52c41a' : '#ff4d4f' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="总解析次数" value={stats?.total_parses || 0} prefix={<DatabaseOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="成功次数" value={stats?.successful_parses || 0} prefix={<CheckCircleOutlined />} valueStyle={{ color: '#52c41a' }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="失败次数" value={stats?.failed_parses || 0} prefix={<ExclamationCircleOutlined />} valueStyle={{ color: '#ff4d4f' }} />
          </Card>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic title="成功率" value={stats?.success_rate_percent || 0} suffix="%" prefix={<FileSearchOutlined />} valueStyle={{ color: (stats?.success_rate_percent || 0) >= 80 ? '#52c41a' : '#faad14' }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="本批次草稿" value={totalCount} prefix={<FileTextOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="本批成功" value={successCount} prefix={<CheckCircleOutlined />} valueStyle={{ color: '#52c41a' }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="本批异常" value={failedCount} prefix={<ClockCircleOutlined />} valueStyle={{ color: failedCount > 0 ? '#ff4d4f' : undefined }} />
          </Card>
        </Col>
      </Row>

      <Card title="引擎配置状态" style={{ marginBottom: 24 }}>
        <Row gutter={16}>
          <Col span={8}>
            <Space direction="vertical">
              <Tag color={status?.llm_multi_engine_enabled ? 'green' : 'red'}>
                {status?.llm_multi_engine_enabled ? '多LLM引擎对比 已启用' : '多LLM引擎对比 已禁用'}
              </Tag>
              <Tag color={status?.llm_enable_parallel_parsing ? 'green' : 'red'}>
                {status?.llm_enable_parallel_parsing ? '双引擎并行解析 已启用' : '双引擎并行解析 已禁用'}
              </Tag>
            </Space>
          </Col>
          <Col span={8}>
            <Descriptions column={1} size="small">
              <Descriptions.Item label="当前账套">{currentLedger?.name || '未选择账套'}</Descriptions.Item>
              <Descriptions.Item label="默认项目">{defaultProject?.name || '未选择项目'}</Descriptions.Item>
            </Descriptions>
          </Col>
          <Col span={8}>
            <Space>
              <Button onClick={fetchData} icon={<ReloadOutlined />}>刷新状态</Button>
              <Button onClick={handleResetStats} danger icon={<ReloadOutlined />}>重置统计</Button>
            </Space>
          </Col>
        </Row>
        <Divider />
        <Row gutter={16}>
          <Col span={12}>
            <Text strong>支持的文件格式:</Text><br />
            {status?.supported_formats.map((format) => <Tag key={format}>{FILE_FORMAT_LABELS[format] || format}</Tag>)}
          </Col>
          <Col span={12}>
            <Text strong>支持的文档类型:</Text><br />
            {status?.supported_document_types.map((docType) => <Tag key={docType}>{DOCUMENT_TYPE_LABELS[docType] || docType}</Tag>)}
          </Col>
        </Row>
      </Card>

      <Card title="批量文件解析工作台" style={{ marginBottom: 24 }}>
        <Alert
          message="上传后系统会为每个文件/工作表生成解析草稿ID，并默认关联当前项目和账套。正式入账或正式进入台账仍需要在对应模块复核确认。"
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
        />
        <Row gutter={16} align="middle" style={{ marginBottom: 16 }}>
          <Col span={5}>
            <Text strong>单文件超时秒数</Text>
            <InputNumber min={10} max={600} value={timeoutSeconds} onChange={(value) => setTimeoutSeconds(value || 90)} style={{ width: '100%', marginTop: 8 }} />
          </Col>
          <Col span={7}>
            <Text strong>默认批量管理路径</Text>
            <Select value={targetModule} onChange={setTargetModule} options={MODULE_OPTIONS.map(({ value, label }) => ({ value, label }))} style={{ width: '100%', marginTop: 8 }} />
          </Col>
          <Col span={12}>
            <input
              type="file"
              multiple
              accept=".pdf,.xlsx,.xls,.csv,.xml,.ofd,.jpg,.jpeg,.png,.doc,.docx,.txt"
              onChange={handleFileUpload}
              style={{ display: 'none' }}
              id="parser-file-upload"
            />
            <Space>
              <Button type="primary" icon={<UploadOutlined />} onClick={() => document.getElementById('parser-file-upload')?.click()} loading={uploading}>
                {uploading ? '解析中...' : '多选上传并解析'}
              </Button>
              <Button danger icon={<StopOutlined />} onClick={handleCancelParsing} disabled={!runningTask}>
                中止当前解析
              </Button>
            </Space>
          </Col>
        </Row>
        <Progress percent={batchProgress} status={uploading ? 'active' : undefined} />
        {runningTask && (
          <Alert
            style={{ marginTop: 12 }}
            type="warning"
            showIcon
            message={`当前解析：${runningTask.fileName}`}
            description={`阶段：${runningTask.stage}；轮询次数：${runningTask.pollCount}；已耗时：${Math.round(runningTask.elapsedMs / 1000)}秒；超时设置：${runningTask.timeoutSeconds}秒`}
          />
        )}
      </Card>

      <Card
        title="解析草稿与批量台账分配"
        extra={(
          <Space>
            <Select value={batchModule} onChange={setBatchModule} options={MODULE_OPTIONS.map(({ value, label }) => ({ value, label }))} style={{ width: 180 }} />
            <Button onClick={handleBatchAssign}>批量分配到模块/台账</Button>
          </Space>
        )}
        style={{ marginBottom: 24 }}
      >
        <Table
          rowSelection={{ selectedRowKeys: selectedTaskIds, onChange: (keys) => setSelectedTaskIds(keys.map(String)) }}
          dataSource={parseTasks}
          columns={taskColumns}
          rowKey="id"
          pagination={{ pageSize: 8 }}
          expandable={{
            expandedRowRender: (row) => (
              <Collapse
                items={[
                  {
                    key: 'timing',
                    label: '阶段耗时统计',
                    children: Object.keys(row.stageTimings).length > 0 ? (
                      <Descriptions size="small" column={2} bordered>
                        {Object.entries(row.stageTimings).map(([stage, ms]) => (
                          <Descriptions.Item key={stage} label={stage}>{Math.round(ms)} ms</Descriptions.Item>
                        ))}
                      </Descriptions>
                    ) : <Empty description="暂无阶段耗时" />,
                  },
                  {
                    key: 'json',
                    label: '完整解析JSON',
                    children: row.result ? (
                      <pre style={{ background: '#f5f5f5', padding: 12, maxHeight: 300, overflowY: 'auto' }}>{JSON.stringify(row.result, null, 2)}</pre>
                    ) : <Empty description={row.errorMessage || '暂无解析结果'} />,
                  },
                ]}
              />
            ),
          }}
          locale={{ emptyText: '暂无解析草稿，请先上传文件' }}
        />
      </Card>

      {latestResult && (
        <Card title="最近一次文件解析结果" style={{ marginBottom: 24 }}>
          <Alert
            message={`解析成功！文档类型: ${DOCUMENT_TYPE_LABELS[latestResult.document_type] || latestResult.document_type}`}
            type="success"
            showIcon
            style={{ marginBottom: 16 }}
          />
          {latestResult.engine_comparison && (
            <Card title="双引擎对比结果" style={{ marginBottom: 16, border: '2px solid #1890ff' }}>
              <Alert message={(latestResult.engine_comparison.selection_reason as string) || '已选择最优结果'} type="info" showIcon style={{ marginBottom: 16 }} />
              {latestDiagnosis && (
                <Alert
                  message={latestDiagnosis.review_required ? '需要人工复核：两个引擎结论存在不确定性' : '两个引擎结果基本一致'}
                  description={latestDiagnosis.review_reason || '系统未发现明显冲突'}
                  type={latestDiagnosis.review_required ? 'warning' : 'success'}
                  showIcon
                  style={{ marginBottom: 16 }}
                />
              )}
              <Row gutter={16}>
                <Col span={8}>
                  <Card title={<><CodeOutlined style={{ color: '#52c41a' }} /> 规则引擎</>} size="small">
                    <Text type="secondary">置信度: </Text>
                    <Text strong style={{ fontSize: 18, color: '#52c41a' }}>{formatPercent(latestResult.engine_comparison.rule_confidence as number)}</Text>
                    <Progress percent={(((latestResult.engine_comparison.rule_confidence as number) || 0) * 100).toFixed(0)} strokeColor="#52c41a" size="small" />
                    <Text type="secondary" style={{ fontSize: 12 }}>规则引擎主要看模板、关键词、正则字段命中率。</Text>
                  </Card>
                </Col>
                <Col span={8}>
                  <Card title={<><ThunderboltOutlined style={{ color: '#1890ff' }} /> LLM大模型</>} size="small">
                    <Text type="secondary">置信度: </Text>
                    <Text strong style={{ fontSize: 18, color: '#1890ff' }}>{formatPercent(latestResult.engine_comparison.llm_confidence as number)}</Text>
                    <Progress percent={(((latestResult.engine_comparison.llm_confidence as number) || 0) * 100).toFixed(0)} strokeColor="#1890ff" size="small" />
                    <Text type="secondary" style={{ fontSize: 12 }}>LLM置信度偏低通常表示文本噪声、字段不完整或模型自评保守。</Text>
                  </Card>
                </Col>
                <Col span={8}>
                  <Card title="交叉验证" size="small">
                    <Text type="secondary">字段一致率: </Text>
                    <Text strong style={{ fontSize: 18 }}>{formatPercent(latestDiagnosis?.consistency_rate)}</Text>
                    <Progress percent={((latestDiagnosis?.consistency_rate || 0) * 100).toFixed(0)} strokeColor={latestDiagnosis?.review_required ? '#faad14' : '#52c41a'} size="small" />
                    <Text type="secondary" style={{ fontSize: 12 }}>看两个引擎在同一字段上的值是否一致，比单看置信度更可靠。</Text>
                  </Card>
                </Col>
              </Row>
              {latestDiagnosis && (
                <Collapse
                  style={{ marginTop: 16 }}
                  items={[
                    {
                      key: 'conflicts',
                      label: `字段冲突 ${latestDiagnosis.conflict_fields?.length || 0} 个`,
                      children: (latestDiagnosis.conflict_fields?.length || 0) > 0 ? (
                        <Table
                          size="small"
                          pagination={false}
                          dataSource={latestDiagnosis.conflict_fields?.map((item) => ({ key: item.field, ...item })) || []}
                          columns={[
                            { title: '字段', dataIndex: 'field', key: 'field' },
                            { title: '规则引擎值', dataIndex: 'rule_value', key: 'rule_value', render: renderValue },
                            { title: 'LLM值', dataIndex: 'llm_value', key: 'llm_value', render: renderValue },
                          ]}
                        />
                      ) : <Empty description="没有发现字段冲突" />,
                    },
                    {
                      key: 'consistent',
                      label: `一致字段 ${latestDiagnosis.consistent_fields?.length || 0} 个`,
                      children: (latestDiagnosis.consistent_fields?.length || 0) > 0 ? (
                        <Space wrap>{latestDiagnosis.consistent_fields?.map((item) => <Tag color="green" key={item.field}>{item.field}: {renderValue(item.value)}</Tag>)}</Space>
                      ) : <Empty description="暂无一致字段" />,
                    },
                    {
                      key: 'only',
                      label: `单方识别字段：规则 ${latestDiagnosis.rule_only_fields?.length || 0} / LLM ${latestDiagnosis.llm_only_fields?.length || 0}`,
                      children: (
                        <Row gutter={16}>
                          <Col span={12}>
                            <Text strong>仅规则引擎识别</Text>
                            <div style={{ marginTop: 8 }}>
                              {(latestDiagnosis.rule_only_fields?.length || 0) > 0 ? latestDiagnosis.rule_only_fields?.map((item) => <Tag key={item.field}>{item.field}: {renderValue(item.rule_value)}</Tag>) : <Empty description="无" />}
                            </div>
                          </Col>
                          <Col span={12}>
                            <Text strong>仅LLM识别</Text>
                            <div style={{ marginTop: 8 }}>
                              {(latestDiagnosis.llm_only_fields?.length || 0) > 0 ? latestDiagnosis.llm_only_fields?.map((item) => <Tag color="blue" key={item.field}>{item.field}: {renderValue(item.llm_value)}</Tag>) : <Empty description="无" />}
                            </div>
                          </Col>
                        </Row>
                      ),
                    },
                  ]}
                />
              )}
            </Card>
          )}
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col span={4}><Card size="small" title="文件格式"><Text strong>{FILE_FORMAT_LABELS[latestResult.file_format] || latestResult.file_format || '未知'}</Text></Card></Col>
            <Col span={4}><Card size="small" title="文档类型"><Text strong>{DOCUMENT_TYPE_LABELS[latestResult.document_type] || latestResult.document_type || '未知'}</Text></Card></Col>
            <Col span={4}><Card size="small" title="置信度"><Text strong>{((latestResult.confidence || 0) * 100).toFixed(1)}%</Text></Card></Col>
            <Col span={4}><Card size="small" title="引擎类型"><Text strong>{latestResult.engine_type || '未知'}</Text></Card></Col>
            <Col span={4}><Card size="small" title="耗时"><Text strong>{(latestResult.parse_duration_ms || 0).toFixed(0)} ms</Text></Card></Col>
          </Row>
          <Card title="最终解析数据">
            <Collapse
              defaultActiveKey={['1']}
              items={[
                {
                  key: '1',
                  label: '解析字段',
                  children: Object.keys(latestResult.data || {}).length === 0 ? <Empty description="未提取到数据" /> : (
                    <Row gutter={16}>{Object.entries(latestResult.data || {}).map(([key, value]) => <Col span={8} key={key}><div style={{ background: '#fafafa', padding: 8, borderRadius: 4 }}><Text type="secondary">{key}:</Text><Text strong style={{ marginLeft: 8 }}>{value !== null && value !== undefined ? String(value) : '空'}</Text></div></Col>)}</Row>
                  ),
                },
                {
                  key: '2',
                  label: '原始文本',
                  children: latestResult.raw_text ? <pre style={{ background: '#f5f5f5', padding: 12, maxHeight: 300, overflowY: 'auto', whiteSpace: 'pre-wrap' }}>{latestResult.raw_text}</pre> : <Empty description="无原始文本" />,
                },
                {
                  key: '3',
                  label: '完整JSON',
                  children: <pre style={{ background: '#f5f5f5', padding: 12, maxHeight: 300, overflowY: 'auto' }}>{JSON.stringify(latestResult, null, 2)}</pre>,
                },
              ]}
            />
          </Card>
        </Card>
      )}

      <Card title="全局成功率进度" style={{ marginBottom: 24 }}>
        <Progress percent={stats?.success_rate_percent || 0} strokeColor={{ '0%': '#10b981', '100%': '#10b981' }} format={(percent) => `${percent}%`} size="small" />
        <div style={{ marginTop: 16, display: 'flex', gap: 16 }}>
          <div><Text type="secondary">成功: </Text><Text strong>{stats?.successful_parses || 0}</Text></div>
          <div><Text type="secondary">失败: </Text><Text strong type="danger">{stats?.failed_parses || 0}</Text></div>
          <div><Text type="secondary">总计: </Text><Text strong>{stats?.total_parses || 0}</Text></div>
        </div>
      </Card>

      <Card title="各阶段耗时统计" style={{ marginBottom: 24 }}>
        <Table dataSource={stats?.stage_stats ? Object.entries(stats.stage_stats).map(([stage, data]) => ({ key: stage, stage, ...data })) : []} columns={StageStatsColumns} pagination={false} rowKey="stage" locale={{ emptyText: '暂无阶段统计数据' }} />
      </Card>

      <Card title="按文件格式统计" style={{ marginBottom: 24 }}>
        <Table dataSource={stats?.format_stats ? Object.entries(stats.format_stats).map(([format, data]) => ({ key: format, format: FILE_FORMAT_LABELS[format] || format, ...data })) : []} columns={FormatStatsColumns} pagination={false} rowKey="key" locale={{ emptyText: '暂无格式统计数据' }} />
      </Card>

      <Card title="按文档类型统计" style={{ marginBottom: 24 }}>
        <Table dataSource={stats?.doctype_stats ? Object.entries(stats.doctype_stats).map(([doctype, data]) => ({ key: doctype, doctype: DOCUMENT_TYPE_LABELS[doctype] || doctype, ...data })) : []} columns={DoctypeStatsColumns} pagination={false} rowKey="key" locale={{ emptyText: '暂无文档类型统计数据' }} />
      </Card>

      {stats?.error_stats && Object.keys(stats.error_stats).length > 0 && (
        <Card title="错误类型统计" style={{ marginBottom: 24 }}>
          <Table dataSource={Object.entries(stats.error_stats).map(([error_type, count]) => ({ key: error_type, error_type, count }))} columns={[{ title: '错误类型', dataIndex: 'error_type', key: 'error_type' }, { title: '发生次数', dataIndex: 'count', key: 'count' }]} pagination={false} rowKey="key" />
        </Card>
      )}

      <Modal
        title="选择要解析的工作表（支持多选）"
        open={excelSheetsVisible}
        onOk={handleParseWithSheets}
        onCancel={() => {
          setExcelSheetsVisible(false)
          setPendingExcelFile(null)
          setPendingExcelQueue([])
          setExcelSheets([])
          setSelectedSheetNames([])
        }}
        okText="开始解析所选工作表"
        cancelText="取消"
        width={760}
      >
        <Alert message="Excel文件可选择一个或多个工作表。每个工作表会生成独立解析草稿ID，便于后续批量管理。" type="info" showIcon style={{ marginBottom: 16 }} />
        <Spin spinning={loadingSheets} tip="正在读取工作表...">
          <Checkbox.Group value={selectedSheetNames} onChange={(values) => setSelectedSheetNames(values.map(String))} style={{ width: '100%' }}>
            <List
              dataSource={excelSheets}
              renderItem={(sheet) => (
                <List.Item style={{ padding: '12px 16px', border: selectedSheetNames.includes(sheet.name) ? '2px solid #1890ff' : '1px solid #d9d9d9', borderRadius: 4, marginBottom: 8, background: selectedSheetNames.includes(sheet.name) ? '#e6f7ff' : '#fff' }}>
                  <Checkbox value={sheet.name} style={{ width: '100%' }}>
                    <Space direction="vertical" size={0}>
                      <Text strong style={{ fontSize: 16 }}>{sheet.name}</Text>
                      <Text type="secondary">行数: {sheet.rows} 行；列数: {sheet.columns.length} 列</Text>
                      <Text type="secondary" style={{ fontSize: 12 }}>列名: {sheet.columns.slice(0, 5).join(', ')}{sheet.columns.length > 5 ? '...' : ''}</Text>
                    </Space>
                  </Checkbox>
                </List.Item>
              )}
            />
          </Checkbox.Group>
        </Spin>
      </Modal>
    </div>
  )
}
