/**
 * 模块功能：前端金额处理系统常量
 * 业务场景：提供币种、精度、舍入方式等全局常量
 * 创建日期：2026-07-02
 */

import Decimal from 'decimal.js';

/**
 * 默认金额精度：2位小数（对应人民币"分"）
 */
export const DEFAULT_MONEY_DECIMAL_PLACES = 2;

/**
 * 统一舍入方式：四舍五入（ROUND_HALF_UP）
 */
export const DEFAULT_ROUNDING = Decimal.ROUND_HALF_UP;

/**
 * 设置 Decimal.js 全局默认配置
 */
Decimal.set({
  rounding: DEFAULT_ROUNDING,
  precision: 28,
});

/**
 * 人民币币种定义
 */
export const CNY = Object.freeze({
  code: 'CNY' as const,
  name: '人民币',
  symbol: '¥',
  decimalPlaces: 2,
});

export type Currency = typeof CNY;

/**
 * 默认最大/最小金额限制
 */
export const DEFAULT_MAX_MONEY_VALUE = '999999999999.99';
export const DEFAULT_MIN_MONEY_VALUE = '-999999999999.99';
