import { useCallback, useEffect, useMemo, useState } from 'react'
import { Card, Table, Select, Space, InputNumber, Button, Alert, message, Typography, Tag } from 'antd'
import { api, type OpeningBalance, type AccountingPeriod, type TrialBalance } from '../../api/client'
import { useAuthStore } from '../../stores/authStore'
import { Money } from '../../money'

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

function buildEmptyRows(coa: CoaItem[]): Row[] {
  return coa.map((c) => ({
    key: c.code,
    account_code: c.code,
    account_name: c.name,
    category: c.category,
    direction: c.direction,
    debit_balance: 0,
    credit_balance: 0,
  }))
}

export function OpeningBalancesPage() {
  const { currentLedgerId, userLedgers } = useAuthStore()
  const currentLedger = userLedgers.find((l) => l.id === currentLedgerId)
  const [periods, setPeriods] = useState<AccountingPeriod[]>([])
  const [coa, setCoa] = useState<CoaItem[]>([])
  const [periodId, setPeriodId] = useState<number | null>(null)
  const [organizationId, setOrganizationId] = useState<number | null>(null)
  const [rows, setRows] = useState<Row[]>([])
  const [trial, setTrial] = useState<TrialBalance | null>(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    setPeriods([])
    setPeriodId(null)
    setOrganizationId(null)
    setRows([])
    setTrial(null)

    if (!currentLedgerId) return

    void (async () => {
      try {
        const [p, coaResp] = await Promise.all([
          api.listAccountingPeriods(undefined, currentLedgerId),
          fetch(`${API_BASE}/api/coa`).then((r) => r.json()),
        ])
        const activeCoa = (coaResp as CoaItem[]).filter((c) => c.status === 'active')
        setCoa(activeCoa)
        setPeriods(p)
        if (p.length > 0) {
          setPeriodId(p[0].id)
          setOrganizationId(p[0].organization_id)
        } else {
          setRows(buildEmptyRows(activeCoa))
        }
      } catch (error) {
        const detail = error instanceof Error ? error.message : String(error)
        message.error(`加载初始数据失败：${detail}`)
      }
    })()
  }, [currentLedgerId])

  const reload = useCallback(async () => {
    if (!periodId || !organizationId || !currentLedgerId || coa.length === 0) {
      setRows(coa.length > 0 ? buildEmptyRows(coa) : [])
      setTrial(null)
      return
    }
    const selectedPeriod = periods.find((p) => p.id === periodId)
    if (!selectedPeriod) {
      setRows(buildEmptyRows(coa))
      setTrial(null)
      return
    }

    setLoading(true)
    try {
      const [items, tb] = await Promise.all([
        api.listOpeningBalances(organizationId, periodId, currentLedgerId),
        api.getOpeningTrialBalance(organizationId, periodId, currentLedgerId),
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
      setRows(buildEmptyRows(coa))
      setTrial(null)
    } finally {
      setLoading(false)
    }
  }, [periodId, organizationId, currentLedgerId, coa, periods])

  useEffect(() => {
    void reload()
  }, [reload])

  const updateRow = (code: string, patch: Partial<Row>) => {
    setRows((prev) => prev.map((r) => (r.account_code === code ? { ...r, ...patch } : r)))
  }

  const handleSaveAll = async () => {
    if (!periodId || !organizationId || !currentLedgerId) return
    setSaving(true)
    try {
      const items = rows
        .filter((r) => (r.debit_balance || 0) !== 0 || (r.credit_balance || 0) !== 0)
        .map((r) => ({
          account_code: r.account_code,
          debit_balance: r.debit_balance || 0,
          credit_balance: r.credit_balance || 0,
        }))
      await api.bulkUpsertOpeningBalances(organizationId, periodId, items, currentLedgerId)
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
    const debit = Money.sum(rows.map(r => Money.cny(r.debit_balance)))
    const credit = Money.sum(rows.map(r => Money.cny(r.credit_balance)))
    return { debit, credit, diff: debit.sub(credit) }
  }, [rows])

  const isBalanced = trial?.is_balanced ?? totals.debit.eq(totals.credit)

  return (
    <div>
      <Title level={3}>期初科目余额</Title>

      {!currentLedgerId && (
        <Alert
          type="warning"
          showIcon
          title="请先选择账簿"
          description="期初余额按当前账簿隔离，请在顶部选择账簿后再录入。"
          style={{ marginBottom: 16 }}
        />
      )}

      <Card style={{ marginBottom: 16 }}>
        <Space wrap>
          <Text>当前账簿：{currentLedger?.name || '未选择'}</Text>
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
            disabled={!currentLedgerId || periods.length === 0}
          />
          <Button onClick={() => void reload()} disabled={!periodId || !currentLedgerId}>刷新</Button>
          <Button
            type="primary"
            loading={saving}
            onClick={handleSaveAll}
            disabled={!periodId || !currentLedgerId}
          >
            保存全部
          </Button>
        </Space>
        {currentLedgerId && periods.length === 0 && (
          <Alert
            type="info"
            showIcon
            title="当前账簿暂无会计期间"
            description="请先在「会计期间」页面为当前账簿创建期间，再录入期初余额。"
            style={{ marginTop: 16 }}
          />
        )}
      </Card>

      {!isBalanced && rows.some((r) => r.debit_balance || r.credit_balance) && (
        <Alert
          type="error"
          title="期初借贷不平衡"
          description={`借方合计 ¥${totals.debit.toFixed(2)}，贷方合计 ¥${totals.credit.toFixed(2)}，差额 ¥${totals.diff.toFixed(2)}`}
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}
      {isBalanced && trial && trial.count > 0 && (
        <Alert
          type="success"
          title={`期初借贷平衡：¥${totals.debit.toFixed(2)}`}
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
                  disabled={!currentLedgerId}
                  onChange={(v) => updateRow(row.account_code, { debit_balance: v ?? 0 })}
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
                  disabled={!currentLedgerId}
                  onChange={(v) => updateRow(row.account_code, { credit_balance: v ?? 0 })}
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
                <strong>¥{totals.debit.toFixed(2)}</strong>
              </Table.Summary.Cell>
              <Table.Summary.Cell index={2}>
                <strong>¥{totals.credit.toFixed(2)}</strong>
              </Table.Summary.Cell>
              <Table.Summary.Cell index={3} />
            </Table.Summary.Row>
          )}
        />
      </Card>
    </div>
  )
}
