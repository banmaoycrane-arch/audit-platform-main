import { ChartOfAccountsPanel } from '../../components/accounting/ChartOfAccountsPanel'

/** 兼容旧入口；推荐 /ledger/dimensions?tab=coa */
export function ChartOfAccountsPage() {
  return (
    <div style={{ padding: 24 }}>
      <ChartOfAccountsPanel />
    </div>
  )
}
