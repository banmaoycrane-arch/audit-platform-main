/**
 * E2 导入聚类候选弹窗：
 * 1. 选导入任务（可选）+ 日期范围 + 最小阈值
 * 2. 调 suggestEconomicEventClusters 拉候选
 * 3. 候选列表：可勾选、可编辑标题、显示分录数与金额
 * 4. 一键创建 → confirmEconomicEventClusters → 关闭并刷新
 *
 * 财务口径：聚类只发生在已入账分录上；已挂在 import_cluster 事件上的分录会被自动排除（幂等）。
 */
import { useEffect, useState } from 'react'
import {
  Alert,
  Button,
  Checkbox,
  DatePicker,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import dayjs from 'dayjs'
import {
  api,
  type EconomicEventClusterSuggestion,
  type ImportJob,
} from '../../api/client'

const { Text } = Typography
const { RangePicker } = DatePicker

type Props = {
  open: boolean
  ledgerId: number
  onClose: () => void
  onConfirmed: () => void
}

type EditableRow = EconomicEventClusterSuggestion & {
  selected: boolean
  editedTitle: string
}

export function ClusterSuggestModal({ open, ledgerId, onClose, onConfirmed }: Props) {
  const [importJobs, setImportJobs] = useState<ImportJob[]>([])
  const [importJobId, setImportJobId] = useState<number | undefined>()
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null] | null>(null)
  const [minEntries, setMinEntries] = useState(2)
  const [loading, setLoading] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [rows, setRows] = useState<EditableRow[]>([])

  // 拉取导入任务列表（按当前账簿过滤）
  useEffect(() => {
    if (!open) return
    api
      .listImportJobs(ledgerId)
      .then((jobs) => setImportJobs(jobs.filter((j) => j.status === 'completed' || j.status === 'parsed')))
      .catch((e: Error) => message.error(e.message || '加载导入任务失败'))
  }, [open, ledgerId])

  // 打开时重置
  useEffect(() => {
    if (open) {
      setImportJobId(undefined)
      setDateRange(null)
      setMinEntries(2)
      setRows([])
    }
  }, [open])

  const handleSuggest = async () => {
    setLoading(true)
    try {
      const payload: Parameters<typeof api.suggestEconomicEventClusters>[1] = {
        min_entries: minEntries,
      }
      if (importJobId != null) payload.import_job_id = importJobId
      if (dateRange && dateRange[0] && dateRange[1]) {
        payload.date_from = dateRange[0].format('YYYY-MM-DD')
        payload.date_to = dateRange[1].format('YYYY-MM-DD')
      }
      const suggestions = await api.suggestEconomicEventClusters(ledgerId, payload)
      const editable: EditableRow[] = suggestions.map((s) => ({
        ...s,
        selected: true,
        editedTitle: s.title,
      }))
      setRows(editable)
      if (editable.length === 0) {
        message.info('未发现可聚类的候选事件（已入账分录可能已挂载到既有导入聚类事件）')
      }
    } catch (e: any) {
      message.error(e.message || '聚类建议失败')
    } finally {
      setLoading(false)
    }
  }

  const handleToggle = (clusterKey: string, checked: boolean) => {
    setRows((prev) =>
      prev.map((r) => (r.cluster_key === clusterKey ? { ...r, selected: checked } : r)),
    )
  }

  const handleTitleChange = (clusterKey: string, title: string) => {
    setRows((prev) =>
      prev.map((r) => (r.cluster_key === clusterKey ? { ...r, editedTitle: title } : r)),
    )
  }

  const handleConfirm = async () => {
    const selected = rows.filter((r) => r.selected)
    if (selected.length === 0) {
      message.warning('请至少勾选 1 个候选事件')
      return
    }
    setConfirming(true)
    try {
      const created = await api.confirmEconomicEventClusters(ledgerId, {
        import_job_id: importJobId ?? null,
        clusters: selected.map((r) => ({
          title: r.editedTitle,
          event_type: 'import_cluster',
          occurred_on: r.occurred_on,
          entry_ids: r.entry_ids,
        })),
      })
      message.success(`已创建 ${created.length} 个事件工单，状态：归集中`)
      onConfirmed()
      onClose()
    } catch (e: any) {
      message.error(e.message || '创建事件失败')
    } finally {
      setConfirming(false)
    }
  }

  const selectedCount = rows.filter((r) => r.selected).length
  const totalEntries = rows.filter((r) => r.selected).reduce((s, r) => s + r.entry_count, 0)
  const totalAmount = rows
    .filter((r) => r.selected)
    .reduce((s, r) => s + Number(r.display_amount), 0)

  const columns = [
    {
      title: '勾选',
      key: 'selected',
      width: 60,
      render: (_: unknown, row: EditableRow) => (
        <Checkbox
          checked={row.selected}
          onChange={(e) => handleToggle(row.cluster_key, e.target.checked)}
        />
      ),
    },
    {
      title: '事件标题',
      key: 'title',
      render: (_: unknown, row: EditableRow) => (
        <Input
          value={row.editedTitle}
          onChange={(e) => handleTitleChange(row.cluster_key, e.target.value)}
          maxLength={300}
          size="small"
        />
      ),
    },
    {
      title: '往来',
      dataIndex: 'counterparty_name',
      key: 'counterparty_name',
      width: 140,
      render: (v: string) => <Tag>{v}</Tag>,
    },
    {
      title: '发生日',
      dataIndex: 'occurred_on',
      key: 'occurred_on',
      width: 120,
      render: (v: string | null) => (v ? dayjs(v).format('YYYY-MM-DD') : '-'),
    },
    {
      title: '分录数',
      dataIndex: 'entry_count',
      key: 'entry_count',
      width: 80,
      align: 'right' as const,
    },
    {
      title: '金额合计',
      dataIndex: 'display_amount',
      key: 'display_amount',
      width: 130,
      align: 'right' as const,
      render: (v: string) => Number(v).toLocaleString('zh-CN', { minimumFractionDigits: 2 }),
    },
  ]

  return (
    <Modal
      title="从导入生成事件工单（E2 聚类建议）"
      open={open}
      onCancel={onClose}
      width={900}
      destroyOnClose
      footer={[
        <Button key="cancel" onClick={onClose}>
          取消
        </Button>,
        <Button key="suggest" loading={loading} onClick={handleSuggest}>
          生成候选
        </Button>,
        <Button
          key="confirm"
          type="primary"
          loading={confirming}
          disabled={rows.length === 0 || selectedCount === 0}
          onClick={handleConfirm}
        >
          创建 {selectedCount} 个事件
        </Button>,
      ]}
    >
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <Alert
          type="info"
          showIcon
          message="聚类规则：往来 + 月份（同往来同月且分录数 ≥ 阈值 才生成候选）"
          description="已挂在「导入聚类」类型事件上的分录会被自动排除（幂等）。事件创建后状态自动推进到「归集中」。"
        />

        <Space wrap>
          <span>导入任务：</span>
          <Select
            style={{ width: 280 }}
            value={importJobId}
            onChange={setImportJobId}
            placeholder="全部已入账分录"
            allowClear
            options={importJobs.map((j) => ({
              value: j.id,
              label: `#${j.id} · ${j.source_type} · ${j.entry_count} 分录 · ${dayjs(j.created_at).format('YYYY-MM-DD')}`,
            }))}
          />
          <span>日期范围：</span>
          <RangePicker
            value={dateRange as any}
            onChange={(v) => setDateRange(v as [dayjs.Dayjs | null, dayjs.Dayjs | null] | null)}
            size="middle"
          />
          <span>最小阈值：</span>
          <InputNumber
            min={1}
            max={100}
            value={minEntries}
            onChange={(v) => setMinEntries(v ?? 2)}
            style={{ width: 80 }}
          />
        </Space>

        {rows.length > 0 && (
          <>
            <Table
              rowKey="cluster_key"
              size="small"
              columns={columns}
              dataSource={rows}
              pagination={false}
              scroll={{ y: 320 }}
            />
            <Text type="secondary">
              已勾选 {selectedCount} 个候选 · 合计 {totalEntries} 条分录 · 金额合计{' '}
              {totalAmount.toLocaleString('zh-CN', { minimumFractionDigits: 2 })}
            </Text>
          </>
        )}
      </Space>
    </Modal>
  )
}
