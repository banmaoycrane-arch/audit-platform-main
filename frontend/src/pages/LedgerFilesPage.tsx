import { useEffect, useState } from 'react'
import { Alert, Button, Card, Form, Input, Modal, Popconfirm, Select, Space, Table, Tag, Typography, message } from 'antd'
import { DeleteOutlined, EditOutlined, FileTextOutlined, ReloadOutlined } from '@ant-design/icons'
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

const FILE_TYPE_OPTIONS = [
  { value: 'invoice', label: '发票' },
  { value: 'contract', label: '合同' },
  { value: 'voucher', label: '凭证' },
  { value: 'statement', label: '银行对账单' },
  { value: 'receipt', label: '收据' },
  { value: 'other', label: '其他' },
]

interface EditFileForm {
  filename: string
  file_type: string
  notes: string
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
    archive_category?: string
  }>({})
  const [bindingFileId, setBindingFileId] = useState<number | null>(null)

  // 编辑相关状态
  const [editModalVisible, setEditModalVisible] = useState(false)
  const [editingFile, setEditingFile] = useState<SourceFileRead | null>(null)
  const [editLoading, setEditLoading] = useState(false)
  const [editForm] = Form.useForm<EditFileForm>()

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
      message.error(error.message || '加载支持性文件失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadData()
  }, [currentLedgerId, filters.counterparty_id, filters.file_type, filters.parse_status, filters.archive_category])

  const handleBindCounterparty = async (fileId: number, counterpartyId: number | null) => {
    try {
      const updated = await api.bindFileCounterparty(fileId, counterpartyId)
      setFiles((prev) => prev.map((item) => (item.id === updated.id ? updated : item)))
      message.success(counterpartyId ? '已保存文件与往来单位关联' : '已取消文件关联')
    } catch (error: any) {
      message.error(error.message || '保存文件关联失败')
    }
  }

  const handleBindLedger = async (fileId: number, ledgerId: number | null) => {
    setBindingFileId(fileId)
    try {
      const updated = await api.bindFileLedger(fileId, ledgerId)
      setFiles((prev) => prev.map((item) => (item.id === updated.id ? updated : item)))
      message.success(ledgerId ? '已将文件绑定到账套' : '已取消账套绑定')
    } catch (error: any) {
      message.error(error.message || '绑定账套失败')
    } finally {
      setBindingFileId(null)
    }
  }

  // 打开编辑弹窗
  const handleOpenEdit = (file: SourceFileRead) => {
    setEditingFile(file)
    editForm.setFieldsValue({
      filename: file.filename,
      file_type: file.file_type,
      notes: file.notes || '',
    })
    setEditModalVisible(true)
  }

  // 提交编辑
  const handleEditSubmit = async () => {
    if (!editingFile) return
    try {
      const values = await editForm.validateFields()
      setEditLoading(true)
      const updated = await api.updateFile(editingFile.id, {
        filename: values.filename,
        file_type: values.file_type,
        notes: values.notes || undefined,
      })
      setFiles((prev) => prev.map((item) => (item.id === updated.id ? updated : item)))
      message.success('文件信息已更新')
      setEditModalVisible(false)
    } catch (error: any) {
      if (error.errorFields) return // 表单验证错误
      message.error(error.message || '更新文件失败')
    } finally {
      setEditLoading(false)
    }
  }

  // 删除文件
  const handleDeleteFile = async (fileId: number) => {
    try {
      await api.deleteFile(fileId)
      setFiles((prev) => prev.filter((item) => item.id !== fileId))
      message.success('文件已删除')
    } catch (error: any) {
      message.error(error.message || '删除文件失败')
    }
  }

  const fileTypeOptions = Array.from(new Set(files.map((item) => item.file_type).filter(Boolean))).map((value) => ({
    value,
    label: value,
  }))

  const archiveCategoryOptions = Array.from(
    new Set(files.map((item) => item.archive_category).filter(Boolean))
  ).map((value) => ({ value: value as string, label: value as string }))

  return (
    <Card>
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <div>
          <Title level={4} style={{ margin: 0 }}>
            <FileTextOutlined /> 支持性文件
          </Title>
          <Paragraph type="secondary" style={{ marginBottom: 0 }}>
            支持性文件是合同、发票、银行回单、客户供应商资料等原始证据，需先归属账簿；进入审计项目后再形成“账簿 + 项目”双绑定。
            这里仅维护文件元数据和关联关系，不把复核意见写回原件。当前账套：{currentLedger ? currentLedger.name : currentLedgerId || '未选择'}
          </Paragraph>
        </div>

        {!currentLedgerId && !loading && (
          <Alert
            type="warning"
            showIcon
            title="尚未选择账套"
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
          <Form.Item label="归档分类">
            <Select
              allowClear
              style={{ width: 160 }}
              placeholder="全部分类"
              value={filters.archive_category}
              onChange={(value) => setFilters((prev) => ({ ...prev, archive_category: value }))}
              options={archiveCategoryOptions}
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
            {
              title: '账套',
              key: 'ledger',
              width: 180,
              render: (_: unknown, row: SourceFileRead) => {
                return (
                  <Select
                    allowClear
                    showSearch
                    style={{ width: 160 }}
                    placeholder="绑定账套"
                    optionFilterProp="label"
                    loading={bindingFileId === row.id}
                    value={row.ledger_id || undefined}
                    onChange={(value) => handleBindLedger(row.id, value || null)}
                    options={userLedgers.map((l) => ({ value: l.id, label: l.name }))}
                    notFoundContent={null}
                  />
                )
              },
            },
            {
              title: '文件名',
              dataIndex: 'filename',
              key: 'filename',
              width: 200,
              ellipsis: true,
            },
            {
              title: '归档路径',
              key: 'archive_path',
              width: 240,
              ellipsis: true,
              render: (_: unknown, row: SourceFileRead) => row.archive_path || '-',
            },
            {
              title: '项目',
              key: 'project_name',
              width: 140,
              ellipsis: true,
              render: (_: unknown, row: SourceFileRead) => row.project_name || '-',
            },
            {
              title: '期间',
              key: 'period_code',
              width: 100,
              render: (_: unknown, row: SourceFileRead) => row.period_code || '-',
            },
            {
              title: '类型',
              dataIndex: 'file_type',
              key: 'file_type',
              width: 100,
            },
            {
              title: '解析状态',
              dataIndex: 'parse_status',
              key: 'parse_status',
              width: 100,
              render: (value: string) => <Tag color={PARSE_STATUS_COLOR[value] || 'default'}>{PARSE_STATUS_LABEL[value] || value}</Tag>,
            },
            {
              title: '备注',
              key: 'notes',
              width: 150,
              ellipsis: true,
              render: (_: unknown, row: SourceFileRead) => row.notes || '-',
            },
            {
              title: '解析摘要',
              key: 'parse_summary',
              width: 200,
              ellipsis: true,
              render: (_: unknown, row: SourceFileRead) => row.parse_summary || row.parse_feedback?.summary || row.raw_text_preview || '-',
            },
            {
              title: '客户/往来单位',
              key: 'counterparty',
              width: 200,
              render: (_: unknown, row: SourceFileRead) => (
                <Select
                  allowClear
                  showSearch
                  style={{ width: 180 }}
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
              width: 180,
              render: (_: unknown, row: SourceFileRead) => (
                <Space direction="vertical" size={0}>
                  <Text>{row.customer_context?.match_source || '未匹配'}</Text>
                  <Text type="secondary" style={{ fontSize: 11 }}>{row.customer_context?.confidence_note || '可手工选择客户/往来单位'}</Text>
                </Space>
              ),
            },
            { title: '上传时间', dataIndex: 'created_at', key: 'created_at', width: 160 },
            {
              title: '操作',
              key: 'actions',
              width: 120,
              fixed: 'right',
              render: (_: unknown, row: SourceFileRead) => (
                <Space size="small">
                  <Button
                    type="text"
                    size="small"
                    icon={<EditOutlined />}
                    onClick={() => handleOpenEdit(row)}
                  />
                  <Popconfirm
                    title="删除文件"
                    description="确定要删除此支持性文件记录吗？此操作不可恢复。"
                    onConfirm={() => handleDeleteFile(row.id)}
                    okText="删除"
                    cancelText="取消"
                    okButtonProps={{ danger: true }}
                  >
                    <Button type="text" size="small" danger icon={<DeleteOutlined />} />
                  </Popconfirm>
                </Space>
              ),
            },
          ]}
        />
      </Space>

      {/* 编辑文件弹窗 */}
      <Modal
        title="编辑文件"
        open={editModalVisible}
        onOk={handleEditSubmit}
        onCancel={() => setEditModalVisible(false)}
        confirmLoading={editLoading}
        okText="保存"
        cancelText="取消"
        width={500}
      >
        <Form form={editForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            name="filename"
            label="文件名"
            rules={[{ required: true, message: '请输入文件名' }]}
          >
            <Input placeholder="请输入文件名" />
          </Form.Item>
          <Form.Item
            name="file_type"
            label="文件类型"
            rules={[{ required: true, message: '请选择文件类型' }]}
          >
            <Select placeholder="请选择文件类型" options={FILE_TYPE_OPTIONS} />
          </Form.Item>
          <Form.Item name="notes" label="备注">
            <Input.TextArea rows={3} placeholder="请输入备注信息（选填）" />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  )
}
