import { useEffect, useMemo, useState } from 'react'
import { Card, Table, Select, Space, InputNumber, Button, Alert, message, Typography, Tag } from 'antd'
import { api, type OpeningBalance, type AccountingPeriod, type TrialBalance } from '../../api/client'
import { useAuthStore } from '../../stores/authStore'

const { Title, Text } = Typography

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

type CoaItem = {
  code: string
  name: string
  category: string
  direction: string
  status: string
}

type Row = {
  key: string
  account_code: string
  account_name: string
  category: string
  direction: string
  id?: number
  debit_balance: number
  credit_balance: number
}

const CATEGORY_LABEL: Record<string, string> = {
  asset: '资产',
  liability: '负债',
  common: '共同',
  equity: '权益',
  cost: '成本',
  profit: '损益',
}

export function OpeningBalancesPage() {
  const { currentLedgerId } = useAuthStore()
  const [periods, setPeriods] = useState<AccountingPeriod[]>([])
  const [coa, setCoa] = useState<CoaItem[]>([])
  const [periodId, setPeriodId] = useState<number | null>(null)
  const [organizationId, setOrganizationId] = useState<number | null>(null)
  const [rows, setRows] = useState<Row[]>([])
  const [trial, setTrial] = useState<TrialBalance | null>(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)

  // 初次加载：期间 + CoA
  useEffect(() => {
    void (async () => {
      try {
        const [p, coaResp] = await Promise.all([
          api.listAccountingPeriods(undefined, currentLedgerId || undefined),
          fetch(`${API_BASE}/api/coa`).then((r) => r.json()),
        ])
        setPeriods(p)
        setCoa((coaResp as CoaItem[]).filter((c) => c.status === 'active'))
        if (p.length > 0) {
          setPeriodId(p[0].id)
          setOrganizationId(p[0].organization_id)
        } else {
          setPeriodId(null)
          setOrganizationId(null)
        }
      } catch (error) {
        const detail = error instanceof Error ? error.message : String(error)
        message.error(`加载初始数据失败：${detail}`)
      }
    })()
  }, [currentLedgerId])

  const reload = async () => {
    if (!periodId || !organizationId) return
    setLoading(true)
    try {
      const [items, tb] = await Promise.all([
        api.listOpeningBalances(organizationId, periodId),
        api.getOpeningTrialBalance(organizationId, periodId),
      ])
      const byCode = new Map<string, OpeningBalance>()
      items.forEach((i) => byCode.set(i.account_code, i))
      const merged: Row[] = coa.map((c) => {
        const exist = byCode.get(c.code)
        return {
          key: c.code,
          account_code: c.code,
          account_name: c.name,
          category: c.category,
          direction: c.direction,
          id: exist?.id,
          debit_balance: exist?.debit_balance ?? 0,
          credit_balance: exist?.credit_balance ?? 0,
        }
      })
      setRows(merged)
      setTrial(tb)
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error)
      message.error(`加载期初失败：${detail}`)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (periodId && organizationId && coa.length > 0) {
      void reload()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [periodId, organizationId, coa])

  const updateRow = (code: string, patch: Partial<Row>) => {
    setRows((prev) => prev.map((r) => (r.account_code === code ? { ...r, ...patch } : r)))
  }

  const handleSaveAll = async () => {
    if (!periodId || !organizationId) return
    setSaving(true)
    try {
      const items = rows
        .filter((r) => (r.debit_balance || 0) !== 0 || (r.credit_balance || 0) !== 0)
        .map((r) => ({
          account_code: r.account_code,
          debit_balance: r.debit_balance || 0,
          credit_balance: r.credit_balance || 0,
        }))
      await api.bulkUpsertOpeningBalances(organizationId, periodId, items)
      message.success(`已保存 ${items.length} 条期初余额`)
      await reload()
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error)
      message.error(`保存失败：${detail}`)
    } finally {
      setSaving(false)
    }
  }

  const totals = useMemo(() => {
    const debit = rows.reduce((s, r) => s + (Number(r.debit_balance) || 0), 0)
    const credit = rows.reduce((s, r) => s + (Number(r.credit_balance) || 0), 0)
    return { debit, credit, diff: debit - credit }
  }, [rows])

  const isBalanced = trial?.is_balanced ?? totals.debit === totals.credit

  return (
    <div>
      <Title level={3}>期初科目余额</Title>

      <Card style={{ marginBottom: 16 }}>
        <Space>
          <Text>会计期间：</Text>
          <Select
            value={periodId ?? undefined}
            style={{ width: 240 }}
            onChange={(v) => {
              const period = periods.find((p) => p.id === v)
              setPeriodId(v)
              if (period) setOrganizationId(period.organization_id)
            }}
            options={periods.map((p) => ({
              value: p.id,
              label: `${p.period_code}（${p.start_date} ~ ${p.end_date}）`,
            }))}
            placeholder="请选择期间"
          />
          <Button onClick={reload} disabled={!periodId}>刷新</Button>
          <Button type="primary" loading={saving} onClick={handleSaveAll} disabled={!periodId}>
            保存全部
          </Button>
        </Space>
      </Card>

      {!isBalanced && (
        <Alert
          type="error"
          title="期初借贷不平衡"
          description={`借方合计 ¥${totals.debit.toLocaleString()}，贷方合计 ¥${totals.credit.toLocaleString()}，差额 ¥${(totals.debit - totals.credit).toLocaleString()}`}
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}
      {isBalanced && trial && trial.count > 0 && (
        <Alert
          type="success"
          title={`期初借贷平衡：¥${totals.debit.toLocaleString()}`}
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      <Card>
        <Table
          rowKey="key"
          dataSource={rows}
          loading={loading}
          pagination={{ pageSize: 50 }}
          size="small"
          columns={[
            { title: '科目代码', dataIndex: 'account_code', key: 'account_code', width: 100 },
            { title: '科目名称', dataIndex: 'account_name', key: 'account_name' },
            {
              title: '类别',
              dataIndex: 'category',
              key: 'category',
              render: (v: string) => CATEGORY_LABEL[v] || v,
              width: 80,
            },
            {
              title: '方向',
              dataIndex: 'direction',
              key: 'direction',
              render: (v: string) => (v === 'debit' ? '借' : '贷'),
              width: 60,
            },
            {
              title: '借方期初',
              dataIndex: 'debit_balance',
              key: 'debit_balance',
              width: 160,
              render: (val: number, row: Row) => (
                <InputNumber
                  value={val}
                  min={0}
                  step={100}
                  onChange={(v) => updateRow(row.account_code, { debit_balance: Number(v ?? 0) })}
                  style={{ width: '100%' }}
                />
              ),
            },
            {
              title: '贷方期初',
              dataIndex: 'credit_balance',
              key: 'credit_balance',
              width: 160,
              render: (val: number, row: Row) => (
                <InputNumber
                  value={val}
                  min={0}
                  step={100}
                  onChange={(v) => updateRow(row.account_code, { credit_balance: Number(v ?? 0) })}
                  style={{ width: '100%' }}
                />
              ),
            },
            {
              title: '状态',
              key: 'status',
              width: 80,
              render: (_: unknown, row: Row) =>
                row.id ? <Tag color="green">已保存</Tag> : <Tag>未保存</Tag>,
            },
          ]}
          summary={() => (
            <Table.Summary.Row>
              <Table.Summary.Cell index={0} colSpan={4}>
                <strong>合计</strong>
              </Table.Summary.Cell>
              <Table.Summary.Cell index={1}>
                <strong>¥{totals.debit.toLocaleString()}</strong>
              </Table.Summary.Cell>
              <Table.Summary.Cell index={2}>
                <strong>¥{totals.credit.toLocaleString()}</strong>
              </Table.Summary.Cell>
              <Table.Summary.Cell index={3} />
            </Table.Summary.Row>
          )}
        />
      </Card>
    </div>
  )
}
