import { useEffect, useMemo, useState } from 'react'

import {

  Card,

  Table,

  Tag,

  Button,

  Space,

  Modal,

  Form,

  Input,

  DatePicker,

  message,

  Popconfirm,

  Alert,

  Descriptions,

  List,

  Typography,

  Steps,

  Select,

  Checkbox,

  Collapse,

} from 'antd'

import {

  api,

  type AccountingPeriod,

  type PlTransferBatchResult,

  type PlTransferHealth,

} from '../api/client'

import { AccountingPeriodRulesPanel } from '../components/ledger/AccountingPeriodRulesPanel'

import { useAuthStore } from '../stores/authStore'

import { formatAmount } from '../money'



const { Text, Title } = Typography



const TRANSFERABLE_STATUSES = new Set(['open', 'reopened'])



const STATUS_COLORS: Record<string, string> = {

  open: 'green',

  pl_transferred: 'blue',

  closed: 'orange',

  reopened: 'purple',

}



const STATUS_LABELS: Record<string, string> = {

  open: '开放',

  pl_transferred: '损益已达标',

  closed: '已结账',

  reopened: '已反结账',

}



function sortPeriods(periods: AccountingPeriod[]) {

  return [...periods].sort((a, b) => a.start_date.localeCompare(b.start_date) || a.id - b.id)

}



/** 当前应处理的工作期间：最早一条未结账期间 */

function resolveWorkingPeriod(periods: AccountingPeriod[]): AccountingPeriod | null {

  const pending = periods.filter((p) => p.status !== 'closed')

  if (pending.length === 0) return null

  return sortPeriods(pending)[0]

}



function periodsInRange(

  periods: AccountingPeriod[],

  fromPeriodId: number,

  toPeriodId: number,

): AccountingPeriod[] {

  const sorted = sortPeriods(periods)

  const fromIdx = sorted.findIndex((p) => p.id === fromPeriodId)

  const toIdx = sorted.findIndex((p) => p.id === toPeriodId)

  if (fromIdx < 0 || toIdx < 0) return []

  const [start, end] = fromIdx <= toIdx ? [fromIdx, toIdx] : [toIdx, fromIdx]

  return sorted.slice(start, end + 1)

}



function periodOptionLabel(period: AccountingPeriod) {

  return `${period.period_code}（${STATUS_LABELS[period.status] || period.status} · ${period.start_date} ~ ${period.end_date}）`

}



