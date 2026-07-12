import { Card, Col, Row, Typography } from 'antd'
import type { ReactNode } from 'react'
import {
  BookOutlined,
  PartitionOutlined,
  DatabaseOutlined,
  ApartmentOutlined,
  SwapOutlined,
  UnorderedListOutlined,
} from '@ant-design/icons'

const { Text } = Typography

export type AccountingStructureTab =
  | 'coa'
  | 'categories'
  | 'parse-mapping'
  | 'master-values'
  | 'external-mapping'
  | 'pending'

type NavItem = {
  key: AccountingStructureTab
  title: string
  description: string
  icon: ReactNode
  requiresLedger?: boolean
  requiresJob?: boolean
}

const NAV_ITEMS: NavItem[] = [
  {
    key: 'coa',
    title: '科目表',
    description: '一级科目与法定明细；税法强制层级保留在此',
    icon: <BookOutlined />,
  },
  {
    key: 'parse-mapping',
    title: '解析映射',
    description: '科目下级段 → Tag 分类；与科目表配套设计',
    icon: <PartitionOutlined />,
    requiresLedger: true,
  },
  {
    key: 'categories',
    title: '维度分类',
    description: 'Tag 字典；可新建自定义维度继续细分口径',
    icon: <ApartmentOutlined />,
    requiresLedger: true,
  },
  {
    key: 'master-values',
    title: '维度值主数据',
    description: '银行户、往来单位、共享 Tag 值维护',
    icon: <DatabaseOutlined />,
    requiresLedger: true,
  },
  {
    key: 'external-mapping',
    title: '外部映射',
    description: '旧 ERP 编码对接内部 Tag',
    icon: <SwapOutlined />,
    requiresLedger: true,
  },
  {
    key: 'pending',
    title: '待处理队列',
    description: '导入后规范名、补主数据（需 jobId）',
    icon: <UnorderedListOutlined />,
    requiresLedger: true,
    requiresJob: true,
  },
]

type AccountingStructureNavProps = {
  activeTab: AccountingStructureTab
  hasLedger: boolean
  hasJob: boolean
  onNavigate: (tab: AccountingStructureTab) => void
}

export function AccountingStructureNav({
  activeTab,
  hasLedger,
  hasJob,
  onNavigate,
}: AccountingStructureNavProps) {
  return (
    <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
      {NAV_ITEMS.map((item) => {
        const disabled =
          (item.requiresLedger && !hasLedger) || (item.requiresJob && !hasJob)
        const active = activeTab === item.key
        return (
          <Col xs={24} sm={12} md={8} lg={4} key={item.key}>
            <Card
              size="small"
              hoverable={!disabled}
              onClick={() => {
                if (!disabled) onNavigate(item.key)
              }}
              style={{
                height: '100%',
                cursor: disabled ? 'not-allowed' : 'pointer',
                opacity: disabled ? 0.55 : 1,
                borderColor: active ? '#1677ff' : undefined,
                background: active ? '#f0f5ff' : undefined,
              }}
            >
              <div style={{ fontSize: 18, marginBottom: 4, color: active ? '#1677ff' : undefined }}>
                {item.icon}
              </div>
              <Text strong style={{ fontSize: 13 }}>
                {item.title}
              </Text>
              <div>
                <Text type="secondary" style={{ fontSize: 11, lineHeight: 1.4 }}>
                  {item.description}
                </Text>
              </div>
            </Card>
          </Col>
        )
      })}
    </Row>
  )
}
