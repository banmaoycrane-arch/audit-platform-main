import { useEffect, useState } from 'react'
import {
  Button,
  Card,
  Col,
  Descriptions,
  Row,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import { DownloadOutlined, FileProtectOutlined, ReloadOutlined, SyncOutlined } from '@ant-design/icons'
import { api, type WorkpaperIndex } from '../../api/client'
import { useAuthStore } from '../../stores/authStore'

const { Title, Paragraph } = Typography

const STATUS_COLOR: Record<string, string> = {
  draft: 'default',
  submitted: 'processing',
  reviewed: 'success',
  superseded: 'warning',
}

export function WorkpapersPage() {
  const { currentLedgerId } = useAuthStore()
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
        value ? <Tag color={STATUS_COLOR[value] || 'default'}>{value}</Tag> : '-',
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
              管理底稿索引号与版本历史；上传解析归档后自动挂接 v1.0，支持修订留痕与目录导出。
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
            title={`底稿详情 · ${selected.index_no} ${selected.title}`}
            extra={<Button type="link" onClick={() => setSelected(null)}>关闭</Button>}
          >
            <Descriptions bordered size="small" column={{ xs: 1, sm: 2 }}>
              <Descriptions.Item label="审计领域">{selected.audit_area || '-'}</Descriptions.Item>
              <Descriptions.Item label="归档路径">{selected.archive_path || '-'}</Descriptions.Item>
              <Descriptions.Item label="模块">{selected.source_module_key || '-'}</Descriptions.Item>
              <Descriptions.Item label="当前版本">{selected.current_version_no || '-'}</Descriptions.Item>
            </Descriptions>
            <Table
              style={{ marginTop: 16 }}
              rowKey="id"
              size="small"
              columns={versionColumns}
              dataSource={selected.versions}
              pagination={false}
            />
          </Card>
        )}
      </Space>
    </div>
  )
}
