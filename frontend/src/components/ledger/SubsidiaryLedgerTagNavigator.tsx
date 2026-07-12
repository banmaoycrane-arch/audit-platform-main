import { useEffect, useMemo, useState } from 'react'
import { Alert, Button, Empty, Input, Select, Space, Tag, Typography } from 'antd'
import { PlusOutlined, SearchOutlined } from '@ant-design/icons'

import { api, type EntryTagAggregate } from '../../api/client'
import {
  addTagToSelection,
  tagValueKey,
  type TagCategorySelection,
} from '../../utils/subsidiaryLedgerSelections'

const { Text } = Typography

const TAG_LIST_MAX_HEIGHT = 220

type SubsidiaryLedgerTagNavigatorProps = {
  ledgerId?: number
  accountCodes: string[]
  accountCodeMatch: 'exact' | 'prefix' | 'contains'
  categoryOptions: Array<{ value: string; label: string }>
  categoryCode?: string
  tagSelections: Record<string, TagCategorySelection>
  /** 含同凭证对方科目分录行上的 tag（需已选科目） */
  includeVoucherLines?: boolean
  onCategoryChange: (code: string | undefined) => void
  onTagSelectionsChange: (next: Record<string, TagCategorySelection>) => void
}

export function SubsidiaryLedgerTagNavigator({
  ledgerId,
  accountCodes,
  accountCodeMatch,
  categoryOptions,
  categoryCode,
  tagSelections,
  includeVoucherLines = false,
  onCategoryChange,
  onTagSelectionsChange,
}: SubsidiaryLedgerTagNavigatorProps) {
  const [searchQ, setSearchQ] = useState('')
  const [loading, setLoading] = useState(false)
  const [items, setItems] = useState<EntryTagAggregate[]>([])

  const activeCategory = categoryCode

  useEffect(() => {
    if (!ledgerId || !activeCategory) {
      setItems([])
      return
    }
    setLoading(true)
    void api
      .aggregateEntryTagsScoped(ledgerId, activeCategory, {
        account_codes: accountCodes.length ? accountCodes : undefined,
        account_code_match: accountCodeMatch,
        include_voucher_lines: includeVoucherLines && accountCodes.length > 0,
        q: searchQ.trim() || undefined,
        limit: 80,
      })
      .then(setItems)
      .catch(() => setItems([]))
      .finally(() => setLoading(false))
  }, [ledgerId, activeCategory, accountCodes, accountCodeMatch, includeVoucherLines, searchQ])

  const selectedSet = useMemo(() => {
    const selection = activeCategory ? tagSelections[activeCategory] : undefined
    if (!selection || selection.includeAll) return null
    return new Set(selection.selectedValues)
  }, [activeCategory, tagSelections])

  const handleAdd = (tag: EntryTagAggregate) => {
    if (!activeCategory) return
    const value = tagValueKey(tag)
    const allValues = items.map((item) => tagValueKey(item))
    onTagSelectionsChange(addTagToSelection(tagSelections, activeCategory, value, allValues))
  }

  return (
    <div
      style={{
        border: '1px solid #f0f0f0',
        borderRadius: 8,
        padding: 12,
        background: '#fff',
      }}
    >
      <Text strong>Tag 快速检索</Text>
      <Text type="secondary" style={{ display: 'block', fontSize: 12, marginTop: 4 }}>
        辅助加入维度筛选，需点击主区域「查询」后生效。
      </Text>
      {includeVoucherLines && accountCodes.length > 0 && (
        <Alert
          type="info"
          showIcon
          style={{ marginTop: 8, marginBottom: 0, fontSize: 12 }}
          message="含对方科目 tag"
          description="列表含已选科目对应凭证中，对方科目分录行上的 tag；筛选时按整凭证匹配。"
        />
      )}
      <Space direction="vertical" style={{ width: '100%', marginTop: 8 }} size="small">
        <Select
          allowClear
          showSearch
          style={{ width: '100%' }}
          placeholder="不限定（请先选择维度分类）"
          value={activeCategory}
          options={categoryOptions}
          onChange={onCategoryChange}
          optionFilterProp="label"
        />
        <Input
          allowClear
          prefix={<SearchOutlined />}
          placeholder="搜索 tag 值"
          value={searchQ}
          disabled={!activeCategory}
          onChange={(e) => setSearchQ(e.target.value)}
        />
        <div style={{ maxHeight: TAG_LIST_MAX_HEIGHT, overflowY: 'auto' }}>
          {!accountCodes.length ? (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="请先选择科目" />
          ) : !activeCategory ? (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="选择维度分类后可检索" />
          ) : loading ? (
            <Text type="secondary">加载中…</Text>
          ) : !items.length ? (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="无匹配 tag" />
          ) : (
            <Space direction="vertical" style={{ width: '100%' }} size={4}>
              {items.map((tag) => {
                const value = tagValueKey(tag)
                const included = selectedSet?.has(value) ?? false
                return (
                  <div
                    key={`${tag.tag_value}-${tag.display_name || ''}`}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: 8,
                      padding: '4px 0',
                      borderBottom: '1px dashed #f0f0f0',
                    }}
                  >
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <Text ellipsis style={{ display: 'block', fontSize: 12 }}>
                        {value}
                      </Text>
                      <Text type="secondary" style={{ fontSize: 11 }}>
                        {tag.count} 条
                      </Text>
                    </div>
                    <Space size={4}>
                      {included ? <Tag color="green">已选</Tag> : <Tag>未选</Tag>}
                      <Button
                        type="link"
                        size="small"
                        icon={<PlusOutlined />}
                        onClick={() => handleAdd(tag)}
                      >
                        加入
                      </Button>
                    </Space>
                  </div>
                )
              })}
            </Space>
          )}
        </div>
      </Space>
    </div>
  )
}
