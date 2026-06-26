import { useEffect, useState, useRef } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Button, Card, Descriptions, Empty, List, message, Result, Spin, Tag, Table, Collapse, Alert } from 'antd'
import { ReloadOutlined, FileTextOutlined, ArrowRightOutlined, ExclamationCircleOutlined, ClockCircleOutlined, CheckCircleOutlined, WarningOutlined } from '@ant-design/icons'
import { api } from '../../api/client'

/**
 * 草稿页面组件 - 支持合同解析结果展示（基于 CAS 14 收入准则）
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
      console.log('获取原始文件列表失败:', error)
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

  // 合同解析结果
  const contractResult = draftData.draft_data?.contract_parse_result as {
    contract_type: string
    contract_valid: boolean
    effective_conditions: string
    commercial_substance: boolean
    collection_probable: boolean
    parties: Array<{ name: string; role: string; tax_id: string; legal_capacity: boolean }>
    signing_date: string
    period: { start_date: string; end_date: string; duration_days: number; termination_terms: string }
    price: {
      total_amount: string
      amount_excl_tax: string
      tax_rate: string
      tax_amount: string
      currency: string
      variable_consideration: string
      variable_type: string
      back_to_back: boolean
      payment_terms: string
    }
    performance_obligations: Array<{
      item_no: number
      description: string
      quantity: string
      unit: string
      unit_price: string
      total_price: string
      distinct: boolean
      highly_interdependent: boolean
      integration_service: boolean
      revenue_recognition_method: string
      time_method_criteria: string[]
      qualified_payment_right: boolean
      irreplaceable_use: boolean
      standalone_selling_price: string
      allocation_ratio: string
    }>
    penalties: Array<{
      penalty_clause: string
      penalty_amount: string
      is_probable: boolean
      provision_required: boolean
      provision_amount: string
      impact_on_revenue: string
    }>
    contract_costs: Array<{ cost_type: string; amount: string; amortization_method: string }>
    financial_assets: Array<{ asset_type: string; amount: string; expected_credit_loss: string; risk_rating: string }>
    tax_treatment: { tax_type: string; tax_rate: string; tax_amount: string; special_treatment: string }
    summary: string
    accounting_notes: string
    five_step_analysis: string
    confidence_score: string
  } | null

  const contractValidationErrors = draftData.draft_data?.contract_validation_errors as string[] | null

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

      {/* 合同解析结果展示 */}
      {contractResult && (
        <Card title="合同解析结果（基于 CAS 14 收入准则）" style={{ marginTop: 16 }}>
          {/* 合同成立判断 */}
          <Alert
            message="合同成立判断（CAS 14 第五条）"
            description={
              <div>
                <p><CheckCircleOutlined style={{ color: contractResult.contract_valid ? '#52c41a' : '#f5222d' }} /> 合同是否成立：{contractResult.contract_valid ? '是' : '否'}</p>
                <p>生效条件：{contractResult.effective_conditions || '无'}</p>
                <p>商业实质：{contractResult.commercial_substance ? '有' : '无'}</p>
                <p>对价很可能收回：{contractResult.collection_probable ? '是' : '否'}</p>
              </div>
            }
            type={contractResult.contract_valid ? 'success' : 'error'}
            style={{ marginBottom: 16 }}
          />

          {/* 合同主体 */}
          <Card title="合同主体" size="small" style={{ marginBottom: 16 }}>
            <Table
              dataSource={contractResult.parties}
              rowKey="name"
              pagination={false}
              columns={[
                { title: '角色', dataIndex: 'role', key: 'role' },
                { title: '名称', dataIndex: 'name', key: 'name' },
                { title: '税号', dataIndex: 'tax_id', key: 'tax_id' },
                { title: '行为能力', dataIndex: 'legal_capacity', key: 'legal_capacity', render: (v: boolean) => v ? '有' : '无' },
              ]}
            />
          </Card>

          {/* 时间信息 */}
          <Card title="合同时间" size="small" style={{ marginBottom: 16 }}>
            <Descriptions bordered column={2}>
              <Descriptions.Item label="签署日期">{contractResult.signing_date || '-'}</Descriptions.Item>
              <Descriptions.Item label="开始日期">{contractResult.period?.start_date || '-'}</Descriptions.Item>
              <Descriptions.Item label="结束日期">{contractResult.period?.end_date || '-'}</Descriptions.Item>
              <Descriptions.Item label="总天数">{contractResult.period?.duration_days || '-'}</Descriptions.Item>
              <Descriptions.Item label="终止条款" span={2}>{contractResult.period?.termination_terms || '-'}</Descriptions.Item>
            </Descriptions>
          </Card>

          {/* 交易价格（价税分离） */}
          <Card title="交易价格（CAS 14 第十四条至第十九条）" size="small" style={{ marginBottom: 16 }}>
            <Descriptions bordered column={2}>
              <Descriptions.Item label="含税总价">{contractResult.price?.total_amount || '0.00'} {contractResult.price?.currency}</Descriptions.Item>
              <Descriptions.Item label="不含税金额（交易价格）">{contractResult.price?.amount_excl_tax || '0.00'}</Descriptions.Item>
              <Descriptions.Item label="税率">{(Number(contractResult.price?.tax_rate) * 100).toFixed(0)}%</Descriptions.Item>
              <Descriptions.Item label="税额">{contractResult.price?.tax_amount || '0.00'}</Descriptions.Item>
              <Descriptions.Item label="可变对价">{contractResult.price?.variable_consideration || '0.00'} ({contractResult.price?.variable_type || '无'})</Descriptions.Item>
              <Descriptions.Item label="背靠背付款">{contractResult.price?.back_to_back ? '是' : '否'}</Descriptions.Item>
              <Descriptions.Item label="付款条款" span={2}>{contractResult.price?.payment_terms || '-'}</Descriptions.Item>
            </Descriptions>
          </Card>

          {/* 履约义务 */}
          <Card title="履约义务（CAS 14 第九条、第十条）" size="small" style={{ marginBottom: 16 }}>
            {contractResult.performance_obligations?.map((obligation, idx) => (
              <Card key={idx} title={`履约义务 ${obligation.item_no}`} size="small" style={{ marginBottom: 8 }}>
                <p><strong>描述：</strong>{obligation.description}</p>
                <p><strong>数量：</strong>{obligation.quantity} {obligation.unit}</p>
                <p><strong>单价：</strong>{obligation.unit_price}</p>
                <p><strong>小计：</strong>{obligation.total_price}</p>
                <p><strong>可明确区分：</strong>{obligation.distinct ? '是' : '否'}</p>
                <p><strong>高度关联：</strong>{obligation.highly_interdependent ? '是' : '否'}</p>
                <p><strong>重大整合服务：</strong>{obligation.integration_service ? '是' : '否'}</p>
                <p><strong>收入确认方法：</strong><Tag color={obligation.revenue_recognition_method === '时段法' ? 'blue' : 'green'}>{obligation.revenue_recognition_method}</Tag></p>
                <p><strong>时段法条件：</strong>{obligation.time_method_criteria?.join(', ') || '-'}</p>
                <p><strong>合格收款权：</strong>{obligation.qualified_payment_right ? '有' : '无'}</p>
                <p><strong>不可替代用途：</strong>{obligation.irreplaceable_use ? '有' : '无'}</p>
                <p><strong>单独售价：</strong>{obligation.standalone_selling_price}</p>
                <p><strong>分摊比例：</strong>{obligation.allocation_ratio}</p>
              </Card>
            ))}
          </Card>

          {/* 违约责任 */}
          <Card title="违约责任（CAS 13 或有事项）" size="small" style={{ marginBottom: 16 }}>
            {contractResult.penalties?.map((penalty, idx) => (
              <Alert
                key={idx}
                message={penalty.penalty_type || '违约'}
                description={
                  <div>
                    <p><strong>条款：</strong>{penalty.penalty_clause}</p>
                    <p><strong>金额：</strong>{penalty.penalty_amount}</p>
                    <p><strong>是否很可能发生：</strong>{penalty.is_probable ? '是' : '否'}</p>
                    <p><strong>需预提：</strong>{penalty.provision_required ? '是' : '否'}</p>
                    <p><strong>预提金额：</strong>{penalty.provision_amount}</p>
                    <p><strong>对收入影响：</strong>{penalty.impact_on_revenue}</p>
                  </div>
                }
                type={penalty.is_probable ? 'warning' : 'info'}
                style={{ marginBottom: 8 }}
              />
            ))}
          </Card>

          {/* 合同成本 */}
          <Card title="合同成本（CAS 14 第二十六条至第二十九条）" size="small" style={{ marginBottom: 16 }}>
            <Table
              dataSource={contractResult.contract_costs}
              rowKey="cost_type"
              pagination={false}
              columns={[
                { title: '成本类型', dataIndex: 'cost_type', key: 'cost_type' },
                { title: '金额', dataIndex: 'amount', key: 'amount' },
                { title: '摊销方法', dataIndex: 'amortization_method', key: 'amortization_method' },
              ]}
            />
          </Card>

          {/* 金融资产 */}
          <Card title="金融资产（CAS 22）" size="small" style={{ marginBottom: 16 }}>
            <Table
              dataSource={contractResult.financial_assets}
              rowKey="asset_type"
              pagination={false}
              columns={[
                { title: '资产类型', dataIndex: 'asset_type', key: 'asset_type' },
                { title: '金额', dataIndex: 'amount', key: 'amount' },
                { title: '预期信用损失', dataIndex: 'expected_credit_loss', key: 'expected_credit_loss' },
                { title: '风险评级', dataIndex: 'risk_rating', key: 'risk_rating' },
              ]}
            />
          </Card>

          {/* 税务处理 */}
          <Card title="税务处理" size="small" style={{ marginBottom: 16 }}>
            <Descriptions bordered column={2}>
              <Descriptions.Item label="税种">{contractResult.tax_treatment?.tax_type || '-'}</Descriptions.Item>
              <Descriptions.Item label="税率">{(Number(contractResult.tax_treatment?.tax_rate) * 100).toFixed(0)}%</Descriptions.Item>
              <Descriptions.Item label="税额">{contractResult.tax_treatment?.tax_amount || '0.00'}</Descriptions.Item>
              <Descriptions.Item label="特殊处理" span={2}>{contractResult.tax_treatment?.special_treatment || '-'}</Descriptions.Item>
            </Descriptions>
          </Card>

          {/* 会计校验错误 */}
          {contractValidationErrors && contractValidationErrors.length > 0 && (
            <Alert
              message="会计校验警告"
              description={
                <ul>
                  {contractValidationErrors.map((error, idx) => (
                    <li key={idx}><WarningOutlined style={{ color: '#faad14' }} /> {error}</li>
                  ))}
                </ul>
              }
              type="warning"
              showIcon
              style={{ marginBottom: 16 }}
            />
          )}

          {/* 摘要和会计说明 */}
          <Card title="摘要与会计说明" size="small">
            <p><strong>合同摘要：</strong>{contractResult.summary}</p>
            <p><strong>会计处理说明：</strong>{contractResult.accounting_notes}</p>
            <p><strong>五步法分析：</strong>{contractResult.five_step_analysis}</p>
            <p><strong>置信度：</strong>{(Number(contractResult.confidence_score) * 100).toFixed(0)}%</p>
          </Card>
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
