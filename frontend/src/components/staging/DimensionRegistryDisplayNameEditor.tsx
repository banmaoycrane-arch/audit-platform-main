import { useEffect, useState } from 'react'

import { Button, Checkbox, Input, Space, message } from 'antd'

import { CheckOutlined } from '@ant-design/icons'

import type { DimensionRegistryResponse, MasterSyncResult } from '../../api/client'

import { describeMasterSync } from '../dimensions/masterSyncUtils'



type RegistryItem = DimensionRegistryResponse['items'][number]



type DimensionRegistryDisplayNameEditorProps = {

  row: RegistryItem

  onSave: (

    row: RegistryItem,

    displayName: string,

    syncToMaster: boolean,

  ) => Promise<{ resolved_findings?: number; master_sync?: MasterSyncResult | null }>

}



export function DimensionRegistryDisplayNameEditor({ row, onSave }: DimensionRegistryDisplayNameEditorProps) {

  const [value, setValue] = useState(row.display_name || row.tag_value || '')

  const [syncToMaster, setSyncToMaster] = useState(true)

  const [saving, setSaving] = useState(false)



  useEffect(() => {

    setValue(row.display_name || row.tag_value || '')

  }, [row.display_name, row.tag_value])



  const handleSave = async () => {

    const next = value.trim()

    if (!next) {

      message.warning('规范全称不能为空')

      return

    }

    if (next === row.display_name && row.name_standardized) {

      return

    }

    setSaving(true)

    try {

      const result = await onSave(row, next, syncToMaster)

      const syncMsg = describeMasterSync(result.master_sync)

      if (result.resolved_findings && result.resolved_findings > 0) {

        message.success(

          syncMsg

            ? `已保存，并自动关闭 ${result.resolved_findings} 条内控提醒；${syncMsg}`

            : `已保存，并自动关闭 ${result.resolved_findings} 条内控提醒`,

        )

      } else if (syncMsg) {

        message.success(`已批量更新规范全称；${syncMsg}`)

      } else {

        message.success('已批量更新规范全称')

      }

    } catch (error) {

      message.error(error instanceof Error ? error.message : '保存失败')

    } finally {

      setSaving(false)

    }

  }



  return (

    <Space direction="vertical" size={4} style={{ width: '100%' }}>

      <Space.Compact style={{ width: '100%' }}>

        <Input

          size="small"

          value={value}

          onChange={(e) => setValue(e.target.value)}

          placeholder="银行/维度规范全称"

          onPressEnter={() => void handleSave()}

        />

        <Button

          type="primary"

          size="small"

          icon={<CheckOutlined />}

          loading={saving}

          onClick={() => void handleSave()}

        />

      </Space.Compact>

      <Checkbox checked={syncToMaster} onChange={(e) => setSyncToMaster(e.target.checked)}>

        同步到主数据

      </Checkbox>

    </Space>

  )

}

