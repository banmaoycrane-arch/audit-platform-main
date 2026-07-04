import { describe, it, expect } from 'vitest';
import Decimal from 'decimal.js';
import { formatMoney, formatAmount, formatDecimalInput } from './format';
import { parseDecimal, safeParseDecimal, parseMoney, safeParseMoney } from './parse';
import { roundDecimal, sumDecimals, sumMoney, debitCreditSplit } from './round';
import { validateMoneyInput, validatePositiveMoney, validateNonNegativeMoney } from './validate';
import { Money, CNY } from './index';

describe('formatAmount', () => {
  it('should format positive numbers with currency symbol', () => {
    expect(formatAmount(1234.56)).toBe('¥1,234.56');
    expect(formatAmount(1000000)).toBe('¥1,000,000.00');
    expect(formatAmount(0)).toBe('¥0.00');
  });

  it('should format negative numbers', () => {
    expect(formatAmount(-1234.56)).toBe('-¥1,234.56');
    expect(formatAmount(-0.01)).toBe('-¥0.01');
  });

  it('should handle string inputs', () => {
    expect(formatAmount('1234.56')).toBe('¥1,234.56');
    expect(formatAmount('1000000')).toBe('¥1,000,000.00');
  });

  it('should handle Decimal inputs', () => {
    expect(formatAmount(new Decimal('1234.56'))).toBe('¥1,234.56');
  });

  it('should handle null and undefined', () => {
    expect(formatAmount(null)).toBe('¥0.00');
    expect(formatAmount(undefined)).toBe('¥0.00');
    expect(formatAmount('')).toBe('¥0.00');
  });

  it('should handle floating point precision issues', () => {
    expect(formatAmount(0.1 + 0.2)).toBe('¥0.30');
  });
});

describe('formatMoney', () => {
  it('should format without symbol when symbol=false', () => {
    expect(formatMoney(1234.56, { symbol: false })).toBe('1,234.56');
  });

  it('should format without thousands separator when thousands=false', () => {
    expect(formatMoney(1234.56, { thousands: false })).toBe('1234.56');
  });

  it('should format with custom decimal places', () => {
    expect(formatMoney(1234.5678, { places: 4 })).toBe('1,234.5678');
  });

  it('should format negative in parentheses', () => {
    expect(formatMoney(-1234.56, { negativeInParens: true })).toBe('(1,234.56)');
  });

  it('should format with symbol when symbol=true', () => {
    expect(formatMoney(1234.56, { symbol: true })).toBe('¥1,234.56');
  });
});

describe('formatDecimalInput', () => {
  it('should format for input display', () => {
    expect(formatDecimalInput(1234.56)).toBe('1,234.56');
    expect(formatDecimalInput(0)).toBe('0.00');
  });
});

describe('parseDecimal', () => {
  it('should parse numbers correctly', () => {
    expect(parseDecimal(1234.56).toNumber()).toBe(1234.56);
    expect(parseDecimal(0).toNumber()).toBe(0);
  });

  it('should parse strings correctly', () => {
    expect(parseDecimal('1234.56').toNumber()).toBe(1234.56);
    expect(parseDecimal('1,234.56').toNumber()).toBe(1234.56);
    expect(parseDecimal('¥1,234.56').toNumber()).toBe(1234.56);
    expect(parseDecimal('￥1,234.56').toNumber()).toBe(1234.56);
  });

  it('should parse parentheses as negative', () => {
    expect(parseDecimal('(1234.56)').toNumber()).toBe(-1234.56);
  });

  it('should parse Decimal inputs', () => {
    expect(parseDecimal(new Decimal('1234.56')).toNumber()).toBe(1234.56);
  });

  it('should handle null and undefined as zero', () => {
    expect(parseDecimal(null).toNumber()).toBe(0);
    expect(parseDecimal(undefined).toNumber()).toBe(0);
    expect(parseDecimal('').toNumber()).toBe(0);
  });

  it('should round to 2 decimal places', () => {
    expect(parseDecimal(1234.567).toNumber()).toBe(1234.57);
    expect(parseDecimal(1234.564).toNumber()).toBe(1234.56);
  });

  it('should handle Money input', () => {
    const money = Money.cny('1234.56');
    expect(parseDecimal(money).toNumber()).toBe(1234.56);
  });
});

