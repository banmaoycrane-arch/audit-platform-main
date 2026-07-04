import { Card, Typography, Space, Tag, Divider } from 'antd'
import type { AccountingEntry } from '../../api/client'

const { Title, Text } = Typography

interface AccountCompareViewProps {
  entry: AccountingEntry
}

export function AccountCompareView({ entry }: AccountCompareViewProps) {
  const originalCode = entry.account_code || '-'
  const originalName = entry.account_name || '-'
  const resolvedCode = entry.resolved_account_code || '-'
  const resolvedName = entry.resolved_account_name || '-'
  const hasChanged = (originalCode !== resolvedCode) || (originalName !== resolvedName)

  return (
    <Card size="small" style={{ marginBottom: 12 }}>
      <Title level={5} style={{ marginBottom: 12 }}>
        科目解析对比
        {hasChanged && <Tag color="orange" style={{ marginLeft: 8 }}>已解析</Tag>}
        {!hasChanged && <Tag color="gray" style={{ marginLeft: 8 }}>无变化</Tag>}
      </Title>

      <Space direction="vertical" style={{ width: '100%' }}>
        <div style={{ display: 'flex', gap: 16 }}>
          <div style={{ flex: 1 }}>
            <Text type="secondary" style={{ fontSize: 12 }}>原始科目</Text>
            <div style={{ marginTop: 4 }}>
              <Text strong>{originalCode}</Text>
              <span style={{ marginLeft: 8 }}>{originalName}</span>
            </div>
          </div>

          <Divider type="vertical" style={{ height: 40 }} />

          <div style={{ flex: 1 }}>
            <Text type="secondary" style={{ fontSize: 12 }}>解析后科目</Text>
            <div style={{ marginTop: 4 }}>
              <Text strong style={{ color: '#1890ff' }}>{resolvedCode}</Text>
              <span style={{ marginLeft: 8, color: '#1890ff' }}>{resolvedName}</span>
            </div>
          </div>
        </div>

        {hasChanged && (
          <div style={{ marginTop: 8, padding: 8, backgroundColor: '#e6f7ff', borderRadius: 4 }}>
            <Text type="secondary" style={{ fontSize: 12 }}>解析说明：</Text>
            <span style={{ fontSize: 12, marginLeft: 4 }}>
              {entry.account_code && entry.resolved_account_code && 
               entry.account_code.length > entry.resolved_account_code.length
                ? '科目已扁平化，下级段转为辅助核算标签'
                : '科目层级已保留'}
            </span>
          </div>
        )}
      </Space>
    </Card>
  )
}
