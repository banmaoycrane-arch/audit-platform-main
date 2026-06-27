import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Row,
  Space,
  Statistic,
  Steps,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import { DownloadOutlined, FileProtectOutlined, ReloadOutlined, SyncOutlined } from '@ant-design/icons'
import { api, type WorkpaperIndex } from '../../api/client'
import { useAuthStore } from '../../stores/authStore'

const { Title, Paragraph, Text } = Typography

const STATUS_COLOR: Record<string, string> = {
  draft: 'default',
  submitted: 'processing',
  reviewed: 'success',
  superseded: 'warning',
}

const STATUS_LABEL: Record<string, string> = {
  draft: '草稿',
  submitted: '已提交',
  reviewed: '已复核',
  superseded: '已替代',
}

const PACKAGE_STEPS = [
  { title: '支持性文件', description: '合同、发票、回单等原始证据' },
  { title: '底稿版本', description: '电子表格或文件快照' },
  { title: '任务/分支', description: 'Issue 与 Branch 承接编制责任' },
  { title: 'PR 复核', description: 'Review 意见旁路留痕' },
  { title: '归档', description: '通过版本固化为 reviewed' },
]

const formatFileSize = (value?: number | null) => {
  if (!value) return '-'
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / 1024 / 1024).toFixed(2)} MB`
}

const getWorkbookSheetsText = (metadata: unknown) => {
  if (!metadata || typeof metadata !== 'object' || !('sheets' in metadata)) return '-'
  const sheets = (metadata as { sheets?: unknown }).sheets
  if (!Array.isArray(sheets) || sheets.length === 0) return '-'
  return sheets.join('、')
}

export function WorkpapersPage() {
  const { currentLedgerId } = useAuthStore()
  const [searchParams] = useSearchParams()
  const highlightVersionId = searchParams.get('version_id')
  const [indexes, setIndexes] = useState<WorkpaperIndex[]>([])
  const [selected, setSelected] = useState<WorkpaperIndex | null>(null)
  const [loading, setLoading] = useState(false)
  const [syncing, setSyncing] = useState(false)

  const loadData = () => {
    if (!currentLedgerId) return
    setLoading(true)
    api
      .listWorkpaperIndexes(currentLedgerId)
      .then((rows) => {
        setIndexes(rows)
        if (selected) {
          const refreshed = rows.find((row) => row.id === selected.id)
          if (refreshed) {
            api.getWorkpaperIndex(currentLedgerId, refreshed.id).then(setSelected).catch(() => setSelected(null))
          }
        }
      })
      .catch((error: Error) => message.error(error.message || '加载工作底稿失败'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadData()
  }, [currentLedgerId])

  const handleSync = async () => {
    if (!currentLedgerId) return
    setSyncing(true)
    try {
      const rows = await api.syncWorkpapersFromArchive(currentLedgerId)
      message.success(`已同步 ${rows.length} 条底稿索引`)
      loadData()
    } catch (error: any) {
      message.error(error.message || '同步失败')
    } finally {
      setSyncing(false)
    }
  }

  const handleExport = async () => {
    if (!currentLedgerId) return
    try {
      const catalog = await api.exportWorkpaperCatalog(currentLedgerId)
      const blob = new Blob([JSON.stringify(catalog, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `workpaper-catalog-ledger-${currentLedgerId}.json`
      link.click()
      URL.revokeObjectURL(url)
      message.success('底稿目录已导出')
    } catch (error: any) {
      message.error(error.message || '导出失败')
    }
  }

  const openDetail = async (row: WorkpaperIndex) => {
    if (!currentLedgerId) return
    try {
      const detail = await api.getWorkpaperIndex(currentLedgerId, row.id)
      setSelected(detail)
    } catch (error: any) {
      message.error(error.message || '加载底稿详情失败')
    }
  }

  const columns = [
    { title: '索引号', dataIndex: 'index_no', key: 'index_no', width: 100 },
    { title: '标题', dataIndex: 'title', key: 'title', ellipsis: true },
    { title: '审计领域', dataIndex: 'audit_area', key: 'audit_area', width: 120 },
    { title: '归档路径', dataIndex: 'archive_path', key: 'archive_path', ellipsis: true },
    { title: '版本数', dataIndex: 'version_count', key: 'version_count', width: 80 },
    {
      title: '当前版本',
      dataIndex: 'current_version_no',
      key: 'current_version_no',
      width: 100,
      render: (value: string | null) => value || '-',
    },
    {
      title: '状态',
      dataIndex: 'current_status',
      key: 'current_status',
      width: 100,
      render: (value: string | null) =>
        value ? <Tag color={STATUS_COLOR[value] || 'default'}>{STATUS_LABEL[value] || value}</Tag> : '-',
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_: unknown, row: WorkpaperIndex) => (
        <Button type="link" onClick={() => openDetail(row)}>
          详情
        </Button>
      ),
    },
  ]

  const versionColumns = [
    { title: '版本', dataIndex: 'version_no', key: 'version_no', width: 80 },
    { title: '文件名', dataIndex: 'filename', key: 'filename', ellipsis: true },
    { title: '类型', dataIndex: 'file_ext', key: 'file_ext', width: 80, render: (value: string | null) => value || '-' },
    {
      title: '文件大小',
      dataIndex: 'file_size',
      key: 'file_size',
      width: 100,
      render: (value: number | null) => formatFileSize(value),
    },
    {
      title: 'Sheet',
      dataIndex: 'sheet_count',
      key: 'sheet_count',
      width: 80,
      render: (value: number | null) => value ?? '-',
    },
    {
      title: 'Sheet 名称',
      dataIndex: 'workbook_metadata',
      key: 'workbook_metadata',
      width: 180,
      ellipsis: true,
      render: (value: unknown) => getWorkbookSheetsText(value),
    },
    {
      title: '文件哈希',
      dataIndex: 'file_hash',
      key: 'file_hash',
      width: 110,
      render: (value: string | null) => (value ? value.slice(0, 10) : '-'),
    },
    {
      title: '状态',
      dataIndex: 'status_label',
      key: 'status_label',
      width: 100,
      render: (value: string, row: { status: string }) => (
        <Tag color={STATUS_COLOR[row.status] || 'default'}>{value}</Tag>
      ),
    },
    { title: '修订说明', dataIndex: 'change_reason', key: 'change_reason', ellipsis: true },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 180 },
  ]

  const totalVersions = indexes.reduce((sum, item) => sum + item.version_count, 0)

  return (
    <div>
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <Title level={4} style={{ margin: 0 }}>
              <FileProtectOutlined /> 工作底稿库
            </Title>
            <Paragraph type="secondary" style={{ marginBottom: 0 }}>
              工作底稿是现场人员加工后的审计成果，不等同于合同、发票、回单等支持性文件原件；
              完整底稿包含电子表格文件、版本、Issue、Branch、PR、复核意见、评论标记和归档状态。
            </Paragraph>
          </div>
          <Space>
            <Button icon={<SyncOutlined />} loading={syncing} onClick={handleSync} disabled={!currentLedgerId}>
              同步归档底稿
            </Button>
            <Button icon={<ReloadOutlined />} onClick={loadData} loading={loading} disabled={!currentLedgerId}>
              刷新
            </Button>
            <Button type="primary" icon={<DownloadOutlined />} onClick={handleExport} disabled={!currentLedgerId}>
              导出目录
            </Button>
          </Space>
        </div>

        <Alert
          type="info"
          showIcon
          message="底稿协作包验收口径"
          description="支持性文件是不可随意篡改的原始证据；审计工作底稿是加工成果。复核意见、评论和标记独立留痕，不覆盖现场人员编制的底稿版本。"
        />

        <Card title="完整底稿协作包流程" size="small">
          <Steps size="small" current={selected?.current_status === 'reviewed' ? 4 : 1} items={PACKAGE_STEPS} />
        </Card>

        <Row gutter={16}>
          <Col xs={12} md={8}>
            <Card><Statistic title="底稿索引" value={indexes.length} /></Card>
          </Col>
          <Col xs={12} md={8}>
            <Card><Statistic title="版本总数" value={totalVersions} /></Card>
          </Col>
          <Col xs={24} md={8}>
            <Card><Statistic title="已复核" value={indexes.filter((i) => i.current_status === 'reviewed').length} /></Card>
          </Col>
        </Row>

        <Card title="底稿索引目录">
          <Table
            rowKey="id"
            loading={loading}
            columns={columns}
            dataSource={indexes}
            pagination={{ pageSize: 15 }}
            locale={{ emptyText: '暂无底稿索引，请先上传资料或点击「同步归档底稿」' }}
          />
        </Card>

        {selected && (
          <Card
            title={`底稿首页 · ${selected.index_no} ${selected.title}`}
            extra={<Button type="link" onClick={() => setSelected(null)}>关闭</Button>}
          >
            <Descriptions bordered size="small" column={{ xs: 1, sm: 2 }}>
              <Descriptions.Item label="审计领域">{selected.audit_area || '-'}</Descriptions.Item>
              <Descriptions.Item label="归档路径">{selected.archive_path || '-'}</Descriptions.Item>
              <Descriptions.Item label="模块">{selected.source_module_key || '-'}</Descriptions.Item>
              <Descriptions.Item label="当前版本">{selected.current_version_no || '-'}</Descriptions.Item>
              <Descriptions.Item label="协作包内容" span={2}>
                电子表格/文件版本 + Issue 任务 + Branch 工作分支 + PR 复核请求 + Review 复核意见 + 评论标记 + 通知 + 归档状态
              </Descriptions.Item>
              <Descriptions.Item label="复核口径" span={2}>
                复核人员认可的是下方明确版本；评论和标记旁路保存，不覆盖支持性文件原件或历史底稿版本。
              </Descriptions.Item>
              <Descriptions.Item label="版本提醒" span={2}>
                {highlightVersionId ? (
                  <Text type="warning">当前从通知跳转而来，请重点检查版本 ID：{highlightVersionId}</Text>
                ) : (
                  <Text type="secondary">如从通知进入，可通过通知中的版本 ID 核对下方版本记录。</Text>
                )}
              </Descriptions.Item>
            </Descriptions>
            <Table
              style={{ marginTop: 16 }}
              rowKey="id"
              size="small"
              columns={versionColumns}
              dataSource={selected.versions}
              rowClassName={(record) => (String(record.id) === highlightVersionId ? 'ant-table-row-selected' : '')}
              pagination={false}
              scroll={{ x: 1180 }}
            />
          </Card>
        )}
      </Space>
    </div>
  )
}
