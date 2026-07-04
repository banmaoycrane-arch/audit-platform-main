/**
 * 模块功能：前端金额输入校验工具
 * 业务场景：校验用户输入的金额是否符合业务规则
 * 创建日期：2026-07-02
 */

import Decimal from 'decimal.js';
import { DEFAULT_MAX_MONEY_VALUE, DEFAULT_MIN_MONEY_VALUE, DEFAULT_MONEY_DECIMAL_PLACES } from './constants';
import { parseDecimal } from './parse';

export interface MoneyValidationOptions {
  min?: string | number;
  max?: string | number;
  allowNegative?: boolean;
  allowZero?: boolean;
  maxDecimalPlaces?: number;
  fieldName?: string;
}

export interface MoneyValidationResult {
  valid: boolean;
  error?: string;
  value?: Decimal;
}

/**
 * 校验金额输入
 *
 * @param value 待校验的值
 * @param options 校验选项
 * @returns 校验结果
 */
export function validateMoneyInput(
  value: string | number | Decimal | null | undefined,
  options: MoneyValidationOptions = {},
): MoneyValidationResult {
  const {
    min = DEFAULT_MIN_MONEY_VALUE,
    max = DEFAULT_MAX_MONEY_VALUE,
    allowNegative = true,
    allowZero = true,
    maxDecimalPlaces = DEFAULT_MONEY_DECIMAL_PLACES,
    fieldName = '金额',
  } = options;

  if (value === null || value === undefined || value === '') {
    return { valid: false, error: `${fieldName}不能为空` };
  }

  let decimal: Decimal;
  try {
    decimal = parseDecimal(value, maxDecimalPlaces * 2);
  } catch {
    return { valid: false, error: `${fieldName}格式不正确` };
  }

  // 校验小数位数
  const decimalPlaces = decimal.decimalPlaces();
  if (decimalPlaces > maxDecimalPlaces) {
    return {
      valid: false,
      error: `${fieldName}最多保留 ${maxDecimalPlaces} 位小数`,
    };
  }

  // 范围校验
  const minDecimal = new Decimal(min);
  const maxDecimal = new Decimal(max);
  if (decimal.lt(minDecimal) || decimal.gt(maxDecimal)) {
    return {
      valid: false,
      error: `${fieldName}应在 ${min} 至 ${max} 之间`,
    };
  }

  // 符号校验
  if (decimal.isNegative() && !allowNegative) {
    return { valid: false, error: `${fieldName}不能为负数` };
  }

  if (decimal.isZero() && !allowZero) {
    return { valid: false, error: `${fieldName}不能为零` };
  }

  return { valid: true, value: parseDecimal(value, maxDecimalPlaces) };
}

/**
 * 校验正数金额（必须 > 0）
 */
export function validatePositiveMoney(
  value: string | number | Decimal | null | undefined,
  options: Omit<MoneyValidationOptions, 'allowNegative' | 'allowZero'> = {},
): MoneyValidationResult {
  return validateMoneyInput(value, { ...options, allowNegative: false, allowZero: false });
}

/**
 * 校验非负金额（必须 >= 0）
 */
export function validateNonNegativeMoney(
  value: string | number | Decimal | null | undefined,
  options: Omit<MoneyValidationOptions, 'allowNegative'> = {},
): MoneyValidationResult {
  return validateMoneyInput(value, { ...options, allowNegative: false });
}
