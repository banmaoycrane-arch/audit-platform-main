/**
 * 模块功能：前端金额舍入与汇总工具
 * 业务场景：统一财务计算的舍入方式和汇总逻辑
 * 创建日期：2026-07-02
 */

import Decimal from 'decimal.js';
import { Currency, CNY, DEFAULT_MONEY_DECIMAL_PLACES } from './constants';
import { Money } from './Money';
import { parseDecimal } from './parse';

/**
 * 按指定精度舍入 Decimal
 *
 * @param value 原始值
 * @param decimalPlaces 小数位数
 * @returns 舍入后的 Decimal
 */
export function roundDecimal(
  value: string | number | Decimal,
  decimalPlaces: number = DEFAULT_MONEY_DECIMAL_PLACES,
): Decimal {
  const decimal = parseDecimal(value, decimalPlaces * 2);
  return decimal.toDecimalPlaces(decimalPlaces, Decimal.ROUND_HALF_UP);
}

/**
 * 按币种精度舍入 Money
 */
export function roundMoney(money: Money): Money {
  return new Money(money.amount, money.currency);
}

/**
 * 汇总多个 Decimal 金额
 */
export function sumDecimals(values: Array<string | number | Decimal | null | undefined>): Decimal {
  return values.reduce<Decimal>((acc, value) => {
    if (value === null || value === undefined || value === '') {
      return acc;
    }
    return acc.plus(parseDecimal(value, DEFAULT_MONEY_DECIMAL_PLACES));
  }, new Decimal(0));
}

/**
 * 汇总多个 Money 金额（币种必须一致）
 *
 * @param monies 待汇总的金额数组
 * @param defaultCurrency 当数组为空时使用的默认币种
 */
export function sumMoney(monies: Array<Money | null | undefined>, defaultCurrency: Currency = CNY): Money {
  const validMonies = monies.filter((m): m is Money => m instanceof Money);
  if (validMonies.length === 0) {
    return Money.zero(defaultCurrency);
  }

  const currency = validMonies[0].currency;
  const total = validMonies.reduce<Decimal>((acc, money) => {
    if (money.currency.code !== currency.code) {
      throw new Error(`币种不一致：${money.currency.code} 与 ${currency.code}`);
    }
    return acc.plus(money.amount);
  }, new Decimal(0));

  return new Money(total, currency);
}

/**
 * 将带符号金额拆分为借方/贷方
 *
 * @param value 带符号金额
 * @returns { debit, credit } 均为非负金额
 */
export function debitCreditSplit(value: string | number | Decimal): { debit: Decimal; credit: Decimal } {
  const decimal = parseDecimal(value, DEFAULT_MONEY_DECIMAL_PLACES);
  if (decimal.gte(0)) {
    return { debit: decimal, credit: new Decimal(0) };
  }
  return { debit: new Decimal(0), credit: decimal.abs() };
}
