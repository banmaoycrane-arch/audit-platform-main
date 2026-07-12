/** 维度核对 / 待处理队列：口语化说明文案，便于用户在系统内直接看懂 */

export type DimensionPendingSummary = {
  total: number
  non_standardized: number
  missing_in_master: number
  requires_llm: number
  unknown_category?: number
  internal_control?: number
  mapped?: number
}

export const DIMENSION_STAT_HINTS = {
  dimensionCount: '这批序时簿里，不同的户名、费用类型等（去重后）一共几种',
  pendingTotal: '简称没改全称、主数据没登记等——入账前建议处理',
  warningCount: '不影响继续审凭证，但入账前最好看一眼',
} as const

export function buildPendingAlertTitle(summary: DimensionPendingSummary): string {
  if (summary.total <= 0) return '本批维度都已对齐，可以进入凭证复核'
  return `还有 ${summary.total} 件事建议入账前处理`
}

export function buildPendingAlertDescription(summary: DimensionPendingSummary): string {
  const parts: string[] = []

  if (summary.non_standardized > 0) {
    parts.push(
      `${summary.non_standardized} 个名称像缩写或尚未对照主数据（常见是银行户名缩写；中文人名如「张悦」不算）`,
    )
  }
  if (summary.missing_in_master > 0) {
    parts.push(
      `${summary.missing_in_master} 个在账里出现了，但开户清单/往来单位里还没登记，请先补主数据`,
    )
  }
  if (summary.requires_llm > 0) {
    parts.push(
      `${summary.requires_llm} 条分录系统没识别出辅助核算，可用「批量 LLM 识别」或人工补`,
    )
  }
  if ((summary.unknown_category ?? 0) > 0) {
    parts.push(`${summary.unknown_category} 个维度分类在账簿里还没建，请先在「维度分类」里登记`)
  }
  if ((summary.internal_control ?? 0) > 0) {
    parts.push(`${summary.internal_control} 条内控提醒待跟进`)
  }

  const detail = parts.length > 0 ? parts.join('；') + '。' : ''
  const mappedNote =
    (summary.mapped ?? 0) > 0
      ? `另有 ${summary.mapped} 条已人工映射留痕（原名→映射值），不影响入账，可在队列中查看或修改。`
      : ''
  return `${detail}${mappedNote}现在可以继续审凭证；点下方「待处理队列」可逐条处理。`
}

export type RegistryWarning = {
  code: string
  message: string
  severity?: string
  account_code?: string
}

export function humanizeRegistryWarning(warning: RegistryWarning): {
  message: string
  description?: string
} {
  switch (warning.code) {
    case 'bank_name_not_standardized':
      return {
        message: warning.message,
        description:
          '户名还是简称的话，确认入账后系统会自动记一条内控提醒。在「维度值主数据」补全规范全称后，这条提醒会自动消失。',
      }
    case 'coa_unused_sub_accounts':
      return {
        message: warning.message,
        description:
          '不一定是错误：可能是科目表里有多余下级户，或本批序时簿还没用到全部账户，核对一下即可。',
      }
    default:
      return { message: warning.message }
  }
}

export const QUEUE_TYPE_HINT: Record<string, string> = {
  non_standardized: '名称不完整或像缩写，建议补全（人名仅姓氏、银行简称等）',
  missing_in_master: '账里用了，但主数据里还没有',
  requires_llm: '系统没识别出来，需 AI 或人工补',
  unknown_category: '维度分类还没在账簿里登记',
  internal_control: '入账后生成的内控提醒，补全后可关闭',
  mapped: '已人工映射，保留导入原名与当前映射值，便于还原对照',
}
