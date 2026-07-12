import { useCallback, useEffect, useMemo, useState } from 'react'
import dayjs from 'dayjs'
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import {
  Alert,
  Breadcrumb,
  Button,
  Card,
  Col,
  Empty,
  Row,
  Segmented,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import { useNavigate } from 'react-router-dom'
import {
  api,
  type AccountingPeriod,
  type BalanceSheetPresentationMode,
  type BalanceSheetReport,
  type TrialBalanceRow,
} from '../../api/client'
import { ReclassificationWorkbenchPanel } from './ReclassificationWorkbenchPanel'
import { AccountContextActions } from './LedgerContextActions'
import {
  buildTreemapSection,
  canDrillDeeper,
  formatScaleMarks,
  toEchartsTreemapData,
  type TreemapLeaf,
} from '../../utils/balanceSheetTreemap'
import { formatAmount } from '../../money'

const { Text, Link: TextLink } = Typography

const ASSET_COLORS = ['#5470c6', '#73c0de', '#91cc75', '#3ba272', '#fac858', '#fc8452', '#9a60b4', '#ee6666']
const LIABILITY_COLORS = ['#ee6666', '#fc8452', '#fac858', '#9a60b4', '#73c0de', '#5470c6']
const EQUITY_COLORS = ['#91cc75', '#3ba272', '#5470c6', '#73c0de', '#fac858', '#9a60b4']

type ViewMode = 'chart' | 'table'
type ChartMetricMode = BalanceSheetPresentationMode

type LeDrillState = {
  side: 'liabilities' | 'equity'
  path: string[]
  detailRows: TrialBalanceRow[] | null
}

type AssetsDrillState = {
  path: string[]
  detailRows: TrialBalanceRow[] | null
}

type BalanceSheetWorkbenchBoardProps = {
  ledgerId?: number | null
}

type ScaleAnchor = 'top-left' | 'top-right' | 'bottom-right'

function treemapOption(
  title: string,
  sectionTotal: number,
  items: ReturnType<typeof toEchartsTreemapData>,
  colors: string[],
  titleAlign: 'left' | 'right' = 'center',
): EChartsOption {
  return {
    title: {
      text: title,
      left: titleAlign === 'right' ? 'right' : titleAlign === 'left' ? 'left' : 'center',
      top: 4,
      textStyle: { fontSize: 13, fontWeight: 600 },
    },
    tooltip: {
      formatter: (params: unknown) => {
        if (Array.isArray(params)) return ''
        const typed = params as { data?: TreemapLeaf & { rawBalance?: number } }
        const data = typed.data
        if (!data) return ''
        const raw = Number(data.rawBalance ?? data.value ?? 0)
        const share = sectionTotal > 0 ? ((data.value / sectionTotal) * 100).toFixed(1) : '0'
        return [
          `<b>${data.name}</b>`,
          `净额：${formatAmount(raw)}`,
          `占比：${share}%`,
          '点击：在当前图内继续细分',
        ].join('<br/>')
      },
    },
    series: [
      {
        type: 'treemap',
        roam: false,
        nodeClick: false,
        sort: false,
        breadcrumb: { show: false },
        left: 4,
        right: 4,
        top: 32,
        bottom: 4,
        label: {
          show: true,
          formatter: (params: unknown) => {
            const typed = params as { name?: string; value?: number | string }
            const name = typed.name || ''
            const shortName = name.length > 14 ? `${name.slice(0, 12)}…` : name
            const value = typeof typed.value === 'number' ? typed.value : Number(typed.value ?? 0)
            return `${shortName}\n${formatAmount(value)}`
          },
          fontSize: 11,
        },
        upperLabel: { show: false },
        itemStyle: {
          borderColor: '#fff',
          borderWidth: 2,
          gapWidth: 2,
        },
        data: items.map((item, index) => ({
          ...item,
          itemStyle: item.isContra
            ? {
                borderColor: '#cf1322',
                borderWidth: 2,
                borderType: 'dashed',
                color: 'rgba(255,255,255,0.85)',
              }
            : { color: colors[index % colors.length] },
        })),
      },
    ],
  } as EChartsOption
}

export function BalanceSheetWorkbenchBoard({ ledgerId }: BalanceSheetWorkbenchBoardProps) {
  const navigate = useNavigate()
  const [periods, setPeriods] = useState<AccountingPeriod[]>([])
  const [periodId, setPeriodId] = useState<number | null>(null)
  const [report, setReport] = useState<BalanceSheetReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [viewMode, setViewMode] = useState<ViewMode>('chart')
  const [chartMetricMode, setChartMetricMode] = useState<ChartMetricMode>('balance')
  const [assetsDrill, setAssetsDrill] = useState<AssetsDrillState>({ path: [], detailRows: null })
  const [leDrill, setLeDrill] = useState<LeDrillState | null>(null)
  const [finestDrillAccount, setFinestDrillAccount] = useState<string | null>(null)
  const [drillLoading, setDrillLoading] = useState(false)

  useEffect(() => {
    if (!ledgerId) {
      setPeriods([])
      setPeriodId(null)
      setReport(null)
      return
    }
    void api
      .listAccountingPeriods(undefined, ledgerId)
      .then((data) => {
        setPeriods(data)
        if (data.length > 0) {
          const open = data.find((p) => p.status === 'open') || data[0]
          setPeriodId(open.id)
        } else {
          setPeriodId(null)
        }
      })
      .catch(() => {
        setPeriods([])
        setPeriodId(null)
      })
  }, [ledgerId])

  useEffect(() => {
    if (!ledgerId || !periodId) {
      setReport(null)
      return
    }
    const selected = periods.find((p) => p.id === periodId)
    if (!selected) {
      setReport(null)
      return
    }
    const asOfDate =
      selected.status === 'closed'
        ? selected.end_date
        : dayjs().format('YYYY-MM-DD')
    setLoading(true)
    void api
      .getBalanceSheetReport({
        ledgerId,
        periodId,
        asOfDate,
        presentationMode: chartMetricMode,
      })
      .then((data) => {
        setReport({
          ...data,
          assets_total: Number(data.assets_total),
          liabilities_total: Number(data.liabilities_total),
          equity_total: Number(data.equity_total),
        })
        setAssetsDrill({ path: [], detailRows: null })
        setLeDrill(null)
        setFinestDrillAccount(null)
      })
      .catch((err) => {
        message.error(`资产负债表加载失败：${err instanceof Error ? err.message : String(err)}`)
        setReport(null)
      })
      .finally(() => setLoading(false))
  }, [periodId, ledgerId, periods, chartMetricMode])

  const selectedPeriod = periods.find((p) => p.id === periodId)
  const isNetMovement = chartMetricMode === 'net_movement'
  const metricLabel = isNetMovement ? '净发生额' : '期末余额'

  const hasVisibleBalance = useMemo(() => {
    if (!report) return false
    return (
      Number(report.assets_total) > 0 ||
      Number(report.liabilities_total) > 0 ||
      Number(report.equity_total) > 0
    )
  }, [report])
  const assetsRows = useMemo(() => {
    if (!report) return []
    return assetsDrill.detailRows ?? report.assets
  }, [report, assetsDrill.detailRows])

  const liabilitiesRows = useMemo(() => {
    if (!report) return []
    if (leDrill?.side === 'liabilities' && leDrill.detailRows) return leDrill.detailRows
    return report.liabilities
  }, [report, leDrill])

  const equityRows = useMemo(() => {
    if (!report) return []
    if (leDrill?.side === 'equity' && leDrill.detailRows) return leDrill.detailRows
    return report.equity
  }, [report, leDrill])

  const assetsDrillPrefix = assetsDrill.path[assetsDrill.path.length - 1] ?? null
  const liabilitiesDrillPrefix = leDrill?.side === 'liabilities' ? leDrill.path[leDrill.path.length - 1] ?? null : null
  const equityDrillPrefix = leDrill?.side === 'equity' ? leDrill.path[leDrill.path.length - 1] ?? null : null

  const assetsSection = useMemo(() => {
    if (!report) return null
    return buildTreemapSection(assetsRows, '资产', {
      drillPrefix: assetsDrillPrefix,
      allRows: assetsRows,
    })
  }, [report, assetsRows, assetsDrillPrefix])

  const liabilitiesSection = useMemo(() => {
    if (!report) return null
    return buildTreemapSection(liabilitiesRows, '负债', {
      drillPrefix: liabilitiesDrillPrefix,
      allRows: liabilitiesRows,
    })
  }, [report, liabilitiesRows, liabilitiesDrillPrefix])

  const equitySection = useMemo(() => {
    if (!report) return null
    return buildTreemapSection(equityRows, '所有者权益', {
      drillPrefix: equityDrillPrefix,
      allRows: equityRows,
    })
  }, [report, equityRows, equityDrillPrefix])

  const leTotal = useMemo(() => {
    if (!report) return 0
    return Number(report.liabilities_total) + Number(report.equity_total)
  }, [report])

  const focusAccountCode = useMemo(() => {
    if (finestDrillAccount) return finestDrillAccount
    if (assetsDrill.path.length > 0) return assetsDrill.path[assetsDrill.path.length - 1]
    if (leDrill?.path.length) return leDrill.path[leDrill.path.length - 1]
    return null
  }, [finestDrillAccount, assetsDrill.path, leDrill?.path])

  const resetDrill = useCallback(() => {
    setAssetsDrill({ path: [], detailRows: null })
    setLeDrill(null)
    setFinestDrillAccount(null)
  }, [])

  const drillIntoAccount = useCallback(
    async (
      side: 'assets' | 'liabilities' | 'equity',
      data: TreemapLeaf & { id?: string },
    ) => {
      if (!report || !ledgerId || !periodId || data.isOther) return

      const category = side === 'assets' ? 'asset' : side === 'liabilities' ? 'liability' : 'equity'
      const baseRows =
        side === 'assets'
          ? assetsDrill.detailRows ?? report.assets
          : side === 'liabilities'
            ? (leDrill?.side === 'liabilities' ? leDrill.detailRows : null) ?? report.liabilities
            : (leDrill?.side === 'equity' ? leDrill.detailRows : null) ?? report.equity

      const currentPath =
        side === 'assets'
          ? assetsDrill.path
          : leDrill?.side === side
            ? leDrill.path
            : []

      const nextPath = [...currentPath, data.accountCode]
      setFinestDrillAccount(null)

      const canDrillLocally = canDrillDeeper(baseRows, data.accountCode)
      const localSection = buildTreemapSection(baseRows, side, {
        drillPrefix: data.accountCode,
        allRows: baseRows,
      })
      const localTiles = localSection.items.filter((item) => !item.isOther)

      if (canDrillLocally && localTiles.length > 1) {
        if (side === 'assets') {
          setAssetsDrill((prev) => ({ ...prev, path: nextPath }))
        } else {
          setLeDrill({
            side,
            path: nextPath,
            detailRows: leDrill?.side === side ? leDrill.detailRows : null,
          })
        }
        return
      }

      setDrillLoading(true)
      try {
        const asOfDate =
          selectedPeriod?.status === 'closed'
            ? selectedPeriod.end_date
            : dayjs().format('YYYY-MM-DD')
        const breakdown = await api.getBalanceSheetBreakdown({
          ledgerId,
          periodId,
          accountPrefix: data.accountCode,
          category,
          asOfDate,
          presentationMode: chartMetricMode,
        })
        const detailRows = breakdown.rows.map((row) => ({
          ...row,
          closing_debit: Number(row.closing_debit),
          closing_credit: Number(row.closing_credit),
        }))
        const detailSection = buildTreemapSection(detailRows, side, {
          drillPrefix: data.accountCode,
          allRows: detailRows,
        })
        const detailTiles = detailSection.items.filter((item) => !item.isOther)

        if (detailTiles.length > 1) {
          if (side === 'assets') {
            setAssetsDrill({ path: nextPath, detailRows })
          } else {
            setLeDrill({ side, path: nextPath, detailRows })
          }
          return
        }

        message.info('该科目已至结构最细层级，图形无法继续细分')
        setFinestDrillAccount(data.accountCode)
      } catch (error) {
        const detail = error instanceof Error ? error.message : String(error)
        message.error(`下钻加载失败：${detail}`)
      } finally {
        setDrillLoading(false)
      }
    },
    [
      report,
      ledgerId,
      periodId,
      assetsDrill.detailRows,
      assetsDrill.path,
      leDrill,
      selectedPeriod,
      chartMetricMode,
    ],
  )

  const handleAssetsClick = useCallback(
    (params: { data?: TreemapLeaf & { id?: string } }) => {
      const data = params.data
      if (!data?.accountCode) return
      void drillIntoAccount('assets', data)
    },
    [drillIntoAccount],
  )

  const handleLiabilitiesClick = useCallback(
    (params: { data?: TreemapLeaf & { id?: string } }) => {
      const data = params.data
      if (!data?.accountCode) return
      void drillIntoAccount('liabilities', data)
    },
    [drillIntoAccount],
  )

  const handleEquityClick = useCallback(
    (params: { data?: TreemapLeaf & { id?: string } }) => {
      const data = params.data
      if (!data?.accountCode) return
      void drillIntoAccount('equity', data)
    },
    [drillIntoAccount],
  )

  const jumpToDrillLevel = useCallback(
    (side: 'assets' | 'liabilities' | 'equity', level: number) => {
      if (side === 'assets') {
        if (level < 0) {
          setAssetsDrill({ path: [], detailRows: null })
        } else {
          setAssetsDrill((prev) => ({
            path: prev.path.slice(0, level + 1),
            detailRows: prev.detailRows,
          }))
        }
        setFinestDrillAccount(null)
        return
      }
      setLeDrill((prev) => {
        if (!prev || prev.side !== side) return prev
        if (level < 0) return null
        return {
          ...prev,
          path: prev.path.slice(0, level + 1),
        }
      })
      setFinestDrillAccount(null)
    },
    [],
  )

  const sortedTableRows = useCallback(
    (rows: TrialBalanceRow[]) =>
      [...rows].sort((a, b) =>
        a.account_code.localeCompare(b.account_code, 'zh-CN', { numeric: true }),
      ),
    [],
  )

  const tableColumns = [
    { title: '代码', dataIndex: 'account_code', key: 'account_code', width: 100 },
    { title: '科目', dataIndex: 'account_name', key: 'account_name' },
    {
      title: isNetMovement ? '净借' : '期末借',
      dataIndex: 'closing_debit',
      key: 'closing_debit',
      render: (v: number) => formatAmount(v),
    },
    {
      title: isNetMovement ? '净贷' : '期末贷',
      dataIndex: 'closing_credit',
      key: 'closing_credit',
      render: (v: number) => formatAmount(v),
    },
    {
      title: '',
      key: 'actions',
      width: 48,
      render: (_: unknown, row: TrialBalanceRow) => (
        <AccountContextActions accountCode={row.account_code} periodId={periodId ?? undefined} />
      ),
    },
  ]

  if (!ledgerId) {
    return (
      <Card>
        <Empty description="请先选择账簿以查看资产负债表结构" />
      </Card>
    )
  }

  return (
    <Card
      title="资产负债表结构"
      loading={loading || drillLoading}
      style={{ marginBottom: 16 }}
      extra={
        <Space wrap>
          <Select
            value={periodId ?? undefined}
            placeholder="选择会计期间"
            style={{ width: 240 }}
            onChange={setPeriodId}
            options={periods.map((p) => ({
              value: p.id,
              label: `${p.period_code}（${p.start_date} ~ ${p.end_date}）`,
            }))}
          />
          <Segmented
            value={chartMetricMode}
            onChange={(v) => setChartMetricMode(v as ChartMetricMode)}
            options={[
              { label: '期间余额', value: 'balance' },
              { label: '净发生额', value: 'net_movement' },
            ]}
          />
          <Segmented
            value={viewMode}
            onChange={(v) => setViewMode(v as ViewMode)}
            options={[
              { label: '图表视图', value: 'chart' },
              { label: '表格视图', value: 'table' },
            ]}
          />
        </Space>
      }
    >
      {!report ? (
        <Empty description="请选择会计期间加载资产负债表" />
      ) : (
        <>
          {isNetMovement ? (
            <Alert
              type="info"
              showIcon
              style={{ marginBottom: 12 }}
              message="净发生额视图：按指定期间本期活动展示"
              description="资产负债权益取本期净发生额（借贷同有发生时按科目余额方向计算）；损益类科目已汇总进 4103 本年利润，不在图中单独列示。"
            />
          ) : report.is_balanced ? (
            <Alert
              type="success"
              showIcon
              style={{ marginBottom: 12 }}
              message={`资产 ${formatAmount(report.assets_total)} = 负债 ${formatAmount(report.liabilities_total)} + 权益 ${formatAmount(report.equity_total)}（期末恒等式平衡）`}
            />
          ) : (
            <Alert
              type="error"
              showIcon
              style={{ marginBottom: 12 }}
              message="资产负债期末恒等式不平衡"
              description={
                <Space direction="vertical" size={4}>
                  <Text>
                    资产 {formatAmount(report.assets_total)} ≠ 负债 {formatAmount(report.liabilities_total)} + 权益{' '}
                    {formatAmount(report.equity_total)}
                  </Text>
                  <Text type="secondary">可能原因：本期损益尚未结转。</Text>
                  <Button type="link" size="small" style={{ padding: 0 }} onClick={() => navigate('/accounting-periods')}>
                    前往会计期间执行损益结转
                  </Button>
                </Space>
              }
            />
          )}

          {isNetMovement && (
            <Alert
              type={report.is_balanced ? 'success' : 'warning'}
              showIcon
              style={{ marginBottom: 12 }}
              message={
                report.is_balanced
                  ? `本期结构净发生额：资产 ${formatAmount(report.assets_total)} = 负债 ${formatAmount(report.liabilities_total)} + 权益 ${formatAmount(report.equity_total)}`
                  : `本期结构净发生额：资产 ${formatAmount(report.assets_total)} ≠ 负债 ${formatAmount(report.liabilities_total)} + 权益 ${formatAmount(report.equity_total)}`
              }
            />
          )}

          {report.pl_transfer_health && report.pl_transfer_health.warnings.length > 0 && (
            <Alert
              type="warning"
              showIcon
              style={{ marginBottom: 12 }}
              message="损益结转状态与数据不一致"
              description={
                <ul style={{ margin: '4px 0 0', paddingLeft: 18 }}>
                  {report.pl_transfer_health.warnings.map((item, index) => (
                    <li key={`pl-warn-${index}`}>{item}</li>
                  ))}
                </ul>
              }
            />
          )}

          {report.unmapped_entry_net != null && Number(report.unmapped_entry_net) !== 0 && (
            <Alert
              type="info"
              showIcon
              style={{ marginBottom: 12 }}
              message={`仍有 ${formatAmount(Number(report.unmapped_entry_net))} 净额未能映射到科目表（已优先使用 resolved_account_code 汇总）`}
            />
          )}

          {report.reclassification_summary && (
            <ReclassificationWorkbenchPanel summary={report.reclassification_summary} />
          )}

          <Row gutter={16} style={{ marginBottom: 12 }}>
            <Col xs={24} md={8}>
              <Statistic title={`资产${metricLabel}`} value={report.assets_total} prefix="¥" precision={2} />
            </Col>
            <Col xs={24} md={8}>
              <Statistic title={`负债${metricLabel}`} value={report.liabilities_total} prefix="¥" precision={2} />
            </Col>
            <Col xs={24} md={8}>
              <Statistic title={`负债+权益${metricLabel}`} value={leTotal} prefix="¥" precision={2} />
            </Col>
          </Row>

          <Space style={{ marginBottom: 12 }}>
            <Tag color={isNetMovement ? 'purple' : report.balance_source === 'snapshot' ? 'default' : 'processing'}>
              {isNetMovement ? '净发生额' : report.balance_source === 'snapshot' ? '结账快照' : '即时余额'}
            </Tag>
            <Text type="secondary">截止 {report.as_of_date || selectedPeriod?.end_date}</Text>
          </Space>

          {!hasVisibleBalance && (
            <Alert
              type="info"
              showIcon
              style={{ marginBottom: 12 }}
              message="当前截止日暂无资产/负债/权益余额"
              description="请确认该期间已有凭证分录，或切换到表格视图查看全部科目。损益类科目需结转后才进入资产负债表。"
            />
          )}

          {viewMode === 'chart' && assetsSection && liabilitiesSection && equitySection && hasVisibleBalance && (
            <>
              <Breadcrumb
                style={{ marginBottom: 8 }}
                items={[
                  {
                    title: <TextLink onClick={resetDrill}>资产负债表</TextLink>,
                  },
                  ...assetsDrill.path.map((code, index) => ({
                    title: (
                      <TextLink onClick={() => jumpToDrillLevel('assets', index)}>
                        <Tag color="blue">资产 · {code}</Tag>
                      </TextLink>
                    ),
                  })),
                  ...(leDrill?.side === 'liabilities'
                    ? leDrill.path.map((code, index) => ({
                        title: (
                          <TextLink onClick={() => jumpToDrillLevel('liabilities', index)}>
                            <Tag color="volcano">负债 · {code}</Tag>
                          </TextLink>
                        ),
                      }))
                    : []),
                  ...(leDrill?.side === 'equity'
                    ? leDrill.path.map((code, index) => ({
                        title: (
                          <TextLink onClick={() => jumpToDrillLevel('equity', index)}>
                            <Tag color="green">权益 · {code}</Tag>
                          </TextLink>
                        ),
                      }))
                    : []),
                ]}
              />
              {focusAccountCode && (
                <div style={{ marginBottom: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Text type="secondary">当前科目：</Text>
                  <Tag color="processing">{focusAccountCode}</Tag>
                  <AccountContextActions accountCode={focusAccountCode} periodId={periodId ?? undefined} />
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    点击色块继续下钻；需要分录/凭证明细时使用「更多」
                  </Text>
                </div>
              )}
              {finestDrillAccount && (
                <Alert
                  type="info"
                  showIcon
                  style={{ marginBottom: 8 }}
                  message={`科目 ${finestDrillAccount} 已无法在本图内继续细分`}
                  description="图形下钻用于科目结构分析。仅当需要查看逐笔分录或凭证时，再进入明细账。"
                  action={(
                    <AccountContextActions accountCode={finestDrillAccount} periodId={periodId ?? undefined} />
                  )}
                />
              )}
              <Row gutter={12} align="stretch">
                <Col xs={24} lg={12}>
                  <TreemapPanel
                    anchor="top-left"
                    height={672}
                    title={`资产 ${formatAmount(assetsSection.total)}（${metricLabel}）`}
                    sectionTotal={assetsSection.total}
                    items={toEchartsTreemapData(assetsSection)}
                    colors={ASSET_COLORS}
                    titleAlign="left"
                    onClick={handleAssetsClick}
                  />
                </Col>
                <Col xs={24} lg={12}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 12, height: 672 }}>
                    <TreemapPanel
                      anchor="top-right"
                      height={330}
                      title={`负债 ${formatAmount(liabilitiesSection.total)}（${metricLabel}）`}
                      sectionTotal={liabilitiesSection.total}
                      items={toEchartsTreemapData(liabilitiesSection)}
                      colors={LIABILITY_COLORS}
                      titleAlign="right"
                      onClick={handleLiabilitiesClick}
                    />
                    <TreemapPanel
                      anchor="bottom-right"
                      height={330}
                      title={`所有者权益 ${formatAmount(equitySection.total)}（${metricLabel}）`}
                      sectionTotal={equitySection.total}
                      items={toEchartsTreemapData(equitySection)}
                      colors={EQUITY_COLORS}
                      titleAlign="right"
                      onClick={handleEquityClick}
                    />
                  </div>
                </Col>
              </Row>
              <Row gutter={12} style={{ marginTop: 12 }}>
                <Col span={24}>
                  <BalanceLayoutGuide
                    assetsTotal={Number(report.assets_total)}
                    liabilitiesTotal={Number(report.liabilities_total)}
                    equityTotal={Number(report.equity_total)}
                    leTotal={leTotal}
                    balanced={report.is_balanced}
                    metricLabel={metricLabel}
                    isNetMovement={isNetMovement}
                  />
                </Col>
              </Row>
              <Text type="secondary" style={{ display: 'block', marginTop: 8, fontSize: 12 }}>
                图形提供两种口径：「期间余额」展示截止日存量；「净发生额」展示本期活动（损益汇总至 4103）。点击色块仅在当前图内逐级细分；只有需要分录或凭证维度时，才使用「分录/凭证查询」。
              </Text>
            </>
          )}

          {viewMode === 'table' && (
            <>
              <Card title="资产" size="small" style={{ marginBottom: 12 }}>
                <Table<TrialBalanceRow>
                  rowKey="account_code"
                  dataSource={sortedTableRows(report.assets)}
                  columns={tableColumns}
                  pagination={false}
                  size="small"
                />
              </Card>
              <Card title="负债" size="small" style={{ marginBottom: 12 }}>
                <Table<TrialBalanceRow>
                  rowKey="account_code"
                  dataSource={sortedTableRows(report.liabilities)}
                  columns={tableColumns}
                  pagination={false}
                  size="small"
                />
              </Card>
              <Card title="所有者权益" size="small">
                <Table<TrialBalanceRow>
                  rowKey="account_code"
                  dataSource={sortedTableRows(report.equity)}
                  columns={tableColumns}
                  pagination={false}
                  size="small"
                />
              </Card>
            </>
          )}
        </>
      )}
    </Card>
  )
}

function TreemapPanel({
  anchor,
  height,
  title,
  sectionTotal,
  items,
  colors,
  titleAlign,
  onClick,
}: {
  anchor: ScaleAnchor
  height: number
  title: string
  sectionTotal: number
  items: ReturnType<typeof toEchartsTreemapData>
  colors: string[]
  titleAlign: 'left' | 'right'
  onClick: (params: { data?: TreemapLeaf & { id?: string } }) => void
}) {
  const anchorLabel =
    anchor === 'top-left' ? '↖ 资产区' : anchor === 'top-right' ? '↗ 负债区' : '↘ 权益区'
  const yOnRight = anchor === 'top-right' || anchor === 'bottom-right'
  const xOnTop = anchor === 'bottom-right'
  const chartHeight = height - 52 - 52

  return (
    <div
      style={{
        border: '1px solid #f0f0f0',
        borderRadius: 8,
        padding: 4,
        position: 'relative',
        height,
        display: 'grid',
        gridTemplateColumns: yOnRight ? '1fr 52px' : '52px 1fr',
        gridTemplateRows: xOnTop ? '52px 1fr' : '1fr 52px',
      }}
    >
      <Tag
        color="default"
        style={{
          position: 'absolute',
          zIndex: 2,
          top: xOnTop ? 'auto' : 6,
          bottom: xOnTop ? 6 : 'auto',
          left: yOnRight ? 'auto' : 8,
          right: yOnRight ? 8 : 'auto',
          margin: 0,
          fontSize: 11,
        }}
      >
        {anchorLabel}
      </Tag>
      {!xOnTop && (
        <div style={{ gridColumn: yOnRight ? 2 : 1, gridRow: '1 / 3' }}>
          <ScaleAxis total={sectionTotal} axis="y" anchor={anchor} />
        </div>
      )}
      {xOnTop && (
        <div style={{ gridColumn: 1, gridRow: 1 }}>
          <ScaleAxis total={sectionTotal} axis="x" anchor={anchor} />
        </div>
      )}
      <div style={{ gridColumn: yOnRight ? 1 : 2, gridRow: xOnTop ? 2 : 1, minHeight: 0 }}>
        <ReactECharts
          option={treemapOption(title, sectionTotal, items, colors, titleAlign)}
          style={{ height: chartHeight }}
          onEvents={{ click: onClick }}
        />
      </div>
      {xOnTop && (
        <div style={{ gridColumn: 2, gridRow: '1 / 3' }}>
          <ScaleAxis total={sectionTotal} axis="y" anchor={anchor} />
        </div>
      )}
      {!xOnTop && (
        <div style={{ gridColumn: yOnRight ? 1 : 2, gridRow: 2 }}>
          <ScaleAxis total={sectionTotal} axis="x" anchor={anchor} />
        </div>
      )}
    </div>
  )
}

function BalanceLayoutGuide({
  assetsTotal,
  liabilitiesTotal,
  equityTotal,
  leTotal,
  balanced,
  metricLabel,
  isNetMovement,
}: {
  assetsTotal: number
  liabilitiesTotal: number
  equityTotal: number
  leTotal: number
  balanced: boolean
  metricLabel: string
  isNetMovement: boolean
}) {
  return (
    <div
      style={{
        border: '1px dashed #d9d9d9',
        borderRadius: 8,
        padding: 16,
        background: '#fafafa',
      }}
    >
      <Text strong>方位说明与恒等式</Text>
      <Text type="secondary" style={{ display: 'block', marginTop: 8, fontSize: 12 }}>
        左侧资产区高度与右侧「负债 + 所有者权益」对齐；各区域刻度轴均标注金额与百分比（X/Y 双轴）。当前口径：{metricLabel}。
      </Text>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: 8,
          marginTop: 12,
          fontSize: 12,
        }}
      >
        <div style={{ padding: 8, background: '#fff', borderRadius: 6, border: '1px solid #e6f4ff' }}>
          <Text type="secondary">↖ 资产{metricLabel}</Text>
          <div><Text strong>{formatAmount(assetsTotal)}</Text></div>
        </div>
        <div style={{ padding: 8, background: '#fff', borderRadius: 6, border: '1px solid #fff1f0' }}>
          <Text type="secondary">↗ 负债{metricLabel}</Text>
          <div><Text strong>{formatAmount(liabilitiesTotal)}</Text></div>
        </div>
        <div style={{ padding: 8, background: '#fff', borderRadius: 6, border: '1px solid #f6ffed' }}>
          <Text type="secondary">↘ 权益{metricLabel}</Text>
          <div><Text strong>{formatAmount(equityTotal)}</Text></div>
        </div>
        <div style={{ padding: 8, background: '#fff', borderRadius: 6, border: '1px solid #f0f0f0' }}>
          <Text type="secondary">负债 + 权益{metricLabel}</Text>
          <div><Text strong>{formatAmount(leTotal)}</Text></div>
        </div>
      </div>
      <Text type={balanced ? 'success' : 'danger'} style={{ display: 'block', marginTop: 12, fontSize: 12 }}>
        {balanced
          ? isNetMovement
            ? `本期结构净发生额对齐：资产 ${formatAmount(assetsTotal)} = 负债 + 权益 ${formatAmount(leTotal)}`
            : `恒等式成立：资产 ${formatAmount(assetsTotal)} = 负债 + 权益 ${formatAmount(leTotal)}`
          : isNetMovement
            ? `本期结构净发生额差额 ${formatAmount(assetsTotal - leTotal)}`
            : `差额 ${formatAmount(assetsTotal - leTotal)}（资产 ${formatAmount(assetsTotal)} ≠ 负债+权益 ${formatAmount(leTotal)}）`}
      </Text>
    </div>
  )
}

