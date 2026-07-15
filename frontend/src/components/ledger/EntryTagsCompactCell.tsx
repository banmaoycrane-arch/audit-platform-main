import { Popover, Space, Tag, Typography } from 'antd'

import type { EntryTag } from '../../api/client'
import type { TagCategoryMeta } from '../../utils/subsidiaryLedgerPrefs'

const { Text } = Typography

const CATEGORY_COLORS = ['blue', 'geekblue', 'cyan', 'purple', 'gold', 'green', 'orange', 'magenta']

function colorForCategory(code: string): string {
  let hash = 0
  for (let i = 0; i < code.length; i += 1) {
    hash = (hash + code.charCodeAt(i) * (i + 1)) % CATEGORY_COLORS.length
  }
  return CATEGORY_COLORS[hash] || 'default'
}

function shortCategoryName(name: string, code: string): string {
  const trimmed = name.trim()
  if (trimmed.length <= 4) return trimmed
  return trimmed.slice(0, 4)
}

function shortTagValue(value: string, max = 10): string {
  const trimmed = value.trim()
  if (trimmed.length <= max) return trimmed
  return `${trimmed.slice(0, max)}…`
}

type EntryTagsCompactCellProps = {
  tags: EntryTag[]
  visibleCategories: TagCategoryMeta[]
  maxInline?: number
}

export function EntryTagsCompactCell({
  tags,
  visibleCategories,
  maxInline = 2,
}: EntryTagsCompactCellProps) {
  const categoryCodes = new Set(visibleCategories.map((item) => item.code))
  const categoryNameByCode = Object.fromEntries(visibleCategories.map((item) => [item.code, item.name]))
  const filtered = tags.filter((tag) => categoryCodes.has(tag.category_code))
  if (!filtered.length) {
    return <Text type="secondary">-</Text>
  }

  const inline = filtered.slice(0, maxInline)
  const overflow = filtered.slice(maxInline)

  const renderTag = (tag: EntryTag) => {
    const categoryLabel = shortCategoryName(
      categoryNameByCode[tag.category_code] || tag.category_name || tag.category_code,
      tag.category_code,
    )
    const value = shortTagValue(tag.display_name || tag.tag_value || '-')
    return (
      <Tag
        key={tag.id}
        color={colorForCategory(tag.category_code)}
        style={{ marginInlineEnd: 0, fontSize: 11, lineHeight: '18px', padding: '0 4px' }}
        title={`${tag.category_name || tag.category_code}: ${tag.display_name || tag.tag_value}`}
      >
        {categoryLabel}:{value}
      </Tag>
    )
  }

  const popoverContent = (
    <Space direction="vertical" size={4} style={{ maxWidth: 320 }}>
      {filtered.map((tag) => (
        <div key={tag.id}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {tag.category_name || tag.category_code}
          </Text>
          <div>{tag.display_name || tag.tag_value || '-'}</div>
        </div>
      ))}
    </Space>
  )

  return (
    <Space size={2} wrap style={{ maxWidth: 168 }}>
      {inline.map(renderTag)}
      {overflow.length > 0 && (
        <Popover title={`全部维度（${filtered.length}）`} content={popoverContent} trigger="click">
          <Tag style={{ marginInlineEnd: 0, cursor: 'pointer', fontSize: 11 }}>+{overflow.length}</Tag>
        </Popover>
      )}
    </Space>
  )
}
