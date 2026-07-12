export type MasterSyncResult = {
  synced?: boolean
  reason?: string
  target?: string
  action?: string
  id?: number
  category_code?: string
}

const TARGET_LABEL: Record<string, string> = {
  bank_accounts: '开户清单',
  counterparties: '往来单位',
}

export function describeMasterSync(
  results: MasterSyncResult | MasterSyncResult[] | null | undefined,
): string | null {
  if (!results) return null
  const list = Array.isArray(results) ? results : [results]
  const synced = list.filter((item) => item.synced)
  if (!synced.length) return null
  const parts = synced.map((item) => {
    const target = TARGET_LABEL[item.target || ''] || item.target || '主数据'
    const action = item.action === 'created' ? '新建' : '更新'
    return `${target}${action}`
  })
  return `已同步主数据：${parts.join('、')}`
}
