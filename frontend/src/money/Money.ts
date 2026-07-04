/**
 * 模块功能：前端金额领域对象 Money
 * 业务场景：为前端提供安全的金额计算和格式化封装
 * 创建日期：2026-07-02
 * 更新记录：
 *     2026-07-02  深度优化：性能提升、功能完善、错误处理增强、代码结构优化
 */

import Decimal from 'decimal.js';
import { CNY, Currency, DEFAULT_MONEY_DECIMAL_PLACES } from './constants';

export type MoneyValue = string | number | Decimal | Money;

export interface MoneyDisplayOptions {
  symbol?: boolean;
  thousands?: boolean;
  places?: number;
  negativeInParens?: boolean;
}

export class Money {
  private readonly value: Decimal;
  readonly currency: Currency;

  private static readonly ZERO_MAP = new Map<string, Money>();

  constructor(value: MoneyValue, currency: Currency = CNY) {
    this.currency = currency;
    this.value = this.parseValue(value);
  }

  private parseValue(value: MoneyValue): Decimal {
    if (value instanceof Money) {
      if (value.currency.code !== this.currency.code) {
        throw new Error(`币种不一致：${value.currency.code} 无法直接转换为 ${this.currency.code}`);
      }
      return value.value;
    }

    if (value instanceof Decimal) {
      return value.toDecimalPlaces(this.currency.decimalPlaces, Decimal.ROUND_HALF_UP);
    }

    const strValue = String(value).trim();
    if (!strValue || strValue === '-') {
      return new Decimal(0).toDecimalPlaces(this.currency.decimalPlaces);
    }

    const cleanValue = strValue.replace(/[¥$,，]/g, '');
    return new Decimal(cleanValue).toDecimalPlaces(this.currency.decimalPlaces, Decimal.ROUND_HALF_UP);
  }

  static cny(value: MoneyValue): Money {
    return new Money(value, CNY);
  }

  get amount(): Decimal {
    return this.value;
  }

  add(other: Money): Money {
    this.ensureSameCurrency(other);
    return new Money(this.value.plus(other.value), this.currency);
  }

  sub(other: Money): Money {
    this.ensureSameCurrency(other);
    return new Money(this.value.minus(other.value), this.currency);
  }

  mul(factor: string | number | Decimal): Money {
    return new Money(this.value.times(factor), this.currency);
  }

  div(divisor: string | number | Decimal): Money {
    const divisorDecimal = new Decimal(divisor);
    if (divisorDecimal.isZero()) {
      throw new Error('金额不能除以零');
    }
    if (divisorDecimal.isNaN()) {
      throw new Error('除数必须是有效数字');
    }
    return new Money(this.value.dividedBy(divisor), this.currency);
  }

  abs(): Money {
    return new Money(this.value.abs(), this.currency);
  }

  negate(): Money {
    return new Money(this.value.negated(), this.currency);
  }

  isZero(): boolean {
    return this.value.isZero();
  }

  isPositive(): boolean {
    return this.value.isPositive();
  }

  isNegative(): boolean {
    return this.value.isNegative();
  }

  isFinite(): boolean {
    return this.value.isFinite();
  }

  eq(other: Money): boolean {
    this.ensureSameCurrency(other);
    return this.value.eq(other.value);
  }

  lt(other: Money): boolean {
    this.ensureSameCurrency(other);
    return this.value.lt(other.value);
  }

  lte(other: Money): boolean {
    this.ensureSameCurrency(other);
    return this.value.lte(other.value);
  }

  gt(other: Money): boolean {
    this.ensureSameCurrency(other);
    return this.value.gt(other.value);
  }

  gte(other: Money): boolean {
    this.ensureSameCurrency(other);
    return this.value.gte(other.value);
  }

  compare(other: Money): number {
    this.ensureSameCurrency(other);
    return this.value.comparedTo(other.value);
  }

  clone(): Money {
    return new Money(this.value, this.currency);
  }

