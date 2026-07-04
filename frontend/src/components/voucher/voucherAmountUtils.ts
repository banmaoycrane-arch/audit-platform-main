import Decimal from 'decimal.js'

/** 传统记账凭证面额分列：亿千百十万千百十元角分 */
export const DENOM_LABELS = ['亿', '千', '百', '十', '万', '千', '百', '十', '元', '角', '分'] as const

export const DENOM_CELL_COUNT = DENOM_LABELS.length

export function roundAmount(amount: number | Decimal): Decimal {
  const decimal = amount instanceof Decimal ? amount : new Decimal(amount)
  return decimal.toDecimalPlaces(2, Decimal.ROUND_HALF_UP)
}

/** 将金额转为 11 位面额字符（空位为空字符串） */
export function amountToDenomCells(amount: number | Decimal): string[] {
  const decimalAmount = roundAmount(amount)
  const cents = Math.max(0, decimalAmount.times(100).toNumber())
  const padded = cents.toString().padStart(DENOM_CELL_COUNT, '0')
  return padded.split('').map((digit, index) => (digit === '0' && index < padded.length - String(cents).length ? '' : digit))
}

/** 面额字符转金额（元） */
export function denomCellsToAmount(cells: string[]): Decimal {
  const digits = cells.map(cell => (cell && /\d/.test(cell) ? cell : '0')).join('')
  const cents = Number.parseInt(digits, 10) || 0
  return roundAmount(cents / 100)
}

/** 合计行中文大写金额（简化版） */
export function amountToChineseUpper(amount: number | Decimal): string {
  const decimalValue = roundAmount(amount)
  if (decimalValue.isZero()) return '零元整'

  const digits = ['零', '壹', '贰', '叁', '肆', '伍', '陆', '柒', '捌', '玖']
  const units = ['', '拾', '佰', '仟']
  const bigUnits = ['', '万', '亿']

  const [intPart, decPart = '00'] = decimalValue.toFixed(2).split('.')
  let intNum = Number.parseInt(intPart, 10)
  let result = ''

  if (intNum === 0) {
    result = '零'
  } else {
    const sections: string[] = []
    let sectionIndex = 0
    while (intNum > 0) {
      const section = intNum % 10000
      if (section > 0) {
        let sectionText = ''
        let temp = section
        for (let i = 0; i < 4; i += 1) {
          const digit = temp % 10
          if (digit > 0) {
            sectionText = `${digits[digit]}${units[i]}${sectionText}`
          } else if (sectionText && !sectionText.startsWith('零')) {
            sectionText = `零${sectionText}`
          }
          temp = Math.floor(temp / 10)
        }
        sections.unshift(`${sectionText.replace(/零+$/, '')}${bigUnits[sectionIndex]}`)
      }
      intNum = Math.floor(intNum / 10000)
      sectionIndex += 1
    }
    result = sections.join('').replace(/零+/g, '零').replace(/零$/, '')
  }

  const jiao = Number.parseInt(decPart[0] || '0', 10)
  const fen = Number.parseInt(decPart[1] || '0', 10)

  if (jiao === 0 && fen === 0) return `${result}元整`
  if (fen === 0) return `${result}元${digits[jiao]}角`
  if (jiao === 0) return `${result}元零${digits[fen]}分`
  return `${result}元${digits[jiao]}角${digits[fen]}分`
}
