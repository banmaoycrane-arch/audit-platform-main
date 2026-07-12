import { useCallback, useEffect, useState } from 'react'
import {
  Button,
  Card,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import { CheckOutlined, CloseOutlined, ThunderboltOutlined } from '@ant-design/icons'
import { api, type EvolutionProposal } from '../api/client'

const { Title, Text } = Typography

const SOURCE_LABEL: Record<string, string> = {
  production_correction: '生产改错',
  top3_scan: 'TOP3 扫描',
  parser_evolution_loop: 'TOP3 扫描',
}

export function ParserEvolutionPage() {
  const [loading, setLoading] = useState(false)
  const [running, setRunning] = useState(false)
  const [nightlyRunning, setNightlyRunning] = useState(false)
  const [proposals, setProposals] = useState<EvolutionProposal[]>([])
  const [selected, setSelected] = useState<number[]>([])

  const loadProposals = useCallback(async () => {
    setLoading(true)
    try {
      const res = await api.listEvolutionProposals({ status: 'draft', limit: 200 })
      setProposals(res.items || [])
    } catch {
      message.error('加载提案失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadProposals()
  }, [loadProposals])

  const runEvolution = async () => {
    setRunning(true)
    try {
      const res = await api.runEvolutionScan()
      message.success(`TOP3 扫描完成：新增 ${res.new_proposals} 条提案（${res.run_id}）`)
      await loadProposals()
    } catch {
      message.error('TOP3 扫描失败')
    } finally {
      setRunning(false)
    }
  }

  const runNightly = async () => {
    setNightlyRunning(true)
    try {
      const res = await api.runNightlyRegression()
      message.success(`Nightly 回归完成（${res.run_id}）`)
    } catch {
      message.error('Nightly 回归失败')
    } finally {
      setNightlyRunning(false)
    }
  }

  const batchApprove = async () => {
    if (selected.length === 0) {
      message.warning('请先勾选要采纳的提案')
      return
    }
    try {
      const res = await api.batchApproveEvolutionProposals(selected, 'ui')
      message.success(`已采纳 ${res.approved_count} 条规则，后续解析自动生效`)
      setSelected([])
      await loadProposals()
    } catch {
      message.error('批量采纳失败')
    }
  }

  const batchReject = async () => {
    if (selected.length === 0) {
      message.warning('请先勾选要驳回的提案')
      return
    }
    try {
      const res = await api.batchRejectEvolutionProposals(selected, '用户批量驳回')
      message.success(`已驳回 ${res.rejected_count} 条`)
      setSelected([])
      await loadProposals()
    } catch {
      message.error('批量驳回失败')
    }
  }

  const renderProposalSummary = (r: EvolutionProposal) => {
    if (r.rule_type === 'column_header') {
      return (
        <span>
          <Text strong>{r.source_header}</Text> → {r.target_field}
        </span>
      )
    }
    if (r.original_value != null && r.original_value !== '') {
      return (
        <span>
          {String(r.original_value)} → <Text strong>{String(r.corrected_value)}</Text>
          <Text type="secondary"> ({r.target_field})</Text>
        </span>
      )
    }
    return (
      <span>
        <Text strong>{String(r.corrected_value ?? '—')}</Text>
        <Text type="secondary"> ({r.target_field})</Text>
      </span>
    )
  }

  return (
    <div style={{ padding: 24 }}>
      <Title level={3}>解析进化审批台</Title>
      <Text type="secondary">
        生产改错自动入队（主信号）；TOP3 nightly 回归仅作标尺。批量采纳后规则对后续解析生效。
      </Text>

      <Card style={{ marginTop: 16 }}>
        <Space wrap>
          <Button loading={nightlyRunning} onClick={runNightly}>
            运行 Nightly 回归（TOP3 标尺）
          </Button>
          <Button
            icon={<ThunderboltOutlined />}
            loading={running}
            onClick={runEvolution}
          >
            TOP3 表头扫描（可选）
          </Button>
          <Button
            type="primary"
            icon={<CheckOutlined />}
            disabled={selected.length === 0}
            onClick={batchApprove}
          >
            批量采纳 ({selected.length})
          </Button>
          <Button
            danger
            icon={<CloseOutlined />}
            disabled={selected.length === 0}
            onClick={batchReject}
          >
            批量驳回
          </Button>
          <Button onClick={loadProposals}>刷新</Button>
        </Space>
      </Card>

      <Table
        style={{ marginTop: 16 }}
        rowKey="id"
        loading={loading}
        dataSource={proposals}
        rowSelection={{
          selectedRowKeys: selected,
          onChange: (keys) => setSelected(keys as number[]),
        }}
        columns={[
          { title: 'ID', dataIndex: 'id', width: 70 },
          {
            title: '来源',
            dataIndex: 'source',
            width: 110,
            render: (v: string | null) => (
              <Tag color={v === 'production_correction' ? 'blue' : 'default'}>
                {SOURCE_LABEL[v || ''] || v || '—'}
              </Tag>
            ),
          },
          {
            title: '规则类型',
            dataIndex: 'rule_type',
            width: 120,
            render: (v: string) => <Tag>{v}</Tag>,
          },
          {
            title: '文档类型',
            dataIndex: 'document_type',
            width: 130,
            render: (v: string) => <Tag>{v}</Tag>,
          },
          {
            title: '提案内容',
            render: (_: unknown, r: EvolutionProposal) => renderProposalSummary(r),
          },
          {
            title: '文件',
            render: (_: unknown, r: EvolutionProposal) => r.file_name || r.evidence_file || '—',
            ellipsis: true,
          },
          {
            title: '修正#',
            dataIndex: 'source_correction_id',
            width: 80,
            render: (v: number | null) => v ?? '—',
          },
          { title: '说明', dataIndex: 'shadow_note', ellipsis: true },
          { title: '时间', dataIndex: 'created_at', width: 180 },
        ]}
        pagination={{ pageSize: 20 }}
      />
    </div>
  )
}
