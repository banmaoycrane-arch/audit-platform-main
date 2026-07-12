import { useEffect, useState } from 'react'

import { Button, Checkbox, Input, Space, Tooltip } from 'antd'
import { CheckOutlined } from '@ant-design/icons'

import type { DimensionPendingQueueItem } from '../../api/client'

import { canEditDimensionPendingRow, submitDimensionDisplayName } from './dimensionPendingSave'

type DimensionPendingDisplayNameEditorProps = {
  jobId: number
  row: Pick<
    DimensionPendingQueueItem,
    'account_code' | 'category_code' | 'tag_value' | 'source_sub_code' | 'display_name'
  >
  onSaved?: () => void
}

export function DimensionPendingDisplayNameEditor({
  jobId,
  row,
  onSaved,
}: DimensionPendingDisplayNameEditorProps) {
  const [value, setValue] = useState(row.display_name || row.tag_value || '')
  const [syncToMaster, setSyncToMaster] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    setValue(row.display_name || row.tag_value || '')
  }, [row.display_name, row.tag_value])

  const handleSave = async () => {
    if (!canEditDimensionPendingRow(row)) return
    setSaving(true)
    try {
      await submitDimensionDisplayName(jobId, row, value, syncToMaster)
      onSaved?.()
    } catch {
      // submitDimensionDisplayName 已提示
    } finally {
      setSaving(false)
    }
  }

  return (
    <Space direction="vertical" size={4} style={{ width: '100%', minWidth: 180 }}>
      <Space.Compact style={{ width: '100%' }}>
        <Input
          size="small"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="规范全称 / 映射值"
          onPressEnter={() => void handleSave()}
        />
        <Tooltip title="名称已正确则直接点确认；需改名则改后点确认">
          <Button
            type="primary"
            size="small"
            icon={<CheckOutlined />}
            loading={saving}
            onClick={() => void handleSave()}
          >
            确认
          </Button>
        </Tooltip>
      </Space.Compact>
      <Checkbox checked={syncToMaster} onChange={(e) => setSyncToMaster(e.target.checked)}>
        同步到主数据
      </Checkbox>
    </Space>
  )
}