export function AccountingPeriodsPage() {

  const { currentLedgerId } = useAuthStore()

  const [list, setList] = useState<AccountingPeriod[]>([])

  const [loading, setLoading] = useState(false)

  const [open, setOpen] = useState(false)

  const [form] = Form.useForm()

  const [reconcileOpen, setReconcileOpen] = useState(false)

  const [reconcileLoading, setReconcileLoading] = useState(false)

  const [reconcileTarget, setReconcileTarget] = useState<AccountingPeriod | null>(null)

  const [reconcileResult, setReconcileResult] = useState<PlTransferHealth | null>(null)

  const [provisionLoading, setProvisionLoading] = useState(false)

  const [batchModalOpen, setBatchModalOpen] = useState(false)

  const [batchLoading, setBatchLoading] = useState(false)

  const [batchForm] = Form.useForm()

  const [batchResult, setBatchResult] = useState<PlTransferBatchResult | null>(null)

  const [batchResultOpen, setBatchResultOpen] = useState(false)

  const [forceTransferLoading, setForceTransferLoading] = useState(false)



  const sortedPeriods = useMemo(() => sortPeriods(list), [list])

  const workingPeriod = useMemo(() => resolveWorkingPeriod(sortedPeriods), [sortedPeriods])

  const pendingPeriodCount = useMemo(

    () => sortedPeriods.filter((p) => p.status !== 'closed').length,

    [sortedPeriods],

  )

  const periodOptions = useMemo(

    () => sortedPeriods.map((p) => ({ value: p.id, label: periodOptionLabel(p) })),

    [sortedPeriods],

  )



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

    setForceTransferLoading(true)

    try {

      const result = await api.plTransfer(periodId)

      message.success(`损益结转完成，凭证 ${result.voucher_no}，净利润 ${formatAmount(result.net_profit)}`)

      await load()

    } catch (error) {

      const detail = error instanceof Error ? error.message : String(error)

      message.error(`结转失败：${detail}`)

    } finally {

      setForceTransferLoading(false)

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



  const openReconcileModal = async (row: AccountingPeriod) => {

    setReconcileTarget(row)

    setReconcileOpen(true)

    setReconcileResult(null)

    setReconcileLoading(true)

    try {

      const result = await api.reconcilePlTransfer(row.id, false)

      setReconcileResult(result)

    } catch (error) {

      const detail = error instanceof Error ? error.message : String(error)

      message.error(`校验失败：${detail}`)

      setReconcileOpen(false)

    } finally {

      setReconcileLoading(false)

    }

  }



  const handleReconcileFix = async () => {

    if (!reconcileTarget) return

    setReconcileLoading(true)

    try {

      const result = await api.reconcilePlTransfer(reconcileTarget.id, true)

      setReconcileResult(result)

      if (result.fixed) {

        message.success('已自动修正期间结转状态')

        await load()

      } else {

        message.info('未发现可自动修正的状态问题')

      }

    } catch (error) {

      const detail = error instanceof Error ? error.message : String(error)

      message.error(`修正失败：${detail}`)

    } finally {

      setReconcileLoading(false)

    }

  }



  const handleAutoProvisionCoa = async (dryRun: boolean) => {

    if (!currentLedgerId) return

    setProvisionLoading(true)

    try {

      const result = await api.autoProvisionCoaGaps(currentLedgerId, dryRun)

      if (dryRun) {

        message.info(`预检完成：发现 ${result.orphan_code_count} 个缺口编码，可补全 ${result.created_count} 个科目`)

      } else if (result.created_count > 0) {

        message.success(`已自动补全 ${result.created_count} 个科目`)

      } else {

        message.info('未发现需要补全的 COA 缺口（运行时映射可能已覆盖）')

      }

    } catch (error) {

      const detail = error instanceof Error ? error.message : String(error)

      message.error(`COA 补全失败：${detail}`)

    } finally {

      setProvisionLoading(false)

    }

  }



  const openBatchTransferModal = () => {

    batchForm.setFieldsValue({

      fromPeriodId: workingPeriod?.id ?? sortedPeriods[0]?.id,

      toPeriodId: workingPeriod?.id ?? sortedPeriods[sortedPeriods.length - 1]?.id,

      stopOnError: true,

      skipTransferred: true,

    })

    setBatchModalOpen(true)

  }



  const handleRangeTransfer = async () => {

    if (!currentLedgerId) return

    const values = await batchForm.validateFields()

    const range = periodsInRange(sortedPeriods, values.fromPeriodId, values.toPeriodId)

    if (range.length === 0) {

      message.warning('起止期间无效')

      return

    }

    setBatchLoading(true)

    try {

      const result = await api.plTransferBatch({

        ledgerId: currentLedgerId,

        fromPeriodId: values.fromPeriodId,

        toPeriodId: values.toPeriodId,

        stopOnError: values.stopOnError !== false,

        skipTransferred: values.skipTransferred !== false,

      })

      setBatchResult(result)

      setBatchResultOpen(true)

      setBatchModalOpen(false)

      await load()

      if (result.failed_count === 0) {

        message.success(`批量结转完成：成功 ${result.succeeded_count}，跳过 ${result.skipped_count}`)

      } else {

        message.warning(`批量结转部分失败：成功 ${result.succeeded_count}，失败 ${result.failed_count}`)

      }

    } catch (error) {

      const detail = error instanceof Error ? error.message : String(error)

      message.error(`批量结转失败：${detail}`)

    } finally {

      setBatchLoading(false)

    }

  }



  const renderPeriodActions = (row: AccountingPeriod, size: 'small' | 'middle' = 'small') => (

    <Space wrap>

      <Button size={size} onClick={() => openReconcileModal(row)}>

        结转校验

      </Button>

      {(TRANSFERABLE_STATUSES.has(row.status) || row.status === 'pl_transferred') && (

        <Popconfirm

          title="确认结账该期间？"

          description={

            <>

              <div>结账将自动校验损益是否已结转：</div>

              <ul style={{ margin: '8px 0 0', paddingLeft: 18 }}>

                <li>导入凭证已清零损益且平衡 → 直接结账</li>

                <li>否则自动生成系统结转凭证后再结账</li>

                <li>固化科目余额表全表并冻结该期间数据</li>

              </ul>

            </>

          }

          onConfirm={() => handleClosePeriod(row.id)}

        >

          <Button size={size} type="primary">

            结账

          </Button>

        </Popconfirm>

      )}

      {row.status === 'pl_transferred' && (

        <Popconfirm

          title="确认删除系统结转凭证？"

          description="仅删除 转-期末-XXX 系统凭证（如有）；导入结转凭证不受影响，期间将恢复为开放。"

          onConfirm={() => handlePlReverse(row.id)}

        >

          <Button size={size}>删除系统结转凭证</Button>

        </Popconfirm>

      )}

      {row.status === 'closed' && (

        <Popconfirm

          title="确认反结账该期间？"

          description="快照将被置为无效，期间恢复为开放状态。"

          onConfirm={() => handleReopenPeriod(row.id)}

        >

          <Button size={size}>反结账</Button>

        </Popconfirm>

      )}

    </Space>

  )



  return (

    <div>

      <Title level={3}>期末处理 — 结账</Title>



      <AccountingPeriodRulesPanel />



      <Alert

        type="info"

        showIcon

        style={{ marginBottom: 16 }}

        title="日常流程：只需关注「当前工作期间」"

        description="凭证过账与结账时会自动校验损益；下方仅展示当前应处理的期间。历史多月补结转请使用「高级 / 补救操作」中的跨期间批量功能。"

      />



      <Card size="small" style={{ marginBottom: 16 }}>

        <Steps

          size="small"

          items={[

            { title: '凭证过账', description: '导入或录入凭证并入账' },

            { title: '损益校验', description: '过账时自动检测是否已结转' },

            { title: '报表核对', description: '科目余额表须平衡' },

            { title: '期间结账', description: '固化末日快照 · 冻结数据' },

          ]}

        />

      </Card>



      {!currentLedgerId && (

        <Alert

          type="warning"

          showIcon

          title="请先选择账簿"

          description="会计期间按当前账簿过滤，请先在顶部选择账簿。"

          style={{ marginBottom: 16 }}

        />

      )}



      <Card

        title="当前工作期间"

        loading={loading}

        style={{ marginBottom: 16 }}

        extra={

          currentLedgerId ? (

            <Space>

              <Button loading={provisionLoading} onClick={() => handleAutoProvisionCoa(true)}>

                预检 COA 缺口

              </Button>

              <Popconfirm

                title="确认自动补全账簿 COA 缺口？"

                description="将为无法映射的明细科目创建子科目或补全缺失的一级科目。"

                onConfirm={() => handleAutoProvisionCoa(false)}

              >

                <Button loading={provisionLoading}>补全 COA 缺口</Button>

              </Popconfirm>

            </Space>

          ) : null

        }

      >

        {workingPeriod ? (

          <>

            <Descriptions bordered size="small" column={{ xs: 1, sm: 2, md: 3 }}>

              <Descriptions.Item label="期间编码">{workingPeriod.period_code}</Descriptions.Item>

              <Descriptions.Item label="起止日期">

                {workingPeriod.start_date} ~ {workingPeriod.end_date}

              </Descriptions.Item>

              <Descriptions.Item label="状态">

                <Tag color={STATUS_COLORS[workingPeriod.status] || 'default'}>

                  {STATUS_LABELS[workingPeriod.status] || workingPeriod.status}

                </Tag>

                {workingPeriod.status === 'closed' && workingPeriod.snapshot_status === 'valid' ? (

                  <Text type="secondary" style={{ marginLeft: 8, fontSize: 12 }}>

                    科目余额表已固化

                  </Text>

                ) : null}

              </Descriptions.Item>

            </Descriptions>

            {pendingPeriodCount > 1 && (

              <Alert

                type="warning"

                showIcon

                style={{ marginTop: 12 }}

                title={`尚有 ${pendingPeriodCount} 个未结账期间`}

                description="请按时间顺序先完成当前期间，再处理后续月份。批量补历史月份请展开下方「高级 / 补救操作」。"

              />

            )}

            <div style={{ marginTop: 16 }}>{renderPeriodActions(workingPeriod, 'middle')}</div>

          </>

        ) : (

          <Alert

            type="success"

            showIcon

            title="所有期间均已结账"

            description="如需调整历史数据，请在下方「全部期间档案」中对目标期间执行反结账。"

          />

        )}

      </Card>



      <Card

        title="高级 / 补救操作"

        size="small"

        style={{ marginBottom: 16, borderStyle: 'dashed' }}

      >

        <Alert

          type="warning"

          showIcon

          style={{ marginBottom: 12 }}

          title="仅用于历史数据修复或多期补结转"

          description="日常记账不必使用。跨期间批量损益结转按起止期间连续执行，无需在列表中逐期勾选。"

        />

        <Space wrap>

          <Button onClick={openBatchTransferModal} disabled={!currentLedgerId || sortedPeriods.length === 0}>

            跨期间批量损益结转

          </Button>

          {workingPeriod && TRANSFERABLE_STATUSES.has(workingPeriod.status) && (

            <Popconfirm

              title="确认对当前期间强制执行损益结转？"

              description="正常流程应依赖过账/结账自动校验；仅在自动校验未生效时使用。"

              onConfirm={() => handlePlTransfer(workingPeriod.id)}

            >

              <Button loading={forceTransferLoading}>当前期间强制结转</Button>

            </Popconfirm>

          )}

        </Space>

      </Card>



      <Collapse

        style={{ marginBottom: 16 }}

        items={[

          {

            key: 'archive',

            label: `全部期间档案（${sortedPeriods.length}）`,

            extra: (

              <Button

                type="primary"

                size="small"

                onClick={(event) => {

                  event.stopPropagation()

                  setOpen(true)

                }}

                disabled={!currentLedgerId}

              >

                新增期间

              </Button>

            ),

            children: (

              <Table

                rowKey="id"

                dataSource={sortedPeriods}

                loading={loading}

                size="small"

                pagination={{ pageSize: 12, hideOnSinglePage: true }}

                columns={[

                  {

                    title: '期间',

                    key: 'period',

                    render: (_: unknown, row: AccountingPeriod) => (

                      <Space direction="vertical" size={0}>

                        <Text strong={row.id === workingPeriod?.id}>{row.period_code}</Text>

                        <Text type="secondary" style={{ fontSize: 11 }}>

                          {row.start_date} ~ {row.end_date}

                        </Text>

                      </Space>

                    ),

                  },

                  {

                    title: '状态',

                    dataIndex: 'status',

                    key: 'status',

                    width: 140,

                    render: (v: string, row: AccountingPeriod) => (

                      <Space direction="vertical" size={0}>

                        <Tag color={STATUS_COLORS[v] || 'default'}>{STATUS_LABELS[v] || v}</Tag>

                        {row.id === workingPeriod?.id && <Text type="secondary" style={{ fontSize: 11 }}>当前工作</Text>}

                        {v === 'closed' && row.snapshot_status === 'valid' ? (

                          <Text type="secondary" style={{ fontSize: 11 }}>

                            已固化

                          </Text>

                        ) : null}

                      </Space>

                    ),

                  },

                  {

                    title: '操作',

                    key: 'action',

                    render: (_: unknown, row: AccountingPeriod) => renderPeriodActions(row),

                  },

                ]}

              />

            ),

          },

        ]}

      />



      <Modal

        title="跨期间批量损益结转"

        open={batchModalOpen}

        onCancel={() => setBatchModalOpen(false)}

        onOk={() => void handleRangeTransfer()}

        okText="开始批量结转"

        confirmLoading={batchLoading}

        width={520}

      >

        <Form

          form={batchForm}

          layout="vertical"

          initialValues={{ stopOnError: true, skipTransferred: true }}

        >

          <Form.Item

            name="fromPeriodId"

            label="起始期间"

            rules={[{ required: true, message: '请选择起始期间' }]}

          >

            <Select options={periodOptions} placeholder="选择起始期间" showSearch optionFilterProp="label" />

          </Form.Item>

          <Form.Item

            name="toPeriodId"

            label="结束期间"

            rules={[{ required: true, message: '请选择结束期间' }]}

          >

            <Select options={periodOptions} placeholder="选择结束期间" showSearch optionFilterProp="label" />

          </Form.Item>

          <Form.Item name="skipTransferred" valuePropName="checked">

            <Checkbox>跳过已结转损益（pl_transferred / 已结账）的期间</Checkbox>

          </Form.Item>

          <Form.Item name="stopOnError" valuePropName="checked">

            <Checkbox>遇错即停止（不勾选则记录失败并继续后续期间）</Checkbox>

          </Form.Item>

        </Form>

      </Modal>



      <Modal

        title="批量结转结果"

        open={batchResultOpen}

        onCancel={() => setBatchResultOpen(false)}

        footer={<Button onClick={() => setBatchResultOpen(false)}>关闭</Button>}

        width={640}

      >

        {batchResult ? (

          <>

            <Descriptions size="small" column={4} bordered style={{ marginBottom: 16 }}>

              <Descriptions.Item label="合计">{batchResult.total}</Descriptions.Item>

              <Descriptions.Item label="成功">{batchResult.succeeded_count}</Descriptions.Item>

              <Descriptions.Item label="失败">{batchResult.failed_count}</Descriptions.Item>

              <Descriptions.Item label="跳过">{batchResult.skipped_count}</Descriptions.Item>

            </Descriptions>

            {batchResult.succeeded.length > 0 && (

              <List

                size="small"

                header={<Text strong>成功</Text>}

                dataSource={batchResult.succeeded}

                style={{ marginBottom: 12 }}

                renderItem={(item) => (

                  <List.Item>

                    <Text>

                      {item.period_code} · 凭证 {item.voucher_no ?? '—'}

                      {item.net_profit != null ? ` · 净利润 ${formatAmount(item.net_profit)}` : ''}

                    </Text>

                  </List.Item>

                )}

              />

            )}

            {batchResult.failed.length > 0 && (

              <List

                size="small"

                header={<Text strong type="danger">失败</Text>}

                dataSource={batchResult.failed}

                style={{ marginBottom: 12 }}

                renderItem={(item) => (

                  <List.Item>

                    <Text type="danger">

                      {item.period_code}：{item.error || '未知错误'}

                    </Text>

                  </List.Item>

                )}

              />

            )}

            {batchResult.skipped.length > 0 && (

              <List

                size="small"

                header={<Text strong>跳过</Text>}

                dataSource={batchResult.skipped}

                renderItem={(item) => (

                  <List.Item>

                    <Text type="secondary">

                      {item.period_code}：{item.reason || '已处理'}

                    </Text>

                  </List.Item>

                )}

              />

            )}

          </>

        ) : null}

      </Modal>



      <Modal

        title={reconcileTarget ? `结转状态校验 · ${reconcileTarget.period_code}` : '结转状态校验'}

        open={reconcileOpen}

        onCancel={() => setReconcileOpen(false)}

        footer={(

          <Space>

            <Button onClick={() => setReconcileOpen(false)}>关闭</Button>

            {reconcileResult && !reconcileResult.period_status_consistent && reconcileTarget?.status === 'pl_transferred' && (

              <Popconfirm

                title="确认自动修正期间状态？"

                description="将把 pl_transferred 恢复为 open（仅未结账期间）。"

                onConfirm={() => handleReconcileFix()}

              >

                <Button type="primary" loading={reconcileLoading}>

                  自动修正状态

                </Button>

              </Popconfirm>

            )}

          </Space>

        )}

      >

        {reconcileLoading && !reconcileResult ? (

          <Text type="secondary">正在校验资产负债表与结转凭证一致性…</Text>

        ) : reconcileResult ? (

          <>

            <Descriptions size="small" column={2} bordered style={{ marginBottom: 16 }}>

              <Descriptions.Item label="期间状态">{reconcileResult.period_status}</Descriptions.Item>

              <Descriptions.Item label="状态一致">

                <Tag color={reconcileResult.period_status_consistent ? 'success' : 'error'}>

                  {reconcileResult.period_status_consistent ? '一致' : '不一致'}

                </Tag>

              </Descriptions.Item>

              <Descriptions.Item label="资产负债表平衡">

                <Tag color={reconcileResult.is_balanced ? 'success' : 'error'}>

                  {reconcileResult.is_balanced ? '平衡' : '不平衡'}

                </Tag>

              </Descriptions.Item>

              <Descriptions.Item label="系统结转凭证">

                {reconcileResult.has_system_pl_voucher ? '有' : '无'}

              </Descriptions.Item>

              <Descriptions.Item label="损益科目已清零">

                <Tag color={reconcileResult.profit_accounts_cleared ? 'success' : 'warning'}>

                  {reconcileResult.profit_accounts_cleared ? '是' : '否'}

                </Tag>

              </Descriptions.Item>

              <Descriptions.Item label="可无需手工结转">

                <Tag color={reconcileResult.can_close_without_manual_transfer ? 'success' : 'default'}>

                  {reconcileResult.can_close_without_manual_transfer ? '是' : '否'}

                </Tag>

              </Descriptions.Item>

              <Descriptions.Item label="校验结论" span={2}>

                {reconcileResult.message || (reconcileResult.ready ? '已满足结账条件' : '尚未满足')}

              </Descriptions.Item>

              <Descriptions.Item label="导入结转凭证" span={2}>

                {reconcileResult.imported_pl_voucher_count} 张

              </Descriptions.Item>

            </Descriptions>

            {reconcileResult.warnings.length > 0 ? (

              <List

                size="small"

                header={<Text strong>发现问题</Text>}

                dataSource={reconcileResult.warnings}

                renderItem={(item) => (

                  <List.Item>

                    <Text type="warning">{item}</Text>

                  </List.Item>

                )}

              />

            ) : (

              <Alert type="success" showIcon title="未发现结转状态异常" />

            )}

            {reconcileResult.fixed && (

              <Alert type="success" showIcon title="已自动修正期间状态" style={{ marginTop: 12 }} />

            )}

          </>

        ) : null}

      </Modal>



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

    </div>

  )

}


