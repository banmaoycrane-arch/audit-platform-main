import { Card, Typography, Tag, Space, Badge } from 'antd'
import type { EntryTag } from '../../api/client'

const { Title, Text } = Typography

const TAG_CATEGORY_COLORS: Record<string, { color: string; bgColor: string; label: string }> = {
  customer: { color: '#1890ff', bgColor: '#e6f7ff', label: '客户' },
  supplier: { color: '#52c41a', bgColor: '#f6ffed', label: '供应商' },
  product: { color: '#722ed1', bgColor: '#f9f0ff', label: '产品' },
  material: { color: '#722ed1', bgColor: '#f9f0ff', label: '材料' },
  department: { color: '#fa8c16', bgColor: '#fff7e6', label: '部门' },
  project: { color: '#eb2f96', bgColor: '#fff0f6', label: '项目' },
  region: { color: '#13c2c2', bgColor: '#e6fffb', label: '区域' },
  expense_type: { color: '#faad14', bgColor: '#fffbe6', label: '费用类型' },
  cost_element: { color: '#2f54eb', bgColor: '#f0f5ff', label: '成本要素' },
  counterparty_object: { color: '#fa541c', bgColor: '#fff2e8', label: '往来对象' },
  tax_type: { color: '#d4380d', bgColor: '#fff1f0', label: '税费类型' },
}

function getTagCategoryInfo(categoryCode: string) {
  return TAG_CATEGORY_COLORS[categoryCode] || {
    color: '#8c8c8c',
    bgColor: '#f5f5f5',
    label: categoryCode,
  }
}

interface TagListProps {
  tags: EntryTag[]
  entryId?: number
}

export function TagList({ tags, entryId }: TagListProps) {
  if (!tags || tags.length === 0) {
    return (
      <Card size="small" style={{ marginBottom: 12 }}>
        <Title level={5} style={{ marginBottom: 8 }}>
          辅助核算标签
          <Tag color="default" style={{ marginLeft: 8 }}>无</Tag>
        </Title>
        <Text type="secondary" style={{ fontSize: 12 }}>暂无辅助核算标签</Text>
      </Card>
    )
  }

  return (
    <Card size="small" style={{ marginBottom: 12 }}>
      <Title level={5} style={{ marginBottom: 12 }}>
        辅助核算标签
        <Tag color="blue" style={{ marginLeft: 8 }}>{tags.length}个</Tag>
      </Title>

      <Space wrap size="small">
        {tags.map((tag) => {
          const info = getTagCategoryInfo(tag.category_code)
          return (
            <div
              key={tag.id}
              style={{
                backgroundColor: info.bgColor,
                borderRadius: 4,
                padding: '4px 8px',
                border: `1px solid ${info.color}20`,
              }}
            >
              <Space size="small">
                <Badge
                  color={info.color}
                  text={
                    <span style={{ fontSize: 12, fontWeight: 500 }}>{info.label}</span>
                  }
                />
                <span style={{ fontSize: 12, color: info.color }}>{tag.display_name}</span>
                {tag.confidence && (
                  <span style={{ fontSize: 11, color: '#999' }}>
                    {(tag.confidence * 100).toFixed(0)}%
                  </span>
                )}
                {tag.tag_source === 'llm' && !tag.reviewed_by_user && (
                  <Tag color="orange">待审批</Tag>
                )}
                {tag.tag_source === 'llm' && tag.reviewed_by_user && (
                  <Tag color="green">已审批</Tag>
                )}
              </Space>
            </div>
          )
        })}
      </Space>
    </Card>
  )
}

export function TagCategoryLegend() {
  return (
    <Card size="small" style={{ marginBottom: 12 }}>
      <Title level={5} style={{ marginBottom: 12 }}>标签类别图例</Title>
      <Space wrap size="small">
        {Object.entries(TAG_CATEGORY_COLORS).map(([code, info]) => (
          <div
            key={code}
            style={{
              backgroundColor: info.bgColor,
              borderRadius: 4,
              padding: '4px 8px',
              border: `1px solid ${info.color}20`,
            }}
          >
            <Space size="small">
              <Badge color={info.color} text={<span style={{ fontSize: 12 }}>{info.label}</span>} />
            </Space>
          </div>
        ))}
      </Space>
    </Card>
  )
}
