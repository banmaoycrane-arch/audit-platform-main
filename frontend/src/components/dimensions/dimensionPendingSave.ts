import { message } from 'antd'

import { api, type DimensionPendingQueueItem } from '../../api/client'

import { describeMasterSync } from './masterSyncUtils'

export type DimensionPendingEditableRow = Pick<
  DimensionPendingQueueItem,
  'account_code' | 'category_code' | 'tag_value' | 'source_sub_code' | 'display_name'
>

export function canEditDimensionPendingRow(row: DimensionPendingEditableRow): boolean {
  return Boolean(row.account_code && row.category_code && row.tag_value)
}

export async function submitDimensionDisplayName(
  jobId: number,
  row: DimensionPendingEditableRow,
  displayName: string,
  syncToMaster: boolean,
): Promise<{ unchanged: boolean }> {
  const next = displayName.trim()
  if (!next) {
    message.warning('映射全称不能为空')
    throw new Error('empty_display_name')
  }
  if (!canEditDimensionPendingRow(row)) {
    message.error('缺少科目/分类/维度值，无法保存')
    throw new Error('missing_row_keys')
  }

  const prior = (row.display_name || row.tag_value || '').trim()
  const unchanged = next === prior

  const result = await api.updateDimensionDisplayName(jobId, {
    account_code: row.account_code!,
    category_code: row.category_code!,
    tag_value: row.tag_value!,
    display_name: next,
    source_sub_code: row.source_sub_code,
    name_standardized: true,
    sync_to_master: syncToMaster,
  })

  const syncMsg = describeMasterSync(result.master_sync)
  if (result.resolved_findings && result.resolved_findings > 0) {
    message.success(
      syncMsg
        ? `已确认，并关闭 ${result.resolved_findings} 条内控提醒；${syncMsg}`
        : `已确认，并关闭 ${result.resolved_findings} 条内控提醒`,
    )
  } else if (unchanged) {
    message.success(syncMsg ? `已确认名称无误；${syncMsg}` : '已确认名称无误，将从待办队列移除')
  } else if (syncMsg) {
    message.success(`已保存映射；${syncMsg}`)
  } else {
    message.success('已保存映射，导入原名已留痕')
  }

  return { unchanged }
}
