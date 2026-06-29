import { useEffect, useState } from 'react'
import { Card, Table, Tag, Button, Space, Modal, Form, Input, DatePicker, message, Popconfirm, Alert } from 'antd'
import { api, type AccountingPeriod } from '../api/client'
import { useAuthStore } from '../stores/authStore'

export function AccountingPeriodsPage() {
  const { currentLedgerId } = useAuthStore()
  const [list, setList] = useState<AccountingPeriod[]>([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const [form] = Form.useForm()

  const load = async () => {
    setLoading(true)
    try {
      setList(await api.listAccountingPeriods(undefined, currentLedgerId || undefined))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [currentLedgerId])

  const handleCreate = async () => {
    const values = await form.validateFields()
    try {
      await api.createAccountingPeriod({
        ledger_id: currentLedgerId || undefined,
        organization_id: list[0]?.organization_id,
        period_code: values.period_code,
        start_date: values.start_date.format('YYYY-MM-DD'),
        end_date: values.end_date.format('YYYY-MM-DD'),
      })
      setOpen(false)
      form.resetFields()
      await load()
      message.success('期间已创建')
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error)
      message.error(`创建失败：${detail}`)
    }
  }

  const handlePlTransfer = async (periodId: number) => {
    try {
      const result = await api.plTransfer(periodId)
      message.success(`损益结转完成，凭证 ${result.voucher_no}，净利润 ¥${result.net_profit.toLocaleString()}`)
      await load()
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error)
      message.error(`结转失败：${detail}`)
    }
  }

  const handlePlReverse = async (periodId: number) => {
    try {
      const result = await api.plTransferReverse(periodId)
      message.success(`已反结转，删除分录 ${result.deleted_lines} 行`)
      await load()
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error)
      message.error(`反结转失败：${detail}`)
    }
  }

  const handleClosePeriod = async (periodId: number) => {
    try {
      await api.closePeriod(periodId)
      message.success('期间已结账')
      await load()
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error)
      message.error(`结账失败：${detail}`)
    }
  }

  const handleReopenPeriod = async (periodId: number) => {
    try {
      await api.reopenPeriod(periodId)
      message.success('期间已反结账')
      await load()
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error)
      message.error(`反结账失败：${detail}`)
    }
  }

  return (
    <Card
      title="会计期间"
      extra={(
        <Button type="primary" onClick={() => setOpen(true)} disabled={!currentLedgerId}>
          新增
        </Button>
      )}
    >
      {!currentLedgerId && (
        <Alert
          type="warning"
          showIcon
          title="请先选择账簿"
          description="会计期间按当前账簿过滤，请先在顶部选择账簿。"
          style={{ marginBottom: 16 }}
        />
      )}
      <Table
        rowKey="id"
        dataSource={list}
        loading={loading}
        size="small"
        pagination={{ pageSize: 20 }}
        columns={[
          { title: 'ID', dataIndex: 'id', key: 'id' },
          { title: '期间编码', dataIndex: 'period_code', key: 'period_code' },
          { title: '开始', dataIndex: 'start_date', key: 'start_date' },
          { title: '结束', dataIndex: 'end_date', key: 'end_date' },
          {
            title: '状态',
            dataIndex: 'status',
            key: 'status',
            render: (v: string) => {
              const colors: Record<string, string> = {
                open: 'green',
                pl_transferred: 'blue',
                closed: 'orange',
                reopened: 'purple',
              }
              const labels: Record<string, string> = {
                open: '开放',
                pl_transferred: '已结转损益',
                closed: '已结账',
                reopened: '已反结账',
              }
              return <Tag color={colors[v] || 'default'}>{labels[v] || v}</Tag>
            },
          },
          {
            title: '操作',
            key: 'action',
            render: (_: unknown, row: AccountingPeriod) => (
              <Space>
                {row.status === 'open' && (
                  <Popconfirm
                    title="确认对该期间执行损益结转？"
                    description="将自动生成 转-期末-XXX 凭证，结转后资产负债表恒等式才能成立。"
                    onConfirm={() => handlePlTransfer(row.id)}
                  >
                    <Button size="small" type="primary">损益结转</Button>
                  </Popconfirm>
                )}
                {row.status === 'pl_transferred' && (
                  <>
                    <Popconfirm
                      title="确认反结转该期间？"
                      description="将删除本期 转-期末-XXX 凭证，并把状态恢复为开放。"
                      onConfirm={() => handlePlReverse(row.id)}
                    >
                      <Button size="small">反结转</Button>
                    </Popconfirm>
                    <Popconfirm
                      title="确认结账该期间？"
                      description="结账后将生成快照，期间不可再修改。"
                      onConfirm={() => handleClosePeriod(row.id)}
                    >
                      <Button size="small" type="primary">结账</Button>
                    </Popconfirm>
                  </>
                )}
                {row.status === 'closed' && (
                  <Popconfirm
                    title="确认反结账该期间？"
                    description="快照将被置为无效，期间恢复为开放状态。"
                    onConfirm={() => handleReopenPeriod(row.id)}
                  >
                    <Button size="small">反结账</Button>
                  </Popconfirm>
                )}
              </Space>
            ),
          },
        ]}
      />
      <Modal title="新增会计期间" open={open} onOk={handleCreate} onCancel={() => setOpen(false)} okText="创建">
        <Form form={form} layout="vertical">
          <Form.Item name="period_code" label="期间编码" rules={[{ required: true }]}>
            <Input placeholder="如 2026-01" />
          </Form.Item>
          <Form.Item name="start_date" label="开始" rules={[{ required: true }]}>
            <DatePicker style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="end_date" label="结束" rules={[{ required: true }]}>
            <DatePicker style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  )
}
