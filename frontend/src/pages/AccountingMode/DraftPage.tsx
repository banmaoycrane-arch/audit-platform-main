import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Button, Card, Descriptions, Empty, List, message, Result, Spin, Tag } from 'antd'
import { ReloadOutlined, FileTextOutlined, ArrowRightOutlined, ExclamationCircleOutlined } from '@ant-design/icons'
import { api } from '../../api/client'

/**
 * 草稿页面组件
 *
 * 功能描述：当 AI 生成凭证 Step 2 上传成功但解析失败时，展示草稿数据供用户处理
 * 业务逻辑：
 *   1. 加载任务草稿数据（draft_data、error_message、file_results 等）
 *   2. 展示失败原因、原始数据预览、重试/手动编辑入口
 *   3. 提供进入下一任务分支的导航
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

  useEffect(() => {
    if (!jobId) {
      message.error('缺少任务 ID')
      navigate('/ledger/vouchers/step/2')
      return
    }
    loadDraftData()
  }, [jobId])

  const loadDraftData = async () => {
    try {
      setLoading(true)
      const data = await api.getImportJobDraft(Number(jobId))
      setDraftData(data)

      // 如果任务不是 draft 状态，自动跳转到对应页面
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
    }
  }

  const handleRetry = async () => {
    try {
      setRetrying(true)
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

  if (loading) {
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

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
      <Card
        title={
          <span>
            <ExclamationCircleOutlined style={{ color: '#faad14', marginRight: 8 }} />
            凭证导入草稿 - 解析失败
          </span>
        }
        extra={
          <Tag color="orange">状态：草稿（draft）</Tag>
        }
      >
        <Result
          status="warning"
          title="文件上传成功，但解析失败"
          subTitle={
            <div>
              <p>{draftData.error_message || '系统处理异常，请检查文件格式后重试'}</p>
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
            >
              重新上传并解析
            </Button>,
            <Button
              key="manual"
              icon={<FileTextOutlined />}
              onClick={handleManualEntry}
            >
              手工录入凭证
            </Button>,
            <Button
              key="step3"
              icon={<ArrowRightOutlined />}
              onClick={handleGoToStep3}
            >
              尝试生成草稿
            </Button>,
          ]}
        />
      </Card>

      <Card title="任务信息" style={{ marginTop: 16 }}>
        <Descriptions bordered column={2}>
          <Descriptions.Item label="任务 ID">{draftData.job_id}</Descriptions.Item>
          <Descriptions.Item label="任务状态">
            <Tag color="orange">{draftData.status}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="来源类型">{draftData.source_type}</Descriptions.Item>
          <Descriptions.Item label="文件数量">{draftData.file_count}</Descriptions.Item>
          <Descriptions.Item label="分录数量">{draftData.entry_count}</Descriptions.Item>
          <Descriptions.Item label="创建时间">
            {draftData.created_at ? new Date(draftData.created_at).toLocaleString('zh-CN') : '-'}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Card title="文件处理详情" style={{ marginTop: 16 }}>
        {fileResults.length === 0 ? (
          <Empty description="暂无文件处理记录" />
        ) : (
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