describe('safeParseDecimal', () => {
  it('should return null for invalid inputs', () => {
    expect(safeParseDecimal('invalid')).toBeNull();
    expect(safeParseDecimal({} as any)).toBeNull();
  });

  it('should return Decimal for valid inputs', () => {
    const result = safeParseDecimal('1234.56');
    expect(result).not.toBeNull();
    expect(result?.toNumber()).toBe(1234.56);
  });
});

describe('parseMoney', () => {
  it('should create Money from number', () => {
    const money = parseMoney(1234.56);
    expect(money.amount.toNumber()).toBe(1234.56);
    expect(money.currency.code).toBe('CNY');
  });

  it('should create Money from string', () => {
    const money = parseMoney('1234.56');
    expect(money.amount.toNumber()).toBe(1234.56);
  });

  it('should create Money with CNY shortcut', () => {
    const money = Money.cny(1234.56);
    expect(money.amount.toNumber()).toBe(1234.56);
    expect(money.currency.code).toBe('CNY');
  });
});

describe('sumDecimals', () => {
  it('should sum multiple values', () => {
    expect(sumDecimals([100, 200, 300]).toNumber()).toBe(600);
  });

  it('should handle floating point precision', () => {
    expect(sumDecimals([0.1, 0.2]).toNumber()).toBe(0.3);
    expect(sumDecimals([0.1, 0.2, 0.3]).toNumber()).toBe(0.6);
  });

  it('should handle null and undefined values', () => {
    expect(sumDecimals([100, null, 200, undefined, '', 300]).toNumber()).toBe(600);
  });

  it('should handle empty arrays', () => {
    expect(sumDecimals([]).toNumber()).toBe(0);
  });

  it('should handle mixed types', () => {
    expect(sumDecimals(['100', 200, new Decimal('300')]).toNumber()).toBe(600);
  });
});

describe('sumMoney', () => {
  it('should sum multiple Money objects', () => {
    const result = sumMoney([Money.cny(100), Money.cny(200), Money.cny(300)]);
    expect(result.amount.toNumber()).toBe(600);
    expect(result.currency.code).toBe('CNY');
  });

  it('should handle null and undefined values', () => {
    const result = sumMoney([Money.cny(100), null, Money.cny(200), undefined]);
    expect(result.amount.toNumber()).toBe(300);
  });

  it('should handle empty arrays', () => {
    const result = sumMoney([]);
    expect(result.amount.toNumber()).toBe(0);
  });

  it('should throw for mixed currencies', () => {
    const usd = { code: 'USD' as const, name: 'USD', symbol: '$', decimalPlaces: 2 } as unknown as typeof CNY;
    expect(() => sumMoney([Money.cny(100), new Money(200, usd)])).toThrow();
  });
});

describe('debitCreditSplit', () => {
  it('should split positive amount as debit', () => {
    const { debit, credit } = debitCreditSplit(1234.56);
    expect(debit.toNumber()).toBe(1234.56);
    expect(credit.toNumber()).toBe(0);
  });

  it('should split negative amount as credit', () => {
    const { debit, credit } = debitCreditSplit(-1234.56);
    expect(debit.toNumber()).toBe(0);
    expect(credit.toNumber()).toBe(1234.56);
  });

  it('should handle zero', () => {
    const { debit, credit } = debitCreditSplit(0);
    expect(debit.toNumber()).toBe(0);
    expect(credit.toNumber()).toBe(0);
  });
});

describe('roundDecimal', () => {
  it('should round to 2 decimal places', () => {
    expect(roundDecimal(1234.567).toNumber()).toBe(1234.57);
    expect(roundDecimal(1234.564).toNumber()).toBe(1234.56);
  });

  it('should use ROUND_HALF_UP', () => {
    expect(roundDecimal(1234.565).toNumber()).toBe(1234.57);
    expect(roundDecimal(1234.5649).toNumber()).toBe(1234.56);
  });
});

