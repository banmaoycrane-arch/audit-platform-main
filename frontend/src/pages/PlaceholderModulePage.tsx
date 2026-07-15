import { Alert, Card, List, Typography } from 'antd'

const { Paragraph, Text } = Typography

type PlaceholderModulePageProps = {
  title: string
  description: string
  items?: string[]
}

export function PlaceholderModulePage({ title, description, items = [] }: PlaceholderModulePageProps) {
  return (
    <Card title={title}>
      <Alert
        type="warning"
        showIcon
        title="功能尚未开发"
        description="当前页面为产品规划占位，暂无正式业务处理能力。请使用「财务总账」或「审计系统」完成 MVP 验收路径。"
        style={{ marginBottom: 16 }}
      />
      <Paragraph>{description}</Paragraph>
      {items.length > 0 && (
        <List
          size="small"
          bordered
          dataSource={items}
          renderItem={(item) => (
            <List.Item>
              <Text>{item}</Text>
            </List.Item>
          )}
        />
      )}
    </Card>
  )
}
