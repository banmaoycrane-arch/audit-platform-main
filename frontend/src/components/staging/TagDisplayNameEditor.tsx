import { useEffect, useState } from 'react'

import { Button, Checkbox, Input, Space, Tag, message } from 'antd'

import { CheckOutlined, EditOutlined } from '@ant-design/icons'

import type { DimensionTagLike } from './formatDimensionTag'

import { formatDimensionTagLabel, isDimensionNameNonStandard } from './formatDimensionTag'



type TagDisplayNameEditorProps = {

  tag: DimensionTagLike

  tagIndex: number

  compact?: boolean

  onSave: (tagIndex: number, displayName: string, syncToMaster: boolean) => Promise<void>

}



export function TagDisplayNameEditor({ tag, tagIndex, compact, onSave }: TagDisplayNameEditorProps) {

  const [editing, setEditing] = useState(false)

  const [value, setValue] = useState(tag.display_name || tag.tag_value || '')

  const [syncToMaster, setSyncToMaster] = useState(true)

  const [saving, setSaving] = useState(false)



  useEffect(() => {

    setValue(tag.display_name || tag.tag_value || '')

  }, [tag.display_name, tag.tag_value])



  const handleSave = async () => {

    const next = value.trim()

    if (!next) {

      message.warning('规范全称不能为空')

      return

    }

    setSaving(true)

    try {

      await onSave(tagIndex, next, syncToMaster)

      setEditing(false)

      message.success('已保存规范全称')

    } catch (error) {

      message.error(error instanceof Error ? error.message : '保存失败')

    } finally {

      setSaving(false)

    }

  }



  if (!editing) {

    return (

      <Space size={4} wrap>

        <Tag color={isDimensionNameNonStandard(tag) ? 'orange' : 'blue'}>

          {formatDimensionTagLabel(tag)}

        </Tag>

        {isDimensionNameNonStandard(tag) && !compact && (

          <span style={{ fontSize: 12, color: '#999' }}>简称</span>

        )}

        <Button

          type="link"

          size="small"

          icon={<EditOutlined />}

          onClick={() => setEditing(true)}

          style={{ padding: 0 }}

        >

          编辑全称

        </Button>

      </Space>

    )

  }



  return (

    <Space direction="vertical" size={4} style={{ width: '100%' }}>

      <Input

        size="small"

        value={value}

        onChange={(e) => setValue(e.target.value)}

        placeholder="输入银行/维度规范全称"

        onPressEnter={() => void handleSave()}

      />

      <Checkbox checked={syncToMaster} onChange={(e) => setSyncToMaster(e.target.checked)}>

        同步到主数据

      </Checkbox>

      <Space>

        <Button type="primary" size="small" icon={<CheckOutlined />} loading={saving} onClick={() => void handleSave()}>

          保存

        </Button>

        <Button size="small" onClick={() => setEditing(false)}>

          取消

        </Button>

      </Space>

    </Space>

  )

}

