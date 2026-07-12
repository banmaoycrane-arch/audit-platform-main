import { Button, Dropdown } from 'antd'
import type { MenuProps } from 'antd'
import { MoreOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { step4ReviewPath } from '../../utils/voucherFlowRoutes'

type AccountActionsProps = {
  accountCode: string
  periodId?: number
  size?: 'small' | 'middle'
}

export function AccountContextActions({ accountCode, periodId, size = 'small' }: AccountActionsProps) {
  const navigate = useNavigate()

  const items: MenuProps['items'] = [
    {
      key: 'subsidiary',
      label: '明细账',
      onClick: () =>
        navigate('/ledger/subsidiary-ledger', {
          state: {
            accountCodes: [accountCode],
            periodIds: periodId ? [periodId] : undefined,
            autoSearch: true,
          },
        }),
    },
    {
      key: 'vouchers',
      label: '凭证查询',
      onClick: () => {
        const params = new URLSearchParams({ account_code: accountCode })
        if (periodId) params.set('period_id', String(periodId))
        navigate(`/ledger/entries?${params.toString()}`)
      },
    },
    {
      key: 'trial-balance',
      label: '科目余额表',
      onClick: () => {
        const params = new URLSearchParams({ account_code: accountCode })
        if (periodId) params.set('period_id', String(periodId))
        navigate(`/reports/trial-balance?${params.toString()}`)
      },
    },
  ]

  return (
    <Dropdown menu={{ items }} trigger={['click']}>
      <Button type="text" size={size} icon={<MoreOutlined />} aria-label="更多操作" />
    </Dropdown>
  )
}

type PendingVoucherActionsProps = {
  voucherNo: string
  importJobId?: number
  periodId?: number
  size?: 'small' | 'middle'
}

export function PendingVoucherContextActions({
  voucherNo,
  importJobId,
  periodId,
  size = 'small',
}: PendingVoucherActionsProps) {
  const navigate = useNavigate()

  const items: MenuProps['items'] = [
    importJobId
      ? {
          key: 'review',
          label: '去 Step4 复核',
          onClick: () => navigate(step4ReviewPath(importJobId, 'vouchers')),
        }
      : null,
    {
      key: 'query',
      label: '凭证查询',
      onClick: () => {
        const params = new URLSearchParams({ voucher_no: voucherNo })
        if (periodId) params.set('period_id', String(periodId))
        navigate(`/ledger/entries?${params.toString()}`)
      },
    },
    {
      key: 'subsidiary',
      label: '明细账',
      onClick: () =>
        navigate('/ledger/subsidiary-ledger', {
          state: {
            voucherNo,
            periodIds: periodId ? [periodId] : undefined,
            autoSearch: true,
          },
        }),
    },
  ].filter(Boolean) as MenuProps['items']

  return (
    <Dropdown menu={{ items }} trigger={['click']}>
      <Button type="text" size={size} icon={<MoreOutlined />} aria-label="更多操作" />
    </Dropdown>
  )
}