function ScaleAxis({
  total,
  axis,
  anchor,
}: {
  total: number
  axis: 'x' | 'y'
  anchor: ScaleAnchor
}) {
  const marks = formatScaleMarks(total)
  const reverseX = anchor === 'top-right' || anchor === 'bottom-right'
  const reverseY = anchor === 'bottom-right'
  const ordered = axis === 'x'
    ? (reverseX ? [...marks].reverse() : marks)
    : (reverseY ? [...marks].reverse() : marks)

  const isVertical = axis === 'y'

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: isVertical ? 'column' : 'row',
        justifyContent: 'space-between',
        alignItems: isVertical ? 'stretch' : 'center',
        height: isVertical ? '100%' : 'auto',
        width: isVertical ? '100%' : 'auto',
        padding: isVertical ? '8px 4px' : '4px 8px',
        fontSize: 10,
        color: '#8c8c8c',
        borderTop: axis === 'x' && anchor !== 'bottom-right' ? '1px dashed #e8e8e8' : undefined,
        borderBottom: axis === 'x' && anchor === 'bottom-right' ? '1px dashed #e8e8e8' : undefined,
        borderLeft: axis === 'y' && anchor === 'top-left' ? '1px dashed #e8e8e8' : undefined,
        borderRight: axis === 'y' && anchor !== 'top-left' ? '1px dashed #e8e8e8' : undefined,
        boxSizing: 'border-box',
      }}
    >
      {ordered.map((mark, index) => {
        const pctIndex = axis === 'x'
          ? (reverseX ? marks.length - 1 - index : index)
          : (reverseY ? marks.length - 1 - index : index)
        const pct = Math.round(pctIndex * 25)
        return (
          <span
            key={`${axis}-${mark}-${index}`}
            style={{
              textAlign: isVertical ? (anchor === 'top-left' ? 'right' : 'left') : 'center',
              lineHeight: 1.25,
              whiteSpace: 'nowrap',
            }}
          >
            {pct}%
            <br />
            ¥{mark}
          </span>
        )
      })}
    </div>
  )
}
