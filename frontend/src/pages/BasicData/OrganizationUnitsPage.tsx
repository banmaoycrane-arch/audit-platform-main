import { Alert, Card, List, Typography } from 'antd'

const { Paragraph, Text } = Typography

const organizationItems = [
  {
    title: '实体组织',
    description: '以法人公司、分支机构、门店或可明确承担责任的经营单元为基础，是财务核算和审计追责的底层对象。',
  },
  {
    title: '虚拟事业部',
    description: '用于内部管理口径拆分收入、成本和绩效，但必须绑定至少一个实体组织，不能脱离真实业务主体。',
  },
  {
    title: '子公司/分公司',
    description: '承接法定报表、税务申报、合并范围和内部往来识别，是总账和审计范围的重要维度。',
  },
  {
    title: '内部考核单元',
    description: '用于管理会计和责任中心考核，可服务项目组、区域、渠道等多维核算。',
  },
]

export function OrganizationUnitsPage() {
  return (
    <Card title="企业组织架构">
      <Alert
        type="warning"
        showIcon
        message="虚拟核算单位必须依托至少一个实体核算对象"
        description="虚拟组织只能作为管理口径，不能替代法人、分支机构、门店等真实承担业务和责任的实体对象。"
        style={{ marginBottom: 16 }}
      />
      <Paragraph>
        组织架构是会计主体、纳税主体、管理主体和审计范围的共同基础。先维护实体组织，再在其上建立虚拟事业部或内部考核单元，能避免财务数据没有责任主体。
      </Paragraph>
      <List
        grid={{ gutter: 16, xs: 1, sm: 2, md: 2, lg: 2 }}
        dataSource={organizationItems}
        renderItem={(item) => (
          <List.Item>
            <Card size="small" title={item.title}>
              <Text>{item.description}</Text>
            </Card>
          </List.Item>
        )}
      />
    </Card>
  )
}
