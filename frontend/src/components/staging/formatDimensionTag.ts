export type DimensionTagLike = {
  category_code?: string
  tag_value?: string
  display_name?: string
  source_sub_code?: string | null
  name_standardized?: boolean
}

/** S2：来源段 + 规范名/简称，便于像辅助核算一样阅读 */
export function formatDimensionTagLabel(tag: DimensionTagLike): string {
  const display = (tag.display_name || tag.tag_value || '').trim()
  const sub = (tag.source_sub_code || '').trim()
  if (sub && display) {
    return `${sub} · ${display}`
  }
  return display || sub || '-'
}

export function isDimensionNameNonStandard(tag: DimensionTagLike): boolean {
  if (tag.name_standardized === true) return false
  const display = (tag.display_name || tag.tag_value || '').trim()
  if (!display) return true
  if (/有限公司|有限责任公司|股份有限公司|电力公司|技术服务部|支行|分行/.test(display)) return false
  if (display.length >= 8 && /[\u4e00-\u9fff]/.test(display)) return false
  const value = (tag.tag_value || '').trim()
  return display === value && display.length <= 6
}
