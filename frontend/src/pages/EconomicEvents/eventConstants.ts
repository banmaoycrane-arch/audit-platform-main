/**
 * 经济事件工单共享常量 — 状态机、类型标签。
 *
 * 状态机（与后端 economic_event_service._TRANSITIONS 对齐）：
 * draft → collecting → pending_review → pending_post → posted → closed
 * 旁支：failed（可回 collecting/draft/cancelled）、cancelled（终态）
 */

export const EVENT_STATUS_LABEL: Record<string, string> = {
  draft: '草稿',
  collecting: '归集中',
  pending_review: '待复核',
  pending_post: '待入账',
  posted: '已入账',
  closed: '已关闭',
  failed: '失败待处理',
  cancelled: '已取消',
}

export const EVENT_STATUS_COLOR: Record<string, string> = {
  draft: 'default',
  collecting: 'processing',
  pending_review: 'gold',
  pending_post: 'orange',
  posted: 'blue',
  closed: 'success',
  failed: 'error',
  cancelled: 'default',
}

export const EVENT_TYPE_LABEL: Record<string, string> = {
  manual: '手工',
  revenue_recognition: '收入确认',
  purchase: '采购',
  receipt: '收款',
  payment: '付款',
  payroll: '工资',
  expense: '费用',
  import_cluster: '导入聚类',
  adjustment: '调整',
}

export const EVENT_TYPE_OPTIONS = [
  { value: 'manual', label: '手工' },
  { value: 'revenue_recognition', label: '收入确认' },
  { value: 'purchase', label: '采购' },
  { value: 'receipt', label: '收款' },
  { value: 'payment', label: '付款' },
  { value: 'payroll', label: '工资' },
  { value: 'expense', label: '费用' },
  { value: 'import_cluster', label: '导入聚类' },
  { value: 'adjustment', label: '调整' },
]

export const EVENT_STATUS_OPTIONS = [
  { value: 'draft', label: '草稿' },
  { value: 'collecting', label: '归集中' },
  { value: 'pending_review', label: '待复核' },
  { value: 'pending_post', label: '待入账' },
  { value: 'posted', label: '已入账' },
  { value: 'closed', label: '已关闭' },
  { value: 'failed', label: '失败待处理' },
  { value: 'cancelled', label: '已取消' },
]

/**
 * 状态机允许的迁移边（与后端 _TRANSITIONS 同步）。
 * 用于详情页渲染「可推进到」按钮。
 */
export const EVENT_TRANSITIONS: Record<string, string[]> = {
  draft: ['collecting', 'cancelled'],
  collecting: ['pending_review', 'cancelled', 'failed'],
  pending_review: ['pending_post', 'collecting', 'failed'],
  pending_post: ['posted', 'pending_review', 'failed'],
  posted: ['closed'],
  closed: [],
  failed: ['collecting', 'draft', 'cancelled'],
  cancelled: [],
}

/** 终态：不可再推进 */
export const EVENT_TERMINAL_STATUSES = new Set(['closed', 'cancelled'])
