import { useEffect, useState } from 'react'
import { Alert, Button, Card, Form, Select, Space, Table, Tag, Typography, message } from 'antd'
import { FileTextOutlined, ReloadOutlined } from '@ant-design/icons'
import { api } from '../api/client'
import type { Counterparty, SourceFileRead } from '../api/client'
import { useAuthStore } from '../stores/authStore'

const { Paragraph, Title, Text } = Typography

const PARSE_STATUS_LABEL: Record<string, string> = {
  pending: '待解析',
  completed: '已解析',
  failed: '解析失败',
  processing: '解析中',
}

const PARSE_STATUS_COLOR: Record<string, string> = {
  pending: 'default',
  completed: 'green',
  failed: 'red',
  processing: 'blue',
}

export function LedgerFilesPage() {
  const { currentLedgerId, setCurrentLedger, userLedgers, setUserLedgers } = useAuthStore()
  const [files, setFiles] = useState<SourceFileRead[]>([])
  const [counterparties, setCounterparties] = useState<Counterparty[]>([])
  const [loading, setLoading] = useState(false)
  const [filters, setFilters] = useState<{
    counterparty_id?: number
    file_type?: string
    parse_status?: string
  }>({})

  const currentLedger = userLedgers.find((ledger) => ledger.id === currentLedgerId)

  const ensureCurrentLedger = async () => {
    if (currentLedgerId) return currentLedgerId
    const ledgers = await api.listLedgers()
    setUserLedgers(ledgers)
    if (ledgers.length === 0) return null
    await api.switchLedger(ledgers[0].id)
    setCurrentLedger(ledgers[0].id)
    return ledgers[0].id
  }

  const loadData = async () => {
    setLoading(true)
    try {
      const ledgerId = await ensureCurrentLedger()
      if (!ledgerId) {
        setFiles([])
        setCounterparties([])
        return
      }
      const [fileResp, counterpartyResp] = await Promise.all([
        api.listLedgerFiles({ ledger_id: ledgerId, ...filters }),
        api.listCounterparties(),
      ])
      setFiles(fileResp)
      setCounterparties(counterpartyResp.filter((item) => item.is_active))
    } catch (error: any) {
      message.error(error.message || '加载账套文件失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadData()
  }, [currentLedgerId, filters.counterparty_id, filters.file_type, filters.parse_status])

  const handleBindCounterparty = async (fileId: number, counterpartyId: number | null) => {
    try {
      const updated = await api.bindFileCounterparty(fileId, counterpartyId)
      setFiles((prev) => prev.map((item) => (item.id === updated.id ? updated : item)))
      message.success(counterpartyId ? '已保存文件与往来单位关联' : '已取消文件关联')
    } catch (error: any) {
      message.error(error.message || '保存文件关联失败')
    }
  }

  const fileTypeOptions = Array.from(new Set(files.map((item) => item.file_type).filter(Boolean))).map((value) => ({
    value,
    label: value,
  }))

  return (
    <Card>
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <div>
          <Title level={4} style={{ margin: 0 }}>
            <FileTextOutlined /> 账套文件
          </Title>
          <Paragraph type="secondary" style={{ marginBottom: 0 }}>
            按账套归集原始凭证、合同、发票、银行流水等资料，并通过文件名、解析摘要和对方单位字段定位客户上下文。
            当前账套：{currentLedger ? currentLedger.name : currentLedgerId || '未选择'}
          </Paragraph>
        </div>

        {!currentLedgerId && !loading && (
          <Alert
            type="warning"
            showIcon
            message="尚未选择账套"
            description="请先在账套管理中创建或选择账套，系统不会在未选择账套时加载全量文件。"
          />
        )}

        <Form layout="inline">
          <Form.Item label="往来单位">
            <Select
              allowClear
              showSearch
              style={{ width: 220 }}
              placeholder="筛选客户/供应商"
              optionFilterProp="label"
              value={filters.counterparty_id}
              onChange={(value) => setFilters((prev) => ({ ...prev, counterparty_id: value }))}
              options={counterparties.map((item) => ({ value: item.id, label: item.name }))}
            />
          </Form.Item>
          <Form.Item label="文件类型">
            <Select
              allowClear
              style={{ width: 140 }}
              placeholder="全部类型"
              value={filters.file_type}
              onChange={(value) => setFilters((prev) => ({ ...prev, file_type: value }))}
              options={fileTypeOptions}
            />
          </Form.Item>
          <Form.Item label="解析状态">
            <Select
              allowClear
              style={{ width: 140 }}
              placeholder="全部状态"
              value={filters.parse_status}
              onChange={(value) => setFilters((prev) => ({ ...prev, parse_status: value }))}
              options={Object.entries(PARSE_STATUS_LABEL).map(([value, label]) => ({ value, label }))}
            />
          </Form.Item>
          <Button icon={<ReloadOutlined />} onClick={loadData}>刷新</Button>
        </Form>

        <Table
          rowKey="id"
          dataSource={files}
          loading={loading}
          size="small"
          pagination={{ pageSize: 20 }}
          columns={[
            { title: '文件名', dataIndex: 'filename', key: 'filename' },
            { title: '类型', dataIndex: 'file_type', key: 'file_type' },
            {
              title: '解析状态',
              dataIndex: 'parse_status',
              key: 'parse_status',
              render: (value: string) => <Tag color={PARSE_STATUS_COLOR[value] || 'default'}>{PARSE_STATUS_LABEL[value] || value}</Tag>,
            },
            {
              title: '解析摘要',
              key: 'parse_summary',
              render: (_: unknown, row: SourceFileRead) => row.parse_summary || row.parse_feedback?.summary || row.raw_text_preview || '-',
            },
            {
              title: '客户/往来单位',
              key: 'counterparty',
              render: (_: unknown, row: SourceFileRead) => (
                <Select
                  allowClear
                  showSearch
                  style={{ width: 220 }}
                  placeholder="手工选择"
                  optionFilterProp="label"
                  value={row.counterparty_id || undefined}
                  onChange={(value) => handleBindCounterparty(row.id, value || null)}
                  options={counterparties.map((item) => ({ value: item.id, label: item.name }))}
                />
              ),
            },
            {
              title: '匹配说明',
              key: 'match_note',
              render: (_: unknown, row: SourceFileRead) => (
                <Space direction="vertical" size={0}>
                  <Text>{row.customer_context?.match_source || '未匹配'}</Text>
                  <Text type="secondary">{row.customer_context?.confidence_note || '可手工选择客户/往来单位'}</Text>
                </Space>
              ),
            },
            { title: '上传时间', dataIndex: 'created_at', key: 'created_at' },
          ]}
        />
      </Space>
    </Card>
  )
}
