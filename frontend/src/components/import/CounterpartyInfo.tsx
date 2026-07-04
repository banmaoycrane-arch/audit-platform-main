import { Card, Typography, Tag, Space, Avatar, Divider } from 'antd'
import { UserOutlined, BuildOutlined, LinkOutlined } from '@ant-design/icons'
import type { Counterparty, AccountingEntry } from '../../api/client'

const { Title, Text } = Typography

interface CounterpartyInfoProps {
  entry: AccountingEntry
  counterparty?: Counterparty
}

export function CounterpartyInfo({ entry, counterparty }: CounterpartyInfoProps) {
  const counterpartyName = counterparty?.name || entry.counterparty || '-'
  const hasCounterparty = !!counterparty || !!entry.counterparty

  if (!hasCounterparty) {
    return (
      <Card size="small" style={{ marginBottom: 12 }}>
        <Title level={5} style={{ marginBottom: 8 }}>
          往来单位
          <Tag color="default" style={{ marginLeft: 8 }}>无</Tag>
        </Title>
        <Text type="secondary" style={{ fontSize: 12 }}>未识别到往来单位</Text>
      </Card>
    )
  }

  return (
    <Card size="small" style={{ marginBottom: 12 }}>
      <Title level={5} style={{ marginBottom: 12 }}>
        往来单位
        {counterparty && <Tag color="green" style={{ marginLeft: 8 }}>已关联</Tag>}
        {!counterparty && <Tag color="orange" style={{ marginLeft: 8 }}>待关联</Tag>}
      </Title>

      <Space direction="vertical" style={{ width: '100%' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <Avatar
            size={40}
            icon={counterparty?.role === 'individual' ? <UserOutlined /> : <BuildOutlined />}
            style={{
              backgroundColor: counterparty ? '#52c41a' : '#faad14',
            }}
          />
          <div style={{ flex: 1 }}>
            <Text strong style={{ fontSize: 14 }}>{counterpartyName}</Text>
            {counterparty && counterparty.role && (
              <span style={{ marginLeft: 8 }}>
                <Tag color="blue">{counterparty.role === 'individual' ? '个人' : '企业'}</Tag>
              </span>
            )}
          </div>
        </div>

        {counterparty && (
          <Space direction="vertical" style={{ width: '100%', marginTop: 8 }}>
            <Divider style={{ margin: '8px 0' }} />

            {counterparty.unified_credit_no && (
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
                <Text type="secondary" style={{ fontSize: 12 }}>统一社会信用代码</Text>
                <span style={{ fontSize: 12 }}>{counterparty.unified_credit_no}</span>
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
              <Text type="secondary" style={{ fontSize: 12 }}>是否关联方</Text>
              <Tag color={counterparty.is_related_party ? 'red' : 'green'}>
                {counterparty.is_related_party ? '是' : '否'}
              </Tag>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
              <Text type="secondary" style={{ fontSize: 12 }}>状态</Text>
              <Tag color={counterparty.is_active ? 'green' : 'gray'}>
                {counterparty.is_active ? '活跃' : '停用'}
              </Tag>
            </div>
          </Space>
        )}

        {!counterparty && entry.counterparty && (
          <div style={{ marginTop: 8, padding: 8, backgroundColor: '#fff7e6', borderRadius: 4 }}>
            <Space size="small" align="center">
              <LinkOutlined style={{ color: '#faad14' }} />
              <Text type="secondary" style={{ fontSize: 12 }}>
                可点击关联到已有往来单位或创建新单位
              </Text>
            </Space>
          </div>
        )}
      </Space>
    </Card>
  )
}
