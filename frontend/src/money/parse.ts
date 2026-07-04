/**
 * 模块功能：前端金额解析工具
 * 业务场景：将用户输入、后端返回、文件导入的金额字符串解析为 Decimal
 * 创建日期：2026-07-02
 */

import Decimal from 'decimal.js';
import { CNY, Currency, DEFAULT_MONEY_DECIMAL_PLACES } from './constants';
import { Money } from './Money';

/**
 * 清理金额字符串中的货币符号和千分位
 */
function cleanAmountString(value: string): string {
  let cleaned = value.replace(/[¥￥$,，\s]/g, '');
  // 处理括号表示的负数 (123.45) -> -123.45
  if (cleaned.startsWith('(') && cleaned.endsWith(')')) {
    cleaned = `-${cleaned.slice(1, -1)}`;
  }
  return cleaned;
}

/**
 * 将任意类型解析为 Decimal
 *
 * @param value 待解析的值
 * @param decimalPlaces 保留小数位数
 * @returns Decimal 对象
 * @throws 解析失败时抛出 Error
 */
export function parseDecimal(
  value: string | number | Decimal | Money | null | undefined,
  decimalPlaces: number = DEFAULT_MONEY_DECIMAL_PLACES,
): Decimal {
  if (value === null || value === undefined || value === '') {
    return new Decimal(0);
  }

  if (value instanceof Money) {
    return value.amount;
  }

  let input: string;
  if (value instanceof Decimal) {
    return value.toDecimalPlaces(decimalPlaces, Decimal.ROUND_HALF_UP);
  } else if (typeof value === 'number') {
    input = value.toString();
  } else {
    input = cleanAmountString(value.trim());
  }

  const decimal = new Decimal(input);
  return decimal.toDecimalPlaces(decimalPlaces, Decimal.ROUND_HALF_UP);
}

/**
 * 安全解析金额，失败时返回 null
 */
export function safeParseDecimal(
  value: string | number | Decimal | null | undefined,
  decimalPlaces: number = DEFAULT_MONEY_DECIMAL_PLACES,
): Decimal | null {
  try {
    return parseDecimal(value, decimalPlaces);
  } catch {
    return null;
  }
}

/**
 * 将任意类型解析为 Money 对象
 */
export function parseMoney(
  value: string | number | Decimal | null | undefined,
  currency: Currency = CNY,
): Money {
  const decimal = parseDecimal(value, currency.decimalPlaces);
  return new Money(decimal, currency);
}

/**
 * 安全解析 Money，失败时返回 null
 */
export function safeParseMoney(
  value: string | number | Decimal | null | undefined,
  currency: Currency = CNY,
): Money | null {
  try {
    return parseMoney(value, currency);
  } catch {
    return null;
  }
}
