import { useState, useEffect } from 'react'
import { Card, Row, Col, Statistic, Table, Button, Space, Tag, Progress, Alert, Typography, Divider, Spin, Collapse, Empty, Modal, List } from 'antd'
import { ReloadOutlined, UploadOutlined, DatabaseOutlined, BarChartOutlined, FileTextOutlined, ExclamationCircleOutlined, CheckCircleOutlined, ClockCircleOutlined, FileSearchOutlined, CodeOutlined, ThunderboltOutlined, SettingOutlined } from '@ant-design/icons'
import { api } from '../api/client'

const { Title, Text } = Typography

const DOCUMENT_TYPE_LABELS: Record<string, string> = {
  invoice: '发票',
  bank_statement: '银行流水',
  contract: '合同协议',
  inventory_receipt: '入库单',
  salary_table: '工资表',
  expense_document: '费用单据',
  receipt: '收据凭证',
  accounting_entry: '会计分录',
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
}

export function ParserEngineManagementPage() {
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
  const [uploadResult, setUploadResult] = useState<{ success: boolean; message: string; data?: unknown } | null>(null)
  const [excelSheetsVisible, setExcelSheetsVisible] = useState(false)
  const [excelSheets, setExcelSheets] = useState<Array<{ name: string; rows: number; columns: string[]; preview: Record<string, unknown>[] }>>([])
  const [selectedSheet, setSelectedSheet] = useState<string>('')
  const [pendingFile, setPendingFile] = useState<File | null>(null)
  const [loadingSheets, setLoadingSheets] = useState(false)

  useEffect(() => {
    fetchData()
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

  const handleResetStats = async () => {
    try {
      await api.resetPerformanceStats()
      await fetchData()
    } catch (error) {
      console.error('重置统计数据失败:', error)
    }
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setUploadResult(null)

    const isExcel = /\.(xlsx|xls)$/i.test(file.name)

    if (isExcel) {
      setPendingFile(file)
      setLoadingSheets(true)
      try {
        const result = await api.listExcelSheets(file)
        if (result.success && result.sheets.length > 0) {
          setExcelSheets(result.sheets)
          setSelectedSheet(result.sheets[0].name)
          setExcelSheetsVisible(true)
        } else {
          message.warning('未找到工作表')
        }
      } catch (error) {
        message.error(`获取工作表列表失败: ${error instanceof Error ? error.message : String(error)}`)
      } finally {
        setLoadingSheets(false)
      }
      e.target.value = ''
      return
    }

    setUploading(true)

    try {
      const result = await api.parseFile(1, file)
      setUploadResult({
        success: true,
        message: `解析成功！文档类型: ${DOCUMENT_TYPE_LABELS[result.document_type] || result.document_type}`,
        data: result,
      })
    } catch (error) {
      setUploadResult({
        success: false,
        message: `解析失败: ${error instanceof Error ? error.message : String(error)}`,
      })
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  const handleParseWithSheet = async () => {
    if (!pendingFile || !selectedSheet) return

    setExcelSheetsVisible(false)
    setUploading(true)

    try {
      const result = await api.parseFile(1, pendingFile, selectedSheet)
      setUploadResult({
        success: true,
        message: `解析成功！文档类型: ${DOCUMENT_TYPE_LABELS[result.document_type] || result.document_type}（工作表: ${selectedSheet}）`,
        data: result,
      })
    } catch (error) {
      setUploadResult({
        success: false,
        message: `解析失败: ${error instanceof Error ? error.message : String(error)}`,
      })
    } finally {
      setUploading(false)
      setPendingFile(null)
      setExcelSheets([])
      setSelectedSheet('')
    }
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
      <Text type="secondary">查看解析引擎状态、性能统计和测试文件解析</Text>

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
            <Statistic
              title="总解析次数"
              value={stats?.total_parses || 0}
              prefix={<DatabaseOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="成功次数"
              value={stats?.successful_parses || 0}
              prefix={<CheckCircleOutlined />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="失败次数"
              value={stats?.failed_parses || 0}
              prefix={<ExclamationCircleOutlined />}
              valueStyle={{ color: '#ff4d4f' }}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="成功率"
              value={stats?.success_rate_percent || 0}
              suffix="%"
              prefix={<FileSearchOutlined />}
              valueStyle={{ color: (stats?.success_rate_percent || 0) >= 80 ? '#52c41a' : '#faad14' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="并发模型数"
              value={status?.llm_max_concurrent_models || 0}
              prefix={<BarChartOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="首选模型"
              value={status?.llm_preferred_model || '-'}
              prefix={<FileTextOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="对比策略"
              value={status?.llm_comparison_strategy === 'weighted_vote' ? '加权投票' : status?.llm_comparison_strategy || '-'}
              prefix={<ClockCircleOutlined />}
            />
          </Card>
        </Col>
      </Row>

      <Card title="引擎配置状态" style={{ marginBottom: 24 }}>
        <Row gutter={16}>
          <Col span={8}>
            <Space>
              <Tag color={status?.llm_multi_engine_enabled ? 'green' : 'red'}>
                {status?.llm_multi_engine_enabled ? '多LLM引擎对比 已启用' : '多LLM引擎对比 已禁用'}
              </Tag>
            </Space>
          </Col>
          <Col span={8}>
            <Space>
              <Tag color={status?.llm_enable_parallel_parsing ? 'green' : 'red'}>
                {status?.llm_enable_parallel_parsing ? '双引擎并行解析 已启用' : '双引擎并行解析 已禁用'}
              </Tag>
            </Space>
          </Col>
          <Col span={8}>
            <Space>
              <Button onClick={fetchData} icon={<ReloadOutlined />}>
                刷新状态
              </Button>
              <Button onClick={handleResetStats} danger icon={<ReloadOutlined />}>
                重置统计
              </Button>
            </Space>
          </Col>
        </Row>

        <Divider />

        <Row gutter={16}>
          <Col span={12}>
            <Text strong>支持的文件格式:</Text>
            <br />
            {status?.supported_formats.map((format) => (
              <Tag key={format}>{FILE_FORMAT_LABELS[format] || format}</Tag>
            ))}
          </Col>
          <Col span={12}>
            <Text strong>支持的文档类型:</Text>
            <br />
            {status?.supported_document_types.map((docType) => (
              <Tag key={docType}>{DOCUMENT_TYPE_LABELS[docType] || docType}</Tag>
            ))}
          </Col>
        </Row>
      </Card>

      <Card title="成功率进度" style={{ marginBottom: 24 }}>
        <Progress
          percent={stats?.success_rate_percent || 0}
          strokeColor={{
            '0%': '#10b981',
            '100%': '#10b981',
          }}
          format={(percent) => `${percent}%`}
          size="small"
        />
        <div style={{ marginTop: 16, display: 'flex', gap: 16 }}>
          <div>
            <Text type="secondary">成功: </Text>
            <Text strong>{stats?.successful_parses || 0}</Text>
          </div>
          <div>
            <Text type="secondary">失败: </Text>
            <Text strong type="danger">{stats?.failed_parses || 0}</Text>
          </div>
          <div>
            <Text type="secondary">总计: </Text>
            <Text strong>{stats?.total_parses || 0}</Text>
          </div>
        </div>
      </Card>

      {uploadResult && (
        <Card title="文件解析结果" style={{ marginBottom: 24 }}>
          <Alert
            message={uploadResult.message}
            type={uploadResult.success ? 'success' : 'error'}
            showIcon
          />
          {uploadResult.data && typeof uploadResult.data === 'object' && (
            <div style={{ marginTop: 16 }}>
              {(uploadResult.data as Record<string, unknown>).engine_comparison && (
                <Card title="🔄 双引擎对比结果" style={{ marginBottom: 16, border: '2px solid #1890ff' }}>
                  <Alert
                    message={(uploadResult.data as Record<string, unknown>).engine_comparison?.selection_reason || '已选择最优结果'}
                    type="info"
                    showIcon
                    style={{ marginBottom: 16 }}
                  />
                  <Row gutter={16}>
                    <Col span={12}>
                      <Card
                        title={<><CodeOutlined style={{ color: '#52c41a' }} /> 规则引擎</>}
                        size="small"
                        bordered={((uploadResult.data as Record<string, unknown>).engine_type as string) === 'rule'}
                        style={{
                          borderColor: ((uploadResult.data as Record<string, unknown>).engine_type as string) === 'rule' ? '#52c41a' : '#d9d9d9',
                          borderWidth: ((uploadResult.data as Record<string, unknown>).engine_type as string) === 'rule' ? 3 : 1,
                          background: ((uploadResult.data as Record<string, unknown>).engine_type as string) === 'rule' ? '#f6ffed' : '#fafafa'
                        }}
                      >
                        <div style={{ marginBottom: 12 }}>
                          <Text type="secondary">置信度: </Text>
                          <Text strong style={{ fontSize: 18, color: '#52c41a' }}>
                            {(((uploadResult.data as Record<string, unknown>).engine_comparison?.rule_confidence as number || 0) * 100).toFixed(1)}%
                          </Text>
                        </div>
                        <Progress
                          percent={(((uploadResult.data as Record<string, unknown>).engine_comparison?.rule_confidence as number || 0) * 100).toFixed(0)}
                          strokeColor="#52c41a"
                          size="small"
                        />
                        <div style={{ marginTop: 12 }}>
                          <Text type="secondary">已提取字段: </Text>
                          <Text strong>
                            {(uploadResult.data as Record<string, unknown>).engine_comparison?.rule_engine_result?.data
                              ? Object.values((uploadResult.data as Record<string, unknown>).engine_comparison?.rule_engine_result?.data as Record<string, unknown> || {}).filter(v => v).length
                              : 0}
                            /
                            {(uploadResult.data as Record<string, unknown>).engine_comparison?.rule_engine_result?.data
                              ? Object.keys((uploadResult.data as Record<string, unknown>).engine_comparison?.rule_engine_result?.data as Record<string, unknown> || {}).length
                              : 0}
                          </Text>
                        </div>
                        {((uploadResult.data as Record<string, unknown>).engine_type as string) === 'rule' && (
                          <Tag color="success" style={{ marginTop: 12 }}>✓ 当前采用此结果</Tag>
                        )}
                      </Card>
                    </Col>
                    <Col span={12}>
                      <Card
                        title={<><ThunderboltOutlined style={{ color: '#1890ff' }} /> LLM大模型</>}
                        size="small"
                        bordered={((uploadResult.data as Record<string, unknown>).engine_type as string) === 'llm'}
                        style={{
                          borderColor: ((uploadResult.data as Record<string, unknown>).engine_type as string) === 'llm' ? '#1890ff' : '#d9d9d9',
                          borderWidth: ((uploadResult.data as Record<string, unknown>).engine_type as string) === 'llm' ? 3 : 1,
                          background: ((uploadResult.data as Record<string, unknown>).engine_type as string) === 'llm' ? '#e6f7ff' : '#fafafa'
                        }}
                      >
                        <div style={{ marginBottom: 12 }}>
                          <Text type="secondary">置信度: </Text>
                          <Text strong style={{ fontSize: 18, color: '#1890ff' }}>
                            {(((uploadResult.data as Record<string, unknown>).engine_comparison?.llm_confidence as number || 0) * 100).toFixed(1)}%
                          </Text>
                        </div>
                        <Progress
                          percent={(((uploadResult.data as Record<string, unknown>).engine_comparison?.llm_confidence as number || 0) * 100).toFixed(0)}
                          strokeColor="#1890ff"
                          size="small"
                        />
                        <div style={{ marginTop: 12 }}>
                          <Text type="secondary">已提取字段: </Text>
                          <Text strong>
                            {(uploadResult.data as Record<string, unknown>).engine_comparison?.llm_engine_result?.data
                              ? Object.values((uploadResult.data as Record<string, unknown>).engine_comparison?.llm_engine_result?.data as Record<string, unknown> || {}).filter(v => v).length
                              : 0}
                            /
                            {(uploadResult.data as Record<string, unknown>).engine_comparison?.llm_engine_result?.data
                              ? Object.keys((uploadResult.data as Record<string, unknown>).engine_comparison?.llm_engine_result?.data as Record<string, unknown> || {}).length
                              : 0}
                          </Text>
                        </div>
                        {((uploadResult.data as Record<string, unknown>).engine_type as string) === 'llm' && (
                          <Tag color="blue" style={{ marginTop: 12 }}>✓ 当前采用此结果</Tag>
                        )}
                        {((uploadResult.data as Record<string, unknown>).engine_comparison?.llm_confidence as number || 0) === 0 && (
                          <Tag color="default" style={{ marginTop: 12 }}>LLM未配置或连接失败</Tag>
                        )}
                      </Card>
                    </Col>
                  </Row>
                  <div style={{ marginTop: 12, padding: 8, background: '#f5f5f5', borderRadius: 4, fontSize: 12 }}>
                    <Text type="secondary">💡 置信度计算规则：已提取字段数 / 总字段数。规则引擎基于正则表达式提取，LLM基于大模型理解。</Text>
                  </div>
                </Card>
              )}

              <Row gutter={16} style={{ marginBottom: 16 }}>
                <Col span={4}>
                  <Card size="small" title="文件格式">
                    <Text strong>{FILE_FORMAT_LABELS[(uploadResult.data as Record<string, unknown>).file_format as string] || (uploadResult.data as Record<string, unknown>).file_format || '未知'}</Text>
                  </Card>
                </Col>
                <Col span={4}>
                  <Card size="small" title="文档类型">
                    <Text strong>{DOCUMENT_TYPE_LABELS[(uploadResult.data as Record<string, unknown>).document_type as string] || (uploadResult.data as Record<string, unknown>).document_type || '未知'}</Text>
                  </Card>
                </Col>
                <Col span={4}>
                  <Card size="small" title="置信度">
                    <Text strong style={{ color: ((uploadResult.data as Record<string, unknown>).confidence as number || 0) >= 0.8 ? '#52c41a' : '#faad14' }}>
                      {(((uploadResult.data as Record<string, unknown>).confidence as number || 0) * 100).toFixed(1)}%
                    </Text>
                  </Card>
                </Col>
                <Col span={4}>
                  <Card size="small" title="引擎类型">
                    <Text strong>{(uploadResult.data as Record<string, unknown>).engine_type === 'rule' ? '规则引擎' : (uploadResult.data as Record<string, unknown>).engine_type === 'llm' ? 'LLM引擎' : (uploadResult.data as Record<string, unknown>).engine_type || '未知'}</Text>
                  </Card>
                </Col>
                <Col span={4}>
                  <Card size="small" title="耗时">
                    <Text strong>{((uploadResult.data as Record<string, unknown>).parse_duration_ms as number || 0).toFixed(0)} ms</Text>
                  </Card>
                </Col>
              </Row>

              <Card title="最终解析数据">
                <Collapse
                  defaultActiveKey={['1']}
                  items={[
                    {
                      key: '1',
                      label: '解析字段',
                      children: (() => {
                        const data = (uploadResult.data as Record<string, unknown>).data as Record<string, unknown> || {}
                        if (Object.keys(data).length === 0) {
                          return <Empty description="未提取到数据" />
                        }
                        return (
                          <Row gutter={16}>
                            {Object.entries(data).map(([key, value]) => (
                              <Col span={8} key={key}>
                                <div style={{ background: '#fafafa', padding: 8, borderRadius: 4 }}>
                                  <Text type="secondary">{key}:</Text>
                                  <Text strong style={{ marginLeft: 8 }}>{value !== null && value !== undefined ? String(value) : '空'}</Text>
                                </div>
                              </Col>
                            ))}
                          </Row>
                        )
                      })(),
                    },
                    {
                      key: '2',
                      label: '原始文本',
                      children: (uploadResult.data as Record<string, unknown>).raw_text ? (
                        <pre style={{ background: '#f5f5f5', padding: 12, maxHeight: 300, overflowY: 'auto', whiteSpace: 'pre-wrap' }}>
                          {(uploadResult.data as Record<string, unknown>).raw_text}
                        </pre>
                      ) : (
                        <Empty description="无原始文本" />
                      ),
                    },
                    {
                      key: '3',
                      label: '完整JSON',
                      children: (
                        <pre style={{ background: '#f5f5f5', padding: 12, maxHeight: 300, overflowY: 'auto' }}>
                          {JSON.stringify(uploadResult.data, null, 2)}
                        </pre>
                      ),
                    },
                  ]}
                />
              </Card>
            </div>
          )}
        </Card>
      )}

      <Card
        title="文件解析测试"
        extra={
          <Space>
            <input
              type="file"
              accept=".pdf,.xlsx,.xls,.csv,.xml,.ofd,.jpg,.jpeg,.png,.doc,.docx,.txt"
              onChange={handleFileUpload}
              style={{ display: 'none' }}
              id="parser-file-upload"
            />
            <Button
              type="primary"
              icon={<UploadOutlined />}
              onClick={() => document.getElementById('parser-file-upload')?.click()}
              loading={uploading}
            >
              {uploading ? '解析中...' : '上传文件测试'}
            </Button>
          </Space>
        }
        style={{ marginBottom: 24 }}
      >
        <Text type="secondary">
          支持格式：PDF、Excel、CSV、XML、OFD、图片、Word、TXT
          <br />
          支持类型：发票、银行流水、合同协议、入库单、工资表、费用单据、收据凭证
        </Text>
      </Card>

      <Card title="各阶段耗时统计" style={{ marginBottom: 24 }}>
        <Table
          dataSource={stats?.stage_stats ? Object.entries(stats.stage_stats).map(([stage, data]) => ({
            key: stage,
            stage,
            ...data,
          })) : []}
          columns={StageStatsColumns}
          pagination={false}
          rowKey="stage"
          locale={{ emptyText: '暂无阶段统计数据' }}
        />
      </Card>

      <Card title="按文件格式统计" style={{ marginBottom: 24 }}>
        <Table
          dataSource={stats?.format_stats ? Object.entries(stats.format_stats).map(([format, data]) => ({
            key: format,
            format: FILE_FORMAT_LABELS[format] || format,
            ...data,
          })) : []}
          columns={FormatStatsColumns}
          pagination={false}
          rowKey="key"
          locale={{ emptyText: '暂无格式统计数据' }}
        />
      </Card>

      <Card title="按文档类型统计" style={{ marginBottom: 24 }}>
        <Table
          dataSource={stats?.doctype_stats ? Object.entries(stats.doctype_stats).map(([doctype, data]) => ({
            key: doctype,
            doctype: DOCUMENT_TYPE_LABELS[doctype] || doctype,
            ...data,
          })) : []}
          columns={DoctypeStatsColumns}
          pagination={false}
          rowKey="key"
          locale={{ emptyText: '暂无文档类型统计数据' }}
        />
      </Card>

      {stats?.error_stats && Object.keys(stats.error_stats).length > 0 && (
        <Card title="错误类型统计" style={{ marginBottom: 24 }}>
          <Table
            dataSource={Object.entries(stats.error_stats).map(([error_type, count]) => ({
              key: error_type,
              error_type,
              count,
            }))}
            columns={[
              { title: '错误类型', dataIndex: 'error_type', key: 'error_type' },
              { title: '发生次数', dataIndex: 'count', key: 'count' },
            ]}
            pagination={false}
            rowKey="key"
          />
        </Card>
      )}

      <Modal
        title="📊 选择要解析的工作表"
        open={excelSheetsVisible}
        onOk={handleParseWithSheet}
        onCancel={() => {
          setExcelSheetsVisible(false)
          setPendingFile(null)
          setExcelSheets([])
          setSelectedSheet('')
        }}
        okText="开始解析"
        cancelText="取消"
        width={700}
      >
        <Alert
          message="Excel文件包含多个工作表，请选择要解析的工作表"
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
        />
        <Spin spinning={loadingSheets} tip="正在读取工作表...">
          <List
            dataSource={excelSheets}
            renderItem={(sheet) => (
              <List.Item
                onClick={() => setSelectedSheet(sheet.name)}
                style={{
                  cursor: 'pointer',
                  padding: '12px 16px',
                  border: selectedSheet === sheet.name ? '2px solid #1890ff' : '1px solid #d9d9d9',
                  borderRadius: 4,
                  marginBottom: 8,
                  background: selectedSheet === sheet.name ? '#e6f7ff' : '#fff',
                }}
              >
                <List.Item.Meta
                  title={
                    <Space>
                      <Text strong style={{ fontSize: 16 }}>{sheet.name}</Text>
                      {selectedSheet === sheet.name && <Tag color="blue">已选择</Tag>}
                    </Space>
                  }
                  description={
                    <div>
                      <Text type="secondary">行数: {sheet.rows} 行</Text>
                      <Divider type="vertical" />
                      <Text type="secondary">列数: {sheet.columns.length} 列</Text>
                      <br />
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        列名: {sheet.columns.slice(0, 5).join(', ')}{sheet.columns.length > 5 ? '...' : ''}
                      </Text>
                    </div>
                  }
                />
              </List.Item>
            )}
          />
        </Spin>
      </Modal>
    </div>
  )
}