describe('validateMoneyInput', () => {
  it('should validate valid amounts', () => {
    expect(validateMoneyInput(1234.56).valid).toBe(true);
    expect(validateMoneyInput('1234.56').valid).toBe(true);
  });

  it('should reject empty values', () => {
    expect(validateMoneyInput(null).valid).toBe(false);
    expect(validateMoneyInput(undefined).valid).toBe(false);
    expect(validateMoneyInput('').valid).toBe(false);
  });

  it('should reject invalid formats', () => {
    expect(validateMoneyInput('invalid').valid).toBe(false);
  });

  it('should reject negative when not allowed', () => {
    expect(validateMoneyInput(-100, { allowNegative: false }).valid).toBe(false);
  });

  it('should reject zero when not allowed', () => {
    expect(validateMoneyInput(0, { allowZero: false }).valid).toBe(false);
  });

  it('should reject too many decimal places', () => {
    expect(validateMoneyInput('1234.567', { maxDecimalPlaces: 2 }).valid).toBe(false);
  });
});

describe('validatePositiveMoney', () => {
  it('should accept positive amounts', () => {
    expect(validatePositiveMoney(100).valid).toBe(true);
    expect(validatePositiveMoney('100').valid).toBe(true);
  });

  it('should reject zero and negative', () => {
    expect(validatePositiveMoney(0).valid).toBe(false);
    expect(validatePositiveMoney(-100).valid).toBe(false);
  });
});

describe('validateNonNegativeMoney', () => {
  it('should accept positive and zero amounts', () => {
    expect(validateNonNegativeMoney(100).valid).toBe(true);
    expect(validateNonNegativeMoney(0).valid).toBe(true);
  });

  it('should reject negative amounts', () => {
    expect(validateNonNegativeMoney(-100).valid).toBe(false);
  });
});

