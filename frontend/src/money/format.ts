/**
 * 模块功能：前端金额格式化工具
 * 业务场景：统一财务报表、凭证、导入预览等金额显示格式
 * 创建日期：2026-07-02
 */

import Decimal from 'decimal.js';
import { Currency, CNY } from './constants';
import { parseDecimal } from './parse';

export interface FormatMoneyOptions {
  symbol?: boolean;
  thousands?: boolean;
  places?: number;
  negativeInParens?: boolean;
  currency?: Currency;
}

/**
 * 将金额格式化为标准显示字符串
 *
 * @param value 金额数值
 * @param options 格式化选项
 * @returns 格式化后的字符串，如 "¥1,234.56" 或 "-1,234.56"
 */
export function formatMoney(
  value: string | number | Decimal | null | undefined,
  options: FormatMoneyOptions = {},
): string {
  const {
    symbol = false,
    thousands = true,
    places,
    negativeInParens = false,
    currency = CNY,
  } = options;

  const decimalPlaces = places ?? currency.decimalPlaces;

  if (value === null || value === undefined || value === '') {
    return symbol ? `${currency.symbol}0.${'0'.repeat(decimalPlaces)}` : `0.${'0'.repeat(decimalPlaces)}`;
  }

  const decimal = parseDecimal(value, decimalPlaces);
  const isNegative = decimal.isNegative();
  const absValue = decimal.abs();

  const numberStr = absValue.toFixed(decimalPlaces);
  const [integerPart, decimalPart] = numberStr.split('.');
  const formattedInteger = thousands
    ? integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, ',')
    : integerPart;

  const numberResult = `${formattedInteger}.${decimalPart}`;
  const prefix = symbol ? currency.symbol : '';

  if (isNegative) {
    if (negativeInParens) {
      return `(${prefix}${numberResult})`;
    }
    return `-${prefix}${numberResult}`;
  }

  return `${prefix}${numberResult}`;
}

/**
 * 格式化金额并始终显示人民币符号
 */
export function formatAmount(value: string | number | Decimal | null | undefined): string {
  return formatMoney(value, { symbol: true, thousands: true });
}

/**
 * 格式化输入框中的金额：千分位 + 2位小数
 * 适用于输入框失焦后的展示
 */
export function formatDecimalInput(value: string | number | Decimal | null | undefined): string {
  return formatMoney(value, { symbol: false, thousands: true, places: 2 });
}
