/**
 * 模块功能：前端金额处理系统统一入口
 * 业务场景：提供 Money 类、格式化、解析、校验、舍入等工具函数
 * 创建日期：2026-07-02
 */

export { Money } from './Money';
export type { MoneyValue } from './Money';
export { CNY, DEFAULT_MONEY_DECIMAL_PLACES, DEFAULT_ROUNDING } from './constants';
export type { Currency } from './constants';
export {
  formatMoney,
  formatAmount,
  formatDecimalInput,
} from './format';
export {
  parseMoney,
  parseDecimal,
  safeParseMoney,
} from './parse';
export {
  validateMoneyInput,
  validatePositiveMoney,
  validateNonNegativeMoney,
} from './validate';
export {
  roundMoney,
  roundDecimal,
  sumMoney,
  sumDecimals,
  debitCreditSplit,
} from './round';