  toFixed(places?: number): string {
    const decimalPlaces = places ?? this.currency.decimalPlaces;
    return this.value.toFixed(decimalPlaces);
  }

  toString(): string {
    return this.value.toFixed(this.currency.decimalPlaces);
  }

  toNumber(): number {
    return this.value.toNumber();
  }

  toDisplay(options: MoneyDisplayOptions = {}): string {
    const {
      symbol = true,
      thousands = true,
      places,
      negativeInParens = false,
    } = options;

    const decimalPlaces = places ?? this.currency.decimalPlaces;
    const isNegative = this.value.isNegative();
    const absValue = this.value.abs();

    const numberStr = absValue.toFixed(decimalPlaces);
    const [integerPart, decimalPart] = numberStr.split('.');

    const formattedInteger = thousands
      ? integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, ',')
      : integerPart;

    const numberResult = `${formattedInteger}.${decimalPart}`;
    const prefix = symbol ? this.currency.symbol : '';

    if (isNegative) {
      if (negativeInParens) {
        return `(${prefix}${numberResult})`;
      }
      return `-${prefix}${numberResult}`;
    }

    return `${prefix}${numberResult}`;
  }

  toDebitCredit(): { debit: Money; credit: Money } {
    if (this.value.gte(0)) {
      return { debit: this, credit: Money.zero(this.currency) };
    }
    return { debit: Money.zero(this.currency), credit: this.abs() };
  }

  static zero(currency: Currency = CNY): Money {
    const cacheKey = currency.code;
    if (!Money.ZERO_MAP.has(cacheKey)) {
      Money.ZERO_MAP.set(cacheKey, new Money(0, currency));
    }
    return Money.ZERO_MAP.get(cacheKey)!;
  }

  static min(...monies: Money[]): Money {
    if (monies.length === 0) {
      return Money.zero();
    }

    const currency = monies[0].currency;
    let minValue = monies[0].value;

    for (let i = 1; i < monies.length; i++) {
      const m = monies[i];
      if (m.currency.code !== currency.code) {
        throw new Error(`币种不一致：${m.currency.code} 与 ${currency.code}`);
      }
      if (m.value.lt(minValue)) {
        minValue = m.value;
      }
    }

    return new Money(minValue, currency);
  }

  static max(...monies: Money[]): Money {
    if (monies.length === 0) {
      return Money.zero();
    }

    const currency = monies[0].currency;
    let maxValue = monies[0].value;

    for (let i = 1; i < monies.length; i++) {
      const m = monies[i];
      if (m.currency.code !== currency.code) {
        throw new Error(`币种不一致：${m.currency.code} 与 ${currency.code}`);
      }
      if (m.value.gt(maxValue)) {
        maxValue = m.value;
      }
    }

    return new Money(maxValue, currency);
  }

  static sum(monies: Array<Money | null | undefined>, currency: Currency = CNY): Money {
    const validMonies = monies.filter((m): m is Money => m instanceof Money);
    if (validMonies.length === 0) {
      return Money.zero(currency);
    }

    const firstCurrency = validMonies[0].currency;
    let total = new Decimal(0);

    for (const money of validMonies) {
      if (money.currency.code !== firstCurrency.code) {
        throw new Error(`币种不一致：${money.currency.code} 与 ${firstCurrency.code}`);
      }
      total = total.plus(money.value);
    }

    return new Money(total, firstCurrency);
  }

  static safe(value: MoneyValue | null | undefined, currency: Currency = CNY): Money {
    if (value === null || value === undefined) {
      return Money.zero(currency);
    }
    try {
      return new Money(value, currency);
    } catch {
      return Money.zero(currency);
    }
  }

  private ensureSameCurrency(other: Money): void {
    if (this.currency.code !== other.currency.code) {
      throw new Error(`币种不一致：${this.currency.code} 与 ${other.currency.code}`);
    }
  }
}
