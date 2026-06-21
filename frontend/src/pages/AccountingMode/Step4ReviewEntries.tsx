import { Card, Table, Button, Steps, Typography, Tag, Space, Checkbox, Input, Select, Alert, message } from 'antd'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { useEffect, useState } from 'react'
import type { ColumnsType } from 'antd/es/table'
import { api, type AccountingEntry } from '../../api/client'
import { FlowNav } from '../../components/FlowNav'

const { Title } = Typography

export function Step4ReviewEntries() {
const navigate = useNavigate()
const location = useLocation()
const stepPath = (step: number) => location.pathname.startsWith('/ledger/vouchers/step/') ? `/ledger/vouchers/step/${step}` : `/accounting/step/${step}`
const [searchParams] = useSearchParams()
const jobId = Number(searchParams.get('jobId') || 0)
const periodId = Number(searchParams.get('periodId') || 0)
const currentStep = 3

const [entries, setEntries] = useState<AccountingEntry[]>([])
const [loading, setLoading] = useState(false)
const [verifiedMap, setVerifiedMap] = useState<Map<number, boolean>>(new Map())
const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])

useEffect(() => {
const loadEntries = async () => {
if (!jobId) return
setLoading(true)
try {
const list = await api.listEntries(jobId)
setEntries(list)
} catch (error) {
console.error('获取分录失败', error)
message.error('获取分录失败')
} finally {
setLoading(false)
}
}
loadEntries()
}, [jobId])

const onSelectChange = (keys: React.Key[]) => {
setSelectedRowKeys(keys)
}

const rowSelection = {
selectedRowKeys,
onChange: onSelectChange
}

const isVerified = (id: number) => verifiedMap.get(id) === true

const toggleVerified = (id: number) => {
setVerifiedMap((prev) => {
const next = new Map(prev)
next.set(id, !next.get(id))
return next
})
 }

  const batchVerify = () => {
    setVerifiedMap((prev) => {
      const next = new Map(prev)
      for (const key of selectedRowKeys) {
        next.set(Number(key), true)
      }
      return next
    })
    setSelectedRowKeys([])
  }

  const columns: ColumnsType<AccountingEntry> = [
    {
      title: '状态',
      key: 'verified',
      width: 80,
      render: (_: unknown, record: AccountingEntry) => (
        <Checkbox
          checked={isVerified(record.id)}
          onChange={() => toggleVerified(record.id)}
        />
      )
    },
    {
      title: '凭证号',
      dataIndex: 'voucher_no',
      key: 'voucher_no',
      render: (val: string | null) => val || '-'
    },
    {
      title: '行号',
      dataIndex: 'entry_line_no',
      key: 'entry_line_no'
    },
    {
      title: '日期',
      dataIndex: 'voucher_date',
      key: 'voucher_date',
      render: (val: string | null) => val || '-'
    },
    {
      title: '科目',
      dataIndex: 'account_name',
      key: 'account_name',
      render: (val: string | null, record: AccountingEntry) => (
        <Input
          defaultValue={val || ''}
          style={{ width: '150px' }}
          disabled={isVerified(record.id)}
        />
      )
    },
    {
      title: '摘要',
      dataIndex: 'summary',
      key: 'summary',
      render: (val: string | null, record: AccountingEntry) => (
        <Input
          defaultValue={val || ''}
          disabled={isVerified(record.id)}
        />
      )
    },
    {
      title: '借方金额',
      dataIndex: 'debit_amount',
      key: 'debit_amount',
      render: (val: number) => (Number(val) > 0 ? `¥${Number(val).toLocaleString()}` : '-')
    },
    {
      title: '贷方金额',
      dataIndex: 'credit_amount',
      key: 'credit_amount',
      render: (val: number) => (Number(val) > 0 ? `¥${Number(val).toLocaleString()}` : '-')
    },
    {
      title: '对方单位',
      dataIndex: 'counterparty',
      key: 'counterparty',
      render: (val: string | null) => val || '-'
    }
  ]

  const verifiedCount = entries.filter((e) => isVerified(e.id)).length
  const allVerified = entries.length > 0 && verifiedCount === entries.length

  const goPrev = () => {
    const params = new URLSearchParams()
    if (jobId) params.set('jobId', String(jobId))
    if (periodId) params.set('periodId', String(periodId))
    const qs = params.toString()
    navigate(qs ? `${stepPath(3)}?${qs}` : stepPath(3))
  }

  const goNext = () => {
    if (!jobId) return
    const params = new URLSearchParams()
    params.set('jobId', String(jobId))
    if (periodId) params.set('periodId', String(periodId))
    navigate(`${stepPath(5)}?${params.toString()}`)
  }

  return (
    <div style={{ padding: '24px', maxWidth: '1000px', margin: '0 auto' }}>
      <Steps
        current={currentStep}
        items={[
          { title: '选择类型' },
          { title: '导入资料' },
          { title: '生成草稿' },
          { title: '复核调整' },
          { title: '确认入账与导出' }
        ]}
        style={{ marginBottom: '32px' }}
      />

      <FlowNav prev={stepPath(3)} onNext={goNext} nextDisabled={!jobId || entries.length === 0 || !allVerified} style={{ marginBottom: '16px' }} />

      <Space style={{ marginBottom: '16px', width: '100%', justifyContent: 'space-between' }}>
        <Title level={4} style={{ margin: 0 }}>复核调整待复核凭证草稿</Title>
        <Tag color={allVerified ? 'green' : 'blue'}>
          已复核 {verifiedCount}/{entries.length}
        </Tag>
      </Space>

      {!jobId && (
        <Alert
          title="尚未找到待复核凭证草稿"
          description="请从「生成草稿」步骤保存待复核凭证草稿后再进入本步骤。"
          type="warning"
          showIcon
          style={{ marginBottom: '16px' }}
        />
      )}

      <Card loading={loading}>
        <Alert
          title="当前步骤用于复核调整待复核凭证草稿"
          description="请重点复核摘要、科目、金额、往来单位和借贷平衡；全部标记已复核后，可进入确认入账与导出步骤。这里不代表完整总账过账或结账流程。"
          type="info"
          showIcon
          style={{ marginBottom: '16px' }}
        />
        <div style={{ marginBottom: '16px', display: 'flex', gap: '12px', alignItems: 'center' }}>
          <Button
            type="primary"
            onClick={batchVerify}
            disabled={selectedRowKeys.length === 0}
          >
            批量标记已复核 ({selectedRowKeys.length})
          </Button>
          <Select placeholder="复核状态" style={{ width: 150 }}>
            <Select.Option value="draft">待复核</Select.Option>
            <Select.Option value="verified">已复核</Select.Option>
            <Select.Option value="ready">待确认入账与导出</Select.Option>
          </Select>
        </div>

        <Table
          rowSelection={rowSelection}
          columns={columns}
          dataSource={entries}
          rowKey="id"
          pagination={{ pageSize: 10 }}
          size="small"
          locale={{ emptyText: jobId ? '暂无待复核凭证草稿，请先在上一步生成并保存草稿' : '请先选择或生成待复核凭证草稿' }}
        />
      </Card>

      <div style={{ marginTop: '24px', display: 'flex', gap: '12px' }}>
        <Button onClick={goPrev}>
          上一步
        </Button>
        <Button
          type="primary"
          onClick={goNext}
          disabled={!jobId || entries.length === 0 || !allVerified}
        >
          确认复核，进入确认入账与导出
        </Button>
      </div>
    </div>
  )
}
