import { Alert, Button, Space, Tag, Typography } from 'antd'
import { useNavigate } from 'react-router-dom'

const { Text } = Typography

interface GuestGuideBannerProps {
  missingBindings: string[]
}

const bindingLabels: Record<string, string> = {
  team: '团队',
  ledger: '账簿',
  project: '项目',
  accounting_entity: '会计主体',
}

export function GuestGuideBanner({ missingBindings }: GuestGuideBannerProps) {
  const navigate = useNavigate()

  return (
    <Alert
      message="当前为访客/待绑定状态"
      description={
        <div>
          <Text type="secondary">
            您已经可以登录并查看系统模块和公共说明。由于尚未绑定以下内容，系统不会展示任何账簿隔离数据：
          </Text>
          <div style={{ marginTop: 8, marginBottom: 12 }}>
            {missingBindings.map((key) => (
              <Tag color="orange" key={key}>
                {bindingLabels[key] || key}
              </Tag>
            ))}
          </div>
          <Text type="secondary">
            请通过以下入口申请绑定鉴权：
          </Text>
        </div>
      }
      type="warning"
      showIcon
      action={
        <Space>
          <Button size="small" onClick={() => navigate('/team-management')}>
            团队控制台（申请加入团队）
          </Button>
          <Button size="small" onClick={() => navigate('/ledger-management')}>
            账簿控制台（申请访问账簿）
          </Button>
          <Button size="small" onClick={() => navigate('/projects')}>
            项目控制台（申请关联项目）
          </Button>
        </Space>
      }
      style={{ marginBottom: 16 }}
    />
  )
}
