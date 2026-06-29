import { useEffect, useState, useRef } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Button, Card, Descriptions, Empty, List, message, Result, Spin, Tag, Table, Collapse, Alert, Row, Col } from 'antd'
import { ReloadOutlined, FileTextOutlined, ArrowRightOutlined, ExclamationCircleOutlined, ClockCircleOutlined } from '@ant-design/icons'
import { api } from '../../api/client'

/**
 * 草稿页面组件 - 统一展示 parser-engine 解析结果
 */

export function DraftPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [retrying, setRetrying] = useState(false)
  const [polling, setPolling] = useState(false)
  const [pollCount, setPollCount] = useState(0)
  const [pollTimeout, setPollTimeout] = useState(false)
  const maxPollCount = 20
  const pollInterval = 3000
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const [draftData, setDraftData] = useState<{
    job_id: number
    status: string
    error_message: string | null
    draft_data: Record<string, unknown> | null
    source_type: string
    entry_count: number
    file_count: number
    created_at: string | null
  } | null>(null)

  const [sourceFiles, setSourceFiles] = useState<Array<{
    id: number
    filename: string
    file_type: string
    file_size: number
    created_at: string
  }>>([])

  useEffect(() => {
    if (!jobId) {
      message.error('缺少任务 ID')
      navigate('/ledger/vouchers/step/2')
      return
    }
    loadDraftData()
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [jobId])

  const loadDraftData = async () => {
    try {
      setLoading(true)
      const data = await api.getImportJobDraft(Number(jobId))
      setDraftData(data)
      await loadSourceFiles()

      if (data.status === 'processing') {
        if (pollCount >= maxPollCount) {
          setPollTimeout(true)
          setPolling(false)
          message.warning('解析超时，请尝试重新上传或手工录入')
          return
        }
        setPolling(true)
        setPollCount(prev => prev + 1)
        timerRef.current = setTimeout(() => loadDraftData(), pollInterval)
        return
      }

      if (data.status === 'completed') {
        message.info('任务已完成，跳转到凭证生成页面')
        navigate(`/ledger/vouchers/step/3?jobId=${jobId}`)
        return
      }
      if (data.status === 'created') {
        message.info('任务待上传，跳转到上传页面')
        navigate(`/ledger/vouchers/step/2?jobId=${jobId}`)
        return
      }
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error)
      message.error(`加载草稿数据失败：${detail}`)
    } finally {
      setLoading(false)
      if (!draftData || draftData.status !== 'processing') setPolling(false)
    }
  }

  const loadSourceFiles = async () => {
    try {
      const report = await api.getImportReport(Number(jobId))
      if (report && report.source_files) setSourceFiles(report.source_files)
    } catch (error) {
      // 原始文件列表失败不影响草稿主流程。
    }
  }

  const handleRetry = async () => {
    try {
      setRetrying(true)
      setPollCount(0)
      setPollTimeout(false)
      const result = await api.retryImportJob(Number(jobId))
      message.success(result.message)
      navigate(`/ledger/vouchers/step/2?jobId=${jobId}`)
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error)
      message.error(`重试失败：${detail}`)
    } finally {
      setRetrying(false)
    }
  }

  const handleManualEntry = () => {
    navigate(`/ledger/vouchers/step/3?jobId=${jobId}&inputMode=manual`)
  }

  const handleGoToStep3 = () => {
    navigate(`/ledger/vouchers/step/3?jobId=${jobId}`)
  }

  const handleForceStop = () => {
    if (timerRef.current) clearTimeout(timerRef.current)
    setPolling(false)
    setPollTimeout(true)
    message.info('已停止轮询，可以手动操作')
  }

  if (loading && !polling) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}>
        <Spin size="large" tip="正在加载草稿数据..." />
      </div>
    )
  }

  if (!draftData) {
    return (
      <Result
        status="error"
        title="加载草稿数据失败"
        subTitle="无法获取任务草稿信息，请返回重试"
        extra={
          <Button type="primary" onClick={() => navigate('/ledger/vouchers/step/2')}>
            返回上传页面
          </Button>
        }
      />
    )
  }

  const fileResults = (draftData.draft_data?.file_results as Array<{
    filename: string
    success: boolean
    error_message?: string
    parse_diagnostics?: Record<string, unknown>
    entries_created?: number
  }>) || []

  const requestId = (draftData.draft_data?.request_id as string) || 'unknown'
  const hasFileResults = fileResults.length > 0
  const isProcessing = draftData.status === 'processing'
  const isDraft = draftData.status === 'draft'
  const parserEngineResult = draftData.draft_data?.parser_engine_result as {
    file_format?: string
    document_type?: string
    document_sub_type?: string | null
    confidence?: number
    engine_type?: string
    data?: Record<string, unknown>
    raw_text?: string | null
    error_message?: string | null
    parse_duration_ms?: number
    stage_timings?: Record<string, number>
    engine_comparison?: Record<string, unknown>
    multi_llm_comparison?: Record<string, unknown>
  } | undefined
  const autoReviewResult = draftData.draft_data?.auto_review_result as {
    passed?: boolean
    confidence?: number
    document_type?: string
    risk_level?: string
    rules?: Array<{ name: string; passed: boolean; message: string }>
    reviewed_at?: string
  } | undefined
  const archiveResult = draftData.draft_data?.archive_result as {
    archived?: boolean
    status?: string
    target?: string | null
    record_id?: number | null
    reason?: string
    document_type?: string
    archived_at?: string
  } | undefined
  const hasParserEngineResult = Boolean(parserEngineResult)

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
      <Card
        title={
          <span>
            <ExclamationCircleOutlined style={{ color: '#faad14', marginRight: 8 }} />
            凭证导入草稿 - {isProcessing ? '解析中' : archiveResult?.archived ? '已自动归档' : hasParserEngineResult ? '统一解析结果待复核' : '待处理'}
          </span>
        }
        extra={
          <Tag color={isProcessing ? 'blue' : 'orange'}>
            状态：{draftData.status}
            {polling && <ClockCircleOutlined style={{ marginLeft: 8 }} spin />}
          </Tag>
        }
      >
        <Result
          status={isProcessing ? 'info' : archiveResult?.archived ? 'success' : hasParserEngineResult ? 'success' : 'warning'}
          title={isProcessing ? '文件上传成功，正在解析中...' : archiveResult?.archived ? '文件已自动复核通过并归档' : hasParserEngineResult ? '文件已由统一解析引擎完成解析' : '文件上传成功，等待处理'}
          subTitle={
            <div>
              <p>{draftData.error_message || (isProcessing ? '系统正在处理文件，请稍候...' : archiveResult?.archived ? `已归档到 ${archiveResult.target}，记录编号：${archiveResult.record_id}` : hasParserEngineResult ? '本页直接展示解析引擎管理页面同源输出；自动复核通过后会归档到对应业务台账。' : '系统处理异常，请检查文件格式后重试')}</p>
              {pollTimeout && (
                <p style={{ color: '#f5222d', fontWeight: 'bold' }}>
                  解析超时：已达到最大等待时间（{maxPollCount * pollInterval / 1000} 秒），请尝试重新上传或手工录入
                </p>
              )}
              <p style={{ fontSize: 12, color: '#999' }}>请求编号：{requestId}</p>
            </div>
          }
          extra={[
            <Button key="retry" type="primary" icon={<ReloadOutlined />} loading={retrying} onClick={handleRetry} disabled={isProcessing && !pollTimeout}>
              重新上传并解析
            </Button>,
            <Button key="manual" icon={<FileTextOutlined />} onClick={handleManualEntry} disabled={isProcessing && !pollTimeout}>
              手工录入凭证
            </Button>,
            <Button key="step3" icon={<ArrowRightOutlined />} onClick={handleGoToStep3} disabled={isProcessing && !pollTimeout}>
              尝试生成草稿
            </Button>,
            isProcessing && !pollTimeout && (
              <Button key="stop" danger onClick={handleForceStop}>停止轮询</Button>
            ),
          ].filter(Boolean)}
        />
      </Card>

      {isProcessing && (
        <Card style={{ marginTop: 16, background: '#f6ffed' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <p style={{ margin: 0 }}>
                <ClockCircleOutlined spin style={{ marginRight: 8, color: '#52c41a' }} />
                正在轮询任务状态...（第 {pollCount} / {maxPollCount} 次）
              </p>
              <p style={{ margin: '8px 0 0 0', fontSize: 12, color: '#999' }}>
                预计剩余时间：约 {Math.max(0, (maxPollCount - pollCount) * pollInterval / 1000)} 秒
              </p>
            </div>
            <Spin size="small" />
          </div>
        </Card>
      )}

      {hasParserEngineResult && parserEngineResult && (
        <Card title="自动复核与归档结果" style={{ marginTop: 16 }}>
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col span={6}>
              <Card size="small" title="自动复核">
                <Tag color={autoReviewResult?.passed ? 'green' : 'orange'}>{autoReviewResult?.passed ? '通过' : '需人工复核'}</Tag>
              </Card>
            </Col>
            <Col span={6}>
              <Card size="small" title="风险等级"><strong>{autoReviewResult?.risk_level || '-'}</strong></Card>
            </Col>
            <Col span={6}>
              <Card size="small" title="归档状态">
                <Tag color={archiveResult?.archived ? 'green' : 'orange'}>{archiveResult?.archived ? '已归档' : '未归档'}</Tag>
              </Card>
            </Col>
            <Col span={6}>
              <Card size="small" title="归档去向"><strong>{archiveResult?.target || '-'}</strong></Card>
            </Col>
          </Row>
          {archiveResult?.archived ? (
            <Alert
              type="success"
              showIcon
              message="自动归档完成"
              description={`记录编号：${archiveResult.record_id}；归档时间：${archiveResult.archived_at ? new Date(archiveResult.archived_at).toLocaleString('zh-CN') : '-'}`}
              style={{ marginBottom: 16 }}
            />
          ) : (
            <Alert
              type="warning"
              showIcon
              message="需要人工复核"
              description={archiveResult?.reason || '自动复核未通过或该文档类型暂不支持自动归档'}
              style={{ marginBottom: 16 }}
            />
          )}
          <Collapse
            items={[
              {
                key: 'rules',
                label: '自动复核规则明细',
                children: autoReviewResult?.rules?.length ? (
                  <List
                    dataSource={autoReviewResult.rules}
                    renderItem={(rule) => (
                      <List.Item>
                        <Tag color={rule.passed ? 'green' : 'red'}>{rule.passed ? '通过' : '未通过'}</Tag>
                        <strong style={{ marginRight: 8 }}>{rule.name}</strong>
                        <span>{rule.message}</span>
                      </List.Item>
                    )}
                  />
                ) : <Empty description="暂无自动复核规则记录" />,
              },
            ]}
          />
        </Card>
      )}

      {hasParserEngineResult && parserEngineResult && (
        <Card title="统一解析引擎结果" style={{ marginTop: 16 }}>
          <Alert
            message="本结果来自解析引擎管理的通用兼容引擎"
            description="凭证草稿页不再另起一套文件解析逻辑；这里展示的是 parser-engine 同源输出。正式凭证生成前，请按会计口径复核字段、金额、往来单位和业务类型。"
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
          />
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col span={4}><Card size="small" title="文件格式"><strong>{parserEngineResult.file_format || '未知'}</strong></Card></Col>
            <Col span={4}><Card size="small" title="文档类型"><strong>{parserEngineResult.document_type || '未知'}</strong></Card></Col>
            <Col span={4}><Card size="small" title="细分类型"><strong>{parserEngineResult.document_sub_type || '-'}</strong></Card></Col>
            <Col span={4}><Card size="small" title="置信度"><strong>{((parserEngineResult.confidence || 0) * 100).toFixed(1)}%</strong></Card></Col>
            <Col span={4}><Card size="small" title="引擎类型"><strong>{parserEngineResult.engine_type || '未知'}</strong></Card></Col>
            <Col span={4}><Card size="small" title="耗时"><strong>{Math.round(parserEngineResult.parse_duration_ms || 0)} ms</strong></Card></Col>
          </Row>
          <Collapse
            defaultActiveKey={['fields']}
            items={[
              {
                key: 'fields',
                label: '解析字段',
                children: Object.keys(parserEngineResult.data || {}).length === 0 ? <Empty description="未提取到字段" /> : (
                  <Row gutter={[16, 12]}>
                    {Object.entries(parserEngineResult.data || {}).map(([key, value]) => (
                      <Col span={8} key={key}>
                        <div style={{ background: '#fafafa', padding: 8, borderRadius: 4 }}>
                          <span style={{ color: '#666' }}>{key}：</span>
                          <strong>{value !== null && value !== undefined ? String(value) : '空'}</strong>
                        </div>
                      </Col>
                    ))}
                  </Row>
                ),
              },
              {
                key: 'comparison',
                label: '双引擎/多引擎对比',
                children: parserEngineResult.engine_comparison || parserEngineResult.multi_llm_comparison ? (
                  <pre style={{ fontSize: 12, background: '#f5f5f5', padding: 12, maxHeight: 320, overflowY: 'auto' }}>{JSON.stringify({
                    engine_comparison: parserEngineResult.engine_comparison,
                    multi_llm_comparison: parserEngineResult.multi_llm_comparison,
                  }, null, 2)}</pre>
                ) : <Empty description="本次结果未包含引擎对比信息" />,
              },
              {
                key: 'raw',
                label: '原始文本',
                children: parserEngineResult.raw_text ? <pre style={{ fontSize: 12, background: '#f5f5f5', padding: 12, maxHeight: 320, overflowY: 'auto', whiteSpace: 'pre-wrap' }}>{parserEngineResult.raw_text}</pre> : <Empty description="无原始文本" />,
              },
              {
                key: 'json',
                label: '完整 JSON',
                children: <pre style={{ fontSize: 12, background: '#f5f5f5', padding: 12, maxHeight: 320, overflowY: 'auto' }}>{JSON.stringify(parserEngineResult, null, 2)}</pre>,
              },
            ]}
          />
        </Card>
      )}

      <Card title="任务信息" style={{ marginTop: 16 }}>
        <Descriptions bordered column={2}>
          <Descriptions.Item label="任务 ID">{draftData.job_id}</Descriptions.Item>
          <Descriptions.Item label="任务状态">
            <Tag color={isProcessing ? 'blue' : isDraft ? 'orange' : 'default'}>{draftData.status}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="来源类型">{draftData.source_type}</Descriptions.Item>
          <Descriptions.Item label="文件数量">{draftData.file_count}</Descriptions.Item>
          <Descriptions.Item label="分录数量">{draftData.entry_count}</Descriptions.Item>
          <Descriptions.Item label="创建时间">{draftData.created_at ? new Date(draftData.created_at).toLocaleString('zh-CN') : '-'}</Descriptions.Item>
        </Descriptions>
      </Card>

      <Card title="上传的原始文件" style={{ marginTop: 16 }}>
        {sourceFiles.length === 0 ? (
          <Empty description="暂无原始文件记录" />
        ) : (
          <Table
            dataSource={sourceFiles}
            rowKey="id"
            pagination={false}
            columns={[
              {
                title: '文件名',
                dataIndex: 'filename',
                key: 'filename',
                render: (text: string) => <span><FileTextOutlined style={{ marginRight: 8 }} />{text}</span>,
              },
              { title: '文件类型', dataIndex: 'file_type', key: 'file_type' },
              {
                title: '文件大小',
                dataIndex: 'file_size',
                key: 'file_size',
                render: (size: number) => {
                  if (size < 1024) return `${size} B`
                  if (size < 1024 * 1024) return `${(size / 1024).toFixed(2)} KB`
                  return `${(size / (1024 * 1024)).toFixed(2)} MB`
                },
              },
              { title: '上传时间', dataIndex: 'created_at', key: 'created_at', render: (date: string) => new Date(date).toLocaleString('zh-CN') },
            ]}
          />
        )}
      </Card>

      <Card title="文件解析详情" style={{ marginTop: 16 }}>
        {isProcessing ? (
          <div style={{ textAlign: 'center', padding: 24 }}>
            <Spin tip="正在解析文件，请稍候..." />
            <p style={{ marginTop: 16, color: '#999' }}>系统正在处理文件，预计需要几秒到几分钟...</p>
          </div>
        ) : hasFileResults ? (
          <List
            dataSource={fileResults}
            renderItem={(item) => (
              <List.Item>
                <List.Item.Meta
                  title={
                    <span>
                      <FileTextOutlined style={{ marginRight: 8 }} />
                      {item.filename}
                      <Tag color={item.success ? 'green' : 'red'} style={{ marginLeft: 8 }}>{item.success ? '成功' : '失败'}</Tag>
                    </span>
                  }
                  description={
                    <div>
                      {item.error_message && <p style={{ color: '#f5222d' }}>错误：{item.error_message}</p>}
                      {item.entries_created !== undefined && <p>生成分录数：{item.entries_created}</p>}
                      {item.parse_diagnostics && (
                        <details>
                          <summary>解析诊断信息</summary>
                          <pre style={{ fontSize: 12, background: '#f5f5f5', padding: 8 }}>{JSON.stringify(item.parse_diagnostics, null, 2)}</pre>
                        </details>
                      )}
                    </div>
                  }
                />
              </List.Item>
            )}
          />
        ) : (
          <Empty description="暂无文件解析记录">
            <p style={{ color: '#999', fontSize: 12 }}>
              可能原因：<br />1. 任务还在处理中（processing）<br />2. 解析失败时未保存详细记录<br />3. 文件格式不支持自动解析
            </p>
          </Empty>
        )}
      </Card>

      <Card title="操作指南" style={{ marginTop: 16 }}>
        <ol>
          <li><strong>重新上传并解析</strong>：如果文件格式有误，修正后重新上传</li>
          <li><strong>手工录入凭证</strong>：放弃自动解析，直接在凭证录入页面手工填写</li>
          <li><strong>尝试生成草稿</strong>：如果部分数据已解析成功，尝试进入 Step 3 生成草稿</li>
        </ol>
        <p style={{ color: '#999', fontSize: 12 }}>提示：如问题持续，请联系管理员并提供请求编号（{requestId}）</p>
      </Card>
    </div>
  )
}
