import type { ReactNode } from 'react'
import { Typography } from 'antd'
import './ClassicReportLayout.css'

const { Title, Text } = Typography

type ClassicReportKind = 'balance_sheet' | 'income_statement' | 'cash_flow'
type ClassicReportOrientation = 'portrait' | 'landscape'

type ClassicReportChromeProps = {
  kind: ClassicReportKind
  ledgerName?: string
  asOfDate?: string
  periodCode?: string
}

function periodYear(periodCode?: string, asOfDate?: string): string {
  if (periodCode && periodCode.length >= 4) return periodCode.slice(0, 4)
  if (asOfDate && asOfDate.length >= 4) return asOfDate.slice(0, 4)
  return '—'
}

export function ClassicReportSheet({
  orientation = 'portrait',
  children,
}: {
  orientation?: ClassicReportOrientation
  children: ReactNode
}) {
  return (
    <div
      className={`classic-report-sheet classic-report-sheet--${orientation}`}
    >
      {children}
    </div>
  )
}

export function ClassicReportHeader({ kind, ledgerName, asOfDate, periodCode }: ClassicReportChromeProps) {
  const title = kind === 'balance_sheet' ? '资产负债表' : kind === 'income_statement' ? '损益表' : '现金流量表'
  const dateLabel =
    kind === 'balance_sheet' ? '编制日期' : kind === 'income_statement' ? '填表日期' : `${periodYear(periodCode, asOfDate)}年`

  return (
    <div className="classic-report-header">
      <Title level={4} className="classic-report-header__title">
        {title}
      </Title>
      <div className="classic-report-header__meta">
        <Text className="classic-report-header__meta-item">编制单位：{ledgerName || '—'}</Text>
        <Text className="classic-report-header__meta-item">
          {kind === 'cash_flow' ? dateLabel : `${dateLabel}：${asOfDate || '—'}`}
        </Text>
        <Text className="classic-report-header__meta-item classic-report-header__meta-item--right">单位：元</Text>
      </div>
    </div>
  )
}

type ClassicReportFooterProps = {
  preparerName?: string
  approverName?: string
  reviewerName?: string
}

export function ClassicReportFooter({ preparerName, approverName, reviewerName }: ClassicReportFooterProps) {
  return (
    <div className="classic-report-footer">
      <span className="classic-report-footer__item">制表人：{preparerName || '____________'}</span>
      <span className="classic-report-footer__item">负责人：{approverName || '____________'}</span>
      <span className="classic-report-footer__item">复核：{reviewerName || '____________'}</span>
    </div>
  )
}

export function ClassicReportTableWrap({ children }: { children: ReactNode }) {
  return <div className="classic-report-table-wrap">{children}</div>
}
