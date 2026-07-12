import { useEffect, useMemo, useState } from 'react'
import { Alert, Button, Card, Space, Steps, Tag, Typography } from 'antd'
import { useNavigate } from 'react-router-dom'
import {
  AuditOutlined,
  CalendarOutlined,
  FileSearchOutlined,
  PieChartOutlined,
  HomeOutlined,
} from '@ant-design/icons'
import { api, type AccountingPeriod } from '../../api/client'
import { useAuthStore } from '../../stores/authStore'
import { reportPathWithPeriod } from '../../utils/ledgerNavTaxonomy'

const { Text, Paragraph } = Typography

type Step5CompletionGuideProps = {
  jobId: number
  periodId?: number
}

const PERIOD_STATUS_META: Record<string, { color: string; text: string }> = {
  open: { color: 'green', text: '已开启' },
  pl_transferred: { color: 'blue', text: '已结转损益' },
  closed: { color: 'default', text: '已结账' },
  reopened: { color: 'purple', text: '已反结账' },
}

export function Step5CompletionGuide({ jobId, periodId }: Step5CompletionGuideProps) {
  const navigate = useNavigate()
  const { currentLedgerId } = useAuthStore()
  const [period, setPeriod] = useState<AccountingPeriod | null>(null)

  useEffect(() => {
    if (!currentLedgerId) {
      setPeriod(null)
      return
    }
    void api
      .listAccountingPeriods(undefined, currentLedgerId)
      .then((list) => {
        if (periodId) {
          setPeriod(list.find((p) => p.id === periodId) ?? null)
          return
        }
        const open = list.find((p) => p.status === 'open' || p.status === 'reopened')
        setPeriod(open ?? list[list.length - 1] ?? null)
      })
      .catch(() => setPeriod(null))
  }, [currentLedgerId, periodId])

  const workflowStep = useMemo(() => {
    if (!period) return 0
    if (period.status === 'closed') return 3
    if (period.status === 'pl_transferred') return 2
    return 1
  }, [period])

  const periodTag = period
    ? PERIOD_STATUS_META[period.status] ?? { color: 'default', text: period.status }
    : null

  const trialPath = reportPathWithPeriod('/reports/trial-balance', period?.id)
  const balancePath = reportPathWithPeriod('/reports/balance-sheet', period?.id)
  const incomePath = reportPathWithPeriod('/reports/income-statement', period?.id)
  const cashFlowPath = reportPathWithPeriod('/reports/cash-flow-statement', period?.id)

  return (
    <Card
      title="入账完成 — 请按总账月结顺序继续"
      style={{ marginTop: 24 }}
      extra={
        period && periodTag ? (
          <Tag color={periodTag.color}>
            {period.period_code} · {periodTag.text}
          </Tag>
        ) : null
      }
    >
      <Paragraph type="secondary" style={{ marginBottom: 16 }}>
        凭证已确认入账。按记账 v1.0 验收路径（A9→A10→A11），建议依次完成：核对凭证 → 损益结转 → 四大报表核对 → 打包导出 → 结账。
      </Paragraph>

      <Steps
        direction="vertical"
        size="small"
        current={workflowStep}
        style={{ marginBottom: 20 }}
        items={[
          {
            title: '核对已过账凭证',
            description: '在凭证查询中确认本分录批次已入账且借贷平衡。',
          },
          {
            title: '损益结转',
            description: period?.status === 'open' || period?.status === 'reopened'
              ? '当前期间尚未结转损益，请前往「损益结转与结账」执行。'
              : '损益已结转，可进入报表核对。',
          },
          {
            title: '财务报表编制与导出',
            description: '按科目余额表 → 资产负债表 → 利润表 → 现金流量表顺序核对；报表中心可打包 ZIP 或导出签章 PDF。',
          },
          {
            title: '期间结账（如适用）',
            description: '报表核对无误后，在会计期间页执行结账生成快照。',
          },
        ]}
      />

      {!period && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message="未找到可用会计期间"
          description="请先在「损益结转与结账」中创建期间，再执行结转与报表核对。"
        />
      )}

      <Space wrap size="middle">
        <Button
          icon={<FileSearchOutlined />}
          onClick={() => navigate(`/ledger/entries?fromWizard=1&jobId=${jobId}`)}
        >
          核对凭证
        </Button>
        <Button
          type={period && (period.status === 'open' || period.status === 'reopened') ? 'primary' : 'default'}
          icon={<CalendarOutlined />}
          onClick={() => navigate('/accounting-periods')}
        >
          损益结转与结账
        </Button>
        <Button icon={<PieChartOutlined />} onClick={() => navigate('/reports')}>
          报表中心（ZIP / PDF）
        </Button>
        <Button onClick={() => navigate(trialPath)}>科目余额表</Button>
        <Button onClick={() => navigate(balancePath)}>资产负债表</Button>
        <Button onClick={() => navigate(incomePath)}>利润表</Button>
        <Button onClick={() => navigate(cashFlowPath)}>现金流量表</Button>
        <Button icon={<AuditOutlined />} onClick={() => navigate('/ledger/control-defects')}>
          内控待办
        </Button>
        <Button icon={<HomeOutlined />} onClick={() => navigate('/ledger/workspace')}>
          返回总账工作台
        </Button>
      </Space>

      {period && (period.status === 'open' || period.status === 'reopened') && (
        <Alert
          type="info"
          showIcon
          style={{ marginTop: 16 }}
          message="资产负债表核对提示"
          description={
            <Text type="secondary">
              开放期间若资产/负债不平衡，通常因损益尚未结转。请先完成损益结转再核对资产负债表与利润表。
            </Text>
          }
        />
      )}
    </Card>
  )
}
