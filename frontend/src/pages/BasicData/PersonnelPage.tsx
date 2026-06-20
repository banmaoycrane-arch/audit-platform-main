import { Card, List, Typography } from 'antd'

const { Paragraph } = Typography

const personnelItems = [
  '真实员工：企业签订劳动合同并纳入组织架构、权限、费用归集和绩效考核的人员。',
  '虚拟员工：外部协作单位人员、顾问、项目制人员等，可用于费用归集和责任追踪，但应关联真实往来单位或合同主体。',
  '人员基础资料后续可与报销、薪酬、项目成本、内部控制审批流联动。',
]

export function PersonnelPage() {
  return (
    <Card title="员工/协作人员">
      <Paragraph>
        人员资料用于识别业务经办人、审批人、费用承担人和内部责任主体。财务上要区分真实员工与外部协作人员，避免把外部单位责任误归到内部员工。
      </Paragraph>
      <List bordered dataSource={personnelItems} renderItem={(item) => <List.Item>{item}</List.Item>} />
    </Card>
  )
}
