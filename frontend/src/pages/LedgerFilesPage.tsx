import { useEffect, useState } from 'react'
import { Alert, Button, Card, Form, Input, Modal, Popconfirm, Select, Space, Table, Tag, Typography, message } from 'antd'
import { DeleteOutlined, EditOutlined, FileTextOutlined, ReloadOutlined } from '@ant-design/icons'
import { api } from '../api/client'
import type { Counterparty, Ledger, Project, SourceFileRead } from '../api/client'
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

const getFileObjectNames = (file: SourceFileRead) => {
  const values = [
    ...(file.object_names || []),
    file.object_name,
    file.counterparty_name,
    file.customer_context?.counterparty_name,
    file.archive_context?.counterparty,
  ].filter(Boolean) as string[]
  return Array.from(new Set(values.map((item) => item.trim()).filter(Boolean)))
}

export function LedgerFilesPage() {
  const { currentLedgerId, setCurrentLedger, userLedgers, setUserLedgers } = useAuthStore()
  const [files, setFiles] = useState<SourceFileRead[]>([])
  const [projects, setProjects] = useState<Project[]>([])
  const [projectLedgers, setProjectLedgers] = useState<Ledger[]>([])
  const [counterparties, setCounterparties] = useState<Counterparty[]>([])
  const [loading, setLoading] = useState(false)
  const [filters, setFilters] = useState<{
    project_id?: number
    ledger_ids?: number[]
    counterparty_id?: number
    object_name?: string
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

  const ensureCurrentLedger = async () => {
    if (currentLedgerId) return currentLedgerId
    const ledgers = await api.listLedgers()
    setUserLedgers(ledgers)
    if (ledgers.length === 0) return null
    await api.switchLedger(ledgers[0].id)
    setCurrentLedger(ledgers[0].id)
    return ledgers[0].id
  }

  const loadProjects = async () => {
    const rows = (await api.listProjects()).filter((item) => item.status !== 'cancelled')
    setProjects(rows)
    if (!filters.project_id && rows.length > 0) {
      setFilters((prev) => ({ ...prev, project_id: rows[0].id }))
    }
  }

  const loadProjectLedgers = async (projectId?: number) => {
    if (!projectId) {
      setProjectLedgers([])
      return
    }
    const [projectRows, ledgerRows] = await Promise.all([
      api.listProjectLedgers(projectId),
      userLedgers.length > 0 ? Promise.resolve(userLedgers) : api.listLedgers(),
    ])
    if (userLedgers.length === 0 && ledgerRows.length > 0) setUserLedgers(ledgerRows)
    const rows = ledgerRows.filter((ledger) => projectRows.some((item) => item.id === ledger.id))
    setProjectLedgers(rows)
    setFilters((prev) => ({
      ...prev,
      ledger_ids: prev.ledger_ids?.filter((id) => rows.some((ledger) => ledger.id === id)),
      object_name: undefined,
      counterparty_id: undefined,
    }))
  }

  const loadData = async () => {
    setLoading(true)
    try {
      await ensureCurrentLedger()
      if (!filters.project_id) {
        setFiles([])
        setCounterparties([])
        return
      }
      const [fileResp, counterpartyResp] = await Promise.all([
        api.listLedgerFiles({
          project_id: filters.project_id,
          ledger_ids: filters.ledger_ids,
          counterparty_id: filters.counterparty_id,
          object_name: filters.object_name,
          file_type: filters.file_type,
          parse_status: filters.parse_status,
          archive_category: filters.archive_category,
        }),
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
    void loadProjects()
  }, [])

  useEffect(() => {
    void loadProjectLedgers(filters.project_id)
  }, [filters.project_id])

  useEffect(() => {
    void loadData()
  }, [currentLedgerId, filters.project_id, filters.ledger_ids?.join(','), filters.counterparty_id, filters.object_name, filters.file_type, filters.parse_status, filters.archive_category])

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
      message.success(ledgerId ? '已将文件绑定到账簿' : '已取消账簿绑定')
    } catch (error: any) {
      message.error(error.message || '绑定账簿失败')
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

  const objectNameOptions = Array.from(
    new Set(files.flatMap((item) => getFileObjectNames(item)).filter(Boolean))
  ).map((value) => ({ value, label: value }))

  return (
    <Card>
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <div>
          <Title level={4} style={{ margin: 0 }}>
            <FileTextOutlined /> 支持性文件
          </Title>
          <Paragraph type="secondary" style={{ marginBottom: 0 }}>
            支持性文件是合同、发票、银行回单、客户供应商资料等原始证据；当前页面按项目范围展示，项目内已绑定账簿的文件均可检索。
          </Paragraph>
        </div>

        {!filters.project_id && !loading && (
          <Alert
            type="warning"
            showIcon
            title="尚未选择项目"
            description="请先选择审计项目；页面将只加载该项目范围内、项目已绑定账簿下的支持性文件。"
          />
        )}

        <Form layout="inline">
          <Form.Item label="项目">
            <Select
              showSearch
              style={{ width: 220 }}
              placeholder="选择项目"
              optionFilterProp="label"
              value={filters.project_id}
              onChange={(value) => setFilters((prev) => ({ ...prev, project_id: value, ledger_ids: undefined, object_name: undefined, counterparty_id: undefined }))}
              options={projects.map((item) => ({ value: item.id, label: item.name }))}
            />
          </Form.Item>
          <Form.Item label="账簿">
            <Select
              allowClear
              mode="multiple"
              showSearch
              maxTagCount="responsive"
              style={{ width: 260 }}
              placeholder="全部项目账簿"
              optionFilterProp="label"
              value={filters.ledger_ids}
              onChange={(value) => setFilters((prev) => ({ ...prev, ledger_ids: value, object_name: undefined, counterparty_id: undefined }))}
              options={projectLedgers.map((item) => ({ value: item.id, label: item.name }))}
            />
          </Form.Item>
          <Form.Item label="往来对象">
            <Select
              allowClear
              showSearch
              style={{ width: 220 }}
              placeholder="按文件对象筛选"
              optionFilterProp="label"
              value={filters.object_name}
              onChange={(value) => setFilters((prev) => ({ ...prev, object_name: value }))}
              options={objectNameOptions}
            />
          </Form.Item>
          <Form.Item label="手工绑定单位">
            <Select
              allowClear
              showSearch
              style={{ width: 220 }}
              placeholder="筛选手工绑定单位"
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
              title: '账簿',
              key: 'ledger',
              width: 180,
              render: (_: unknown, row: SourceFileRead) => {
                return (
                  <Select
                    allowClear
                    showSearch
                    style={{ width: 160 }}
                    placeholder="绑定账簿"
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
              title: '往来对象',
              key: 'object_names',
              width: 220,
              render: (_: unknown, row: SourceFileRead) => {
                const names = getFileObjectNames(row)
                return names.length ? names.map((name) => <Tag key={name}>{name}</Tag>) : '-'
              },
            },
            {
              title: '手工绑定单位',
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