describe('Money class', () => {
  it('should create from number', () => {
    const money = new Money(1234.56);
    expect(money.amount.toNumber()).toBe(1234.56);
  });

  it('should create from string', () => {
    const money = new Money('1234.56');
    expect(money.amount.toNumber()).toBe(1234.56);
  });

  it('should create from Decimal', () => {
    const money = new Money(new Decimal('1234.56'));
    expect(money.amount.toNumber()).toBe(1234.56);
  });

  it('should create from Money', () => {
    const original = Money.cny(1234.56);
    const money = new Money(original);
    expect(money.amount.toNumber()).toBe(1234.56);
    expect(money.currency.code).toBe('CNY');
  });

  it('should add two Money objects', () => {
    const result = Money.cny(100).add(Money.cny(200));
    expect(result.amount.toNumber()).toBe(300);
  });

  it('should subtract two Money objects', () => {
    const result = Money.cny(200).sub(Money.cny(100));
    expect(result.amount.toNumber()).toBe(100);
  });

  it('should multiply by factor', () => {
    const result = Money.cny(100).mul(1.5);
    expect(result.amount.toNumber()).toBe(150);
  });

  it('should divide by divisor', () => {
    const result = Money.cny(200).div(2);
    expect(result.amount.toNumber()).toBe(100);
  });

  it('should throw when dividing by zero', () => {
    expect(() => Money.cny(100).div(0)).toThrow();
  });

  it('should compare Money objects', () => {
    const a = Money.cny(100);
    const b = Money.cny(200);
    expect(a.eq(a)).toBe(true);
    expect(a.eq(b)).toBe(false);
    expect(a.lt(b)).toBe(true);
    expect(a.gt(b)).toBe(false);
    expect(a.lte(b)).toBe(true);
    expect(a.gte(a)).toBe(true);
  });

  it('should throw for mismatched currencies', () => {
    const usd = { code: 'USD' as const, name: 'USD', symbol: '$', decimalPlaces: 2 } as unknown as typeof CNY;
    const cny = Money.cny(100);
    const usdMoney = new Money(200, usd);
    expect(() => cny.add(usdMoney)).toThrow();
    expect(() => cny.eq(usdMoney)).toThrow();
  });

  it('should format to display string', () => {
    expect(Money.cny(1234.56).toDisplay()).toBe('¥1,234.56');
    expect(Money.cny(1234.56).toDisplay({ symbol: false })).toBe('1,234.56');
    expect(Money.cny(1234.56).toDisplay({ symbol: true, thousands: false })).toBe('¥1234.56');
  });

  it('should convert to string for API', () => {
    expect(Money.cny(1234.56).toString()).toBe('1234.56');
    expect(Money.cny(100).toString()).toBe('100.00');
  });

  it('should convert to number', () => {
    expect(Money.cny(1234.56).toNumber()).toBe(1234.56);
  });

  it('should check sign', () => {
    expect(Money.cny(100).isPositive()).toBe(true);
    expect(Money.cny(-100).isNegative()).toBe(true);
    expect(Money.cny(0).isZero()).toBe(true);
  });

  it('should get absolute value', () => {
    expect(Money.cny(-100).abs().amount.toNumber()).toBe(100);
    expect(Money.cny(100).abs().amount.toNumber()).toBe(100);
  });

  it('should split into debit/credit', () => {
    const { debit, credit } = Money.cny(100).toDebitCredit();
    expect(debit.amount.toNumber()).toBe(100);
    expect(credit.amount.toNumber()).toBe(0);

    const { debit: d, credit: c } = Money.cny(-100).toDebitCredit();
    expect(d.amount.toNumber()).toBe(0);
    expect(c.amount.toNumber()).toBe(100);
  });

  it('should format to fixed decimal places', () => {
    expect(Money.cny(1234.567).toFixed()).toBe('1234.57');
    expect(Money.cny(1234.56).toFixed(4)).toBe('1234.5600');
  });

  it('should return negated value', () => {
    expect(Money.cny(100).negate().amount.toNumber()).toBe(-100);
    expect(Money.cny(-100).negate().amount.toNumber()).toBe(100);
    expect(Money.cny(0).negate().amount.isZero()).toBe(true);
  });

  it('should compare values', () => {
    const a = Money.cny(100);
    const b = Money.cny(200);
    const c = Money.cny(100);
    expect(a.compare(b)).toBe(-1);
    expect(b.compare(a)).toBe(1);
    expect(a.compare(c)).toBe(0);
  });

  it('should clone Money object', () => {
    const original = Money.cny(1234.56);
    const cloned = original.clone();
    expect(cloned.amount.toNumber()).toBe(1234.56);
    expect(cloned.currency.code).toBe('CNY');
    expect(cloned).not.toBe(original);
  });

  it('should create zero Money', () => {
    const zero = Money.zero();
    expect(zero.amount.toNumber()).toBe(0);
    expect(zero.currency.code).toBe('CNY');
  });

  it('should find min of Money objects', () => {
    expect(Money.min(Money.cny(100), Money.cny(50), Money.cny(200)).amount.toNumber()).toBe(50);
    expect(Money.min(Money.cny(0)).amount.toNumber()).toBe(0);
  });

  it('should find max of Money objects', () => {
    expect(Money.max(Money.cny(100), Money.cny(50), Money.cny(200)).amount.toNumber()).toBe(200);
    expect(Money.max(Money.cny(0)).amount.toNumber()).toBe(0);
  });

  it('should sum Money objects', () => {
    const result = Money.sum([Money.cny(100), Money.cny(200), Money.cny(300)]);
    expect(result.amount.toNumber()).toBe(600);
  });

  it('should return zero for empty sum', () => {
    const result = Money.sum([]);
    expect(result.amount.toNumber()).toBe(0);
  });

  it('should filter null/undefined in sum', () => {
    const result = Money.sum([Money.cny(100), null, Money.cny(200), undefined]);
    expect(result.amount.toNumber()).toBe(300);
  });
});

describe('formatMoney with currency', () => {
  it('should use currency symbol from options', () => {
    const usd = { code: 'USD' as const, name: 'USD', symbol: '$', decimalPlaces: 2 } as unknown as typeof CNY;
    expect(formatMoney(1234.56, { symbol: true, currency: usd })).toBe('$1,234.56');
  });
});

describe('sumMoney with default currency', () => {
  it('should use default currency for empty array', () => {
    const result = sumMoney([]);
    expect(result.amount.toNumber()).toBe(0);
    expect(result.currency.code).toBe('CNY');
  });
});