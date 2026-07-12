export type CharsetOption = 'auto' | 'utf-8' | 'utf-8-sig' | 'gb18030' | 'gbk'
export type DelimiterOption = 'auto' | 'comma' | 'tab' | 'semicolon'

export type StructuredParseOptions = {
  charset: CharsetOption
  delimiter: DelimiterOption
}

export const DEFAULT_STRUCTURED_PARSE_OPTIONS: StructuredParseOptions = {
  charset: 'auto',
  delimiter: 'auto',
}

export const CHARSET_OPTIONS: Array<{ value: CharsetOption; label: string; hint?: string }> = [
  { value: 'auto', label: '自动检测', hint: '推荐：系统识别 UTF-8 / GBK / GB18030 等' },
  { value: 'utf-8', label: 'UTF-8' },
  { value: 'utf-8-sig', label: 'UTF-8（带 BOM）', hint: 'Excel「另存为 CSV」常见' },
  { value: 'gb18030', label: 'GB18030', hint: '国标扩展，兼容 GBK' },
  { value: 'gbk', label: 'GBK', hint: '用友/金蝶等老版本导出' },
]

export const DELIMITER_OPTIONS: Array<{ value: DelimiterOption; label: string; hint?: string }> = [
  { value: 'auto', label: '自动检测', hint: '识别逗号、Tab、分号' },
  { value: 'comma', label: '逗号 (,)', hint: '标准 CSV' },
  { value: 'tab', label: 'Tab 制表符', hint: '部分财务软件「伪 CSV」' },
  { value: 'semicolon', label: '分号 (;)', hint: '欧洲区域 Excel 导出' },
]

export const STRUCTURED_PARSE_GUIDANCE = {
  title: '解析兼容性说明（上传前请了解）',
  intro:
    '结构化文件（CSV/TSV/Excel）在上传后将进入规则预识别与解析。CSV/TSV 文本文件可能需要指定字符集与分隔符；Excel 无需字符集设置。',
  bullets: [
    '支持 .xlsx / .xls / .csv / .tsv；建议保留凭证号、日期、摘要、科目、借方、贷方等列名',
    'CSV/TSV 默认自动检测字符集与分隔符；若出现乱码或列错位，请在下方手动调整后再上传',
    '可先「预检测文件」查看识别结果，确认无误后再正式上传并解析',
    'Excel 二进制格式无需字符集；若表头前有标题行（公司名、期间等），系统会自动跳过',
  ],
}
