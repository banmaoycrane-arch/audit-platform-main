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
import { AuditOutlined, ReloadOutlined } from '@ant-design/icons'
import { Link } from 'react-router-dom'
import { api, type PurchaseMatchResult } from '../../api/client'
import { useAuthStore } from '../../stores/authStore'
import { formatAmount } from '../../money'

const { Title, Paragraph } = Typography

const STATUS_COLOR: Record<string, string> = {
  matched: 'success',
  incomplete: 'warning',
  exception: 'error',
}

export function PurchaseMatchPage() {
  const { currentLedgerId } = useAuthStore()
  const [summary, setSummary] = useState<Awaited<ReturnType<typeof api.getPurchaseMatchSummary>> | null>(null)
  const [selected, setSelected] = useState<PurchaseMatchResult | null>(null)
  const [loading, setLoading] = useState(false)

  const loadData = () => {
    if (!currentLedgerId) return
    setLoading(true)
    api
      .getPurchaseMatchSummary(currentLedgerId)
      .then((data) => {
        setSummary(data)
        setSelected(data.results[0] || null)
      })
      .catch((error: Error) => message.error(error.message || '加载三单匹配结果失败'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadData()
  }, [currentLedgerId])

  const columns = [
    {
      title: '合同编号',
      key: 'contract_no',
      render: (_: unknown, row: PurchaseMatchResult) => row.contract.contract_no || `#${row.contract.id}`,
    },
    {
      title: '合同名称',
      key: 'contract_name',
      render: (_: unknown, row: PurchaseMatchResult) => row.contract.contract_name || '-',
    },
    {
      title: '合同金额',
      key: 'contract_amount',
      render: (_: unknown, row: PurchaseMatchResult) => formatAmount(row.totals.contract_amount),
    },
    {
      title: '发票合计',
      key: 'invoice_total',
      render: (_: unknown, row: PurchaseMatchResult) => formatAmount(row.totals.invoice_total),
    },
    {
      title: '入库合计',
      key: 'inventory_total',
      render: (_: unknown, row: PurchaseMatchResult) => formatAmount(row.totals.inventory_total),
    },
    {
      title: '匹配状态',
      dataIndex: 'match_status',
      key: 'match_status',
      render: (value: string, row: PurchaseMatchResult) => (
        <Tag color={STATUS_COLOR[value]}>{row.match_status_label}</Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, row: PurchaseMatchResult) => (
        <Button type="link" onClick={() => setSelected(row)}>
          查看差异
        </Button>
      ),
    },
  ]

  const exceptionColumns = [
    { title: '合同', dataIndex: 'contract_name', key: 'contract_name' },
    { title: '异常类型', dataIndex: 'exception_label', key: 'exception_label' },
    { title: '说明', dataIndex: 'message', key: 'message' },
  ]

  return (
    <div>
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <Title level={4} style={{ margin: 0 }}>
              <AuditOutlined /> 采购三单匹配
            </Title>
            <Paragraph type="secondary" style={{ marginBottom: 0 }}>
              按采购合同勾稽发票与入库单，输出差异清单；差异为审计发现，不触发自动冲销。
              <Link to="/inventory/purchase-in" style={{ marginLeft: 8 }}>
                查看采购台账
              </Link>
            </Paragraph>
          </div>
          <Button icon={<ReloadOutlined />} onClick={loadData} loading={loading} disabled={!currentLedgerId}>
            刷新匹配
          </Button>
        </div>

        {summary && (
          <Row gutter={16}>
            <Col xs={12} md={6}>
              <Card><Statistic title="采购合同" value={summary.contract_count} /></Card>
            </Col>
            <Col xs={12} md={6}>
              <Card><Statistic title="已匹配" value={summary.matched_count} valueStyle={{ color: '#3f8600' }} /></Card>
            </Col>
            <Col xs={12} md={6}>
              <Card><Statistic title="单据不全" value={summary.incomplete_count} valueStyle={{ color: '#d48806' }} /></Card>
            </Col>
            <Col xs={12} md={6}>
              <Card><Statistic title="金额异常" value={summary.exception_count} valueStyle={{ color: '#cf1322' }} /></Card>
            </Col>
          </Row>
        )}

        <Card title="合同匹配结果">
          <Table
            rowKey={(row) => String(row.contract.id)}
            loading={loading}
            columns={columns}
            dataSource={summary?.results || []}
            pagination={{ pageSize: 10 }}
            locale={{ emptyText: '暂无采购合同，请先登记采购合同/发票/入库单' }}
          />
        </Card>

        {summary && summary.exception_items.length > 0 && (
          <Card title="差异清单">
            <Table
              rowKey={(row, index) => `${row.contract_id}-${row.exception_type}-${index}`}
              columns={exceptionColumns}
              dataSource={summary.exception_items}
              pagination={false}
              size="small"
            />
          </Card>
        )}

        {selected && (
          <Card
            title={`匹配详情 · ${selected.contract.contract_no || selected.contract.contract_name || selected.contract.id}`}
            extra={<Button type="link" onClick={() => setSelected(null)}>关闭</Button>}
          >
            <Descriptions bordered size="small" column={{ xs: 1, sm: 2, md: 3 }}>
              <Descriptions.Item label="合同金额">{formatAmount(selected.totals.contract_amount)}</Descriptions.Item>
              <Descriptions.Item label="发票合计">{formatAmount(selected.totals.invoice_total)}</Descriptions.Item>
              <Descriptions.Item label="入库合计">{formatAmount(selected.totals.inventory_total)}</Descriptions.Item>
            </Descriptions>

            <Table
              style={{ marginTop: 16 }}
              rowKey="check_key"
              size="small"
              pagination={false}
              columns={[
                { title: '校验项', dataIndex: 'label', key: 'label' },
                {
                  title: '左侧金额',
                  dataIndex: 'left_amount',
                  key: 'left_amount',
                  render: (value: number) => formatAmount(value),
                },
                {
                  title: '右侧金额',
                  dataIndex: 'right_amount',
                  key: 'right_amount',
                  render: (value: number) => formatAmount(value),
                },
                {
                  title: '结果',
                  dataIndex: 'passed',
                  key: 'passed',
                  render: (value: boolean) => <Tag color={value ? 'success' : 'error'}>{value ? '通过' : '未通过'}</Tag>,
                },
              ]}
              dataSource={selected.checks}
              locale={{ emptyText: '暂无可比对金额校验项' }}
            />

            {selected.exceptions.length > 0 && (
              <Table
                style={{ marginTop: 16 }}
                rowKey={(row, index) => `${row.exception_type}-${index}`}
                size="small"
                pagination={false}
                columns={[
                  { title: '异常类型', dataIndex: 'exception_label', key: 'exception_label' },
                  { title: '说明', dataIndex: 'message', key: 'message' },
                ]}
                dataSource={selected.exceptions}
              />
            )}
          </Card>
        )}
      </Space>
    </div>
  )
}
