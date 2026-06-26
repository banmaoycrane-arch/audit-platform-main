import { useEffect, useState, useRef } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Button, Card, Descriptions, Empty, List, message, Result, Spin, Tag, Table } from 'antd'
import { ReloadOutlined, FileTextOutlined, ArrowRightOutlined, ExclamationCircleOutlined, ClockCircleOutlined } from '@ant-design/icons'
import { api } from '../../api/client'

/**
 * 草稿页面组件
 *
 * 功能描述：当 AI 生成凭证 Step 2 上传成功但解析失败时，展示草稿数据供用户处理
 * 业务逻辑：
 *   1. 加载任务草稿数据（draft_data、error_message、file_results 等）
 *   2. 展示失败原因、原始数据预览、重试/手动编辑入口
 *   3. 提供进入下一任务分支的导航
 *   4. 轮询任务状态，最大轮询 20 次（约 1 分钟），超时后停止轮询
 *
 * 会计口径：
 *   - 草稿状态 = 上传成功但解析未完成，用户可重试或手动录入
 *   - 与 "completed" 状态区分：completed 表示已生成正式分录
 */

export function DraftPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [retrying, setRetrying] = useState(false)
  const [polling, setPolling] = useState(false)
  const [pollCount, setPollCount] = useState(0)
  const [pollTimeout, setPollTimeout] = useState(false)
  const maxPollCount = 20 // 最大轮询 20 次，约 1 分钟
  const pollInterval = 3000 // 轮询间隔 3 秒
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

  // 新增：原始文件列表（从 source_files 获取）
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

    // 清理定时器
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current)
      }
    }
  }, [jobId])

  const loadDraftData = async () => {
    try {
      setLoading(true)
      const data = await api.getImportJobDraft(Number(jobId))
      setDraftData(data)

      // 加载原始文件列表
      await loadSourceFiles()

      // 如果任务还在处理中，轮询检查状态
      if (data.status === 'processing') {
        // 检查是否超过最大轮询次数
        if (pollCount >= maxPollCount) {
          setPollTimeout(true)
          setPolling(false)
          message.warning('解析超时，请尝试重新上传或手工录入')
          return
        }

        setPolling(true)
        setPollCount(prev => prev + 1)
        timerRef.current = setTimeout(() => {
          loadDraftData()
        }, pollInterval)
        return
      }

      // 如果任务已完成，自动跳转
      if (data.status === 'completed') {
        message.info('任务已完成，跳转到凭证生成页面')
        navigate(`/ledger/vouchers/step/3?jobId=${jobId}`)
        return
      }
      // 如果任务待上传，跳转回上传页面
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
      if (!draftData || draftData.status !== 'processing') {
        setPolling(false)
      }
    }
  }

  const loadSourceFiles = async () => {
    try {
      // 从 import job report 或专门的 API 获取原始文件列表
      const report = await api.getImportReport(Number(jobId))
      if (report && report.source_files) {
        setSourceFiles(report.source_files)
      }
    } catch (error) {
      // 忽略错误，source_files 是可选的
      console.log('获取原始文件列表失败:', error)
    }
  }

  const handleRetry = async () => {
    try {
      setRetrying(true)
      // 重置轮询计数
      setPollCount(0)
      setPollTimeout(false)
      const result = await api.retryImportJob(Number(jobId))
      message.success(result.message)
      // 重试后跳转到 Step 2 重新上传
      navigate(`/ledger/vouchers/step/2?jobId=${jobId}`)
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error)
      message.error(`重试失败：${detail}`)
    } finally {
      setRetrying(false)
    }
  }

  const handleManualEntry = () => {
    // 跳转到 Step 3 生成草稿页面，允许用户手动编辑
    navigate(`/ledger/vouchers/step/3?jobId=${jobId}&inputMode=manual`)
  }

  const handleGoToStep3 = () => {
    // 直接进入 Step 3，尝试生成草稿（可能部分数据可用）
    navigate(`/ledger/vouchers/step/3?jobId=${jobId}`)
  }

  const handleForceStop = () => {
    // 强制停止轮询，显示超时状态
    if (timerRef.current) {
      clearTimeout(timerRef.current)
    }
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

  // 判断是否有解析详情
  const hasFileResults = fileResults.length > 0
  const isProcessing = draftData.status === 'processing'
  const isDraft = draftData.status === 'draft'

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
      <Card
        title={
          <span>
            <ExclamationCircleOutlined style={{ color: '#faad14', marginRight: 8 }} />
            凭证导入草稿 - {isProcessing ? '解析中' : '解析失败'}
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
          status={isProcessing ? 'info' : 'warning'}
          title={isProcessing ? '文件上传成功，正在解析中...' : '文件上传成功，但解析失败'}
          subTitle={
            <div>
              <p>{draftData.error_message || (isProcessing ? '系统正在处理文件，请稍候...' : '系统处理异常，请检查文件格式后重试')}</p>
              {pollTimeout && (
                <p style={{ color: '#f5222d', fontWeight: 'bold' }}>
                  解析超时：已达到最大等待时间（{maxPollCount * pollInterval / 1000} 秒），请尝试重新上传或手工录入
                </p>
              )}
              <p style={{ fontSize: 12, color: '#999' }}>
                请求编号：{requestId}
              </p>
            </div>
          }
          extra={[
            <Button
              key="retry"
              type="primary"
              icon={<ReloadOutlined />}
              loading={retrying}
              onClick={handleRetry}
              disabled={isProcessing && !pollTimeout}
            >
              重新上传并解析
            </Button>,
            <Button
              key="manual"
              icon={<FileTextOutlined />}
              onClick={handleManualEntry}
              disabled={isProcessing && !pollTimeout}
            >
              手工录入凭证
            </Button>,
            <Button
              key="step3"
              icon={<ArrowRightOutlined />}
              onClick={handleGoToStep3}
              disabled={isProcessing && !pollTimeout}
            >
              尝试生成草稿
            </Button>,
            isProcessing && !pollTimeout && (
              <Button
                key="stop"
                danger
                onClick={handleForceStop}
              >
                停止轮询
              </Button>
            ),
          ].filter(Boolean)}
        />
      </Card>

      {/* 轮询状态提示 */}
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

      <Card title="任务信息" style={{ marginTop: 16 }}>
        <Descriptions bordered column={2}>
          <Descriptions.Item label="任务 ID">{draftData.job_id}</Descriptions.Item>
          <Descriptions.Item label="任务状态">
            <Tag color={isProcessing ? 'blue' : isDraft ? 'orange' : 'default'}>
              {draftData.status}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="来源类型">{draftData.source_type}</Descriptions.Item>
          <Descriptions.Item label="文件数量">{draftData.file_count}</Descriptions.Item>
          <Descriptions.Item label="分录数量">{draftData.entry_count}</Descriptions.Item>
          <Descriptions.Item label="创建时间">
            {draftData.created_at ? new Date(draftData.created_at).toLocaleString('zh-CN') : '-'}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {/* 原始文件列表 */}
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
                render: (text: string) => (
                  <span>
                    <FileTextOutlined style={{ marginRight: 8 }} />
                    {text}
                  </span>
                ),
              },
              {
                title: '文件类型',
                dataIndex: 'file_type',
                key: 'file_type',
              },
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
              {
                title: '上传时间',
                dataIndex: 'created_at',
                key: 'created_at',
                render: (date: string) => new Date(date).toLocaleString('zh-CN'),
              },
            ]}
          />
        )}
      </Card>

      {/* 文件解析详情 */}
      <Card title="文件解析详情" style={{ marginTop: 16 }}>
        {isProcessing ? (
          <div style={{ textAlign: 'center', padding: 24 }}>
            <Spin tip="正在解析文件，请稍候..." />
            <p style={{ marginTop: 16, color: '#999' }}>
              系统正在处理文件，预计需要几秒到几分钟...
            </p>
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
                      <Tag
                        color={item.success ? 'green' : 'red'}
                        style={{ marginLeft: 8 }}
                      >
                        {item.success ? '成功' : '失败'}
                      </Tag>
                    </span>
                  }
                  description={
                    <div>
                      {item.error_message && (
                        <p style={{ color: '#f5222d' }}>错误：{item.error_message}</p>
                      )}
                      {item.entries_created !== undefined && (
                        <p>生成分录数：{item.entries_created}</p>
                      )}
                      {item.parse_diagnostics && (
                        <details>
                          <summary>解析诊断信息</summary>
                          <pre style={{ fontSize: 12, background: '#f5f5f5', padding: 8 }}>
                            {JSON.stringify(item.parse_diagnostics, null, 2)}
                          </pre>
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
              可能原因：
              <br />1. 任务还在处理中（processing）
              <br />2. 解析失败时未保存详细记录
              <br />3. 文件格式不支持自动解析
            </p>
          </Empty>
        )}
      </Card>

      <Card title="操作指南" style={{ marginTop: 16 }}>
        <ol>
          <li>
            <strong>重新上传并解析</strong>：如果文件格式有误，修正后重新上传
          </li>
          <li>
            <strong>手工录入凭证</strong>：放弃自动解析，直接在凭证录入页面手工填写
          </li>
          <li>
            <strong>尝试生成草稿</strong>：如果部分数据已解析成功，尝试进入 Step 3 生成草稿
          </li>
        </ol>
        <p style={{ color: '#999', fontSize: 12 }}>
          提示：如问题持续，请联系管理员并提供请求编号（{requestId}）
        </p>
      </Card>
    </div>
  )
}
