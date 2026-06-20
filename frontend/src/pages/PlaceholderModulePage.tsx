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
        type="info"
        showIcon
        message="预留功能，待接入真实数据"
        description="当前页面用于说明业务边界和后续建设方向，暂不代表该模块已完成正式业务处理。"
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
